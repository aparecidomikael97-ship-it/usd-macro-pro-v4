"""A252 LAB: SQLite backup must serialize with cooperating COMMITs.

Real SQLite files and subprocesses; simulated process crash, no real power
loss, no external witness, provider effects, or deployed Worker.
"""
from contextlib import closing
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


SCOPE = Scope("owner-a252", "tenant-a252", "workspace-a252")


def _count(path, table):
    with closing(sqlite3.connect(str(path))) as db:
        return db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]


def _seed(path):
    store = SQLiteChatStore(path)
    c = store.create_conversation(SCOPE, "synthetic backup")
    return store, c


def _child(path, cid, *, crash):
    script = """
import os, sys, time
from pathlib import Path
from aion_chat.models import Message, Scope
from aion_chat.store import SQLiteChatStore
path,cid,crash=Path(sys.argv[1]),sys.argv[2],sys.argv[3]=="1"
db=SQLiteChatStore(path)
normal=db._clear_message_commit_marker
def after_real_commit():
    print("COMMIT_ACK_PENDING", flush=True)
    if crash:
        os._exit(71)
    time.sleep(0.85)
    normal()
db._clear_message_commit_marker=after_real_commit
db.append_message(
    Scope("owner-a252","tenant-a252","workspace-a252"),
    Message(cid,"user","written while backup attempts to start",id="a252-child-message"),
)
db.close()
print("COMMIT_ACK_OK",flush=True)
"""
    return subprocess.Popen(
        [sys.executable, "-B", "-c", script, str(path), cid, "1" if crash else "0"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
    )


class A252CoordinatedSQLiteBackupTests(unittest.TestCase):
    def test_01_normal_backup_creates_verified_distinct_sqlite(self):
        with TemporaryDirectory(prefix="a252-normal-") as raw:
            path, backup = Path(raw) / "live.db", Path(raw) / "backup.db"
            db, c = _seed(path)
            try:
                db.append_message(SCOPE, Message(c.id, "user", "one"))
                result = db.backup_to(backup)
                self.assertEqual(result["state"], "BACKUP_VERIFIED")
                self.assertEqual(db.require_healthy()["state"], HEALTHY)
                self.assertTrue(backup.is_file())
                self.assertEqual(_count(backup, "messages"), 1)
            finally:
                db.close()

    def test_02_cross_process_commit_held_before_ack_is_not_backed_up_midflight(self):
        with TemporaryDirectory(prefix="a252-wait-") as raw:
            path, backup = Path(raw) / "live.db", Path(raw) / "backup.db"
            db, c = _seed(path)
            child = _child(path, c.id, crash=False)
            try:
                ready = child.stdout.readline().strip()
                self.assertEqual(ready, "COMMIT_ACK_PENDING", child.stderr.read() if child.poll() is not None else ready)
                self.assertTrue(Path(str(path) + ".aion-message-commit-pending").is_file())
                started = time.monotonic()
                result = db.backup_to(backup)
                elapsed = time.monotonic() - started
                self.assertGreater(elapsed, 0.3)
                self.assertEqual(result["state"], "BACKUP_VERIFIED")
                out, err = child.communicate(timeout=15)
                self.assertEqual(child.returncode, 0, (out, err))
                self.assertEqual(_count(backup, "messages"), 1)
                self.assertEqual(_count(path, "messages"), 1)
                self.assertFalse(Path(str(path) + ".aion-message-commit-pending").exists())
            finally:
                if child.poll() is None:
                    child.kill()
                    child.communicate(timeout=5)
                db.close()

    def test_03_real_crash_after_commit_releases_lock_but_pending_marker_denies_backup(self):
        with TemporaryDirectory(prefix="a252-crash-") as raw:
            path, backup = Path(raw) / "live.db", Path(raw) / "backup.db"
            db, c = _seed(path)
            child = _child(path, c.id, crash=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), "COMMIT_ACK_PENDING")
                out, err = child.communicate(timeout=15)
                self.assertEqual(child.returncode, 71, (out, err))
                self.assertEqual(_count(path, "messages"), 1)
                with self.assertRaises(StorageUnavailableError):
                    db.backup_to(backup)
                self.assertFalse(backup.exists())
                self.assertTrue(Path(str(path) + ".aion-message-commit-pending").exists())
            finally:
                if child.poll() is None:
                    child.kill()
                    child.communicate(timeout=5)
                db.close()

    def test_04_backup_lock_timeout_denies_without_destination_publication(self):
        with TemporaryDirectory(prefix="a252-busy-") as raw:
            path, backup = Path(raw) / "live.db", Path(raw) / "backup.db"
            db, c = _seed(path)
            holder_code = """
import sys, time
from pathlib import Path
from aion_chat.store import _cross_process_message_lifecycle_lock
with _cross_process_message_lifecycle_lock(Path(sys.argv[1])):
    print("HELD", flush=True)
    time.sleep(1.2)
"""
            holder = subprocess.Popen(
                [sys.executable, "-B", "-c", holder_code, str(path)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            try:
                self.assertEqual(holder.stdout.readline().strip(), "HELD")
                orig = _cross_process_message_lifecycle_lock
                with mock.patch(
                    "aion_chat.store._cross_process_message_lifecycle_lock",
                    side_effect=lambda local_path: orig(local_path, wait_seconds=0.1),
                ):
                    with self.assertRaises(StorageUnavailableError):
                        db.backup_to(backup)
                self.assertFalse(backup.exists())
                out, err = holder.communicate(timeout=8)
                self.assertEqual(holder.returncode, 0, (out, err))
            finally:
                if holder.poll() is None:
                    holder.kill()
                    holder.communicate(timeout=5)
                db.close()

    def test_05_backup_has_explicit_cooperative_guard(self):
        import inspect
        code = inspect.getsource(SQLiteChatStore.backup_to)
        self.assertIn("@_local_commit_gate", code)

    @unittest.expectedFailure
    def test_06_red_uncooperative_sqlite_writer_can_ignore_backup_lock(self):
        """Desired protection is NOT achievable with a local advisory lock."""
        with TemporaryDirectory(prefix="a252-host-red-") as raw:
            path = Path(raw) / "live.db"
            db, c = _seed(path)
            db.close()
            with _cross_process_message_lifecycle_lock(path):
                # A raw SQLite client ignores the advisory companion lock.
                with closing(sqlite3.connect(str(path))) as rogue:
                    with self.assertRaises(sqlite3.OperationalError):
                        rogue.execute("CREATE TABLE uncooperative_writer (id INTEGER)")


if __name__ == "__main__":
    unittest.main()
