"""A149 laboratory only: signed one-time challenges, CAS and crash boundaries.

No real publisher identity, network trust, external effect or production GO.
Negative proofs deliberately demonstrate rollback and lack of challenge TTL.
"""
import base64
from contextlib import closing
from dataclasses import replace
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_p0_a145_checkpoint_verifier_lab import canonical_history_digest
from aion_p0_a146_signed_highwater_lab import verify_signed_highwater
from aion_p0_a147_sqlite_crash_journal_lab import SyntheticCrashJournalLAB
from aion_p0_a149_authenticated_cas_lab import (
    A149Denied, AuthenticatedWitnessLAB, LAB_ONLY,
    PublicationReceipt, PublishRequest, SignedPublishRequest,
    SignedPublicationReceipt, canonical_publish_request, verify_signed_receipt,
)

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "aion_p0_a149_broker_cli_lab.py"


def raw_public(signer):
    return signer.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )


def raw_private(signer):
    return signer.private_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


class A149AuthenticatedCASLAB(unittest.TestCase):
    def setUp(self):
        flags = patch.dict(os.environ, {
            "AION_LAB_MODE": "1", "AION_WORKER_ENABLED": "0",
            "AION_EXTERNAL_EXECUTION_ENABLED": "0",
        })
        flags.start()
        self.addCleanup(flags.stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.witness_dir = self.root / "simulated_other_process"
        self.witness_dir.mkdir()
        self.publisher = Ed25519PrivateKey.generate()
        self.witness_signer = Ed25519PrivateKey.generate()
        self.pinned_witness = raw_public(self.witness_signer)
        self.witness = AuthenticatedWitnessLAB.bootstrap_synthetic(
            witness_dir=self.witness_dir, ledger_id="ledger-A",
            publisher_key_id="publisher-1",
            publisher_public_key=raw_public(self.publisher),
            witness_private_key=raw_private(self.witness_signer),
        )
        self.events1 = [{"seq": 1, "intent": "synthetic_first"}]
        self.events2 = self.events1 + [{"seq": 2, "intent": "synthetic_second"}]

    def signed(self, *, challenge=None, events=None, signer=None, **changes):
        challenge = challenge or self.witness.issue_challenge()
        events = self.events1 if events is None else events
        attrs = {
            "ledger_id": challenge["ledger_id"],
            "epoch": challenge["epoch"],
            "publisher_key_id": challenge["publisher_key_id"],
            "challenge_id": challenge["challenge_id"],
            "request_id": secrets.token_hex(16),
            "expected_sequence": challenge["expected_sequence"],
            "expected_digest": challenge["expected_digest"],
            "next_sequence": challenge["expected_sequence"] + 1,
            "next_digest": canonical_history_digest(events),
        }
        attrs.update(changes)
        request = PublishRequest(**attrs)
        signer = signer or self.publisher
        signature = base64.b64encode(
            signer.sign(canonical_publish_request(request))
        ).decode("ascii")
        return SignedPublishRequest(request, signature)

    def mutate_unsigned(self, envelope, **changes):
        return SignedPublishRequest(replace(envelope.request, **changes),
                                    envelope.signature_b64)

    def reopen(self):
        return AuthenticatedWitnessLAB(witness_dir=self.witness_dir, ledger_id="ledger-A")

    def cli(self, op, *, envelope=None, request_id=None, fault=None,
            overrides=None, raw=None, env_overrides=None):
        body = {"operation": op, "directory": str(self.witness_dir),
                "ledger_id": "ledger-A"}
        if envelope is not None:
            body["request"] = {k: getattr(envelope.request, k)
                               for k in PublishRequest.__dataclass_fields__}
            body["signature_b64"] = envelope.signature_b64
        if request_id is not None:
            body["request_id"] = request_id
        if fault is not None:
            body["fault"] = fault
        if overrides:
            body.update(overrides)
        env = dict(os.environ)
        if env_overrides:
            env.update(env_overrides)
        proc = subprocess.run(
            [sys.executable, "-B", str(CLI)], input=json.dumps(body) if raw is None else raw,
            cwd=ROOT, env=env, text=True, capture_output=True, timeout=25,
        )
        reply = json.loads(proc.stdout) if proc.stdout.strip() else None
        return proc.returncode, reply, proc.stderr

    def assert_cli_denied(self, result, reason=None):
        code, payload, stderr = result
        self.assertEqual(code, 2, stderr)
        self.assertEqual(payload["marker"], LAB_ONLY)
        self.assertIn("error", payload)
        if reason:
            self.assertIn(reason, payload["error"])

    def test_01_genesis_immutable_default(self):
        self.assertEqual(self.witness.read_head()["sequence"], 0)
        self.assertEqual(self.witness.read_head()["digest"], canonical_history_digest([]))

    def test_02_challenge_issued_and_survives_reopen(self):
        challenge = self.witness.issue_challenge()
        self.assertEqual(len(challenge["challenge_id"]), 32)
        self.assertEqual(self.reopen().read_head()["epoch"], challenge["epoch"])
        self.assertTrue(self.reopen().publish(envelope=self.signed(challenge=challenge)))

    def test_03_authorized_publisher_signed_increment(self):
        envelope = self.signed()
        receipt = self.witness.publish(envelope=envelope)
        self.assertEqual(receipt.receipt.sequence, 1)
        self.assertEqual(self.witness.read_head()["sequence"], 1)

    def test_04_signed_receipt_verifies_under_pre_pinned_witness(self):
        signed = self.witness.publish(envelope=self.signed())
        self.assertEqual(verify_signed_receipt(
            envelope=signed, pinned_witness_key=self.pinned_witness
        ), signed.receipt)

    def test_05_read_signed_highwater_verifies(self):
        head = self.witness.read_signed_head()
        self.assertEqual(verify_signed_highwater(
            envelope=head, pinned_authorities={"a149-witness-synthetic": self.pinned_witness},
            forbidden_checkpoint_key=raw_public(self.publisher),
        ).sequence, 0)

    def test_06_same_signed_request_replay_denied(self):
        envelope = self.signed()
        self.witness.publish(envelope=envelope)
        with self.assertRaisesRegex(A149Denied, "challenge_already_consumed"):
            self.reopen().publish(envelope=envelope)

    def test_07_same_challenge_new_request_id_denied(self):
        envelope = self.signed()
        self.witness.publish(envelope=envelope)
        other = self.signed(challenge={
            "ledger_id": envelope.request.ledger_id,
            "epoch": envelope.request.epoch,
            "challenge_id": envelope.request.challenge_id,
            "publisher_key_id": envelope.request.publisher_key_id,
            "expected_sequence": envelope.request.expected_sequence,
            "expected_digest": envelope.request.expected_digest,
        })
        with self.assertRaisesRegex(A149Denied, "challenge_already_consumed"):
            self.witness.publish(envelope=other)

    def test_08_other_signer_denied(self):
        with self.assertRaisesRegex(A149Denied, "publisher_signature_invalid"):
            self.witness.publish(envelope=self.signed(signer=Ed25519PrivateKey.generate()))

    def test_09_signature_bit_corruption_denied(self):
        env = self.signed()
        with self.assertRaisesRegex(A149Denied, "publisher_signature_invalid"):
            self.witness.publish(envelope=SignedPublishRequest(
                env.request, base64.b64encode(b"\x11" * 64).decode("ascii")
            ))

    def test_10_invalid_signature_encoding_denied(self):
        env = self.signed()
        with self.assertRaisesRegex(A149Denied, "invalid_signature_encoding"):
            self.witness.publish(envelope=SignedPublishRequest(env.request, "not base64!"))

    def test_11_unauthenticated_digest_mutation_denied(self):
        env = self.signed()
        with self.assertRaisesRegex(A149Denied, "publisher_signature_invalid"):
            self.witness.publish(envelope=self.mutate_unsigned(env, next_digest="b" * 64))

    def test_12_unauthenticated_sequence_mutation_denied(self):
        env = self.signed()
        with self.assertRaisesRegex(A149Denied, "invalid_sequence_transition"):
            self.witness.publish(envelope=self.mutate_unsigned(env, next_sequence=3))

    def test_13_unknown_publisher_id_denied(self):
        env = self.signed(publisher_key_id="attacker")
        with self.assertRaisesRegex(A149Denied, "untrusted_publisher_key_id"):
            self.witness.publish(envelope=env)

    def test_14_foreign_ledger_denied(self):
        env = self.signed(ledger_id="ledger-B")
        with self.assertRaisesRegex(A149Denied, "request_identity_or_epoch_mismatch"):
            self.witness.publish(envelope=env)

    def test_15_wrong_epoch_denied(self):
        env = self.signed(epoch=secrets.token_hex(16))
        with self.assertRaisesRegex(A149Denied, "request_identity_or_epoch_mismatch"):
            self.witness.publish(envelope=env)

    def test_16_nonexistent_challenge_denied(self):
        env = self.signed(challenge_id=secrets.token_hex(16))
        with self.assertRaisesRegex(A149Denied, "unknown_witness_challenge"):
            self.witness.publish(envelope=env)

    def test_17_challenge_expected_digest_mismatch_denied(self):
        env = self.signed(expected_digest="e" * 64)
        with self.assertRaisesRegex(A149Denied, "challenge_request_mismatch"):
            self.witness.publish(envelope=env)

    def test_18_outstanding_challenge_stale_after_other_publication(self):
        stale = self.signed()
        self.witness.publish(envelope=self.signed())
        with self.assertRaisesRegex(A149Denied, "stale_cas_and_history"):
            self.witness.publish(envelope=stale)

    def test_19_two_valid_sequential_increments(self):
        self.witness.publish(envelope=self.signed())
        env = self.signed(events=self.events2)
        self.assertEqual(env.request.next_sequence, 2)
        self.witness.publish(envelope=env)
        self.assertEqual(self.reopen().read_head()["sequence"], 2)

    def test_20_duplicate_request_id_on_next_challenge_denied(self):
        first = self.signed()
        self.witness.publish(envelope=first)
        second = self.signed(events=self.events2, request_id=first.request.request_id)
        with self.assertRaisesRegex(A149Denied, "request_id_reused"):
            self.witness.publish(envelope=second)

    def test_21_readonly_receipt_lookup_does_not_advance(self):
        env = self.signed()
        self.witness.publish(envelope=env)
        before = self.witness.read_head()
        receipt = self.reopen().read_receipt(env.request.request_id)
        self.assertEqual(receipt.receipt.request_id, env.request.request_id)
        self.assertEqual(self.witness.read_head(), before)

    def test_22_unknown_receipt_is_none(self):
        self.assertIsNone(self.witness.read_receipt(secrets.token_hex(16)))

    def test_23_receipt_tampered_identity_signature_denied(self):
        signed = self.witness.publish(envelope=self.signed())
        altered = SignedPublicationReceipt(
            replace(signed.receipt, request_id=secrets.token_hex(16)),
            signed.signature_b64,
        )
        with self.assertRaisesRegex(A149Denied, "receipt_signature_invalid"):
            verify_signed_receipt(envelope=altered,
                                  pinned_witness_key=self.pinned_witness)

    def test_24_receipt_wrong_key_denied(self):
        signed = self.witness.publish(envelope=self.signed())
        with self.assertRaisesRegex(A149Denied, "receipt_signature_invalid"):
            verify_signed_receipt(
                envelope=signed, pinned_witness_key=raw_public(Ed25519PrivateKey.generate())
            )

    def test_25_no_rebootstrap_over_existing_witness(self):
        with self.assertRaisesRegex(A149Denied, "rebootstrap_forbidden"):
            AuthenticatedWitnessLAB.bootstrap_synthetic(
                witness_dir=self.witness_dir, ledger_id="ledger-A",
                publisher_key_id="publisher-1",
                publisher_public_key=raw_public(self.publisher),
                witness_private_key=raw_private(self.witness_signer),
            )

    def test_26_unknown_database_file_never_recreated(self):
        self.witness.db_path.unlink()
        with self.assertRaisesRegex(A149Denied, "missing_witness_files"):
            self.reopen()
        self.assertFalse(self.witness.db_path.exists())

    def test_27_deleted_private_key_never_regenerated(self):
        self.witness.key_path.unlink()
        with self.assertRaisesRegex(A149Denied, "missing_witness_files"):
            self.reopen()

    def test_28_schema_trigger_attestation_denied(self):
        with closing(sqlite3.connect(self.witness.db_path)) as db:
            db.execute("CREATE TRIGGER extra AFTER UPDATE ON witness_meta BEGIN SELECT 1; END")
            db.commit()
        with self.assertRaisesRegex(A149Denied, "unexpected_schema_objects"):
            self.witness.read_head()

    def test_29_stored_publisher_identity_tamper_detected_by_signature(self):
        with closing(sqlite3.connect(self.witness.db_path)) as db:
            db.execute("UPDATE witness_meta SET publisher_public_hex=?",
                       (raw_public(Ed25519PrivateKey.generate()).hex(),))
            db.commit()
        with self.assertRaisesRegex(A149Denied, "publisher_signature_invalid"):
            self.witness.publish(envelope=self.signed())

    def test_30_negative_storage_owner_can_replace_trusted_publisher_key(self):
        # NEGATIVE: mutable local SQLite policy means key custody is NOT solved.
        attacker = Ed25519PrivateKey.generate()
        with closing(sqlite3.connect(self.witness.db_path)) as db:
            db.execute("UPDATE witness_meta SET publisher_public_hex=?",
                       (raw_public(attacker).hex(),))
            db.commit()
        malicious = self.signed(signer=attacker)
        self.assertEqual(self.witness.publish(envelope=malicious).receipt.sequence, 1)

    def test_31_negative_old_challenge_lacks_deadline(self):
        # NEGATIVE: no expiry policy; an unconsumed challenge is reusable later.
        stale = self.signed()
        self.assertTrue(self.reopen().publish(envelope=stale))
        self.assertEqual(self.witness.read_head()["sequence"], 1)

    def test_32_negative_witness_database_rollback_reopens_old_epoch(self):
        # NEGATIVE: snapshot can roll back challenge and high-water in same domain.
        old = self.root / "old_snapshot.sqlite"
        shutil.copyfile(self.witness.db_path, old)
        request = self.signed()
        self.witness.publish(envelope=request)
        self.assertEqual(self.reopen().read_head()["sequence"], 1)
        shutil.copyfile(old, self.witness.db_path)
        self.assertEqual(self.reopen().read_head()["sequence"], 0)
        self.assertIsNone(self.reopen().read_receipt(request.request.request_id))

    def test_33_runtime_lab_mode_off_denied(self):
        with patch.dict(os.environ, {"AION_LAB_MODE": "0"}):
            with self.assertRaisesRegex(A149Denied, "lab_mode_required"):
                self.witness.read_head()

    def test_34_runtime_worker_enabled_denied(self):
        with patch.dict(os.environ, {"AION_WORKER_ENABLED": "1"}):
            with self.assertRaisesRegex(A149Denied, "worker_must_be_disabled"):
                self.witness.issue_challenge()

    def test_35_runtime_external_execution_enabled_denied(self):
        with patch.dict(os.environ, {"AION_EXTERNAL_EXECUTION_ENABLED": "1"}):
            with self.assertRaisesRegex(A149Denied, "external_execution_must_be_disabled"):
                self.witness.publish(envelope=self.signed())

    def test_36_two_parallel_distinct_signed_challenges_one_wins(self):
        a = self.signed()
        b = self.signed()
        results = []
        def work(envelope):
            try:
                self.reopen().publish(envelope=envelope)
                results.append("success")
            except A149Denied:
                results.append("rejected")
        tasks = [threading.Thread(target=work, args=(e,)) for e in (a, b)]
        for t in tasks: t.start()
        for t in tasks: t.join()
        self.assertEqual(sorted(results), ["rejected", "success"])
        self.assertEqual(self.witness.read_head()["sequence"], 1)

    def test_37_cli_challenge_cross_process(self):
        code, payload, stderr = self.cli("challenge")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(payload["marker"], LAB_ONLY)
        self.assertEqual(payload["challenge"]["expected_sequence"], 0)

    def test_38_cli_signed_publish_and_readonly_receipt(self):
        envelope = self.signed()
        code, payload, stderr = self.cli("publish", envelope=envelope)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(payload["publication_receipt"]["receipt"]["sequence"], 1)
        code, payload, stderr = self.cli("receipt", request_id=envelope.request.request_id)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(payload["publication_receipt"]["receipt"]["request_id"],
                         envelope.request.request_id)

    def test_39_cli_missing_signature_denied(self):
        self.assert_cli_denied(self.cli("publish"), "invalid_publish_shape")

    def test_40_cli_attacker_extra_public_key_denied(self):
        env = self.signed()
        self.assert_cli_denied(self.cli("publish", envelope=env, overrides={
            "attacker_public_key": raw_public(self.publisher).hex(),
        }), "invalid_top_level_request")

    def test_41_cli_duplicate_json_key_denied(self):
        self.assert_cli_denied(self.cli("head", raw='{"operation":"head","operation":"publish"}'),
                               "duplicate_json_field")

    def test_42_cli_unknown_operation_denied(self):
        self.assert_cli_denied(self.cli("external-provider"), "unsupported_operation")

    def test_43_cli_worker_enabled_denied(self):
        self.assert_cli_denied(self.cli("head", env_overrides={"AION_WORKER_ENABLED":"1"}),
                               "worker_must_be_disabled")

    def test_44_cli_non_lab_mode_denied(self):
        self.assert_cli_denied(self.cli("head", env_overrides={"AION_LAB_MODE":"0"}),
                               "lab_mode_required")

    def test_45_cli_second_process_cas_denies_unsigned_request(self):
        code, payload, stderr = self.cli("publish", envelope=self.signed(
            signer=Ed25519PrivateKey.generate()
        ))
        self.assertEqual(code, 2, stderr)
        self.assertIn("publisher_signature_invalid", payload["error"])
        self.assertEqual(self.witness.read_head()["sequence"], 0)

    def test_46_crash_before_commit_does_not_consume_challenge(self):
        envelope = self.signed()
        code, payload, stderr = self.cli(
            "publish", envelope=envelope, fault="before_commit",
            env_overrides={"AION_A149_FAULT_LAB":"1"},
        )
        self.assertEqual(code, 91, stderr)
        self.assertIsNone(payload)
        self.assertEqual(self.reopen().read_head()["sequence"], 0)
        self.assertIsNone(self.reopen().read_receipt(envelope.request.request_id))

    def test_47_crash_after_commit_lost_reply_has_signed_receipt(self):
        envelope = self.signed()
        code, payload, stderr = self.cli(
            "publish", envelope=envelope, fault="after_commit",
            env_overrides={"AION_A149_FAULT_LAB":"1"},
        )
        self.assertEqual(code, 92, stderr)
        self.assertIsNone(payload)
        self.assertEqual(self.reopen().read_head()["sequence"], 1)
        signed = self.reopen().read_receipt(envelope.request.request_id)
        self.assertEqual(verify_signed_receipt(
            envelope=signed, pinned_witness_key=self.pinned_witness
        ).request_id, envelope.request.request_id)
        with self.assertRaisesRegex(A149Denied, "challenge_already_consumed"):
            self.reopen().publish(envelope=envelope)

    def test_48_cli_fault_injection_requires_lab_switch(self):
        self.assert_cli_denied(
            self.cli("publish", envelope=self.signed(), fault="after_commit"),
            "unauthorized_fault_injection",
        )

    def test_49_local_first_intent_stays_uncertain_after_witness_attestation(self):
        local = self.root / "local_journal"
        local.mkdir()
        journal = SyntheticCrashJournalLAB.bootstrap_synthetic_lab(
            lab_dir=local, ledger_id="ledger-A",
        )
        journal.reserve_local_uncertain("synthetic_first")
        self.witness.publish(envelope=self.signed())
        self.assertEqual(self.witness.read_head()["sequence"], 1)
        with self.assertRaisesRegex(Exception, "unresolved_first_operation"):
            journal.reserve_local_uncertain("synthetic_second")

    def test_50_signed_receipt_does_not_prove_provider_effect(self):
        signed = self.witness.publish(envelope=self.signed())
        receipt = verify_signed_receipt(
            envelope=signed, pinned_witness_key=self.pinned_witness,
        )
        self.assertEqual(receipt.sequence, 1)
        # This payload signs a witness CAS, NOT any external provider result.
        self.assertEqual(set(PublicationReceipt.__dataclass_fields__), {
            "ledger_id", "epoch", "request_id", "challenge_id", "sequence",
            "history_digest", "request_digest",
        })


if __name__ == "__main__":
    unittest.main()
