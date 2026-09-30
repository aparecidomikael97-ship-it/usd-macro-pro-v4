import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_b2b_revenue_offer import (
    PIPELINE_STAGES,
    PRIORITY_OFFER_ID,
    calculate_offer_economics,
    commercial_pipeline_template,
    offer_readiness,
    pipeline_transition_review,
    priority_offer_template,
    revenue_priority_snapshot,
)
from atlasquant_aion_business_capacity_scale_manager import (
    evaluate_capacity_scale,
)


def _capacity_review():
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_CAPACITY_QUOTA_GUARDRAIL_V1",
        "version": "1",
        "state": "CAPACITY_QUOTA_REVIEW_READY",
        "review_digest": "",
        "ledger_digest": "9" * 64,
        "tenant_ids": ["client-a"],
        "minimum_margin_pct": 20.0,
        "reserve_capacity_pct": 10.0,
        "quota_rows": [{"tenant_id": "client-a"}],
        "quota_application_authorized": False,
        "billing_authorized": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


def _valid_capacity():
    import hashlib
    import json

    review = _capacity_review()
    payload = {
        "ledger_digest": review["ledger_digest"],
        "minimum_margin_pct": review["minimum_margin_pct"],
        "reserve_capacity_pct": review["reserve_capacity_pct"],
        "quota_rows": review["quota_rows"],
    }
    review["review_digest"] = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()

    return evaluate_capacity_scale(
        review,
        usage_rows=[{
            "tenant_id": "client-a",
            "current_month_cost_brl": 20.0,
            "max_utilization_pct": 40.0,
            "active_high_severity_incidents": 0,
        }],
        measurement_ref="metrics://offer-test",
        approved_monthly_budget_cap_brl=200.0,
        shared_platform_cost_brl=20.0,
        available_support_hours=20.0,
        support_hours_per_new_tenant=2.0,
        infra_headroom_pct=60.0,
        infra_load_pct_per_new_tenant=5.0,
        estimated_new_tenant_cost_brl=20.0,
        expected_new_tenant_revenue_brl=300.0,
    )


def _economics():
    return calculate_offer_economics(
        monthly_price_brl=800.0,
        estimated_monthly_cost_brl=240.0,
        implementation_fee_brl=600.0,
        estimated_implementation_cost_brl=200.0,
        minimum_margin_pct=40.0,
    )


