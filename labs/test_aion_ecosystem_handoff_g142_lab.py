"""G142 LAB targeted tests: routing cannot become authority by self-declaration."""
import unittest

from labs.aion_ecosystem_handoff_g142_lab import (
    assess_handoff,
    ecosystem_contract_snapshot,
)

OWNER = "owner/private"
PERSON_A = "tenant/" + "a" * 32
PERSON_B = "tenant/" + "b" * 32
COMPANY_A = "company/acme-0001"
COMPANY_B = "company/other-0002"


class G142EcosystemHandoffLabTests(unittest.TestCase):
    def plan(self, area, scope, ns, **overrides):
        params = {
            "workspace": area,
            "principal_scope": scope,
            "principal_namespace": ns,
            "target_namespace": ns,
            "request_kind": "READ_SUMMARY",
        }
        params.update(overrides)
        return assess_handoff(**params)

    def assert_no_authority(self, out):
        for key in (
            "identity_authenticated", "tenant_acl_verified", "data_read_authorized",
            "cross_tenant_access_authorized", "owner_memory_exposed",
            "client_memory_exposed", "external_action_authorized",
            "external_action_executed", "memory_written", "provider_called",
            "billing_authorized", "worker_enabled", "real_trade_enabled",
        ):
            self.assertIs(out[key], False, key)
        self.assertTrue(out["hard_no_go"])
        self.assertEqual(out["p0_homologated"], 0)

    def test_owner_routes_trader(self):
        out = self.plan("TRADER", "OWNER_PRIVATE", OWNER)
        self.assertTrue(out["eligible_for_planning"])
        self.assertEqual(out["route_candidate"], "TRADER")
        self.assert_no_authority(out)

    def test_owner_routes_investimentos(self):
        self.assertTrue(self.plan("INVESTIMENTOS", "OWNER_PRIVATE", OWNER)["eligible_for_planning"])

    def test_owner_routes_aion(self):
        self.assertTrue(self.plan("AION", "OWNER_PRIVATE", OWNER)["eligible_for_planning"])

    def test_owner_business_is_overview_not_raw_tenant(self):
        out = self.plan("NEGOCIOS", "OWNER_PRIVATE", OWNER)
        self.assertTrue(out["eligible_for_planning"])
        self.assertEqual(out["route_candidate"], "NEGOCIOS_OWNER_OVERVIEW_ONLY")
        self.assert_no_authority(out)

    def test_owner_cannot_impersonate_business_tenant(self):
        out = self.plan("NEGOCIOS", "OWNER_PRIVATE", OWNER, target_namespace=COMPANY_A)
        self.assertFalse(out["eligible_for_planning"])
        self.assertIsNone(out["route_candidate"])
        self.assert_no_authority(out)

    def test_subscriber_routes_trader(self):
        out = self.plan("TRADER", "SUBSCRIBER_PERSONAL", PERSON_A)
        self.assertTrue(out["eligible_for_planning"])
        self.assert_no_authority(out)

    def test_subscriber_routes_investimentos(self):
        self.assertTrue(self.plan("INVESTIMENTOS", "SUBSCRIBER_PERSONAL", PERSON_A)["eligible_for_planning"])

    def test_subscriber_routes_aion(self):
        self.assertTrue(self.plan("AION", "SUBSCRIBER_PERSONAL", PERSON_A)["eligible_for_planning"])

    def test_subscriber_business_denied(self):
        out = self.plan("NEGOCIOS", "SUBSCRIBER_PERSONAL", PERSON_A)
        self.assertIn("WORKSPACE_NOT_AVAILABLE_FOR_SCOPE", out["blockers"])
        self.assert_no_authority(out)

    def test_subscriber_cannot_read_other_subscriber(self):
        out = self.plan("AION", "SUBSCRIBER_PERSONAL", PERSON_A, target_namespace=PERSON_B)
        self.assertIn("CROSS_SCOPE_OR_TENANT_HANDOFF_DENIED", out["blockers"])
        self.assert_no_authority(out)

    def test_business_tenant_can_plan_own_business_summary_only(self):
        out = self.plan("NEGOCIOS", "BUSINESS_TENANT", COMPANY_A)
        self.assertTrue(out["eligible_for_planning"])
        self.assert_no_authority(out)

    def test_business_tenant_can_plan_own_aion_help(self):
        self.assertTrue(self.plan("AION", "BUSINESS_TENANT", COMPANY_A)["eligible_for_planning"])

    def test_business_tenant_cannot_read_other_company(self):
        out = self.plan("NEGOCIOS", "BUSINESS_TENANT", COMPANY_A, target_namespace=COMPANY_B)
        self.assertIn("CROSS_SCOPE_OR_TENANT_HANDOFF_DENIED", out["blockers"])

    def test_business_tenant_cannot_route_personal_trader(self):
        self.assertFalse(self.plan("TRADER", "BUSINESS_TENANT", COMPANY_A)["eligible_for_planning"])

    def test_business_tenant_cannot_route_personal_investments(self):
        self.assertFalse(self.plan("INVESTIMENTOS", "BUSINESS_TENANT", COMPANY_A)["eligible_for_planning"])

    def test_unknown_workspaces_default_deny(self):
        out = self.plan("SECRETS", "OWNER_PRIVATE", OWNER)
        self.assertIn("UNKNOWN_WORKSPACE", out["blockers"])

    def test_unknown_scope_default_deny(self):
        self.assertFalse(self.plan("AION", "GOD_MODE", OWNER)["eligible_for_planning"])

    def test_missing_namespace_default_deny(self):
        out = self.plan("AION", "SUBSCRIBER_PERSONAL", "")
        self.assertIn("UNVERIFIED_OR_INVALID_PRINCIPAL_NAMESPACE", out["blockers"])

    def test_path_injection_namespace_denied(self):
        out = self.plan("NEGOCIOS", "BUSINESS_TENANT", "company/../owner/private")
        self.assertIn("UNVERIFIED_OR_INVALID_PRINCIPAL_NAMESPACE", out["blockers"])

    def test_forged_permission_cannot_turn_into_authority(self):
        out = self.plan("AION", "OWNER_PRIVATE", OWNER, caller_claims={
            "approved": True, "verified_owner": True, "p0_homologated": 6,
        })
        self.assertIn("CALLER_SELF_ATTESTATION_NOT_AUTHORITY", out["blockers"])
        self.assert_no_authority(out)

    def test_effect_requests_always_denied(self):
        for kind in ("REAL_TRADE", "SEND_WHATSAPP", "CHARGE_CUSTOMER", "DEPLOY",
                     "WRITE_MEMORY", "APPROVE_COST", "MERGE_MAIN"):
            with self.subTest(kind=kind):
                out = self.plan("AION", "OWNER_PRIVATE", OWNER, request_kind=kind)
                self.assertIn("NON_READ_ONLY_REQUEST_HARD_NO_GO", out["blockers"])
                self.assert_no_authority(out)

    def test_allowed_plan_kinds_are_still_not_actions(self):
        for kind in ("EXPLAIN", "READ_SUMMARY", "PREPARE_DRAFT"):
            with self.subTest(kind=kind):
                out = self.plan("AION", "OWNER_PRIVATE", OWNER, request_kind=kind)
                self.assertTrue(out["eligible_for_planning"])
                self.assert_no_authority(out)

    def test_untrusted_claims_never_override_mismatch(self):
        out = self.plan("NEGOCIOS", "BUSINESS_TENANT", COMPANY_A,
                        target_namespace=COMPANY_B, caller_claims={"permit": True})
        self.assertFalse(out["eligible_for_planning"])
        self.assert_no_authority(out)

    def test_non_text_scope_namespace_or_workspace_denied(self):
        for field, value in (("workspace", {"name": "AION"}),
                             ("principal_scope", ["OWNER_PRIVATE"]),
                             ("principal_namespace", [OWNER]),
                             ("target_namespace", [OWNER])):
            with self.subTest(field=field):
                out = self.plan("AION", "OWNER_PRIVATE", OWNER, **{field: value})
                self.assertFalse(out["eligible_for_planning"])
                self.assert_no_authority(out)

    def test_snapshot_retains_four_areas_and_no_go(self):
        state = ecosystem_contract_snapshot()
        self.assertEqual(state["workspaces"], ["TRADER", "INVESTIMENTOS", "NEGOCIOS", "AION"])
        self.assertFalse(state["owner_admin_memory_shared_with_clients"])
        self.assertFalse(state["subscriber_business_data_access"])
        self.assertFalse(state["business_tenant_private_trader_access"])
        self.assertTrue(state["hard_no_go"])
        self.assertEqual(state["p0_homologated"], 0)


if __name__ == "__main__":
    unittest.main()
