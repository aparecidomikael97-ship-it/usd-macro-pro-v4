import unittest

import pandas as pd

from atlasquant_backtest_context import enrich_signals_point_in_time
from atlasquant_multitimeframe_alignment import alignment_gate
from atlasquant_operational_backtest import backtest_signal


class MultiTimeframeAlignmentTests(unittest.TestCase):
    def _candles(self):
        return pd.DataFrame({
            "datetime":pd.date_range("2026-09-15T00:00:00Z",periods=4,freq="4h",tz="UTC"),
            "open":[10.0,10.0,10.0,12.0],
            "high":[10.1,10.2,12.2,12.1],
            "low":[9.9,9.9,9.9,11.9],
            "close":[10.0,10.0,12.0,12.0],
        })

    def _plan(self, **extra):
        row={
            "signal_time":"2026-09-15T00:00:00Z",
            "pair":"EUR/USD","setup":"FVG","timeframe":"H4","trading_style":"SWING",
            "side":"BUY","entry":10.0,"stop":9.0,"target":12.0,
        }
        row.update(extra)
        return row

    def test_missing_alignment_evidence_fails_closed(self):
        gate=alignment_gate({},timeframe="H4",strict=True)
        self.assertFalse(gate["passed"])
        self.assertEqual(set(gate["missing"]),{
            "reading_aligned","direction_aligned","filters_aligned","trigger_aligned",
        })
        self.assertEqual(gate["context_timeframes"],["D1","W1"])
        self.assertFalse(gate["real_orders_enabled"])

    def test_any_failed_alignment_blocks_execution_grade_test(self):
        gate=alignment_gate({
            "reading_aligned":True,
            "direction_aligned":True,
            "filters_aligned":False,
            "trigger_aligned":True,
        },timeframe="H1")
        self.assertFalse(gate["passed"])
        self.assertEqual(gate["failed"],["filters_aligned"])

    def test_all_four_alignment_layers_are_required(self):
        gate=alignment_gate({
            "reading_aligned":True,
            "direction_aligned":True,
            "filters_aligned":True,
            "trigger_aligned":True,
        },timeframe="W1")
        self.assertTrue(gate["passed"])
        self.assertEqual(gate["reason"],"ALINHADO")

    def test_backtest_blocks_signal_without_alignment(self):
        out=backtest_signal(self._candles(),self._plan(),require_alignment=True)
        self.assertEqual(out["status"],"ALIGNMENT_BLOCKED")
        self.assertEqual(out["outcome"],"NO_TRADE")
        self.assertIsNone(out["net_r"])

    def test_backtest_allows_aligned_signal_to_reach_price_simulation(self):
        out=backtest_signal(
            self._candles(),
            self._plan(
                reading_aligned=True,
                direction_aligned=True,
                filters_aligned=True,
                trigger_aligned=True,
            ),
            require_alignment=True,
        )
        self.assertEqual(out["status"],"TARGET")
        self.assertEqual(out["outcome"],"GAIN")
        self.assertEqual(out["net_r"],2.0)

    def test_point_in_time_context_prefers_same_timeframe(self):
        context=pd.DataFrame([
            {
                "captured_at":"2026-09-14T20:00:00Z","pair":"EUR/USD","timeframe":"",
                "reading_aligned":False,"direction_aligned":False,
                "filters_aligned":False,"trigger_aligned":False,
            },
            {
                "captured_at":"2026-09-14T21:00:00Z","pair":"EUR/USD","timeframe":"H4",
                "reading_aligned":True,"direction_aligned":True,
                "filters_aligned":True,"trigger_aligned":True,
            },
            {
                "captured_at":"2026-09-15T01:00:00Z","pair":"EUR/USD","timeframe":"H4",
                "reading_aligned":False,"direction_aligned":False,
                "filters_aligned":False,"trigger_aligned":False,
            },
        ])
        pack=enrich_signals_point_in_time([self._plan()],context)
        row=pack["signals"][0]
        self.assertTrue(row["reading_aligned"])
        self.assertTrue(row["direction_aligned"])
        self.assertTrue(row["filters_aligned"])
        self.assertTrue(row["trigger_aligned"])
        self.assertFalse(pack["future_context_used"])


if __name__=="__main__":
    unittest.main()