class BusinessB2BRevenueOfferTests(unittest.TestCase):
    def test_priority_offer_is_recurring_b2b_service(self):
        row = priority_offer_template()
        self.assertEqual(row["offer_id"], PRIORITY_OFFER_ID)
        self.assertEqual(
            row["commercial_model"],
            "IMPLEMENTATION_PLUS_MONTHLY_RECURRING",
        )
        self.assertFalse(row["result_guarantee"])
        self.assertFalse(row["automatic_sale"])

    def test_economics_calculates_margin_and_sustainable_floor(self):
        row = _economics()
        self.assertEqual(row["state"], "OFFER_ECONOMICS_READY")
        self.assertEqual(row["monthly_contribution_brl"], 560.0)
        self.assertEqual(row["margin_pct"], 70.0)
        self.assertEqual(
            row["minimum_sustainable_monthly_price_brl"],
            400.0,
        )
        self.assertFalse(row["automatic_price_change"])
        self.assertFalse(row["automatic_charge"])

    def test_price_below_admin_margin_floor_requires_review(self):
        row = calculate_offer_economics(
            monthly_price_brl=400.0,
            estimated_monthly_cost_brl=300.0,
            implementation_fee_brl=200.0,
            estimated_implementation_cost_brl=200.0,
            minimum_margin_pct=40.0,
        )
        self.assertEqual(row["state"], "PRICING_REVIEW_REQUIRED")
        self.assertIn("MONTHLY_MARGIN_BELOW_ADMIN_FLOOR", row["blockers"])

    def test_implementation_fee_below_cost_requires_review(self):
        row = calculate_offer_economics(
            monthly_price_brl=800.0,
            estimated_monthly_cost_brl=200.0,
            implementation_fee_brl=100.0,
            estimated_implementation_cost_brl=200.0,
            minimum_margin_pct=40.0,
        )
        self.assertEqual(row["state"], "PRICING_REVIEW_REQUIRED")
        self.assertIn(
            "IMPLEMENTATION_FEE_BELOW_IMPLEMENTATION_COST",
            row["blockers"],
        )

    def test_offer_readiness_needs_all_business_gates(self):
        result = offer_readiness(
            _economics(),
            _valid_capacity(),
            diagnostic_complete=True,
            scope_confirmed=True,
            privacy_terms_reviewed=True,
            sla_defined=True,
            demo_sandbox_ready=True,
            onboarding_checklist_ready=True,
            support_capacity_ready=True,
            integrations_healthy=True,
            finance_guardrails_ready=True,
        )
        self.assertEqual(result["state"], "READY_FOR_ADMIN_SALES_REVIEW")
        self.assertFalse(result["external_contact_authorized"])
        self.assertFalse(result["billing_authorized"])
        self.assertFalse(result["customer_admission_authorized"])
        self.assertFalse(result["executes_action"])

    def test_no_capacity_blocks_offer_readiness(self):
        result = offer_readiness(
            _economics(),
            {},
            diagnostic_complete=True,
            scope_confirmed=True,
            privacy_terms_reviewed=True,
            sla_defined=True,
            demo_sandbox_ready=True,
            onboarding_checklist_ready=True,
            support_capacity_ready=True,
            integrations_healthy=True,
            finance_guardrails_ready=True,
        )
        self.assertEqual(result["state"], "OFFER_READINESS_BLOCKED")
        self.assertIn("capacity_ready", result["blockers"])

    def test_pipeline_is_end_to_end_through_renewal(self):
        pipeline = commercial_pipeline_template()
        stages = [row["stage"] for row in pipeline["stages"]]
        self.assertEqual(tuple(stages), PIPELINE_STAGES)
        self.assertEqual(stages[-1], "RENEWAL_EXPANSION_REVIEW")
        self.assertFalse(pipeline["automatic_stage_advance"])

    def test_pipeline_only_allows_adjacent_review_with_evidence(self):
        result = pipeline_transition_review(
            current_stage="TARGETING",
            target_stage="QUALIFICATION",
            evidence={
                "target_defined": True,
                "contact_permission_reviewed": True,
            },
        )
        self.assertEqual(
            result["state"],
            "PIPELINE_TRANSITION_REVIEW_READY",
        )
        self.assertFalse(result["stage_advance_authorized"])

    def test_pipeline_cannot_skip_to_contract(self):
        result = pipeline_transition_review(
            current_stage="TARGETING",
            target_stage="CONTRACT_REVIEW",
            evidence={
                "proposal_reviewed": True,
                "privacy_terms_reviewed": True,
                "sla_defined": True,
            },
        )
        self.assertEqual(result["state"], "PIPELINE_TRANSITION_BLOCKED")
        self.assertFalse(result["adjacent_transition"])

    def test_revenue_priority_keeps_business_primary_and_trade_nonessential(self):
        row = revenue_priority_snapshot()
        self.assertEqual(
            row["short_term_primary_engine"],
            "BUSINESS_B2B_RECURRING_SERVICES",
        )
        self.assertTrue(row["business_may_fund_ecosystem"])
        self.assertFalse(row["trade_is_required_to_fund_ecosystem"])
        self.assertFalse(row["dropshipping_priority"])

    def test_admin_exposes_b2b_offer_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("27 · Oferta B2B & Receita", source)
        self.assertIn("business_priority_offer_template", source)

    def test_module_has_no_network_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_b2b_revenue_offer.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in (
            "requests",
            "urllib",
            "httpx",
            "socket",
            "subprocess",
            "github",
            "paramiko",
            "docker",
            "kubernetes",
        ):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
