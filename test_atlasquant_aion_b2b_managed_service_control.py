from __future__ import annotations

import unittest

from atlasquant_aion_b2b_managed_service_control import (
    build_managed_service_contract,
    evaluate_managed_service_cycle,
)

SCOPE = {"owner_id": "owner-a", "tenant_id": "tenant-a", "workspace_id": "ws-a"}


def conversion(**overrides):
    row = {
        "state": "REVIEWABLE",
        "decision": "COMMERCIAL_REVIEW_CANDIDATE",
        "blockers": [],
        "review_reasons": [],
        "owner_commercial_approval_required": True,
        "evidence_digest": "sha256:conversion",
        "recommended_package": "PROFISSIONAL",
        "customer_id": "customer-001",
    }
    row.update(overrides)
    return row


def owner_commercial(**overrides):
    row = {
        **SCOPE,
        "state": "CONFIRMED",
        "approved_by_owner": True,
        "customer_id": "customer-001",
        "package": "PROFISSIONAL",
        "approval_ref": "owner-commercial:001",
    }
    row.update(overrides)
    return row


def spec(**overrides):
    row = {
        **SCOPE,
        "customer_id": "customer-001",
        "package": "PROFISSIONAL",
        "monthly_price_brl": 5000.0,
        "monthly_service_cost_cap_brl": 2800.0,
        "max_capacity_units": 60,
        "max_calls_per_cycle": 1000,
        "max_tokens_per_cycle": 1000000,
        "max_support_tickets_per_cycle": 40,
        "sla_first_response_hours": 4.0,
        "sla_resolution_hours": 24.0,
        "allowed_workflows": ["lead-intake", "followup-draft", "crm-update"],
        "integration_refs": ["whatsapp:v1", "crm:v1", "email:v1"],
        "allowed_roles": ["OWNER", "ADMIN", "MANAGER", "COLLABORATOR"],
        "evidence_refs": ["conversion:v1", "scope:v1", "sla:v1", "quota:v1", "rbac:v1"],
    }
    row.update(overrides)
    return row


def activation(**overrides):
    row = {
        **SCOPE,
        "state": "CONFIRMED",
        "approved_by_owner": True,
        "customer_id": "customer-001",
        "package": "PROFISSIONAL",
        "activation_ref": "owner-activation:001",
    }
    row.update(overrides)
    return row


def tenant(**overrides):
    row = {
        **SCOPE,
        "state": "PASS",
        "cross_tenant_access": False,
        "tenant_data_isolated": True,
        "security_incident": False,
        "privacy_incident": False,
        "scope_breach": False,
    }
    row.update(overrides)
    return row


def finops(**overrides):
    row = {
        **SCOPE,
        "state": "ALLOW",
        "actual_service_cost_brl": 2200.0,
    }
    row.update(overrides)
    return row


def quota(**overrides):
    row = {
        **SCOPE,
        "used_capacity_units": 40,
        "calls": 700,
        "tokens": 700000,
        "support_tickets": 20,
    }
    row.update(overrides)
    return row


def support(**overrides):
    row = {
        **SCOPE,
        "avg_first_response_hours": 2.0,
        "avg_resolution_hours": 12.0,
        "critical_open_tickets": 0,
    }
    row.update(overrides)
    return row


def health(**overrides):
    row = {
        **SCOPE,
        "health_score": 88.0,
        "observed_roi_pct": 60.0,
        "value_confirmed": True,
    }
    row.update(overrides)
    return row


