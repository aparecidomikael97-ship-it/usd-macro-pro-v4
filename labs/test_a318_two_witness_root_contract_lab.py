"""A318 real 2-of-2 crypto quorum tests; ALL signers are synthetic.

These tests prove math and fail-closed behavior only. They intentionally
show attacker-reminted roots + attacker-controlled pinset can pass locally.
P0 0/6, HARD NO-GO, ZERO_AUTO_RESEND in every result.
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
    SCHEMA as A317_SCHEMA, read_fixture_snapshot,
    signing_bytes as a317_signing_bytes, encode, sha,
)
from labs.a318_two_witness_root_contract_lab import (
    SCHEMA, ALL_FIELDS, SIGNABLE, QUORUM, statement_bytes,
    verify_two_witness_hold,
)

SCOPE = Scope("a318-synthetic-owner", "a318-synthetic-tenant",
              "a318-synthetic-workspace")
NONCE = "c" * 64
PREV = {"sequence": 8, "sha256": "b" * 64}


def public_bytes(key):
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


class A318TwoWitnessRootContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="a315-lab-a318-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "only-test.db"
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
            SCOPE, "A315 TEST A318 synthetic fixture",
        ).id
        self.intent = "a318-intent-original"
        self.msgid = "a318-message-original"
        first = self.store.append_message_once(
            SCOPE, Message(
                self.cid, "user", "A315 TEST A318 custody fixture",
                id=self.msgid,
            ), intent_id=self.intent,
        )
        self.assertEqual(first["status"], "LOCAL_ACKED_ONCE")
        local, problem = read_fixture_snapshot(self.path, SCOPE, self.intent)
        self.assertIsNone(problem)
        self.snapshot = local
        self.previous_head = dict(PREV)
        self.a317_signer = Ed25519PrivateKey.generate()
        self.a317_pin = public_bytes(self.a317_signer)
        self.anchor = {
            **self.snapshot, "schema": A317_SCHEMA,
            "witness_id": "a318-lab-a317",
            "incident_epoch": 7, "chain_sequence": 9,
            "previous_anchor_sha256": PREV["sha256"],
            "challenge_nonce": NONCE,
            "issued_at": 10000, "expires_at": 10100,
        }
        self.sign_a317()
        self.root_signers = {
            "root-fixture-A": Ed25519PrivateKey.generate(),
            "root-fixture-B": Ed25519PrivateKey.generate(),
        }
        self.pinset = {name: public_bytes(key)
                       for name, key in self.root_signers.items()}
        self.generation = 3
        self.statements = self.mint_statements()

    def sign_a317(self):
        self.anchor["signature_hex"] = self.a317_signer.sign(
            a317_signing_bytes(self.anchor)
        ).hex()

    def mint_statements(self):
        result = []
        for root_id, key in sorted(self.root_signers.items()):
            statement = {
                "schema": SCHEMA, "root_id": root_id,
                "root_generation": self.generation,
                "anchor_sha256": sha(encode(self.anchor)),
                "chain_sequence": self.anchor["chain_sequence"],
                "previous_anchor_sha256": self.anchor["previous_anchor_sha256"],
                "incident_epoch": self.anchor["incident_epoch"],
                "challenge_nonce": self.anchor["challenge_nonce"],
                "issued_at": 10000, "expires_at": 10100,
                "decision": "HOLD_ONLY",
            }
            statement["signature_hex"] = key.sign(
                statement_bytes(statement)
            ).hex()
            result.append(statement)
        return result

    def verify(self, **kwargs):
        args = {
            "db_path": self.path, "scope": SCOPE, "intent_id": self.intent,
            "signed_anchor": self.anchor,
            "pinned_a317_witness_key": self.a317_pin,
            "previous_head": self.previous_head,
            "challenge_nonce": NONCE, "now_epoch": 10050,
            "expected_incident_epoch": 7,
            "witness_statements": self.statements,
            "pinned_root_keys": self.pinset,
            "revoked_root_ids": (),
            "root_generation": self.generation,
        }
        args.update(kwargs)
        return verify_two_witness_hold(**args)

    def assert_no_go(self, result):
        self.assertEqual(result["schema"], SCHEMA)
        self.assertTrue(result["research_only"])
        self.assertTrue(result["synthetic_only"])
        self.assertFalse(result["roots_independently_pinned"])
        self.assertFalse(result["root_rotation_independently_authorized"])
        self.assertFalse(result["revocations_independently_attested"])
        self.assertFalse(result["external_high_water_authenticated"])
        self.assertFalse(result["trusted_time_proven"])
        self.assertFalse(result["off_host_custody_proven"])
        self.assertFalse(result["independent_provider_ack_proven"])
        self.assertFalse(result["semantic_exactly_once_proven"])
        self.assertFalse(result["can_authorize_real_effect"])
        self.assertFalse(result["can_resume"])
        self.assertFalse(result["can_resend"])
        self.assertFalse(result["can_auto_retry"])
        self.assertEqual(result["automatic_retries"], 0)
        self.assertTrue(result["zero_auto_resend"])
        self.assertTrue(result["hard_no_go"])
        self.assertEqual(result["p0_homologated"], 0)
        self.assertTrue(result["no_worker_deploy_provider_orders"])
        self.assertFalse(result["new_paid_services"])

    def test_two_correct_signatures_match_but_never_authorize(self):
        r = self.verify()
        self.assertEqual(
            r["status"],
            "LAB_TWO_SIGNATURES_MATCH_STILL_NO_EXTERNAL_AUTHORITY",
        )
        self.assertEqual(r["verified_witness_signatures"], 2)
        self.assertEqual(r["required_witness_signatures"], 2)
        self.assertTrue(r["mathematical_two_witness_quorum_valid"])
        self.assertTrue(r["local_a317_signature_and_snapshot_valid"])
        self.assert_no_go(r)

    def test_signed_fields_and_domain_are_explicit(self):
        self.assertEqual(len(self.statements), QUORUM)
        for statement in self.statements:
            self.assertEqual(set(statement), ALL_FIELDS)
            self.assertEqual(statement["decision"], "HOLD_ONLY")
            self.assertTrue(statement_bytes(statement).startswith(
                b"ATLASQUANT_AION_A318_TWO_WITNESS_CUSTODY_CONTRACT_LAB_V1"
            ))
        self.assertEqual(len(SIGNABLE), len(ALL_FIELDS) - 1)

    def test_missing_second_signature_refused(self):
        r = self.verify(witness_statements=self.statements[:1])
        self.assertIn("ANCHOR_OR_QUORUM_SHAPE_INVALID", r["reasons"])
        self.assert_no_go(r)

    def test_repeated_same_witness_is_not_two_independent_witnesses(self):
        repeated = [self.statements[0], copy.deepcopy(self.statements[0])]
        r = self.verify(witness_statements=repeated)
        self.assertIn("WITNESS_ROOT_REUSED", r["reasons"])
        self.assertIn("TWO_DIFFERENT_PINNED_WITNESSES_REQUIRED", r["reasons"])
        self.assert_no_go(r)

    def test_same_public_key_for_both_roots_refused(self):
        pinset = dict(self.pinset)
        pinset["root-fixture-B"] = pinset["root-fixture-A"]
        r = self.verify(pinned_root_keys=pinset)
        self.assertIn("ROOT_KEYS_NOT_DISTINCT", r["reasons"])
        self.assert_no_go(r)

    def test_root_key_cannot_equal_a317_signer(self):
        pinset = dict(self.pinset)
        pinset["root-fixture-A"] = self.a317_pin
        r = self.verify(pinned_root_keys=pinset)
        self.assertIn("ROOT_NOT_DISTINCT_FROM_A317_SIGNER", r["reasons"])
        self.assert_no_go(r)

    def test_wrong_pinned_root_key_refused(self):
        pinset = dict(self.pinset)
        pinset["root-fixture-A"] = public_bytes(Ed25519PrivateKey.generate())
        r = self.verify(pinned_root_keys=pinset)
        self.assertIn("WITNESS_SIGNATURE_INVALID", r["reasons"])
        self.assert_no_go(r)

    def test_root_rotation_without_old_attestation_refused(self):
        pinset = {
            "root-fixture-A": self.pinset["root-fixture-A"],
            "new-root-not-authorized": public_bytes(
                Ed25519PrivateKey.generate()
            ),
        }
        r = self.verify(pinned_root_keys=pinset)
        self.assertIn("WITNESS_ROOT_NOT_PINNED", r["reasons"])
        self.assertIn("TWO_DIFFERENT_PINNED_WITNESSES_REQUIRED", r["reasons"])
        self.assert_no_go(r)

    def test_root_generation_replay_refused(self):
        r = self.verify(root_generation=4)
        self.assertIn("ROOT_GENERATION_REPLAY_OR_MISMATCH", r["reasons"])
        self.assert_no_go(r)

    def test_root_revocation_locally_listed_refuses_quorum(self):
        r = self.verify(revoked_root_ids=("root-fixture-A",))
        self.assertIn("WITNESS_ROOT_REVOKED", r["reasons"])
        self.assert_no_go(r)

    def test_revocation_list_under_caller_control_not_independent(self):
        r = self.verify(revoked_root_ids=())
        self.assertTrue(r["mathematical_two_witness_quorum_valid"])
        self.assertFalse(r["revocations_independently_attested"])
        self.assert_no_go(r)

    def test_missing_or_malformed_revocation_list_refused(self):
        for bad in (None, True, {}, "root-fixture-A", (None,)):
            with self.subTest(value=repr(bad)):
                r = self.verify(revoked_root_ids=bad)
                self.assertIn("REVOCATION_SET_INVALID", r["reasons"])
                self.assert_no_go(r)

    def test_old_head_sequence_cannot_be_used_again(self):
        r = self.verify(previous_head={
            "sequence": 9, "sha256": PREV["sha256"]
        })
        self.assertIn("HIGH_WATER_ROLLBACK_OR_REPLAY", r["reasons"])
        self.assert_no_go(r)

    def test_changed_head_hash_refused_even_if_head_seq_matches(self):
        r = self.verify(previous_head={
            "sequence": 8, "sha256": "0" * 64
        })
        self.assertIn("HIGH_WATER_ROLLBACK_OR_REPLAY", r["reasons"])
        self.assert_no_go(r)

    def test_reopen_incident_epoch_refused(self):
        r = self.verify(expected_incident_epoch=8)
        self.assertIn("INCIDENT_REOPEN_OR_EPOCH_MISMATCH", r["reasons"])
        self.assert_no_go(r)

    def test_replayed_challenge_refused(self):
        r = self.verify(challenge_nonce="e" * 64)
        self.assertIn("CHALLENGE_REPLAY_OR_MISMATCH", r["reasons"])
        self.assert_no_go(r)

    def test_expired_statement_refused(self):
        r = self.verify(now_epoch=10101)
        self.assertIn("WITNESS_EXPIRED_FUTURE_OR_OVERSIZED", r["reasons"])
        self.assert_no_go(r)

    def test_early_clock_refused(self):
        r = self.verify(now_epoch=9999)
        self.assertIn("WITNESS_EXPIRED_FUTURE_OR_OVERSIZED", r["reasons"])
        self.assert_no_go(r)

    def test_statement_with_extra_go_field_refused(self):
        bad = copy.deepcopy(self.statements)
        bad[0]["can_authorize_real_effect"] = True
        r = self.verify(witness_statements=bad)
        self.assertIn("WITNESS_FIELDS_INVALID", r["reasons"])
        self.assert_no_go(r)

    def test_untrusted_positive_number_bool_invalid(self):
        bad = copy.deepcopy(self.statements)
        bad[0]["root_generation"] = True
        r = self.verify(witness_statements=bad)
        self.assertIn("WITNESS_NUMBER_INVALID", r["reasons"])
        self.assert_no_go(r)

    def test_tampered_anchor_digest_after_signing_refused(self):
        bad = copy.deepcopy(self.statements)
        bad[0]["anchor_sha256"] = "0" * 64
        r = self.verify(witness_statements=bad)
        self.assertIn("ANCHOR_DIGEST_MISMATCH", r["reasons"])
        self.assertIn("WITNESS_SIGNATURE_INVALID", r["reasons"])
        self.assert_no_go(r)

    def test_witness_signature_tampering_refused(self):
        bad = copy.deepcopy(self.statements)
        bad[1]["signature_hex"] = "0" * 128
        r = self.verify(witness_statements=bad)
        self.assertIn("WITNESS_SIGNATURE_INVALID", r["reasons"])
        self.assert_no_go(r)

    def test_local_receipt_removed_even_with_valid_quorum_refused(self):
        self.store.close()
        with closing(sqlite3.connect(str(self.path))) as db:
            db.execute("DELETE FROM a315_local_intent_receipts")
            db.commit()
        r = self.verify()
        self.assertEqual(r["status"], "LAB_LOCAL_ANCHOR_VETO")
        self.assertIn("LOCAL_RECEIPT_MISSING", r["reasons"])
        self.assertFalse(r["local_a317_signature_and_snapshot_valid"])
        self.assert_no_go(r)

    def test_local_message_tampered_even_with_two_signatures_refused(self):
        self.store.close()
        with closing(sqlite3.connect(str(self.path))) as db:
            db.execute(
                "UPDATE messages SET content=? WHERE id=?",
                ("A315 TEST hostile mutation", self.msgid),
            )
            db.commit()
        r = self.verify()
        self.assertEqual(r["status"], "LAB_LOCAL_ANCHOR_VETO")
        self.assert_no_go(r)

    def test_a317_anchor_signature_invalid_with_valid_quorum_refused(self):
        bad_anchor = dict(self.anchor)
        bad_anchor["signature_hex"] = "0" * 128
        # Even if the two witnesses honestly sign the damaged A317 anchor,
        # the underlying signature must still be checked independently.
        old = self.anchor
        self.anchor = bad_anchor
        try:
            newly_signed = self.mint_statements()
        finally:
            self.anchor = old
        r = self.verify(witness_statements=newly_signed,
                        signed_anchor=bad_anchor)
        self.assertEqual(r["status"], "LAB_LOCAL_ANCHOR_VETO")
        self.assertIn("SIGNATURE_NOT_VALID", r["reasons"])
        self.assert_no_go(r)

    def test_host_remints_both_roots_and_old_reference_and_still_no_go(self):
        """Essential P0-3 failure: 2 local keys != independent custodians."""
        self.a317_signer = Ed25519PrivateKey.generate()
        self.a317_pin = public_bytes(self.a317_signer)
        self.root_signers = {
            "root-fixture-A": Ed25519PrivateKey.generate(),
            "root-fixture-B": Ed25519PrivateKey.generate(),
        }
        self.pinset = {name: public_bytes(key)
                       for name, key in self.root_signers.items()}
        self.previous_head = {"sequence": 8, "sha256": "e" * 64}
        self.anchor["previous_anchor_sha256"] = self.previous_head["sha256"]
        self.sign_a317()
        self.statements = self.mint_statements()
        r = self.verify(previous_head=self.previous_head,
                        pinned_a317_witness_key=self.a317_pin,
                        pinned_root_keys=self.pinset)
        self.assertEqual(
            r["status"],
            "LAB_TWO_SIGNATURES_MATCH_STILL_NO_EXTERNAL_AUTHORITY",
        )
        self.assertTrue(r["mathematical_two_witness_quorum_valid"])
        self.assertFalse(r["roots_independently_pinned"])
        self.assertFalse(r["off_host_custody_proven"])
        self.assert_no_go(r)

    def test_even_tampered_local_data_and_two_new_roots_can_be_reminted(self):
        """Another honest negative control for same-host TOTAL trust reset."""
        self.store.close()
        with closing(sqlite3.connect(str(self.path))) as db:
            raw = db.execute(
                "SELECT data FROM messages WHERE id=?", (self.msgid,)
            ).fetchone()[0]
            record = json.loads(raw)
            record["content"] = "A315 TEST attacker-reminted local content"
            db.execute(
                "UPDATE messages SET data=?,content=? WHERE id=?",
                (json.dumps(record), record["content"], self.msgid),
            )
            db.commit()
        # Owner also replaces A317 pin + dual-witness pins and snapshot.
        from labs.a317_detached_signed_intent_anchor_lab import read_fixture_snapshot
        updated, error = read_fixture_snapshot(self.path, SCOPE, self.intent)
        self.assertIsNone(error)
        self.anchor.update(updated)
        self.a317_signer = Ed25519PrivateKey.generate()
        self.a317_pin = public_bytes(self.a317_signer)
        self.root_signers = {
            "root-fixture-A": Ed25519PrivateKey.generate(),
            "root-fixture-B": Ed25519PrivateKey.generate(),
        }
        self.pinset = {name: public_bytes(key)
                       for name, key in self.root_signers.items()}
        self.sign_a317()
        self.statements = self.mint_statements()
        r = self.verify()
        self.assertTrue(r["mathematical_two_witness_quorum_valid"])
        self.assertTrue(r["local_a317_signature_and_snapshot_valid"])
        self.assertFalse(r["off_host_custody_proven"])
        self.assert_no_go(r)

    def test_unknown_root_pinset_types_refused(self):
        for item in (None, [], {}, True, {"bad": b"foo"}):
            with self.subTest(value=repr(item)):
                r = self.verify(pinned_root_keys=item)
                self.assert_no_go(r)
                self.assertNotEqual(
                    r["status"],
                    "LAB_TWO_SIGNATURES_MATCH_STILL_NO_EXTERNAL_AUTHORITY",
                )

    def test_invalid_previous_head_type_refused(self):
        for bad in (None, [], {"sequence": True, "sha256": "b" * 64},
                    {"sequence": -1, "sha256": "b" * 64}):
            with self.subTest(value=repr(bad)):
                r = self.verify(previous_head=bad)
                self.assertIn("HIGH_WATER_HEAD_INVALID", r["reasons"])
                self.assert_no_go(r)


if __name__ == "__main__":
    unittest.main()
