import ast
import unittest
from pathlib import Path

from atlasquant_aion_independence_index import (
    evaluate_independence_index,
    independence_policy,
    transition_review_questions,
)


class AionIndependenceIndexTests(unittest.TestCase):
    def test_policy_keeps_personal_values_out_of_repository_contract(self):
        row = independence_policy()
        self.assertFalse(row["personal_financial_values_persisted_by_module"])
        self.assertFalse(row["repository_hardcodes_personal_income"])
        self.assertFalse(row["automatic_employment_exit_recommendation"])

    def test_building_zone_for_early_stage(self):
        row = evaluate_independence_index(
            baseline_net_income_low_brl=4000,
            baseline_net_income_high_brl=5000,
            non_trade_ecosystem_net_income_history_brl=[1000, 1500, 2000],
            recurring_revenue_share_pct=50,
            largest_client_share_pct=70,
            emergency_reserve_months=2,
            safety_multiplier=1.5,
            required_consistency_months=6,
            required_reserve_months=6,
            minimum_recurring_share_pct=70,
            maximum_client_concentration_pct=40,
            essential_expenses_depend_on_trade=False,
        )
        self.assertEqual(row["state"], "INDEPENDENCE_INDEX_CALCULATED")
        self.assertEqual(row["zone"], "BUILDING")
        self.assertFalse(row["transition_review_available"])
        self.assertFalse(row["score_is_probability"])

    def test_transition_review_zone_requires_non_trade_stability(self):
        row = evaluate_independence_index(
            baseline_net_income_low_brl=4000,
            baseline_net_income_high_brl=5000,
            non_trade_ecosystem_net_income_history_brl=[
                8000, 8200, 8100, 8300, 8400, 8500
            ],
            recurring_revenue_share_pct=85,
            largest_client_share_pct=25,
            emergency_reserve_months=8,
            safety_multiplier=1.5,
            required_consistency_months=6,
            required_reserve_months=6,
            minimum_recurring_share_pct=70,
            maximum_client_concentration_pct=40,
            essential_expenses_depend_on_trade=False,
        )
        self.assertEqual(row["zone"], "TRANSITION_REVIEW_ZONE")
        self.assertTrue(row["transition_review_available"])
        self.assertFalse(row["employment_exit_recommended"])
        self.assertTrue(row["requires_personal_human_decision"])

    def test_trade_dependency_blocks_transition_review(self):
        row = evaluate_independence_index(
            baseline_net_income_low_brl=4000,
            baseline_net_income_high_brl=5000,
            non_trade_ecosystem_net_income_history_brl=[
                8500, 8500, 8500, 8500, 8500, 8500
            ],
            recurring_revenue_share_pct=90,
            largest_client_share_pct=20,
            emergency_reserve_months=12,
            safety_multiplier=1.5,
            required_consistency_months=6,
            required_reserve_months=6,
            minimum_recurring_share_pct=70,
            maximum_client_concentration_pct=40,
            essential_expenses_depend_on_trade=True,
        )
        self.assertFalse(row["transition_review_available"])
        self.assertFalse(
            row["gates"]["essential_expenses_independent_from_trade"]
        )

    def test_largest_client_concentration_can_block_review(self):
        row = evaluate_independence_index(
            baseline_net_income_low_brl=4000,
            baseline_net_income_high_brl=5000,
            non_trade_ecosystem_net_income_history_brl=[
                8500, 8500, 8500, 8500, 8500, 8500
            ],
            recurring_revenue_share_pct=90,
            largest_client_share_pct=80,
            emergency_reserve_months=12,
            safety_multiplier=1.5,
            required_consistency_months=6,
            required_reserve_months=6,
            minimum_recurring_share_pct=70,
            maximum_client_concentration_pct=40,
            essential_expenses_depend_on_trade=False,
        )
        self.assertFalse(row["transition_review_available"])
        self.assertFalse(row["gates"]["client_concentration_met"])

    def test_review_questions_never_make_exit_decision(self):
        index = evaluate_independence_index(
            baseline_net_income_low_brl=4000,
            baseline_net_income_high_brl=5000,
            non_trade_ecosystem_net_income_history_brl=[
                8500, 8500, 8500, 8500, 8500, 8500
            ],
            recurring_revenue_share_pct=90,
            largest_client_share_pct=20,
            emergency_reserve_months=12,
            safety_multiplier=1.5,
            required_consistency_months=6,
            required_reserve_months=6,
            minimum_recurring_share_pct=70,
            maximum_client_concentration_pct=40,
            essential_expenses_depend_on_trade=False,
        )
        review = transition_review_questions(index)
        self.assertEqual(review["state"], "HUMAN_TRANSITION_REVIEW_AVAILABLE")
        self.assertFalse(review["employment_exit_recommended"])
        self.assertEqual(review["decision_owner"], "USER")

    def test_admin_exposes_independence_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("30 · Indice de Independencia CLT", source)
        self.assertIn("aion_independence_policy", source)

    def test_module_has_no_network_or_executor_imports(self):
        source = Path("atlasquant_aion_independence_index.py").read_text(
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
