"""AION A171 LAB: best-effort read-window SQLite metadata observations.

All mutations happen in temporary databases. Tests distinguish detection,
legitimate write collisions, and write-operation ABA not addressed by A171.
No independent producer, Worker, provider call or production authority.
"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aion_chat.models import Message, Page, Scope
from aion_chat.staged_store import OperationScopedSQLiteChatStore
from aion_chat.store import FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError


class SQLiteReadSnapshotLabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scope = Scope("owner", "tenant", "workspace")

    def facade(self):
        handle = OperationScopedSQLiteChatStore(self.root / "primary.sqlite3")
        self.addCleanup(handle.close)
        return handle

    def test_01_normal_read_has_stable_snapshot(self):
        handle = self.facade()
        result = handle.list_conversations(self.scope)
        self.assertEqual(result.items, [])
        self.assertEqual(handle.storage_health()["state"], HEALTHY)

    def test_02_injected_read_metadata_drift_fails_closed(self):
        handle = self.facade()
        with patch.object(handle, "_read_snapshot",
                          side_effect=[("before",), ("after",)]):
            with self.assertRaisesRegex(
                    StorageUnavailableError,
                    "BOUND_DATABASE_READ_SNAPSHOT_CHANGED"):
                handle.list_conversations(self.scope)
        self.assertEqual(handle.storage_health()["state"], FAILED)
        with self.assertRaises(StorageUnavailableError):
            handle.list_conversations(self.scope)

    def test_03_real_same_inode_aba_during_read(self):
        handle = self.facade()
        expected = handle._path_identity(allow_missing=False)
        away = self.root / "aba-away.sqlite3"
        attempts = []
        Native = SQLiteChatStore

        class Intercept(Native):
            def list_conversations(self, *args, **kwargs):
                try:
                    os.replace(self.path, away)
                    os.replace(away, self.path)
                except OSError:
                    if away.exists():
                        os.replace(away, self.path)
                    attempts.append("OS_DENIED_OR_RESTORED")
                else:
                    attempts.append("ABA_COMPLETED")
                return Page(items=[])

        error = None
        with patch("aion_chat.staged_store.SQLiteChatStore", Intercept):
            try:
                handle.list_conversations(self.scope)
            except StorageUnavailableError as exc:
                error = exc
        self.assertEqual(len(attempts), 1)
        self.assertEqual(handle._path_identity(allow_missing=False), expected)
        if attempts[0] == "ABA_COMPLETED":
            self.assertIsNotNone(error)
            self.assertIn("BOUND_DATABASE_READ_SNAPSHOT_CHANGED", str(error))
            self.assertEqual(handle.storage_health()["state"], FAILED)
        else:
            self.assertIsNone(error)
            self.assertEqual(handle.storage_health()["state"], HEALTHY)
        print("A171_READ_ABA=" + attempts[0] +
              ("_OBSERVED_DENIED" if error else "_OS_NOT_EXERCISED"))

    def test_04_legitimate_concurrent_writer_can_invalidate_read(self):
        handle = self.facade()
        cid = handle.create_conversation(self.scope).id
        Native = SQLiteChatStore
        scope = self.scope

        class Intercept(Native):
            def list_conversations(self, *args, **kwargs):
                writer = Native(self.path)
                try:
                    writer.append_message(
                        scope, Message(cid, "user", "legitimate-writer"))
                finally:
                    writer.close()
                return Page(items=[])

        error = None
        with patch("aion_chat.staged_store.SQLiteChatStore", Intercept):
            try:
                result = handle.list_conversations(self.scope)
                self.assertEqual(result.items, [])
            except StorageUnavailableError as exc:
                error = exc
        readback = Native(handle.path)
        try:
            messages = readback.list_messages(self.scope, cid).items
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0].content, "legitimate-writer")
        finally:
            readback.close()
        if error is not None:
            self.assertIn("BOUND_DATABASE_READ_SNAPSHOT_CHANGED", str(error))
            self.assertEqual(handle.storage_health()["state"], FAILED)
            print("A171_CONCURRENT_WRITER=READ_DENIED_FALSE_POSITIVE")
        else:
            self.assertEqual(handle.storage_health()["state"], HEALTHY)
            print("A171_CONCURRENT_WRITER=NOT_OBSERVED_LIMIT")

    def test_05_real_aba_during_write_is_outside_read_guard(self):
        handle = self.facade()
        cid = handle.create_conversation(self.scope).id
        away = self.root / "aba-write-away.sqlite3"
        attempts = []
        Native = SQLiteChatStore

        class Intercept(Native):
            def append_message(self, *args, **kwargs):
                try:
                    os.replace(self.path, away)
                    os.replace(away, self.path)
                except OSError:
                    if away.exists():
                        os.replace(away, self.path)
                    attempts.append("OS_DENIED_OR_RESTORED")
                else:
                    attempts.append("ABA_COMPLETED")
                return super().append_message(*args, **kwargs)

        with patch("aion_chat.staged_store.SQLiteChatStore", Intercept):
            handle.append_message(
                self.scope, Message(cid, "user", "write-after-aba"))
        self.assertEqual(len(attempts), 1)
        self.assertEqual(handle.storage_health()["state"], HEALTHY)
        readback = Native(handle.path)
        try:
            self.assertEqual(len(readback.list_messages(self.scope, cid).items), 1)
        finally:
            readback.close()
        print("A171_WRITE_ABA=" + attempts[0] +
              ("_NOT_ATTESTED" if attempts[0] == "ABA_COMPLETED"
               else "_OS_NOT_EXERCISED"))

    def test_06_snapshot_observation_failure_latches(self):
        handle = self.facade()
        with patch.object(
                handle, "_read_snapshot",
                side_effect=StorageUnavailableError(
                    "BOUND_DATABASE_READ_SNAPSHOT_UNAVAILABLE")):
            with self.assertRaisesRegex(
                    StorageUnavailableError,
                    "BOUND_DATABASE_READ_SNAPSHOT_UNAVAILABLE"):
                handle.list_conversations(self.scope)
        self.assertEqual(handle.storage_health()["state"], FAILED)

    def test_07_write_method_does_not_claim_read_snapshot_gate(self):
        handle = self.facade()
        with patch.object(
                handle, "_read_snapshot",
                side_effect=AssertionError("write must not snapshot")):
            handle.create_conversation(self.scope)
        self.assertEqual(handle.storage_health()["state"], HEALTHY)


if __name__ == "__main__":
    unittest.main()
