"""A300 negative tests: passing means counterexamples reproduced, not GO."""
import unittest
from aion_chat.store import HEALTHY
from labs.a300_cold_restart_sqlite_recovery_lab import (
    SCHEMA, probe_cold_restart_after_incomplete_wal_copy,
    probe_uncertain_ack_marker_not_in_database_backup,
)


class A300ColdWALTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = probe_cold_restart_after_incomplete_wal_copy()

    def test_committed_in_wal_before_copy(self):
        self.assertEqual(self.r["checkpoint_busy"], 0)
        self.assertEqual(self.r["committed_sequence"], 1)
        self.assertGreater(self.r["wal_bytes_before_close"], 0)
        self.assertEqual(self.r["another_connection_saw_commit"], 1)

    def test_raw_snapshot_is_missing_wal_sidecar(self):
        self.assertTrue(self.r["raw_snapshot_wal_missing"])

    def test_raw_cold_reopen_healthy_but_loses_acknowledged_message(self):
        self.assertEqual(self.r["raw_main_cold"]["health"], HEALTHY)
        self.assertEqual(self.r["raw_main_cold"]["message_count"], 0)
        self.assertTrue(self.r["silent_loss_in_healthy_cold_raw_copy"])

    def test_native_backup_cold_reopen_has_message(self):
        self.assertEqual(self.r["backup_cold"]["health"], HEALTHY)
        self.assertEqual(self.r["backup_cold"]["message_ids"],
                         ["a300-confirmed-message"])

    def test_original_cold_reopen_has_message(self):
        self.assertEqual(self.r["original_cold"]["message_count"], 1)
        self.assertTrue(self.r["normal_ack_marker_absent"])

    def test_no_power_cut_or_real_recovery_claim(self):
        self.assertFalse(self.r["power_cut_simulated"])
        self.assertFalse(self.r["production_recovery_validated"])
        self.assertTrue(self.r["store_restore_apis_not_called"])

    def test_no_p0_closure(self):
        self.assertEqual(self.r["schema"], SCHEMA)
        self.assertEqual(self.r["p0_homologated"], 0)
        self.assertTrue(self.r["hard_no_go"])


class A300PendingAckMarkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = probe_uncertain_ack_marker_not_in_database_backup()

    def test_commit_succeeded_before_synthetic_ack_loss(self):
        self.assertTrue(self.r["uncertain_error"])
        self.assertEqual(self.r["confirmed_sqlite_effect"], 1)
        self.assertTrue(self.r["store_failed_sticky"])

    def test_original_restart_refuses_pending_marker(self):
        self.assertTrue(self.r["original_pending_marker"])
        self.assertTrue(self.r["original_cold_restart_refused"])

    def test_relocated_sqlite_db_does_not_have_marker(self):
        self.assertTrue(self.r["relocated_marker_absent"])

    def test_relocated_database_looks_healthy_despite_uncertainty(self):
        self.assertEqual(self.r["relocated_db_cold"]["health"], HEALTHY)
        self.assertEqual(self.r["relocated_db_cold"]["message_ids"],
                         ["a300-uncertain-message"])
        self.assertTrue(self.r["relocation_drops_uncertain_ack_veto"])

    def test_zero_auto_resend_in_all_cases(self):
        self.assertEqual(self.r["automatic_retry_attempts"], 0)
        self.assertTrue(self.r["zero_auto_resend"])
        self.assertFalse(self.r["can_authorize_real_effect"])

    def test_isolated_test_environment(self):
        self.assertTrue(self.r["research_only"])
        self.assertTrue(self.r["temporary_paths_only"])
        self.assertTrue(self.r["real_sqlite3_and_chat_store"])
        self.assertTrue(self.r["no_paid_services"])
        self.assertTrue(self.r["no_provider_worker_deploy_orders"])

    def test_native_fd_and_independent_custody_still_missing(self):
        self.assertFalse(self.r["native_fd_attested"])
        self.assertFalse(self.r["off_host_rollback_witness"])
        self.assertFalse(self.r["p0_5_homologated"])
        self.assertFalse(self.r["p0_6_homologated"])
        self.assertEqual(self.r["p0_homologated"], 0)
        self.assertTrue(self.r["hard_no_go"])


if __name__ == "__main__":
    unittest.main()
