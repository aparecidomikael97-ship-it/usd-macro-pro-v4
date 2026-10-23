"""A189 LAB — ten falsifiable local monotonicity tests, INCLUDING bypasses.

Green means experiments were reproduced, NOT that trust-root/H0 is fixed.
"""
import json
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from labs.a189.local_witness_failclosed_lab import GateClosed, LocalWitnessLab


class A189LocalWitnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="a189-witness-")
        self.addCleanup(self.tmp.cleanup)
        self.lab = LocalWitnessLab(Path(self.tmp.name))
        self.lab.bootstrap_synthetic()

    def first(self):
        result = self.lab.reserve("req-1", "claimed-e1", "synthetic-data")
        self.assertEqual(result["status"], "RESERVED_LOCAL_ONLY")
        self.assertFalse(result["auto_resend"])
        self.assertEqual(self.lab.admission()["seq"], 1)

    def test_lab_genesis_and_sequence_progression(self):
        self.assertEqual(self.lab.admission(), {"status": "ADMITTED_LOCAL_UNTRUSTED", "seq": 0})
        self.first()
        self.assertEqual(self.lab.reserve("req-2", "claimed-e2", "synthetic")["seq"], 2)
        self.assertEqual(self.lab.admission()["seq"], 2)
        print("A189_LOCAL_SEQUENCE_AND_DIGEST=COHERENT_SYNTHETIC")

    def test_conflict_and_duplicate_claimed_id_denied(self):
        self.first()
        self.assertEqual(self.lab.reserve("req-1", "claimed-e1", "synthetic-data")["status"], "ALREADY_RESERVED_LOCAL")
        self.assertEqual(self.lab.reserve("req-1", "different-e1", "synthetic-data")["status"], "DENIED_REQUEST_CONFLICT")
        self.assertEqual(self.lab.reserve("req-2", "claimed-e1", "synthetic-data")["status"], "DENIED_EVENT_ALREADY_RESERVED")
        self.assertEqual(self.lab.admission()["seq"], 1)
        print("A189_LOCAL_REQUEST_AND_CLAIMED_EVENT_UNIQUENESS=ENFORCED")

    def test_rollback_only_database_denied(self):
        self.first()
        snapshot = Path(self.tmp.name) / "before.sqlite"
        shutil.copyfile(self.lab.db_path, snapshot)
        self.assertEqual(self.lab.reserve("req-2", "claimed-e2", "two")["seq"], 2)
        shutil.copyfile(snapshot, self.lab.db_path)
        with self.assertRaisesRegex(GateClosed, "A189_ROLLBACK_OR_DIVERGENCE_DENIED"):
            self.lab.admission()
        print("A189_DB_ONLY_ROLLBACK_WITH_LOCAL_WITNESS=DENIED")

    def test_rollback_only_witness_denied(self):
        self.first()
        snapshot = Path(self.tmp.name) / "before.json"
        shutil.copyfile(self.lab.witness_path, snapshot)
        self.assertEqual(self.lab.reserve("req-2", "claimed-e2", "two")["seq"], 2)
        shutil.copyfile(snapshot, self.lab.witness_path)
        with self.assertRaisesRegex(GateClosed, "A189_ROLLBACK_OR_DIVERGENCE_DENIED"):
            self.lab.admission()
        print("A189_WITNESS_ONLY_ROLLBACK=DENIED")

    def test_joint_rollback_reopens_stale_history_negative_control(self):
        self.first()
        db_snapshot = Path(self.tmp.name) / "saved.sqlite"
        wit_snapshot = Path(self.tmp.name) / "saved.json"
        shutil.copyfile(self.lab.db_path, db_snapshot)
        shutil.copyfile(self.lab.witness_path, wit_snapshot)
        self.assertEqual(self.lab.reserve("req-2", "claimed-e2", "two")["seq"], 2)
        shutil.copyfile(db_snapshot, self.lab.db_path)
        shutil.copyfile(wit_snapshot, self.lab.witness_path)
        self.assertEqual(self.lab.admission()["seq"], 1)
        self.assertEqual(self.lab.reserve("req-2", "claimed-e2", "two")["status"], "RESERVED_LOCAL_ONLY")
        print("A189_JOINT_LOCAL_DB_PLUS_WITNESS_ROLLBACK=UNSAFE_READMISSION_REPRODUCED")

    def test_forged_local_witness_matches_modified_db_negative_control(self):
        self.first()
        with closing(sqlite3.connect(self.lab.db_path)) as db:
            db.execute("INSERT INTO reservations VALUES(2,'forged-req','forged-event','0')")
            db.commit()
            forged = self.lab._state(db)
        self.lab.witness_path.write_text(json.dumps(forged), encoding="utf-8")
        self.assertEqual(self.lab.admission()["seq"], 2)
        print("A189_SAME_HOST_WITNESS_FORGERY=UNSAFE_READMISSION_REPRODUCED")

    def test_missing_witness_and_reenrollment_fail_closed(self):
        self.first()
        self.lab.witness_path.unlink()
        with self.assertRaisesRegex(GateClosed, "A189_WITNESS_UNAVAILABLE"):
            self.lab.admission()
        with self.assertRaisesRegex(GateClosed, "A189_REENROLLMENT_REQUIRES_MANUAL_REVIEW"):
            self.lab.bootstrap_synthetic()
        fresh = LocalWitnessLab(Path(self.tmp.name) / "new-genesis")
        with self.assertRaisesRegex(GateClosed, "A189_DB_UNAVAILABLE"):
            fresh.admission()
        self.assertFalse(fresh.db_path.exists())
        print("A189_H0_WITNESS_MISSING=DENIED_WITHOUT_AUTO_BOOTSTRAP")

    def test_ack_loss_after_witness_commit_never_authorizes_resend(self):
        result = self.lab.reserve(
            "req-1", "claimed-e1", "synthetic-data", lose_ack_after_witness=True)
        self.assertEqual(result, {"status": "UNCERTAIN", "auto_resend": False})
        self.assertEqual(self.lab.admission()["seq"], 1)
        print("A189_POST_WITNESS_ACK_LOSS=UNCERTAIN_ZERO_AUTO_RESEND")

    def test_split_commit_after_db_before_witness_is_uncertain_and_blocks(self):
        result = self.lab.reserve(
            "req-1", "claimed-e1", "synthetic-data", fail_after_db_commit=True)
        self.assertEqual(result, {"status": "UNCERTAIN", "auto_resend": False})
        with self.assertRaisesRegex(GateClosed, "A189_ROLLBACK_OR_DIVERGENCE_DENIED"):
            self.lab.admission()
        with self.assertRaises(GateClosed):
            self.lab.reserve("req-1", "claimed-e1", "synthetic-data")
        print("A189_SPLIT_COMMIT=UNCERTAIN_AND_DENY_NO_RETRY")

    def test_semantic_original_event_still_self_claimed_negative_control(self):
        self.first()
        self.assertEqual(self.lab.reserve(
            "req-other", "attacker-claimed-other", "synthetic-data")["status"],
            "RESERVED_LOCAL_ONLY")
        self.assertEqual(self.lab.admission()["seq"], 2)
        print("A189_ORIGINAL_EVENT_NOT_AUTHENTICATED=DOUBLE_SEMANTIC_CLAIM_REPRODUCED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
