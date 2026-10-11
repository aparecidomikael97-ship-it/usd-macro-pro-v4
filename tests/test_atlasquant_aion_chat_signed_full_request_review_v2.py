"""V2 full-request signed-turn adversarial CI only, disposable keys/store."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_chat_pending_model_turn_v1 import stage_pending_model_user_turn
from atlasquant_aion_chat_signed_turn_review_v1 import (
    FALSE_GATES as V1_FALSE, APPROVAL_SCHEMA as V1_SCHEMA,
)
from atlasquant_aion_chat_signed_full_request_review_v2 import (
    SCHEMA, APPROVAL_SCHEMA, PURPOSE, ROLE, DOMAIN, CANDIDATE,
    EXTRA_FALSE_GATES, canonical_full_request_approval_v2,
    review_signed_full_provider_request_v2,
)
from atlasquant_aion_provider import preview_openai_request_binding


def access(username="owner", role="ADMIN"):
    return {
        "allowed": True, "mode": "AUTHENTICATED", "role": role,
        "session": {
            "role": role, "username": username,
            "credential_fingerprint": "ci-fingerprint-fixture",
            "permissions": ["app:read", "aion:admin"],
        },
    }


class SignedFullRequestReviewV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SQLiteChatStore(Path(self.temp.name) / "chat.db")
        self.scope = Scope("owner", "tenant", "workspace")
        self.cid = self.store.create_conversation(self.scope, "AION").id
        self.source = "Explique inflação e seus efeitos"
        self.pending = stage_pending_model_user_turn(
            self.store, self.scope, access(),
            conversation_id=self.cid, request_id="request-v2-123456",
            message=self.source,
        )
        self.prompt = "Responda em português, com acentuação 😀:\n" + self.source
        self.env = {
            "AION_MODEL_PROVIDER": "openai",
            "OPENAI_API_KEY": "fixture-value-not-a-secret",
            "AION_OPENAI_FAST_MODEL": "mock-fast-model",
            "AION_OPENAI_REASONING_MODEL": "mock-reasoning-model",
            "AION_OPENAI_INPUT_USD_PER_MTOK": "1",
            "AION_OPENAI_OUTPUT_USD_PER_MTOK": "2",
            "AION_OPENAI_MAX_OUTPUT_TOKENS": "400",
            "AION_OPENAI_TIMEOUT_SECONDS": "45",
        }
        self.key = Ed25519PrivateKey.generate()
        public = self.key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.pin = {"key_id": "ci-owner-key",
                    "public_key_hex": public.hex()}
        preview = preview_openai_request_binding(
            self.prompt, lane="EXTERNAL_FAST", values=self.env,
        )
        assert preview["state"] == "BOUND_REQUEST_PREVIEW_UNTRUSTED"
        self.payload = {
            "schema": APPROVAL_SCHEMA, "purpose": PURPOSE,
            "role": ROLE, "owner_key_id": self.pin["key_id"],
            "owner_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "conversation_id": self.cid,
            "message_id": self.pending["message_id"],
            "request_digest": self.pending["request_digest"],
            "source_message_sha256": sha256(self.source.encode("utf-8")).hexdigest(),
            "final_prompt_sha256": sha256(self.prompt.encode("utf-8")).hexdigest(),
            "full_provider_request_sha256": preview["request_sha256"],
            "provider_id": preview["provider"],
            "model_id": preview["resolved_model"],
            "lane": preview["lane"],
            "endpoint": preview["endpoint"],
            "max_output_tokens": preview["max_output_tokens"],
            "timeout_seconds_repr": repr(preview["timeout_seconds"]),
            "max_cost_micro_usd": 2000,
            "policy_generation": 7,
            "nonce_hex": "ac"*32,
        }

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def signed(self, payload=None, key=None):
        p = deepcopy(self.payload if payload is None else payload)
        return {
            "payload": p,
            "signature_hex": (key or self.key).sign(
                canonical_full_request_approval_v2(p),
            ).hex(),
        }

    def review(self, envelope=None, **kwargs):
        options = {
            "conversation_id": self.cid,
            "message_id": self.pending["message_id"],
            "final_prompt": self.prompt,
            "envelope": self.signed() if envelope is None else envelope,
            "host_public_pin": self.pin,
            "expected_policy_generation": 7,
            "provider_values": self.env,
            "host_quote_micro_usd": 1000,
        }
        options.update(kwargs)
        result = review_signed_full_provider_request_v2(
            self.store, self.scope, access(), **options,
        )
        self.assertEqual(result["schema"], SCHEMA)
        self.assertTrue(result["reference_only"])
        for flags in (V1_FALSE, EXTRA_FALSE_GATES):
            for field, expected in flags.items():
                self.assertIs(result[field], expected, field)
        return result

    def test_valid_v2_math_does_not_grant_any_operational_authority(self):
        result = self.review()
        self.assertEqual(result["state"], CANDIDATE)
        self.assertTrue(result["resolved_full_request_matched"])
        self.assertTrue(result["stored_pending_user_message_matched"])
        self.assertTrue(result["public_signature_math_valid"])
        self.assertEqual(len(result["signed_payload_sha256"]), 64)
        self.assertFalse(result["model_invocation_authorized"])
        self.assertFalse(result["anti_replay_verified"])
        self.assertFalse(result["owner_public_key_enrollment_verified"])
        self.assertFalse(result["real_budget_reserved"])

    def test_replay_is_math_only_and_does_not_consume_nonce(self):
        signed = self.signed()
        first, second = self.review(signed), self.review(signed)
        self.assertEqual(first, second)
        self.assertEqual(first["state"], CANDIDATE)
        self.assertFalse(second["nonce_reserved_or_consumed"])
        self.assertEqual(self.store.get_conversation(self.scope, self.cid).message_count, 1)

    def test_domain_is_distinct_from_v1(self):
        self.assertTrue(DOMAIN.endswith(b"\x00"))
        self.assertIn(b"V2", DOMAIN)
        self.assertNotEqual(APPROVAL_SCHEMA, V1_SCHEMA)

    def test_v1_schema_even_if_resigned_must_not_upgrade_to_v2(self):
        p = deepcopy(self.payload)
        p["schema"] = V1_SCHEMA
        with self.assertRaisesRegex(ValueError, "V2"):
            canonical_full_request_approval_v2({k:v for k,v in p.items() if k!="full_provider_request_sha256"})
        with self.assertRaisesRegex(ValueError, "V2"):
            canonical_full_request_approval_v2({k:v for k,v in p.items() if k!="max_output_tokens"})
        e = self.signed()
        e["payload"]["schema"] = V1_SCHEMA
        self.assertEqual(self.review(e)["state"], "BLOCKED")

    def test_existing_v1_signature_cannot_verify_as_v2(self):
        e = self.signed()
        p = e["payload"]
        legacy_message = b"ATLASQUANT_AION_CHAT_OWNER_MODEL_APPROVAL_V1\x00" + __import__("json").dumps(
            p, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        e["signature_hex"] = self.key.sign(legacy_message).hex()
        self.assertEqual(self.review(e)["reason"], "V2_SIGNATURE_MATH_INVALID")

    def test_purpose_role_key_and_unknown_authority_fields_are_rejected(self):
        for name, bad in (
            ("purpose","APPROVE_PAID_CALL_NOW"),
            ("role","COLLECTOR_ED25519"),
            ("owner_key_id","fake-key"),
        ):
            with self.subTest(name=name):
                e = self.signed()
                e["payload"][name] = bad
                self.assertEqual(self.review(e)["state"], "BLOCKED")
        for field in ("safe_to_resume", "owner_approved"):
            e = self.signed()
            e["payload"][field] = True
            self.assertEqual(self.review(e)["reason"], "SIGNED_V2_SCHEMA_REQUIRED_NO_V1_FALLBACK")

    def test_missing_any_v2_field_blocks_and_never_falls_back(self):
        for field in self.payload:
            with self.subTest(field=field):
                e = self.signed()
                e["payload"].pop(field)
                self.assertEqual(self.review(e)["state"], "BLOCKED")
        for name in ("payload", "signature_hex"):
            e = self.signed()
            e.pop(name)
            self.assertEqual(self.review(e)["state"], "BLOCKED")

    def test_tamper_payload_after_signature_is_not_valid(self):
        e = self.signed()
        e["payload"]["max_cost_micro_usd"] += 1
        self.assertEqual(self.review(e)["reason"], "V2_SIGNATURE_MATH_INVALID")
        e = self.signed()
        e["signature_hex"] = "0"*128
        self.assertEqual(self.review(e)["reason"], "V2_SIGNATURE_MATH_INVALID")

    def test_runtime_model_token_limit_timeout_endpoint_or_lane_change_blocks(self):
        mutations = [
            ("AION_OPENAI_FAST_MODEL", "another-model"),
            ("AION_OPENAI_MAX_OUTPUT_TOKENS", "401"),
            ("AION_OPENAI_TIMEOUT_SECONDS", "8.5"),
            ("AION_MODEL_PROVIDER", "offline"),
        ]
        for field, value in mutations:
            with self.subTest(field=field):
                other = dict(self.env)
                other[field] = value
                self.assertEqual(self.review(provider_values=other)["state"], "BLOCKED")
        with patch("atlasquant_aion_provider.OPENAI_RESPONSES_URL",
                   "https://elsewhere.invalid/v1/responses"):
            self.assertEqual(self.review()["reason"],
                             "SIGNED_FULL_REQUEST_OR_RESOLVED_OPTIONS_MISMATCH")
        self.assertEqual(self.review(final_prompt=self.prompt+"!")["state"], "BLOCKED")

    def test_resigned_changes_in_signed_options_still_fail_against_real_preview(self):
        for field, value in (
            ("model_id", "alternate"),
            ("max_output_tokens", 401),
            ("timeout_seconds_repr", "8.5"),
            ("endpoint", "https://elsewhere.invalid/x"),
            ("full_provider_request_sha256", "0"*64),
            ("provider_id", "other"),
            ("lane", "EXTERNAL_REASONING"),
        ):
            with self.subTest(field=field):
                p = deepcopy(self.payload)
                p[field] = value
                self.assertEqual(self.review(self.signed(p))["state"], "BLOCKED")

    def test_reject_higher_host_quote_even_with_good_signature(self):
        result = self.review(host_quote_micro_usd=2001)
        self.assertEqual(result["reason"], "V2_POLICY_OR_MAX_COST_INVALID")
        for quote in (None, True, "1000", -1, 0, 20_000_001):
            self.assertEqual(self.review(host_quote_micro_usd=quote)["state"], "BLOCKED")

    def test_policy_mismatch_rejects_no_downgrade(self):
        self.assertEqual(self.review(expected_policy_generation=8)["state"], "BLOCKED")
        for bad in (True, "7", 0, None):
            self.assertEqual(self.review(expected_policy_generation=bad)["state"], "BLOCKED")

    def test_scope_session_and_stored_message_binding(self):
        self.assertEqual(self.review(message_id="other")["state"], "BLOCKED")
        with patch("atlasquant_aion_chat_signed_full_request_review_v2.validate_product_binding",
                   return_value={"bound":False}):
            self.assertEqual(self.review()["reason"], "SCOPE_AND_SESSION_MISMATCH")
        e = self.signed()
        e["payload"]["tenant_id"] = "cross-tenant"
        self.assertEqual(self.review(e)["state"], "BLOCKED")

    def test_stored_user_content_mutation_is_rejected(self):
        e = self.signed()
        self.store.db.execute(
            "UPDATE messages SET data=replace(data, ?, ?) WHERE id=?",
            ("Explique inflação", "Explique recessão", self.pending["message_id"]),
        )
        self.store.db.commit()
        self.assertEqual(self.review(e)["reason"], "STORED_USER_CONTENT_OR_REQUEST_MISMATCH")

    def test_forged_pin_only_validates_math_not_real_owner(self):
        attacker = Ed25519PrivateKey.generate()
        forged = dict(self.pin)
        forged["public_key_hex"] = attacker.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()
        self.assertEqual(self.review(self.signed(key=attacker))["state"], "BLOCKED")
        forged_result = self.review(self.signed(key=attacker), host_public_pin=forged)
        self.assertEqual(forged_result["state"], CANDIDATE)
        self.assertFalse(forged_result["enrolled_owner_key_verified"])
        self.assertFalse(forged_result["trusted_host_configuration_verified"])

    def test_invalid_nonce_and_signature_types_rejected(self):
        for nonce in ("00", "G"*64, 0, True, None):
            p = deepcopy(self.payload)
            p["nonce_hex"] = nonce
            self.assertEqual(self.review({"payload":p, "signature_hex":"0"*128})["state"], "BLOCKED")
        for signature in (True, 0, None, "ff"):
            self.assertEqual(self.review({"payload":deepcopy(self.payload),
                                          "signature_hex":signature})["state"], "BLOCKED")

    def test_noncanonical_whitespace_or_sensitive_content_is_blocked(self):
        for prompt in (" leading", "trailing ", "senha pessoal", "", " \n "):
            self.assertEqual(self.review(final_prompt=prompt)["state"], "BLOCKED")

    def test_no_network_or_provider_even_when_signature_is_valid(self):
        with patch("requests.post", side_effect=AssertionError("network forbidden")), \
             patch("atlasquant_aion_provider.execute_openai_answer",
                   side_effect=AssertionError("dispatch forbidden")):
            self.assertEqual(self.review()["state"], CANDIDATE)
        self.assertFalse(self.review()["provider_called"])

    def test_provider_preflight_rejects_missing_config_or_untrusted_types(self):
        self.assertEqual(self.review(provider_values={})["state"], "BLOCKED")
        self.assertEqual(self.review(provider_values={"AION_MODEL_PROVIDER":"local"})["state"], "BLOCKED")
        for pin in (None, {"key_id":"abc"}, {"key_id":"abc","public_key_hex":"0"*64,"authority":True}):
            self.assertEqual(self.review(host_public_pin=pin)["state"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
