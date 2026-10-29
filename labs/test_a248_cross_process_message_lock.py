"""A248 LAB: SQLite message lifecycle advisory file lock across processes.

Only disposable SQLite, subprocesses and local files. No provider/Worker/egress.
"""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest import mock

from aion_chat.models import Message, Scope
from aion_chat.store import (
    HEALTHY, SQLiteChatStore, StorageUnavailableError,
    _cross_process_message_lifecycle_lock,
)

SCOPE = Scope("owner-a248", "tenant-a248", "workspace-a248")
LOCK_SUFFIX = ".aion-message-lifecycle.lock"


def _python_worker(source):
    return [sys.executable, "-B", "-c", source]


class A248CrossProcessSQLiteLockTests(unittest.TestCase):
    def test_01_normal_store_and_message_commit_reuse_lock(self):
        with TemporaryDirectory(prefix="a248-normal-") as raw:
            path = Path(raw) / "chat.db"
            store = SQLiteChatStore(path)
            try:
                c = store.create_conversation(SCOPE, "normal")
                self.assertEqual(store.require_healthy()["state"], HEALTHY)
                row = store.append_message(
                    SCOPE, Message(c.id, "user", "normal", id="a248-normal")
                )
                self.assertEqual(row.sequence, 1)
                self.assertTrue(Path(str(path) + LOCK_SUFFIX).is_file())
            finally:
                store.close()
            again = SQLiteChatStore(path)
            try:
                self.assertEqual(again.get_conversation(SCOPE, c.id).message_count, 1)
            finally:
                again.close()

    def test_02_real_three_processes_commit_24_messages_in_order(self):
        with TemporaryDirectory(prefix="a248-procs-") as raw:
            path = Path(raw) / "chat.db"
            seed = SQLiteChatStore(path)
            try:
                c = seed.create_conversation(SCOPE, "multi-process")
            finally:
                seed.close()
            script = """
import sys
from pathlib import Path
from aion_chat.models import Scope, Message
from aion_chat.store import SQLiteChatStore
path, cid, worker = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
scope = Scope("owner-a248","tenant-a248","workspace-a248")
store = SQLiteChatStore(path)
try:
    for i in range(8):
        store.append_message(scope, Message(cid,"user",f"worker-{worker}-{i}",
                                           id=f"a248-{worker}-{i}"))
finally:
    store.close()
print("COMPLETED", flush=True)
"""
            processes = [
                subprocess.Popen(
                    _python_worker(script) + [str(path), c.id, str(i)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                for i in range(3)
            ]
            try:
                for worker in processes:
                    out, err = worker.communicate(timeout=35)
                    self.assertEqual(worker.returncode, 0, (out, err))
                    self.assertIn("COMPLETED", out)
            finally:
                for worker in processes:
                    if worker.poll() is None:
                        worker.kill()
                        worker.communicate(timeout=5)
            check = SQLiteChatStore(path)
            try:
                page = check.list_messages(SCOPE, c.id, page_size=100).items
                self.assertEqual(len(page), 24)
                self.assertEqual(len({m.id for m in page}), 24)
                self.assertEqual([m.sequence for m in page], list(range(1, 25)))
                self.assertEqual(check.get_conversation(SCOPE, c.id).message_count, 24)
            finally:
                check.close()

    def _holder(self, path, duration=0.7):
        script = """
import sys, time
from aion_chat.store import _cross_process_message_lifecycle_lock
from pathlib import Path
with _cross_process_message_lifecycle_lock(Path(sys.argv[1])):
    print("READY", flush=True)
    time.sleep(float(sys.argv[2]))
"""
        child = subprocess.Popen(
            _python_worker(script) + [str(path), str(duration)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            bufsize=1,
        )
        self.assertEqual(child.stdout.readline().strip(), "READY")
        return child

    def test_03_other_process_lock_is_waited_for_without_false_veto(self):
        with TemporaryDirectory(prefix="a248-wait-") as raw:
            path = Path(raw) / "chat.db"
            child = self._holder(path, 0.6)
            try:
                started = time.monotonic()
                store = SQLiteChatStore(path)
                elapsed = time.monotonic() - started
                try:
                    self.assertEqual(store.require_healthy()["state"], HEALTHY)
                finally:
                    store.close()
                self.assertGreater(elapsed, 0.05)
                child.communicate(timeout=5)
                self.assertEqual(child.returncode, 0)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.communicate(timeout=5)

    def test_04_lock_timeout_denies_before_new_db_or_message(self):
        with TemporaryDirectory(prefix="a248-timeout-") as raw:
            path = Path(raw) / "chat.db"
            child = self._holder(path, 1.5)
            real_guard = _cross_process_message_lifecycle_lock
            try:
                # Short timeout only in this parent; child has the real kernel
                # lock. No mocked claim that a witness has been authenticated.
                with mock.patch(
                    "aion_chat.store._cross_process_message_lifecycle_lock",
                    side_effect=lambda database: real_guard(database, wait_seconds=0.1),
                ):
                    with self.assertRaisesRegex(
                        StorageUnavailableError, "lifecycle lock unavailable"
                    ):
                        SQLiteChatStore(path)
                self.assertFalse(path.exists())
            finally:
                child.communicate(timeout=5)
                if child.poll() is None:
                    child.kill()
                    child.communicate(timeout=5)

    def test_05_local_pending_marker_still_denies_after_lock_release(self):
        with TemporaryDirectory(prefix="a248-marker-") as raw:
            path = Path(raw) / "chat.db"
            marker = Path(str(path) + ".aion-message-commit-pending")
            with _cross_process_message_lifecycle_lock(path):
                marker.write_text("synthetic uncertainty", encoding="utf8")
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore(path)
            self.assertFalse(path.exists())

    def test_06_lock_path_symlink_refused_when_no_follow_supported(self):
        if not getattr(os, "O_NOFOLLOW", None):
            self.skipTest("O_NOFOLLOW not available on this host")
        with TemporaryDirectory(prefix="a248-link-") as raw:
            path = Path(raw) / "chat.db"
            lock = Path(str(path) + LOCK_SUFFIX)
            target = Path(raw) / "target.txt"
            target.write_text("DO NOT TOUCH", encoding="utf8")
            try:
                lock.symlink_to(target)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(str(exc))
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore(path)
            self.assertEqual(target.read_text(encoding="utf8"), "DO NOT TOUCH")
            self.assertFalse(path.exists())

    @unittest.expectedFailure
    def test_07_red_host_unlink_of_locked_inode_breaks_single_authority(self):
        """Host-controlled lock path can be replaced on POSIX; P0 remains."""
        if os.name == "nt":
            self.skipTest("Windows does not support unlink of this locked file")
        with TemporaryDirectory(prefix="a248-red-") as raw:
            path = Path(raw) / "chat.db"
            lock = Path(str(path) + LOCK_SUFFIX)
            with _cross_process_message_lifecycle_lock(path):
                lock.unlink()  # hostile host detaches the locked inode
                # Desired: new lock pathname must NOT create a second owner.
                # Actual: new inode accepts a second advisory lock.
                with self.assertRaises((OSError, TimeoutError)):
                    with _cross_process_message_lifecycle_lock(
                        path, wait_seconds=0.1
                    ):
                        pass


if __name__ == "__main__":
    unittest.main()
