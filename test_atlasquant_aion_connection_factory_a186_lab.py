"""A186 LAB: opt-in SQLite factory propagation on actual AION store/staged/backup.

This is a coverage experiment, not independent authorization or native VFS.
Untrusted callers can still create an unguarded store or conn, and can remove
the local progress handler. NEVER treat GREEN as P0 homologation.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from aion_chat.models import Scope
from aion_chat.staged_store import OperationScopedSQLiteChatStore
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from atlasquant_aion_execution_outbox import ExecutionOutbox


class SyntheticEpochFactory:
    """Captures one LAB epoch; pin and current state are under TEST control."""
    def __init__(self) -> None:
        self.pinned_epoch = 7
        self.current_epoch = 7
        self.available = True
        self.paths = []

    def __call__(self, path: str, **kw):
        # Reject BEFORE opening a native connection when the authority is bad.
        if not self.available or self.current_epoch != self.pinned_epoch:
            raise StorageUnavailableError("A186_LAB_EPOCH_UNAVAILABLE_OR_STALE")
        conn = sqlite3.connect(path, **kw)

        def abort_on_revocation():
            return int(not self.available or self.current_epoch != self.pinned_epoch)

        try:
            conn.set_progress_handler(abort_on_revocation, 1)
        except Exception:
            conn.close()
            raise
        self.paths.append(str(path))
        return conn


class A186OptInConnectionFactoryLab(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="a186-conn-factory-")
        self.path = Path(self.tmp.name) / "chat.sqlite"
        self.scope = Scope(
            owner_id="lab-owner", tenant_id="lab-tenant",
            workspace_id="lab-workspace")
        self.factory = SyntheticEpochFactory()
        self.store = SQLiteChatStore(self.path, connection_factory=self.factory)

    def tearDown(self) -> None:
        try:
            self.store.close()
        finally:
            self.tmp.cleanup()

    def test_factory_controls_the_initial_live_store(self):
        self.assertEqual(len(self.factory.paths), 1)
        self.store.create_conversation(self.scope, title="A186 dummy")
        self.assertEqual(len(self.store.list_conversations(self.scope).items), 1)
        self.factory.current_epoch = 8
        with self.assertRaisesRegex(sqlite3.OperationalError, "(?i)interrupt"):
            self.store.db.execute("SELECT count(*) FROM conversations").fetchone()
        print("A186_INITIAL_CONNECTION_AFTER_REVOCATION=DENIED")

    def test_outbox_shares_factory_created_connection(self):
        outbox = ExecutionOutbox(self.store, self.scope)
        self.assertIs(outbox.db, self.store.db)
        self.assertEqual(outbox.list(), [])
        self.factory.current_epoch = 8
        with self.assertRaisesRegex(sqlite3.OperationalError, "(?i)interrupt"):
            outbox.list()
        print("A186_OUTBOX_SHARED_FACTORY_CONNECTION=DENIED_AFTER_REVOCATION")

    def test_new_factory_store_cannot_reenroll_after_synthetic_epoch_revocation(self):
        self.factory.current_epoch = 8
        before = len(self.factory.paths)
        with self.assertRaisesRegex(StorageUnavailableError, "A186_LAB_EPOCH_UNAVAILABLE_OR_STALE"):
            SQLiteChatStore(self.path, connection_factory=self.factory)
        self.assertEqual(len(self.factory.paths), before)
        print("A186_MANAGED_REOPEN_REVOKED=DENIED_BEFORE_NATIVE_OPEN")

    def test_staged_store_propagates_factory_to_every_per_operation_open(self):
        staged = OperationScopedSQLiteChatStore(
            self.path, connection_factory=self.factory)
        try:
            count_before = len(self.factory.paths)
            staged.create_conversation(self.scope, title="staged synthetic")
            self.assertGreater(len(self.factory.paths), count_before)
            self.factory.current_epoch = 8
            with self.assertRaises(StorageUnavailableError):
                staged.list_conversations(self.scope)
        finally:
            staged.close()
        print("A186_STAGED_REOPEN_MANAGED=DENIED_AFTER_REVOCATION")

    def test_backup_target_uses_same_opt_in_factory(self):
        self.store.create_conversation(self.scope, title="backup synthetic")
        backup_path = Path(self.tmp.name) / "backup.sqlite"
        report = self.store.backup_to(backup_path)
        self.assertEqual(report["state"], "BACKUP_VERIFIED")
        self.assertTrue(backup_path.exists())
        self.assertTrue(any(".tmp-" in p for p in self.factory.paths[1:]))
        print("A186_BACKUP_TEMP_CONNECTION=FACTORY_CALLED")

    def test_unmanaged_raw_and_default_store_remain_bypasses(self):
        self.factory.current_epoch = 8
        # Explicit counterexamples: no factory -> no epoch check.
        unguarded = SQLiteChatStore(self.path)
        try:
            self.assertEqual(unguarded.db.execute("SELECT 1").fetchone()[0], 1)
        finally:
            unguarded.close()
        raw = sqlite3.connect(self.path)
        try:
            raw.execute("CREATE TABLE IF NOT EXISTS a186_unmanaged_proof(value INTEGER)")
            raw.execute("INSERT INTO a186_unmanaged_proof VALUES (8)")
            raw.commit()
        finally:
            raw.close()
        print("A186_UNMANAGED_CONNECTION_BYPASS=REPRODUCED")


if __name__ == "__main__":
    print("A186_SQLITE_VERSION=" + sqlite3.sqlite_version)
    unittest.main(verbosity=2)
