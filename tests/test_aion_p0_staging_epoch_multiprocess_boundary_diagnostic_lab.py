"""AION P0 negative LAB audit of STAGING security boundary in #1350.

PASS in tests 01/02/03/04/05 documents INCOMPLETE AUTHORITY, not readiness.
A local RLock and a dict holding hashes never authenticates revocation epochs,
cannot revoke per-process or cross-session references, and cannot prevent
injecting an optimistic runtime_context unless separately checked.

No provider, customer data, worker, network API or real credentials used.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from unittest.mock import patch
import os
import subprocess
import sys
import tempfile
import unittest

from aion_chat.store import HEALTHY, FAILED
import atlasquant_aion_chat_host_staging as host
import test_atlasquant_aion_chat_host_staging as fixture


class STAGINGTrustEpochAndProcessDiagnosticLAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.session={}
        self.addCleanup(host.close_all_staged_host_stores,self.session)

    def access(self,fp="fp-old",timestamp=10):
        x=fixture.access()
        x["session"]["username"]="fictional-admin"
        x["session"]["credential_fingerprint"]=fp
        x["session"]["authenticated_at"]=timestamp
        x["session"]["last_seen"]=timestamp
        return x

    def bind(self,access=None,session=None,runtime=None):
        return host.build_staged_host_binding(
            self.session if session is None else session,
            self.access() if access is None else access,
            config=fixture.config(self.root),environment="STAGING",
            runtime_context=runtime if runtime is not None else {
                "provider_enabled":False,"network_enabled":False,
                "production_persistence":False})

    def test_01_stale_claim_can_rebind_after_new_fingerprint(self):
        old=self.bind(self.access("credential-epoch-old",5))
        current=self.bind(self.access("credential-epoch-new",100))
        self.assertEqual(old["store"].storage_health()["state"],FAILED)
        self.assertEqual(current["store"].storage_health()["state"],HEALTHY)
        replay=self.bind(self.access("credential-epoch-old",5))
        # Green here means a replay of an unverified credential claim was
        # accepted; THIS IS A REMAINING GAP, not an authorization success.
        self.assertEqual(replay["store"].storage_health()["state"],HEALTHY)
        self.assertEqual(current["store"].storage_health()["state"],FAILED)
        self.assertEqual(replay["session_binding_digest"],old["session_binding_digest"])
        self.assertIs(replay["grants_authority"],False)

    def test_02_fictional_claim_with_ancient_authentication_time_is_accepted(self):
        binding=self.bind(self.access("ancient-self-asserted",1))
        self.assertEqual(binding["state"],"STAGED_BOUND")
        self.assertIs(binding["production_store_activated"],False)
        self.assertIs(binding["external_action_executed"],False)

    def test_03_logout_in_another_session_dict_cannot_revoke_handle(self):
        second={}
        self.addCleanup(host.close_all_staged_host_stores,second)
        a=self.bind(self.access("same-claim",20))
        b=self.bind(self.access("same-claim",20),session=second)
        self.assertIsNot(a["store"],b["store"])
        self.assertEqual(host.close_all_staged_host_stores(self.session),1)
        self.assertEqual(a["store"].storage_health()["state"],FAILED)
        self.assertEqual(b["store"].storage_health()["state"],HEALTHY)
        self.assertIs(b["grants_authority"],False)

    def test_04_fresh_process_retains_local_handle_after_parent_session_logout(self):
        # Process isolation: child opens a real second STAGING handle to same
        # temporary SQLite path, waits for parent to logout, then reads health.
        self.bind(self.access("same-claim",20))
        script=r"""
import sys
from pathlib import Path
import atlasquant_aion_chat_host_staging as h
import test_atlasquant_aion_chat_host_staging as f
root=Path(sys.argv[1])
a=f.access()
a["session"]["username"]="fictional-admin"
a["session"]["credential_fingerprint"]="same-claim"
s={}
b=h.build_staged_host_binding(s,a,config=f.config(root),environment="STAGING",
    runtime_context={"provider_enabled":False,"network_enabled":False})
sys.stdin.readline()
print("LIVE="+b["store"].storage_health()["state"],flush=True)
h.close_all_staged_host_stores(s)
"""
        p=subprocess.Popen([sys.executable,"-B","-c",script,str(self.root)],
            cwd=str(Path(__file__).resolve().parents[1]),
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"})
        try:
            # The child may not have opened yet; either sequence leaves each
            # Python interpreter with independent, unrevoked handle state.
            self.assertEqual(host.close_all_staged_host_stores(self.session),1)
            out,err=p.communicate(input="\n",timeout=20)
            self.assertEqual(p.returncode,0,err)
            self.assertIn("LIVE=healthy",out)
        finally:
            if p.poll() is None:
                p.kill()
                p.communicate(timeout=5)

    def test_05_global_host_mutex_serializes_unrelated_sessions(self):
        entered=Event()
        release=Event()
        native_constructor=host.OperationScopedSQLiteChatStore
        class HeldOnce(native_constructor):
            def __init__(self,path):
                entered.set()
                if not release.wait(10):
                    raise AssertionError("test mutex hold exceeded timeout")
                super().__init__(path)
        second={}
        self.addCleanup(host.close_all_staged_host_stores,second)
        with patch.object(host,"OperationScopedSQLiteChatStore",HeldOnce):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first=pool.submit(self.bind,self.access("one",50))
                self.assertTrue(entered.wait(6))
                another=pool.submit(self.bind,self.access("two",50),second)
                try:
                    # Coarse global lock prevents unrelated session from binding.
                    self.assertFalse(another.done(),"global mutex serialized unrelated sessions")
                finally:
                    release.set()
                x=first.result(timeout=15)
                y=another.result(timeout=15)
        self.assertEqual(x["store"].storage_health()["state"],HEALTHY)
        self.assertEqual(y["store"].storage_health()["state"],HEALTHY)

    def test_06_external_effect_flags_stay_false_despite_untrusted_claim(self):
        b=self.bind(self.access("fp-any",1))
        for key in ("provider_called","network_called","external_action_executed",
                    "grants_authority","production_store_activated"):
            self.assertIs(b[key],False)

    def test_07_runtime_context_positive_provider_claim_passes_through_unchecked(self):
        b=self.bind(runtime={"provider_enabled":True,
                             "network_enabled":True,
                             "production_persistence":True})
        self.assertIs(b["runtime_context"]["provider_enabled"],True)
        self.assertIs(b["runtime_context"]["network_enabled"],True)
        self.assertIs(b["runtime_context"]["production_persistence"],True)
        # Not evidence that any effect occurred; it is inconsistent metadata.
        self.assertIs(b["provider_called"],False)
        self.assertIs(b["network_called"],False)
        self.assertIs(b["external_action_executed"],False)

if __name__=="__main__":
    unittest.main()
