"""A184 LAB synthetic faults: offline snapshot aliases and bounded local reads.

These exercise local denial only. They do not attest a live VFS, an independent
root, custody, production identity, wall-clock bounds or process RSS limits.
"""
from contextlib import closing
from hashlib import sha256
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from aion_chat.pinned_snapshot_a183_lab import PinnedSQLiteSnapshotLab
from aion_chat.store import StorageUnavailableError


class SnapshotLimitsA184Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "artifact.db"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("create table events(value integer)")
            db.executemany("insert into events values(?)", [(i,) for i in range(64)])
            db.execute("create table messages(value text)")
            db.executemany("insert into messages values(?)", [("x" * 80,)] * 8)
        self.digest = sha256(self.path.read_bytes()).hexdigest()

    def snapshot(self, **budgets):
        result = PinnedSQLiteSnapshotLab(
            self.path, expected_sha256=self.digest, **budgets
        )
        self.addCleanup(result.close)
        return result

    def symlink_or_report(self, entry):
        try:
            entry.symlink_to(self.path.parent / "nonexistent-sidecar-target")
        except OSError as exc:
            print("A184_DANGLING_SIDECAR_CAPABILITY_UNAVAILABLE=" + type(exc).__name__)
            return False
        self.assertTrue(entry.is_symlink())
        self.assertFalse(entry.exists())
        return True

    def test_dangling_sidecar_directory_entries_deny_capture(self):
        for suffix in ("-wal", "-shm", "-journal"):
            with self.subTest(suffix=suffix):
                entry = Path(str(self.path) + suffix)
                if not self.symlink_or_report(entry):
                    return
                try:
                    with self.assertRaisesRegex(StorageUnavailableError, "SIDECAR"):
                        self.snapshot()
                finally:
                    entry.unlink()
        print("A184_DANGLING_SIDECAR=CAPTURE_DENIED")

    def test_dangling_sidecar_created_during_read_denies_capture(self):
        # Preflight proves the platform capability before injecting the race.
        entry = Path(str(self.path) + "-journal")
        if not self.symlink_or_report(entry):
            return
        entry.unlink()
        real_read = os.read
        injected = False

        def replace_after_read(fd, size):
            nonlocal injected
            result = real_read(fd, size)
            if not injected:
                injected = True
                entry.symlink_to(self.path.parent / "nonexistent-sidecar-target")
            return result

        with patch("aion_chat.pinned_snapshot_a183_lab.os.read", side_effect=replace_after_read):
            with self.assertRaisesRegex(StorageUnavailableError, "SIDECAR"):
                self.snapshot()

    def test_sidecar_directory_denies_capture(self):
        Path(str(self.path) + "-wal").mkdir()
        with self.assertRaisesRegex(StorageUnavailableError, "SIDECAR"):
            self.snapshot()

    def test_nonpositive_and_noninteger_budgets_deny(self):
        for name in ("max_vm_steps", "max_rows", "max_result_bytes"):
            for value in (0, -1, True, 1.5, "5", None):
                with self.subTest(name=name, value=value):
                    with self.assertRaisesRegex(StorageUnavailableError, "BUDGET"):
                        self.snapshot(**{name: value})

    def test_budgets_cannot_exceed_lab_safety_ceilings(self):
        for name, value in (("max_vm_steps", 1_000_001),
                            ("max_rows", 10_001),
                            ("max_result_bytes", 4 * 1024 * 1024 + 1)):
            with self.subTest(name=name):
                with self.assertRaisesRegex(StorageUnavailableError, "BUDGET"):
                    self.snapshot(**{name: value})

    def test_vm_budget_denies_bounded_synthetic_cross_join(self):
        # Even on the old implementation the complete query is only 64^3 rows.
        snapshot = self.snapshot(max_vm_steps=500)
        with self.assertRaisesRegex(StorageUnavailableError, "VM_STEP_BUDGET"):
            snapshot.rows("select count(*) from events a, events b, events c")
        self.assertEqual(snapshot.rows("select 1"), [(1,)])
        print("A184_VM_STEP_BUDGET=QUERY_DENIED_NO_PARTIAL_RESULT")

    def test_row_budget_denies_instead_of_returning_partial_rows(self):
        snapshot = self.snapshot(max_rows=3)
        with self.assertRaisesRegex(StorageUnavailableError, "ROW_BUDGET"):
            snapshot.rows("select value from events")
        self.assertEqual(snapshot.rows("select value from events limit 3"), [(0,), (1,), (2,)])
        print("A184_ROW_BUDGET=QUERY_DENIED_NO_TRUNCATION")

    def test_result_byte_budget_accounts_for_aggregate_rows(self):
        snapshot = self.snapshot(max_result_bytes=400)
        with self.assertRaisesRegex(StorageUnavailableError, "RESULT_BYTE_BUDGET"):
            snapshot.rows("select value from messages")
        self.assertEqual(snapshot.rows("select value from messages limit 1"), [("x" * 80,)])

    def test_large_single_value_denied_by_sqlite_length_limit(self):
        snapshot = self.snapshot(max_result_bytes=128)
        # Deterministic, bounded concatenation: no large hostile allocation.
        with self.assertRaisesRegex(StorageUnavailableError, "RESULT_BYTE_BUDGET"):
            snapshot.rows("select value || value || value from messages limit 1")
        self.assertEqual(snapshot.rows("select 1"), [(1,)])

    def test_unicode_budget_counts_utf8_bytes(self):
        snapshot = self.snapshot(max_result_bytes=130)
        with self.assertRaisesRegex(StorageUnavailableError, "RESULT_BYTE_BUDGET"):
            snapshot.rows("select ?", ("\U0001f600" * 12,))

    def test_connections_close_on_vm_row_size_and_authorization_errors(self):
        real_connect = sqlite3.connect
        opened = []
        closed = []

        class TrackedConnection(sqlite3.Connection):
            def close(self):
                closed.append(id(self))
                return super().close()

        def connect(*args, **kwargs):
            kwargs["factory"] = TrackedConnection
            db = real_connect(*args, **kwargs)
            opened.append(id(db))
            return db

        with patch("aion_chat.pinned_snapshot_a183_lab.sqlite3.connect", side_effect=connect):
            snapshot = self.snapshot(max_vm_steps=500, max_rows=1, max_result_bytes=200)
            for sql, exception in (
                ("select count(*) from events a, events b, events c", StorageUnavailableError),
                ("select value from events", StorageUnavailableError),
                ("select value || value || value from messages limit 1", StorageUnavailableError),
                ("delete from events", sqlite3.DatabaseError),
            ):
                with self.subTest(sql=sql), self.assertRaises(exception):
                    snapshot.rows(sql)
            self.assertEqual(snapshot.rows("select 1"), [(1,)])
        self.assertCountEqual(opened, closed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
