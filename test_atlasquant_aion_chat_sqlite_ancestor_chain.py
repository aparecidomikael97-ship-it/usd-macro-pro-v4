"""AION A170 LAB: ancestor-chain alias and drift guards for staged SQLite.

Real temporary SQLite for storage; injected parent identity observations for
deterministic races. No provider, production, Worker or host-side attestation.
"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aion_chat.models import Message, Scope
from aion_chat.staged_store import OperationScopedSQLiteChatStore
from aion_chat.store import FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError


class SQLiteAncestorChainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scope = Scope("owner", "tenant", "workspace")

    def facade(self):
        handle = OperationScopedSQLiteChatStore(self.root / "stable.sqlite3")
        self.addCleanup(handle.close)
        return handle

    def test_01_actual_parent_symlink_denied_before_native_open(self):
        real = self.root / "real"
        real.mkdir()
        alias = self.root / "alias"
        try:
            alias.symlink_to(real, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("directory symlink unavailable: " + type(exc).__name__)
        with patch("aion_chat.staged_store.SQLiteChatStore") as native:
            with self.assertRaisesRegex(
                    StorageUnavailableError,
                    "BOUND_DATABASE_ANCESTOR_ALIAS_DENIED"):
                OperationScopedSQLiteChatStore(alias / "db.sqlite3")
            native.assert_not_called()
        self.assertFalse((real / "db.sqlite3").exists())

    def test_02_simulated_junction_is_denied_before_native_open(self):
        candidate = self.root / "junction-like"
        candidate.mkdir()
        if not hasattr(Path, "is_junction"):
            self.skipTest("Path.is_junction not provided by interpreter")
        with patch.object(Path, "is_junction",
                          autospec=True, side_effect=lambda p: p == candidate):
            with patch("aion_chat.staged_store.SQLiteChatStore") as native:
                with self.assertRaisesRegex(
                        StorageUnavailableError,
                        "BOUND_DATABASE_ANCESTOR_ALIAS_DENIED"):
                    OperationScopedSQLiteChatStore(candidate / "db.sqlite3")
                native.assert_not_called()

    def test_03_parent_component_is_regular_file_fails_closed(self):
        not_dir = self.root / "ordinary-file"
        not_dir.write_text("not a directory", encoding="utf-8")
        with patch("aion_chat.staged_store.SQLiteChatStore") as native:
            with self.assertRaisesRegex(
                    StorageUnavailableError,
                    "BOUND_DATABASE_ANCESTOR_NOT_DIRECTORY"):
                OperationScopedSQLiteChatStore(not_dir / "db.sqlite3")
            native.assert_not_called()

    def test_04_ancestor_drift_after_native_open_denies_operation(self):
        handle = self.facade()
        original = handle._ancestor_chain_identity
        calls = [0]

        def drift(*, allow_missing):
            calls[0] += 1
            identity = original(allow_missing=allow_missing)
            if calls[0] == 3:
                return ((identity[0][0] + 1, identity[0][1] + 1),
                        *identity[1:])
            return identity

        with patch.object(handle, "_ancestor_chain_identity", side_effect=drift):
            with self.assertRaisesRegex(
                    StorageUnavailableError,
                    "BOUND_DATABASE_ANCESTOR_CHANGED_DURING_OPEN"):
                handle.list_conversations(self.scope)
        self.assertEqual(calls[0], 3)
        self.assertEqual(handle.storage_health()["state"], FAILED)
        with self.assertRaises(StorageUnavailableError):
            handle.list_conversations(self.scope)

    def test_05_postcommit_ancestor_drift_is_unknown_never_replayed(self):
        handle = self.facade()
        cid = handle.create_conversation(self.scope).id
        original = handle._ancestor_chain_identity
        calls = [0]

        def drift(*, allow_missing):
            calls[0] += 1
            identity = original(allow_missing=allow_missing)
            if calls[0] == 4:
                return ((identity[0][0] + 1, identity[0][1] + 1),
                        *identity[1:])
            return identity

        with patch.object(handle, "_ancestor_chain_identity", side_effect=drift):
            with self.assertRaisesRegex(
                    StorageUnavailableError,
                    "BOUND_DATABASE_ANCESTOR_CHANGED_DURING_OPERATION"):
                handle.append_message(self.scope, Message(cid, "user", "once"))
        self.assertEqual(calls[0], 4)
        self.assertEqual(handle.storage_health()["state"], FAILED)
        with self.assertRaises(StorageUnavailableError):
            handle.append_message(self.scope, Message(cid, "user", "no-retry"))
        native = SQLiteChatStore(handle.path)
        try:
            items = native.list_messages(self.scope, cid).items
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].content, "once")
        finally:
            native.close()

    def test_06_new_nested_directories_bootstrap_and_pin_after_open(self):
        path = self.root / "new" / "nested" / "db.sqlite3"
        handle = OperationScopedSQLiteChatStore(path)
        self.addCleanup(handle.close)
        self.assertEqual(handle.storage_health()["state"], HEALTHY)
        self.assertTrue(path.is_file())
        self.assertTrue(all(identity is not None
                            for identity in handle._parent_identity))
        self.assertEqual(
            handle.create_conversation(self.scope).owner_id,
            self.scope.owner_id)


if __name__ == "__main__":
    unittest.main()
