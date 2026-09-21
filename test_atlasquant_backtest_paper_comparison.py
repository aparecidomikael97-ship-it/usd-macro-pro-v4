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

    def test_malformed_runtime_evidence_fails_closed_without_exception(self):
        for evidence in ([], "bad", 42, True):
            with self.subTest(evidence=evidence):
                result = compare_backtest_paper(evidence)
                self.assertFalse(result["comparable"])
                self.assertTrue(result["manual_review_required"])
                self.assertFalse(result["automatic_strategy_change"])
                self.assertFalse(result["automatic_weight_change"])
                self.assertFalse(result["real_orders_enabled"])

    def test_zero_sample_evidence_fails_closed(self):
        for evidence in (
            {"backtest_samples": 0, "forward_samples": 30, "expectancy_r": 0.1, "forward_expectancy_r": 0.1},
            {"backtest_samples": 100, "forward_samples": 0, "expectancy_r": 0.1, "forward_expectancy_r": 0.1},
            {"backtest_samples": 0, "forward_samples": 0, "expectancy_r": 0.1, "forward_expectancy_r": 0.1},
        ):
            with self.subTest(evidence=evidence):
                result = compare_backtest_paper(evidence)
                self.assertFalse(result["comparable"])
                self.assertIsNone(result["expectancy_gap_r"])
                self.assertIsNone(result["expectancy_retention_pct"])
                self.assertTrue(result["manual_review_required"])
                self.assertFalse(result["automatic_strategy_change"])
                self.assertFalse(result["automatic_weight_change"])
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

    def test_rows_fail_closed_for_malformed_container_and_mixed_keys(self):
        self.assertEqual(comparison_rows([]), [])
        rows = comparison_rows({2: {}, "fvg": {}})
        self.assertEqual([row["setup_id"] for row in rows], ["2", "fvg"])
        self.assertTrue(all(not row["comparable"] for row in rows))
        self.assertTrue(all(not row["real_orders_enabled"] for row in rows))


    def test_small_samples_never_trigger_automatic_changes_or_real_orders(self):
        for backtest_samples, paper_samples in ((1,1),(2,1),(5,3),(10,5)):
            with self.subTest(backtest_samples=backtest_samples,paper_samples=paper_samples):
                result=compare_backtest_paper({
                    "backtest_samples":backtest_samples,
                    "forward_samples":paper_samples,
                    "expectancy_r":9.0,
                    "forward_expectancy_r":12.0,
                    "profit_factor":99.0,
                    "forward_profit_factor":99.0,
                    "forward_win_rate_pct":100.0,
                })
                self.assertTrue(result["descriptive_only"])
                self.assertTrue(result["manual_review_required"])
                self.assertFalse(result["automatic_strategy_change"])
                self.assertFalse(result["automatic_weight_change"])
                self.assertFalse(result["real_orders_enabled"])

    def test_extreme_positive_metrics_do_not_override_safety_contract(self):
        result=compare_backtest_paper({
            "backtest_samples":100000,
            "forward_samples":100000,
            "expectancy_r":1000.0,
            "forward_expectancy_r":1000.0,
            "profit_factor":1000.0,
            "forward_profit_factor":1000.0,
            "forward_win_rate_pct":100.0,
        })
        self.assertTrue(result["comparable"])
        self.assertTrue(result["descriptive_only"])
        self.assertTrue(result["manual_review_required"])
        self.assertFalse(result["automatic_strategy_change"])
        self.assertFalse(result["automatic_weight_change"])
        self.assertFalse(result["real_orders_enabled"])


if __name__ == "__main__":
    unittest.main()