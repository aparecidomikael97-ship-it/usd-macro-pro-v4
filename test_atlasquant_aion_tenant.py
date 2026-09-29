import unittest
from datetime import datetime, timezone

from atlasquant_aion_entitlements import (
    approve_entitlement_request,
    mark_entitlement_from_provider_evidence,
    new_entitlement_request,
)
from atlasquant_aion_tenant import (
    PERSONAL_SCOPE,
    sanitize_tenant_memory,
    tenant_policy_snapshot,
    tenant_readiness_summary,
)
from atlasquant_aion_tenant_store import (
    prepare_tenant_write,
    tenant_store_target,
)


class AtlasQuantAionTenantReadinessTests(unittest.TestCase):
    def setUp(self):
        self.admin={"role":"ADMIN","username":"admin.01"}
        self.user={
            "session":{
                "username":"cliente.01",
                "role":"USER",
                "credential_fingerprint":"a"*32,
            },
        }
        self.now=datetime(2026,9,24,12,0,0,tzinfo=timezone.utc)

    def _active(self,subject,*,scope=PERSONAL_SCOPE,external_id="aion-1",created_at="2026-09-24T10:00:00Z"):
        item=new_entitlement_request(
            subject,
            scope=scope,
            source_kind="MANUAL_GRANT",
            created_at=created_at,
        )
        item=approve_entitlement_request(item,self.admin)
        return mark_entitlement_from_provider_evidence(
            item,
            {
                "confirmed":True,
                "provider":"subscription_registry",
                "external_id":external_id,
            },
        )

    def test_empty_readiness_is_safe_and_non_executing(self):
        out=tenant_readiness_summary([],now=self.now)
        self.assertEqual(out["personal_entitlements"],0)
        self.assertEqual(out["effective_confirmed"],0)
        self.assertEqual(out["effective_subjects"],0)
        self.assertEqual(out["duplicate_effective_subjects"],[])
        self.assertFalse(out["subscriber_shell_enabled"])
        self.assertFalse(out["persistent_tenant_runtime_confirmed"])
        self.assertFalse(out["automatic_provisioning"])
        self.assertFalse(out["admin_memory_inherited"])
        self.assertFalse(out["project_docs_inherited"])
        self.assertFalse(out["cross_tenant_access"])
        self.assertFalse(out["external_provider_auto_enabled"])
        self.assertFalse(out["billing_auto_enabled"])
        self.assertFalse(out["real_trading_enabled"])
        self.assertTrue(out["readiness_only"])
        self.assertFalse(out["executes_action"])

    def test_confirmed_personal_entitlement_counts_as_effective_subject(self):
        item=self._active("cliente.01")
        out=tenant_readiness_summary([item],now=self.now)
        self.assertEqual(out["personal_entitlements"],1)
        self.assertEqual(out["effective_confirmed"],1)
        self.assertEqual(out["effective_subjects"],1)
        self.assertEqual(out["duplicate_effective_subjects"],[])

    def test_app_access_does_not_count_as_personal_aion(self):
        item=self._active("cliente.01",scope="APP_ACCESS")
        out=tenant_readiness_summary([item],now=self.now)
        self.assertEqual(out["personal_entitlements"],0)
        self.assertEqual(out["effective_confirmed"],0)
        self.assertEqual(out["effective_subjects"],0)

    def test_duplicate_effective_personal_entitlements_are_visible(self):
        a=self._active("cliente.01",external_id="aion-1",created_at="2026-09-24T10:00:00Z")
        b=self._active("cliente.01",external_id="aion-2",created_at="2026-09-24T10:01:00Z")
        out=tenant_readiness_summary([a,b],now=self.now)
        self.assertEqual(out["personal_entitlements"],2)
        self.assertEqual(out["effective_confirmed"],2)
        self.assertEqual(out["effective_subjects"],1)
        self.assertEqual(out["duplicate_effective_subjects"],["cliente.01"])

    def test_future_or_expired_personal_entitlement_is_not_effective(self):
        future=new_entitlement_request(
            "cliente.01",
            scope=PERSONAL_SCOPE,
            starts_at="2026-10-01T00:00:00+00:00",
            created_at="2026-09-24T09:00:00Z",
        )
        future=approve_entitlement_request(future,self.admin)
        future=mark_entitlement_from_provider_evidence(
            future,{"confirmed":True,"provider":"registry","external_id":"future-1"},
        )

        expired=new_entitlement_request(
            "cliente.02",
            scope=PERSONAL_SCOPE,
            starts_at="2026-09-01T00:00:00+00:00",
            expires_at="2026-09-20T00:00:00+00:00",
            created_at="2026-09-24T09:01:00Z",
        )
        expired=approve_entitlement_request(expired,self.admin)
        expired=mark_entitlement_from_provider_evidence(
            expired,{"confirmed":True,"provider":"registry","external_id":"expired-1"},
        )

        out=tenant_readiness_summary([future,expired],now=self.now)
        self.assertEqual(out["personal_entitlements"],2)
        self.assertEqual(out["effective_confirmed"],0)
        self.assertEqual(out["effective_subjects"],0)

    def test_policy_snapshot_keeps_admin_and_cross_tenant_isolation(self):
        policy=tenant_policy_snapshot()
        self.assertTrue(policy["requires_confirmed_entitlement"])
        self.assertFalse(policy["admin_memory_inherited"])
        self.assertFalse(policy["project_docs_inherited"])
        self.assertFalse(policy["cross_tenant_access"])
        self.assertFalse(policy["external_provider_enabled_by_default"])
        self.assertFalse(policy["billing_enabled"])
        self.assertFalse(policy["real_trading_enabled"])


    def test_tenant_memory_projection_does_not_overconsume_bounded_fields(self):
        from collections.abc import Mapping

        class GuardedMapping(Mapping):
            def __init__(self,count,limit):
                self.count=count
                self.limit=limit
                self.reads=0
            def __len__(self):
                return self.count
            def __iter__(self):
                for index in range(self.count):
                    if self.reads>=self.limit:
                        raise AssertionError("mapping consumed past bound")
                    self.reads+=1
                    yield f"k{index}"
            def __getitem__(self,key):
                return "v"

        class GuardedList(list):
            def __init__(self,limit,total, factory):
                super().__init__()
                self.limit=limit
                self.total=total
                self.factory=factory
                self.reads=0
            def __iter__(self):
                for index in range(self.total):
                    if self.reads>=self.limit:
                        raise AssertionError("sequence consumed past bound")
                    self.reads+=1
                    yield self.factory(index)

        ns_memory={
            "tenant_id":"",
        }
        from atlasquant_aion_tenant import tenant_memory_seed
        seed=tenant_memory_seed(self.user)
        prefs=GuardedMapping(51,50)
        academy=GuardedMapping(201,200)
        notes=GuardedList(200,201,lambda i:{"text":f"note {i}"})
        watchlist=GuardedList(100,101,lambda i:f"SYM{i}")
        ns_memory={
            "tenant_id":seed["tenant_id"],
            "profile":{"preferences":prefs},
            "conversation_notes":notes,
            "academy_progress":academy,
            "watchlist":watchlist,
        }
        cleaned=sanitize_tenant_memory(ns_memory,self.user)
        self.assertEqual(len(cleaned["profile"]["preferences"]),50)
        self.assertEqual(len(cleaned["conversation_notes"]),200)
        self.assertEqual(len(cleaned["academy_progress"]),200)
        self.assertEqual(len(cleaned["watchlist"]),100)
        self.assertEqual(prefs.reads,50)
        self.assertEqual(academy.reads,200)
        self.assertEqual(notes.reads,200)
        self.assertEqual(watchlist.reads,100)

    def test_tenant_write_requires_exact_boolean_true(self):
        entitlement=self._active("cliente.01")
        for flag in ("true","false","yes","1",1,1.0,False,0,None):
            with self.subTest(flag=flag):
                result=prepare_tenant_write(
                    self.user,
                    [entitlement],
                    {},
                    approved=flag,
                    now=self.now,
                )
                self.assertFalse(result["allowed"])
                self.assertEqual(
                    result["reason"],
                    "EXPLICIT_WRITE_APPROVAL_REQUIRED",
                )
                self.assertFalse(result["approved"])
                self.assertFalse(result["executes_network"])
                self.assertFalse(result["executes_write"])

        confirmed=prepare_tenant_write(
            self.user,
            [entitlement],
            {},
            approved=True,
            now=self.now,
        )
        self.assertTrue(confirmed["allowed"])
        self.assertTrue(confirmed["approved"])
        self.assertFalse(confirmed["executes_network"])
        self.assertFalse(confirmed["executes_write"])
        target=tenant_store_target(self.user)
        self.assertTrue(target["ready"])
        self.assertEqual(
            confirmed["target"]["tenant_id"],
            target["tenant_id"],
        )
        self.assertIn(
            target["tenant_id"],
            confirmed["target"]["path"],
        )

    def test_tenant_write_rejects_foreign_memory_even_with_exact_approval(self):
        entitlement=self._active("cliente.01")
        target=tenant_store_target(self.user)
        result=prepare_tenant_write(
            self.user,
            [entitlement],
            {
                "tenant_id":"f"*32,
                "profile":{"display_name":"foreign"},
            },
            approved=True,
            now=self.now,
        )
        self.assertTrue(target["ready"])
        self.assertFalse(result["allowed"])
        self.assertEqual(
            result["reason"],
            "FOREIGN_TENANT_MEMORY_REJECTED",
        )
        self.assertTrue(result["approved"])
        self.assertFalse(result["executes_write"])
        self.assertFalse(result["executes_network"])


if __name__=="__main__":
    unittest.main()
