"""Normative LAB security contracts: STAGING holder swap must be serialized.

Derived from RED diagnostic in review branch, but written as affirmative
safe invariants; two racing callers must not leave concurrently live scopes
or leave usable references after a completed credential change.

Tests use real current host and native SQLite in temporary dirs; no network,
worker, provider, customer data, production credentials or deployment.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from unittest.mock import patch
import tempfile
import unittest

from aion_chat.models import Message, Scope
from aion_chat.staged_store import OperationScopedSQLiteChatStore
from aion_chat.store import HEALTHY, FAILED, SQLiteChatStore, StorageUnavailableError
import atlasquant_aion_chat_host_staging as host
import test_atlasquant_aion_chat_host_staging as fixture


class SessionAtomicityCandidateLAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.session={}
        self.addCleanup(host.close_all_staged_host_stores,self.session)
        self._all_handles=[]

    def identity(self,name="lab-a",fingerprint="fp-a"):
        d=fixture.access()
        d["session"]["username"]=name
        d["session"]["credential_fingerprint"]=fingerprint
        return d

    def binding(self,access):
        b=host.build_staged_host_binding(
            self.session, access, config=fixture.config(self.root),
            environment="STAGING",
            runtime_context={"provider_enabled":False, "network_enabled":False})
        self._all_handles.append(b["store"])
        return b

    def racers(self,*accesses):
        gate=Barrier(len(accesses),timeout=12)
        def one(value):
            gate.wait()
            return self.binding(value)
        with ThreadPoolExecutor(max_workers=len(accesses)) as pool:
            return list(pool.map(one,accesses,timeout=20))

    def assert_single_active_and_revoked(self,outputs,may_be_empty=False):
        keys=[k for k in self.session if str(k).startswith(host._STORE_PREFIX)]
        self.assertLessEqual(len(keys),1,"two live session holders survived transition")
        active=self.session.get(host._ACTIVE_SCOPE_KEY)
        if not may_be_empty:
            self.assertEqual(len(keys),1)
            self.assertEqual(keys,[active])
            live=self.session[keys[0]]["store"]
            self.assertIsInstance(live,OperationScopedSQLiteChatStore)
            self.assertEqual(live.storage_health()["state"],HEALTHY)
        else:
            self.assertEqual(bool(keys),bool(active))
            live=self.session[keys[0]]["store"] if keys else None
        for row in outputs:
            h=row["store"]
            self.assertEqual(h.storage_health()["state"],
                             HEALTHY if h is live else FAILED)
            self.assertFalse(row["grants_authority"])
            self.assertFalse(row["external_action_executed"])

    def test_01_simultaneous_distinct_principals_revoke_all_non_active(self):
        outputs=self.racers(self.identity("alice","fp-a"),self.identity("bob","fp-b"))
        self.assertNotEqual(outputs[0]["scope"],outputs[1]["scope"])
        self.assert_single_active_and_revoked(outputs)

    def test_02_simultaneous_fingerprint_rotation_has_no_orphan_live_handle(self):
        outputs=self.racers(self.identity("alice","fp-old"),
                            self.identity("alice","fp-new"))
        self.assertEqual(outputs[0]["scope"],outputs[1]["scope"])
        self.assertNotEqual(outputs[0]["session_binding_digest"],
                            outputs[1]["session_binding_digest"])
        self.assert_single_active_and_revoked(outputs)

    def test_03_eight_racing_identity_and_fingerprint_changes_have_one_live_holder(self):
        participants=[self.identity("alice" if i%2 else "bob",
                                    f"fp-version-{i}") for i in range(8)]
        outputs=self.racers(*participants)
        self.assertEqual(len({id(x["store"]) for x in outputs}),8)
        self.assert_single_active_and_revoked(outputs)

    def test_04_parallel_logout_and_new_binding_never_orphan_session_holder(self):
        original=self.binding(self.identity("alice","original"))
        gate=Barrier(2,timeout=12)
        def rebind():
            gate.wait()
            return self.binding(self.identity("alice","rotated"))
        def logout():
            gate.wait()
            return host.close_all_staged_host_stores(self.session)
        with ThreadPoolExecutor(max_workers=2) as pool:
            f1=pool.submit(rebind)
            f2=pool.submit(logout)
            newer=f1.result(timeout=20)
            closed=f2.result(timeout=20)
        self.assertIn(closed,(0,1))
        self.assert_single_active_and_revoked([original,newer],may_be_empty=True)

    def test_05_legacy_native_wrong_thread_denial_does_not_mutate_holder(self):
        scope=Scope("native-owner","tenant-a","workspace-a")
        n=host.get_or_create_staged_store(self.session,scope,self.root,
                                           session_binding_digest="native")
        self.assertIsInstance(n,SQLiteChatStore)
        before=dict(self.session)
        def foreign():
            return host.get_or_create_staged_store(self.session,scope,self.root,
                session_binding_digest="different",
                connection_free=True)
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.assertRaisesRegex(StorageUnavailableError,
                                         "SQLITE_STORE_CONNECTION_THREAD_MISMATCH"):
                pool.submit(foreign).result(timeout=12)
        self.assertEqual(self.session,before)
        self.assertEqual(n.storage_health()["state"],HEALTHY)

    def test_06_inflight_operation_finishes_before_holder_revocation(self):
        first=self.binding(self.identity("alice","old"))
        scope=first["scope"]
        conversation=first["store"].create_conversation(scope,"read ongoing")
        reached=Event()
        finish=Event()
        original_get=SQLiteChatStore.get_conversation
        def paused(native,*args,**kwargs):
            reached.set()
            if not finish.wait(8):
                raise AssertionError("test did not release paused read")
            return original_get(native,*args,**kwargs)
        with patch.object(SQLiteChatStore,"get_conversation",paused):
            with ThreadPoolExecutor(max_workers=2) as pool:
                read=pool.submit(first["store"].get_conversation,scope,conversation.id)
                self.assertTrue(reached.wait(6))
                rotate=pool.submit(self.binding,self.identity("alice","new"))
                try:
                    self.assertFalse(rotate.done(),
                                      "revocation cannot finish while an operation owns handle lock")
                finally:
                    finish.set()
                self.assertEqual(read.result(timeout=12).id,conversation.id)
                next_binding=rotate.result(timeout=12)
        self.assertEqual(first["store"].storage_health()["state"],FAILED)
        self.assertEqual(next_binding["store"].storage_health()["state"],HEALTHY)

    def test_07_new_identity_cannot_read_other_owner_history(self):
        a=self.binding(self.identity("alice","fp-a"))
        c=a["store"].create_conversation(a["scope"],"alice only")
        b=self.binding(self.identity("bob","fp-b"))
        with self.assertRaises(StorageUnavailableError):
            a["store"].get_conversation(a["scope"],c.id)
        with self.assertRaises(LookupError):
            b["store"].get_conversation(b["scope"],c.id)
        self.assert_single_active_and_revoked([a,b])

    def test_08_native_thread_checks_not_disabled_by_session_serialization(self):
        store=SQLiteChatStore(self.root/"native.sqlite3")
        self.addCleanup(store.close)
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.assertRaisesRegex(StorageUnavailableError,
                                         "SQLITE_STORE_CONNECTION_THREAD_MISMATCH"):
                pool.submit(store.list_conversations,Scope("x","y","z")).result(timeout=12)
        self.assertEqual(store.storage_health()["state"],HEALTHY)

    def test_09_no_lock_or_credential_is_inserted_into_streamlit_session(self):
        binding=self.binding(self.identity("alice","fake-fingerprint"))
        self.assertEqual(len([k for k in self.session if str(k).startswith(host._STORE_PREFIX)]),1)
        self.assertNotIn("RLock",repr(self.session))
        self.assertFalse(any("LOCK" in str(k).upper() for k in self.session))
        self.assertNotIn("fake-fingerprint",repr(self.session))
        self.assertFalse(binding["provider_called"])

    def test_10_production_and_unprivileged_access_always_denied(self):
        for env in ("PRODUCTION","PROD"):
            with self.subTest(env=env):
                with self.assertRaises(PermissionError):
                    host.build_staged_host_binding(
                        self.session,self.identity(),config=fixture.config(self.root),
                        environment=env,runtime_context={})
        denied=self.identity()
        denied["role"]="USER"
        with self.assertRaises(PermissionError):
            host.build_staged_host_binding(
                self.session,denied,config=fixture.config(self.root),
                environment="STAGING",runtime_context={})

    def test_11_no_external_execution_or_worker_entry_exposed(self):
        b=self.binding(self.identity())
        for key in ("provider_called","network_called","external_action_executed",
                    "production_store_activated","grants_authority"):
            self.assertIs(b[key],False)
        for forbidden in ("db","dispatch_claimed","claim_next","execute","rollback"):
            self.assertFalse(hasattr(b["store"],forbidden))

    def test_12_closed_holder_never_revives_on_next_access(self):
        b=self.binding(self.identity())
        handle=b["store"]
        self.assertEqual(host.close_all_staged_host_stores(self.session),1)
        self.assertEqual(handle.storage_health()["state"],FAILED)
        with self.assertRaises(StorageUnavailableError):
            handle.list_conversations(b["scope"])
        renewed=self.binding(self.identity())
        self.assertIsNot(renewed["store"],handle)
        self.assertEqual(handle.storage_health()["state"],FAILED)


if __name__=="__main__":
    unittest.main()
