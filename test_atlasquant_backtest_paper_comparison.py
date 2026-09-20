import unittest

from atlasquant_backtest_paper_comparison import compare_backtest_paper, comparison_rows


class BacktestPaperComparisonTests(unittest.TestCase):
    def test_complete_evidence_is_compared_descriptively(self):
        result = compare_backtest_paper({
            "backtest_samples": 140,
            "forward_samples": 45,
            "expectancy_r": 0.20,
            "forward_expectancy_r": 0.12,
            "profit_factor": 1.40,
            "forward_profit_factor": 1.20,
            "max_drawdown_r": 6.0,
            "forward_max_drawdown_r": 7.5,
            "forward_win_rate_pct": 55.0,
        })
        self.assertTrue(result["comparable"])
        self.assertEqual(result["expectancy_gap_r"], -0.08)
        self.assertEqual(result["expectancy_retention_pct"], 60.0)
        self.assertTrue(result["descriptive_only"])
        self.assertTrue(result["manual_review_required"])
        self.assertFalse(result["automatic_strategy_change"])
        self.assertFalse(result["automatic_weight_change"])
        self.assertFalse(result["real_orders_enabled"])

    def test_missing_or_invalid_core_evidence_fails_closed(self):
        for evidence in (
            {},
            {"backtest_samples": 100, "forward_samples": 30, "expectancy_r": 0.1},
            {"backtest_samples": True, "forward_samples": 30, "expectancy_r": 0.1, "forward_expectancy_r": 0.1},
            {"backtest_samples": -1, "forward_samples": 30, "expectancy_r": 0.1, "forward_expectancy_r": 0.1},
            {"backtest_samples": 100, "forward_samples": 30, "expectancy_r": float("nan"), "forward_expectancy_r": 0.1},
        ):
            with self.subTest(evidence=evidence):
                result = compare_backtest_paper(evidence)
                self.assertFalse(result["comparable"])
                self.assertIsNone(result["expectancy_gap_r"])
                self.assertFalse(result["real_orders_enabled"])

    def test_zero_backtest_expectancy_does_not_divide_by_zero(self):
        result = compare_backtest_paper({
            "backtest_samples": 100,
            "forward_samples": 30,
            "expectancy_r": 0.0,
            "forward_expectancy_r": 0.1,
        })
        self.assertTrue(result["comparable"])
        self.assertIsNone(result["expectancy_retention_pct"])

    def test_rows_are_stable_and_do_not_promote_setups(self):
        rows = comparison_rows({
            "ote": {"backtest_samples": 120, "forward_samples": 35, "expectancy_r": 0.1, "forward_expectancy_r": 0.08},
            "fvg": {"backtest_samples": 130, "forward_samples": 40, "expectancy_r": 0.2, "forward_expectancy_r": 0.15},
        })
        self.assertEqual([row["setup_id"] for row in rows], ["fvg", "ote"])
        self.assertTrue(all(row["manual_review_required"] for row in rows))
        self.assertTrue(all(not row["automatic_strategy_change"] for row in rows))


if __name__ == "__main__":
    unittest.main()
