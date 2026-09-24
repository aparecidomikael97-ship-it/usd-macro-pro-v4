import unittest
from datetime import datetime, timezone

from atlasquant_aion_entitlements import (
    approve_entitlement_request,
    entitlement_activation_preflight,
    entitlement_effective,
    entitlement_summary,
    mark_entitlement_from_provider_evidence,
    new_entitlement_request,
    normalize_entitlement,
    upsert_entitlement,
)
from atlasquant_aion_tenant import (
    PERSONAL_SCOPE,
    cross_tenant_access_allowed,
    personal_aion_eligibility,
    sanitize_tenant_memory,
    tenant_action_decision,
    tenant_memory_seed,
    tenant_namespace,
    tenant_policy_snapshot,
    tenant_prompt_contract,
)
from atlasquant_aion_tenant_store import (
    accept_loaded_memory,
    prepare_tenant_load,
    prepare_tenant_write,
    resolve_write_conflict,
    tenant_memory_change_summary,
    tenant_memory_payload,
    tenant_store_policy,
    tenant_store_target,
)


class AtlasQuantAionEntitlementsTests(unittest.TestCase):
    def setUp(self):
        self.admin={"role":"ADMIN","username":"admin.test"}

    def test_new_request_is_draft_and_never_changes_account_or_role(self):
        item=new_entitlement_request(
            "cliente.01",
            scope="APP_ACCESS",
            source_kind="MANUAL_GRANT",
            note="cortesia futura",
        )
        self.assertEqual(item["status"],"DRAFT")
        self.assertFalse(item["approval"]["approved"])
        self.assertFalse(item["provider_evidence"]["confirmed"])
        self.assertFalse(item["effects"]["account_registry_changed"])
        self.assertFalse(item["effects"]["role_changed"])
        self.assertFalse(item["effects"]["payment_executed"])
        self.assertFalse(item["effects"]["trading_permission_changed"])

    def test_approval_requires_admin_and_does_not_activate(self):
        item=new_entitlement_request("cliente.01")
        with self.assertRaises(PermissionError):
            approve_entitlement_request(item,{"role":"USER"})
        approved=approve_entitlement_request(item,self.admin)
        self.assertEqual(approved["status"],"APPROVED")
        self.assertTrue(approved["approval"]["approved"])
        self.assertFalse(entitlement_effective(approved)["effective"])

    def test_activation_preflight_is_double_locked_and_non_executing(self):
        item=approve_entitlement_request(new_entitlement_request("cliente.01"),self.admin)
        no_flag=entitlement_activation_preflight(
            item,self.admin,
            feature_flags={"entitlement_activation":False},
            approved=True,
        )
        self.assertFalse(no_flag["allowed"])
        no_click=entitlement_activation_preflight(
            item,self.admin,
            feature_flags={"entitlement_activation":True},
            approved=False,
        )
        self.assertFalse(no_click["allowed"])
        ready=entitlement_activation_preflight(
            item,self.admin,
            feature_flags={"entitlement_activation":True},
            approved=True,
        )
        self.assertTrue(ready["allowed"])
        self.assertFalse(ready["executes_entitlement"])
        self.assertFalse(ready["changes_account_registry"])
        self.assertFalse(ready["changes_role"])

    def test_confirmed_active_state_requires_provider_evidence(self):
        approved=approve_entitlement_request(new_entitlement_request("cliente.01"),self.admin)
        with self.assertRaises(ValueError):
            mark_entitlement_from_provider_evidence(
                approved,
                {"confirmed":True,"provider":"billing"},
            )
        active=mark_entitlement_from_provider_evidence(
            approved,
            {
                "confirmed":True,
                "provider":"subscription_registry",
                "external_id":"ent-123",
                "event_id":"evt-456",
            },
        )
        self.assertEqual(active["status"],"ACTIVE_CONFIRMED")
        self.assertTrue(active["provider_evidence"]["confirmed"])
        self.assertTrue(entitlement_effective(active)["effective"])

    def test_normalization_downgrades_unproven_active_claim(self):
        item=new_entitlement_request("cliente.01")
        item["status"]="ACTIVE_CONFIRMED"
        normalized=normalize_entitlement(item)
        self.assertEqual(normalized["status"],"DRAFT")
        item=approve_entitlement_request(item,self.admin)
        item["status"]="ACTIVE_CONFIRMED"
        normalized=normalize_entitlement(item)
        self.assertEqual(normalized["status"],"APPROVED")

    def test_window_blocks_future_and_expired_effective_access(self):
        item=new_entitlement_request(
            "cliente.01",
            starts_at="2026-10-01T00:00:00+00:00",
            expires_at="2026-10-31T00:00:00+00:00",
        )
        item=approve_entitlement_request(item,self.admin)
        item=mark_entitlement_from_provider_evidence(
            item,
            {"confirmed":True,"provider":"registry","external_id":"x-1"},
        )
        before=entitlement_effective(
            item,now=datetime(2026,9,30,tzinfo=timezone.utc),
        )
        self.assertFalse(before["effective"])
        self.assertIn("NOT_STARTED",before["reasons"])
        during=entitlement_effective(
            item,now=datetime(2026,10,15,tzinfo=timezone.utc),
        )
        self.assertTrue(during["effective"])
        after=entitlement_effective(
            item,now=datetime(2026,11,1,tzinfo=timezone.utc),
        )
        self.assertFalse(after["effective"])
        self.assertIn("EXPIRED",after["reasons"])

    def test_summary_and_upsert(self):
        a=new_entitlement_request("cliente.01",created_at="2026-09-24T12:00:00Z")
        b=new_entitlement_request("cliente.02",created_at="2026-09-24T12:01:00Z")
        b=approve_entitlement_request(b,self.admin)
        rows=upsert_entitlement([],a)
        rows=upsert_entitlement(rows,b)
        summary=entitlement_summary(rows)
        self.assertEqual(summary["records"],2)
        self.assertEqual(summary["approved"],1)
        self.assertEqual(summary["active_confirmed"],0)


