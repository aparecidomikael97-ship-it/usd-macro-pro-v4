"""A249 LAB — detect visible advisory lockfile replacement, never certify host trust.

These tests operate on disposable local files and SQLite. A lockfile can still
be removed or rolled back by a hostile host, and detection after a COMMIT is
too late to prove exclusion of a concurrent independent lock owner.
"""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from aion_chat.models import Message, Scope
from aion_chat.store import (
    FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError,
    MessageLifecycleLockIdentityError, _cross_process_message_lifecycle_lock,
)


SCOPE = Scope("owner-a249", "tenant-a249", "workspace-a249")


def lock_path_of(path):
    return Path(str(path) + ".aion-message-lifecycle.lock")


class A249LockPathIdentityTests(unittest.TestCase):
    def test_01_normal_lock_and_sqlite_message_still_work(self):
        with TemporaryDirectory(prefix="a249-normal-") as raw:
            path = Path(raw) / "chat.db"
            with _cross_process_message_lifecycle_lock(path):
                self.assertTrue(lock_path_of(path).is_file())
            store = SQLiteChatStore(path)
            try:
                c = store.create_conversation(SCOPE, "normal")
                row = store.append_message(SCOPE, Message(c.id, "user", "works"))
                self.assertEqual(row.sequence, 1)
                self.assertEqual(store.require_healthy()["state"], HEALTHY)
            finally:
                store.close()

    def test_02_synthetic_identity_mismatch_denied_on_both_platforms(self):
        with TemporaryDirectory(prefix="a249-inode-") as raw:
            path = Path(raw) / "chat.db"
            lock = lock_path_of(path)
            with _cross_process_message_lifecycle_lock(path):
                pass
            real_stat = Path.stat
            observed = 0

            def injected_stat(candidate, *args, **kwargs):
                nonlocal observed
                result = real_stat(candidate, *args, **kwargs)
                if candidate == lock:
                    observed += 1
                    parts = list(result)
                    parts[1] = int(result.st_ino) + 1
                    return os.stat_result(parts)
                return result

            with mock.patch.object(Path, "stat", injected_stat):
                with self.assertRaisesRegex(
                    MessageLifecycleLockIdentityError, "no longer binds",
                ):
                    with _cross_process_message_lifecycle_lock(path):
                        self.fail("SQLite access under mismatched lock identity")
            self.assertGreater(observed, 0)

    def test_03_posix_swap_after_lock_before_yield_denied(self):
        if os.name != "posix":
            self.skipTest("real pathname replacement of open lock tested on POSIX")
        import fcntl
        with TemporaryDirectory(prefix="a249-swap-") as raw:
            root = Path(raw)
            path, replacement = root / "chat.db", root / "replacement.lock"
            with _cross_process_message_lifecycle_lock(path):
                pass
            replacement.write_bytes(b"0")
            actual_flock = fcntl.flock
            swapped = False

            def flock_then_swap(fd, op):
                nonlocal swapped
                result = actual_flock(fd, op)
                if not swapped and op & fcntl.LOCK_EX and op & fcntl.LOCK_NB:
                    os.replace(replacement, lock_path_of(path))
                    swapped = True
                return result

            with mock.patch.object(fcntl, "flock", flock_then_swap):
                with self.assertRaises(MessageLifecycleLockIdentityError):
                    with _cross_process_message_lifecycle_lock(path):
                        self.fail("the swapped lock path was not rejected")
            self.assertTrue(swapped)

    def test_04_posix_deleted_lock_after_yield_denied(self):
        if os.name != "posix":
            self.skipTest("unlink open advisory lock tested on POSIX")
        with TemporaryDirectory(prefix="a249-delete-") as raw:
            path = Path(raw) / "chat.db"
            with self.assertRaises(MessageLifecycleLockIdentityError):
                with _cross_process_message_lifecycle_lock(path):
                    lock_path_of(path).unlink()

    def test_05_post_commit_tamper_marks_connection_failed(self):
        if os.name != "posix":
            self.skipTest("real unlink of locked file requires POSIX")
        with TemporaryDirectory(prefix="a249-postcommit-") as raw:
            path = Path(raw) / "chat.db"
            store = SQLiteChatStore(path)
            c = store.create_conversation(SCOPE, "committed")
            normal_cleanup = store._clear_message_commit_marker

            def cleanup_and_unlink_lock():
                normal_cleanup()  # a successful COMMIT already happened
                lock_path_of(path).unlink()

            store._clear_message_commit_marker = cleanup_and_unlink_lock
            try:
                with self.assertRaisesRegex(
                    StorageUnavailableError, "lock uncertain",
                ):
                    store.append_message(
                        SCOPE, Message(c.id, "user", "persisted", id="a249-real-commit")
                    )
                self.assertEqual(store._health_state, FAILED)
                with self.assertRaises(StorageUnavailableError):
                    store.append_message(
                        SCOPE, Message(c.id, "user", "must not retry")
                    )
                with closing(sqlite3.connect(str(path))) as db:
                    persisted = db.execute(
                        "SELECT COUNT(*) FROM messages WHERE id='a249-real-commit'"
                    ).fetchone()[0]
                self.assertEqual(persisted, 1)
            finally:
                store.close()

    def test_06_before_entry_swapped_lock_denies_sqlite_startup(self):
        with TemporaryDirectory(prefix="a249-startup-") as raw:
            path = Path(raw) / "chat.db"
            lock = lock_path_of(path)
            real_stat = Path.stat

            def forged_stat(candidate, *args, **kwargs):
                result = real_stat(candidate, *args, **kwargs)
                if candidate == lock:
                    fields = list(result)
                    fields[1] = int(result.st_ino) + 5
                    return os.stat_result(fields)
                return result

            with mock.patch.object(Path, "stat", forged_stat):
                with self.assertRaises(StorageUnavailableError):
                    SQLiteChatStore(path)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
