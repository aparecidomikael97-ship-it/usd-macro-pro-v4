from __future__ import annotations

import unittest

from atlasquant_aion_b2b_owner_renewal_review import (
    SCHEMA,
    build_owner_renewal_review_packet,
)
from atlasquant_aion_b2b_value_bound_service_cycle import (
    SCHEMA as SERVICE_CYCLE_SCHEMA,
)

SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "tenant-a",
    "workspace_id": "workspace-a",
}


def cycle(**overrides):
    row = {
        "schema": SERVICE_CYCLE_SCHEMA,
        "state": "HEALTHY",
        "decision": "RENEWAL_REVIEW_CANDIDATE",
        "scope": dict(SCOPE),
        **SCOPE,
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "package": "PROFISSIONAL",
        "health_score": 88.0,
        "observed_roi_pct": 60.0,
        "actual_service_cost_brl": 2200.0,
        "review_reasons": [],
        "incident_reasons": [],
        "blockers": [],
        "contract_digest": "sha256:contract",
        "value_bound_conversion_digest": "sha256:value-bound",
        "source_cycle_evidence_digest": "sha256:cycle-source",
        "evidence_digest": "sha256:cycle",
        "owner_review_required": True,
        "customer_visible": False,
        "contains_internal_finops": True,
        "requires_customer_safe_projection": True,
        "source_value_decision": "EXPANSION_REVIEW_CANDIDATE",
        "source_conversion_decision": "EXPANSION_COMMERCIAL_REVIEW_CANDIDATE",
        "automatic_renewal": False,
        "automatic_expansion": False,
        "automatic_package_change": False,
        "automatic_pause": False,
        "automatic_termination": False,
        "automatic_billing": False,
        "automatic_quota_increase": False,
        "automatic_role_change": False,
        "automatic_integration_change": False,
        "automatic_customer_contact": False,
        "automatic_provisioning": False,
        "automatic_deploy": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


class OwnerRenewalReviewTests(unittest.TestCase):
    def test_healthy_cycle_becomes_owner_review_only(self):
        out = build_owner_renewal_review_packet(
            trusted_scope=SCOPE,
            service_cycle=cycle(),
        )
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "REVIEWABLE")
        self.assertEqual(out["decision"], "OWNER_REVIEW_REQUIRED")
        self.assertEqual(out["review_type"], "RENEWAL_REVIEW")
        self.assertIn("RENEW_AS_IS_REVIEW", out["allowed_owner_choices"])
        self.assertTrue(out["expansion_review_candidate"])
        self.assertFalse(out["continuation_review_candidate"])
        self.assertTrue(out["owner_decision_required"])
        self.assertTrue(out["owner_only"])
        self.assertFalse(out["customer_visible"])
        self.assertFalse(out["automatic_renewal"])
        self.assertFalse(out["automatic_expansion"])

    def test_continue_candidate_is_preserved_as_review_candidate(self):
        out = build_owner_renewal_review_packet(
            trusted_scope=SCOPE,
            service_cycle=cycle(
                source_value_decision="CONTINUE_REVIEW_CANDIDATE",
                source_conversion_decision="CONTINUE_COMMERCIAL_REVIEW_CANDIDATE",
            ),
        )
        self.assertEqual(out["state"], "REVIEWABLE")
        self.assertFalse(out["expansion_review_candidate"])
        self.assertTrue(out["continuation_review_candidate"])

    def test_remediation_cycle_changes_review_type_only(self):
        out = build_owner_renewal_review_packet(
            trusted_scope=SCOPE,
            service_cycle=cycle(
                state="REMEDIATION",
                decision="REMEDIATE_REVIEW",
                review_reasons=["FIRST_RESPONSE_SLA_MISSED"],
            ),
        )
        self.assertEqual(out["review_type"], "REMEDIATION_REVIEW")
        self.assertIn(
            "REMEDIATION_PLAN_REVIEW",
            out["allowed_owner_choices"],
        )
        self.assertFalse(out["automatic_customer_contact"])

    def test_capacity_hold_remains_review_only(self):
        out = build_owner_renewal_review_packet(
            trusted_scope=SCOPE,
            service_cycle=cycle(
                state="CAPACITY_HOLD",
                decision="CAPACITY_REVIEW",
                review_reasons=["CAPACITY_QUOTA_EXCEEDED"],
            ),
        )
        self.assertEqual(out["review_type"], "CAPACITY_REVIEW")
        self.assertIn(
            "RESCOPE_CAPACITY_REVIEW",
            out["allowed_owner_choices"],
        )
        self.assertFalse(out["automatic_quota_increase"])
        self.assertFalse(out["automatic_pricing_change"])

    def test_incident_cycle_never_auto_pauses_or_terminates(self):
        out = build_owner_renewal_review_packet(
            trusted_scope=SCOPE,
            service_cycle=cycle(
                state="INCIDENT_REVIEW",
                decision="INCIDENT_REVIEW",
                incident_reasons=["TENANT_PRIVACY_INCIDENT"],
            ),
        )
        self.assertEqual(out["review_type"], "INCIDENT_REVIEW")
        self.assertIn(
            "TERMINATION_REVIEW",
            out["allowed_owner_choices"],
        )
        self.assertFalse(out["automatic_pause"])
        self.assertFalse(out["automatic_termination"])

    def test_scope_mismatch_fails_closed(self):
        bad = cycle()
        bad["scope"] = {**SCOPE, "tenant_id": "tenant-other"}
        out = build_owner_renewal_review_packet(
            trusted_scope=SCOPE,
            service_cycle=bad,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("SERVICE_CYCLE_SCOPE_MISMATCH", out["blockers"])

    def test_blocked_cycle_fails_closed(self):
        out = build_owner_renewal_review_packet(
            trusted_scope=SCOPE,
            service_cycle=cycle(
                state="BLOCKED",
                decision="BLOCKED",
                blockers=["SOMETHING"],
            ),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("SERVICE_CYCLE_HAS_BLOCKERS", out["blockers"])
        self.assertIn(
            "SERVICE_CYCLE_STATE_DECISION_INVALID",
            out["blockers"],
        )

    def test_internal_visibility_boundary_is_mandatory(self):
        out = build_owner_renewal_review_packet(
            trusted_scope=SCOPE,
            service_cycle=cycle(customer_visible=True),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "INTERNAL_CYCLE_VISIBILITY_BOUNDARY_INVALID",
            out["blockers"],
        )

    def test_unsafe_source_flag_fails_closed(self):
        out = build_owner_renewal_review_packet(
            trusted_scope=SCOPE,
            service_cycle=cycle(automatic_renewal=True),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "SERVICE_CYCLE_UNSAFE_FIELD:automatic_renewal",
            out["blockers"],
        )

    def test_unknown_conversion_lineage_fails_closed(self):
        out = build_owner_renewal_review_packet(
            trusted_scope=SCOPE,
            service_cycle=cycle(
                source_conversion_decision="AUTO_EXPAND",
            ),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "SOURCE_CONVERSION_DECISION_INVALID",
            out["blockers"],
        )

    def test_no_external_authority_is_granted(self):
        out = build_owner_renewal_review_packet(
            trusted_scope=SCOPE,
            service_cycle=cycle(),
        )
        for key in (
            "automatic_owner_choice",
            "automatic_renewal",
            "automatic_expansion",
            "automatic_package_change",
            "automatic_pause",
            "automatic_termination",
            "automatic_billing",
            "automatic_pricing_change",
            "automatic_quota_increase",
            "automatic_role_change",
            "automatic_integration_change",
            "automatic_customer_contact",
            "automatic_provisioning",
            "automatic_deploy",
            "provider_called",
            "crm_write",
            "production_mutation",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
