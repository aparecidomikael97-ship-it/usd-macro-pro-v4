"""Offline, real SQLite lifecycle regression tests for Windows and Linux."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from aion_chat.models import Message, Scope
from aion_chat.staged_store import OperationScopedSQLiteChatStore
from aion_chat.store import FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError
import atlasquant_aion_chat_host_staging as host
from atlasquant_aion_chat_storage_resilience import (
    create_verified_staging_backup, restore_verified_staging_backup,
)


def access(owner="owner", fingerprint="fixture-fingerprint"):
    return {"allowed": True, "mode": "AUTHENTICATED", "role": "ADMIN",
            "session": {"username": owner, "role": "ADMIN",
                        "permissions": ["app:read", "aion:admin"],
                        "credential_fingerprint": fingerprint}}


class SQLiteLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scope = Scope("owner", "tenant-a", "workspace-a")
        self.session = {}
        self.addCleanup(host.close_all_staged_host_stores, self.session)

    def binding(self, *, owner="owner", tenant="tenant-a", workspace="workspace-a",
                fingerprint="fixture-fingerprint"):
        return host.build_staged_host_binding(
            self.session, access(owner, fingerprint), environment="TEST",
            config={host.FLAG: "true", host.TENANT_KEY: tenant,
                    host.WORKSPACE_KEY: workspace, host.DIRECTORY_KEY: str(self.root)},
            runtime_context={},
        )

    def store(self):
        store = OperationScopedSQLiteChatStore(self.root / "unit.sqlite3")
        self.addCleanup(store.close)
        return store

    def worker(self, action):
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(action).result(timeout=10)

    def test_native_connection_remains_thread_affine(self):
        native = SQLiteChatStore(self.root / "native.sqlite3")
        try:
            with self.assertRaises(sqlite3.ProgrammingError):
                self.worker(lambda: native.db.execute("SELECT 1").fetchone())
        finally:
            native.close()

    def test_real_host_rerun_on_another_thread_reuses_no_native_connection(self):
        first = self.binding()
        cid = first["store"].create_conversation(first["scope"]).id
        first["store"].append_message(first["scope"], Message(cid, "user", "persisted"))
        second = self.worker(self.binding)
        self.assertIs(first["store"], second["store"])
        self.assertFalse(hasattr(second["store"], "db"))
        message = self.worker(lambda: second["store"].list_messages(second["scope"], cid).items[0])
        self.assertEqual(message.content, "persisted")
        self.assertEqual(second["storage_health"]["state"], HEALTHY)

    def test_native_connections_close_on_their_creating_thread_even_on_error(self):
        events = []
        class Tracked(SQLiteChatStore):
            def __init__(self, path):
                super().__init__(path)
                self.owner = threading.get_ident()
                events.append(("open", self.owner, id(self)))
            def close(self):
                if self.db is not None:
                    if self.owner != threading.get_ident():
                        raise AssertionError("connection crossed threads")
                    super().close()
                    events.append(("close", self.owner, id(self)))
        with patch("aion_chat.staged_store.SQLiteChatStore", Tracked):
            store = self.store()
            cid = store.create_conversation(self.scope).id
            self.worker(lambda: store.append_message(self.scope, Message(cid, "user", "ok")))
            with self.assertRaises(LookupError):
                self.worker(lambda: store.get_conversation(self.scope, "missing"))
        self.assertEqual([e[1:] for e in events if e[0] == "open"],
                         [e[1:] for e in events if e[0] == "close"])

    def test_owner_tenant_workspace_and_credential_changes_revoke_old_handles(self):
        for change in ({"owner": "other"}, {"tenant": "tenant-b"},
                       {"workspace": "workspace-b"}, {"fingerprint": "rotated"}):
            with self.subTest(change=change):
                first = self.binding()
                second = self.worker(lambda: self.binding(**change))
                self.assertIsNot(first["store"], second["store"])
                with self.assertRaises(StorageUnavailableError):
                    first["store"].list_conversations(first["scope"])
                host.close_all_staged_host_stores(self.session)

    def test_logout_from_another_thread_revokes_and_relogin_preserves_data(self):
        first = self.binding()
        cid = first["store"].create_conversation(self.scope).id
        first["store"].append_message(self.scope, Message(cid, "user", "durable"))
        self.assertEqual(self.worker(lambda: host.close_all_staged_host_stores(self.session)), 1)
        self.assertEqual(self.session, {})
        with self.assertRaises(StorageUnavailableError):
            first["store"].get_conversation(self.scope, cid)
        second = self.binding()
        self.assertEqual(second["store"].list_messages(self.scope, cid).items[0].content, "durable")

    def test_tenant_isolation_survives_host_rotation(self):
        first = self.binding()
        cid = first["store"].create_conversation(self.scope).id
        second = self.binding(tenant="tenant-b")
        with self.assertRaises(LookupError):
            second["store"].get_conversation(second["scope"], cid)
        with self.assertRaises(LookupError):
            second["store"].list_messages(self.scope, cid)

    def test_concurrent_messages_are_materialized_and_not_lost(self):
        store = self.store()
        cid = store.create_conversation(self.scope).id
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda i: store.append_message(
                self.scope, Message(cid, "user", "message-" + str(i))), range(12)))
        self.assertEqual(len(results), 12)
        messages = store.list_messages(self.scope, cid).items
        self.assertEqual(len(messages), 12)
        self.assertEqual([m.sequence for m in messages], list(range(1, 13)))

    def test_independent_handles_use_existing_sqlite_transactions(self):
        one = self.store()
        two = OperationScopedSQLiteChatStore(one.path)
        self.addCleanup(two.close)
        cid = one.create_conversation(self.scope).id
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda i: (one if i % 2 else two).append_message(
                self.scope, Message(cid, "user", str(i))), range(8)))
        self.assertEqual(len(results), 8)
        self.assertEqual(one.get_conversation(self.scope, cid).message_count, 8)

    def test_constraint_failure_is_visible_and_rolls_back_message_count(self):
        store = self.store()
        cid = store.create_conversation(self.scope).id
        native = SQLiteChatStore(store.path)
        try:
            native.db.execute("CREATE TRIGGER reject_message BEFORE INSERT ON messages "
                              "BEGIN SELECT RAISE(ABORT,'fixture refusal'); END")
            native.db.commit()
        finally:
            native.close()
        with self.assertRaises(sqlite3.IntegrityError):
            self.worker(lambda: store.append_message(self.scope, Message(cid, "user", "refused")))
        self.assertEqual(store.get_conversation(self.scope, cid).message_count, 0)
        self.assertEqual(store.list_messages(self.scope, cid).items, [])

    def test_database_error_is_propagated_and_latched_not_hidden_by_reopen(self):
        store = self.store()
        with patch.object(SQLiteChatStore, "get_conversation", side_effect=sqlite3.DatabaseError("fixture")):
            with self.assertRaises(sqlite3.DatabaseError):
                store.get_conversation(self.scope, "id")
        self.assertEqual(store.storage_health()["state"], FAILED)
        with self.assertRaises(StorageUnavailableError):
            store.list_conversations(self.scope)

    def test_close_failure_after_commit_is_not_reported_as_success(self):
        store = self.store()
        cid = store.create_conversation(self.scope).id
        original_close = SQLiteChatStore.close
        def close_then_fail(native):
            original_close(native)
            raise sqlite3.OperationalError("fixture close error")
        with patch.object(SQLiteChatStore, "close", close_then_fail):
            with self.assertRaisesRegex(StorageUnavailableError, "CONNECTION_CLOSE_FAILED"):
                store.append_message(self.scope, Message(cid, "user", "commit may exist"))
        self.assertEqual(store.storage_health()["state"], FAILED)
        fresh = OperationScopedSQLiteChatStore(store.path)
        self.addCleanup(fresh.close)
        self.assertEqual(fresh.get_conversation(self.scope, cid).message_count, 1)

    def test_backup_restore_keeps_committed_data_and_integrity(self):
        store = self.store()
        cid = store.create_conversation(self.scope).id
        store.append_message(self.scope, Message(cid, "user", "backup-data"))
        backup = self.root / "backup.sqlite3"
        out = self.worker(lambda: create_verified_staging_backup(store, backup))
        self.assertEqual(out["state"], "BACKUP_VERIFIED")
        target = self.root / "restored.sqlite3"
        restored = restore_verified_staging_backup(backup, target)
        self.assertEqual(restored["state"], "RESTORE_VERIFIED")
        fresh = OperationScopedSQLiteChatStore(target)
        self.addCleanup(fresh.close)
        self.assertEqual(fresh.list_messages(self.scope, cid).items[0].content, "backup-data")
        self.assertEqual(fresh.storage_health(deep=True)["quick_check"], "ok")

    def test_fresh_process_reads_committed_message(self):
        store = self.store()
        cid = store.create_conversation(self.scope).id
        store.append_message(self.scope, Message(cid, "user", "after-restart"))
        code = ("from aion_chat.store import SQLiteChatStore; from aion_chat.models import Scope; "
                "import sys; s=SQLiteChatStore(sys.argv[1]); "
                "assert s.list_messages(Scope('owner','tenant-a','workspace-a'),sys.argv[2]).items[0].content=='after-restart'; s.close()")
        result = subprocess.run([sys.executable, "-B", "-c", code, str(store.path), cid],
                                cwd=Path(__file__).parent, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))

    def test_foreign_legacy_connection_is_retained_until_owner_can_close_it(self):
        native = SQLiteChatStore(self.root / "legacy.sqlite3")
        key = host._holder_key(self.scope)
        self.session[key] = {"store": native, "path": str(native.path)}
        try:
            with self.assertRaises(StorageUnavailableError):
                self.worker(self.binding)
            self.assertIs(self.session[key]["store"], native)
        finally:
            native.close()
        self.assertIsInstance(self.binding()["store"], OperationScopedSQLiteChatStore)

    def test_close_waits_for_inflight_operation_then_blocks_future_use(self):
        store = self.store()
        cid = store.create_conversation(self.scope).id
        started = threading.Event()
        release = threading.Event()
        original = SQLiteChatStore.get_conversation
        def wait_read(native, *args, **kwargs):
            started.set()
            if not release.wait(5):
                raise AssertionError("test release timed out")
            return original(native, *args, **kwargs)
        with patch.object(SQLiteChatStore, "get_conversation", wait_read):
            with ThreadPoolExecutor(max_workers=2) as pool:
                read = pool.submit(store.get_conversation, self.scope, cid)
                self.assertTrue(started.wait(5))
                close = pool.submit(store.close)
                self.assertFalse(close.done())
                release.set()
                self.assertEqual(read.result(timeout=10).id, cid)
                close.result(timeout=10)
        with self.assertRaises(StorageUnavailableError):
            store.get_conversation(self.scope, cid)

    def test_missing_or_replaced_database_is_not_silently_recreated(self):
        for replace in (False, True):
            with self.subTest(replace=replace):
                path = self.root / ("replace.sqlite3" if replace else "missing.sqlite3")
                store = OperationScopedSQLiteChatStore(path)
                self.addCleanup(store.close)
                store.create_conversation(self.scope)
                path.rename(path.with_suffix(".preserved"))
                if replace:
                    replacement = SQLiteChatStore(path)
                    replacement.close()
                with self.assertRaises(StorageUnavailableError):
                    store.list_conversations(self.scope)
                self.assertEqual(store.storage_health()["state"], FAILED)
                if not replace:
                    self.assertFalse(path.exists())

    def test_corruption_does_not_become_healthy_on_implicit_reopen(self):
        store = self.store()
        store.path.write_bytes(b"not a sqlite database")
        with self.assertRaises(StorageUnavailableError):
            store.list_conversations(self.scope)
        self.assertEqual(store.storage_health()["state"], FAILED)


if __name__ == "__main__":
    unittest.main()
