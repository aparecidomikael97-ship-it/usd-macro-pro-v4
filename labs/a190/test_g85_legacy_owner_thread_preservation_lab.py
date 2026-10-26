"""G85 RED-first: staging host must not strand legacy SQLite handles.

Synthetic temp SQLite only. Retain creating-thread close authority while
refusing cross-thread reuse/cleanup. No independent native VFS proof, no live
SEND, no Worker, no merge/deploy or H0 custody claims. P0 0/6 HARD NO-GO.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.staged_store import OperationScopedSQLiteChatStore
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
import atlasquant_aion_chat_host_staging as host


SCOPE = Scope("g85-owner", "g85-tenant", "g85-workspace")


class G85LegacyThreadOwnerPreservation(unittest.TestCase):
    def setUp(self):
        disposable = tempfile.TemporaryDirectory(prefix="aion-g85-owner-")
        self.addCleanup(disposable.cleanup)
        self.root = Path(disposable.name)
        self.scope = SCOPE
        self.path = host._store_path(self.scope, self.root)
        self.native = SQLiteChatStore(self.path)
        self.raw = self.native.db
        # Test fixture retains the raw owner-thread handle for a guaranteed
        # cleanup even when the original code has already detached self.db.
        self.addCleanup(self.raw.close)
        self.key = host._holder_key(self.scope)
        self.session = {
            self.key: {"store": self.native, "path": str(self.native.path)}
        }

    @staticmethod
    def capture(callback):
        try:
            return callback()
        except BaseException as exc:
            return exc

    @staticmethod
    def foreign(callback):
        with ThreadPoolExecutor(max_workers=1) as executor:
            return G85LegacyThreadOwnerPreservation.capture(
                lambda: executor.submit(callback).result(timeout=10)
            )

    def binding(self):
        return host.get_or_create_staged_store(
            self.session, self.scope, self.root
        )

    def assert_owner_can_close(self):
        self.assertIs(self.native.db, self.raw)
        self.native.close()
        self.assertIsNone(self.native.db)
        with self.assertRaises(sqlite3.ProgrammingError):
            self.raw.execute("SELECT 1")
        probe = sqlite3.connect(str(self.path), timeout=0)
        try:
            probe.execute("BEGIN IMMEDIATE")
            self.assertTrue(probe.in_transaction)
        finally:
            probe.close()

    def test_01_foreign_legacy_replacement_must_not_consume_native_handle(self):
        caught = self.foreign(self.binding)
        self.assertIsInstance(caught, StorageUnavailableError)
        self.assertIs(self.session[self.key]["store"], self.native)
        self.assert_owner_can_close()
        print("G85_FOREIGN_REPLACE_GREEN=OWNER_CAN_RELEASE_NATIVE_HANDLE")

    def test_02_foreign_close_all_must_keep_owner_close_right(self):
        caught = self.foreign(
            lambda: host.close_all_staged_host_stores(self.session)
        )
        self.assertIsInstance(caught, StorageUnavailableError)
        self.assertIs(self.session[self.key]["store"], self.native)
        self.assert_owner_can_close()
        print("G85_FOREIGN_CLOSE_ALL_GREEN=OWNER_RETAINED")

    def test_03_foreign_close_one_must_refuse_before_driver_close(self):
        caught = self.foreign(
            lambda: host.close_staged_host_store(self.session, self.scope)
        )
        self.assertIsInstance(caught, StorageUnavailableError)
        self.assertIs(self.session[self.key]["store"], self.native)
        self.assert_owner_can_close()
        print("G85_FOREIGN_CLOSE_ONE_GREEN=OWNER_RETAINED")

    def test_04_creating_thread_migration_replaces_legacy_with_scoped(self):
        staged = self.binding()
        self.assertIsInstance(staged, OperationScopedSQLiteChatStore)
        self.assertIs(self.session[self.key]["store"], staged)
        self.assertIsNone(self.native.db)
        with self.assertRaises(sqlite3.ProgrammingError):
            self.raw.execute("SELECT 1")
        staged.close()
        print("G85_OWNER_REPLACE_GREEN=SCOPED_HANDLE")

    def test_05_operation_scoped_handle_remains_cross_thread_closeable(self):
        staged = self.binding()
        self.assertIsInstance(staged, OperationScopedSQLiteChatStore)
        closed = self.foreign(
            lambda: host.close_all_staged_host_stores(self.session)
        )
        self.assertEqual(closed, 1)
        self.assertNotIn(self.key, self.session)
        with self.assertRaises(StorageUnavailableError):
            staged.list_conversations(self.scope)
        print("G85_SCOPED_CROSS_THREAD_GREEN=STILL_REVOKABLE")


if __name__ == "__main__":
    unittest.main()