class AionB2BManagedServiceControlTests(unittest.TestCase):
    def test_valid_service_contract_is_draft_for_owner_activation_only(self):
        out = build_managed_service_contract(
            trusted_scope=SCOPE,
            conversion=conversion(),
            owner_commercial_approval=owner_commercial(),
            spec=spec(),
        )
        self.assertEqual(out["state"], "DRAFT_FOR_OWNER_ACTIVATION")
        self.assertEqual(out["activation_state"], "BLOCKED_UNTIL_OWNER_ACTIVATION")
        self.assertFalse(out["blockers"])
        self.assertTrue(out["owner_activation_required"])
        self.assertFalse(out["automatic_activation"])
        self.assertFalse(out["executes_action"])

    def test_conversion_must_be_clean_and_reviewable(self):
        out = build_managed_service_contract(
            trusted_scope=SCOPE,
            conversion=conversion(state="COMMERCIAL_HOLD", decision="REPRICE_OR_RESCOPE_REVIEW"),
            owner_commercial_approval=owner_commercial(),
            spec=spec(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("CONVERSION_NOT_REVIEWABLE", out["blockers"])
        self.assertIn("CONVERSION_NOT_COMMERCIAL_REVIEW_CANDIDATE", out["blockers"])

    def test_owner_commercial_approval_is_mandatory(self):
        out = build_managed_service_contract(
            trusted_scope=SCOPE,
            conversion=conversion(),
            owner_commercial_approval=owner_commercial(state="PENDING", approved_by_owner=False),
            spec=spec(),
        )
        self.assertIn("COMMERCIAL_OWNER_APPROVAL_NOT_CONFIRMED", out["blockers"])
        self.assertIn("COMMERCIAL_OWNER_APPROVAL_REQUIRED", out["blockers"])

    def test_scope_and_package_mismatch_fail_closed(self):
        out = build_managed_service_contract(
            trusted_scope=SCOPE,
            conversion=conversion(),
            owner_commercial_approval=owner_commercial(),
            spec=spec(tenant_id="tenant-b", package="COMPLETO"),
        )
        self.assertIn("SERVICE_SPEC_SCOPE_MISMATCH", out["blockers"])
        self.assertIn("SERVICE_SPEC_PACKAGE_MISMATCH", out["blockers"])

    def test_cost_cap_must_preserve_positive_margin(self):
        out = build_managed_service_contract(
            trusted_scope=SCOPE,
            conversion=conversion(),
            owner_commercial_approval=owner_commercial(),
            spec=spec(monthly_price_brl=5000.0, monthly_service_cost_cap_brl=5000.0),
        )
        self.assertIn("SERVICE_COST_CAP_ERASES_MARGIN", out["blockers"])

    def test_rbac_and_workflow_bounds_are_required(self):
        out = build_managed_service_contract(
            trusted_scope=SCOPE,
            conversion=conversion(),
            owner_commercial_approval=owner_commercial(),
            spec=spec(allowed_roles=["OWNER", "ADMIN"], allowed_workflows=[]),
        )
        self.assertIn("RBAC_ROLE_SET_INCOMPLETE", out["blockers"])
        self.assertIn("ALLOWED_WORKFLOW_REQUIRED", out["blockers"])

    def test_healthy_cycle_becomes_renewal_review_candidate_only(self):
        contract = build_managed_service_contract(
            trusted_scope=SCOPE,
            conversion=conversion(),
            owner_commercial_approval=owner_commercial(),
            spec=spec(),
        )
        out = evaluate_managed_service_cycle(
            contract,
            owner_activation_attestation=activation(),
            tenant_evidence=tenant(),
            finops_evidence=finops(),
            quota_evidence=quota(),
            support_evidence=support(),
            customer_health_evidence=health(),
        )
        self.assertEqual(out["state"], "HEALTHY")
        self.assertEqual(out["decision"], "RENEWAL_REVIEW_CANDIDATE")
        self.assertTrue(out["owner_review_required"])
        self.assertFalse(out["automatic_renewal"])

    def test_tenant_isolation_failure_blocks_cycle(self):
        contract = build_managed_service_contract(
            trusted_scope=SCOPE,
            conversion=conversion(),
            owner_commercial_approval=owner_commercial(),
            spec=spec(),
        )
        out = evaluate_managed_service_cycle(
            contract,
            owner_activation_attestation=activation(),
            tenant_evidence=tenant(state="BLOCKED", cross_tenant_access=True),
            finops_evidence=finops(),
            quota_evidence=quota(),
            support_evidence=support(),
            customer_health_evidence=health(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("TENANT_ISOLATION_NOT_PASS", out["blockers"])
        self.assertIn("CROSS_TENANT_ACCESS_UNSAFE", out["blockers"])

    def test_service_cost_cap_is_enforced(self):
        contract = build_managed_service_contract(
            trusted_scope=SCOPE,
            conversion=conversion(),
            owner_commercial_approval=owner_commercial(),
            spec=spec(monthly_service_cost_cap_brl=2500.0),
        )
        out = evaluate_managed_service_cycle(
            contract,
            owner_activation_attestation=activation(),
            tenant_evidence=tenant(),
            finops_evidence=finops(actual_service_cost_brl=2600.0),
            quota_evidence=quota(),
            support_evidence=support(),
            customer_health_evidence=health(),
        )
        self.assertIn("SERVICE_COST_CAP_EXCEEDED", out["blockers"])

    def test_quota_overage_causes_capacity_hold(self):
        contract = build_managed_service_contract(
            trusted_scope=SCOPE,
            conversion=conversion(),
            owner_commercial_approval=owner_commercial(),
            spec=spec(),
        )
        out = evaluate_managed_service_cycle(
            contract,
            owner_activation_attestation=activation(),
            tenant_evidence=tenant(),
            finops_evidence=finops(),
            quota_evidence=quota(used_capacity_units=61),
            support_evidence=support(),
            customer_health_evidence=health(),
        )
        self.assertEqual(out["state"], "CAPACITY_HOLD")
        self.assertEqual(out["decision"], "CAPACITY_REVIEW")
        self.assertIn("CAPACITY_QUOTA_EXCEEDED", out["review_reasons"])
        self.assertFalse(out["automatic_quota_increase"])

    def test_sla_miss_causes_remediation_review(self):
        contract = build_managed_service_contract(
            trusted_scope=SCOPE,
            conversion=conversion(),
            owner_commercial_approval=owner_commercial(),
            spec=spec(),
        )
        out = evaluate_managed_service_cycle(
            contract,
            owner_activation_attestation=activation(),
            tenant_evidence=tenant(),
            finops_evidence=finops(),
            quota_evidence=quota(),
            support_evidence=support(avg_first_response_hours=6.0),
            customer_health_evidence=health(),
        )
        self.assertEqual(out["state"], "REMEDIATION")
        self.assertEqual(out["decision"], "REMEDIATE_REVIEW")
        self.assertIn("FIRST_RESPONSE_SLA_MISSED", out["review_reasons"])

    def test_low_health_or_negative_value_causes_remediation_review(self):
        contract = build_managed_service_contract(
            trusted_scope=SCOPE,
            conversion=conversion(),
            owner_commercial_approval=owner_commercial(),
            spec=spec(),
        )
        out = evaluate_managed_service_cycle(
            contract,
            owner_activation_attestation=activation(),
            tenant_evidence=tenant(),
            finops_evidence=finops(),
            quota_evidence=quota(),
            support_evidence=support(),
            customer_health_evidence=health(health_score=55.0, observed_roi_pct=-10.0),
        )
        self.assertEqual(out["decision"], "REMEDIATE_REVIEW")
        self.assertIn("CUSTOMER_HEALTH_BELOW_TARGET", out["review_reasons"])
        self.assertIn("CUSTOMER_VALUE_NEGATIVE", out["review_reasons"])

    def test_security_privacy_or_scope_incident_forces_incident_review(self):
        contract = build_managed_service_contract(
            trusted_scope=SCOPE,
            conversion=conversion(),
            owner_commercial_approval=owner_commercial(),
            spec=spec(),
        )
        for field, reason in (
            ("security_incident", "TENANT_SECURITY_INCIDENT"),
            ("privacy_incident", "TENANT_PRIVACY_INCIDENT"),
            ("scope_breach", "TENANT_SCOPE_BREACH"),
        ):
            with self.subTest(field=field):
                out = evaluate_managed_service_cycle(
                    contract,
                    owner_activation_attestation=activation(),
                    tenant_evidence=tenant(**{field: True}),
                    finops_evidence=finops(),
                    quota_evidence=quota(),
                    support_evidence=support(),
                    customer_health_evidence=health(),
                )
                self.assertEqual(out["state"], "INCIDENT_REVIEW")
                self.assertEqual(out["decision"], "INCIDENT_REVIEW")
                self.assertIn(reason, out["incident_reasons"])
                self.assertFalse(out["automatic_pause"])
                self.assertFalse(out["automatic_termination"])

    def test_no_external_authority_is_granted(self):
        contract = build_managed_service_contract(
            trusted_scope=SCOPE,
            conversion=conversion(),
            owner_commercial_approval=owner_commercial(),
            spec=spec(),
        )
        for key in (
            "automatic_activation",
            "automatic_contract_signature",
            "automatic_billing",
            "automatic_provisioning",
            "automatic_integration_enablement",
            "automatic_role_grant",
            "automatic_deploy",
            "production_mutation",
            "executes_action",
        ):
            self.assertFalse(contract[key], key)

        cycle = evaluate_managed_service_cycle(
            contract,
            owner_activation_attestation=activation(),
            tenant_evidence=tenant(),
            finops_evidence=finops(),
            quota_evidence=quota(),
            support_evidence=support(),
            customer_health_evidence=health(),
        )
        for key in (
            "automatic_renewal",
            "automatic_pause",
            "automatic_termination",
            "automatic_billing",
            "automatic_quota_increase",
            "automatic_role_change",
            "automatic_integration_change",
            "automatic_customer_contact",
            "automatic_deploy",
            "production_mutation",
            "executes_action",
        ):
            self.assertFalse(cycle[key], key)


if __name__ == "__main__":
    unittest.main()
