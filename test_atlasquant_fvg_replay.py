import unittest
import pandas as pd

from atlasquant_fvg_replay import generate_fvg_signals
from atlasquant_operational_backtest import backtest_many, summarize_results


def frame(rows):
    d=pd.DataFrame(rows,columns=["open","high","low","close"])
    d["datetime"]=pd.date_range(
        "2026-09-15T00:00:00Z",periods=len(d),freq="15min",tz="UTC"
    )
    return d[["datetime","open","high","low","close"]]


class FVGReplayTests(unittest.TestCase):
    def test_bullish_fvg_generates_buy_plan(self):
        rows=[(10,10.2,9.8,10.0)]*13
        rows += [
            (10.0,10.0,9.8,9.9),
            (10.1,10.4,10.0,10.3),
            (10.5,10.8,10.3,10.7),
        ]
        d=frame(rows)
        sig=generate_fvg_signals(d,pair="EUR/USD",min_bars=14)
        buy=[x for x in sig if x["side"]=="BUY"]
        self.assertTrue(buy)
        r=buy[-1]
        self.assertEqual(r["setup"],"FVG")
        self.assertLess(r["stop"],r["entry"])
        self.assertLess(r["entry"],r["target"])
        self.assertAlmostEqual(r["fvg_zone_low"],10.0)
        self.assertAlmostEqual(r["fvg_zone_high"],10.3)

    def test_bearish_fvg_generates_sell_plan(self):
        rows=[(10,10.2,9.8,10.0)]*13
        rows += [
            (10.0,10.2,10.0,10.1),
            (9.9,10.0,9.6,9.7),
            (9.4,9.7,9.2,9.3),
        ]
        d=frame(rows)
        sig=generate_fvg_signals(d,pair="GBP/USD",min_bars=14)
        sell=[x for x in sig if x["side"]=="SELL"]
        self.assertTrue(sell)
        r=sell[-1]
        self.assertLess(r["target"],r["entry"])
        self.assertLess(r["entry"],r["stop"])
        self.assertAlmostEqual(r["fvg_zone_low"],9.7)
        self.assertAlmostEqual(r["fvg_zone_high"],10.0)

    def test_min_gap_atr_filters_tiny_gap(self):
        rows=[(10,10.2,9.8,10.0)]*13
        rows += [
            (10.0,10.00,9.9,10.0),
            (10.0,10.1,9.9,10.0),
            (10.0,10.2,10.01,10.1),
        ]
        d=frame(rows)
        sig=generate_fvg_signals(d,pair="EUR/USD",min_gap_atr=1.0,min_bars=14)
        self.assertEqual(sig,[])

    def test_side_filter_is_respected(self):
        rows=[(10,10.2,9.8,10.0)]*13
        rows += [
            (10.0,10.0,9.8,9.9),
            (10.1,10.4,10.0,10.3),
            (10.5,10.8,10.3,10.7),
        ]
        d=frame(rows)
        sig=generate_fvg_signals(d,pair="EUR/USD",allow_buy=False,min_bars=14)
        self.assertFalse(any(x["side"]=="BUY" for x in sig))

    def test_invalid_parameters_fail_closed(self):
        d=frame([(10,10.2,9.8,10.0)]*20)
        with self.assertRaises(ValueError):
            generate_fvg_signals(d,pair="EUR/USD",rr_target=0)
        with self.assertRaises(ValueError):
            generate_fvg_signals(d,pair="EUR/USD",min_gap_atr=-0.1)

    def test_fvg_results_remain_separate_from_other_setups(self):
        rows=[
            {"outcome":"GAIN","net_r":2.0,"setup":"FVG"},
            {"outcome":"LOSS","net_r":-1.0,"setup":"FVG"},
        ]
        m=summarize_results(rows)
        self.assertEqual(m["trades"],2)
        self.assertEqual(m["gains"],1)
        self.assertEqual(m["losses"],1)
        self.assertAlmostEqual(m["net_r"],1.0)

    def test_generated_signal_can_run_in_generic_backtester(self):
        rows=[(10,10.2,9.8,10.0)]*13
        rows += [
            (10.0,10.0,9.8,9.9),
            (10.1,10.4,10.0,10.3),
            (10.5,10.8,10.3,10.7),
            (10.7,10.9,10.1,10.5),
            (10.5,11.3,10.4,11.2),
        ]
        d=frame(rows)
        sig=generate_fvg_signals(d,pair="EUR/USD",rr_target=1.0,min_bars=14)
        self.assertTrue(sig)
        results=backtest_many({"EUR/USD":d},sig,single_position_per_pair=True)
        self.assertEqual(len(results),len(sig))


if __name__=="__main__":
    unittest.main()