class AtlasQuantAionTenantIsolationContractTests(unittest.TestCase):
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

    def _confirmed_personal(self, username="cliente.01"):
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

    def test_login_alone_never_grants_personal_aion(self):
        result=personal_aion_eligibility(self.user,[])
        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"],"AION_PERSONAL_ENTITLEMENT_REQUIRED")
        self.assertFalse(result["admin_memory_access"])
        self.assertFalse(result["other_tenant_access"])

    def test_confirmed_matching_entitlement_grants_only_personal_eligibility(self):
        result=personal_aion_eligibility(self.user,[self._confirmed_personal()])
        self.assertTrue(result["eligible"])
        self.assertFalse(result["provider_enabled"])
        self.assertFalse(result["real_trading_enabled"])

    def test_cross_user_entitlement_and_cross_tenant_memory_are_blocked(self):
        self.assertFalse(
            personal_aion_eligibility(
                self.user,[self._confirmed_personal("cliente.02")]
            )["eligible"]
        )
        own=tenant_namespace(self.user)["tenant_id"]
        other=tenant_namespace(self.other)["tenant_id"]
        self.assertTrue(cross_tenant_access_allowed(self.user,own))
        self.assertFalse(cross_tenant_access_allowed(self.user,other))

    def test_credential_rotation_changes_namespace(self):
        first=tenant_namespace(self.user)["tenant_id"]
        rotated={
            "session":{
                "username":"cliente.01",
                "role":"USER",
                "credential_fingerprint":"d"*24,
            }
        }
        second=tenant_namespace(rotated)["tenant_id"]
        self.assertNotEqual(first,second)

    def test_foreign_memory_is_discarded_not_merged(self):
        foreign=tenant_memory_seed(self.other)
        foreign["profile"]["display_name"]="Outro Cliente"
        foreign["conversation_notes"]=[{"text":"segredo estrangeiro","truth_state":"CONFIRMED"}]
        sanitized=sanitize_tenant_memory(foreign,self.user)
        self.assertEqual(sanitized["tenant_id"],tenant_namespace(self.user)["tenant_id"])
        self.assertEqual(sanitized["profile"]["display_name"],"")
        self.assertEqual(sanitized["conversation_notes"],[])

    def test_admin_financial_external_and_real_trade_actions_are_denied(self):
        ent=self._confirmed_personal()
        self.assertTrue(
            tenant_action_decision("academy_help",self.user,[ent])["allowed"]
        )
        for action in (
            "read_admin_memory","read_other_tenant","manage_users",
            "approve_cost","charge_customer","deploy_production","real_trade",
        ):
            self.assertFalse(
                tenant_action_decision(action,self.user,[ent])["allowed"]
            )

    def test_policy_and_prompt_contract_are_fail_closed(self):
        policy=tenant_policy_snapshot()
        self.assertEqual(policy["personal_scope"],"AION_PERSONAL")
        self.assertFalse(policy["admin_memory_inherited"])
        self.assertFalse(policy["project_docs_inherited"])
        self.assertFalse(policy["cross_tenant_access"])
        self.assertFalse(policy["external_provider_enabled_by_default"])
        self.assertFalse(policy["billing_enabled"])
        self.assertFalse(policy["real_trading_enabled"])
        contract=tenant_prompt_contract(self.user)
        joined=" ".join(contract["system_rules"]).lower()
        self.assertIn("aion admin",joined)
        self.assertIn("outro tenant",joined)
        self.assertIn("trading real",joined)


