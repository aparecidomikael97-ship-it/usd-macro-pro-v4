"""A169 LAB: real temporary filesystem changes around an open SQLite handle.

Tests classify OS-denied attempts separately from observed detections and
from known blind spots. Only temporary local paths are used; zero providers,
zero Worker and zero production authorization.
"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aion_chat.models import Message, Page, Scope
from aion_chat.staged_store import OperationScopedSQLiteChatStore
from aion_chat.store import FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError


class SQLiteLiveMutationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scope = Scope("owner", "tenant", "workspace")

    def facade(self):
        handle = OperationScopedSQLiteChatStore(self.root / "primary.sqlite3")
        self.addCleanup(handle.close)
        return handle

    def alternate(self, filename):
        path = self.root / filename
        native = SQLiteChatStore(path)
        native.close()
        return path

    def test_01_replace_database_before_native_open(self):
        handle = self.facade()
        replacement = self.alternate("before.sqlite3")
        attempts = []
        Native = SQLiteChatStore

        class Intercept(Native):
            def __init__(self, path):
                try:
                    os.replace(replacement, path)
                except OSError:
                    attempts.append("OS_DENIED")
                else:
                    attempts.append("REPLACED")
                super().__init__(path)

        error = None
        with patch("aion_chat.staged_store.SQLiteChatStore", Intercept):
            try:
                handle.list_conversations(self.scope)
            except StorageUnavailableError as exc:
                error = exc
        self.assertEqual(len(attempts), 1)
        if attempts[0] == "REPLACED":
            self.assertIsNotNone(error)
            self.assertIn("BOUND_DATABASE_CHANGED_DURING_OPEN", str(error))
            self.assertEqual(handle.storage_health()["state"], FAILED)
        else:
            self.assertIsNone(error)
            self.assertEqual(handle.storage_health()["state"], HEALTHY)
        print("A169_BEFORE_NATIVE_OPEN=" + attempts[0])

    def test_02_replace_database_while_native_connection_open(self):
        handle = self.facade()
        replacement = self.alternate("during.sqlite3")
        attempts = []
        Native = SQLiteChatStore

        class Intercept(Native):
            def list_conversations(self, *args, **kwargs):
                try:
                    os.replace(replacement, self.path)
                except OSError:
                    attempts.append("OS_DENIED")
                else:
                    attempts.append("REPLACED")
                return Page(items=[])

        error = None
        with patch("aion_chat.staged_store.SQLiteChatStore", Intercept):
            try:
                handle.list_conversations(self.scope)
            except StorageUnavailableError as exc:
                error = exc
        self.assertEqual(len(attempts), 1)
        if attempts[0] == "REPLACED":
            self.assertIsNotNone(error)
            self.assertIn("BOUND_DATABASE_CHANGED_DURING_OPERATION", str(error))
            self.assertEqual(handle.storage_health()["state"], FAILED)
        else:
            self.assertIsNone(error)
            self.assertEqual(handle.storage_health()["state"], HEALTHY)
        print("A169_WHILE_NATIVE_OPEN=" + attempts[0])

    def test_03_actual_aba_path_rename_is_a_known_blind_spot(self):
        handle = self.facade()
        temporary = self.root / "aba-away.sqlite3"
        original = handle._path_identity(allow_missing=False)
        attempts = []
        Native = SQLiteChatStore

        class Intercept(Native):
            def list_conversations(self, *args, **kwargs):
                try:
                    os.replace(self.path, temporary)
                    os.replace(temporary, self.path)
                except OSError:
                    if temporary.exists():
                        os.replace(temporary, self.path)
                    attempts.append("OS_DENIED_OR_RESTORED")
                else:
                    attempts.append("ABA_COMPLETED")
                return Page(items=[])

        with patch("aion_chat.staged_store.SQLiteChatStore", Intercept):
            result = handle.list_conversations(self.scope)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(result.items, [])
        self.assertEqual(handle._path_identity(allow_missing=False), original)
        self.assertEqual(handle.storage_health()["state"], HEALTHY)
        # If completed, this is an observed LIMIT, not a security gate pass.
        print("A169_ABA=" + attempts[0] +
              ("_NOT_DETECTED" if attempts[0] == "ABA_COMPLETED"
               else "_NOT_EXERCISED"))

    def test_04_concurrent_same_inode_write_is_not_content_attestation(self):
        handle = self.facade()
        cid = handle.create_conversation(self.scope).id
        Native = SQLiteChatStore
        access = self.scope

        class Intercept(Native):
            def list_conversations(self, *args, **kwargs):
                writer = Native(self.path)
                try:
                    writer.append_message(
                        access, Message(cid, "user", "other-writer"))
                finally:
                    writer.close()
                return Page(items=[])

        before = handle._path_identity(allow_missing=False)
        with patch("aion_chat.staged_store.SQLiteChatStore", Intercept):
            result = handle.list_conversations(self.scope)
        self.assertEqual(result.items, [])
        self.assertEqual(handle._path_identity(allow_missing=False), before)
        self.assertEqual(handle.storage_health()["state"], HEALTHY)
        readback = Native(handle.path)
        try:
            items = readback.list_messages(self.scope, cid).items
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].content, "other-writer")
        finally:
            readback.close()
        print("A169_SAME_INODE_WRITE=PERMITTED_NOT_ATTESTED")

    def test_05_parent_directory_symlink_is_not_an_identity_proof(self):
        target = self.root / "real-parent"
        target.mkdir()
        alias = self.root / "aliased-parent"
        try:
            alias.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("OS does not permit a directory symlink here: " +
                          type(exc).__name__)
        handle = OperationScopedSQLiteChatStore(alias / "nested.sqlite3")
        self.addCleanup(handle.close)
        self.assertEqual(handle.storage_health()["state"], HEALTHY)
        self.assertTrue((target / "nested.sqlite3").is_file())
        print("A169_PARENT_DIRECTORY_ALIAS=ALLOWED_NOT_ATTESTED")


if __name__ == "__main__":
    unittest.main()
