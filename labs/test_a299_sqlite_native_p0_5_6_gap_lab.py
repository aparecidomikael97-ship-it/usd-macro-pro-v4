"""A299 LAB: WAL copy loses acknowledged data, native identity still no-go."""
import unittest

from labs.a299_sqlite_native_p0_5_6_gap_lab import (
    G17, G18, SCHEMA,
    probe_main_file_copy_vs_sqlite_backup,
    inspect_actual_store_native_boundary,
    probe_combined_p0_5_6_negative_evidence,
)


class A299RealWALCopyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = probe_main_file_copy_vs_sqlite_backup()

    def test_ordinary_commit_was_visible_through_wal(self):
        self.assertEqual(self.result["checkpoint_busy"], 0)
        self.assertEqual(self.result["before_message_count"], 0)
        self.assertEqual(self.result["sequence"], 1)
        self.assertEqual(
            self.result["external_original_reads_committed_message"], 1
        )
        self.assertTrue(self.result["wal_file_nonempty_after_commit"])
        self.assertGreater(self.result["wal_bytes_after_commit"], 0)

    def test_raw_main_db_copy_can_lose_committed_message(self):
        self.assertEqual(self.result["main_only_copy_message_count"], 0)
        self.assertTrue(self.result["lost_committed_message_in_main_only_copy"])

    def test_sqlite_backup_captures_commit_and_original_stays_correct(self):
        self.assertEqual(self.result["native_backup_message_count"], 1)
        self.assertEqual(self.result["primary_after_close_message_count"], 1)

    def test_local_marker_cleared_does_not_prove_raw_copy_durable(self):
        self.assertTrue(self.result["pending_marker_absent_after_ack"])
        self.assertTrue(self.result["store_still_healthy"])
        self.assertFalse(self.result["power_loss_durability_proved"])

    def test_no_live_effect_or_p0_claim_from_wal_experiment(self):
        self.assertTrue(self.result["research_only"])
        self.assertTrue(self.result["native_sqlite3_not_mocked"])
        self.assertFalse(self.result["can_authorize_real_effect"])
        self.assertEqual(self.result["p0_homologated"], 0)
        self.assertTrue(self.result["hard_no_go"])
        self.assertTrue(self.result["zero_auto_resend"])


class A299NativeSourceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = inspect_actual_store_native_boundary()

    def test_current_store_has_only_local_observation_fences(self):
        self.assertTrue(self.result["current_store_has_pathname_identity_guard"])
        self.assertTrue(self.result["current_store_has_local_data_version_guard"])
        self.assertTrue(self.result["current_store_uses_local_commit_marker"])

    def test_current_store_does_not_load_unsigned_native_extension(self):
        self.assertFalse(
            self.result["current_store_calls_native_extension_loader"]
        )
        self.assertFalse(self.result["native_fd_attestation_callable_found"])

    def test_g17_g18_are_separate_lab_native_probes(self):
        self.assertEqual(G17["pr_number"], 1504)
        self.assertEqual(G18["pr_number"], 1505)
        self.assertIn("SQLITE_FCNTL_HAS_MOVED", G17["probe"])
        self.assertIn("SQLITE_FCNTL_WIN32_GET_HANDLE", G18["probe"])
        self.assertTrue(
            self.result["g17_g18_github_source_reviewed_not_executed"]
        )
        self.assertEqual(
            G18["risk"], "CLOSED_HOST_REPLACE_WRONG_CONTENT_NATIVE_MATCH_RED"
        )

    def test_native_identity_and_unsigned_binary_remain_no_go(self):
        self.assertTrue(self.result["runtime_native_identity_not_proven"])
        self.assertTrue(
            self.result["native_extension_supply_chain_not_reviewed_for_production"]
        )
        self.assertFalse(self.result["authenticated_vfs_fd_identity"])
        self.assertFalse(self.result["p0_5_homologated"])
        self.assertFalse(self.result["p0_6_homologated"])


class A299P0BoundariesNegativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = probe_combined_p0_5_6_negative_evidence()

    def test_external_process_can_write_without_marker(self):
        self.assertTrue(self.result["other_pid_can_commit_unmarked_data"])

    def test_closed_rollback_reopens_as_healthy(self):
        self.assertTrue(self.result["closed_valid_rollback_still_accepted"])

    def test_ack_loss_must_stay_uncertain_and_no_auto_retry(self):
        self.assertTrue(self.result["commit_may_succeed_before_ack_loss"])
        self.assertTrue(self.result["zero_auto_resend"])

    def test_private_same_process_sql_bypass_remains(self):
        self.assertTrue(self.result["same_process_private_sql_bypass_remains"])

    def test_negative_security_evidence_cannot_homologate_p0(self):
        self.assertTrue(
            self.result["no_canonical_p0_closure_from_negative_tests"]
        )
        self.assertEqual(self.result["schema"], SCHEMA)
        self.assertFalse(self.result["can_authorize_real_effect"])
        self.assertEqual(self.result["p0_homologated"], 0)
        self.assertFalse(self.result["power_loss_durability_proved"])
        self.assertFalse(self.result["authenticated_vfs_fd_identity"])
        self.assertTrue(self.result["no_provider_worker_deploy_orders"])


if __name__ == "__main__":
    unittest.main()
