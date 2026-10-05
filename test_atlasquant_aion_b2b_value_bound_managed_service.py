import unittest

from atlasquant_aion_b2b_value_bound_managed_service import (
    SCHEMA,
    VALUE_BOUND_CONVERSION_SCHEMA,
    build_value_bound_managed_service_contract,
)


SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "tenant-a",
    "workspace_id": "workspace-a",
}


def gate_row(**changes):
    row = {
        "schema": VALUE_BOUND_CONVERSION_SCHEMA,
        "state": "REVIEWABLE",
        "decision": "EXPANSION_COMMERCIAL_REVIEW_CANDIDATE",
        "scope": dict(SCOPE),
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "recommended_package": "PROFISSIONAL",
        "value_recommendation": "EXPANSION_REVIEW_CANDIDATE",
        "blockers": [],
        "evidence_digest": "sha256:value-bound",
        "owner_commercial_approval_required": True,
        "owner_review_required": True,
        "automatic_conversion": False,
        "automatic_expansion": False,
        "automatic_package_change": False,
        "automatic_pricing_change": False,
        "automatic_contract": False,
        "automatic_billing": False,
        "automatic_provisioning": False,
        "automatic_customer_contact": False,
        "automatic_renewal": False,
        "automatic_deploy": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }
    row.update(changes)
    return row


def approval_row(**changes):
    row = {
        **SCOPE,
        "state": "CONFIRMED",
        "approved_by_owner": True,
        "customer_id": "customer-a",
        "package": "PROFISSIONAL",
        "approval_ref": "owner:commercial:approval",
    }
    row.update(changes)
    return row


def spec_row(**changes):
    row = {
        **SCOPE,
        "customer_id": "customer-a",
        "package": "PROFISSIONAL",
        "monthly_price_brl": 1500.0,
        "monthly_service_cost_cap_brl": 450.0,
        "max_capacity_units": 50,
        "max_calls_per_cycle": 10000,
        "max_tokens_per_cycle": 1000000,
        "max_support_tickets_per_cycle": 20,
        "sla_first_response_hours": 4.0,
        "sla_resolution_hours": 24.0,
        "allowed_workflows": ["lead-qualification", "follow-up"],
        "integration_refs": ["integration:crm"],
        "allowed_roles": ["OWNER", "ADMIN", "MANAGER", "COLLABORATOR"],
        "evidence_refs": [
            "evidence:1",
            "evidence:2",
            "evidence:3",
            "evidence:4",
            "evidence:5",
        ],
    }
    row.update(changes)
    return row


class ValueBoundManagedServiceTests(unittest.TestCase):
    def test_reviewable_gate_builds_activation_blocked_service_draft(self):
        result = build_value_bound_managed_service_contract(
            trusted_scope=SCOPE,
            value_bound_conversion=gate_row(),
            owner_commercial_approval=approval_row(),
            spec=spec_row(),
        )
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["state"], "DRAFT_FOR_OWNER_ACTIVATION")
        self.assertEqual(
            result["activation_state"],
            "BLOCKED_UNTIL_OWNER_ACTIVATION",
        )
        self.assertEqual(result["customer_id"], "customer-a")
        self.assertEqual(result["pilot_id"], "pilot-a")
        self.assertEqual(result["package"], "PROFISSIONAL")
        self.assertEqual(
            result["value_bound_conversion_digest"],
            "sha256:value-bound",
        )
        self.assertTrue(result["owner_activation_required"])
        self.assertFalse(result["automatic_activation"])
        self.assertFalse(result["automatic_billing"])
        self.assertFalse(result["automatic_provisioning"])
        self.assertFalse(result["automatic_customer_contact"])
        self.assertFalse(result["automatic_renewal"])
        self.assertFalse(result["automatic_deploy"])
        self.assertFalse(result["provider_called"])
        self.assertFalse(result["production_mutation"])
        self.assertFalse(result["executes_action"])

    def test_continue_candidate_is_also_eligible(self):
        result = build_value_bound_managed_service_contract(
            trusted_scope=SCOPE,
            value_bound_conversion=gate_row(
                decision="CONTINUE_COMMERCIAL_REVIEW_CANDIDATE",
                value_recommendation="CONTINUE_REVIEW_CANDIDATE",
            ),
            owner_commercial_approval=approval_row(),
            spec=spec_row(),
        )
        self.assertEqual(result["state"], "DRAFT_FOR_OWNER_ACTIVATION")

    def test_scope_mismatch_fails_closed(self):
        gate = gate_row()
        gate["scope"] = {**SCOPE, "tenant_id": "tenant-b"}
        result = build_value_bound_managed_service_contract(
            trusted_scope=SCOPE,
            value_bound_conversion=gate,
            owner_commercial_approval=approval_row(),
            spec=spec_row(),
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "VALUE_BOUND_CONVERSION_SCOPE_MISMATCH",
            result["blockers"],
        )

    def test_non_reviewable_gate_fails_closed(self):
        result = build_value_bound_managed_service_contract(
            trusted_scope=SCOPE,
            value_bound_conversion=gate_row(
                state="BLOCKED",
                decision="BLOCKED",
            ),
            owner_commercial_approval=approval_row(),
            spec=spec_row(),
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "VALUE_BOUND_CONVERSION_NOT_REVIEWABLE",
            result["blockers"],
        )

    def test_unsafe_gate_fails_closed(self):
        result = build_value_bound_managed_service_contract(
            trusted_scope=SCOPE,
            value_bound_conversion=gate_row(automatic_billing=True),
            owner_commercial_approval=approval_row(),
            spec=spec_row(),
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "VALUE_BOUND_UNSAFE_FIELD:automatic_billing",
            result["blockers"],
        )

    def test_owner_approval_customer_mismatch_stays_blocked(self):
        result = build_value_bound_managed_service_contract(
            trusted_scope=SCOPE,
            value_bound_conversion=gate_row(),
            owner_commercial_approval=approval_row(
                customer_id="customer-other",
            ),
            spec=spec_row(),
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "COMMERCIAL_OWNER_APPROVAL_CUSTOMER_MISMATCH",
            result["blockers"],
        )

    def test_service_spec_package_mismatch_stays_blocked(self):
        result = build_value_bound_managed_service_contract(
            trusted_scope=SCOPE,
            value_bound_conversion=gate_row(),
            owner_commercial_approval=approval_row(),
            spec=spec_row(package="COMPLETO"),
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("SERVICE_SPEC_PACKAGE_MISMATCH", result["blockers"])


if __name__ == "__main__":
    unittest.main()
