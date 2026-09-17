import unittest

import pandas as pd

from atlasquant_paper_friction_panel_v116 import friction_snapshot


class PaperFrictionPanelV116Tests(unittest.TestCase):
    def test_summary_values_are_exposed(self):
        summary = {
            "gross_r_before_friction": 1.0,
            "friction_r": 0.12,
            "net_r_after_friction": 0.88,
            "friction_v116": {
                "version": "V11.6_PAPER_FRICTION",
                "closed_costed": 2,
                "gross_r": 1.0,
                "friction_r": 0.12,
                "net_r": 0.88,
                "profit_factor_net_r": 1.94,
            },
            "safety": {"real_orders": False, "broker_connection": False},
        }
        snap = friction_snapshot(summary, pd.DataFrame())
        self.assertEqual(snap["closed_costed"], 2)
        self.assertAlmostEqual(snap["gross_r"], 1.0)
        self.assertAlmostEqual(snap["friction_r"], 0.12)
        self.assertAlmostEqual(snap["net_r"], 0.88)
        self.assertAlmostEqual(snap["profit_factor_net_r"], 1.94)
        self.assertTrue(snap["safety_confirmed"])

    def test_runtime_csv_is_safe_fallback(self):
        trades = pd.DataFrame([
            {"status": "CLOSED", "gross_r": 2.0, "total_friction_r": 0.06, "net_r": 1.94},
            {"status": "CLOSED", "gross_r": -1.0, "total_friction_r": 0.06, "net_r": -1.06},
            {"status": "OPEN", "gross_r": None, "total_friction_r": None, "net_r": None},
        ])
        snap = friction_snapshot(
            {"safety": {"real_orders": False, "broker_connection": False}},
            trades,
        )
        self.assertEqual(snap["closed_costed"], 2)
        self.assertAlmostEqual(snap["gross_r"], 1.0)
        self.assertAlmostEqual(snap["friction_r"], 0.12)
        self.assertAlmostEqual(snap["net_r"], 0.88)
        self.assertTrue(snap["safety_confirmed"])


if __name__ == "__main__":
    unittest.main()
