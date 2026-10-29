"""A236 — subprocess termination at SQLite restore publication fence.

Real, disposable SQLite on both OSes, no provider, no Worker and NO auto-retry.
Process exit is NOT an electrical power-loss or fsync-directory proof.
"""
from contextlib import closing
import errno
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from aion_chat.store import (
    SQLiteChatStore, StorageUnavailableError, RestorePublicationUncertainError,
)


def _make(path, value=31):
    with closing(sqlite3.connect(str(path))) as db:
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("CREATE TABLE record (id INTEGER PRIMARY KEY, value INTEGER)")
        db.execute("INSERT INTO record VALUES (1, ?)", (value,))
        db.commit()


def _value(path):
    with closing(sqlite3.connect(str(path))) as db:
        return db.execute("SELECT value FROM record WHERE id=1").fetchone()[0]


def _marker(target):
    return Path(str(target) + ".aion-restore-pending")


# Child terminates at the exact Python boundary, without calling handlers.
# Exit 71: marker written, pathname NOT published.
# Exit 72: marker written, pathname WAS published, no cleanup/ack.
_CRASH_SCRIPT = r"""
import os, sys
from aion_chat.store import SQLiteChatStore
from aion_chat import store as module
link = module.os.link
phase = sys.argv[3]
def cut(source, destination):
    if phase == 'before':
        os._exit(71)
    link(source, destination)
    if phase == 'after':
        os._exit(72)
module.os.link = cut
SQLiteChatStore.restore_from_backup(sys.argv[1], sys.argv[2])
sys.exit(0)
"""


