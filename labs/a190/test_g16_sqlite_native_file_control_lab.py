"""A190 G16: same-connection official SQLite file_control, synthetic temp DBs."""
import ctypes
from pathlib import Path
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

import apsw
from labs.a190.g16_sqlite_native_file_control_lab import (
    native_sqlite_has_moved, win32_native_file_identity,
)


class G16SqliteVfsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aion-g16-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.live = self.root / "live.sqlite3"
        self.clone = self.root / "clone.sqlite3"
        with sqlite3.connect(self.live) as db:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("CREATE TABLE synthetic_events(value TEXT)")
            db.execute("CREATE TABLE aion_native_marker_v1(marker TEXT)")
            db.execute("INSERT INTO aion_native_marker_v1 VALUES(?)", ("b" * 32,))
            db.execute("INSERT INTO synthetic_events VALUES('live')")
        shutil.copyfile(self.live, self.clone)
        with sqlite3.connect(self.clone) as db:
            db.execute("INSERT INTO synthetic_events VALUES('clone-only')")

    @staticmethod
    def _scalar(db, query):
        return next(iter(db.execute(query)))[0]

    def test_01_has_moved_runs_on_actually_opened_connection(self):
        connection = apsw.Connection(str(self.live))
        try:
            self.assertEqual(self._scalar(connection, "SELECT count(*) FROM synthetic_events"), 1)
            result = native_sqlite_has_moved(connection)
            self.assertTrue(result.native_connection_tied)
            self.assertFalse(result.homologated)
            if sys.platform == "linux":
                self.assertEqual(result.status, "G16_NATIVE_HANDLE_NOT_MOVED_OBSERVATION_ONLY")
            else:
                self.assertIn(result.status, (
                    "G16_NATIVE_HANDLE_NOT_MOVED_OBSERVATION_ONLY",
                    "G16_NATIVE_HAS_MOVED_UNSUPPORTED_DENY"))
            print("G16_OFFICIAL_HAS_MOVED_UNSWAPPED=" + result.status)
        finally:
            connection.close()

    def test_02_clone_keeps_local_marker_and_differs_in_payload(self):
        with sqlite3.connect(self.live) as one, sqlite3.connect(self.clone) as two:
            left = one.execute("SELECT marker FROM aion_native_marker_v1").fetchone()[0]
            right = two.execute("SELECT marker FROM aion_native_marker_v1").fetchone()[0]
            self.assertEqual(left, right)
            self.assertEqual(one.execute("SELECT count(*) FROM synthetic_events").fetchone()[0], 1)
            self.assertEqual(two.execute("SELECT count(*) FROM synthetic_events").fetchone()[0], 2)
        print("G16_SAME_MARKER_DIFFERENT_BYTES=ADVERSARIAL_SETUP_CONFIRMED")

    @unittest.skipUnless(sys.platform == "linux", "same-path rename ABA exercised on Linux")
    def test_03_native_has_moved_detects_same_marker_transient_swap(self):
        saved = self.root / "saved.sqlite3"
        detached = self.root / "detached.sqlite3"
        self.live.rename(saved)
        shutil.copyfile(self.clone, self.live)
        rogue = None
        try:
            rogue = apsw.Connection(str(self.live))
            self.assertEqual(self._scalar(rogue, "SELECT count(*) FROM synthetic_events"), 2)
            self.assertIn("live.sqlite3", rogue.filename)
            self.live.rename(detached)
            saved.rename(self.live)
            probe = native_sqlite_has_moved(rogue)
            self.assertEqual(probe.status, "G16_NATIVE_HANDLE_MOVED_DENY")
            self.assertFalse(probe.homologated)
            print("G16_NATIVE_VFS_SAME_MARKER_ABA=MOVED_DENIED_ON_LINUX")
        finally:
            if rogue is not None:
                rogue.close()
            if saved.exists() and not self.live.exists():
                saved.rename(self.live)

    @unittest.skipUnless(sys.platform == "linux", "same-path rename ABA exercised on Linux")
    def test_04_preopened_rogue_plus_decoy_does_not_fool_connection_control(self):
        saved = self.root / "original.sqlite3"
        detached = self.root / "detached.sqlite3"
        self.live.rename(saved)
        shutil.copyfile(self.clone, self.live)
        rogue = None
        honest = None
        try:
            rogue = apsw.Connection(str(self.live))
            self.assertEqual(self._scalar(rogue, "SELECT count(*) FROM synthetic_events"), 2)
            self.live.rename(detached)
            saved.rename(self.live)
            honest = apsw.Connection(str(self.live))
            self.assertEqual(self._scalar(honest, "SELECT count(*) FROM synthetic_events"), 1)
            rogue_result = native_sqlite_has_moved(rogue)
            honest_result = native_sqlite_has_moved(honest)
            self.assertEqual(rogue_result.status, "G16_NATIVE_HANDLE_MOVED_DENY")
            self.assertEqual(honest_result.status, "G16_NATIVE_HANDLE_NOT_MOVED_OBSERVATION_ONLY")
            self.assertFalse(rogue_result.homologated)
            self.assertFalse(honest_result.homologated)
            print("G16_PREOPENED_ROGUE_VS_DECOY=NATIVE_CONNECTIONS_DIFFERENTIATED")
        finally:
            if honest is not None:
                honest.close()
            if rogue is not None:
                rogue.close()
            if saved.exists() and not self.live.exists():
                saved.rename(self.live)

    def test_05_windows_native_handle_matches_independent_real_path(self):
        connection = apsw.Connection(str(self.live))
        try:
            self.assertEqual(self._scalar(connection, "SELECT count(*) FROM synthetic_events"), 1)
            native = win32_native_file_identity(connection, self.live)
            self.assertFalse(native.homologated)
            if sys.platform == "win32":
                self.assertEqual(native.status, "G16_WIN32_SAME_CONNECTION_NATIVE_MATCH_LOCAL_ONLY")
                self.assertTrue(native.native_connection_tied)
                print("G16_WIN32_NATIVE_SQLITE_OS_HANDLE=MATCH_LOCAL_ONLY")
            else:
                self.assertEqual(native.status, "G16_WIN32_ONLY_UNSUPPORTED_DENY")
                print("G16_WIN32_NATIVE_HANDLE=OTHER_OS_DENIED")
        finally:
            connection.close()

    def test_06_windows_native_handle_denies_incorrect_target_path(self):
        connection = apsw.Connection(str(self.live))
        try:
            self.assertEqual(self._scalar(connection, "SELECT count(*) FROM synthetic_events"), 1)
            other = win32_native_file_identity(connection, self.clone)
            if sys.platform == "win32":
                self.assertEqual(other.status, "G16_WIN32_SAME_CONNECTION_NATIVE_MISMATCH_DENY")
            else:
                self.assertEqual(other.status, "G16_WIN32_ONLY_UNSUPPORTED_DENY")
            self.assertFalse(other.homologated)
            print("G16_WINDOWS_WRONG_ANCHOR_PATH=MISMATCH_OR_NON_WINDOWS_DENY")
        finally:
            connection.close()

    def test_07_fake_host_file_control_cannot_be_external_trust(self):
        class Missing:
            def file_control(self, name, op, pointer):
                return False

        class HostFabricated:
            def file_control(self, name, op, pointer):
                ctypes.c_int.from_address(pointer).value = 0
                return True

        missing = native_sqlite_has_moved(Missing())
        self.assertEqual(missing.status, "G16_NATIVE_HAS_MOVED_UNSUPPORTED_DENY")
        fabricated = native_sqlite_has_moved(HostFabricated())
        self.assertEqual(fabricated.status, "G16_NATIVE_HANDLE_NOT_MOVED_OBSERVATION_ONLY")
        self.assertFalse(fabricated.homologated)
        self.assertFalse(missing.homologated)
        print("G16_CALLER_CONTROLLED_FAKE_MAY_REPORT_SAFE=NOT_EXTERNAL_TRUST_RED")

    def test_08_wal_scenario_still_not_receipt_or_rollback_proof(self):
        connection = apsw.Connection(str(self.live))
        try:
            self.assertEqual(self._scalar(connection, "PRAGMA journal_mode=WAL").lower(), "wal")
            connection.execute("INSERT INTO synthetic_events VALUES('wal')")
            self.assertEqual(self._scalar(connection, "SELECT count(*) FROM synthetic_events"), 2)
            observed = native_sqlite_has_moved(connection)
            self.assertFalse(observed.homologated)
            if sys.platform == "linux":
                self.assertEqual(observed.status, "G16_NATIVE_HANDLE_NOT_MOVED_OBSERVATION_ONLY")
            win_observed = win32_native_file_identity(connection, self.live)
            self.assertFalse(win_observed.homologated)
            if sys.platform == "win32":
                self.assertEqual(win_observed.status, "G16_WIN32_SAME_CONNECTION_NATIVE_MATCH_LOCAL_ONLY")
            print("G16_WAL_NATIVE_MAIN_OBSERVATION=SIDE_CAR_AND_ROLLBACK_UNPROVEN")
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
