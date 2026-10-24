"""G27 adversarial durable local custody: restart GREEN and host rollback RED."""
from pathlib import Path
import shutil
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from g20_independent_witness_recovery_contract_lab import Admission, RecoveryDenied, canonical_hash
from g24_challenge_bound_witness_lab import new_challenge
from g25_monotonic_custody_contract_lab import inspect_monotonic_recovery
from g26_isolated_custody_service_lab import CustodyConflict
from g27_durable_sqlite_custody_lab import DurableCustodyLab

ROOT = "G27_LOCAL_LAB_ROOT"
KEY = "tenant:invoice:42"


def journal(seq, key=KEY, effect="UNKNOWN"):
    return {"semantic_key": key, "sequence": seq, "phase": "UNCERTAIN", "effect": effect}


class G27DurableSQLiteCustody(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-g27-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "custody.sqlite3"
        self.signer = Ed25519PrivateKey.generate()
        self.public = self.signer.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.db = self.open()
        self.addCleanup(self.db.close)
        self.first = self.db.reserve(KEY, "UNCERTAIN", canonical_hash(journal(1)))

    def open(self):
        return DurableCustodyLab(self.path, self.signer, ROOT)

    def admission(self, service, key=KEY, local=None, nonce=None):
        ch = new_challenge() if nonce is None else nonce
        return inspect_monotonic_recovery(
            semantic_key=key,
            local_journal=journal(1) if local is None else local,
            witness_response=service.attest(key, ch),
            pinned_root_id=ROOT,
            pinned_public_key=self.public,
            verifier_challenge=ch,
            external_high_water=service.high_water(key),
        )

    def test_01_first_reservation_sequence_one(self):
        self.assertEqual(self.first.sequence, 1)

    def test_02_persistent_reservation_after_reopen(self):
        self.db.close()
        self.db = self.open()
        self.assertEqual(self.db.read(KEY), self.first)
        print("G27_RESTART_GREEN=RESERVATION_SURVIVES_REOPEN")

    def test_03_reopened_attestation_matches_only_uncertain(self):
        self.db.close()
        self.db = self.open()
        self.assertEqual(self.admission(self.db), Admission.UNCERTAIN)

    def test_04_exact_duplicate_reservation_idempotent_after_restart(self):
        self.db.close()
        self.db = self.open()
        self.assertEqual(
            self.db.reserve(KEY, "UNCERTAIN", canonical_hash(journal(1))),
            self.first,
        )

    def test_05_conflicting_same_semantic_key_denies(self):
        with self.assertRaisesRegex(CustodyConflict, "G27_SEMANTIC_REUSE_CONFLICT"):
            self.db.reserve(KEY, "UNCERTAIN", "a" * 64)

    def test_06_conflicting_phase_denies(self):
        with self.assertRaisesRegex(CustodyConflict, "G27_SEMANTIC_REUSE_CONFLICT"):
            self.db.reserve(KEY, "RESERVED", canonical_hash(journal(1)))

    def test_07_second_key_monotonic_sequence_after_restart(self):
        self.db.close()
        self.db = self.open()
        other = "tenant:invoice:43"
        second = self.db.reserve(other, "UNCERTAIN", canonical_hash(journal(2, other)))
        self.assertEqual(second.sequence, 2)

    def test_08_two_connections_unique_sequence(self):
        with self.open() as other_db:
            other = "tenant:invoice:43"
            second = other_db.reserve(other, "UNCERTAIN", canonical_hash(journal(2, other)))
            third_key = "tenant:invoice:44"
            third = self.db.reserve(third_key, "UNCERTAIN", canonical_hash(journal(3, third_key)))
            self.assertEqual((second.sequence, third.sequence), (2, 3))

    def test_09_second_connection_conflict_denied(self):
        with self.open() as other_db:
            with self.assertRaisesRegex(CustodyConflict, "G27_SEMANTIC_REUSE_CONFLICT"):
                other_db.reserve(KEY, "UNCERTAIN", "b" * 64)

    def test_10_missing_key_denies(self):
        with self.assertRaisesRegex(CustodyConflict, "G27_CUSTODY_RESERVATION_MISSING"):
            self.db.read("missing")

    def test_11_invalid_digest_denies(self):
        with self.assertRaisesRegex(CustodyConflict, "G27_INVALID_DIGEST"):
            self.db.reserve("new", "UNCERTAIN", "g" * 64)

    def test_12_invalid_phase_denies(self):
        with self.assertRaisesRegex(CustodyConflict, "G27_INVALID_PHASE"):
            self.db.reserve("new", "SEND", "a" * 64)

    def test_13_local_sequence_rollback_denies(self):
        with self.assertRaisesRegex(RecoveryDenied, "LOCAL_SEQUENCE_MISMATCH"):
            self.admission(self.db, local=journal(0))

    def test_14_local_payload_tamper_denies(self):
        with self.assertRaisesRegex(RecoveryDenied, "LOCAL_DIGEST_MISMATCH"):
            self.admission(self.db, local=journal(1, effect="CONFIRMED"))

    def test_15_custody_db_deleted_then_recreated_loses_history_red(self):
        self.db.close()
        self.path.unlink()
        self.db = self.open()
        with self.assertRaisesRegex(CustodyConflict, "G27_CUSTODY_RESERVATION_MISSING"):
            self.db.read(KEY)
        print("G27_HOST_DELETE_RED=LOCAL_CUSTODY_RECORD_LOST")

    def test_16_host_replaces_custody_with_old_snapshot_red(self):
        # Both local custody files live on same host; old copy is attacker-held.
        backup = Path(self.tmp.name) / "old.sqlite3"
        self.db.close()
        shutil.copyfile(self.path, backup)
        self.db = self.open()
        other = "tenant:invoice:43"
        self.db.reserve(other, "UNCERTAIN", canonical_hash(journal(2, other)))
        self.db.close()
        shutil.copyfile(backup, self.path)
        self.db = self.open()
        self.assertEqual(self.admission(self.db), Admission.UNCERTAIN)
        with self.assertRaisesRegex(CustodyConflict, "G27_CUSTODY_RESERVATION_MISSING"):
            self.db.read(other)
        print("G27_HOST_ROLLBACK_RED=OLD_SQLITE_CUSTODY_ACCEPTED")

    def test_17_host_replaces_custody_counter_resets_red(self):
        backup = Path(self.tmp.name) / "old.sqlite3"
        self.db.close()
        shutil.copyfile(self.path, backup)
        self.db = self.open()
        self.db.reserve("tenant:invoice:43", "UNCERTAIN", "a" * 64)
        self.db.close()
        shutil.copyfile(backup, self.path)
        self.db = self.open()
        next_row = self.db.reserve("tenant:invoice:99", "UNCERTAIN", "b" * 64)
        self.assertEqual(next_row.sequence, 2)
        print("G27_HOST_COUNTER_ROLLBACK_RED=SEQUENCE_REUSED_AFTER_RESTORE")

    def test_18_matching_custody_never_authorizes_send(self):
        self.assertNotEqual(self.admission(self.db), "SEND")


if __name__ == "__main__":
    unittest.main()