class A236CrashFenceTests(unittest.TestCase):
    def fixture(self, folder):
        root = Path(folder)
        source, target = root / "backup.db", root / "new.db"
        _make(source)
        return source, target

    def child(self, source, target, phase):
        result = subprocess.run(
            [sys.executable, "-B", "-c", _CRASH_SCRIPT, str(source), str(target), phase],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True, text=True, timeout=20, check=False,
        )
        self.assertEqual(result.stderr, "", result.stderr)
        return result.returncode

    def test_01_normal_publish_clears_local_guard(self):
        with TemporaryDirectory(prefix="a236-") as root:
            source, target = self.fixture(root)
            result = SQLiteChatStore.restore_from_backup(source, target)
            self.assertEqual(result["state"], "RESTORE_VERIFIED")
            self.assertEqual(_value(target), 31)
            self.assertFalse(_marker(target).exists())

    def test_02_kill_before_link_leaves_no_target_and_pending_fence(self):
        with TemporaryDirectory(prefix="a236-") as root:
            source, target = self.fixture(root)
            self.assertEqual(self.child(source, target, "before"), 71)
            self.assertFalse(target.exists())
            self.assertTrue(_marker(target).exists())

    def test_03_kill_after_link_leaves_published_target_and_pending_fence(self):
        with TemporaryDirectory(prefix="a236-") as root:
            source, target = self.fixture(root)
            self.assertEqual(self.child(source, target, "after"), 72)
            self.assertTrue(target.is_file())
            self.assertTrue(_marker(target).exists())
            self.assertEqual(_value(target), 31)

    def test_04_kill_before_publication_blocks_followup_attempt(self):
        with TemporaryDirectory(prefix="a236-") as root:
            source, target = self.fixture(root)
            self.assertEqual(self.child(source, target, "before"), 71)
            with self.assertRaisesRegex(StorageUnavailableError, "destination or SQLite sidecars"):
                SQLiteChatStore.restore_from_backup(source, target)
            self.assertFalse(target.exists())

    def test_05_kill_after_publication_blocks_followup_attempt(self):
        with TemporaryDirectory(prefix="a236-") as root:
            source, target = self.fixture(root)
            self.assertEqual(self.child(source, target, "after"), 72)
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(source, target)
            self.assertEqual(_value(target), 31)

    def test_06_guard_bytes_created_before_process_exits(self):
        with TemporaryDirectory(prefix="a236-") as root:
            source, target = self.fixture(root)
            self.assertEqual(self.child(source, target, "before"), 71)
            guard = _marker(target).read_bytes()
            self.assertIn(b"RESTORE_PENDING", guard)
            self.assertIn(b"NO_AUTO_RETRY", guard)

    def test_07_stale_guard_without_target_is_not_automatically_cleared(self):
        with TemporaryDirectory(prefix="a236-") as root:
            source, target = self.fixture(root)
            _marker(target).write_text("untrusted-text")
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(source, target)
            self.assertFalse(target.exists())
            self.assertEqual(_marker(target).read_text(), "untrusted-text")

    def test_08_guard_only_one_creator_wins_during_race(self):
        with TemporaryDirectory(prefix="a236-") as root:
            source, target = self.fixture(root)
            def no_publish(a, b):
                raise FileExistsError(errno.EEXIST, "synthetic create collision", str(b))
            with mock.patch("aion_chat.store.os.link", side_effect=no_publish):
                with self.assertRaises(StorageUnavailableError):
                    SQLiteChatStore.restore_from_backup(source, target)
            self.assertTrue(_marker(target).exists())
            self.assertFalse(target.exists())
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(source, target)

    def test_09_guard_creation_permission_error_does_not_publish(self):
        with TemporaryDirectory(prefix="a236-") as root:
            source, target = self.fixture(root)
            original = Path.open
            def denied(path, mode="r", *a, **kw):
                if str(path).endswith(".aion-restore-pending") and mode == "xb":
                    raise PermissionError(errno.EACCES, "synthetic guard denied")
                return original(path, mode, *a, **kw)
            with mock.patch("aion_chat.store.Path.open", autospec=True, side_effect=denied):
                with self.assertRaises(StorageUnavailableError):
                    SQLiteChatStore.restore_from_backup(source, target)
            self.assertFalse(target.exists())

    def test_10_fsync_failure_retains_guard_and_refuses_publication(self):
        with TemporaryDirectory(prefix="a236-") as root:
            source, target = self.fixture(root)
            with mock.patch("aion_chat.store.os.fsync",
                            side_effect=OSError(errno.EIO, "synthetic fsync failure")):
                with self.assertRaises(StorageUnavailableError):
                    SQLiteChatStore.restore_from_backup(source, target)
            self.assertFalse(target.exists())
            self.assertTrue(_marker(target).exists())

    def test_11_guard_cleanup_failure_after_link_is_uncertain(self):
        with TemporaryDirectory(prefix="a236-") as root:
            source, target = self.fixture(root)
            real_unlink = Path.unlink
            def fail_guard_unlink(path, *a, **kw):
                if str(path).endswith(".aion-restore-pending"):
                    raise PermissionError(errno.EACCES, "synthetic guard unlink denied")
                return real_unlink(path, *a, **kw)
            with mock.patch("aion_chat.store.Path.unlink", autospec=True,
                            side_effect=fail_guard_unlink):
                with self.assertRaises(RestorePublicationUncertainError) as ctx:
                    SQLiteChatStore.restore_from_backup(source, target)
            self.assertIn("POST_LINK_IO_ZERO_AUTO_RETRY", str(ctx.exception))
            self.assertTrue(target.exists())
            self.assertTrue(_marker(target).exists())

    def test_12_after_guard_cleanup_failure_retry_refused(self):
        with TemporaryDirectory(prefix="a236-") as root:
            source, target = self.fixture(root)
            real_unlink = Path.unlink
            def fail_guard_unlink(path, *a, **kw):
                if str(path).endswith(".aion-restore-pending"):
                    raise PermissionError(errno.EACCES, "synthetic guard unlink denied")
                return real_unlink(path, *a, **kw)
            with mock.patch("aion_chat.store.Path.unlink", autospec=True,
                            side_effect=fail_guard_unlink):
                with self.assertRaises(RestorePublicationUncertainError):
                    SQLiteChatStore.restore_from_backup(source, target)
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(source, target)
            self.assertEqual(_value(target), 31)

    def test_13_sidecar_with_guard_blocks_reentry(self):
        with TemporaryDirectory(prefix="a236-") as root:
            source, target = self.fixture(root)
            _marker(target).write_bytes(b"pending")
            Path(str(target) + "-wal").write_bytes(b"orphan")
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(source, target)
            self.assertFalse(target.exists())
            self.assertEqual(_marker(target).read_bytes(), b"pending")

    def test_14_separate_target_not_fenced_by_another_target_guard(self):
        with TemporaryDirectory(prefix="a236-") as root:
            source, target = self.fixture(root)
            _marker(target).write_bytes(b"pending")
            second = Path(root) / "independent-target.db"
            self.assertEqual(SQLiteChatStore.restore_from_backup(source, second)["state"],
                             "RESTORE_VERIFIED")
            self.assertTrue(_marker(target).exists())
            self.assertFalse(_marker(second).exists())

    def test_15_guard_is_not_an_out_of_host_security_witness(self):
        from labs.a232_six_p0_evidence_crosswalk import P0_DEFINITIONS
        self.assertIn("INDEPENDENT_MONOTONIC_WITNESS", P0_DEFINITIONS["P0-4"][2])
        self.assertIn("ATOMIC_NATIVE_SQLITE_READ_HANDLE", P0_DEFINITIONS["P0-5"][2])
        self.assertIn("POST_COMMIT_OUTCOME_RECONCILIATION", P0_DEFINITIONS["P0-6"][2])


if __name__ == "__main__":
    unittest.main()
