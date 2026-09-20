import unittest

import pandas as pd

from atlasquant_admin_insights import (
    BeginnerReadinessCriteria,
    StrategyObservation,
    build_weekly_admin_brief,
    evaluate_beginner_readiness,
)
from atlasquant_admin_research_panel import (
    admin_research_access_allowed,
    build_admin_research_snapshot,
    normalize_weekly_research_csv,
    behavior_stats_from_frame,
    behavior_template_csv,
)
from atlasquant_position_event_manager import (
    EventContext,
    PositionContext,
    assess_post_event,
    assess_pre_event,
)


class PositionEventManagerTests(unittest.TestCase):
    def test_long_eurusd_conflicts_with_supportive_usd_scenario(self):
        position = PositionContext("EURUSD", "EUR", "USD", "LONG", "SWING", 1.5)
        event = EventContext("FOMC", "USD", "HIGH", 120, "SUPPORTIVE", "PARTIAL")
        result = assess_pre_event(position, event)
        self.assertTrue(result["impacted"])
        self.assertEqual(result["currency_exposure"], -1)
        self.assertEqual(result["scenario_alignment"], "CONFLICTING_SCENARIO")
        self.assertTrue(result["review_required"])
        self.assertEqual(result["action"], "HUMAN_REVIEW_ONLY")

    def test_short_eurusd_aligns_with_supportive_usd_scenario(self):
        position = PositionContext("EURUSD", "EUR", "USD", "SHORT", "SWING")
        event = EventContext("CPI", "USD", "HIGH", 90, "SUPPORTIVE", "UNKNOWN")
        result = assess_pre_event(position, event)
        self.assertEqual(result["scenario_alignment"], "ALIGNED_SCENARIO")
        self.assertTrue(result["review_required"])
        self.assertIn("não é previsão", result["interpretation"].lower())

    def test_unrelated_currency_does_not_force_review(self):
        position = PositionContext("EURUSD", "EUR", "USD", "LONG", "POSITION")
        event = EventContext("BoJ", "JPY", "HIGH", 30, "UNCERTAIN", "UNKNOWN")
        result = assess_pre_event(position, event)
        self.assertFalse(result["impacted"])
        self.assertFalse(result["review_required"])
        self.assertEqual(result["scenario_alignment"], "NOT_RELEVANT")

    def test_post_event_never_turns_into_automatic_order(self):
        position = PositionContext("GBPUSD", "GBP", "USD", "SHORT", "SWING")
        event = EventContext("Payroll", "USD", "HIGH", -1, "UNCERTAIN", "UNKNOWN")
        result = assess_post_event(position, event, realized_currency_effect="SUPPORTIVE")
        self.assertEqual(result["thesis_state"], "EVENT_ALIGNED_WITH_POSITION")
        self.assertEqual(result["action"], "HUMAN_REVIEW_ONLY")


class AdminResearchPanelTests(unittest.TestCase):
    def test_admin_and_local_open_mode_can_view_research_panel(self):
        self.assertTrue(admin_research_access_allowed({"role":"ADMIN","mode":"AUTHENTICATED"}))
        self.assertTrue(admin_research_access_allowed({"role":"OPEN","mode":"OPEN"}))
        self.assertFalse(admin_research_access_allowed({"role":"USER","mode":"AUTHENTICATED"}))
        self.assertFalse(admin_research_access_allowed({"role":"PREVIEW","mode":"PREVIEW"}))

    def test_admin_weekly_csv_accepts_portuguese_date_high_low_aliases(self):
        raw=pd.DataFrame({
            "data":["2026-09-14"],
            "máxima":[1.2],
            "mínima":[1.0],
        })
        out=normalize_weekly_research_csv(raw)
        self.assertEqual(list(out.columns),["datetime","high","low"])
        self.assertEqual(len(out),1)

    def test_behavior_shift_template_parses_baseline_and_recent(self):
        frame=pd.read_csv(__import__("io").StringIO(behavior_template_csv()))
        baseline,recent=behavior_stats_from_frame(frame)
        self.assertIsNotNone(baseline)
        self.assertIsNotNone(recent)
        self.assertEqual(baseline.sample_size,100)
        self.assertEqual(recent.sample_size,30)

    def test_admin_snapshot_never_promotes_or_changes_strategy(self):
        backtest={
            "strategy":"FVG",
            "executed_trades":10,
            "rich_context_trades":4,
            "diagnoses":[{} for _ in range(10)],
            "passport":{
                "state":"TESTING",
                "evidence_flags":["paper trading ainda insuficiente"],
            },
        }
        out=build_admin_research_snapshot(
            access={"role":"ADMIN","mode":"AUTHENTICATED"},
            last_backtest=backtest,
        )
        self.assertTrue(out["allowed"])
        self.assertEqual(out["last_strategy"],"FVG")
        self.assertEqual(out["context_gap_trades"],6)
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["automatic_strategy_change"])
        self.assertFalse(out["real_orders_enabled"])


class AdminInsightsTests(unittest.TestCase):
    def setUp(self):
        self.criteria = BeginnerReadinessCriteria(
            min_trades=50,
            min_profit_factor=1.2,
            min_expectancy_r=0.1,
            max_drawdown_r=8.0,
            min_regimes_covered=3,
            max_abs_paper_backtest_gap_r=0.25,
            min_data_quality_pct=90.0,
        )

    def test_high_profit_short_sample_is_not_ready(self):
        obs = StrategyObservation(
            "FAST_WIN", 12, 0.8, 9.0, 2.4, 2.0, 1, 0.05, 98.0
        )
        result = evaluate_beginner_readiness(obs, self.criteria)
        self.assertFalse(result["eligible_for_human_review"])
        self.assertIn("sample_size", result["failures"])
        self.assertIn("regime_coverage", result["failures"])
        self.assertFalse(result["automatic_promotion"])

    def test_robust_sample_can_only_enter_human_review(self):
        obs = StrategyObservation(
            "ROBUST", 140, 0.24, 22.0, 1.45, 5.2, 5, 0.12, 97.0
        )
        result = evaluate_beginner_readiness(obs, self.criteria)
        self.assertTrue(result["eligible_for_human_review"])
        self.assertFalse(result["automatic_promotion"])
        self.assertIn("revisão humana", result["interpretation"])

    def test_weekly_brief_separates_sample_leader_from_promotion(self):
        observations = [
            StrategyObservation("A", 120, 0.30, 18, 1.5, 4.0, 4, 0.10, 96),
            StrategyObservation("B", 15, 0.90, 12, 2.8, 1.0, 1, 0.05, 99),
            StrategyObservation("C", 100, 0.12, 8, 1.25, 7.5, 3, 0.20, 94),
        ]
        brief = build_weekly_admin_brief(observations, self.criteria)
        self.assertEqual(brief["observed_expectancy_leader"], "B")
        self.assertIn("B", brief["insufficient_validation"])
        self.assertFalse(brief["automatic_beginner_promotion"])
        self.assertIn("A", brief["eligible_for_human_review"])


if __name__ == "__main__":
    unittest.main()
