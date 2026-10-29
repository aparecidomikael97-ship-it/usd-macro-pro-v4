"""A247 LAB: local pre-COMMIT fence and restart veto, NOT external custody."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from aion_chat.models import Message, Scope
from aion_chat.store import (
    HEALTHY, SQLiteChatStore, StorageUnavailableError,
    StoreCommitOutcomeUncertainError,
)
from labs.test_a246_chat_commit_uncertainty import LostAckConnection


SCOPE = Scope("owner-a247", "tenant-a247", "workspace-a247")


def marker_for(path):
    return Path(str(path) + ".aion-message-commit-pending")


def count_messages(path):
    with closing(sqlite3.connect(str(path))) as db:
        return db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]


class A247DurableLocalVetoTests(unittest.TestCase):
    def test_01_normal_commit_clears_local_marker(self):
        with TemporaryDirectory(prefix="a247-normal-") as raw:
            path = Path(raw) / "chat.db"
            store = SQLiteChatStore(path)
            try:
                c = store.create_conversation(SCOPE, "normal")
                self.assertFalse(marker_for(path).exists())
                row = store.append_message(SCOPE, Message(c.id, "user", "OK"))
                self.assertEqual(row.sequence, 1)
                self.assertFalse(marker_for(path).exists())
                self.assertEqual(store.require_healthy()["state"], HEALTHY)
            finally:
                store.close()
            again = SQLiteChatStore(path)
            again.close()
            self.assertEqual(count_messages(path), 1)

    def test_02_commit_ack_lost_blocks_reopen_and_preserves_row(self):
        with TemporaryDirectory(prefix="a247-ack-") as raw:
            path = Path(raw) / "chat.db"
            store = SQLiteChatStore(path)
            c = store.create_conversation(SCOPE, "lost ack")
            store.db = LostAckConnection(store.db, after_commit=True)
            try:
                with self.assertRaises(StoreCommitOutcomeUncertainError):
                    store.append_message(SCOPE, Message(c.id, "user", "committed"))
                self.assertTrue(marker_for(path).is_file())
            finally:
                store.close()
            self.assertEqual(count_messages(path), 1)
            with mock.patch("aion_chat.store.sqlite3.connect") as fake_connect:
                with self.assertRaisesRegex(StorageUnavailableError, "COMMIT outcome pending"):
                    SQLiteChatStore(path)
                fake_connect.assert_not_called()

    def test_03_before_commit_error_preserves_veto_even_if_no_row(self):
        with TemporaryDirectory(prefix="a247-before-") as raw:
            path = Path(raw) / "chat.db"
            store = SQLiteChatStore(path)
            c = store.create_conversation(SCOPE, "no commit")
            store.db = LostAckConnection(store.db, after_commit=False)
            try:
                with self.assertRaises(StoreCommitOutcomeUncertainError):
                    store.append_message(SCOPE, Message(c.id, "user", "not committed"))
            finally:
                store.close()
            self.assertTrue(marker_for(path).exists())
            self.assertEqual(count_messages(path), 0)
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore(path)

    def test_04_existing_marker_refuses_new_database_and_symlink(self):
        with TemporaryDirectory(prefix="a247-veto-") as raw:
            path = Path(raw) / "not-created.db"
            marker_for(path).write_text("untrusted marker; veto only", encoding="utf8")
            with mock.patch("aion_chat.store.sqlite3.connect") as fake_connect:
                with self.assertRaises(StorageUnavailableError):
                    SQLiteChatStore(path)
                fake_connect.assert_not_called()
            self.assertFalse(path.exists())

    def test_05_marker_appearing_later_blocks_open_handle(self):
        with TemporaryDirectory(prefix="a247-later-") as raw:
            path = Path(raw) / "chat.db"
            store = SQLiteChatStore(path)
            try:
                c = store.create_conversation(SCOPE, "later")
                marker_for(path).write_text("untrusted synthetic veto", encoding="utf8")
                self.assertEqual(store.storage_health(deep=True)["state"], "failed")
                with self.assertRaises(StorageUnavailableError):
                    store.get_conversation(SCOPE, c.id)
                with self.assertRaises(StorageUnavailableError):
                    store.append_message(SCOPE, Message(c.id, "user", "must not write"))
            finally:
                store.close()

    def test_06_cleanup_failure_keeps_veto_after_real_commit(self):
        with TemporaryDirectory(prefix="a247-unlink-") as raw:
            path = Path(raw) / "chat.db"
            store = SQLiteChatStore(path)
            c = store.create_conversation(SCOPE, "unlink fails")
            original_unlink = Path.unlink

            def deny_unlink(candidate, *args, **kwargs):
                if candidate == marker_for(path):
                    raise OSError("synthetic marker unlink denied")
                return original_unlink(candidate, *args, **kwargs)

            try:
                with mock.patch.object(Path, "unlink", deny_unlink):
                    with self.assertRaises(StoreCommitOutcomeUncertainError):
                        store.append_message(SCOPE, Message(c.id, "user", "confirmed"))
                self.assertEqual(store._health_state, "failed")
                self.assertTrue(marker_for(path).exists())
            finally:
                store.close()
            self.assertEqual(count_messages(path), 1)
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore(path)

    def test_07_real_subprocess_exits_after_commit_before_marker_clear(self):
        with TemporaryDirectory(prefix="a247-crash-") as raw:
            path = Path(raw) / "chat.db"
            script = """
import os, sys
from pathlib import Path
from aion_chat.models import Message, Scope
from aion_chat.store import SQLiteChatStore
path=Path(sys.argv[1])
store=SQLiteChatStore(path)
scope=Scope("owner-a247", "tenant-a247", "workspace-a247")
c=store.create_conversation(scope,"synthetic crash")
def terminate_after_commit():
    os._exit(77)
store._clear_message_commit_marker=terminate_after_commit
store.append_message(scope,Message(c.id,"user","committed before crash"))
os._exit(91)
"""
            proc = subprocess.run(
                [sys.executable, "-c", script, str(path)],
                capture_output=True, text=True, timeout=20,
            )
            self.assertEqual(proc.returncode, 77, (proc.stdout, proc.stderr))
            self.assertTrue(marker_for(path).is_file())
            self.assertEqual(count_messages(path), 1)
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore(path)

    @unittest.expectedFailure
    def test_08_red_host_deleted_marker_cannot_be_trusted_again(self):
        """Local marker can be removed by host; external witness remains absent."""
        with TemporaryDirectory(prefix="a247-red-") as raw:
            path = Path(raw) / "chat.db"
            store = SQLiteChatStore(path)
            c = store.create_conversation(SCOPE, "host tamper")
            store.db = LostAckConnection(store.db, after_commit=True)
            try:
                with self.assertRaises(StoreCommitOutcomeUncertainError):
                    store.append_message(SCOPE, Message(c.id, "user", "committed"))
            finally:
                store.close()
            self.assertTrue(marker_for(path).is_file())
            marker_for(path).unlink()  # malicious host deletes local veto
            # Desired behavior: still refuse without external monotonic proof.
            with self.assertRaises(StorageUnavailableError):
                reopened = SQLiteChatStore(path)
                reopened.close()


if __name__ == "__main__":
    unittest.main()
