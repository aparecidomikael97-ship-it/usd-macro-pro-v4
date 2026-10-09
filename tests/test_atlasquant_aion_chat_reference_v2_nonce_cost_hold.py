"""CI-only V2 nonce/cost reference ledger tests: synthetic keys, mock model only."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
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
from atlasquant_aion_chat_signed_full_request_review_v2 import (
    APPROVAL_SCHEMA, PURPOSE, ROLE, canonical_full_request_approval_v2,
)
from atlasquant_aion_chat_reference_nonce_budget_hold_v1 import ReferenceNonceBudgetLedger
from atlasquant_aion_chat_reference_v2_nonce_cost_hold import (
    ReferenceV2NonceCostLedger, REFERENCE_HELD, REFERENCE_REPLAY,
)
from atlasquant_aion_provider import preview_openai_request_binding


def owner_access():
    return {
        "allowed": True, "mode": "AUTHENTICATED", "role": "ADMIN",
        "session": {
            "role": "ADMIN", "username": "owner",
            "credential_fingerprint": "ci-fixture-fingerprint",
            "permissions": ["app:read", "aion:admin"],
        },
    }


class V2NonceCostHoldTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.chat_path = Path(self.temp.name) / "chat.db"
        self.ledger_path = Path(self.temp.name) / "holds-v2.db"
        self.chat = SQLiteChatStore(self.chat_path)
        self.scope = Scope("owner", "tenant", "workspace")
        self.cid = self.chat.create_conversation(self.scope, "AION").id
        self.key = Ed25519PrivateKey.generate()
        self.pin = {
            "key_id": "synthetic-owner-key",
            "public_key_hex": self.key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            ).hex(),
        }
        self.env = {
            "AION_MODEL_PROVIDER": "openai",
            "OPENAI_API_KEY": "synthetic-not-production",
            "AION_OPENAI_FAST_MODEL": "fixture-fast",
            "AION_OPENAI_REASONING_MODEL": "fixture-reasoning",
            "AION_OPENAI_INPUT_USD_PER_MTOK": "1",
            "AION_OPENAI_OUTPUT_USD_PER_MTOK": "2",
            "AION_OPENAI_MAX_OUTPUT_TOKENS": "500",
            "AION_OPENAI_TIMEOUT_SECONDS": "45",
        }
        self.ledger = self._open()
        self.first = self.make_intent("request-0001", "Explique inflação",
                                      "ab"*32)

    def _open(self, **kwargs):
        conf = {
            "scope": self.scope, "period_id": "2026-10",
            "policy_generation": 7, "owner_public_pin": self.pin,
            "limit_micro_usd": 220,
        }
        conf.update(kwargs)
        return ReferenceV2NonceCostLedger(self.ledger_path, **conf)

    def tearDown(self):
        self.chat.db.close()
        self.ledger.close()
        self.temp.cleanup()

    def make_intent(self, request_id, source, nonce, *, cap=100):
        pending = stage_pending_model_user_turn(
            self.chat, self.scope, owner_access(),
            conversation_id=self.cid, request_id=request_id,
            message=source,
        )
        prompt = "AION responde em português claro: " + source
        preview = preview_openai_request_binding(
            prompt, lane="EXTERNAL_FAST", values=self.env,
        )
        self.assertEqual(preview["state"], "BOUND_REQUEST_PREVIEW_UNTRUSTED")
        payload = {
            "schema": APPROVAL_SCHEMA,
            "purpose": PURPOSE,
            "role": ROLE,
            "owner_key_id": self.pin["key_id"],
            "owner_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "conversation_id": self.cid,
            "message_id": pending["message_id"],
            "request_digest": pending["request_digest"],
            "source_message_sha256": pending["message_sha256"],
            "final_prompt_sha256": sha256(prompt.encode("utf-8")).hexdigest(),
            "full_provider_request_sha256": preview["request_sha256"],
            "provider_id": preview["provider"],
            "model_id": preview["resolved_model"],
            "lane": preview["lane"],
            "endpoint": preview["endpoint"],
            "max_output_tokens": preview["max_output_tokens"],
            "timeout_seconds_repr": repr(preview["timeout_seconds"]),
            "max_cost_micro_usd": cap,
            "policy_generation": 7,
            "nonce_hex": nonce,
        }
        return {"pending": pending, "prompt": prompt, "payload": payload}

    def signed(self, intent, *, payload=None, key=None):
        p = deepcopy(intent["payload"] if payload is None else payload)
        return {
            "payload": p,
            "signature_hex": (key or self.key).sign(
                canonical_full_request_approval_v2(p),
            ).hex(),
        }

    def reserve(self, intent=None, *, envelope=None, quote=80,
                pin=None, values=None, ledger=None, access=None):
        intent = self.first if intent is None else intent
        result = (ledger or self.ledger).hold_reference_only(
            self.chat, owner_access() if access is None else access,
            conversation_id=self.cid,
            message_id=intent["pending"]["message_id"],
            final_prompt=intent["prompt"],
            envelope=self.signed(intent) if envelope is None else envelope,
            host_public_pin=self.pin if pin is None else pin,
            host_quote_micro_usd=quote,
            provider_values=self.env if values is None else values,
        )
        self.assertIs(result["model_invocation_authorized"], False)
        self.assertIs(result["real_budget_reserved"], False)
        self.assertIs(result["provider_called"], False)
        self.assertIs(result["safe_to_resume"], False)
        return result

    def test_v2_reference_holds_entire_signed_maximum_not_quote(self):
        result = self.reserve()
        self.assertEqual(result["state"], REFERENCE_HELD)
        self.assertEqual(result["reference_hold_micro_usd"], 100)
        snap = self.ledger.reference_snapshot()
        self.assertEqual(snap["held_micro_usd"], 100)
        self.assertEqual(snap["hold_count"], 1)

    def test_identical_replay_is_read_only_and_not_double_charged(self):
        self.assertEqual(self.reserve()["state"], REFERENCE_HELD)
        self.assertEqual(self.reserve()["state"], REFERENCE_REPLAY)
        self.assertEqual(self.reserve(quote=90)["state"], REFERENCE_REPLAY)
        self.assertEqual(self.ledger.reference_snapshot()["held_micro_usd"], 100)

    def test_distinct_v2_nonce_competing_for_same_message_rejected(self):
        self.reserve()
        p = deepcopy(self.first["payload"])
        p["nonce_hex"] = "bc"*32
        result = self.reserve(envelope=self.signed(self.first, payload=p))
        self.assertEqual(result["reason"], "MESSAGE_ALREADY_HAS_REFERENCE_HOLD")

    def test_v2_nonce_reused_for_different_scoped_message_rejected(self):
        self.reserve()
        second = self.make_intent("request-0002", "Explique desemprego",
                                  "ab"*32)
        result = self.reserve(second)
        self.assertEqual(result["reason"], "NONCE_ALREADY_BOUND_DIFFERENTLY")

    def test_v2_monthly_reference_cap_is_atomic_and_no_refund(self):
        self.reserve()
        second = self.make_intent("request-0002", "Explique juros",
                                  "cd"*32, cap=110)
        self.assertEqual(self.reserve(second)["state"], REFERENCE_HELD)
        third = self.make_intent("request-0003", "Explique emprego",
                                 "ef"*32, cap=30)
        self.assertEqual(self.reserve(third, quote=20)["reason"], "REFERENCE_BUDGET_EXCEEDED")
        self.assertEqual(self.ledger.reference_snapshot()["held_micro_usd"], 210)

    def test_no_host_quote_higher_than_signed_cost(self):
        self.assertEqual(self.reserve(quote=101)["state"], "BLOCKED")
        self.assertEqual(self.ledger.reference_snapshot()["hold_count"], 0)
        for val in (None, True, 0, -1, "80", 80.0, 2_000_000_001):
            with self.subTest(quote=repr(val)):
                self.assertEqual(self.reserve(quote=val)["state"], "BLOCKED")
        self.assertEqual(self.ledger.reference_snapshot()["hold_count"], 0)

    def test_v2_model_timeout_or_token_mutation_blocks_before_hold(self):
        for field, value in (
            ("AION_OPENAI_FAST_MODEL", "different-model"),
            ("AION_OPENAI_MAX_OUTPUT_TOKENS", "501"),
            ("AION_OPENAI_TIMEOUT_SECONDS", "12"),
        ):
            with self.subTest(field=field):
                changed = dict(self.env)
                changed[field] = value
                self.assertEqual(self.reserve(values=changed)["state"], "BLOCKED")
        self.assertEqual(self.ledger.reference_snapshot()["hold_count"], 0)

    def test_old_v1_signed_envelope_cannot_create_v2_reference_hold(self):
        p = deepcopy(self.first["payload"])
        p.pop("full_provider_request_sha256")
        p["schema"] = "ATLASQUANT_AION_CHAT_OWNER_MODEL_APPROVAL_PAYLOAD_V1"
        self.assertEqual(self.reserve(envelope={
            "payload": p, "signature_hex": "a"*128,
        })["state"], "BLOCKED")

    def test_forged_signed_content_or_public_pin_does_not_hold(self):
        p = deepcopy(self.first["payload"])
        p["max_cost_micro_usd"] = 200
        forged_envelope = self.signed(self.first)
        forged_envelope["payload"]["max_cost_micro_usd"] = 200
        self.assertEqual(self.reserve(envelope=forged_envelope)["state"], "BLOCKED")
        other_key = Ed25519PrivateKey.generate()
        other_pin = dict(self.pin)
        other_pin["public_key_hex"] = other_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()
        self.assertEqual(self.reserve(pin=other_pin)["state"], "BLOCKED")
        self.assertEqual(self.ledger.reference_snapshot()["hold_count"], 0)

    def test_reopen_preserves_v2_and_rejects_policy_cap_or_period_changes(self):
        self.reserve()
        self.ledger.close()
        self.ledger = self._open()
        self.assertEqual(self.reserve()["state"], REFERENCE_REPLAY)
        for kw in ({"policy_generation": 8},
                   {"limit_micro_usd": 300},
                   {"period_id": "2026-11"},
                   {"scope": Scope("other", "tenant", "workspace")}):
            with self.subTest(config=kw):
                with self.assertRaisesRegex(ValueError, "config/pin mismatch"):
                    self._open(**kw)

    def test_v1_reference_db_refused_without_silent_data_migration(self):
        legacy_path = Path(self.temp.name)/"legacy-v1.db"
        old = ReferenceNonceBudgetLedger(
            legacy_path, scope=self.scope, period_id="2026-10",
            policy_generation=7, owner_public_pin=self.pin,
            limit_micro_usd=220,
        )
        old.close()
        with self.assertRaisesRegex(ValueError, "V1/unknown"):
            ReferenceV2NonceCostLedger(
                legacy_path, scope=self.scope, period_id="2026-10",
                policy_generation=7, owner_public_pin=self.pin,
                limit_micro_usd=220,
            )

    def test_reference_totals_corruption_blocks_all_new_holds(self):
        self.reserve()
        self.ledger.db.execute(
            "UPDATE reference_v2_config SET held_total_micro_usd=0 WHERE singleton=1"
        )
        second = self.make_intent("request-0002", "Explique juros", "dd"*32)
        self.assertEqual(self.reserve(second)["state"], "BLOCKED")
        self.assertEqual(self.ledger.reference_snapshot()["state"], "BLOCKED")

    def test_record_scope_corruption_detected(self):
        self.reserve()
        self.ledger.db.execute(
            "UPDATE reference_v2_holds SET full_request_sha256=? WHERE nonce_hex=?",
            ("bad-digest", "ab"*32),
        )
        self.assertEqual(self.ledger.reference_snapshot()["state"], "BLOCKED")

    def test_failed_atomic_transaction_rolls_back_without_partial_hold(self):
        self.ledger.db.execute(
            """CREATE TRIGGER abort_v2 BEFORE UPDATE ON reference_v2_config
               BEGIN SELECT RAISE(ABORT, 'synthetic write error'); END;"""
        )
        self.assertEqual(self.reserve()["state"], "BLOCKED")
        self.assertEqual(self.ledger.reference_snapshot()["hold_count"], 0)
        self.ledger.db.execute("DROP TRIGGER abort_v2")
        self.assertEqual(self.reserve()["state"], REFERENCE_HELD)

    def test_read_only_verifier_and_hold_never_dispatch_provider(self):
        with patch("requests.post", side_effect=AssertionError("network forbidden")), \
             patch("atlasquant_aion_provider.execute_openai_answer",
                   side_effect=AssertionError("model forbidden")):
            self.assertEqual(self.reserve()["state"], REFERENCE_HELD)
        self.assertFalse(self.ledger.reference_snapshot()["real_billing_authorized"])

    def test_concurrent_same_nonce_is_one_hold_in_db(self):
        def worker(_):
            chat = SQLiteChatStore(self.chat_path)
            local = self._open()
            try:
                intent = self.first
                r = local.hold_reference_only(
                    chat, owner_access(), conversation_id=self.cid,
                    message_id=intent["pending"]["message_id"],
                    final_prompt=intent["prompt"],
                    envelope=self.signed(intent),
                    host_public_pin=self.pin,
                    host_quote_micro_usd=80,
                    provider_values=self.env,
                )
                return r["state"]
            finally:
                local.close()
                chat.db.close()
        with ThreadPoolExecutor(max_workers=4) as pool:
            result = list(pool.map(worker, range(6)))
        self.assertEqual(result.count(REFERENCE_HELD), 1)
        self.assertEqual(result.count(REFERENCE_REPLAY), 5)
        self.assertEqual(self.ledger.reference_snapshot()["hold_count"], 1)


if __name__ == "__main__":
    unittest.main()
