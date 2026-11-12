"""Offline fail-closed tests for real-MT5 historical PPI7 preflight."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from copy import deepcopy
import unittest

from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import USD_FX
from atlasquant_trader_ppi7_mt5_real_history_preflight_lab import (
    inspect_pre_event_mt5_m15_history_lab as inspect,
)
from test_atlasquant_trader_ppi_mt5_m15_capture_lab import FakeMT5, TERMINAL

UTC = timezone.utc
NOW = datetime(2026, 11, 12, 22, 20, tzinfo=UTC)
REFERENCE = "2026-11-11"
SHIFT = 2 * 86400


class PastHistoryMT5(FakeMT5):
    def __init__(self):
        super().__init__()
        for sym in USD_FX:
            for bar in self.data[sym]:
                bar["time"] -= SHIFT


class RealHistoryReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.api = PastHistoryMT5()

    def run_probe(self, *, api=None, day=REFERENCE, now=NOW, terminal=TERMINAL):
        return inspect(
            self.api if api is None else api,
            terminal_path=terminal, reference_day=day,
            clock=lambda: now,
        )

    def safe(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["broker_identity_independently_authenticated"])
        self.assertFalse(r["market_data_point_in_time_authenticated"])
        self.assertFalse(r["future_ppi_event_candles_available"])
        self.assertFalse(r["event_reaction_measured"])
        self.assertIsNone(r["validated_bias_accuracy"])
        self.assertEqual(r["files_written"], 0)
        self.assertEqual(r["new_cost_brl"], 0)
        self.assertFalse(r["visibility_changed_by_script"])
        self.assertFalse(r["orders_or_positions_accessed"])
        self.assertFalse(r["account_information_accessed"])

    def test_all_119_past_bars_pass_exact_capture_serializer(self):
        r = self.run_probe()
        self.safe(r)
        self.assertEqual(r["validated_bars"], 119)
        self.assertEqual(r["validated_pairs"], 7)
        self.assertEqual(r["state"], "LAB_MT5_7PAIR_REAL_HISTORICAL_M15_CANDIDATE_UNATTESTED")
        self.assertEqual(set(r["pair_results"]), set(USD_FX))
        for sym in USD_FX:
            self.assertEqual(r["pair_results"][sym]["closed_m15_bars"], 17)
            self.assertEqual(r["pair_results"][sym]["median_stored_bar_spread_points"], 8)
            self.assertEqual(r["pair_results"][sym]["max_stored_bar_spread_points"], 8)
            self.assertFalse(r["pair_results"][sym]["price_bytes_or_ohlc_retained"])
        self.assertEqual(
            {x[0] for x in self.api.calls},
            {"initialize", "terminal_info", "symbol_info", "copy_rates_range",
             "shutdown"},
        )

    def test_hidden_symbol_does_not_need_market_watch_change(self):
        self.api.visible -= {"NZDUSD", "USDCHF", "USDCAD"}
        before = set(self.api.visible)
        r = self.run_probe()
        self.safe(r)
        self.assertEqual(r["validated_bars"], 119)
        self.assertEqual(r["hidden_pairs_with_valid_history"],
                         ["NZDUSD", "USDCHF", "USDCAD"])
        self.assertEqual(self.api.visible, before)

    def test_early_or_invalid_reference_blocks_without_mt5_access(self):
        for day in ("2026-11-13", "2026-11-09", "../2026-11-11", None):
            with self.subTest(day=day):
                r = self.run_probe(day=day)
                self.safe(r)
                self.assertEqual(r["state"], "LAB_MT5_PRE_EVENT_HISTORY_PREFLIGHT_BLOCKED")
        self.assertEqual(self.api.calls, [])

    def test_unclosed_or_naive_local_time_no_terminal_access(self):
        for clock in (
            datetime(2026, 11, 11, 17, 29, tzinfo=UTC),
            NOW.replace(tzinfo=None), NOW + timedelta(microseconds=1),
        ):
            with self.subTest(clock=clock):
                r = self.run_probe(now=clock)
                self.safe(r)
                self.assertEqual(r["validated_bars"], 0)
        self.assertEqual(self.api.calls, [])

    def test_first_empty_window_bounded_history_then_retry(self):
        class InitiallyEmpty(PastHistoryMT5):
            def __init__(self):
                super().__init__()
                self.empty = True

            def copy_rates_range(self, sym, timeframe, begin, end):
                rows = super().copy_rates_range(sym, timeframe, begin, end)
                if sym == "USDJPY" and begin.date().isoformat() == REFERENCE and self.empty:
                    self.empty = False
                    return []
                return rows

        api = InitiallyEmpty()
        r = self.run_probe(api=api)
        self.safe(r)
        self.assertEqual(r["validated_bars"], 119)
        self.assertEqual(r["history_warmup_attempted"], ["USDJPY"])
        reads = [c for c in api.calls if c[0] == "copy_rates_range"
                 and c[1] == "USDJPY"]
        self.assertEqual(len(reads), 3)
        self.assertEqual(reads[1][3].date().isoformat(), "2026-11-09")

    def test_never_available_does_not_fabricate_candles(self):
        class NeverAvailable(PastHistoryMT5):
            def copy_rates_range(self, sym, timeframe, begin, end):
                rows = super().copy_rates_range(sym, timeframe, begin, end)
                if sym == "GBPUSD" and begin.date().isoformat() == REFERENCE:
                    return []
                return rows

        api = NeverAvailable()
        r = self.run_probe(api=api)
        self.safe(r)
        self.assertIn("REQUIRE_EXACTLY_17_M15_BARS", r["reason"])
        self.assertEqual(r["failed_symbol"], "GBPUSD")
        self.assertEqual(r["validated_bars"], 17)
        self.assertEqual(api.calls[-1][0], "shutdown")

    def test_wrong_epoch_duplicate_and_partial_window_block(self):
        variants = (
            lambda data: data["AUDUSD"][1].__setitem__("time", data["AUDUSD"][0]["time"]),
            lambda data: data["AUDUSD"].pop(),
        )
        for corrupt in variants:
            with self.subTest(corrupt=corrupt):
                self.api = PastHistoryMT5()
                corrupt(self.api.data)
                r = self.run_probe()
                self.safe(r)
                self.assertEqual(r["state"], "LAB_MT5_PRE_EVENT_HISTORY_PREFLIGHT_BLOCKED")
                self.assertEqual(r["failed_symbol"], "AUDUSD")

    def test_ohlc_error_and_negative_spread_block(self):
        for field, bad in (("high", 0.5), ("spread", -1)):
            with self.subTest(field=field):
                self.api = PastHistoryMT5()
                self.api.data["EURUSD"][0][field] = bad
                r = self.run_probe()
                self.safe(r)
                self.assertEqual(r["validated_bars"], 0)

    def test_wrong_currency_metadata_fails(self):
        self.api.specs["EURUSD"]["currency_base"] = "USD"
        r = self.run_probe()
        self.safe(r)
        self.assertEqual(r["reason"], "SYMBOL_IDENTITY_OR_TICK_INVALID")
        self.assertEqual(r["failed_symbol"], "EURUSD")

    def test_failing_initialize_and_unrecognized_terminal_are_safe(self):
        self.api.connected = False
        r = self.run_probe()
        self.safe(r)
        self.assertEqual(r["reason"], "MT5_NOT_CONNECTED")

    def test_past_window_strict_serializer_cannot_accept_reordered_bars(self):
        self.api.data["NZDUSD"] = list(reversed(self.api.data["NZDUSD"]))
        r = self.run_probe()
        self.safe(r)
        self.assertEqual(r["failed_symbol"], "NZDUSD")
        self.assertIn("PPI_M15_EPOCH_GAP", r["reason"])


if __name__ == "__main__":
    unittest.main()
