"""A187 LAB: strict opt-in SQLite factory admission and honest bypasses.

This is NOT an authenticated trust root. A caller-controlled factory, removal
of the sqlite3 progress handler, and raw sqlite3.connect remain bypasses.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from aion_chat.staged_store import OperationScopedSQLiteChatStore
from test_atlasquant_aion_connection_factory_a186_lab import SyntheticEpochFactory


class A187StrictManagedConnectionLab(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="a187-strict-store-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "aion.sqlite"
        self.scope = Scope(owner_id="lab-owner", tenant_id="lab-tenant",
                           workspace_id="lab-workspace")
        self.factory = SyntheticEpochFactory()

    def managed(self):
        obj = SQLiteChatStore(
            self.path, connection_factory=self.factory,
            require_managed_connection=True)
        self.addCleanup(obj.close)
        return obj

    def test_missing_factory_denied_before_any_file_or_directory_creation(self):
        path = Path(self.tmp.name) / "nested" / "never.sqlite"
        with self.assertRaisesRegex(StorageUnavailableError, "A187_MANAGED_CONNECTION_REQUIRED"):
            SQLiteChatStore(path, require_managed_connection=True)
        self.assertFalse(path.parent.exists(), "strict denial had filesystem effects")
        with self.assertRaisesRegex(StorageUnavailableError, "A187_MANAGED_CONNECTION_REQUIRED"):
            OperationScopedSQLiteChatStore(path, require_managed_connection=True)
        self.assertFalse(path.parent.exists())
        print("A187_MISSING_FACTORY=DENIED_BEFORE_FS_EFFECT")

    def test_native_default_factory_denied_when_strict_is_requested(self):
        with self.assertRaisesRegex(StorageUnavailableError, "A187_NATIVE_DEFAULT_FACTORY_DENIED"):
            SQLiteChatStore(self.path, connection_factory=sqlite3.connect,
                            require_managed_connection=True)
        with self.assertRaisesRegex(StorageUnavailableError, "A187_NATIVE_DEFAULT_FACTORY_DENIED"):
            OperationScopedSQLiteChatStore(self.path, connection_factory=sqlite3.connect,
                                           require_managed_connection=True)
        self.assertFalse(self.path.exists())
        print("A187_EXPLICIT_NATIVE_DEFAULT_FACTORY=DENIED")

    def test_bad_types_denied_without_open(self):
        for flag in ("yes", 1, [], None):
            with self.subTest(flag=flag):
                with self.assertRaises(TypeError):
                    SQLiteChatStore(self.path, require_managed_connection=flag)
        with self.assertRaises(TypeError):
            SQLiteChatStore(self.path, connection_factory="not-callable",
                            require_managed_connection=True)
        with self.assertRaises(TypeError):
            OperationScopedSQLiteChatStore(
                self.path, connection_factory="not-callable",
                require_managed_connection=True)
        self.assertFalse(self.path.exists())
        print("A187_INVALID_FACTORY_AND_FLAG=DENIED")

    def test_managed_constructor_and_reopen_deny_revoked_local_epoch(self):
        store = self.managed()
        store.create_conversation(self.scope, title="synthetic")
        self.factory.current_epoch = 8
        with self.assertRaisesRegex(sqlite3.OperationalError, "(?i)interrupt"):
            store.db.execute("SELECT count(*) FROM conversations").fetchone()
        count = len(self.factory.paths)
        with self.assertRaisesRegex(StorageUnavailableError,
                                    "A186_LAB_EPOCH_UNAVAILABLE_OR_STALE"):
            SQLiteChatStore(self.path, connection_factory=self.factory,
                            require_managed_connection=True)
        self.assertEqual(count, len(self.factory.paths))
        print("A187_STRICT_MANAGED_CACHED_READ_AND_REOPEN=DENIED")

    def test_staged_store_requires_factory_on_reopen(self):
        store = self.managed()
        staged = OperationScopedSQLiteChatStore(
            self.path, connection_factory=self.factory,
            require_managed_connection=True)
        self.addCleanup(staged.close)
        opened = len(self.factory.paths)
        staged.create_conversation(self.scope, title="synthetic staged")
        self.assertGreater(len(self.factory.paths), opened)
        self.factory.current_epoch = 8
        with self.assertRaises(StorageUnavailableError):
            staged.list_conversations(self.scope)
        print("A187_STAGED_STRICT_FACTORY=PROPAGATED_AND_REVOKED")

    def test_strict_backup_target_opens_with_same_factory(self):
        store = self.managed()
        store.create_conversation(self.scope, title="backup data")
        report = store.backup_to(Path(self.tmp.name) / "capture.sqlite")
        self.assertEqual(report["state"], "BACKUP_VERIFIED")
        self.assertTrue(any(".tmp-" in x for x in self.factory.paths))
        print("A187_BACKUP_TEMP_CONNECTION=STRICT_FACTORY")

    def test_removing_local_progress_handler_remains_real_bypass(self):
        store = self.managed()
        store.db.execute("SELECT 1").fetchone()
        store.db.set_progress_handler(None, 0)
        self.factory.current_epoch = 8
        self.assertEqual(store.db.execute("SELECT 1").fetchone()[0], 1)
        print("A187_PROGRESS_HANDLER_REMOVAL_BYPASS=REPRODUCED")

    def test_caller_supplied_fake_factory_and_raw_connections_bypass(self):
        # This passes the structural admission test but installs no epoch guard.
        def fake(path, **kw):
            return sqlite3.connect(path, **kw)
        store = SQLiteChatStore(
            self.path, connection_factory=fake,
            require_managed_connection=True)
        self.addCleanup(store.close)
        self.factory.current_epoch = 8
        self.assertEqual(store.db.execute("SELECT 1").fetchone()[0], 1)
        other = sqlite3.connect(self.path)
        try:
            other.execute("CREATE TABLE a187_untrusted(value INTEGER)")
            other.execute("INSERT INTO a187_untrusted VALUES(8)")
            other.commit()
        finally:
            other.close()
        self.assertEqual(store.db.execute(
            "SELECT value FROM a187_untrusted").fetchone()[0], 8)
        print("A187_CALLER_FAKE_FACTORY_AND_RAW_SQLITE_BYPASS=REPRODUCED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
