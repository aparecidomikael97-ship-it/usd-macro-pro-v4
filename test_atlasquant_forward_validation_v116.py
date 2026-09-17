import unittest

import pandas as pd

from atlasquant_forward_validation_v116 import (
    comparison_frame_v116,
    paper_metrics_after_friction,
    paper_records_after_friction,
)


class ForwardValidationV116Tests(unittest.TestCase):
    def test_net_r_has_priority_over_realized_r(self):
        df = pd.DataFrame([
            {"status": "CLOSED", "result": "WIN", "realized_r": 2.0, "net_r": 1.94, "pair": "EUR/USD", "total_friction_r": 0.06},
            {"status": "CLOSED", "result": "LOSS", "realized_r": -1.0, "net_r": -1.06, "pair": "USD/JPY", "total_friction_r": 0.06},
        ])
        records = paper_records_after_friction(df)
        self.assertEqual(len(records), 2)
        self.assertAlmostEqual(records[0]["net_r"], 1.94)
        self.assertAlmostEqual(records[1]["net_r"], -1.06)

        metrics = paper_metrics_after_friction(df)
        self.assertAlmostEqual(metrics["gross_r_before_friction"], 1.0)
        self.assertAlmostEqual(metrics["friction_r"], 0.12)
        self.assertAlmostEqual(metrics["net_r"], 0.88)
        self.assertAlmostEqual(metrics["expectancy_r"], 0.44)
        self.assertTrue(metrics["uses_net_r_when_available"])

    def test_falls_back_to_realized_r_for_legacy_rows(self):
        df = pd.DataFrame([
            {"status": "CLOSED", "result": "WIN", "realized_r": 2.0, "pair": "EUR/USD"},
        ])
        records = paper_records_after_friction(df)
        self.assertEqual(len(records), 1)
        self.assertAlmostEqual(records[0]["net_r"], 2.0)

    def test_comparison_remains_descriptive(self):
        snapshot = {
            "evidence": {"bundle": {"evidence_summary": [{
                "operacional": "FVG",
                "trades": 20,
                "win_rate_pct": 50.0,
                "expectancy_r": 0.1,
                "net_r": 2.0,
                "profit_factor": 1.2,
                "max_drawdown_r": 3.0,
                "sample_tier": "SMALL",
            }]}}
        }
        frame = comparison_frame_v116(snapshot, pd.DataFrame())
        self.assertEqual(list(frame["fonte"]), ["BACKTEST HISTÓRICO", "PAPER PROSPECTIVO"])
        self.assertIn("base_resultado", frame.columns)
        self.assertNotIn("ranking", frame.columns)
        self.assertNotIn("winner", frame.columns)


if __name__ == "__main__":
    unittest.main()
