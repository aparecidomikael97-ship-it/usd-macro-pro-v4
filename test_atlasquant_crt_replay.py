import unittest
import pandas as pd

from atlasquant_crt_replay import generate_crt_signals
from atlasquant_operational_backtest import backtest_many


def frame(rows):
    d=pd.DataFrame(rows,columns=["open","high","low","close"])
    d["datetime"]=pd.date_range(
        "2026-09-15T00:00:00Z",periods=len(d),freq="15min",tz="UTC"
    )
    return d[["datetime","open","high","low","close"]]


def prefix():
    return [(10.5,11.0,10.0,10.5)]*11


class CRTReplayTests(unittest.TestCase):
    def test_buy_crt_matches_anchor_raid_delivery_rule(self):
        d=frame(prefix()+[
            (11.0,12.0,10.0,11.0),   # anchor
            (10.6,11.0,9.5,10.5),    # sweep SSL + reclaim
            (10.5,11.4,10.4,11.2),   # delivery above mid and c2 close
        ])
        rows=generate_crt_signals(d,pair="EUR/USD")
        self.assertEqual(len(rows),1)
        r=rows[0]
        self.assertEqual(r["side"],"BUY")
        self.assertEqual(r["raid_side"],"SSL")
        self.assertAlmostEqual(r["entry"],11.2)
        self.assertAlmostEqual(r["target"],12.0)
        self.assertLess(r["stop"],r["entry"])
        self.assertGreater(r["setup_rr"],0)

    def test_sell_crt_matches_anchor_raid_delivery_rule(self):
        d=frame(prefix()+[
            (11.0,12.0,10.0,11.0),
            (11.4,12.5,11.0,11.5),   # sweep BSL + reclaim
            (11.5,11.6,10.6,10.8),   # delivery below mid
        ])
        rows=generate_crt_signals(d,pair="GBP/USD")
        self.assertEqual(len(rows),1)
        r=rows[0]
        self.assertEqual(r["side"],"SELL")
        self.assertEqual(r["raid_side"],"BSL")
        self.assertAlmostEqual(r["entry"],10.8)
        self.assertAlmostEqual(r["target"],10.0)
        self.assertLess(r["target"],r["entry"])
        self.assertLess(r["entry"],r["stop"])

    def test_raid_without_reclaim_does_not_signal(self):
        d=frame(prefix()+[
            (11.0,12.0,10.0,11.0),
            (9.8,10.8,9.4,9.7),      # closes below anchor low
            (9.7,11.5,9.6,11.2),
        ])
        rows=generate_crt_signals(d,pair="EUR/USD")
        self.assertEqual(rows,[])

    def test_delivery_must_confirm_midpoint_and_direction(self):
        d=frame(prefix()+[
            (11.0,12.0,10.0,11.0),
            (10.6,11.0,9.5,10.5),
            (10.5,10.9,10.2,10.8),   # below anchor midpoint 11
        ])
        rows=generate_crt_signals(d,pair="EUR/USD")
        self.assertEqual(rows,[])

    def test_min_rr_filter_is_fail_closed(self):
        d=frame(prefix()+[
            (11.0,12.0,10.0,11.0),
            (10.6,11.0,9.5,10.5),
            (10.5,11.4,10.4,11.2),
        ])
        rows=generate_crt_signals(d,pair="EUR/USD",min_rr=10.0)
        self.assertEqual(rows,[])

    def test_invalid_parameters_fail_closed(self):
        d=frame(prefix()+[(11,12,10,11),(10.6,11,9.5,10.5),(10.5,11.4,10.4,11.2)])
        with self.assertRaises(ValueError):
            generate_crt_signals(d,pair="EUR/USD",stop_buffer_atr=-0.1)
        with self.assertRaises(ValueError):
            generate_crt_signals(d,pair="EUR/USD",min_rr=-1.0)

    def test_generated_crt_runs_in_generic_backtester(self):
        d=frame(prefix()+[
            (11.0,12.0,10.0,11.0),
            (10.6,11.0,9.5,10.5),
            (10.5,11.4,10.4,11.2),
            (11.2,11.3,11.0,11.1),
            (11.1,12.1,11.0,12.0),
        ])
        sig=generate_crt_signals(d,pair="EUR/USD")
        self.assertTrue(sig)
        results=backtest_many({"EUR/USD":d},sig,single_position_per_pair=True)
        self.assertEqual(len(results),len(sig))


if __name__=="__main__":
    unittest.main()
