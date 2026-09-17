import unittest

import pandas as pd

from paper_friction_v116 import apply_paper_friction, summarize_net


class PaperFrictionV116Tests(unittest.TestCase):
    def test_closed_trade_keeps_gross_and_adds_net(self):
        src = pd.DataFrame([{
            "trade_id": "x1", "status": "CLOSED", "result": "WIN", "realized_r": 2.0,
        }])
        out = apply_paper_friction(src)
        self.assertEqual(float(out.iloc[0]["realized_r"]), 2.0)
        self.assertEqual(float(out.iloc[0]["gross_r"]), 2.0)
        self.assertAlmostEqual(float(out.iloc[0]["total_friction_r"]), 0.06, places=8)
        self.assertAlmostEqual(float(out.iloc[0]["net_r"]), 1.94, places=8)
        self.assertEqual(out.iloc[0]["result"], "WIN")

    def test_open_trade_is_not_charged_early(self):
        src = pd.DataFrame([{
            "trade_id": "x2", "status": "OPEN", "result": "", "realized_r": None,
        }])
        out = apply_paper_friction(src)
        self.assertTrue(pd.isna(out.iloc[0]["net_r"]))
        self.assertTrue(pd.isna(out.iloc[0]["total_friction_r"]))

    def test_summary_reports_gross_cost_and_net(self):
        src = pd.DataFrame([
            {"status": "CLOSED", "realized_r": 2.0},
            {"status": "CLOSED", "realized_r": -1.0},
        ])
        s = summarize_net(src)
        self.assertEqual(s["closed_costed"], 2)
        self.assertAlmostEqual(s["gross_r"], 1.0, places=8)
        self.assertAlmostEqual(s["friction_r"], 0.12, places=8)
        self.assertAlmostEqual(s["net_r"], 0.88, places=8)
        self.assertFalse(s["safety"]["real_orders"])
        self.assertFalse(s["safety"]["broker_connection"])
        self.assertFalse(s["safety"]["auto_strategy_selection"])


if __name__ == "__main__":
    unittest.main()
