"""A290 LAB: cache-safe cooperative SQLite write facade and hard limits."""
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from labs.a290_sqlite_local_write_gate_lab import (
    SCHEMA, MODES, WRITE_ACTIONS, LocalWritePermitGate,
    probe_gate_mode, probe_same_process_uninstalls_authorizer,
)


class A290SQLiteLocalWriteGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modes = {
            mode: probe_gate_mode(mode=mode) for mode in sorted(MODES)
        }
        cls.disabled = probe_same_process_uninstalls_authorizer()

    def test_01_trusted_writer_commits_once_in_all_modes(self):
        for mode, result in self.modes.items():
            with self.subTest(mode=mode):
                self.assertEqual(result["schema"], SCHEMA)
                self.assertEqual(result["trusted_increment_value"], 2)

    def test_02_uncached_statements_block_same_sql_outside_lease(self):
        result = self.modes["uncached"]
        self.assertEqual(result["cached_statements"], 0)
        self.assertTrue(result["second_write_blocked"])
        self.assertEqual(result["final_value"], 2)

    def test_03_cached_rearm_blocks_same_sql_after_lease_revocation(self):
        result = self.modes["cached_rearmed"]
        self.assertTrue(result["rearm_on_revocation"])
        self.assertTrue(result["second_write_blocked"])
        self.assertEqual(result["final_value"], 2)

    def test_04_negative_unrearmed_cache_allows_unauthorized_repeat(self):
        result = self.modes["cached_unrearmed"]
        self.assertFalse(result["rearm_on_revocation"])
        self.assertFalse(result["second_write_blocked"])
        self.assertEqual(result["final_value"], 3)

    def test_05_denials_recompile_only_when_cache_removed_or_rearmed(self):
        for mode in ("uncached", "cached_rearmed"):
            with self.subTest(mode=mode):
                self.assertGreaterEqual(
                    self.modes[mode]["second_write_authorizer_checks"], 1
                )
        self.assertEqual(
            self.modes["cached_unrearmed"]["second_write_authorizer_checks"], 0
        )

    def test_06_raw_python_handle_can_explicitly_remove_authorizer(self):
        self.assertTrue(self.disabled["raw_handle_authorizer_removed"])
        self.assertTrue(self.disabled["write_succeeded_after_removal"])
        self.assertEqual(self.disabled["final_value"], 3)
        self.assertTrue(self.disabled["not_a_host_boundary"])

    def test_07_data_version_never_attests_own_connection_writes(self):
        for mode, result in self.modes.items():
            with self.subTest(mode=mode):
                self.assertTrue(result["local_data_version_unchanged"])

    def test_08_native_sqlite_quick_check_does_not_attest_write_lease(self):
        for mode, result in self.modes.items():
            with self.subTest(mode=mode):
                self.assertTrue(result["quick_check_ok"])
                self.assertFalse(result["native_fd_authenticated"])

    def test_09_facade_does_not_expose_public_generic_execute(self):
        for mode, result in self.modes.items():
            with self.subTest(mode=mode):
                self.assertTrue(result["no_public_execute_method"])
                self.assertTrue(result["raw_python_handle_reachable"])

    def test_10_read_without_lease_is_allowed(self):
        with TemporaryDirectory(prefix="a290-read-") as raw:
            gate = LocalWritePermitGate(Path(raw) / "staging.db")
            try:
                self.assertEqual(gate.read_value(), 1)
                self.assertEqual(gate.trusted_increment(), 2)
                self.assertEqual(gate.read_value(), 2)
            finally:
                gate.close()

    def test_11_direct_insert_is_denied_when_no_lease(self):
        with TemporaryDirectory(prefix="a290-insert-") as raw:
            gate = LocalWritePermitGate(Path(raw) / "staging.db")
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    gate._db.execute("INSERT INTO state VALUES(2, 2)")
                self.assertEqual(gate.read_value(), 1)
            finally:
                gate.close()

    def test_12_direct_delete_is_denied_when_no_lease(self):
        with TemporaryDirectory(prefix="a290-delete-") as raw:
            gate = LocalWritePermitGate(Path(raw) / "staging.db")
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    gate._db.execute("DELETE FROM state")
                self.assertEqual(gate.read_value(), 1)
            finally:
                gate.close()

    def test_13_schema_create_is_denied_outside_lease(self):
        with TemporaryDirectory(prefix="a290-schema-") as raw:
            gate = LocalWritePermitGate(Path(raw) / "staging.db")
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    gate._db.execute("CREATE TABLE rogue(x INTEGER)")
                self.assertEqual(gate.read_value(), 1)
            finally:
                gate.close()

    def test_14_nested_local_leases_are_refused(self):
        with TemporaryDirectory(prefix="a290-nested-") as raw:
            gate = LocalWritePermitGate(Path(raw) / "staging.db")
            try:
                with gate._authorized_write():
                    with self.assertRaisesRegex(
                        RuntimeError, "nested write lease"
                    ):
                        with gate._authorized_write():
                            pass
                self.assertEqual(gate.trusted_increment(), 2)
            finally:
                gate.close()

    def test_15_closed_gate_never_reopens_via_read_or_trusted_write(self):
        with TemporaryDirectory(prefix="a290-closed-") as raw:
            gate = LocalWritePermitGate(Path(raw) / "staging.db")
            gate.close()
            with self.assertRaisesRegex(RuntimeError, "closed or failed"):
                gate.read_value()
            with self.assertRaisesRegex(RuntimeError, "closed or failed"):
                gate.trusted_increment()

    def test_16_invalid_modes_are_denied_before_file_creation(self):
        with TemporaryDirectory(prefix="a290-type-") as raw:
            path = Path(raw) / "staging.db"
            for invalid in (None, 1, True, "", "unknown", [], {}):
                with self.subTest(invalid=repr(invalid)):
                    with self.assertRaises(ValueError):
                        LocalWritePermitGate(path, mode=invalid)
                    with self.assertRaises(ValueError):
                        probe_gate_mode(mode=invalid)
            self.assertFalse(path.exists())

    def test_17_authorizer_write_set_contains_crucial_dml_actions(self):
        for action in (
            sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE
        ):
            self.assertIn(action, WRITE_ACTIONS)

    def test_18_all_results_remain_lab_no_go_and_zero_auto_resend(self):
        for result in [*self.modes.values(), self.disabled]:
            self.assertTrue(result["research_only"])
            self.assertTrue(result["same_process_cooperation_only"])
            self.assertTrue(result["zero_auto_resend"])
            self.assertTrue(result["no_provider_worker_deploy_orders"])
            self.assertFalse(result["authorizes_send"])
            self.assertFalse(result["off_host_rollback_floor"])
            self.assertFalse(result["independent_owner_identity"])
            self.assertEqual(result["p0_homologated"], 0)


if __name__ == "__main__":
    unittest.main()
