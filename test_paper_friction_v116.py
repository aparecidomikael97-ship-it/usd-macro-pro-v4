import math
import unittest
import pandas as pd
import paper_friction_v116 as f

class PaperFrictionV116Tests(unittest.TestCase):
    def test_closed_trade_gets_deterministic_conservative_cost(self):
        d=pd.DataFrame([{"status":"CLOSED","realized_r":2.0,"result":"WIN"}])
        out=f.apply_paper_friction(d)
        self.assertEqual(out.loc[0,"gross_r"],2.0)
        self.assertEqual(out.loc[0,"total_friction_r"],f.DEFAULT_TOTAL_R)
        self.assertEqual(out.loc[0,"net_r"],round(2.0-f.DEFAULT_TOTAL_R,4))
        self.assertEqual(out.loc[0,"result"],"WIN")

    def test_open_trade_is_not_costed(self):
        out=f.apply_paper_friction(pd.DataFrame([{"status":"OPEN","realized_r":1.0}]))
        self.assertTrue(pd.isna(out.loc[0,"net_r"]))

    def test_nonfinite_realized_r_is_never_costed(self):
        for value in (float("nan"),float("inf"),-float("inf"),"bad",None):
            with self.subTest(value=value):
                out=f.apply_paper_friction(pd.DataFrame([{"status":"CLOSED","realized_r":value}]))
                self.assertTrue(pd.isna(out.loc[0,"net_r"]))


    def test_summary_remains_finite_with_invalid_realized_r(self):
        d=pd.DataFrame([
            {"status":"CLOSED","realized_r":2.0},
            {"status":"CLOSED","realized_r":float("nan")},
            {"status":"CLOSED","realized_r":float("inf")},
            {"status":"CLOSED","realized_r":float("-inf")},
        ])
        s=f.summarize_net(d)
        self.assertEqual(s["closed_costed"],1)
        self.assertTrue(math.isfinite(s["gross_r"]))
        self.assertTrue(math.isfinite(s["net_r"]))
        self.assertTrue(math.isfinite(s["avg_net_r"]))

    def test_summary_safety_contract_never_enables_execution(self):
        s=f.summarize_net(pd.DataFrame([{"status":"CLOSED","realized_r":1.0}]))
        self.assertFalse(s["safety"]["real_orders"])
        self.assertFalse(s["safety"]["broker_connection"])
        self.assertFalse(s["safety"]["changes_signal"])
        self.assertFalse(s["safety"]["changes_gate"])
        self.assertFalse(s["safety"]["auto_strategy_selection"])

    def test_friction_constants_are_finite_and_nonnegative(self):
        for value in (f.DEFAULT_SPREAD_R,f.DEFAULT_SLIPPAGE_R,f.DEFAULT_TOTAL_R):
            self.assertTrue(math.isfinite(value))
            self.assertGreaterEqual(value,0)
        self.assertAlmostEqual(f.DEFAULT_TOTAL_R,f.DEFAULT_SPREAD_R+f.DEFAULT_SLIPPAGE_R)

if __name__=="__main__":
    unittest.main()
