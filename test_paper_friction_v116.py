import math
import unittest
from unittest.mock import patch
import pandas as pd
import paper_friction_v116 as f
import autopilot_paper_v112 as paper_runner
import autopilot_model_paper_v1 as model_runner

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


    def test_autopilot_persists_costed_ledger_and_status(self):
        closed=pd.DataFrame([{
            "trade_id":"x3","status":"CLOSED","result":"WIN","realized_r":2.0,
        }])
        saved_csv={}
        saved_json={}

        def fake_get_json(path,default):
            return {}, ""

        def fake_get_csv(path):
            return pd.DataFrame(), ""

        def fake_put_csv(path,frame,message):
            saved_csv[path]=frame.copy()
            return True, ""

        def fake_put_json(path,payload,message):
            saved_json[path]=dict(payload)
            return True, ""

        legacy_summary={
            "trades_total":1,"pending_entries":0,"open_positions":0,"closed_trades":1,
            "wins":1,"losses":0,"breakeven":0,"win_rate_pct":100.0,
            "net_r":2.0,"avg_r":2.0,"profit_factor_r":None,
        }

        with patch.object(paper_runner.base,"gh_get_json",side_effect=fake_get_json), \
             patch.object(paper_runner.base,"gh_get_csv",side_effect=fake_get_csv), \
             patch.object(paper_runner.base,"gh_put_csv",side_effect=fake_put_csv), \
             patch.object(paper_runner.base,"gh_put_json",side_effect=fake_put_json), \
             patch.object(paper_runner,"run_paper_cycle",return_value=(closed,{"trades_closed":1})), \
             patch.object(paper_runner,"summarize_paper_trades",return_value=legacy_summary):
            ok,summary,errors=paper_runner._paper_cycle()

        self.assertTrue(ok)
        self.assertEqual(errors,[])
        persisted=saved_csv[paper_runner.PAPER_CSV_PATH]
        self.assertAlmostEqual(float(persisted.iloc[0]["gross_r"]),2.0,places=8)
        self.assertAlmostEqual(float(persisted.iloc[0]["total_friction_r"]),f.DEFAULT_TOTAL_R,places=8)
        self.assertAlmostEqual(float(persisted.iloc[0]["net_r"]),2.0-f.DEFAULT_TOTAL_R,places=8)
        self.assertAlmostEqual(float(summary["net_r_after_friction"]),2.0-f.DEFAULT_TOTAL_R,places=8)
        status=saved_json[paper_runner.base.STATUS_PATH]["paper_trading_v112"]
        self.assertEqual(status["friction_version"],"V11.6_PAPER_FRICTION")
        self.assertAlmostEqual(float(status["net_r_after_friction"]),2.0-f.DEFAULT_TOTAL_R,places=8)
        self.assertFalse(summary["safety"]["friction_changes_signal"])
        self.assertFalse(summary["safety"]["friction_changes_result_classification"])



    def test_model_paper_runner_persists_separate_ledger_without_market_provider_calls(self):
        ledger=pd.DataFrame([{
            "trade_id":"e1","signal_id":"e1","pair":"EUR/USD","side":"BUY",
            "setup_id":"fvg","setup_attribution":"SOURCE_MODEL_EXPLICIT",
            "status":"CLOSED","result":"WIN","realized_r":2.0,
            "data_quality_pct":95.0,"d1_regime":"TREND","w1_regime":"EXPANSION",
            "active_session":"London",
        }])
        saved_csv={}
        saved_json={}

        def fake_get_json(path,default):
            if path==model_runner.base.STATUS_PATH:
                return {}, ""
            return {}, ""

        def fake_get_csv(path):
            return pd.DataFrame(), ""

        def fake_put_csv(path,frame,message):
            saved_csv[path]=frame.copy()
            return True, ""

        def fake_put_json(path,payload,message):
            saved_json[path]=dict(payload)
            return True, ""

        with patch.object(model_runner.base,"gh_get_json",side_effect=fake_get_json), \
             patch.object(model_runner.base,"gh_get_csv",side_effect=fake_get_csv), \
             patch.object(model_runner.base,"gh_put_csv",side_effect=fake_put_csv), \
             patch.object(model_runner.base,"gh_put_json",side_effect=fake_put_json), \
             patch.object(model_runner.base,"utcnow",return_value=pd.Timestamp("2026-09-20T12:00:00Z")), \
             patch.object(model_runner,"run_model_paper_cycle",return_value=(ledger,{"new_candidates_observed":1})):
            ok,summary,errors=model_runner._model_paper_cycle()

        self.assertTrue(ok)
        self.assertEqual(errors,[])
        self.assertIn(model_runner.MODEL_PAPER_CSV_PATH,saved_csv)
        self.assertIn(model_runner.MODEL_PAPER_SUMMARY_PATH,saved_json)
        persisted=saved_csv[model_runner.MODEL_PAPER_CSV_PATH]
        self.assertAlmostEqual(float(persisted.iloc[0]["net_r"]),2.0-f.DEFAULT_TOTAL_R,places=8)
        status=saved_json[model_runner.base.STATUS_PATH]["model_paper_v1"]
        self.assertFalse(status["real_orders"])
        self.assertIn("by_setup",status)
        self.assertFalse(summary["safety"]["additional_market_data_calls"])

if __name__=="__main__":
    unittest.main()
