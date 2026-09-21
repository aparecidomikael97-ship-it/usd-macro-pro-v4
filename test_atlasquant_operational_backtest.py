import unittest
import pandas as pd

from atlasquant_operational_backtest import (
    backtest_signal,
    backtest_many,
    summarize_results,
    summarize_by,
    ledger_frame,
    normalize_candles,
)


def candles(rows):
    d = pd.DataFrame(rows, columns=["open","high","low","close"])
    d["datetime"] = pd.date_range(
        "2026-09-15T00:00:00Z", periods=len(d), freq="15min", tz="UTC"
    )
    return d[["datetime","open","high","low","close"]]


class OperationalBacktestTests(unittest.TestCase):
    def test_buy_target_is_gain_in_r(self):
        d=candles([
            (10,10.2,9.8,10.0),
            (10,10.1,9.9,10.0),
            (10,10.5,9.9,10.4),
            (10.4,12.2,10.2,12.0),
        ])
        s={"signal_time":d.iloc[0]["datetime"],"pair":"EUR/USD","setup":"OB+CHOCH",
           "side":"BUY","entry":10.0,"stop":9.0,"target":12.0}
        r=backtest_signal(d,s)
        self.assertEqual(r["outcome"],"GAIN")
        self.assertEqual(r["status"],"TARGET")
        self.assertEqual(r["net_r"],2.0)

    def test_sell_target_is_gain(self):
        d=candles([
            (10,10.2,9.8,10.0),
            (10,10.2,9.9,10.0),
            (10,10.1,8.8,9.0),
        ])
        s={"signal_time":d.iloc[0]["datetime"],"pair":"GBP/USD","setup":"BOS+OB",
           "side":"SELL","entry":10.0,"stop":11.0,"target":9.0}
        r=backtest_signal(d,s)
        self.assertEqual(r["outcome"],"GAIN")
        self.assertEqual(r["net_r"],1.0)

    def test_same_bar_stop_and_target_is_loss(self):
        d=candles([
            (10,10.2,9.8,10.0),
            (10,12.2,8.8,10.5),
        ])
        s={"signal_time":d.iloc[0]["datetime"],"side":"BUY",
           "entry":10.0,"stop":9.0,"target":12.0}
        r=backtest_signal(d,s)
        self.assertEqual(r["status"],"AMBIGUOUS_SAME_BAR_STOP_FIRST")
        self.assertEqual(r["outcome"],"LOSS")
        self.assertEqual(r["net_r"],-1.0)
        self.assertTrue(r["same_bar_ambiguous"])

    def test_no_lookahead_starts_after_signal_bar(self):
        d=candles([
            (10,12.5,8.5,11.0),  # would touch everything, but this is signal bar
            (11,11.5,10.5,11.0),
            (11,11.3,10.7,11.0),
        ])
        s={"signal_time":d.iloc[0]["datetime"],"side":"BUY",
           "entry":10.0,"stop":9.0,"target":12.0}
        r=backtest_signal(d,s,max_wait_bars=2)
        self.assertEqual(r["status"],"NO_ENTRY")
        self.assertEqual(r["outcome"],"NO_TRADE")

    def test_time_exit_marks_observed_result(self):
        d=candles([
            (10,10.1,9.9,10.0),
            (10,10.2,9.9,10.0),
            (10,10.6,9.8,10.5),
            (10.5,10.7,10.3,10.5),
        ])
        s={"signal_time":d.iloc[0]["datetime"],"side":"BUY",
           "entry":10.0,"stop":9.0,"target":12.0}
        r=backtest_signal(d,s,max_hold_bars=3)
        self.assertEqual(r["status"],"TIME_EXIT")
        self.assertEqual(r["outcome"],"GAIN")
        self.assertAlmostEqual(r["net_r"],0.5,places=6)

    def test_invalid_geometry_fails_closed(self):
        d=candles([(10,10.2,9.8,10.0),(10,10.2,9.8,10.0)])
        s={"signal_time":d.iloc[0]["datetime"],"side":"BUY",
           "entry":10.0,"stop":11.0,"target":12.0}
        r=backtest_signal(d,s)
        self.assertEqual(r["status"],"INVALID_PLAN")
        self.assertEqual(r["outcome"],"NO_TRADE")
        self.assertIsNone(r["net_r"])

    def test_cost_and_slippage_are_both_deducted_in_r(self):
        d=candles([
            (10,10.2,9.8,10.0),
            (10,10.1,9.9,10.0),
            (10,12.2,9.9,12.0),
        ])
        plan={"signal_time":d.iloc[0]["datetime"],"side":"BUY",
              "entry":10.0,"stop":9.0,"target":12.0}
        r=backtest_signal(d,plan,cost_r=0.10,slippage_r=0.05)
        self.assertEqual(r["status"],"TARGET")
        self.assertAlmostEqual(r["gross_r"],2.0)
        self.assertAlmostEqual(r["cost_r"],0.10)
        self.assertAlmostEqual(r["slippage_r"],0.05)
        self.assertAlmostEqual(r["total_friction_r"],0.15)
        self.assertAlmostEqual(r["net_r"],1.85)

    def test_negative_friction_fails_closed(self):
        d=candles([(10,10.2,9.8,10.0),(10,10.2,9.8,10.0)])
        plan={"signal_time":d.iloc[0]["datetime"],"side":"BUY",
              "entry":10.0,"stop":9.0,"target":12.0}
        r=backtest_signal(d,plan,slippage_r=-0.01)
        self.assertEqual(r["status"],"INVALID_FRICTION")
        self.assertEqual(r["outcome"],"NO_TRADE")
        self.assertIsNone(r["net_r"])

    def test_nonfinite_friction_fails_closed(self):
        d=candles([(10,10.2,9.8,10.0),(10,10.2,9.8,10.0)])
        plan={"signal_time":d.iloc[0]["datetime"],"side":"BUY",
              "entry":10.0,"stop":9.0,"target":12.0}
        for value in (float("nan"),float("inf")):
            r=backtest_signal(d,plan,cost_r=value)
            self.assertEqual(r["status"],"INVALID_FRICTION")
            self.assertEqual(r["outcome"],"NO_TRADE")
            self.assertIsNone(r["net_r"])

    def test_single_position_per_pair_blocks_overlapping_signal(self):
        d=candles([
            (10,10.1,9.9,10.0),
            (10,10.2,9.9,10.0),
            (10,12.2,9.9,12.0),
            (12,12.1,11.9,12.0),
        ])
        signals=[
            {"signal_time":d.iloc[0]["datetime"],"pair":"EUR/USD","side":"BUY","entry":10,"stop":9,"target":12},
            {"signal_time":d.iloc[1]["datetime"],"pair":"EUR/USD","side":"BUY","entry":10,"stop":9,"target":12},
        ]
        rows=backtest_many({"EUR/USD":d},signals,single_position_per_pair=True)
        self.assertEqual(rows[0]["outcome"],"GAIN")
        self.assertEqual(rows[1]["status"],"OVERLAP_BLOCKED")
        self.assertEqual(rows[1]["outcome"],"NO_TRADE")

    def test_summary_counts_gain_loss_be_and_streaks(self):
        rows=[
            {"outcome":"GAIN","net_r":2.0},
            {"outcome":"GAIN","net_r":1.0},
            {"outcome":"LOSS","net_r":-1.0},
            {"outcome":"LOSS","net_r":-1.0},
            {"outcome":"BREAKEVEN","net_r":0.0},
            {"outcome":"NO_TRADE","net_r":None},
        ]
        m=summarize_results(rows)
        self.assertEqual(m["trades"],5)
        self.assertEqual(m["gains"],2)
        self.assertEqual(m["losses"],2)
        self.assertEqual(m["breakeven"],1)
        self.assertEqual(m["no_trade"],1)
        self.assertEqual(m["max_gain_streak"],2)
        self.assertEqual(m["max_loss_streak"],2)
        self.assertAlmostEqual(m["net_r"],1.0)

    def test_many_grouping_and_ledger(self):
        d=candles([
            (10,10.1,9.9,10.0),
            (10,10.2,9.9,10.0),
            (10,12.2,9.9,12.0),
        ])
        signals=[
            {"signal_time":d.iloc[0]["datetime"],"pair":"EUR/USD","setup":"OB",
             "session":"London","side":"BUY","entry":10,"stop":9,"target":12},
            {"signal_time":d.iloc[0]["datetime"],"pair":"EUR/USD","setup":"FVG",
             "session":"London","side":"BUY","entry":10,"stop":9,"target":12},
        ]
        rows=backtest_many({"EUR/USD":d},signals)
        self.assertEqual(len(rows),2)
        g=summarize_by(rows,"setup")
        self.assertEqual(set(g["setup"]),{"OB","FVG"})
        ledger=ledger_frame(rows)
        self.assertIn("net_r",ledger.columns)
        self.assertIn("setup",ledger.columns)

    def test_zero_or_negative_windows_fail_closed(self):
        d=candles([(10,10.2,9.8,10.0),(10,10.2,9.8,10.0)])
        plan={"signal_time":d.iloc[0]["datetime"],"side":"BUY","entry":10,"stop":9,"target":12}
        for kwargs in ({"max_wait_bars":0},{"max_hold_bars":0},{"max_wait_bars":-1},{"max_hold_bars":-1}):
            with self.subTest(kwargs=kwargs):
                r=backtest_signal(d,plan,**kwargs)
                self.assertEqual(r["status"],"INVALID_WINDOW")
                self.assertEqual(r["outcome"],"NO_TRADE")
                self.assertIsNone(r["net_r"])

    def test_malformed_and_nonfinite_candles_fail_closed(self):
        d=pd.DataFrame([
            {"datetime":"bad","open":10,"high":11,"low":9,"close":10},
            {"datetime":"2026-09-15T00:15:00Z","open":10,"high":9,"low":8,"close":10},
            {"datetime":"2026-09-15T00:30:00Z","open":10,"high":float("inf"),"low":9,"close":10},
        ])
        plan={"signal_time":"2026-09-15T00:00:00Z","side":"BUY","entry":10,"stop":9,"target":12}
        r=backtest_signal(d,plan)
        self.assertEqual(r["status"],"NO_DATA")
        self.assertEqual(r["outcome"],"NO_TRADE")

    def test_duplicate_candle_timestamp_keep_last_is_deterministic(self):
        d=pd.DataFrame([
            {"datetime":"2026-09-15T00:00:00Z","open":10,"high":10.2,"low":9.8,"close":10},
            {"datetime":"2026-09-15T00:15:00Z","open":10,"high":10.2,"low":9.8,"close":10},
            {"datetime":"2026-09-15T00:15:00Z","open":10,"high":12.2,"low":9.9,"close":12},
        ])
        plan={"signal_time":"2026-09-15T00:00:00Z","side":"BUY","entry":10,"stop":9,"target":12}
        a=backtest_signal(d,plan)
        b=backtest_signal(d,plan)
        self.assertEqual(a["status"],"TARGET")
        self.assertEqual(a,b)

    def test_separate_pairs_may_overlap(self):
        d=candles([(10,10.1,9.9,10),(10,10.2,9.9,10),(10,12.2,9.9,12)])
        signals=[
            {"signal_time":d.iloc[0]["datetime"],"pair":"EUR/USD","side":"BUY","entry":10,"stop":9,"target":12},
            {"signal_time":d.iloc[0]["datetime"],"pair":"GBP/USD","side":"BUY","entry":10,"stop":9,"target":12},
        ]
        rows=backtest_many({"EUR/USD":d,"GBP/USD":d},signals,single_position_per_pair=True)
        self.assertEqual([r["outcome"] for r in rows],["GAIN","GAIN"])


    def test_point_in_time_diagnostic_context_is_preserved_on_result(self):
        d=candles([
            (10,10.1,9.9,10.0),
            (10,10.2,9.9,10.0),
            (10,12.2,9.9,12.0),
        ])
        plan={
            "signal_time":d.iloc[0]["datetime"],
            "pair":"EUR/USD",
            "setup":"FVG",
            "side":"BUY",
            "entry":10.0,
            "stop":9.0,
            "target":12.0,
            "macro_alignment":1,
            "technical_confirmation":True,
            "liquidity_confirmation":True,
            "regime_fit":True,
            "regime":"TREND",
            "known_high_impact_event":False,
            "data_quality_pct":94,
            "plan_followed":True,
            "event_label":"CPI",
            "event_impact":"HIGH",
            "event_time":"2026-09-15T00:20:00+00:00",
            "event_known_before_entry":True,
        }
        out=backtest_signal(d,plan)
        self.assertEqual(out["outcome"],"GAIN")
        self.assertEqual(out["macro_alignment"],1)
        self.assertTrue(out["technical_confirmation"])
        self.assertEqual(out["regime"],"TREND")
        self.assertEqual(out["data_quality_pct"],94)
        self.assertEqual(out["event_label"],"CPI")


    def test_timeframe_and_trading_style_are_preserved_in_result_and_ledger(self):
        d=candles([
            (10,10.1,9.9,10.0),
            (10,10.2,9.9,10.0),
            (10,12.2,9.9,12.0),
        ])
        plan={"signal_time":d.iloc[0]["datetime"],"pair":"EUR/USD","setup":"FVG",
              "timeframe":"H4","trading_style":"SWING","side":"BUY",
              "entry":10.0,"stop":9.0,"target":12.0}
        out=backtest_signal(d,plan)
        self.assertEqual(out["timeframe"],"H4")
        self.assertEqual(out["trading_style"],"SWING")
        ledger=ledger_frame([out])
        self.assertEqual(ledger.iloc[0]["timeframe"],"H4")
        self.assertEqual(ledger.iloc[0]["trading_style"],"SWING")

    def test_mixed_timestamp_formats_are_normalized_without_losing_valid_rows(self):
        d=pd.DataFrame([
            {"datetime":"2026-09-15T00:00:00Z","open":10,"high":10.2,"low":9.8,"close":10},
            {"datetime":"2026-09-15 00:15:00+00:00","open":10,"high":10.3,"low":9.9,"close":10.1},
        ])
        out=normalize_candles(d)
        self.assertEqual(len(out),2)
        self.assertTrue(str(out.iloc[0]["datetime"].tzinfo))



if __name__=="__main__":
    unittest.main()
