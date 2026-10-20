"""AION P0 STAGING: require fail-closed local-only runtime claims.

Independent candidate based on diagnostic #1352. The earlier observed
positive provider/network/production flags MUST now be rejected *before*
get_or_create_staged_store. This is NOT a real producer, identity or
external no-effect fence; all tests are offline/ephemeral, NO-GO.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

import atlasquant_aion_chat_host_staging as host
import test_atlasquant_aion_chat_host_staging as fixture
from aion_chat.store import HEALTHY


class StagingRuntimeFlagDenyLAB(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.session={}
        self.addCleanup(host.close_all_staged_host_stores,self.session)

    def bind(self,ctx):
        return host.build_staged_host_binding(
            self.session,fixture.access(),config=fixture.config(self.root),
            environment="STAGING",runtime_context=ctx)

    def assert_rejected_before_db_open(self,ctx,exc=PermissionError):
        with patch.object(host,"get_or_create_staged_store",
                          side_effect=AssertionError("no SQLite open before denial")):
            with self.assertRaises(exc):
                self.bind(ctx)
        self.assertEqual(self.session,{})
        self.assertEqual(list(self.root.iterdir()),[])

    def test_01_explicit_false_flags_are_accepted(self):
        r=self.bind({"provider_enabled":False,"network_enabled":False,
                     "production_persistence":False,"lab_reference":"safe"})
        self.assertEqual(r["state"],"STAGED_BOUND")
        self.assertEqual(r["runtime_context"]["lab_reference"],"safe")
        self.assertFalse(r["grants_authority"])
        self.assertFalse(r["external_action_executed"])

    def test_02_none_uses_default_local_only_runtime(self):
        r=self.bind(None)
        for flag in ("provider_enabled","network_enabled","production_persistence"):
            self.assertIs(r["runtime_context"][flag],False)
        self.assertIs(r["production_store_activated"],False)

    def test_03_provider_enabled_true_denied_without_db_creation(self):
        self.assert_rejected_before_db_open({"provider_enabled":True})

    def test_04_network_enabled_true_denied_without_db_creation(self):
        self.assert_rejected_before_db_open({"network_enabled":True})

    def test_05_production_persistence_true_denied_without_db_creation(self):
        self.assert_rejected_before_db_open({"production_persistence":True})

    def test_06_multiple_forbidden_true_flags_denied(self):
        self.assert_rejected_before_db_open({
            "provider_enabled":True,"network_enabled":True,
            "production_persistence":True})

    def test_07_false_strings_and_numeric_bools_do_not_silently_authorize(self):
        for value in ("false","0",0,1,None,{},[],object()):
            with self.subTest(type=type(value).__name__,repr=repr(value)[:30]):
                self.assert_rejected_before_db_open({"provider_enabled":value})

    def test_08_non_mapping_context_no_longer_falls_back_to_default(self):
        for x in ([],(),True,"", "STAGING"):
            with self.subTest(value=str(x)):
                self.assert_rejected_before_db_open(x,TypeError)

    def test_09_foreign_metadata_retained_but_not_authoritative(self):
        r=self.bind({"claim":"untrusted","checkpoint_id":"synthetic","provider_enabled":False})
        self.assertEqual(r["runtime_context"]["claim"],"untrusted")
        self.assertIs(r["provider_called"],False)
        self.assertIs(r["network_called"],False)
        self.assertIs(r["external_action_executed"],False)

    def test_10_denied_positive_runtime_cannot_detach_existing_good_handle(self):
        first=self.bind({"network_enabled":False})
        key=host._holder_key(first["scope"])
        with self.assertRaisesRegex(PermissionError,
                                    "STAGED_RUNTIME_FORBIDDEN_FLAG:network_enabled"):
            self.bind({"network_enabled":True})
        self.assertIs(self.session[key]["store"],first["store"])
        self.assertEqual(first["store"].storage_health()["state"],HEALTHY)

    def test_11_runtime_context_bad_user_mode_rejected_before_storage(self):
        for role,mode in (("USER","AUTHENTICATED"),("ADMIN","PREVIEW")):
            with self.subTest(role=role,mode=mode):
                acc=fixture.access()
                acc["role"]=role
                acc["session"]["role"]=role
                acc["mode"]=mode
                with patch.object(host,"get_or_create_staged_store",
                                  side_effect=AssertionError("no SQLite")):
                    with self.assertRaises(PermissionError):
                        host.build_staged_host_binding(self.session,acc,
                            config=fixture.config(self.root),
                            environment="STAGING",
                            runtime_context={"provider_enabled":False})

    def test_12_no_unsafe_flags_required_for_normal_cross_thread_binding(self):
        import concurrent.futures
        r=self.bind({"provider_enabled":False,"network_enabled":False})
        c=r["store"].create_conversation(r["scope"],"only in LAB")
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            f=ex.submit(lambda:self.bind({"provider_enabled":False,"network_enabled":False}))
            other=f.result(timeout=10)
            self.assertIs(other["store"],r["store"])
            self.assertEqual(ex.submit(lambda:
                other["store"].get_conversation(other["scope"],c.id).title
                ).result(timeout=10),"only in LAB")
        self.assertFalse(other["grants_authority"])

if __name__=="__main__":
    unittest.main()
