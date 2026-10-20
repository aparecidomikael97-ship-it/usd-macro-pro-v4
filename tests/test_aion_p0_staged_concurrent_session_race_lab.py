"""P0 LAB diagnostic: deterministic concurrent STAGING host binding races.

These PASS tests demonstrate a real session revocation GAP in the unpatched
candidate #1348. They do NOT certify safety. All identities are fictional,
SQLite stores are ephemeral; no provider, production actions or worker.
When reviewed/fixed, these exact observations must be converted to NEGATIVE
safety assertions on an independent candidate, never waived.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Lock
from unittest.mock import patch
import tempfile
import unittest

from aion_chat.staged_store import OperationScopedSQLiteChatStore
from aion_chat.store import HEALTHY
import atlasquant_aion_chat_host_staging as host
import test_atlasquant_aion_chat_host_staging as fixture


class SessionRaceDiagnosticLAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.session={}
        self.addCleanup(host.close_all_staged_host_stores,self.session)

    def identity(self,name="fixture-owner",fingerprint="fp-a"):
        d=fixture.access()
        d["session"]["username"]=name
        d["session"]["credential_fingerprint"]=fingerprint
        return d

    def concurrent(self,*credentials):
        gate=Barrier(2,timeout=12)
        initialize_one_at_a_time=Lock()
        class ForcedOverlap(OperationScopedSQLiteChatStore):
            def __init__(self,path):
                # The test isolates SESSION mutation interleaving, avoiding
                # concurrent CREATE TABLE on the same freshly initialized DB.
                with initialize_one_at_a_time:
                    super().__init__(path)
                gate.wait()
        def worker(cred):
            return host.build_staged_host_binding(
                self.session,cred,config=fixture.config(self.root),
                environment="STAGING",
                runtime_context={"network_enabled":False,"provider_enabled":False}
            )
        with patch.object(host,"OperationScopedSQLiteChatStore",ForcedOverlap):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(worker,c) for c in credentials]
                return [f.result(timeout=20) for f in futures]

    def test_01_two_simultaneous_different_principals_leave_two_live_scopes(self):
        a,b=self.concurrent(self.identity("fixture-a","fp-a"),
                            self.identity("fixture-b","fp-b"))
        self.assertNotEqual(a["scope"],b["scope"])
        holders=[(k,v) for k,v in self.session.items()
                 if str(k).startswith(host._STORE_PREFIX)]
        self.assertEqual(len(holders),2,
                         "Diagnostic gap exists: simultaneous scope switch skipped preflight")
        self.assertEqual(a["store"].storage_health()["state"],HEALTHY)
        self.assertEqual(b["store"].storage_health()["state"],HEALTHY)
        self.assertIn(self.session[host._ACTIVE_SCOPE_KEY],
                      {host._holder_key(a["scope"]),host._holder_key(b["scope"])})
        self.assertIs(a["grants_authority"],False)
        self.assertIs(b["grants_authority"],False)

    def test_02_same_principal_concurrent_fingerprint_change_orphans_live_handle(self):
        a,b=self.concurrent(self.identity("fixture-a","fp-old"),
                            self.identity("fixture-a","fp-rotated"))
        key=host._holder_key(a["scope"])
        self.assertEqual(a["scope"],b["scope"])
        self.assertNotEqual(a["session_binding_digest"],b["session_binding_digest"])
        self.assertEqual(len([k for k in self.session if k.startswith(host._STORE_PREFIX)]),1)
        self.assertIn(self.session[key]["store"],(a["store"],b["store"]))
        orphan=a["store"] if self.session[key]["store"] is b["store"] else b["store"]
        self.assertEqual(orphan.storage_health()["state"],HEALTHY,
                         "Diagnostic gap: rotated credential holder is still usable")
        # No external side-effect. Ensure orphan is explicitly revoked in test.
        orphan.close()

    def test_03_without_forced_race_sequential_credential_rotation_revokes(self):
        old=host.build_staged_host_binding(
            self.session,self.identity("fixture-a","fp-old"),
            config=fixture.config(self.root),environment="STAGING",
            runtime_context={})
        new=host.build_staged_host_binding(
            self.session,self.identity("fixture-a","fp-new"),
            config=fixture.config(self.root),environment="STAGING",
            runtime_context={})
        self.assertIsNot(old["store"],new["store"])
        self.assertEqual(old["store"].storage_health()["state"],"failed")
        self.assertEqual(new["store"].storage_health()["state"],HEALTHY)

    def test_04_no_execution_gates_are_present_in_staging_binding(self):
        output=host.build_staged_host_binding(
            self.session,self.identity(),config=fixture.config(self.root),
            environment="STAGING",runtime_context={})
        for flag in ("provider_called","network_called","external_action_executed",
                     "production_store_activated","grants_authority"):
            self.assertIs(output[flag],False)


if __name__=="__main__":
    unittest.main()
