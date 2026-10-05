from __future__ import annotations

import unittest

from atlasquant_aion_b2b_conversion_capacity import (
    evaluate_conversion_capacity,
    recommend_package,
)

SCOPE = {"owner_id": "owner-a", "tenant_id": "tenant-a", "workspace_id": "ws-a"}


def outcome(**overrides):
    row = {
        "state": "HEALTHY",
        "decision": "CONTINUE_REVIEW_CANDIDATE",
        "blockers": [],
        "hard_stop_reasons": [],
        "owner_review_required": True,
        "evidence_digest": "sha256:pilot-outcome",
    }
    row.update(overrides)
    return row


def commercial(**overrides):
    row = {
        **SCOPE,
        "customer_id": "customer-001",
        "need_tracks": ["ATENDIMENTO_CONVERSAO", "GESTAO_INTELIGENTE"],
        "integration_count": 4,
        "channel_count": 3,
        "requested_capacity_units": 40,
        "monthly_price_brl": 5000.0,
        "expected_monthly_service_cost_brl": 2500.0,
        "implementation_price_brl": 3000.0,
        "expected_implementation_cost_brl": 1500.0,
        "evidence_refs": ["pricing:v1", "scope:v1", "capacity:v1", "pilot:v1"],
    }
    row.update(overrides)
    return row


def capacity(**overrides):
    row = {
        **SCOPE,
        "active_customer_count": 3,
        "max_active_customers": 10,
        "current_capacity_units": 120,
        "max_capacity_units": 300,
    }
    row.update(overrides)
    return row


def policy(**overrides):
    row = {
        **SCOPE,
        "state": "VERIFIED",
        "min_monthly_gross_margin_pct": 35.0,
        "max_portfolio_utilization_pct": 85.0,
        "max_single_customer_capacity_share_pct": 30.0,
    }
    row.update(overrides)
    return row


