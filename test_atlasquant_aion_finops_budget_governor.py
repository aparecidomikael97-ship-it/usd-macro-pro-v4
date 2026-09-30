import ast
import unittest
from pathlib import Path

from atlasquant_aion_finops_budget_governor import (
    INITIAL_MAX_TRADER_ALLOCATION_PCT,
    INITIAL_MONTHLY_ECOSYSTEM_CAP_BRL,
    evaluate_monthly_budget,
    evaluate_trader_capital_allocation,
    finops_policy,
    revenue_routing_policy,
    trade_target_snapshot,
)


class AionFinopsBudgetGovernorTests(unittest.TestCase):
    def test_policy_matches_current_budget_and_treasury_direction(self):
        policy = finops_policy()
        self.assertEqual(
            policy["initial_monthly_ecosystem_cap_brl"],
            INITIAL_MONTHLY_ECOSYSTEM_CAP_BRL,
        )
        self.assertEqual(
            policy["initial_max_trader_allocation_pct"],
            INITIAL_MAX_TRADER_ALLOCATION_PCT,
        )
        self.assertTrue(policy["business_revenue_primary_ecosystem_funding"])
        self.assertTrue(policy["trader_profit_retained_in_trader_bucket"])
        self.assertFalse(policy["trade_return_target_is_guarantee"])
        self.assertFalse(policy["executes_action"])

    def test_budget_under_cap_is_allowed_for_review_only(self):
        result = evaluate_monthly_budget(
            [
                {"category": "hosting", "amount_brl": 40.0, "recurring": True},
                {"category": "api", "amount_brl": 35.0, "recurring": True},
            ],
            planned_new_commitment_brl=20.0,
        )
        self.assertTrue(result["allowed_for_admin_review"])
        self.assertEqual(result["projected_monthly_cost_brl"], 95.0)
        self.assertFalse(result["automatic_spending"])
        self.assertFalse(result["executes_action"])

    def test_budget_over_200_is_blocked(self):
        result = evaluate_monthly_budget(
            [{"category": "api", "amount_brl": 190.0, "recurring": True}],
            planned_new_commitment_brl=20.0,
        )
        self.assertFalse(result["allowed_for_admin_review"])
        self.assertEqual(result["state"], "BUDGET_BLOCKED")

    def test_cannot_raise_cap_above_200_inside_this_policy(self):
        result = evaluate_monthly_budget(
            [],
            monthly_cap_brl=500.0,
        )
        self.assertFalse(result["allowed_for_admin_review"])
        self.assertIn(
            "MONTHLY_CAP_OUTSIDE_APPROVED_BOUNDARY",
            result["blockers"],
        )

    def test_duplicate_cost_category_is_blocked(self):
        result = evaluate_monthly_budget(
            [
                {"category": "api", "amount_brl": 10.0},
                {"category": "API", "amount_brl": 20.0},
            ]
        )
        self.assertFalse(result["allowed_for_admin_review"])

    def test_trader_initial_allocation_at_30_percent_is_within_policy(self):
        result = evaluate_trader_capital_allocation(
            total_ecosystem_capital_brl=100_000.0,
            requested_trader_capital_brl=30_000.0,
        )
        self.assertEqual(result["state"], "TRADER_ALLOCATION_WITHIN_POLICY")
        self.assertEqual(result["requested_trader_allocation_pct"], 30.0)
        self.assertFalse(result["capital_transfer_authorized"])
        self.assertFalse(result["trade_authorized"])

    def test_trader_initial_allocation_above_30_percent_is_blocked(self):
        result = evaluate_trader_capital_allocation(
            total_ecosystem_capital_brl=100_000.0,
            requested_trader_capital_brl=50_000.0,
        )
        self.assertEqual(result["state"], "TRADER_ALLOCATION_REVIEW_BLOCKED")
        self.assertIn(
            "TRADER_ALLOCATION_ABOVE_INITIAL_30_PERCENT_POLICY",
            result["blockers"],
        )

    def test_business_funds_ecosystem_and_trader_profit_stays_in_trader(self):
        policy = revenue_routing_policy()
        self.assertEqual(
            policy["business_net_cash"]["role"],
            "PRIMARY_ECOSYSTEM_FUNDING_SOURCE",
        )
        self.assertEqual(
            policy["trader_net_profit"]["role"],
            "RETAIN_IN_TRADER_BUCKET",
        )
        self.assertFalse(policy["cross_bucket_transfer_automatic"])

    def test_trade_target_is_never_a_guarantee(self):
        result = trade_target_snapshot(
            trader_capital_brl=100_000.0,
            target_monthly_profit_brl=6_000.0,
        )
        self.assertEqual(result["implied_monthly_return_pct"], 6.0)
        self.assertFalse(result["guaranteed"])
        self.assertFalse(result["expected_return_claim"])
        self.assertTrue(result["requires_backtest_validation"])
        self.assertFalse(result["trade_authorized"])

    def test_admin_exposes_finops_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("25 · FinOps & Tesouraria", source)
        self.assertIn("business_finops_policy", source)

    def test_module_has_no_network_or_executor_imports(self):
        source = Path("atlasquant_aion_finops_budget_governor.py").read_text(
            encoding="utf-8"
        )
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
