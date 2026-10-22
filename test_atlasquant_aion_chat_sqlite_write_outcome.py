"""A173 LAB: write ABA detection versus persisted effects and false positives.

All objects and filesystem changes are temporary. No external provider,
real financial operation, receipt, Worker, or production authority.
"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aion_chat.models import Message, Scope
from aion_chat.staged_store import OperationScopedSQLiteChatStore
from aion_chat.store import FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError


class WriteOutcomeUnknownTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scope = Scope("owner", "tenant", "workspace")

    def facade(self):
        handle = OperationScopedSQLiteChatStore(self.root / "primary.sqlite3")
        self.addCleanup(handle.close)
        return handle

    def native_messages(self, handle, cid):
        native = SQLiteChatStore(handle.path)
        try:
            return native.list_messages(self.scope, cid).items
        finally:
            native.close()

    def test_01_normal_sqlite_writes_do_not_change_parent_entry(self):
        handle = self.facade()
        cid = handle.create_conversation(self.scope).id
        handle.append_message(
            self.scope, Message(cid, "user", "first"))
        handle.append_message(
            self.scope, Message(cid, "user", "second"))
        self.assertEqual(len(self.native_messages(handle, cid)), 2)
        self.assertEqual(handle.storage_health()["state"], HEALTHY)
        print("A173_NORMAL_WRITES=ALLOWED")

    def test_02_post_write_observation_denies_success_but_write_exists(self):
        handle = self.facade()
        cid = handle.create_conversation(self.scope).id
        with patch.object(handle, "_write_snapshot",
                          side_effect=[("before",), ("after",)]):
            with self.assertRaisesRegex(
                    StorageUnavailableError,
                    "BOUND_DATABASE_WRITE_OUTCOME_UNKNOWN_DIRECTORY_CHANGED"):
                handle.append_message(
                    self.scope, Message(cid, "user", "committed-once"))
        self.assertEqual(handle.storage_health()["state"], FAILED)
        self.assertEqual(
            handle.storage_health()["reason"],
            "BOUND_DATABASE_WRITE_OUTCOME_UNKNOWN_DIRECTORY_CHANGED")
        items = self.native_messages(handle, cid)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].content, "committed-once")
        with self.assertRaises(StorageUnavailableError):
            handle.append_message(
                self.scope, Message(cid, "user", "forbidden-replay"))
        self.assertEqual(len(self.native_messages(handle, cid)), 1)
        print("A173_INJECTED_DRIFT=OUTCOME_UNKNOWN_BUT_COMMITTED_ONCE")

    def test_03_pre_write_observation_error_blocks_before_mutation(self):
        handle = self.facade()
        cid = handle.create_conversation(self.scope).id
        with patch.object(
                handle, "_write_snapshot",
                side_effect=StorageUnavailableError(
                    "BOUND_DATABASE_FINGERPRINT_UNAVAILABLE")):
            with self.assertRaisesRegex(
                    StorageUnavailableError,
                    "BOUND_DATABASE_FINGERPRINT_UNAVAILABLE"):
                handle.append_message(
                    self.scope, Message(cid, "user", "must-not-append"))
        self.assertEqual(handle.storage_health()["state"], FAILED)
        self.assertEqual(self.native_messages(handle, cid), [])

    def test_04_unrelated_directory_file_can_mark_committed_write_unknown(self):
        handle = self.facade()
        cid = handle.create_conversation(self.scope).id
        extra = self.root / "not-this-database.txt"
        Native = SQLiteChatStore

        class Intercept(Native):
            def append_message(self, *args, **kwargs):
                extra.write_text("unrelated", encoding="utf-8")
                return super().append_message(*args, **kwargs)

        error = None
        with patch("aion_chat.staged_store.SQLiteChatStore", Intercept):
            try:
                handle.append_message(
                    self.scope, Message(cid, "user", "already-committed"))
            except StorageUnavailableError as exc:
                error = exc
        self.assertTrue(extra.is_file())
        self.assertEqual(len(self.native_messages(handle, cid)), 1)
        if error is not None:
            self.assertIn("BOUND_DATABASE_WRITE_OUTCOME_UNKNOWN_DIRECTORY_CHANGED",
                          str(error))
            self.assertEqual(handle.storage_health()["state"], FAILED)
            print("A173_UNRELATED_FILE=FALSE_POST_WRITE_UNKNOWN")
        else:
            self.assertEqual(handle.storage_health()["state"], HEALTHY)
            print("A173_UNRELATED_FILE=TIMESTAMP_DRIFT_NOT_OBSERVED")

    def test_05_concurrent_wal_writer_does_not_mark_own_write_unknown(self):
        handle = self.facade()
        cid = handle.create_conversation(self.scope).id
        Native = SQLiteChatStore
        scope = self.scope

        class Intercept(Native):
            def append_message(self, *args, **kwargs):
                other = Native(self.path)
                try:
                    other.append_message(
                        scope, Message(cid, "user", "other-writer"))
                finally:
                    other.close()
                return super().append_message(*args, **kwargs)

        with patch("aion_chat.staged_store.SQLiteChatStore", Intercept):
            handle.append_message(
                self.scope, Message(cid, "user", "own-writer"))
        self.assertEqual(handle.storage_health()["state"], HEALTHY)
        items = self.native_messages(handle, cid)
        self.assertEqual(len(items), 2)
        self.assertEqual(
            {item.content for item in items}, {"other-writer", "own-writer"})
        print("A173_CONCURRENT_WRITER=WRITES_ALLOWED")

    def test_06_backup_file_protocol_intentionally_not_covered(self):
        handle = self.facade()
        self.assertNotIn("backup_to", handle._WRITE_SENSITIVE_METHODS)
        self.assertIn("append_message", handle._WRITE_SENSITIVE_METHODS)
        self.assertIn("wal_checkpoint", handle._WRITE_SENSITIVE_METHODS)


if __name__ == "__main__":
    unittest.main()
