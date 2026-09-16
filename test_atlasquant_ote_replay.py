import unittest
import pandas as pd

from atlasquant_ote_replay import _impulse_range, generate_ote_signals
from atlasquant_operational_backtest import backtest_many


def frame(rows):
    d=pd.DataFrame(rows,columns=["open","high","low","close"])
    d["datetime"]=pd.date_range(
        "2026-09-15T00:00:00Z",periods=len(d),freq="15min",tz="UTC"
    )
    return d[["datetime","open","high","low","close"]]


def buy_case():
    rows=[(10.0,10.2,9.8,10.0)]*16
    rows += [
        (9.5,10.0,9.0,9.4),
        (9.4,10.2,9.3,10.0),
        (10.0,10.8,9.9,10.6),
        (10.6,11.4,10.5,11.2),
        (11.2,12.0,11.1,11.8),
        (11.8,12.6,11.7,12.4),
        (12.4,13.0,12.3,12.8),
        (12.8,13.2,12.7,13.0),
        (13.0,13.1,12.0,12.2),
        (12.2,12.3,11.0,11.2),
        (11.2,11.3,10.6,10.8),
        (10.8,10.9,10.1,10.3),
        (10.3,10.8,10.0,10.6),
        (10.6,12.0,10.5,11.8),
    ]
    return frame(rows)


class OTEReplayTests(unittest.TestCase):
    def test_buy_impulse_matches_engine_geometry(self):
        d=buy_case().iloc[:28]
        imp=_impulse_range(d,"BUY")
        self.assertIsNotNone(imp)
        self.assertAlmostEqual(imp["swing_low"],9.0)
        self.assertAlmostEqual(imp["swing_high"],13.2)

    def test_buy_ote_emits_once_per_impulse(self):
        d=buy_case()
        rows=generate_ote_signals(
            d,pair="EUR/USD",allow_sell=False,min_bars=28,stop_buffer_atr=0.0
        )
        self.assertEqual(len(rows),1)
        r=rows[0]
        self.assertEqual(r["side"],"BUY")
        self.assertEqual(r["setup"],"OTE")
        self.assertGreaterEqual(r["retracement_pct"],62.0)
        self.assertLessEqual(r["retracement_pct"],79.0)
        self.assertAlmostEqual(r["entry"],r["ote_sweet_705"])
        self.assertLess(r["stop"],r["entry"])
        self.assertLess(r["entry"],r["target"])

    def test_sell_geometry_is_valid(self):
        d=buy_case().copy()
        pivot=11.0
        for c in ("open","high","low","close"):
            d[c]=2*pivot-d[c]
        rows=generate_ote_signals(
            d,pair="GBP/USD",allow_buy=False,min_bars=28,stop_buffer_atr=0.0
        )
        self.assertTrue(rows)
        r=rows[0]
        self.assertEqual(r["side"],"SELL")
        self.assertLess(r["target"],r["entry"])
        self.assertLess(r["entry"],r["stop"])

    def test_impulse_filter_can_reject_small_ranges(self):
        d=buy_case()
        rows=generate_ote_signals(
            d,pair="EUR/USD",allow_sell=False,min_impulse_atr=100.0,min_bars=28
        )
        self.assertEqual(rows,[])

    def test_invalid_parameters_fail_closed(self):
        d=buy_case()
        with self.assertRaises(ValueError):
            generate_ote_signals(d,pair="EUR/USD",rr_target=0)
        with self.assertRaises(ValueError):
            generate_ote_signals(d,pair="EUR/USD",lookback=6)
        with self.assertRaises(ValueError):
            generate_ote_signals(d,pair="EUR/USD",entry_mode="BAD")

    def test_generated_ote_runs_in_generic_backtester(self):
        d=buy_case()
        sig=generate_ote_signals(
            d,pair="EUR/USD",allow_sell=False,min_bars=28,rr_target=1.0
        )
        self.assertTrue(sig)
        results=backtest_many({"EUR/USD":d},sig,single_position_per_pair=True)
        self.assertEqual(len(results),len(sig))


if __name__=="__main__":
    unittest.main()
