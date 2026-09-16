import unittest
import pandas as pd

from atlasquant_amd_replay import generate_amd_signals
from atlasquant_operational_backtest import backtest_many


def frame(rows):
    d=pd.DataFrame(rows,columns=["open","high","low","close"])
    d["datetime"]=pd.date_range(
        "2026-09-15T00:00:00Z",periods=len(d),freq="15min",tz="UTC"
    )
    return d[["datetime","open","high","low","close"]]


def acc_prefix():
    rows=[]
    for i in range(8):
        rows.append((10.4,11.0,10.0,10.5))
    return rows


class AMDReplayTests(unittest.TestCase):
    def test_buy_requires_accumulation_then_manipulation_then_later_distribution(self):
        d=frame(
            acc_prefix()
            + [
                (10.4,10.8,9.6,10.2),   # manipulation: SSL sweep + reclaim
                (10.2,10.7,10.1,10.4),  # still below mid=10.5
                (10.4,10.9,10.3,10.7),  # distribution
                (10.7,11.1,10.6,11.0),
            ]
        )
        rows=generate_amd_signals(
            d,pair="EUR/USD",accumulation_bars=8,max_distribution_bars=4,min_bars=9
        )
        self.assertEqual(len(rows),1)
        r=rows[0]
        self.assertEqual(r["side"],"BUY")
        self.assertEqual(r["setup"],"AMD_PO3")
        self.assertEqual(r["manipulation_index"],8)
        self.assertEqual(r["distribution_index"],10)
        self.assertGreater(r["distribution_index"],r["manipulation_index"])
        self.assertEqual(r["manipulation_side"],"SSL")
        self.assertAlmostEqual(r["acc_high"],11.0)
        self.assertAlmostEqual(r["acc_low"],10.0)
        self.assertLess(r["stop"],r["entry"])
        self.assertLess(r["entry"],r["target"])

    def test_sell_sequence_is_mirrored(self):
        d=frame(
            acc_prefix()
            + [
                (10.6,11.4,10.2,10.8),  # BSL sweep + reclaim
                (10.8,10.9,10.4,10.6),
                (10.6,10.7,10.1,10.3),  # distribution below mid and manip close
                (10.3,10.4,9.9,10.0),
            ]
        )
        rows=generate_amd_signals(
            d,pair="GBP/USD",accumulation_bars=8,max_distribution_bars=4,min_bars=9
        )
        self.assertEqual(len(rows),1)
        r=rows[0]
        self.assertEqual(r["side"],"SELL")
        self.assertEqual(r["manipulation_side"],"BSL")
        self.assertEqual(r["manipulation_index"],8)
        self.assertEqual(r["distribution_index"],10)
        self.assertLess(r["target"],r["entry"])
        self.assertLess(r["entry"],r["stop"])

    def test_same_candle_cannot_be_manipulation_and_distribution(self):
        d=frame(
            acc_prefix()
            + [
                (10.4,11.2,9.6,10.8),  # manip BUY, also > mid, but same candle must not distribute
                (10.8,10.9,10.2,10.6), # later valid distribution
            ]
        )
        rows=generate_amd_signals(
            d,pair="EUR/USD",accumulation_bars=8,max_distribution_bars=2,min_bars=9,
            allow_sell=False
        )
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["manipulation_index"],8)
        self.assertEqual(rows[0]["distribution_index"],9)

    def test_distribution_must_occur_before_expiry(self):
        d=frame(
            acc_prefix()
            + [
                (10.4,10.8,9.6,10.2),  # manipulation
                (10.2,10.4,10.1,10.3),
                (10.3,10.4,10.2,10.3),
                (10.3,10.8,10.2,10.7), # too late if max_distribution_bars=2
            ]
        )
        rows=generate_amd_signals(
            d,pair="EUR/USD",accumulation_bars=8,max_distribution_bars=2,min_bars=9,
            allow_sell=False
        )
        self.assertEqual(rows,[])

    def test_no_reclaim_means_no_manipulation_state(self):
        d=frame(
            acc_prefix()
            + [
                (10.1,10.4,9.6,9.8),  # closes below acc low, no reclaim
                (9.8,10.9,9.7,10.7),
            ]
        )
        rows=generate_amd_signals(
            d,pair="EUR/USD",accumulation_bars=8,max_distribution_bars=3,min_bars=9,
            allow_sell=False
        )
        self.assertEqual(rows,[])

    def test_two_sided_sweep_chooses_deeper_manipulation_deterministically(self):
        d=frame(
            acc_prefix()
            + [
                (10.5,11.2,9.5,10.5),  # both sides swept; BUY depth 0.5 > SELL depth 0.2
                (10.5,10.9,10.4,10.7),
            ]
        )
        rows=generate_amd_signals(
            d,pair="EUR/USD",accumulation_bars=8,max_distribution_bars=2,min_bars=9
        )
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["side"],"BUY")
        self.assertEqual(rows[0]["manipulation_side"],"SSL")

    def test_min_rr_filter_is_fail_closed(self):
        d=frame(
            acc_prefix()
            + [
                (10.4,10.8,9.6,10.2),
                (10.2,10.9,10.1,10.7),
            ]
        )
        rows=generate_amd_signals(
            d,pair="EUR/USD",accumulation_bars=8,max_distribution_bars=3,min_bars=9,
            min_rr=10.0,allow_sell=False
        )
        self.assertEqual(rows,[])

    def test_invalid_parameters_fail_closed(self):
        d=frame(acc_prefix()+[(10.4,10.8,9.6,10.2),(10.2,10.9,10.1,10.7)])
        with self.assertRaises(ValueError):
            generate_amd_signals(d,pair="EUR/USD",accumulation_bars=3)
        with self.assertRaises(ValueError):
            generate_amd_signals(d,pair="EUR/USD",max_distribution_bars=0)
        with self.assertRaises(ValueError):
            generate_amd_signals(d,pair="EUR/USD",stop_buffer_atr=-0.1)
        with self.assertRaises(ValueError):
            generate_amd_signals(d,pair="EUR/USD",min_rr=-1)

    def test_generated_amd_runs_in_generic_backtester(self):
        d=frame(
            acc_prefix()
            + [
                (10.4,10.8,9.6,10.2),
                (10.2,10.9,10.1,10.7),
                (10.7,11.1,10.6,11.0),
            ]
        )
        sig=generate_amd_signals(
            d,pair="EUR/USD",accumulation_bars=8,max_distribution_bars=3,min_bars=9,
            allow_sell=False
        )
        self.assertTrue(sig)
        results=backtest_many({"EUR/USD":d},sig,single_position_per_pair=True)
        self.assertEqual(len(results),len(sig))


if __name__=="__main__":
    unittest.main()
