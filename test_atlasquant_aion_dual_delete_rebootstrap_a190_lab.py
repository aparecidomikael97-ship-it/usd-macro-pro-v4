"""A190 G0 RED-LAB: destroying both local authority files reopens genesis.

All data are synthetic and disposable. Passing this test means a security
counterexample was reproduced; it is NOT a production anti-rollback guarantee.
"""
from pathlib import Path
import tempfile
import unittest

from labs.a189.local_witness_failclosed_lab import GateClosed, LocalWitnessLab


class A190DualDeleteRebootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="a190-g0-")
        self.addCleanup(self.temp.cleanup)
        self.lab = LocalWitnessLab(Path(self.temp.name))
        self.lab.bootstrap_synthetic()

    def test_01_both_files_deleted_reopen_genesis_and_same_semantic_reservation(self):
        first = self.lab.reserve("r-original", "original-event", "effect")
        self.assertEqual(first["status"], "RESERVED_LOCAL_ONLY")
        self.assertEqual(self.lab.admission()["seq"], 1)

        # Lab attacker controls BOTH files, not the issuer of any external truth.
        self.lab.db_path.unlink()
        self.lab.witness_path.unlink()
        self.lab.bootstrap_synthetic()
        self.assertEqual(self.lab.admission()["seq"], 0)

        # Re-reserve the original event: counterexample to H0 anti-rollback.
        second = self.lab.reserve("r-original", "original-event", "effect")
        self.assertEqual(second["status"], "RESERVED_LOCAL_ONLY")
        self.assertEqual(self.lab.admission()["seq"], 1)
        self.assertFalse(second["auto_resend"])
        print("A190_G0_DUAL_DELETE_REBOOTSTRAP=UNSAFE_READMISSION_REPRODUCED")

    def test_02_witness_only_missing_stays_fail_closed(self):
        self.lab.reserve("r-original", "original-event", "effect")
        self.lab.witness_path.unlink()
        with self.assertRaisesRegex(GateClosed, "A189_WITNESS_UNAVAILABLE"):
            self.lab.admission()
        with self.assertRaisesRegex(GateClosed, "A189_REENROLLMENT_REQUIRES_MANUAL_REVIEW"):
            self.lab.bootstrap_synthetic()
        print("A190_G0_WITNESS_ONLY_DELETE=DENIED")

    def test_03_database_only_missing_stays_fail_closed(self):
        self.lab.reserve("r-original", "original-event", "effect")
        self.lab.db_path.unlink()
        with self.assertRaisesRegex(GateClosed, "A189_DB_UNAVAILABLE"):
            self.lab.admission()
        with self.assertRaisesRegex(GateClosed, "A189_REENROLLMENT_REQUIRES_MANUAL_REVIEW"):
            self.lab.bootstrap_synthetic()
        print("A190_G0_DB_ONLY_DELETE=DENIED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
