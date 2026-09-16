import unittest
from unittest.mock import patch
import pandas as pd

from atlasquant_strategy_replay import generate_bos_choch_ob_signals
from atlasquant_operational_backtest import backtest_many


def candles(n=30):
    idx=pd.date_range("2026-09-15T00:00:00Z",periods=n,freq="15min",tz="UTC")
    close=[10.0+0.05*i for i in range(n)]
    return pd.DataFrame({
        "datetime":idx,
        "open":[x-0.02 for x in close],
        "high":[x+0.10 for x in close],
        "low":[x-0.10 for x in close],
        "close":close,
    })


class StrategyReplayTests(unittest.TestCase):
    def test_replay_emits_plan_only_on_current_structure_bar(self):
        d=candles(25)

        def fake_structure(prefix,side):
            if side=="BUY" and len(prefix)==20:
                return {
                    "event":"BOS","event_side":"BUY","bars_ago":0,
                    "level":10.5,"prior_bias":"BULLISH",
                    "break_margin":0.2,"noise_tolerance":0.01,
                }
            return {"event":"NONE","bars_ago":999}

        def fake_ob(prefix,side):
            if side=="BUY" and len(prefix)==20:
                return {
                    "structure_index":19,"zone_low":10.20,"zone_high":10.40,
                    "invalidated":False,"origin_index":17,
                }
            return {"structure_index":-1}

        with patch("atlasquant_strategy_replay.detect_bos_choch",side_effect=fake_structure), \
             patch("atlasquant_strategy_replay.detect_order_block",side_effect=fake_ob), \
             patch("atlasquant_strategy_replay._atr_last",return_value=1.0):
            rows=generate_bos_choch_ob_signals(
                d,pair="EUR/USD",rr_target=2.0,stop_buffer_atr=0.05,min_bars=20
            )

        self.assertEqual(len(rows),1)
        r=rows[0]
        self.assertEqual(r["side"],"BUY")
        self.assertEqual(r["setup"],"BOS+ORDER_BLOCK")
        self.assertAlmostEqual(r["entry"],10.30)
        self.assertAlmostEqual(r["stop"],10.15)
        self.assertAlmostEqual(r["target"],10.60)

    def test_choch_can_be_disabled(self):
        d=candles(22)
        with patch("atlasquant_strategy_replay.detect_bos_choch",return_value={
            "event":"CHOCH","event_side":"BUY","bars_ago":0
        }), patch("atlasquant_strategy_replay.detect_order_block",return_value={
            "structure_index":19,"zone_low":10.0,"zone_high":10.2,"invalidated":False
        }), patch("atlasquant_strategy_replay._atr_last",return_value=1.0):
            rows=generate_bos_choch_ob_signals(
                d,pair="EUR/USD",allow_choch=False,min_bars=20
            )
        self.assertEqual(rows,[])

    def test_sell_geometry_is_valid(self):
        d=candles(20)
        with patch("atlasquant_strategy_replay.detect_bos_choch",side_effect=lambda prefix,side: {
            "event":"BOS","event_side":"SELL","bars_ago":0
        } if side=="SELL" else {"event":"NONE","bars_ago":99}), \
             patch("atlasquant_strategy_replay.detect_order_block",side_effect=lambda prefix,side: {
            "structure_index":19,"zone_low":10.0,"zone_high":10.4,
            "invalidated":False,"origin_index":17
        } if side=="SELL" else {"structure_index":-1}), \
             patch("atlasquant_strategy_replay._atr_last",return_value=1.0):
            rows=generate_bos_choch_ob_signals(
                d,pair="GBP/USD",rr_target=2.0,stop_buffer_atr=0.1,min_bars=20
            )
        self.assertEqual(len(rows),1)
        r=rows[0]
        self.assertLess(r["target"],r["entry"])
        self.assertLess(r["entry"],r["stop"])

    def test_invalid_rr_fails_closed(self):
        with self.assertRaises(ValueError):
            generate_bos_choch_ob_signals(candles(),pair="EUR/USD",rr_target=0)

    def test_single_position_mode_blocks_overlapping_signal(self):
        d=pd.DataFrame({
            "datetime":pd.date_range("2026-09-15T00:00:00Z",periods=8,freq="15min",tz="UTC"),
            "open":[10]*8,
            "high":[10.2,10.2,10.4,10.5,10.6,12.2,10.5,10.5],
            "low":[9.8,9.8,9.9,9.9,9.9,9.9,9.9,9.9],
            "close":[10,10,10.1,10.2,10.3,12,10.2,10.2],
        })
        signals=[
            {"signal_time":d.iloc[0]["datetime"],"pair":"EUR/USD","setup":"A","side":"BUY","entry":10,"stop":9,"target":12},
            {"signal_time":d.iloc[2]["datetime"],"pair":"EUR/USD","setup":"B","side":"BUY","entry":10,"stop":9,"target":12},
        ]
        rows=backtest_many(
            {"EUR/USD":d},signals,
            single_position_per_pair=True,
            max_wait_bars=8,max_hold_bars=8,
        )
        self.assertEqual(rows[0]["outcome"],"GAIN")
        self.assertEqual(rows[1]["status"],"OVERLAP_BLOCKED")
        self.assertIsNone(rows[1]["net_r"])


if __name__=="__main__":
    unittest.main()
