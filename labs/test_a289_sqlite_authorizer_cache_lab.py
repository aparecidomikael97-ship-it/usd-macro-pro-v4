"""A289: real Python sqlite3 compile-time authorizer and cache limits."""
import unittest

from aion_chat.store import HEALTHY
from labs.a289_sqlite_authorizer_cache_lab import (
    SCHEMA, MODES, probe_dynamic_authorizer_reuse,
    probe_cached_select_authorizer_reuse, probe_real_store_same_handle_write,
)


class A289NativeSQLiteAuthorizerCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runs = {
            mode: probe_dynamic_authorizer_reuse(mode=mode)
            for mode in sorted(MODES)
        }
        cls.read = probe_cached_select_authorizer_reuse()
        cls.real = probe_real_store_same_handle_write()

    def test_01_cached_dynamic_grant_does_not_revoke_prepared_update(self):
        p = self.runs["cached_dynamic"]
        self.assertEqual(p["schema"], SCHEMA)
        self.assertFalse(p["second_update_blocked"])
        self.assertEqual(p["trusted_update_value"], 2)
        self.assertEqual(p["final_value"], 3)

    def test_02_callback_did_not_recheck_cached_update_after_revoke(self):
        p = self.runs["cached_dynamic"]
        self.assertGreaterEqual(p["authorized_update_checks"], 1)
        self.assertEqual(p["after_revoke_update_checks"], 0)
        self.assertTrue(p["callback_not_runtime_write_proof"])

    def test_03_uncached_statements_force_new_compile_and_deny(self):
        p = self.runs["uncached_dynamic"]
        self.assertEqual(p["cached_statements"], 0)
        self.assertTrue(p["second_update_blocked"])
        self.assertGreaterEqual(p["after_revoke_update_checks"], 1)
        self.assertEqual(p["final_value"], 2)

    def test_04_reinstall_authorizer_invalidates_cached_grant(self):
        p = self.runs["reinstall_after_revoke"]
        self.assertTrue(p["new_authorizer_installed"])
        self.assertTrue(p["second_update_blocked"])
        self.assertGreaterEqual(p["after_revoke_update_checks"], 1)
        self.assertEqual(p["final_value"], 2)

    def test_05_same_handle_can_explicitly_disable_authorizer(self):
        p = self.runs["disable_authorizer"]
        self.assertTrue(p["authorizer_disabled_by_same_process"])
        self.assertFalse(p["second_update_blocked"])
        self.assertEqual(p["final_value"], 3)

    def test_06_new_statement_sql_is_compiled_and_denied(self):
        p = self.runs["distinct_sql"]
        self.assertTrue(p["second_update_blocked"])
        self.assertGreaterEqual(p["after_revoke_update_checks"], 1)
        self.assertEqual(p["final_value"], 2)

    def test_07_self_connection_data_version_never_attests_own_writes(self):
        for mode, p in self.runs.items():
            with self.subTest(mode=mode):
                self.assertTrue(p["local_data_version_unchanged"])
                self.assertFalse(p["is_independent_witness"])

    def test_08_native_quick_check_ok_in_every_cache_control(self):
        for mode, p in self.runs.items():
            with self.subTest(mode=mode):
                self.assertTrue(p["native_quick_check_ok"])

    def test_09_strict_real_store_exposes_direct_raw_handle_mutation(self):
        self.assertTrue(self.real["strict_mode_active"])
        self.assertEqual(
            self.real["returned_raw_same_handle_title"], "raw-same-handle"
        )

    def test_10_real_store_local_version_and_health_stay_healthy(self):
        self.assertTrue(self.real["version_unchanged"])
        self.assertEqual(self.real["health_before"], HEALTHY)
        self.assertEqual(self.real["health_after"], HEALTHY)
        self.assertTrue(self.real["integrity_ok"])

    def test_11_same_inode_still_cannot_authenticate_same_handle_history(self):
        self.assertTrue(self.real["same_path_inode"])
        self.assertTrue(self.real["raw_handle_is_not_independent_authority"])
        self.assertFalse(self.real["native_fd_authenticated"])

    def test_12_raw_write_did_not_use_protected_commit_marker(self):
        self.assertFalse(self.real["pending_chat_commit_marker_exists"])

    def test_13_cached_select_also_bypasses_dynamic_read_revocation(self):
        p = self.read
        self.assertEqual(p["first_value"], 7)
        self.assertTrue(p["read_returned_after_revoke"])
        self.assertEqual(p["second_value"], 7)
        self.assertGreaterEqual(p["first_compile_checks"], 1)
        self.assertEqual(p["second_compile_checks"], 0)

    def test_14_invalid_mode_fails_closed_before_sqlite(self):
        for mode in (None, True, 0, "unknown", [], {}):
            with self.subTest(mode=repr(mode)):
                with self.assertRaises(ValueError):
                    probe_dynamic_authorizer_reuse(mode=mode)

    def test_15_all_observations_keep_hard_no_go_and_no_send(self):
        for p in [*self.runs.values(), self.read, self.real]:
            self.assertTrue(p["research_only"])
            self.assertTrue(p["zero_auto_resend"])
            self.assertTrue(p["no_provider_worker_deploy_orders"])
            self.assertFalse(p["can_authorize_send"])
            self.assertFalse(p["off_host_rollback_floor"])
            self.assertEqual(p["p0_homologated"], 0)

    def test_16_only_recompilation_not_runtime_callback_explains_controls(self):
        cached = self.runs["cached_dynamic"]
        uncached = self.runs["uncached_dynamic"]
        reinstalled = self.runs["reinstall_after_revoke"]
        self.assertFalse(cached["second_update_blocked"])
        self.assertTrue(uncached["second_update_blocked"])
        self.assertTrue(reinstalled["second_update_blocked"])
        self.assertEqual(cached["after_revoke_update_checks"], 0)
        self.assertGreaterEqual(
            uncached["after_revoke_update_checks"], 1
        )


if __name__ == "__main__":
    unittest.main()
