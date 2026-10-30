"""A285: real local SQLite connection observer, non-custodial negative proof."""
import sqlite3
from tempfile import TemporaryDirectory
from pathlib import Path
from contextlib import closing
import unittest

from labs.a285_sqlite_live_data_version_lab import (
    SCHEMA, LocalDataVersionWatch,
    probe_live_semantic_reversion,
    probe_same_connection_change_not_seen,
)


class A285NativeLiveSQLiteDataVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.delete_mode = probe_live_semantic_reversion(journal_mode="DELETE")
        cls.wal_mode = probe_live_semantic_reversion(journal_mode="WAL")
        cls.self_change = probe_same_connection_change_not_seen()

    def test_01_two_open_connections_see_real_semantic_reversion(self):
        self.assertEqual(self.delete_mode["observed_values"], [1, 2, 1])
        self.assertTrue(self.delete_mode["valid"])

    def test_02_wal_mode_sees_same_reversion(self):
        self.assertEqual(self.wal_mode["observed_values"], [1, 2, 1])
        self.assertTrue(self.wal_mode["valid"])
        self.assertEqual(self.wal_mode["journal_mode"], "WAL")

    def test_03_read_handle_remains_open_during_external_writer_commits(self):
        self.assertEqual(self.delete_mode["journal_mode"], "DELETE")
        self.assertTrue(self.delete_mode[
            "external_sql_commit_detectable_while_reader_open"
        ])

    def test_04_same_path_and_inode_do_not_authenticate_semantic_history(self):
        for observed in (self.delete_mode, self.wal_mode):
            self.assertTrue(observed["same_path_exists"])
            self.assertTrue(observed["same_path_inode"])
            self.assertFalse(observed["same_inode_native_fd_authenticated"])

    def test_05_native_quick_check_ok_while_original_value_restored(self):
        for observed in (self.delete_mode, self.wal_mode):
            self.assertTrue(observed["native_integrity_check"])
            self.assertEqual(observed["observed_values"][0],
                             observed["observed_values"][-1])
            self.assertFalse(observed["antirollback_witness_authenticated"])

    def test_06_data_version_change_must_latch_local_denial(self):
        for observed in (self.delete_mode, self.wal_mode):
            changed = observed["after_external_update"]
            self.assertTrue(changed["local_change_seen"])
            self.assertEqual(changed["decision"],
                             "DENY_LOCAL_EXTERNAL_CHANGE_OR_UNAVAILABLE")
            self.assertFalse(changed["can_authorize_send"])

    def test_07_reversion_to_same_value_does_not_clear_local_denial(self):
        for observed in (self.delete_mode, self.wal_mode):
            following = observed["after_semantic_reversion"]
            self.assertTrue(following["local_change_seen"])
            self.assertEqual(following["decision"],
                             "DENY_LOCAL_EXTERNAL_CHANGE_OR_UNAVAILABLE")

    def test_08_baseline_is_observed_without_authenticating_trust(self):
        for observed in (self.delete_mode, self.wal_mode):
            first = observed["first_check"]
            self.assertFalse(first["local_change_seen"])
            self.assertEqual(first["decision"],
                             "UNCHANGED_LOCAL_HINT_NOT_AUTHORITY")
            self.assertFalse(first["can_authorize_read_as_trusted"])

    def test_09_late_reopen_resets_local_baseline(self):
        for observed in (self.delete_mode, self.wal_mode):
            late = observed["late_open_check"]
            self.assertFalse(late["local_change_seen"])
            self.assertFalse(late["is_independent_witness"])
            self.assertFalse(observed["late_open_can_attest_prior_history"])

    def test_10_same_connection_commit_does_not_change_data_version(self):
        self.assertTrue(self.self_change["valid"])
        self.assertEqual(self.self_change["values"], [1, 9])
        self.assertFalse(self.self_change[
            "same_connection_change_detected_by_data_version"
        ])
        self.assertEqual(
            self.self_change["after_same_connection_write"]["decision"],
            "UNCHANGED_LOCAL_HINT_NOT_AUTHORITY",
        )

    def test_11_none_as_connection_is_denied_not_broken(self):
        watch = LocalDataVersionWatch(None)
        observed = watch.check()
        self.assertTrue(observed["local_change_seen"])
        self.assertEqual(observed["decision"],
                         "DENY_LOCAL_EXTERNAL_CHANGE_OR_UNAVAILABLE")

    def test_12_hostile_object_is_not_inspected(self):
        class Hostile:
            def __getattribute__(self, name):
                raise AssertionError("HOSTILE_CALLBACK_WAS_CALLED")
        watch = LocalDataVersionWatch(Hostile())
        self.assertEqual(watch.check()["decision"],
                         "DENY_LOCAL_EXTERNAL_CHANGE_OR_UNAVAILABLE")

    def test_13_closing_native_handle_latches_unavailable(self):
        with TemporaryDirectory(prefix="a285-close-") as raw:
            db = sqlite3.connect(str(Path(raw) / "test.db"))
            watch = LocalDataVersionWatch(db)
            self.assertEqual(watch.check()["decision"],
                             "UNCHANGED_LOCAL_HINT_NOT_AUTHORITY")
            db.close()
            self.assertEqual(watch.check()["decision"],
                             "DENY_LOCAL_EXTERNAL_CHANGE_OR_UNAVAILABLE")

    def test_14_unrelated_sqlite_connection_counter_not_global_epoch(self):
        with TemporaryDirectory(prefix="a285-counters-") as raw:
            path = Path(raw) / "test.db"
            with closing(sqlite3.connect(str(path))) as a:
                a.execute("CREATE TABLE state (id INTEGER)")
                a.commit()
                with closing(sqlite3.connect(str(path))) as b:
                    left, right = LocalDataVersionWatch(a), LocalDataVersionWatch(b)
                    self.assertFalse(left.check()["is_independent_witness"])
                    self.assertFalse(right.check()["is_independent_witness"])
                    self.assertFalse(left.check()["can_authorize_send"])
                    self.assertFalse(right.check()["can_authorize_send"])

    def test_15_invalid_mode_never_creates_a_prod_effect(self):
        for mode in (None, True, "wal", "TRUNCATE", "OFF"):
            with self.subTest(mode=mode):
                outcome = probe_live_semantic_reversion(journal_mode=mode)
                self.assertFalse(outcome["valid"])
                self.assertEqual(outcome["error"], "UNSUPPORTED_JOURNAL_MODE")
                self.assertFalse(outcome["authorizes_send"])

    def test_16_disposable_sql_update_not_raw_byte_restore(self):
        for observed in (self.delete_mode, self.wal_mode):
            self.assertTrue(observed["semantic_reversion_not_byte_level_rollback"])
            self.assertFalse(observed["physical_power_loss_simulated"])

    def test_17_p0_5_and_p0_6_are_never_claimed_homologated(self):
        for observed in (self.delete_mode, self.wal_mode, self.self_change):
            self.assertEqual(observed["schema"], SCHEMA)
            self.assertFalse(observed["same_inode_native_fd_authenticated"])
            self.assertFalse(observed["antirollback_witness_authenticated"])
            self.assertEqual(observed["p0_homologated"], 0)

    def test_18_local_counter_cannot_prove_owner_or_provider_identity(self):
        for observed in (self.delete_mode, self.wal_mode, self.self_change):
            self.assertFalse(observed["external_ownership_verified"])
            self.assertFalse(observed["external_effect_confirmed"])

    def test_19_observer_always_exposes_no_authority(self):
        for observed in (self.delete_mode, self.wal_mode):
            for name in ("first_check", "after_external_update",
                         "after_semantic_reversion", "late_open_check"):
                item = observed[name]
                self.assertFalse(item["is_independent_witness"])
                self.assertFalse(item["can_authorize_read_as_trusted"])
                self.assertFalse(item["can_authorize_send"])
                self.assertFalse(item["p0_5_homologated"])
                self.assertFalse(item["p0_6_homologated"])

    def test_20_no_worker_order_alert_provider_or_auto_retry(self):
        for observed in (self.delete_mode, self.wal_mode, self.self_change):
            self.assertTrue(observed["no_new_data_calls"])
            self.assertTrue(observed["no_orders"])
            self.assertTrue(observed["no_alerts"])
            self.assertTrue(observed["zero_auto_resend"])
            self.assertFalse(observed["authorizes_send"])


if __name__ == "__main__":
    unittest.main()
