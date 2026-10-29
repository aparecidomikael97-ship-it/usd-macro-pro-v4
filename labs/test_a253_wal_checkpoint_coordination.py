"""A253 LAB: explicit WAL checkpoint must respect cooperative COMMIT fences.

Runs real SQLite and local subprocesses only. Does not authenticate SQLite FD,
prove physical fsync/power-loss durability, or prevent a non-cooperating host.
"""
import inspect
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest import mock

from aion_chat.models import Message, Scope
from aion_chat.store import (
    FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError,
    _cross_process_message_lifecycle_lock,
)

SCOPE = Scope("owner-a253", "tenant-a253", "workspace-a253")


def marker(db):
    return Path(str(db) + ".aion-message-commit-pending")


def start_writer(db, conversation_id, *, crash):
    code = """
import os,sys,time
from pathlib import Path
from aion_chat.models import Scope,Message
from aion_chat.store import SQLiteChatStore
db=SQLiteChatStore(Path(sys.argv[1]))
original=db._clear_message_commit_marker
def on_post_commit():
    print("COMMIT_WITHOUT_MARKER_CLEAR",flush=True)
    if sys.argv[3]=="crash":
        os._exit(73)
    time.sleep(.8)
    original()
db._clear_message_commit_marker=on_post_commit
db.append_message(
    Scope("owner-a253","tenant-a253","workspace-a253"),
    Message(sys.argv[2],"user","a253 synthetic real committed write",id="a253-writer"),
)
db.close()
"""
    return subprocess.Popen(
        [sys.executable, "-B", "-c", code, str(db), conversation_id,
         "crash" if crash else "normal"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
    )


class A253WalCheckpointCoordinationTests(unittest.TestCase):
    def test_01_public_passive_full_restart_and_truncate(self):
        with TemporaryDirectory(prefix="a253-modes-") as raw:
            path = Path(raw) / "chat.db"
            store = SQLiteChatStore(path)
            try:
                c = store.create_conversation(SCOPE, "modes")
                store.append_message(SCOPE, Message(c.id, "user", "one"))
                for mode in ("PASSIVE", "FULL", "RESTART", "TRUNCATE"):
                    with self.subTest(mode=mode):
                        report = store.wal_checkpoint(mode.lower())
                        self.assertEqual(report["mode"], mode)
                        self.assertEqual(report["busy"], 0)
                        self.assertGreaterEqual(report["log_frames"], 0)
                self.assertEqual(store.require_healthy()["state"], HEALTHY)
                with self.assertRaises(ValueError):
                    store.wal_checkpoint("FULL); DROP TABLE messages")
                self.assertEqual(store.get_conversation(SCOPE, c.id).message_count, 1)
            finally:
                store.close()

    def test_02_public_checkpoint_waits_for_real_post_commit_marker(self):
        with TemporaryDirectory(prefix="a253-wait-") as raw:
            path = Path(raw) / "chat.db"
            db = SQLiteChatStore(path)
            c = db.create_conversation(SCOPE, "before concurrent write")
            child = start_writer(path, c.id, crash=False)
            try:
                ready = child.stdout.readline().strip()
                self.assertEqual(ready, "COMMIT_WITHOUT_MARKER_CLEAR")
                self.assertTrue(marker(path).exists())
                started = time.monotonic()
                report = db.wal_checkpoint("FULL")
                elapsed = time.monotonic() - started
                self.assertGreater(elapsed, .25)
                self.assertEqual(report["mode"], "FULL")
                self.assertEqual(report["busy"], 0)
                out, err = child.communicate(timeout=15)
                self.assertEqual(child.returncode, 0, (out, err))
                self.assertFalse(marker(path).exists())
                self.assertEqual(db.get_conversation(SCOPE, c.id).message_count, 1)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.communicate(timeout=5)
                db.close()

    def test_03_crash_after_commit_denies_explicit_checkpoint(self):
        with TemporaryDirectory(prefix="a253-crash-") as raw:
            path = Path(raw) / "chat.db"
            db = SQLiteChatStore(path)
            c = db.create_conversation(SCOPE, "after crash")
            child = start_writer(path, c.id, crash=True)
            try:
                self.assertEqual(child.stdout.readline().strip(),
                                 "COMMIT_WITHOUT_MARKER_CLEAR")
                out, err = child.communicate(timeout=15)
                self.assertEqual(child.returncode, 73, (out, err))
                self.assertTrue(marker(path).exists())
                with self.assertRaises(StorageUnavailableError):
                    db.wal_checkpoint("FULL")
                self.assertEqual(db._health_state, FAILED)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.communicate(timeout=5)
                db.close()

    def test_04_external_lifecycle_lock_timeout_is_failclosed(self):
        with TemporaryDirectory(prefix="a253-timeout-") as raw:
            path = Path(raw) / "chat.db"
            db = SQLiteChatStore(path)
            held = """
import sys,time
from pathlib import Path
from aion_chat.store import _cross_process_message_lifecycle_lock
with _cross_process_message_lifecycle_lock(Path(sys.argv[1])):
    print("LOCK_HELD",flush=True)
    time.sleep(1.1)
"""
            proc = subprocess.Popen(
                [sys.executable, "-B", "-c", held, str(path)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
            )
            try:
                self.assertEqual(proc.stdout.readline().strip(), "LOCK_HELD")
                actual = _cross_process_message_lifecycle_lock
                with mock.patch(
                    "aion_chat.store._cross_process_message_lifecycle_lock",
                    side_effect=lambda db_path: actual(db_path, wait_seconds=.1),
                ):
                    with self.assertRaises(StorageUnavailableError):
                        db.wal_checkpoint("TRUNCATE")
                proc.communicate(timeout=10)
                self.assertEqual(proc.returncode, 0)
                # A249's lock-failure handling only marks write methods sticky.
                # This checkpoint was denied; it never entered PRAGMA.
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate(timeout=5)
                db.close()

    def test_05_backup_uses_private_checkpoint_with_one_outer_lock(self):
        with TemporaryDirectory(prefix="a253-backup-") as raw:
            path = Path(raw) / "chat.db"
            backup = Path(raw) / "backup.db"
            db = SQLiteChatStore(path)
            try:
                c = db.create_conversation(SCOPE, "backup")
                db.append_message(SCOPE, Message(c.id, "user", "saved"))
                with mock.patch.object(
                    db, "_wal_checkpoint_under_lifecycle_lock",
                    wraps=db._wal_checkpoint_under_lifecycle_lock,
                ) as checkpoint:
                    result = db.backup_to(backup)
                self.assertEqual(result["state"], "BACKUP_VERIFIED")
                checkpoint.assert_called_once_with("FULL")
                self.assertTrue(backup.is_file())
            finally:
                db.close()

    def test_06_public_checkpoint_and_backup_have_same_outer_lock_contract(self):
        src = inspect.getsource(SQLiteChatStore.wal_checkpoint)
        backup = inspect.getsource(SQLiteChatStore.backup_to)
        self.assertIn("@_local_commit_gate", src)
        self.assertIn("@_local_commit_gate", backup)
        self.assertIn("_wal_checkpoint_under_lifecycle_lock", backup)
        self.assertNotIn("self.wal_checkpoint(", backup)

    @unittest.expectedFailure
    def test_07_red_raw_sqlite_checkpoint_can_bypass_cooperative_lock(self):
        """External SQLite client does not take AION's companion file lock."""
        import sqlite3
        with TemporaryDirectory(prefix="a253-raw-red-") as raw:
            path = Path(raw) / "chat.db"
            db = SQLiteChatStore(path)
            db.close()
            with _cross_process_message_lifecycle_lock(path):
                with sqlite3.connect(str(path)) as rogue:
                    # Desired invariant: checkpoint cannot execute without
                    # independent authority. SQLite permits raw PRAGMA.
                    with self.assertRaises(sqlite3.OperationalError):
                        rogue.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()


if __name__ == "__main__":
    unittest.main()
