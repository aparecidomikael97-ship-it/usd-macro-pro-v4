"""Offline tests for the read-only MT5 closed-bar snapshot adapter."""
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest

from atlasquant_instrument_registry import FX_28
from atlasquant_trader_mt5_readonly_snapshot_lab import (
    SCHEMA, TIMEFRAME_COUNTS, collect_mt5_fx_snapshot_lab,
)


NOW = datetime(2026, 11, 7, 2, 0, tzinfo=timezone.utc)


def bars(tf: str) -> list[dict]:
    count = TIMEFRAME_COUNTS[tf]
    step = {"M15": 900, "D1": 86400, "W1": 604800}[tf]
    last = {
        "M15": datetime(2026, 11, 6, 23, 30, tzinfo=timezone.utc),
        "D1": datetime(2026, 11, 5, tzinfo=timezone.utc),
        "W1": datetime(2026, 10, 25, tzinfo=timezone.utc),
    }[tf]
    first = int(last.timestamp()) - (count - 1) * step
    return [dict(time=first + i * step, open=1.1, high=1.2, low=1.0,
                 close=1.15, tick_volume=4, spread=1, real_volume=0)
            for i in range(count)]


class FakeMT5:
    TIMEFRAME_M15 = 15
    TIMEFRAME_D1 = 1440
    TIMEFRAME_W1 = 10080

    def __init__(self):
        self.available = list(FX_28)
        self.called = []
        self.initialized = False
        self.shutdown_called = False
        self.mutation = None

    def initialize(self):
        self.initialized = True
        return True

    def symbols_get(self):
        return [SimpleNamespace(name=n) for n in self.available]

    def copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
        self.called.append((symbol, timeframe, start_pos, count))
        label = {15: "M15", 1440: "D1", 10080: "W1"}[timeframe]
        result = bars(label)
        if self.mutation is not None:
            self.mutation(symbol, label, result)
        return result

    def shutdown(self):
        self.shutdown_called = True


class SnapshotTests(unittest.TestCase):
    def test_all_28_pairs_and_three_closed_timeframes(self):
        api = FakeMT5()
        report = collect_mt5_fx_snapshot_lab(api, captured_at_utc=NOW)
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["validated_pairs"], 28)
        self.assertEqual(report["validated_bars"], 2968)
        self.assertEqual(len(api.called), 84)
        self.assertTrue(all(call[2] == 1 for call in api.called))
        self.assertTrue(api.shutdown_called)
        self.assertFalse(report["trade_authorized"])
        self.assertFalse(report["can_feed_live_radar"])
        self.assertEqual(report["operational_bias"], "AGUARDAR")
        self.assertIsNone(report["historical_predictive_accuracy"])

    def test_missing_canonical_pair_blocks_all_data(self):
        api = FakeMT5()
        api.available.remove("CHFJPY")
        report = collect_mt5_fx_snapshot_lab(api, captured_at_utc=NOW)
        self.assertEqual(report["state"], "LAB_BLOCKED")
        self.assertEqual(report["missing_symbols"], ["CHFJPY"])
        self.assertEqual(report["pairs"], {})
        self.assertFalse(api.called)
        self.assertTrue(api.shutdown_called)

    def test_current_or_future_candle_blocks_all_data(self):
        api = FakeMT5()

        def mutate(symbol, label, result):
            if symbol == "EURUSD" and label == "M15":
                result[-1]["time"] = int(NOW.timestamp())

        api.mutation = mutate
        report = collect_mt5_fx_snapshot_lab(api, captured_at_utc=NOW)
        self.assertEqual(report["state"], "LAB_BLOCKED")
        self.assertEqual(report["reason"], "CURRENT_OR_FUTURE_BAR_REJECTED")
        self.assertEqual(report["validated_bars"], 0)
        self.assertTrue(api.shutdown_called)

    def test_bad_ohlc_blocks_all_data(self):
        api = FakeMT5()

        def mutate(symbol, label, result):
            if symbol == "EURUSD" and label == "D1":
                result[-1]["high"] = 0.9

        api.mutation = mutate
        report = collect_mt5_fx_snapshot_lab(api, captured_at_utc=NOW)
        self.assertEqual(report["reason"], "INCONSISTENT_OHLC")
        self.assertEqual(report["pairs"], {})

    def test_unavailable_terminal_does_not_read(self):
        api = FakeMT5()
        api.initialize = lambda: False
        report = collect_mt5_fx_snapshot_lab(api, captured_at_utc=NOW)
        self.assertEqual(report["reason"], "MT5_TERMINAL_NOT_CONNECTED")
        self.assertFalse(api.called)

    def test_timezone_required(self):
        with self.assertRaises(ValueError):
            collect_mt5_fx_snapshot_lab(FakeMT5(), captured_at_utc=NOW.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