class AionB2BConversionCapacityTests(unittest.TestCase):
    def test_package_recommendation_is_deterministic(self):
        self.assertEqual(
            recommend_package(
                need_tracks=["ATENDIMENTO_CONVERSAO"],
                integration_count=2,
                channel_count=2,
                requested_capacity_units=20,
            ),
            "ESSENCIAL",
        )
        self.assertEqual(
            recommend_package(
                need_tracks=["ATENDIMENTO_CONVERSAO", "GESTAO_INTELIGENTE"],
                integration_count=4,
                channel_count=3,
                requested_capacity_units=40,
            ),
            "PROFISSIONAL",
        )
        self.assertEqual(
            recommend_package(
                need_tracks=["ATENDIMENTO_CONVERSAO", "MARKETING_VENDAS", "GESTAO_INTELIGENTE"],
                integration_count=7,
                channel_count=5,
                requested_capacity_units=80,
            ),
            "COMPLETO",
        )

    def test_healthy_profitable_capacity_fit_reaches_commercial_review_only(self):
        out = evaluate_conversion_capacity(
            trusted_scope=SCOPE,
            pilot_outcome=outcome(),
            commercial=commercial(),
            capacity=capacity(),
            policy=policy(),
        )
        self.assertEqual(out["state"], "REVIEWABLE")
        self.assertEqual(out["decision"], "COMMERCIAL_REVIEW_CANDIDATE")
        self.assertEqual(out["recommended_package"], "PROFISSIONAL")
        self.assertEqual(out["monthly_contribution_brl"], 2500.0)
        self.assertEqual(out["monthly_gross_margin_pct"], 50.0)
        self.assertEqual(out["implementation_contribution_brl"], 1500.0)
        self.assertTrue(out["owner_commercial_approval_required"])
        self.assertFalse(out["automatic_conversion"])

    def test_unhealthy_or_non_continue_pilot_blocks(self):
        out = evaluate_conversion_capacity(
            trusted_scope=SCOPE,
            pilot_outcome=outcome(state="WATCH", decision="PAUSE_OR_REMEDIATE_REVIEW"),
            commercial=commercial(),
            capacity=capacity(),
            policy=policy(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PILOT_OUTCOME_NOT_HEALTHY", out["blockers"])
        self.assertIn("PILOT_NOT_CONTINUE_REVIEW_CANDIDATE", out["blockers"])

    def test_scope_mismatch_blocks(self):
        out = evaluate_conversion_capacity(
            trusted_scope=SCOPE,
            pilot_outcome=outcome(),
            commercial=commercial(tenant_id="tenant-b"),
            capacity=capacity(),
            policy=policy(),
        )
        self.assertIn("COMMERCIAL_SCOPE_MISMATCH", out["blockers"])

    def test_margin_below_policy_requires_reprice_or_rescope_review(self):
        out = evaluate_conversion_capacity(
            trusted_scope=SCOPE,
            pilot_outcome=outcome(),
            commercial=commercial(monthly_price_brl=5000.0, expected_monthly_service_cost_brl=4000.0),
            capacity=capacity(),
            policy=policy(min_monthly_gross_margin_pct=35.0),
        )
        self.assertEqual(out["state"], "COMMERCIAL_HOLD")
        self.assertEqual(out["decision"], "REPRICE_OR_RESCOPE_REVIEW")
        self.assertIn("MONTHLY_MARGIN_BELOW_POLICY", out["review_reasons"])

    def test_negative_implementation_contribution_requires_review(self):
        out = evaluate_conversion_capacity(
            trusted_scope=SCOPE,
            pilot_outcome=outcome(),
            commercial=commercial(implementation_price_brl=1000.0, expected_implementation_cost_brl=1500.0),
            capacity=capacity(),
            policy=policy(),
        )
        self.assertEqual(out["decision"], "REPRICE_OR_RESCOPE_REVIEW")
        self.assertIn("IMPLEMENTATION_CONTRIBUTION_NEGATIVE", out["review_reasons"])

    def test_customer_count_capacity_exceeded_holds_conversion(self):
        out = evaluate_conversion_capacity(
            trusted_scope=SCOPE,
            pilot_outcome=outcome(),
            commercial=commercial(),
            capacity=capacity(active_customer_count=10, max_active_customers=10),
            policy=policy(),
        )
        self.assertEqual(out["state"], "CAPACITY_HOLD")
        self.assertEqual(out["decision"], "CAPACITY_REVIEW")
        self.assertIn("CUSTOMER_COUNT_CAPACITY_EXCEEDED", out["review_reasons"])

    def test_capacity_units_exceeded_holds_conversion(self):
        out = evaluate_conversion_capacity(
            trusted_scope=SCOPE,
            pilot_outcome=outcome(),
            commercial=commercial(requested_capacity_units=50),
            capacity=capacity(current_capacity_units=270, max_capacity_units=300),
            policy=policy(max_portfolio_utilization_pct=100.0),
        )
        self.assertEqual(out["decision"], "CAPACITY_REVIEW")
        self.assertIn("CAPACITY_UNITS_EXCEEDED", out["review_reasons"])

    def test_portfolio_utilization_policy_is_enforced_before_hard_capacity(self):
        out = evaluate_conversion_capacity(
            trusted_scope=SCOPE,
            pilot_outcome=outcome(),
            commercial=commercial(requested_capacity_units=40),
            capacity=capacity(current_capacity_units=220, max_capacity_units=300),
            policy=policy(max_portfolio_utilization_pct=85.0),
        )
        self.assertEqual(out["decision"], "CAPACITY_REVIEW")
        self.assertIn("PORTFOLIO_UTILIZATION_POLICY_EXCEEDED", out["review_reasons"])
        self.assertLessEqual(out["projected_capacity_units"], 300)

    def test_single_customer_concentration_is_bounded(self):
        out = evaluate_conversion_capacity(
            trusted_scope=SCOPE,
            pilot_outcome=outcome(),
            commercial=commercial(requested_capacity_units=100),
            capacity=capacity(current_capacity_units=50, max_capacity_units=300),
            policy=policy(max_single_customer_capacity_share_pct=30.0),
        )
        self.assertEqual(out["decision"], "CAPACITY_REVIEW")
        self.assertIn("SINGLE_CUSTOMER_CAPACITY_SHARE_EXCEEDED", out["review_reasons"])

    def test_verified_policy_is_required(self):
        out = evaluate_conversion_capacity(
            trusted_scope=SCOPE,
            pilot_outcome=outcome(),
            commercial=commercial(),
            capacity=capacity(),
            policy=policy(state="DRAFT"),
        )
        self.assertIn("COMMERCIAL_POLICY_NOT_VERIFIED", out["blockers"])

    def test_commercial_evidence_is_required(self):
        out = evaluate_conversion_capacity(
            trusted_scope=SCOPE,
            pilot_outcome=outcome(),
            commercial=commercial(evidence_refs=["one"]),
            capacity=capacity(),
            policy=policy(),
        )
        self.assertIn("COMMERCIAL_EVIDENCE_INSUFFICIENT", out["blockers"])

    def test_no_external_authority_is_granted(self):
        out = evaluate_conversion_capacity(
            trusted_scope=SCOPE,
            pilot_outcome=outcome(),
            commercial=commercial(),
            capacity=capacity(),
            policy=policy(),
        )
        for key in (
            "automatic_conversion",
            "automatic_package_change",
            "automatic_pricing_change",
            "automatic_contract",
            "automatic_billing",
            "automatic_provisioning",
            "automatic_customer_contact",
            "automatic_deploy",
            "production_mutation",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