class AtlasQuantAionTenantStoreContractTests(unittest.TestCase):
    def setUp(self):
        self.user={
            "session":{
                "username":"cliente.01",
                "role":"USER",
                "credential_fingerprint":"a"*24,
            },
            "role":"USER",
        }
        request=new_entitlement_request(
            "cliente.01",
            scope=PERSONAL_SCOPE,
            source_kind="MANUAL_GRANT",
            created_at="2026-09-24T12:00:00Z",
        )
        request=approve_entitlement_request(
            request,
            {"role":"ADMIN","username":"admin"},
        )
        self.entitlement=mark_entitlement_from_provider_evidence(
            request,
            {"confirmed":True,"provider":"subscription_registry","external_id":"aion-tenant-1"},
        )

    def test_store_target_rejects_code_branch_and_uses_tenant_path(self):
        blocked=tenant_store_target(self.user,runtime_branch="main")
        self.assertFalse(blocked["ready"])
        self.assertEqual(blocked["reason"],"UNSAFE_RUNTIME_BRANCH")
        ready=tenant_store_target(self.user,runtime_branch="atlasquant-runtime")
        self.assertTrue(ready["ready"])
        self.assertTrue(ready["path"].startswith("dados/aion/tenants/"))
        self.assertTrue(ready["path"].endswith("/checkpoint.json"))

    def test_load_requires_confirmed_personal_entitlement(self):
        blocked=prepare_tenant_load(self.user,[])
        self.assertFalse(blocked["allowed"])
        self.assertFalse(blocked["executes_network"])
        ready=prepare_tenant_load(self.user,[self.entitlement])
        self.assertTrue(ready["allowed"])
        self.assertFalse(ready["executes_read"])
        self.assertFalse(ready["admin_memory_fallback"])
        self.assertFalse(ready["other_tenant_fallback"])

    def test_write_requires_explicit_approval_and_never_executes_network(self):
        memory=tenant_memory_seed(self.user)
        blocked=prepare_tenant_write(
            self.user,[self.entitlement],memory,approved=False,
        )
        self.assertFalse(blocked["allowed"])
        self.assertEqual(blocked["reason"],"EXPLICIT_WRITE_APPROVAL_REQUIRED")
        ready=prepare_tenant_write(
            self.user,[self.entitlement],memory,approved=True,
            expected_revision="abc123",
        )
        self.assertTrue(ready["allowed"])
        self.assertFalse(ready["executes_network"])
        self.assertFalse(ready["executes_write"])
        self.assertEqual(ready["expected_revision"],"abc123")
        self.assertFalse(ready["account_registry_changed"])
        self.assertFalse(ready["role_changed"])
        self.assertFalse(ready["billing_changed"])
        self.assertFalse(ready["real_trading_changed"])

    def test_foreign_memory_is_rejected_before_write_plan(self):
        other={
            "session":{
                "username":"cliente.02",
                "role":"USER",
                "credential_fingerprint":"b"*24,
            }
        }
        foreign=tenant_memory_seed(other)
        result=prepare_tenant_write(
            self.user,[self.entitlement],foreign,approved=True,
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"],"FOREIGN_TENANT_MEMORY_REJECTED")

    def test_loaded_memory_requires_explicit_matching_tenant_id(self):
        missing=accept_loaded_memory(
            self.user,[self.entitlement],{"profile":{}},
        )
        self.assertFalse(missing["accepted"])
        self.assertEqual(missing["reason"],"TENANT_ID_MISSING")

        other={
            "session":{
                "username":"cliente.02",
                "role":"USER",
                "credential_fingerprint":"b"*24,
            }
        }
        foreign=accept_loaded_memory(
            self.user,[self.entitlement],tenant_memory_seed(other),
        )
        self.assertFalse(foreign["accepted"])
        self.assertEqual(foreign["reason"],"FOREIGN_TENANT_MEMORY_REJECTED")

        own=tenant_memory_seed(self.user)
        own["profile"]["display_name"]="Cliente Um"
        accepted=accept_loaded_memory(
            self.user,[self.entitlement],own,
        )
        self.assertTrue(accepted["accepted"])
        self.assertEqual(
            accepted["memory"]["tenant_id"],
            tenant_namespace(self.user)["tenant_id"],
        )

    def test_revision_conflict_never_auto_overwrites(self):
        ok=resolve_write_conflict(expected_revision="sha-1",current_revision="sha-1")
        self.assertTrue(ok["can_write"])
        self.assertFalse(ok["automatic_overwrite"])
        conflict=resolve_write_conflict(expected_revision="sha-1",current_revision="sha-2")
        self.assertFalse(conflict["can_write"])
        self.assertEqual(conflict["reason"],"REVISION_CONFLICT")
        self.assertTrue(conflict["requires_reload"])
        self.assertFalse(conflict["automatic_overwrite"])

    def test_change_summary_flags_foreign_memory_without_merging_it(self):
        own=tenant_memory_seed(self.user)
        own["watchlist"]=["EURUSD"]
        other={
            "session":{
                "username":"cliente.02",
                "role":"USER",
                "credential_fingerprint":"b"*24,
            }
        }
        foreign=tenant_memory_seed(other)
        summary=tenant_memory_change_summary(own,foreign,self.user)
        self.assertTrue(summary["contains_other_tenant_memory"])
        self.assertFalse(summary["contains_admin_memory"])

    def test_store_policy_is_offline_and_fail_closed(self):
        policy=tenant_store_policy()
        self.assertFalse(policy["network_io_implemented"])
        self.assertFalse(policy["automatic_write"])
        self.assertFalse(policy["automatic_overwrite"])
        self.assertTrue(policy["explicit_write_approval_required"])
        self.assertTrue(policy["confirmed_entitlement_required"])
        self.assertFalse(policy["code_branch_write_allowed"])
        self.assertFalse(policy["admin_memory_fallback"])
        self.assertFalse(policy["other_tenant_fallback"])

    def test_payload_is_tenant_bound_and_bounded(self):
        memory=tenant_memory_seed(self.user)
        memory["profile"]["display_name"]="Cliente Um"
        payload=tenant_memory_payload(memory,self.user)
        self.assertEqual(
            payload["tenant_id"],
            tenant_namespace(self.user)["tenant_id"],
        )
        self.assertFalse(payload["privacy"]["admin_memory_inherited"])
        self.assertFalse(payload["privacy"]["other_tenant_memory_visible"])


if __name__=="__main__":
    unittest.main()
