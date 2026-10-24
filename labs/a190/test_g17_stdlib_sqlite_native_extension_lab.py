"""A190 G17 — native VFS on the REAL stdlib sqlite3.Connection, LAB ONLY.

Tests explicitly load compiled C extension into synthetic TEMP SQLite databases,
then immediately disable further extension loading. Never execute on customer
data or production, and never auto-load an unsigned/untrusted extension.
"""
from contextlib import closing
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest


EXTENSION = os.environ.get("AION_G17_LAB_EXTENSION", "/tmp/aion_g17_probe.so")
ENTRYPOINT = "sqlite3_aiong17_init"


def load_native_lab_extension(connection):
    """For synthetic test connection only; revoke future loads in finally."""
    connection.enable_load_extension(True)
    try:
        connection.load_extension(EXTENSION, entrypoint=ENTRYPOINT)
    finally:
        connection.enable_load_extension(False)


def moved_on_the_connection(connection):
    return connection.execute("SELECT aion_lab_native_has_moved()").fetchone()[0]


class G17StdlibExactConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aion-g17-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.live = self.root / "live.sqlite3"
        self.clone = self.root / "clone.sqlite3"
        with closing(sqlite3.connect(self.live)) as db, db:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("CREATE TABLE synthetic_events(value TEXT)")
            db.execute("CREATE TABLE aion_native_marker_v1(marker TEXT)")
            db.execute("INSERT INTO aion_native_marker_v1 VALUES(?)", ("c" * 32,))
            db.execute("INSERT INTO synthetic_events VALUES('original')")
        shutil.copyfile(self.live, self.clone)
        with closing(sqlite3.connect(self.clone)) as db, db:
            db.execute("INSERT INTO synthetic_events VALUES('clone-only')")
        if not Path(EXTENSION).is_file():
            self.fail("G17_EXPLICIT_VERIFIED_COMPILED_LAB_EXTENSION_REQUIRED")

    @staticmethod
    def _count(connection):
        return connection.execute("SELECT count(*) FROM synthetic_events").fetchone()[0]

    def test_01_real_stdlib_connection_unchanged_file_returns_zero(self):
        with closing(sqlite3.connect(self.live)) as db:
            load_native_lab_extension(db)
            self.assertEqual(self._count(db), 1)
            self.assertEqual(moved_on_the_connection(db), 0)
        print("G17_PYTHON_STDLIB_REAL_CONNECTION=HAS_MOVED_ZERO_OBSERVATION_ONLY")

    def test_02_loading_revoked_immediately_but_registered_function_works(self):
        with closing(sqlite3.connect(self.live)) as db:
            load_native_lab_extension(db)
            with self.assertRaises(sqlite3.OperationalError):
                db.load_extension(EXTENSION, entrypoint=ENTRYPOINT)
            self.assertEqual(moved_on_the_connection(db), 0)
        print("G17_EXTENSION_LOADING_REVOKED_AFTER_REGISTRATION=OBSERVED")

    def test_03_native_in_memory_database_has_no_physical_handle_and_denies(self):
        with closing(sqlite3.connect(":memory:")) as db:
            load_native_lab_extension(db)
            with self.assertRaisesRegex(sqlite3.OperationalError,
                                        "G17_HAS_MOVED_UNSUPPORTED_DENY"):
                moved_on_the_connection(db)
        print("G17_NO_NATIVE_MAIN_FILE=FAIL_CLOSED")

    def test_04_backup_clone_preserves_marker_but_not_payload(self):
        with closing(sqlite3.connect(self.live)) as one:
            with closing(sqlite3.connect(self.clone)) as two:
                self.assertEqual(
                    one.execute("SELECT marker FROM aion_native_marker_v1").fetchone(),
                    two.execute("SELECT marker FROM aion_native_marker_v1").fetchone())
                self.assertEqual(self._count(one), 1)
                self.assertEqual(self._count(two), 2)
        print("G17_SAME_MARKER_CLONE_DIFFERENT_PAYLOAD=ADVERSARIAL_SETUP")

    @unittest.skipUnless(sys.platform == "linux", "native same-path rename LAB Linux only")
    def test_05_same_marker_path_restored_cloned_stdlib_connection_denies(self):
        saved = self.root / "original.sqlite3"
        detached = self.root / "detached.sqlite3"
        self.live.rename(saved)
        shutil.copyfile(self.clone, self.live)
        wrong = None
        try:
            wrong = sqlite3.connect(self.live)
            load_native_lab_extension(wrong)
            self.assertEqual(self._count(wrong), 2)
            self.assertEqual(moved_on_the_connection(wrong), 0)
            self.live.rename(detached)
            saved.rename(self.live)
            self.assertEqual(moved_on_the_connection(wrong), 1)
            print("G17_STDLIB_NATIVE_SAME_MARKER_ABA=MOVED_DETECTED")
        finally:
            if wrong is not None:
                wrong.close()
            if saved.exists() and not self.live.exists():
                saved.rename(self.live)

    @unittest.skipUnless(sys.platform == "linux", "native same-path rename LAB Linux only")
    def test_06_preopened_rogue_and_decoy_separate_real_sqlite_connections(self):
        saved = self.root / "original.sqlite3"
        detached = self.root / "detached.sqlite3"
        self.live.rename(saved)
        shutil.copyfile(self.clone, self.live)
        wrong = good = None
        try:
            wrong = sqlite3.connect(self.live)
            load_native_lab_extension(wrong)
            self.assertEqual(self._count(wrong), 2)
            self.live.rename(detached)
            saved.rename(self.live)
            good = sqlite3.connect(self.live)
            load_native_lab_extension(good)
            self.assertEqual(self._count(good), 1)
            self.assertEqual(moved_on_the_connection(wrong), 1)
            self.assertEqual(moved_on_the_connection(good), 0)
            print("G17_STDLIB_ROGUE_PREOPENED_PLUS_DECOY=CONNECTIONS_DIFFERENTIATED")
        finally:
            if good is not None:
                good.close()
            if wrong is not None:
                wrong.close()
            if saved.exists() and not self.live.exists():
                saved.rename(self.live)

    def test_07_sql_function_is_direct_only_no_sql_view_execution(self):
        with closing(sqlite3.connect(self.live)) as db:
            load_native_lab_extension(db)
            db.execute("CREATE VIEW synthetic_untrusted_view AS SELECT aion_lab_native_has_moved() AS moved")
            with self.assertRaisesRegex(sqlite3.OperationalError, "unsafe use"):
                db.execute("SELECT * FROM synthetic_untrusted_view").fetchall()
            self.assertEqual(moved_on_the_connection(db), 0)
        print("G17_DIRECTONLY=UNTRUSTED_VIEW_CANNOT_CALL_NATIVE_PROBE")

    def test_08_wal_mutation_does_not_prove_sidecar_or_external_custody(self):
        with closing(sqlite3.connect(self.live)) as db:
            load_native_lab_extension(db)
            self.assertEqual(db.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower(), "wal")
            with db:
                db.execute("INSERT INTO synthetic_events VALUES('wal')")
            self.assertEqual(self._count(db), 2)
            self.assertEqual(moved_on_the_connection(db), 0)
        print("G17_STDLIB_WAL_NATIVE_MAIN=UNMOVED_NOT_SIDE_CAR_PROOF")


if __name__ == "__main__":
    unittest.main()
