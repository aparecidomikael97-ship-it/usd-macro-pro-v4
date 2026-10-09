"""Adversarial fake independent witness protocol for AION V2; NO live witness."""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_chat_pending_model_turn_v1 import stage_pending_model_user_turn
from atlasquant_aion_chat_signed_full_request_review_v2 import (
    APPROVAL_SCHEMA, PURPOSE as OWNER_PURPOSE, ROLE as OWNER_ROLE,
    canonical_full_request_approval_v2,
)
from atlasquant_aion_chat_reference_v2_nonce_cost_hold import (
    ReferenceV2NonceCostLedger, REFERENCE_HELD,
)
from atlasquant_aion_provider import preview_openai_request_binding
from atlasquant_aion_v2_external_witness_rollback_reference import (
    SCHEMA, HEAD_SCHEMA, PURPOSE, ROLE, DOMAIN, CANDIDATE,
    NO_AUTHORITY, ZERO, canonical_witness_head, signed_receipt_sha256,
    local_v2_snapshot_commitment, make_unsigned_witness_head_candidate,
    review_witnessed_v2_reference_state,
)


def access():
    return {
        "allowed": True, "mode": "AUTHENTICATED", "role": "ADMIN",
        "session": {
            "role": "ADMIN", "username": "owner",
            "credential_fingerprint": "synthetic-fixture",
            "permissions": ["app:read", "aion:admin"],
        },
    }


class ExternalWitnessRollbackReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.chat_path = base / "chat.db"
        self.ref_path = base / "ledger.db"
        self.chat = SQLiteChatStore(self.chat_path)
        self.scope = Scope("owner", "tenant", "workspace")
        self.cid = self.chat.create_conversation(self.scope, "AION").id
        self.owner_key = Ed25519PrivateKey.generate()
        self.collector_key = Ed25519PrivateKey.generate()
        self.owner_pin = self.pin(self.owner_key, "synthetic-owner")
        self.collector_pin = self.pin(self.collector_key, "synthetic-collector")
        self.env = {
            "AION_MODEL_PROVIDER": "openai",
            "OPENAI_API_KEY": "fixture-unusable-string",
            "AION_OPENAI_FAST_MODEL": "synthetic-model",
            "AION_OPENAI_REASONING_MODEL": "synthetic-reasoning",
            "AION_OPENAI_INPUT_USD_PER_MTOK": "1",
            "AION_OPENAI_OUTPUT_USD_PER_MTOK": "2",
            "AION_OPENAI_MAX_OUTPUT_TOKENS": "200",
            "AION_OPENAI_TIMEOUT_SECONDS": "45",
        }
        self.ledger = self.open_ledger()
        # External memory is NOT stored alongside the locally restorable DB.
        # It is a caller-supplied CI fixture, not an actual remote authority.
        self.external_head = None

    def pin(self, key, key_id):
        return {"key_id": key_id, "public_key_hex":
                key.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                ).hex()}

    def open_ledger(self, **options):
        conf = {
            "scope": self.scope, "period_id": "2026-10",
            "policy_generation": 9, "owner_public_pin": self.owner_pin,
            "limit_micro_usd": 400,
        }
        conf.update(options)
        return ReferenceV2NonceCostLedger(self.ref_path, **conf)

    def tearDown(self):
        self.ledger.close()
        self.chat.db.close()
        self.tmp.cleanup()

    def add_hold(self, request_id, source, nonce, cap=100):
        pending = stage_pending_model_user_turn(
            self.chat, self.scope, access(), conversation_id=self.cid,
            request_id=request_id, message=source,
        )
        prompt = "AION expõe evidências: " + source
        preview = preview_openai_request_binding(
            prompt, lane="EXTERNAL_FAST", values=self.env,
        )
        self.assertEqual(preview["state"], "BOUND_REQUEST_PREVIEW_UNTRUSTED")
        payload = {
            "schema": APPROVAL_SCHEMA,
            "purpose": OWNER_PURPOSE, "role": OWNER_ROLE,
            "owner_key_id": self.owner_pin["key_id"],
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
            "policy_generation": 9,
            "nonce_hex": nonce,
        }
        envelope = {
            "payload": payload,
            "signature_hex": self.owner_key.sign(
                canonical_full_request_approval_v2(payload)
            ).hex(),
        }
        result = self.ledger.hold_reference_only(
            self.chat, access(), conversation_id=self.cid,
            message_id=pending["message_id"], final_prompt=prompt,
            envelope=envelope, host_public_pin=self.owner_pin,
            host_quote_micro_usd=min(80,cap),
            provider_values=self.env,
        )
        self.assertEqual(result["state"], REFERENCE_HELD, result)
        self.assertFalse(result["provider_called"])

    def witness(self, *, seq=1, previous=ZERO, key=None):
        payload = make_unsigned_witness_head_candidate(
            self.ledger,
            collector_key_id=self.collector_pin["key_id"],
            witness_sequence=seq,
            previous_receipt_sha256=previous,
        )
        signing = key or self.collector_key
        return {
            "payload": payload,
            "signature_hex": signing.sign(canonical_witness_head(payload)).hex(),
        }

    def make_external_head(self, receipt):
        # In real life this MUST be fetched freshly, authenticated and
        # independently from protected external storage (NOT implemented).
        return {"sequence": receipt["payload"]["witness_sequence"],
                "receipt_sha256": signed_receipt_sha256(receipt)}

    def review(self, receipt, *, remote=None, key_pin=None, ledger=None):
        result = review_witnessed_v2_reference_state(
            self.ledger if ledger is None else ledger,
            envelope=receipt,
            collector_public_pin=self.collector_pin if key_pin is None else key_pin,
            independent_expected_head=self.external_head if remote is None else remote,
        )
        self.assertEqual(result["schema"], SCHEMA)
        for field, val in NO_AUTHORITY.items():
            self.assertIs(result[field], val, field)
        return result

    def test_signed_matching_fixture_is_only_mathematical_candidate(self):
        self.add_hold("request-0001", "Explique inflação", "ab"*32)
        receipt = self.witness()
        self.external_head = self.make_external_head(receipt)
        r = self.review(receipt)
        self.assertEqual(r["state"], CANDIDATE)
        self.assertTrue(r["signed_collector_math_valid"])
        self.assertFalse(r["independent_witness_freshness_verified"])
        self.assertFalse(r["rollback_protection_production_verified"])

    def test_missing_external_head_fails_closed_not_trusted_by_local_receipt(self):
        self.add_hold("request-0001", "Explique juros", "ab"*32)
        self.assertEqual(self.review(self.witness())["reason"],
                         "FRESH_INDEPENDENT_HEAD_REQUIRED")

    def test_local_hold_after_signature_without_new_head_fails_closed(self):
        self.add_hold("request-0001", "Explique juros", "ab"*32)
        old = self.witness()
        self.external_head = self.make_external_head(old)
        self.add_hold("request-0002", "Explique inflação", "bc"*32)
        self.assertEqual(self.review(old)["reason"],
                         "LOCAL_SQLITE_SNAPSHOT_NOT_AT_EXTERNAL_HEAD")

    def test_roll_back_old_sqlite_snapshot_against_newer_head_detects(self):
        self.add_hold("request-0001", "Explique juros", "ab"*32)
        old_receipt = self.witness(seq=1)
        backup_path = Path(self.tmp.name) / "older.db"
        with closing(sqlite3.connect(str(backup_path))) as backup:
            self.ledger.db.backup(backup)
        self.add_hold("request-0002", "Explique inflação", "bc"*32)
        latest = self.witness(seq=2, previous=signed_receipt_sha256(old_receipt))
        self.external_head = self.make_external_head(latest)
        self.assertEqual(self.review(latest)["state"], CANDIDATE)

        self.ledger.close()
        shutil.copyfile(backup_path, self.ref_path)
        self.ledger = self.open_ledger()
        # Local restored file is self-consistent but older than the remote head.
        self.assertEqual(self.ledger.reference_snapshot()["hold_count"], 1)
        self.assertEqual(self.review(latest)["reason"],
                         "LOCAL_SQLITE_SNAPSHOT_NOT_AT_EXTERNAL_HEAD")
        self.assertEqual(self.review(old_receipt)["reason"],
                         "EXTERNAL_WITNESS_SEQUENCE_STALE_OR_FUTURE")
        # Critical negative control: if caller can ALSO lie about head
        # freshness, stale signed state appears to match again.
        attacker_old_head = self.make_external_head(old_receipt)
        self.assertEqual(self.review(old_receipt, remote=attacker_old_head)["state"],
                         CANDIDATE)
        self.assertFalse(self.review(old_receipt, remote=attacker_old_head)[
            "independent_witness_freshness_verified"])

    def test_signed_fork_same_sequence_is_rejected_against_remote(self):
        self.add_hold("request-0001", "Explique juros", "ab"*32)
        true = self.witness(seq=7)
        self.external_head = self.make_external_head(true)
        fake = self.witness(seq=7, previous="1"*64)
        self.assertEqual(self.review(fake)["reason"],
                         "EXTERNAL_WITNESS_RECEIPT_FORK_OR_ROLLBACK")
        self.assertEqual(self.review(true)["state"], CANDIDATE)

    def test_stale_and_future_sequences_both_fail_closed(self):
        self.add_hold("request-0001", "Explique juros", "ab"*32)
        true = self.witness(seq=2)
        self.external_head = self.make_external_head(true)
        for seq in (1,3,20):
            with self.subTest(seq=seq):
                candidate = self.witness(seq=seq)
                self.assertEqual(self.review(candidate)["reason"],
                                 "EXTERNAL_WITNESS_SEQUENCE_STALE_OR_FUTURE")

    def test_full_hash_detects_valid_format_local_tampering(self):
        self.add_hold("request-0001", "Explique juros", "ab"*32)
        receipt = self.witness()
        self.external_head = self.make_external_head(receipt)
        self.ledger.db.execute(
            "UPDATE reference_v2_holds SET full_request_sha256=?",
            ("f"*64,),
        )
        self.assertEqual(self.review(receipt)["reason"],
                         "LOCAL_SQLITE_SNAPSHOT_NOT_AT_EXTERNAL_HEAD")

    def test_readonly_snapshot_does_not_mutate_reference_hold(self):
        self.add_hold("request-0001", "Explique juros", "ab"*32)
        a = local_v2_snapshot_commitment(self.ledger)
        b = local_v2_snapshot_commitment(self.ledger)
        self.assertEqual(a, b)
        self.assertEqual(a["hold_count"], 1)
        self.assertFalse(self.ledger.db.in_transaction)
        self.assertFalse(a["witness_append_performed"])

    def test_wrong_collector_pin_and_fake_key_not_trust(self):
        self.add_hold("request-0001", "Explique juros", "ab"*32)
        receipt = self.witness()
        self.external_head = self.make_external_head(receipt)
        attacker_key = Ed25519PrivateKey.generate()
        self.assertEqual(self.review(self.witness(key=attacker_key))["state"],
                         "BLOCKED")
        fake_pin = self.pin(attacker_key, self.collector_pin["key_id"])
        forged = self.witness(key=attacker_key)
        # If the caller controls BOTH pin and independent head input,
        # signature math succeeds. Never claim actual collector enrollment.
        attacker_head = self.make_external_head(forged)
        r = self.review(forged, key_pin=fake_pin, remote=attacker_head)
        self.assertEqual(r["state"], CANDIDATE)
        self.assertFalse(r["trusted_collector_enrollment_verified"])

    def test_bad_signature_or_tampered_role_or_purpose_rejected(self):
        self.add_hold("request-0001", "Explique juros", "ab"*32)
        receipt = self.witness()
        self.external_head = self.make_external_head(receipt)
        e = deepcopy(receipt)
        e["signature_hex"] = "0"*128
        self.assertEqual(self.review(e)["reason"], "COLLECTOR_SIGNATURE_MATH_INVALID")
        for field, value in (("role", "HUMAN_OWNER_ED25519"),
                             ("purpose", "AUTHORIZE_DISPATCH"),
                             ("schema", "V0")):
            with self.subTest(field=field):
                e = deepcopy(receipt)
                e["payload"][field] = value
                self.assertEqual(self.review(e)["state"], "BLOCKED")

    def test_no_unknown_or_missing_authority_fields(self):
        self.add_hold("request-0001", "Explique juros", "ab"*32)
        r = self.witness()
        self.external_head = self.make_external_head(r)
        for field in ("safe_to_resume", "provider_called"):
            e = deepcopy(r)
            e["payload"][field] = True
            self.assertEqual(self.review(e)["reason"], "WITNESS_PAYLOAD_SCHEMA_INVALID")
        for field in list(r["payload"]):
            with self.subTest(field=field):
                e = deepcopy(r)
                e["payload"].pop(field)
                self.assertEqual(self.review(e)["state"], "BLOCKED")

    def test_invalid_external_head_or_pin_or_sequence_type_blocks(self):
        self.add_hold("request-0001", "Explique juros", "ab"*32)
        receipt = self.witness()
        for h in ({"sequence":True,"receipt_sha256":"a"*64},
                  {"sequence":0,"receipt_sha256":"a"*64},
                  {"sequence":1,"receipt_sha256":"x"*64},
                  {"sequence":1}, True, {}, "head"):
            with self.subTest(head=repr(h)):
                self.assertEqual(self.review(receipt, remote=h)["state"], "BLOCKED")
        self.external_head = self.make_external_head(receipt)
        for p in ({"key_id":"x"}, {"key_id":"x","public_key_hex":"x"*64},
                  {"key_id":"x","public_key_hex":True}, {}):
            self.assertEqual(self.review(receipt, key_pin=p)["state"], "BLOCKED")
        for seq in (True, -1, 0, 1.0, "1"):
            with self.assertRaises(ValueError):
                make_unsigned_witness_head_candidate(
                    self.ledger, collector_key_id="synthetic-collector",
                    witness_sequence=seq, previous_receipt_sha256=ZERO,
                )

    def test_corrupt_local_totals_fails_closed(self):
        self.add_hold("request-0001", "Explique juros", "ab"*32)
        receipt = self.witness()
        self.external_head = self.make_external_head(receipt)
        self.ledger.db.execute(
            "UPDATE reference_v2_config SET held_total_micro_usd=0"
        )
        self.assertEqual(self.review(receipt)["reason"],
                         "LOCAL_V2_LEDGER_UNAVAILABLE_OR_CORRUPT")

    def test_no_network_signer_or_provider_called_even_for_matching_head(self):
        self.add_hold("request-0001", "Explique juros", "ab"*32)
        receipt = self.witness()
        self.external_head = self.make_external_head(receipt)
        with patch("requests.post", side_effect=AssertionError("network")), \
             patch("atlasquant_aion_provider.execute_openai_answer",
                   side_effect=AssertionError("provider")):
            self.assertEqual(self.review(receipt)["state"], CANDIDATE)
        self.assertFalse(self.review(receipt)["provider_called"])

    def test_genesis_and_previous_link_are_not_claimed_as_trusted_chain(self):
        self.add_hold("request-0001", "Explique juros", "ab"*32)
        genesis = self.witness(seq=1, previous=ZERO)
        self.external_head = self.make_external_head(genesis)
        self.assertEqual(genesis["payload"]["schema"], HEAD_SCHEMA)
        self.assertEqual(genesis["payload"]["role"], ROLE)
        self.assertEqual(genesis["payload"]["purpose"], PURPOSE)
        self.assertTrue(DOMAIN.endswith(b"\x00"))
        self.assertEqual(self.review(genesis)["state"], CANDIDATE)
        self.assertFalse(self.review(genesis)["witness_sequence_reservation_verified"])


if __name__ == "__main__":
    unittest.main()
