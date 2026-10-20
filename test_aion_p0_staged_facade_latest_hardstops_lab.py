"""LAB port review: keep native SQLite hardstops and new STAGING availability.

17 inherited lifecycle tests are a byte-for-byte copy of #1195. This file
adds current-branch security/compatibility checks; no production Worker, AION
dispatch, real owner identity, provider call, or independent external receipt.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope, Message
from aion_chat.staged_store import OperationScopedSQLiteChatStore
from aion_chat.store import HEALTHY, FAILED, SQLiteChatStore, StorageUnavailableError
import atlasquant_aion_chat_host_staging as host
import test_atlasquant_aion_chat_host_staging as original
from atlasquant_aion_chat_storage_resilience import create_verified_staging_backup

SCOPE=Scope("fixture","tenant","workspace")

class StagedFacadeLatestHardstopsLAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.session={}
        self.addCleanup(host.close_all_staged_host_stores,self.session)

    def call_other_thread(self,callback):
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(callback).result(timeout=12)

    def staged(self):
        return host.build_staged_host_binding(
            self.session,original.access(),
            config=original.config(self.root),
            environment="STAGING",
            runtime_context={"network_enabled":False,"provider_enabled":False}
        )

    def test_01_staging_host_is_connection_free_and_cross_thread_available(self):
        a=self.staged()
        self.assertIsInstance(a["store"],OperationScopedSQLiteChatStore)
        self.assertFalse(hasattr(a["store"],"db"))
        c=a["store"].create_conversation(a["scope"],"first")
        a["store"].append_message(a["scope"],Message(c.id,"user","durable"))
        b=self.call_other_thread(self.staged)
        self.assertIs(a["store"],b["store"])
        self.assertEqual(self.call_other_thread(lambda:
            b["store"].list_messages(b["scope"],c.id).items[0].content),"durable")
        self.assertFalse(b["grants_authority"])
        self.assertFalse(b["external_action_executed"])

    def test_02_low_level_native_store_still_rejects_wrong_thread(self):
        native=host.get_or_create_staged_store(
            self.session,SCOPE,self.root,session_binding_digest="native-only")
        self.assertIsInstance(native,SQLiteChatStore)
        self.assertTrue(hasattr(native,"db"))
        with self.assertRaisesRegex(StorageUnavailableError,
                                    "SQLITE_STORE_CONNECTION_THREAD_MISMATCH"):
            self.call_other_thread(lambda: native.list_conversations(SCOPE))
        self.assertEqual(native.storage_health(deep=True)["state"],HEALTHY)

    def test_03_foreign_thread_native_holder_cannot_be_discarded_by_facade_rotation(self):
        native=host.get_or_create_staged_store(
            self.session,SCOPE,self.root,session_binding_digest="same-fingerprint")
        key=host._holder_key(SCOPE)
        before=set(self.session)
        with self.assertRaisesRegex(StorageUnavailableError,
                                    "SQLITE_STORE_CONNECTION_THREAD_MISMATCH"):
            self.call_other_thread(lambda:host.get_or_create_staged_store(
                self.session,SCOPE,self.root,session_binding_digest="same-fingerprint",
                connection_free=True))
        self.assertIs(self.session[key]["store"],native)
        self.assertEqual(set(self.session),before)
        # On its own original thread, migration closes the old handle safely.
        facade=host.get_or_create_staged_store(
            self.session,SCOPE,self.root,session_binding_digest="same-fingerprint",
            connection_free=True)
        self.assertIsInstance(facade,OperationScopedSQLiteChatStore)
        self.assertIsNone(native.db)

    def test_04_connection_free_staging_does_not_expose_database_or_execution_methods(self):
        f=self.staged()["store"]
        for forbidden in ("db","execute","cursor","commit","rollback",
                          "dispatch_claimed","reconcile","claim_next",
                          "restore_from_backup"):
            with self.subTest(name=forbidden):
                self.assertFalse(hasattr(f,forbidden))
        self.assertEqual(f.storage_health(deep=True)["state"],HEALTHY)

    def test_05_backup_of_chat_only_facade_succeeds_without_changing_restore_hardstop(self):
        f=self.staged()["store"]
        c=f.create_conversation(self.staged()["scope"],"backup")
        f.append_message(self.staged()["scope"],Message(c.id,"user","fixture"))
        backup=self.root/"chat.backup.sqlite3"
        report=create_verified_staging_backup(f,backup)
        self.assertEqual(report["state"],"BACKUP_VERIFIED")
        self.assertTrue(backup.is_file())
        # A no-op attempt to restore into the SAME chat DB is forbidden as soon
        # as an execution ledger exists, even though the backup is chat-only.
        native=SQLiteChatStore(f.path)
        try:
            native.db.execute(
                "CREATE TABLE IF NOT EXISTS action_outbox (id TEXT)")
            native.db.commit()
        finally:
            native.close()
        with self.assertRaisesRegex(StorageUnavailableError,
                  "P0_EXECUTION_RESTORE_REQUIRES_INDEPENDENT_WITNESS"):
            SQLiteChatStore.restore_from_backup(backup,f.path)

    def test_06_native_thread_guard_keeps_correct_thread_usable_after_denial(self):
        native=SQLiteChatStore(self.root/"raw.sqlite3")
        self.addCleanup(native.close)
        conv=native.create_conversation(SCOPE,"guard")
        with self.assertRaisesRegex(StorageUnavailableError,
                                    "SQLITE_STORE_CONNECTION_THREAD_MISMATCH"):
            self.call_other_thread(lambda:native.get_conversation(SCOPE,conv.id))
        self.assertEqual(native.get_conversation(SCOPE,conv.id).id,conv.id)
        self.assertEqual(native.storage_health()["state"],HEALTHY)

    def test_07_explicit_admin_production_and_preview_denial_unchanged(self):
        for env in ("PRODUCTION","PROD"):
            with self.subTest(env=env):
                with self.assertRaises(PermissionError):
                    host.build_staged_host_binding(
                        self.session,original.access(),
                        config=original.config(self.root),
                        environment=env,
                        runtime_context={})
        preview=original.access()
        preview["mode"]="PREVIEW"
        with self.assertRaises(PermissionError):
            host.build_staged_host_binding(
                self.session,preview,
                config=original.config(self.root),
                environment="STAGING",runtime_context={})

    def test_08_legacy_native_owner_thread_cleanup_preflight_survives_new_facade(self):
        newer=self.staged()
        native=SQLiteChatStore(self.root/"other-native.sqlite3")
        extra=Scope("other-owner","other-tenant","other-workspace")
        self.session[host._holder_key(extra)]={
            "store":native,"path":str(native.path),
            "session_binding_digest":"legacy-fingerprint"}
        # A mixture of facade and legacy native handles must not close the
        # facade before the foreign legacy handle can be safely closed.
        before=set(self.session)
        with self.assertRaisesRegex(StorageUnavailableError,
                                    "SQLITE_STORE_CONNECTION_THREAD_MISMATCH"):
            self.call_other_thread(lambda:
                host.close_all_staged_host_stores(self.session))
        self.assertEqual(set(self.session),before)
        self.assertEqual(newer["store"].storage_health()["state"],HEALTHY)
        self.assertEqual(host.close_all_staged_host_stores(self.session),2)

if __name__=="__main__":
    unittest.main()
