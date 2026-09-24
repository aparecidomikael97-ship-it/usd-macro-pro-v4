import unittest
from datetime import datetime, timezone

from atlasquant_aion_entitlements import (
    approve_entitlement_request,
    mark_entitlement_from_provider_evidence,
    new_entitlement_request,
)
from atlasquant_aion_tenant import (
    PERSONAL_SCOPE,
    cross_tenant_access_allowed,
    personal_aion_eligibility,
    sanitize_tenant_memory,
    tenant_action_decision,
    tenant_domain_allowed,
    tenant_memory_seed,
    tenant_namespace,
    tenant_policy_snapshot,
    tenant_prompt_contract,
    tenant_runtime_path,
)


class AtlasQuantAionTenantTests(unittest.TestCase):
    def setUp(self):
        self.user={
            "session":{
                "username":"cliente.01",
                "role":"USER",
                "credential_fingerprint":"a"*24,
            },
            "role":"USER",
        }
        self.other={
            "session":{
                "username":"cliente.02",
                "role":"USER",
                "credential_fingerprint":"b"*24,
            },
            "role":"USER",
        }
        self.admin={"role":"ADMIN","username":"admin","credential_fingerprint":"c"*24}

    def _confirmed_entitlement(self, username="cliente.01"):
        item=new_entitlement_request(
            username,
            scope=PERSONAL_SCOPE,
            source_kind="MANUAL_GRANT",
            created_at="2026-09-24T12:00:00Z",
        )
        item=approve_entitlement_request(item,{"role":"ADMIN","username":"admin"})
        return mark_entitlement_from_provider_evidence(
            item,
            {"confirmed":True,"provider":"subscription_registry","external_id":"aion-1"},
        )

    def test_namespace_requires_authenticated_user_or_sales_not_admin(self):
        ns=tenant_namespace(self.user)
        self.assertTrue(ns["ready"])
        self.assertEqual(len(ns["tenant_id"]),32)
        self.assertTrue(ns["namespace"].startswith("tenant/"))
        self.assertTrue(tenant_runtime_path(self.user).startswith("dados/aion/tenants/"))
        self.assertFalse(tenant_namespace(self.admin)["ready"])

    def test_credential_rotation_changes_namespace_to_prevent_stale_memory_reuse(self):
        a=tenant_namespace(self.user)
        rotated={
            "session":{
                "username":"cliente.01",
                "role":"USER",
                "credential_fingerprint":"d"*24,
            }
        }
        b=tenant_namespace(rotated)
        self.assertNotEqual(a["tenant_id"],b["tenant_id"])

    def test_login_alone_does_not_grant_personal_aion(self):
        result=personal_aion_eligibility(self.user,[])
        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"],"AION_PERSONAL_ENTITLEMENT_REQUIRED")
        self.assertFalse(result["admin_memory_access"])
        self.assertFalse(result["other_tenant_access"])

    def test_confirmed_matching_entitlement_grants_eligibility_only(self):
        ent=self._confirmed_entitlement()
        result=personal_aion_eligibility(
            self.user,[ent],now=datetime(2026,9,24,tzinfo=timezone.utc)
        )
        self.assertTrue(result["eligible"])
        self.assertFalse(result["provider_enabled"])
        self.assertFalse(result["real_trading_enabled"])

    def test_entitlement_for_other_user_does_not_cross_grant(self):
        ent=self._confirmed_entitlement("cliente.02")
        self.assertFalse(personal_aion_eligibility(self.user,[ent])["eligible"])

    def test_expired_or_unconfirmed_entitlement_does_not_grant(self):
        draft=new_entitlement_request(
            "cliente.01",
            scope=PERSONAL_SCOPE,
            expires_at="2026-09-10T00:00:00+00:00",
        )
        self.assertFalse(
            personal_aion_eligibility(
                self.user,[draft],now=datetime(2026,9,24,tzinfo=timezone.utc)
            )["eligible"]
        )
        confirmed=self._confirmed_entitlement()
        confirmed["window"]["expires_at"]="2026-09-10T00:00:00+00:00"
        self.assertFalse(
            personal_aion_eligibility(
                self.user,[confirmed],now=datetime(2026,9,24,tzinfo=timezone.utc)
            )["eligible"]
        )

    def test_tenant_actions_remain_local_and_forbidden_admin_actions_are_denied(self):
        ent=self._confirmed_entitlement()
        allowed=tenant_action_decision("academy_help",self.user,[ent])
        self.assertTrue(allowed["allowed"])
        self.assertFalse(allowed["executes_external_action"])
        for action in (
            "read_admin_memory","manage_users","charge_customer",
            "deploy_production","real_trade",
        ):
            self.assertFalse(
                tenant_action_decision(action,self.user,[ent])["allowed"]
            )

    def test_domains_are_small_and_do_not_include_admin_workspaces(self):
        self.assertTrue(tenant_domain_allowed("central"))
        self.assertTrue(tenant_domain_allowed("trading"))
        self.assertFalse(tenant_domain_allowed("development"))
        self.assertFalse(tenant_domain_allowed("promotions"))

    def test_memory_seed_never_inherits_admin_or_project_memory(self):
        seed=tenant_memory_seed(self.user)
        self.assertFalse(seed["privacy"]["admin_memory_inherited"])
        self.assertFalse(seed["privacy"]["project_docs_inherited"])
        self.assertFalse(seed["privacy"]["other_tenant_memory_visible"])
        self.assertFalse(seed["permissions"]["admin"])
        self.assertFalse(seed["permissions"]["billing"])
        self.assertFalse(seed["permissions"]["real_trading"])

    def test_sanitizer_rejects_foreign_tenant_memory(self):
        own=tenant_memory_seed(self.user)
        own["profile"]["display_name"]="Cliente Um"
        own["conversation_notes"]=[{"text":"prefiro explicações simples","truth_state":"CONFIRMED"}]
        kept=sanitize_tenant_memory(own,self.user)
        self.assertEqual(kept["profile"]["display_name"],"Cliente Um")
        self.assertEqual(len(kept["conversation_notes"]),1)

        foreign=tenant_memory_seed(self.other)
        foreign["profile"]["display_name"]="Outro Cliente"
        sanitized=sanitize_tenant_memory(foreign,self.user)
        self.assertEqual(sanitized["tenant_id"],tenant_namespace(self.user)["tenant_id"])
        self.assertEqual(sanitized["profile"]["display_name"],"")
        self.assertEqual(sanitized["conversation_notes"],[])

    def test_cross_tenant_access_is_same_tenant_only(self):
        own=tenant_namespace(self.user)["tenant_id"]
        other=tenant_namespace(self.other)["tenant_id"]
        self.assertTrue(cross_tenant_access_allowed(self.user,own))
        self.assertFalse(cross_tenant_access_allowed(self.user,other))

    def test_policy_snapshot_keeps_personal_aion_fail_closed(self):
        policy=tenant_policy_snapshot()
        self.assertEqual(policy["personal_scope"],"AION_PERSONAL")
        self.assertFalse(policy["admin_memory_inherited"])
        self.assertFalse(policy["project_docs_inherited"])
        self.assertFalse(policy["cross_tenant_access"])
        self.assertFalse(policy["external_provider_enabled_by_default"])
        self.assertFalse(policy["billing_enabled"])
        self.assertFalse(policy["real_trading_enabled"])
        self.assertTrue(policy["requires_confirmed_entitlement"])
        self.assertTrue(policy["credential_bound_namespace"])

    def test_prompt_contract_explicitly_denies_admin_other_tenant_and_real_trade(self):
        contract=tenant_prompt_contract(self.user)
        self.assertTrue(contract["ready"])
        self.assertFalse(contract["admin_memory_access"])
        self.assertFalse(contract["other_tenant_access"])
        self.assertFalse(contract["external_provider_enabled_by_default"])
        self.assertFalse(contract["real_trading_enabled"])
        joined=" ".join(contract["system_rules"]).lower()
        self.assertIn("aion admin",joined)
        self.assertIn("outro tenant",joined)
        self.assertIn("trading real",joined)


if __name__=="__main__":
    unittest.main()
