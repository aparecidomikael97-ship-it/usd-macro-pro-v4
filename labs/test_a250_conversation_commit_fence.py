"""A250 LAB: protect conversation creation against uncertain SQLite COMMIT.

Real disposable SQLite and real subprocess crash after COMMIT. Lost ACK is
synthetically injected; no external witness, network, Worker or real effect.
"""
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
    FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError,
    StoreCommitOutcomeUncertainError,
)
from labs.test_a246_chat_commit_uncertainty import LostAckConnection

SCOPE = Scope("owner-a250", "tenant-a250", "workspace-a250")


def marker(path):
    return Path(str(path) + ".aion-message-commit-pending")


def count_conversations(path):
    with closing(sqlite3.connect(str(path))) as db:
        return db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]


class A250ConversationCommitFenceTests(unittest.TestCase):
    def test_01_normal_conversation_then_message_keeps_db_healthy(self):
        with TemporaryDirectory(prefix="a250-normal-") as raw:
            path = Path(raw) / "chat.db"
            store = SQLiteChatStore(path)
            try:
                c = store.create_conversation(SCOPE, "normal")
                self.assertFalse(marker(path).exists())
                m = store.append_message(SCOPE, Message(c.id, "user", "hello"))
                self.assertEqual(m.sequence, 1)
                self.assertFalse(marker(path).exists())
                self.assertEqual(store.require_healthy()["state"], HEALTHY)
            finally:
                store.close()
            opened = SQLiteChatStore(path)
            try:
                self.assertEqual(opened.get_conversation(SCOPE, c.id).message_count, 1)
            finally:
                opened.close()

    def test_02_real_create_commit_then_lost_ack_sticky_and_restart_denied(self):
        with TemporaryDirectory(prefix="a250-after-") as raw:
            path = Path(raw) / "chat.db"
            store = SQLiteChatStore(path)
            store.db = LostAckConnection(store.db, after_commit=True)
            try:
                with self.assertRaisesRegex(
                    StoreCommitOutcomeUncertainError, "COMMIT outcome unknown",
                ):
                    store.create_conversation(SCOPE, "committed but ACK lost")
                self.assertEqual(store._health_state, FAILED)
                self.assertTrue(marker(path).is_file())
                with self.assertRaises(StorageUnavailableError):
                    store.create_conversation(SCOPE, "no second attempt")
            finally:
                store.close()
            self.assertEqual(count_conversations(path), 1)
            with mock.patch("aion_chat.store.sqlite3.connect") as connection:
                with self.assertRaises(StorageUnavailableError):
                    SQLiteChatStore(path)
                connection.assert_not_called()

    def test_03_error_before_create_commit_still_vetoes_reopen(self):
        with TemporaryDirectory(prefix="a250-before-") as raw:
            path = Path(raw) / "chat.db"
            store = SQLiteChatStore(path)
            store.db = LostAckConnection(store.db, after_commit=False)
            try:
                with self.assertRaises(StoreCommitOutcomeUncertainError):
                    store.create_conversation(SCOPE, "not persisted")
            finally:
                store.close()
            self.assertEqual(count_conversations(path), 0)
            self.assertTrue(marker(path).is_file())
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore(path)

    def test_04_failed_marker_preparation_denies_commit(self):
        with TemporaryDirectory(prefix="a250-marker-") as raw:
            path = Path(raw) / "chat.db"
            store = SQLiteChatStore(path)
            try:
                with mock.patch.object(
                    store, "_publish_message_commit_marker",
                    side_effect=OSError("synthetic pre-COMMIT failure"),
                ):
                    with self.assertRaises(OSError):
                        store.create_conversation(SCOPE, "must not persist")
                self.assertEqual(count_conversations(path), 0)
            finally:
                store.close()

    def test_05_failed_post_commit_marker_cleanup_denies_reuse(self):
        with TemporaryDirectory(prefix="a250-cleanup-") as raw:
            path = Path(raw) / "chat.db"
            store = SQLiteChatStore(path)
            original = store._clear_message_commit_marker

            def fail_after_commit():
                self.assertTrue(marker(path).exists())
                raise OSError("synthetic cleanup interruption")

            store._clear_message_commit_marker = fail_after_commit
            try:
                with self.assertRaises(OSError):
                    store.create_conversation(SCOPE, "persisted before cleanup")
                self.assertTrue(marker(path).exists())
            finally:
                store._clear_message_commit_marker = original
                store.close()
            self.assertEqual(count_conversations(path), 1)
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore(path)

    def test_06_subprocess_crash_after_conversation_commit_vetoes_restart(self):
        with TemporaryDirectory(prefix="a250-crash-") as raw:
            path = Path(raw) / "chat.db"
            script = """
import os, sys
from pathlib import Path
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
db=SQLiteChatStore(Path(sys.argv[1]))
db._clear_message_commit_marker=lambda:os._exit(76)
db.create_conversation(Scope("owner-a250","tenant-a250","workspace-a250"),
                       "real committed conversation before crash")
os._exit(91)
"""
            proc = subprocess.run(
                [sys.executable, "-B", "-c", script, str(path)],
                capture_output=True, text=True, timeout=25,
            )
            self.assertEqual(proc.returncode, 76, (proc.stdout, proc.stderr))
            self.assertEqual(count_conversations(path), 1)
            self.assertTrue(marker(path).is_file())
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore(path)

    def test_07_three_processes_create_distinct_conversations_without_loss(self):
        with TemporaryDirectory(prefix="a250-procs-") as raw:
            path = Path(raw) / "chat.db"
            seed = SQLiteChatStore(path)
            seed.close()
            script = """
import sys
from pathlib import Path
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
scope=Scope("owner-a250","tenant-a250","workspace-a250")
store=SQLiteChatStore(Path(sys.argv[1]))
try:
    for i in range(6):
        store.create_conversation(scope, f"worker-{sys.argv[2]}-{i}")
finally:
    store.close()
"""
            processes = [
                subprocess.Popen(
                    [sys.executable, "-B", "-c", script, str(path), str(i)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                for i in range(3)
            ]
            try:
                for proc in processes:
                    out, err = proc.communicate(timeout=35)
                    self.assertEqual(proc.returncode, 0, (out, err))
            finally:
                for proc in processes:
                    if proc.poll() is None:
                        proc.kill()
                        proc.communicate(timeout=5)
            self.assertEqual(count_conversations(path), 18)
            self.assertFalse(marker(path).exists())
            reopened = SQLiteChatStore(path)
            try:
                self.assertEqual(len(reopened.list_conversations(
                    SCOPE, page_size=30
                ).items), 18)
                self.assertEqual(reopened.require_healthy()["state"], HEALTHY)
            finally:
                reopened.close()

    @unittest.expectedFailure
    def test_08_red_archive_writer_still_outside_shared_commit_fence(self):
        """Other SQLite writers still require the same protection in future."""
        with TemporaryDirectory(prefix="a250-red-") as raw:
            path = Path(raw) / "chat.db"
            store = SQLiteChatStore(path)
            try:
                conv = store.create_conversation(SCOPE, "archive needs fencing")
                with mock.patch.object(
                    store, "_publish_message_commit_marker",
                ) as publish:
                    store.archive_conversation(SCOPE, conv.id)
                # Desired: every mutating operation must prepare the crash veto.
                publish.assert_called()
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
