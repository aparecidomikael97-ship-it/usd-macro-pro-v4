"""A317: detached cryptographic anchor vs disposable A316 SQLite.

All signed witnesses and pins are generated IN THIS TEST on the same host.
A mathematical PASS must remain HARD NO-GO. No off-host provider or service.
"""
from contextlib import closing
import copy
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_chat.models import Message, Scope
from aion_chat.store import SQLiteChatStore
from labs.a317_detached_signed_intent_anchor_lab import (
    SCHEMA, ALL_FIELDS, SNAPSHOT_FIELDS, encode, sha, signing_bytes,
    read_fixture_snapshot, assess_detached_intent_anchor,
)

SCOPE = Scope("a317-fixture-owner", "a317-fixture-tenant",
              "a317-fixture-workspace")
NONCE = "c" * 64
PREV = {"sequence": 5, "sha256": "b" * 64}


def pubkey(key):
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


class A317DetachedAnchorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(prefix="a315-lab-a317-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "test-synthetic.sqlite"
        (self.path.parent / ".a315-synthetic-only").write_text(
            "A315 DISPOSABLE SYNTHETIC LAB ONLY\n", encoding="utf-8",
        )
        self.store = SQLiteChatStore(
            self.path, strict_local_data_version=True,
            strict_private_write_helpers=True, strict_sql_authorizer=True,
            strict_semantic_intent=True,
        )
        self.addCleanup(self.store.close)
        self.cid = self.store.create_conversation(
            SCOPE, "A315 TEST A317 local snapshot"
        ).id
        self.intent = "a317-original-intent"
        self.msg_id = "a317-original-message"
        self.report = self.store.append_message_once(
            SCOPE,
            Message(self.cid, "user", "A315 TEST witness payload", id=self.msg_id),
            intent_id=self.intent,
        )
        self.key = Ed25519PrivateKey.generate()
        self.pin = pubkey(self.key)
        snapshot, problem = read_fixture_snapshot(
            self.path, SCOPE, self.intent,
        )
        self.assertIsNone(problem)
        self.assertIsNotNone(snapshot)
        self.local_snapshot = snapshot
        self.anchor = {
            **snapshot, "schema": SCHEMA, "witness_id": "fixture-witness",
            "incident_epoch": 8, "chain_sequence": 6,
            "previous_anchor_sha256": PREV["sha256"],
            "challenge_nonce": NONCE, "issued_at": 9990,
            "expires_at": 10090,
        }
        self.sign()

    def sign(self):
        self.anchor["signature_hex"] = self.key.sign(
            signing_bytes(self.anchor)
        ).hex()

    def assess(self, **kw):
        return assess_detached_intent_anchor(**dict({
            "db_path": self.path, "scope": SCOPE,
            "intent_id": self.intent, "signed_anchor": self.anchor,
            "pinned_witness_key": self.pin, "previous_head": PREV,
            "challenge_nonce": NONCE, "now_epoch": 10000,
            "expected_incident_epoch": 8,
        }, **kw))

    def assert_no_go(self, result):
        self.assertEqual(result["schema"], SCHEMA)
        self.assertTrue(result["research_only"])
        self.assertTrue(result["synthetic_only"])
        self.assertFalse(result["independently_pinned_witness_identity"])
        self.assertFalse(result["off_host_head_authenticated"])
        self.assertFalse(result["external_custody_proven"])
        self.assertFalse(result["provider_effect_verified"])
        self.assertFalse(result["semantic_exactly_once_proven"])
        self.assertFalse(result["trusted_clock_proven"])
        self.assertFalse(result["can_authorize_real_effect"])
        self.assertFalse(result["can_resume"])
        self.assertFalse(result["can_resend"])
        self.assertFalse(result["can_auto_retry"])
        self.assertEqual(result["automatic_retries"], 0)
        self.assertTrue(result["zero_auto_resend"])
        self.assertTrue(result["hard_no_go"])
        self.assertEqual(result["p0_homologated"], 0)
        self.assertFalse(result["new_paid_services"])

    def test_valid_cryptographic_witness_is_not_external_authority(self):
        r = self.assess()
        self.assertEqual(r["status"], "LAB_SNAPSHOT_MATCH_NO_EXTERNAL_AUTHORITY")
        self.assertTrue(r["cryptographic_signature_valid"])
        self.assertTrue(r["signed_snapshot_mathematically_coherent"])
        self.assertTrue(r["local_snapshot_matches_signed_witness"])
        self.assertEqual(r["issues"], [])
        self.assert_no_go(r)

    def test_raw_local_snapshot_matches_fixed_signed_projection(self):
        self.assertEqual(set(self.local_snapshot), SNAPSHOT_FIELDS)
        self.assertEqual(self.local_snapshot["message_id"], self.msg_id)
        self.assertEqual(self.local_snapshot["intent_id"], self.intent)
        self.assertEqual(len(self.local_snapshot["receipt_row_sha256"]), 64)
        self.assertEqual(len(self.local_snapshot["message_data_sha256"]), 64)

    def test_receipt_only_deletion_is_detected_by_detached_anchor(self):
        self.store.close()
        with closing(sqlite3.connect(str(self.path))) as attacker:
            attacker.execute(
                "DELETE FROM a315_local_intent_receipts WHERE intent_id=?",
                (self.intent,),
            )
            attacker.commit()
        r = self.assess()
        self.assertEqual(r["status"], "LAB_LOCAL_DIVERGENCE_VETO")
        self.assertIn("LOCAL_RECEIPT_MISSING", r["issues"])
        self.assertTrue(r["local_rollback_or_tamper_observed"])
        self.assert_no_go(r)

    def test_message_and_receipt_both_deleted_are_still_detected(self):
        self.store.close()
        with closing(sqlite3.connect(str(self.path))) as attacker:
            attacker.execute("DELETE FROM a315_local_intent_receipts")
            attacker.execute(
                "DELETE FROM messages WHERE id=?", (self.msg_id,)
            )
            attacker.execute(
                "UPDATE conversations SET data=json_set(data, "
                "'$.message_count', 0) WHERE id=?", (self.cid,)
            )
            attacker.commit()
        r = self.assess()
        self.assertEqual(r["status"], "LAB_LOCAL_DIVERGENCE_VETO")
        self.assertIn("LOCAL_RECEIPT_MISSING", r["issues"])
        self.assert_no_go(r)

    def test_message_content_mutation_diverges_from_anchor(self):
        self.store.close()
        with closing(sqlite3.connect(str(self.path))) as attacker:
            data = json.loads(attacker.execute(
                "SELECT data FROM messages WHERE id=?", (self.msg_id,)
            ).fetchone()[0])
            data["content"] = "A315 TEST modified"
            attacker.execute(
                "UPDATE messages SET content=?,data=? WHERE id=?",
                (data["content"], json.dumps(data), self.msg_id),
            )
            attacker.commit()
        r = self.assess()
        self.assertEqual(r["status"], "LAB_LOCAL_DIVERGENCE_VETO")
        self.assertTrue(any("message_data_sha256" in x for x in r["issues"]))
        self.assert_no_go(r)

    def test_local_receipt_digest_mutation_diverges_from_anchor(self):
        self.store.close()
        with closing(sqlite3.connect(str(self.path))) as attacker:
            attacker.execute(
                "UPDATE a315_local_intent_receipts SET payload_digest=?",
                ("a" * 64,),
            )
            attacker.commit()
        r = self.assess()
        self.assertEqual(r["status"], "LAB_LOCAL_DIVERGENCE_VETO")
        self.assertIn("LOCAL_RECEIPT_MESSAGE_DIVERGED", r["issues"])
        self.assert_no_go(r)

    def test_replay_cannot_change_signed_intent_id(self):
        fake = copy.deepcopy(self.anchor)
        fake["intent_id"] = "a317-another"
        result = self.assess(signed_anchor=fake)
        self.assertEqual(result["status"], "LAB_WITNESS_INVALID_VETO")
        self.assertIn("SCOPE_INTENT_BINDING_MISMATCH", result["issues"])
        self.assert_no_go(result)

    def test_substituting_payload_digest_breaks_signature(self):
        fake = dict(self.anchor, payload_digest="f" * 64)
        r = self.assess(signed_anchor=fake)
        self.assertEqual(r["status"], "LAB_WITNESS_INVALID_VETO")
        self.assertIn("SIGNATURE_NOT_VALID", r["issues"])
        self.assert_no_go(r)

    def test_wrong_pinned_public_key_is_denied(self):
        forged_pin = pubkey(Ed25519PrivateKey.generate())
        r = self.assess(pinned_witness_key=forged_pin)
        self.assertIn("SIGNATURE_NOT_VALID", r["issues"])
        self.assert_no_go(r)

    def test_invalid_pin_type_denied(self):
        for value in (None, True, "x" * 32, b"abc", []):
            with self.subTest(value=repr(value)):
                r = self.assess(pinned_witness_key=value)
                self.assertIn("WITNESS_PIN_INVALID", r["issues"])
                self.assert_no_go(r)

    def test_wrong_scope_binding_even_with_valid_signature(self):
        another = Scope("a317-fixture-owner", "wrong-tenant",
                        "a317-fixture-workspace")
        r = self.assess(scope=another)
        self.assertIn("SCOPE_INTENT_BINDING_MISMATCH", r["issues"])
        self.assert_no_go(r)

    def test_wrong_incident_epoch_denied(self):
        r = self.assess(expected_incident_epoch=9)
        self.assertIn("INCIDENT_EPOCH_MISMATCH", r["issues"])
        self.assert_no_go(r)

    def test_wrong_last_seen_head_denied(self):
        r = self.assess(previous_head={
            "sequence": 5, "sha256": "0" * 64
        })
        self.assertIn("CHAIN_ROLLBACK_OR_REPLAY", r["issues"])
        self.assert_no_go(r)

    def test_reused_signed_sequence_denied(self):
        r = self.assess(previous_head={
            "sequence": 6, "sha256": "b" * 64
        })
        self.assertIn("CHAIN_ROLLBACK_OR_REPLAY", r["issues"])
        self.assert_no_go(r)

    def test_nonce_mismatch_denied(self):
        r = self.assess(challenge_nonce="1" * 64)
        self.assertIn("CHALLENGE_REUSED_OR_MISMATCH", r["issues"])
        self.assert_no_go(r)

    def test_expired_receipt_denied(self):
        r = self.assess(now_epoch=10100)
        self.assertIn("ANCHOR_STALE_OR_FUTURE", r["issues"])
        self.assert_no_go(r)

    def test_future_dated_receipt_denied(self):
        r = self.assess(now_epoch=9989)
        self.assertIn("ANCHOR_STALE_OR_FUTURE", r["issues"])
        self.assert_no_go(r)

    def test_mutable_clock_and_head_are_not_external_proof(self):
        r = self.assess()
        self.assertFalse(r["trusted_clock_proven"])
        self.assertFalse(r["off_host_head_authenticated"])
        self.assertFalse(r["independently_pinned_witness_identity"])
        self.assert_no_go(r)

    def test_missing_field_rejected(self):
        fake = dict(self.anchor)
        del fake["sequence"]
        r = self.assess(signed_anchor=fake)
        self.assertIn("ANCHOR_FIELDS_INVALID", r["issues"])
        self.assert_no_go(r)

    def test_extra_untrusted_field_rejected(self):
        fake = dict(self.anchor, can_resume=True)
        r = self.assess(signed_anchor=fake)
        self.assertIn("ANCHOR_FIELDS_INVALID", r["issues"])
        self.assert_no_go(r)

    def test_noncanonical_types_dont_promote_go(self):
        for value in (None, True, [], "s", -2):
            with self.subTest(value=repr(value)):
                fake = dict(self.anchor, sequence=value)
                r = self.assess(signed_anchor=fake)
                self.assertIn("ANCHOR_NUMBER_INVALID", r["issues"])
                self.assert_no_go(r)
        # A positive integer remains well-typed; the changed signed
        # value is instead rejected cryptographically, never promoted.
        tampered = dict(self.anchor, sequence=2)
        result = self.assess(signed_anchor=tampered)
        self.assertIn("SIGNATURE_NOT_VALID", result["issues"])
        self.assert_no_go(result)

    def test_non_lab_path_rejected_without_opening_operational_data(self):
        other = Path(self.tmp.name) / "unmarked.sqlite"
        r = self.assess(db_path=other)
        self.assertEqual(r["status"], "LAB_LOCAL_DIVERGENCE_VETO")
        self.assertIn("LAB_FIXTURE_REFUSED", r["issues"])
        self.assert_no_go(r)

    def test_malformed_json_message_is_denied(self):
        self.store.close()
        with closing(sqlite3.connect(str(self.path))) as attacker:
            attacker.execute(
                "UPDATE messages SET data=? WHERE id=?",
                ("not-json", self.msg_id),
            )
            attacker.commit()
        r = self.assess()
        self.assertEqual(r["status"], "LAB_LOCAL_DIVERGENCE_VETO")
        self.assertIn("LOCAL_READ_UNCERTAIN", r["issues"])
        self.assert_no_go(r)

    def test_all_local_artifacts_and_signer_pins_can_be_reminted(self):
        """Essential negative: self-issued key and pin cannot prove off-host."""
        self.store.close()
        with closing(sqlite3.connect(str(self.path))) as attacker:
            data = json.loads(attacker.execute(
                "SELECT data FROM messages WHERE id=?", (self.msg_id,)
            ).fetchone()[0])
            data["content"] = "A315 TEST fake new local state"
            attacker.execute(
                "UPDATE messages SET content=?,data=? WHERE id=?",
                (data["content"], json.dumps(data), self.msg_id),
            )
            attacker.commit()
        self.key = Ed25519PrivateKey.generate()
        self.pin = pubkey(self.key)
        local, problem = read_fixture_snapshot(
            self.path, SCOPE, self.intent
        )
        self.assertIsNone(problem)
        self.anchor.update(local)
        self.sign()
        r = self.assess()
        self.assertEqual(r["status"], "LAB_SNAPSHOT_MATCH_NO_EXTERNAL_AUTHORITY")
        self.assertTrue(r["cryptographic_signature_valid"])
        self.assertFalse(r["external_custody_proven"])
        self.assert_no_go(r)


if __name__ == "__main__":
    unittest.main()
