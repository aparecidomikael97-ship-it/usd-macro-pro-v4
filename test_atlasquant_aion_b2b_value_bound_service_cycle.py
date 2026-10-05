from __future__ import annotations

import unittest

from atlasquant_aion_b2b_value_bound_managed_service import SCHEMA as SERVICE_SCHEMA
from atlasquant_aion_b2b_value_bound_service_cycle import (
    SCHEMA,
    evaluate_value_bound_service_cycle,
)

SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "tenant-a",
    "workspace_id": "workspace-a",
}


def service(**overrides):
    contract = {
        **SCOPE,
        "customer_id": "customer-a",
        "package": "PROFISSIONAL",
        "monthly_price_brl": 5000.0,
        "monthly_service_cost_cap_brl": 2800.0,
        "max_capacity_units": 60,
        "max_calls_per_cycle": 1000,
        "max_tokens_per_cycle": 1000000,
        "max_support_tickets_per_cycle": 40,
        "sla_first_response_hours": 4.0,
        "sla_resolution_hours": 24.0,
        "allowed_workflows": ["lead-intake", "followup-draft"],
        "integration_refs": ["crm:v1"],
        "allowed_roles": ["OWNER", "ADMIN", "MANAGER", "COLLABORATOR"],
        "evidence_refs": ["e1", "e2", "e3", "e4", "e5"],
        "conversion_evidence_digest": "sha256:conversion-compat",
        "owner_commercial_approval_ref": "owner-commercial:001",
    }
    contract.update(overrides.pop("contract", {}))
    row = {
        "schema": SERVICE_SCHEMA,
        "state": "DRAFT_FOR_OWNER_ACTIVATION",
        "activation_state": "BLOCKED_UNTIL_OWNER_ACTIVATION",
        "contract": contract,
        "blockers": [],
        "contract_digest": "sha256:contract",
        "owner_activation_required": True,
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "package": "PROFISSIONAL",
        "value_bound_conversion_digest": "sha256:value-bound",
        "source_value_decision": "EXPANSION_REVIEW_CANDIDATE",
        "source_conversion_decision": "EXPANSION_COMMERCIAL_REVIEW_CANDIDATE",
        "automatic_activation": False,
        "automatic_contract_signature": False,
        "automatic_billing": False,
        "automatic_provisioning": False,
        "automatic_integration_enablement": False,
        "automatic_role_grant": False,
        "automatic_customer_contact": False,
        "automatic_renewal": False,
        "automatic_deploy": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def activation(**overrides):
    row = {
        **SCOPE,
        "state": "CONFIRMED",
        "approved_by_owner": True,
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "package": "PROFISSIONAL",
        "activation_ref": "owner-activation:001",
    }
    row.update(overrides)
    return row


def tenant(**overrides):
    row = {
        **SCOPE,
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
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
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "state": "ALLOW",
        "actual_service_cost_brl": 2200.0,
    }
    row.update(overrides)
    return row


def quota(**overrides):
    row = {
        **SCOPE,
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
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
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "avg_first_response_hours": 2.0,
        "avg_resolution_hours": 12.0,
        "critical_open_tickets": 0,
    }
    row.update(overrides)
    return row


def health(**overrides):
    row = {
        **SCOPE,
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "health_score": 88.0,
        "observed_roi_pct": 60.0,
        "value_confirmed": True,
    }
    row.update(overrides)
    return row


def evaluate(**changes):
    inputs = {
        "trusted_scope": SCOPE,
        "value_bound_service": service(),
        "owner_activation_attestation": activation(),
        "tenant_evidence": tenant(),
        "finops_evidence": finops(),
        "quota_evidence": quota(),
        "support_evidence": support(),
        "customer_health_evidence": health(),
    }
    inputs.update(changes)
    return evaluate_value_bound_service_cycle(**inputs)


class ValueBoundServiceCycleTests(unittest.TestCase):
    def test_healthy_cycle_is_renewal_review_candidate_only(self):
        out = evaluate()
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "HEALTHY")
        self.assertEqual(out["decision"], "RENEWAL_REVIEW_CANDIDATE")
        self.assertEqual(out["customer_id"], "customer-a")
        self.assertEqual(out["pilot_id"], "pilot-a")
        self.assertEqual(out["package"], "PROFISSIONAL")
        self.assertTrue(out["owner_review_required"])
        self.assertFalse(out["customer_visible"])
        self.assertTrue(out["contains_internal_finops"])
        self.assertTrue(out["requires_customer_safe_projection"])
        self.assertFalse(out["automatic_renewal"])
        self.assertFalse(out["automatic_expansion"])
        self.assertEqual(
            out["source_conversion_decision"],
            "EXPANSION_COMMERCIAL_REVIEW_CANDIDATE",
        )
        self.assertEqual(
            out["source_value_decision"],
            "EXPANSION_REVIEW_CANDIDATE",
        )

    def test_quota_overage_is_capacity_review_not_auto_increase(self):
        out = evaluate(
            quota_evidence=quota(used_capacity_units=61),
        )
        self.assertEqual(out["state"], "CAPACITY_HOLD")
        self.assertEqual(out["decision"], "CAPACITY_REVIEW")
        self.assertIn("CAPACITY_QUOTA_EXCEEDED", out["review_reasons"])
        self.assertFalse(out["automatic_quota_increase"])

    def test_sla_miss_is_remediation_review(self):
        out = evaluate(
            support_evidence=support(avg_first_response_hours=6.0),
        )
        self.assertEqual(out["state"], "REMEDIATION")
        self.assertEqual(out["decision"], "REMEDIATE_REVIEW")
        self.assertIn("FIRST_RESPONSE_SLA_MISSED", out["review_reasons"])

    def test_incident_is_review_only(self):
        out = evaluate(
            tenant_evidence=tenant(privacy_incident=True),
        )
        self.assertEqual(out["state"], "INCIDENT_REVIEW")
        self.assertEqual(out["decision"], "INCIDENT_REVIEW")
        self.assertIn("TENANT_PRIVACY_INCIDENT", out["incident_reasons"])
        self.assertFalse(out["automatic_pause"])
        self.assertFalse(out["automatic_termination"])

    def test_source_schema_mismatch_fails_closed(self):
        out = evaluate(
            value_bound_service=service(schema="WRONG"),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("VALUE_BOUND_SERVICE_SCHEMA_INVALID", out["blockers"])

    def test_source_scope_mismatch_fails_closed(self):
        row = service()
        row["contract"] = {
            **row["contract"],
            "tenant_id": "tenant-other",
        }
        out = evaluate(value_bound_service=row)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("VALUE_BOUND_SERVICE_SCOPE_MISMATCH", out["blockers"])

    def test_source_customer_contract_mismatch_fails_closed(self):
        out = evaluate(
            value_bound_service=service(customer_id="customer-other"),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "VALUE_BOUND_CUSTOMER_CONTRACT_MISMATCH",
            out["blockers"],
        )

    def test_unsafe_source_flag_fails_closed(self):
        out = evaluate(
            value_bound_service=service(automatic_billing=True),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "VALUE_BOUND_UNSAFE_FIELD:automatic_billing",
            out["blockers"],
        )

    def test_cross_customer_evidence_fails_closed(self):
        out = evaluate(
            customer_health_evidence=health(customer_id="customer-other"),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "CUSTOMER_HEALTH_EVIDENCE_CUSTOMER_MISMATCH",
            out["blockers"],
        )

    def test_cross_pilot_activation_fails_closed(self):
        out = evaluate(
            owner_activation_attestation=activation(pilot_id="pilot-other"),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "OWNER_ACTIVATION_PILOT_MISMATCH",
            out["blockers"],
        )

    def test_internal_finops_is_never_marked_customer_visible(self):
        out = evaluate()
        self.assertEqual(out["actual_service_cost_brl"], 2200.0)
        self.assertFalse(out["customer_visible"])
        self.assertTrue(out["requires_customer_safe_projection"])

    def test_no_external_authority_is_granted(self):
        out = evaluate()
        for key in (
            "automatic_renewal",
            "automatic_expansion",
            "automatic_package_change",
            "automatic_pause",
            "automatic_termination",
            "automatic_billing",
            "automatic_quota_increase",
            "automatic_role_change",
            "automatic_integration_change",
            "automatic_customer_contact",
            "automatic_provisioning",
            "automatic_deploy",
            "provider_called",
            "production_mutation",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
