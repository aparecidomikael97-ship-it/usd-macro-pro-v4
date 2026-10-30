"""A293 LAB regression: external SQL tamper and restored old SQLite history."""
import os
import unittest

from labs.a293_host_sqlite_boundary_lab import (
    SCHEMA, probe_closed_store_rollback, probe_external_process_write,
    probe_live_pathname_swap,
)


class A293CrossProcessNativeSQLiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.strict = probe_external_process_write(strict=True)
        cls.default = probe_external_process_write(strict=False)

    def test_external_process_successfully_writes_without_local_marker(self):
        for result in (self.strict, self.default):
            with self.subTest(strict=result["strict_single_writer_mode"]):
                self.assertTrue(result["independent_process_exit_zero"])
                self.assertTrue(result["external_process_sql_changed_title"])
                self.assertTrue(result["external_change_visible_before_guard"])
                self.assertTrue(result["no_local_marker_before_or_after"])

    def test_opt_in_strict_data_version_detects_external_commit_late(self):
        self.assertTrue(self.strict["guard_rejected_next_read"])
        self.assertTrue(self.strict["store_health_failed"])
        self.assertEqual(self.strict["local_reason"], "LOCAL_DATA_VERSION_CHANGED")

    def test_non_strict_mode_does_not_block_external_commit(self):
        self.assertFalse(self.default["guard_rejected_next_read"])
        self.assertFalse(self.default["store_health_failed"])
        self.assertEqual(self.default["local_reason"], "OK")

    def test_external_process_is_not_external_authorization_proof(self):
        for result in (self.strict, self.default):
            self.assertFalse(result["native_fd_authenticated"])
            self.assertFalse(result["off_host_witness"])
            self.assertFalse(result["independent_authority"])
            self.assertFalse(result["cross_process_tamper_resistance_proved"])
            self.assertEqual(result["p0_homologated"], 0)
            self.assertTrue(result["production_hard_no_go"])


class A293HostRollbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = probe_closed_store_rollback()

    def test_real_new_history_is_confirmed_before_rollback(self):
        self.assertEqual(self.result["baseline_old_count"], 0)
        self.assertEqual(self.result["new_message_sequence"], 1)
        self.assertEqual(self.result["count_before_rollback"], 1)

    def test_host_controlled_old_snapshot_erases_message(self):
        self.assertEqual(self.result["count_after_rollback"], 0)
        self.assertEqual(self.result["reopened_conversation_message_count"], 0)
        self.assertTrue(self.result["older_history_silently_accepted"])

    def test_local_marker_and_strict_reopen_do_not_witness_old_history(self):
        self.assertTrue(self.result["marker_absent_after_host_rollback"])
        self.assertTrue(self.result["strict_reopen_health_healthy"])
        self.assertFalse(self.result["off_host_witness"])
        self.assertFalse(self.result["native_fd_authenticated"])


class A293LivePathSwapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = probe_live_pathname_swap()

    def test_platform_scope_is_explicit(self):
        self.assertEqual(self.result["supported_host"], os.name == "posix")
        self.assertEqual(self.result["tested"], os.name == "posix")
        if os.name != "posix":
            self.assertEqual(
                self.result["reason"],
                "HOT_REPLACE_OPEN_SQLITE_NOT_PORTABLE_ON_WINDOWS",
            )

    def test_posix_pathname_identity_guard_detects_open_file_swap(self):
        if os.name != "posix":
            self.skipTest("Windows hot replacement of open SQLite is not tested")
        self.assertEqual(self.result["pathname_reason_before"], "OK")
        self.assertEqual(
            self.result["pathname_reason_after"], "PATH_IDENTITY_CHANGED"
        )
        self.assertTrue(self.result["next_local_guard_denied"])
        self.assertTrue(self.result["subsequent_local_guard_denied_sticky"])
        self.assertTrue(self.result["health_failed_sticky"])
        self.assertEqual(self.result["local_reason"], "PATH_IDENTITY_CHANGED")
        self.assertTrue(self.result["pending_marker_absent"])

    def test_no_native_vfs_fd_authentication_claim(self):
        self.assertFalse(self.result["native_fd_authenticated"])
        self.assertFalse(self.result["off_host_witness"])
        self.assertFalse(self.result["cross_process_tamper_resistance_proved"])


class A293PolicyScopeTests(unittest.TestCase):
    def test_invalid_strict_flag_is_rejected(self):
        for bad in ("true", 1, None, []):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(ValueError):
                    probe_external_process_write(strict=bad)

    def test_all_probe_types_are_disposable_lab_only(self):
        for result in (
            probe_external_process_write(strict=True),
            probe_closed_store_rollback(),
            probe_live_pathname_swap(),
        ):
            self.assertEqual(result["schema"], SCHEMA)
            self.assertTrue(result["research_only"])
            self.assertTrue(result["sandbox_disposable_sqlite_only"])
            self.assertTrue(result["no_services_no_deploy_no_worker_no_orders"])
            self.assertTrue(result["zero_auto_resend"])
            self.assertTrue(result["production_hard_no_go"])
            self.assertEqual(result["p0_homologated"], 0)


if __name__ == "__main__":
    unittest.main()
