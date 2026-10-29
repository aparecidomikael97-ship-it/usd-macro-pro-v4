"""A237: native SQLite staging directory-fsync boundaries and crash windows.

Tests request OS file/directory sync and kill subprocesses at barriers, but do
not claim a physical power-failure experiment or independent storage custody.
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
    _sync_staging_restore_directory,
)


def _source(path):
    with closing(sqlite3.connect(str(path))) as db:
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("CREATE TABLE state (id INTEGER PRIMARY KEY, value INTEGER)")
        db.execute("INSERT INTO state VALUES (1, 29)")
        db.commit()


def _read(path):
    with closing(sqlite3.connect(str(path))) as db:
        return db.execute("SELECT value FROM state WHERE id=1").fetchone()[0]


def _marker(target):
    return Path(str(target) + ".aion-restore-pending")


_CHILD = r"""
import os, sys
from aion_chat import store as module
phase = sys.argv[3]
original = module._sync_staging_restore_directory
counter = [0]
def barrier(directory):
    result = original(directory)
    counter[0] += 1
    if phase == 'before' and counter[0] == 1: os._exit(73)
    if phase == 'after' and counter[0] == 2: os._exit(74)
    if phase == 'clean' and counter[0] == 3: os._exit(75)
    return result
module._sync_staging_restore_directory = barrier
module.SQLiteChatStore.restore_from_backup(sys.argv[1], sys.argv[2])
sys.exit(0)
"""


class A237NativeDirectorySyncTests(unittest.TestCase):
    def fixture(self, root):
        base = Path(root)
        src, target = base / "backup.db", base / "restored.db"
        _source(src)
        return src, target

    def child(self, source, target, phase):
        proc = subprocess.run(
            [sys.executable, "-B", "-c", _CHILD, str(source), str(target), phase],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True, text=True, check=False, timeout=20,
        )
        self.assertFalse(proc.stderr, proc.stderr)
        return proc.returncode

    def test_01_successful_native_restore_not_powerloss_certified(self):
        with TemporaryDirectory(prefix="a237-") as raw:
            src, target = self.fixture(raw)
            outcome = SQLiteChatStore.restore_from_backup(src, target)
            self.assertEqual(outcome["state"], "RESTORE_VERIFIED")
            self.assertFalse(outcome["power_loss_durability_verified"])
            self.assertEqual(_read(target), 29)

    def test_02_dirsync_support_is_platform_capability_not_certification(self):
        with TemporaryDirectory(prefix="a237-") as raw:
            src, target = self.fixture(raw)
            result = SQLiteChatStore.restore_from_backup(src, target)
            self.assertIs(result["directory_sync_requested"],
                          os.name == "posix" and hasattr(os, "O_DIRECTORY"))
            self.assertFalse(result["power_loss_durability_verified"])

    def test_03_three_directory_barriers_called_on_success(self):
        with TemporaryDirectory(prefix="a237-") as raw:
            src, target = self.fixture(raw)
            with mock.patch("aion_chat.store._sync_staging_restore_directory",
                            wraps=_sync_staging_restore_directory) as sync:
                result = SQLiteChatStore.restore_from_backup(src, target)
            self.assertEqual(sync.call_count, 3)
            self.assertEqual(result["state"], "RESTORE_VERIFIED")

    def test_04_native_posix_directory_fsync_returns_boolean(self):
        with TemporaryDirectory(prefix="a237-") as raw:
            supported = _sync_staging_restore_directory(Path(raw))
            self.assertIs(type(supported), bool)
            self.assertEqual(supported, os.name == "posix" and hasattr(os, "O_DIRECTORY"))

    def test_05_before_publish_barrier_error_keeps_marker_no_target(self):
        with TemporaryDirectory(prefix="a237-") as raw:
            src, target = self.fixture(raw)
            with mock.patch("aion_chat.store._sync_staging_restore_directory",
                            side_effect=OSError(errno.EIO, "synthetic pre-publish barrier failure")):
                with self.assertRaises(StorageUnavailableError) as ctx:
                    SQLiteChatStore.restore_from_backup(src, target)
            self.assertNotIsInstance(ctx.exception, RestorePublicationUncertainError)
            self.assertFalse(target.exists())
            self.assertTrue(_marker(target).exists())

    def test_06_after_link_barrier_error_is_uncertain(self):
        with TemporaryDirectory(prefix="a237-") as raw:
            src, target = self.fixture(raw)
            with mock.patch("aion_chat.store._sync_staging_restore_directory",
                            side_effect=[True, OSError(errno.EIO, "synthetic post-link barrier")]):
                with self.assertRaises(RestorePublicationUncertainError):
                    SQLiteChatStore.restore_from_backup(src, target)
            self.assertTrue(target.exists())
            self.assertTrue(_marker(target).exists())
            self.assertEqual(_read(target), 29)

    def test_07_after_marker_removal_barrier_error_is_uncertain(self):
        with TemporaryDirectory(prefix="a237-") as raw:
            src, target = self.fixture(raw)
            with mock.patch("aion_chat.store._sync_staging_restore_directory",
                            side_effect=[True, True, OSError(errno.EIO, "synthetic final barrier")]):
                with self.assertRaises(RestorePublicationUncertainError):
                    SQLiteChatStore.restore_from_backup(src, target)
            self.assertTrue(target.exists())
            self.assertFalse(_marker(target).exists())
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(src, target)

    def test_08_child_exit_after_first_barrier_leaves_marker_only(self):
        with TemporaryDirectory(prefix="a237-") as raw:
            src, target = self.fixture(raw)
            self.assertEqual(self.child(src, target, "before"), 73)
            self.assertFalse(target.exists())
            self.assertTrue(_marker(target).exists())

    def test_09_child_exit_after_second_barrier_leaves_both(self):
        with TemporaryDirectory(prefix="a237-") as raw:
            src, target = self.fixture(raw)
            self.assertEqual(self.child(src, target, "after"), 74)
            self.assertTrue(target.exists())
            self.assertTrue(_marker(target).exists())
            self.assertEqual(_read(target), 29)

    def test_10_child_exit_after_final_barrier_leaves_target(self):
        with TemporaryDirectory(prefix="a237-") as raw:
            src, target = self.fixture(raw)
            self.assertEqual(self.child(src, target, "clean"), 75)
            self.assertTrue(target.exists())
            self.assertFalse(_marker(target).exists())
            self.assertEqual(_read(target), 29)

    def test_11_crash_before_barrier_cannot_trigger_automatic_retry(self):
        with TemporaryDirectory(prefix="a237-") as raw:
            src, target = self.fixture(raw)
            self.assertEqual(self.child(src, target, "before"), 73)
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(src, target)

    def test_12_crash_after_barrier_cannot_trigger_automatic_retry(self):
        with TemporaryDirectory(prefix="a237-") as raw:
            src, target = self.fixture(raw)
            self.assertEqual(self.child(src, target, "after"), 74)
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(src, target)

    def test_13_fsync_unsupported_not_reported_as_durable(self):
        with TemporaryDirectory(prefix="a237-") as raw:
            src, target = self.fixture(raw)
            with mock.patch("aion_chat.store._sync_staging_restore_directory",
                            return_value=False) as sync:
                result = SQLiteChatStore.restore_from_backup(src, target)
            self.assertEqual(sync.call_count, 3)
            self.assertFalse(result["directory_sync_requested"])
            self.assertFalse(result["power_loss_durability_verified"])

    def test_14_subsequent_restore_still_refuses_existing_target(self):
        with TemporaryDirectory(prefix="a237-") as raw:
            src, target = self.fixture(raw)
            SQLiteChatStore.restore_from_backup(src, target)
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(src, target)
            self.assertEqual(_read(target), 29)

    def test_15_new_barriers_do_not_verify_external_identity_or_vfs(self):
        from labs.a232_six_p0_evidence_crosswalk import P0_DEFINITIONS
        self.assertIn("INDEPENDENT_MONOTONIC_WITNESS", P0_DEFINITIONS["P0-4"][2])
        self.assertIn("ATOMIC_NATIVE_SQLITE_READ_HANDLE", P0_DEFINITIONS["P0-5"][2])
        self.assertIn("POST_COMMIT_OUTCOME_RECONCILIATION", P0_DEFINITIONS["P0-6"][2])


if __name__ == "__main__":
    unittest.main()
