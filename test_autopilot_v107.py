import unittest
import pandas as pd

import autopilot_v107 as a

class AutopilotV107Tests(unittest.TestCase):
    def test_market_schedule(self):
        sat = pd.Timestamp("2026-09-12T15:00:00Z")
        mon = pd.Timestamp("2026-09-14T15:00:00Z")
        self.assertFalse(a.forex_market_likely_open(sat))
        self.assertTrue(a.forex_market_likely_open(mon))

    def test_macro_side(self):
        self.assertEqual(a.macro_side("COMPRA USD/CHF"), "BUY")
        self.assertEqual(a.macro_side("VENDA EUR/USD"), "SELL")
        self.assertEqual(a.macro_side("AGUARDAR"), "WAIT")

    def test_directional_return(self):
        self.assertAlmostEqual(a.directional_return("BUY",100,101),1.0)
        self.assertAlmostEqual(a.directional_return("SELL",100,99),1.0)

    def test_exact_horizon_close_uses_candle_close_time(self):
        frame=pd.DataFrame({
            "datetime":pd.to_datetime(["2026-09-14T17:45:00Z","2026-09-14T18:00:00Z"]),
            "open":[1,1],"high":[1,1],"low":[1,1],"close":[1.1,1.2]
        })
        target=pd.Timestamp("2026-09-14T18:00:00Z")
        # 17:45 candle closes exactly at 18:00 and must be used.
        self.assertAlmostEqual(a.exact_horizon_close(frame,target),1.1)

    def test_news_side(self):
        self.assertEqual(a.news_side(2.1),"BUY")
        self.assertEqual(a.news_side(-2.1),"SELL")
        self.assertEqual(a.news_side(1.9),"NEUTRAL")

    def test_validation_schema_has_timing_integrity(self):
        for c in ("signal_frozen_at","m15_candle_time","entry_time","auto_managed"):
            self.assertIn(c,a.VALIDATION_COLS)


    def test_market_closed_does_not_look_open_near_weekend_boundaries(self):
        fri_after_close = pd.Timestamp("2026-09-18T21:01:00Z")
        sun_before_open = pd.Timestamp("2026-09-20T20:59:00Z")
        sun_open = pd.Timestamp("2026-09-20T21:00:00Z")
        self.assertFalse(a.forex_market_likely_open(fri_after_close))
        self.assertFalse(a.forex_market_likely_open(sun_before_open))
        self.assertTrue(a.forex_market_likely_open(sun_open))

    def test_runtime_branch_is_never_a_code_branch(self):
        self.assertNotIn(a.BRANCH, {"main","atlasquant-dev"})

    def test_autopilot_source_keeps_real_execution_out_of_decision_evidence(self):
        from pathlib import Path
        text = Path("autopilot_v107.py").read_text(encoding="utf-8")
        self.assertIn('"real_orders": False', text)
        self.assertIn('"automatic_gate_change": False', text)
        self.assertIn('"automatic_promotion": False', text)

    def test_autopilot_persists_shadow_and_flight_evidence(self):
        from pathlib import Path
        text = Path("autopilot_v107.py").read_text(encoding="utf-8")
        self.assertIn("persist_shadow_samples", text)
        self.assertIn("persist_records", text)
        self.assertIn("build_pair_intelligence_packs", text)

    def test_main_has_autopilot_serialization_imports(self):
        from pathlib import Path
        text = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn("import base64", text[:2500])
        self.assertIn("import json", text[:2500])

if __name__=="__main__":
    unittest.main()
