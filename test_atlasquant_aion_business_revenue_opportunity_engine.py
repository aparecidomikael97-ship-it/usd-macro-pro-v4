import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_revenue_opportunity_engine import (
    evaluate_revenue_opportunity,
    opportunity_template_catalog,
    rank_revenue_opportunities,
    revenue_opportunity_policy,
)


def _opportunity(
    opportunity_id="aion-b2b",
    label="AION B2B",
    startup_cost=50.0,
    budget=200.0,
    price=500.0,
    monthly_cost=100.0,
    days=10,
    margin_floor=40.0,
    repeatability=90.0,
    evidence=80.0,
    support=30.0,
    complexity=35.0,
    capacity=True,
    opportunity_type="B2B_AUTOMATION",
):
    return {
        "opportunity_id": opportunity_id,
        "label": label,
        "opportunity_type": opportunity_type,
        "startup_cost_brl": startup_cost,
        "available_startup_budget_brl": budget,
        "monthly_price_brl": price,
        "estimated_monthly_cost_brl": monthly_cost,
        "implementation_days": days,
        "minimum_margin_pct": margin_floor,
        "repeatability_pct": repeatability,
        "evidence_readiness_pct": evidence,
        "support_load_pct": support,
        "implementation_complexity_pct": complexity,
        "capacity_ready": capacity,
    }


class BusinessRevenueOpportunityEngineTests(unittest.TestCase):
    def test_policy_is_service_first_and_nonexecuting(self):
        row = revenue_opportunity_policy()
        self.assertEqual(row["strategy"], "SERVICE_FIRST_RECURRING_B2B")
        self.assertFalse(row["dropshipping_priority"])
        self.assertFalse(row["score_is_probability"])
        self.assertFalse(row["automatic_sale"])

    def test_eligible_opportunity_gets_planning_score(self):
        row = evaluate_revenue_opportunity(_opportunity())
        self.assertEqual(row["state"], "REVENUE_OPPORTUNITY_ELIGIBLE")
        self.assertGreater(row["score"], 0)
        self.assertEqual(row["margin_pct"], 80.0)
        self.assertEqual(row["monthly_contribution_brl"], 400.0)
        self.assertFalse(row["score_is_probability"])
        self.assertFalse(row["sales_forecast"])

    def test_budget_violation_blocks_before_ranking(self):
        row = evaluate_revenue_opportunity(
            _opportunity(startup_cost=300.0, budget=200.0)
        )
        self.assertEqual(row["state"], "REVENUE_OPPORTUNITY_BLOCKED")
        self.assertIn("STARTUP_COST_ABOVE_AVAILABLE_BUDGET", row["blockers"])
        self.assertIsNone(row["score"])

    def test_margin_violation_blocks_before_ranking(self):
        row = evaluate_revenue_opportunity(
            _opportunity(price=200.0, monthly_cost=150.0, margin_floor=40.0)
        )
        self.assertEqual(row["state"], "REVENUE_OPPORTUNITY_BLOCKED")
        self.assertIn("MARGIN_BELOW_ADMIN_FLOOR", row["blockers"])

    def test_capacity_violation_blocks_before_ranking(self):
        row = evaluate_revenue_opportunity(_opportunity(capacity=False))
        self.assertEqual(row["state"], "REVENUE_OPPORTUNITY_BLOCKED")
        self.assertIn("CAPACITY_NOT_READY", row["blockers"])

    def test_portfolio_ranks_only_eligible_inputs(self):
        fast = _opportunity(
            opportunity_id="fast",
            label="Fast",
            days=5,
            startup_cost=20,
            support=20,
            complexity=20,
        )
        slower = _opportunity(
            opportunity_id="slower",
            label="Slower",
            days=40,
            startup_cost=100,
            support=50,
            complexity=60,
        )
        blocked = _opportunity(
            opportunity_id="blocked",
            label="Blocked",
            capacity=False,
        )
        result = rank_revenue_opportunities([slower, blocked, fast])
        self.assertEqual(
            result["state"],
            "READY_FOR_ADMIN_REVENUE_PRIORITY_REVIEW",
        )
        self.assertEqual(result["top_opportunity_id"], "fast")
        self.assertEqual(result["eligible_count"], 2)
        self.assertEqual(result["blocked_count"], 1)
        self.assertFalse(result["top_is_sales_forecast"])
        self.assertFalse(result["top_is_automatic_decision"])

    def test_templates_embed_no_market_price_assumptions(self):
        row = opportunity_template_catalog()
        self.assertEqual(len(row["templates"]), 3)
        self.assertFalse(row["market_assumptions_embedded"])
        self.assertFalse(row["prices_embedded"])
        self.assertFalse(row["dropshipping_in_current_strategy"])

    def test_admin_exposes_revenue_opportunity_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("34 · Oportunidades de Receita", source)
        self.assertIn("business_revenue_opportunity_policy", source)

    def test_module_has_no_network_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_revenue_opportunity_engine.py"
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
