"""P0 SQLite facade: hostile path alias and mid-operation identity race tests.

Offline real SQLite except deterministic identity change injectors. The
injectors demonstrate a fail-closed *detection* boundary, not immunity to
untrusted OS/filesystem activity, WAL replay or hostile physical rollback.
"""
from pathlib import Path
from types import SimpleNamespace
import stat
import tempfile
import unittest
from unittest.mock import patch

from aion_chat.models import Message, Scope
from aion_chat.staged_store import OperationScopedSQLiteChatStore
from aion_chat.store import FAILED, SQLiteChatStore, StorageUnavailableError


class SQLitePathIdentityHardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scope = Scope("owner", "tenant", "workspace")

    def store(self):
        handle = OperationScopedSQLiteChatStore(self.root / "identity.sqlite3")
        self.addCleanup(handle.close)
        return handle

    def test_01_preexisting_symlink_is_denied_before_sqlite_open(self):
        alias = self.root / "alias.sqlite3"
        fake_link = SimpleNamespace(st_mode=stat.S_IFLNK, st_dev=1, st_ino=2)
        real_lstat = Path.lstat

        def observed(path, *args, **kwargs):
            # Only the final DB entry is a synthetic symlink. Parent
            # directories remain real to exercise the final-file gate.
            if path == alias:
                return fake_link
            return real_lstat(path, *args, **kwargs)

        with patch.object(Path, "lstat", autospec=True, side_effect=observed):
            with patch("aion_chat.staged_store.SQLiteChatStore") as native:
                with self.assertRaisesRegex(
                        StorageUnavailableError, "BOUND_DATABASE_SYMLINK_DENIED"):
                    OperationScopedSQLiteChatStore(alias)
                native.assert_not_called()
        self.assertFalse(alias.exists())

    def test_02_nonregular_path_is_denied_before_sqlite_open(self):
        directory = self.root / "not_a_database"
        directory.mkdir()
        with patch("aion_chat.staged_store.SQLiteChatStore") as native:
            with self.assertRaisesRegex(
                    StorageUnavailableError, "BOUND_DATABASE_NOT_REGULAR_FILE"):
                OperationScopedSQLiteChatStore(directory)
            native.assert_not_called()

    def test_03_identity_change_during_native_open_denies_method(self):
        handle = self.store()
        # Existing facade already pinned its real database identity.
        original = handle._path_identity
        calls = [0]

        def observed(*, allow_missing):
            calls[0] += 1
            real = original(allow_missing=allow_missing)
            if calls[0] == 3:  # after native SQLite opens; anchor adds a pre-open check
                return real[0] + 1, real[1] + 1
            return real

        with patch.object(handle, "_path_identity", side_effect=observed):
            with self.assertRaisesRegex(
                    StorageUnavailableError, "BOUND_DATABASE_CHANGED_DURING_OPEN"):
                handle.list_conversations(self.scope)
        self.assertEqual(calls[0], 3)
        self.assertEqual(handle.storage_health()["state"], FAILED)
        with self.assertRaises(StorageUnavailableError):
            handle.list_conversations(self.scope)

    def test_04_post_commit_path_drift_is_uncertain_and_not_replayed(self):
        handle = self.store()
        cid = handle.create_conversation(self.scope).id
        original = handle._path_identity
        calls = [0]

        def observed(*, allow_missing):
            calls[0] += 1
            real = original(allow_missing=allow_missing)
            if calls[0] == 4:  # after SQLite method may have committed
                return real[0] + 1, real[1] + 1
            return real

        with patch.object(handle, "_path_identity", side_effect=observed):
            with self.assertRaisesRegex(
                    StorageUnavailableError,
                    "BOUND_DATABASE_CHANGED_DURING_OPERATION"):
                handle.append_message(
                    self.scope, Message(cid, "user", "once-only"))
        self.assertEqual(calls[0], 4)
        self.assertEqual(handle.storage_health()["state"], FAILED)
        with self.assertRaises(StorageUnavailableError):
            handle.append_message(self.scope, Message(cid, "user", "never-resend"))
        # Readback is diagnostic only; it does not grant authority to retry.
        native = SQLiteChatStore(handle.path)
        try:
            items = native.list_messages(self.scope, cid).items
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].content, "once-only")
        finally:
            native.close()


if __name__ == "__main__":
    unittest.main()
