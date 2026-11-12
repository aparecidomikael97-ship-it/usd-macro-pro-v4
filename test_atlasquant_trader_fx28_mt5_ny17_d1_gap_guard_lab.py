"""Synthetic 28-cross NY17 M15 readiness tests, never real broker history."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest

from atlasquant_instrument_registry import FX_28
from atlasquant_trader_fx28_mt5_ny17_d1_gap_guard_lab import (
    inspect_fx28_ny17_d1_m15_readiness_lab as inspect,
    _expected_epochs,
)
from test_atlasquant_trader_ppi_mt5_m15_capture_lab import TERMINAL

UTC = timezone.utc
START = datetime(2026, 11, 10, 22, tzinfo=UTC)
END = START + timedelta(days=1)
NOW = datetime(2026, 11, 12, 23, 15, tzinfo=UTC)
EPOCHS = _expected_epochs(START)


class FakeFX28:
    TIMEFRAME_M15 = 15

    def __init__(self):
        self.calls = []
        self.connected = True
        self.visible = set(FX_28) - {"EURNZD", "GBPNZD", "CHFJPY"}
        self.lazy_once = set()
        self.specs = {}
        self.data = {}
        for sym in FX_28:
            digits = 3 if sym.endswith("JPY") else 5
            self.specs[sym] = {
                "name": sym, "currency_base": sym[:3],
                "currency_profit": sym[3:], "digits": digits,
                "point": 0.001 if digits == 3 else 0.00001,
            }
            close = 150.123 if digits == 3 else 1.12345
            self.data[sym] = [
                {"time": t, "open": close, "high": close,
                 "low": close, "close": close, "tick_volume": 20,
                 "spread": 0, "real_volume": 0}
                for t in EPOCHS
            ]

    def initialize(self, *, path, timeout):
        self.calls.append(("initialize", path, timeout))
        return self.connected

    def terminal_info(self):
        self.calls.append(("terminal_info",))
        return SimpleNamespace(connected=self.connected, company="Pepperstone Group Limited")

    def symbol_info(self, symbol):
        self.calls.append(("symbol_info", symbol))
        if symbol not in self.specs:
            return None
        return SimpleNamespace(visible=(symbol in self.visible),
                               **self.specs[symbol])

    def copy_rates_range(self, symbol, timeframe, start, end):
        self.calls.append(("copy_rates_range", symbol, timeframe, start, end))
        if (symbol in self.lazy_once and start == START
                and end == END - timedelta(minutes=15)):
            self.lazy_once.remove(symbol)
            return []
        return deepcopy(self.data[symbol])

    def shutdown(self):
        self.calls.append(("shutdown",))


class Fx28NY17D1GapGuardTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeFX28()

    def probe(self, *, api=None, day="2026-11-10", now=NOW, terminal=TERMINAL):
        return inspect(
            self.api if api is None else api,
            terminal_path=terminal, session_start_day=day,
            clock=lambda: now)

    def safe(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assertIsNone(r["directional_accuracy_validated"])
        self.assertIsNone(r["directional_bias"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["broker_feed_independently_authenticated"])
        self.assertFalse(r["original_history_point_in_time_attested"])
        self.assertFalse(r["future_bias_forecast_preregistered"])
        self.assertFalse(r["future_outcome_label_authorized"])
        self.assertFalse(r["market_watch_modified_by_script"])
        self.assertFalse(r["account_info_accessed"])
        self.assertFalse(r["orders_or_positions_accessed"])
        self.assertEqual(r["files_written"], 0)
        self.assertEqual(r["new_cost_brl"], 0)

    def test_01_complete_all_28_synthetic_has_2688_candles_but_no_bias(self):
        r = self.probe()
        self.safe(r)
        self.assertEqual(r["state"], "LAB_FX28_NY17_D1_HISTORICAL_COVERAGE_ONLY_NO_GO")
        self.assertEqual(r["pairs_checked"], 28)
        self.assertEqual(r["pairs_with_complete_history"], 28)
        self.assertEqual(r["expected_total_candles"], 2688)
        self.assertEqual(r["valid_candles_seen"], 2688)
        self.assertEqual(r["missing_candles_total"], 0)
        self.assertTrue(r["all_28_d1_m15_histories_structurally_complete"])
        self.assertEqual(r["pairs_with_gaps_or_invalid_data"], [])
        self.assertEqual(
            r["symbols_hidden_but_history_queried"],
            ["EURNZD", "GBPNZD", "CHFJPY"])
        self.assertEqual(
            {c[0] for c in self.api.calls},
            {"initialize", "terminal_info", "symbol_info",
             "copy_rates_range", "shutdown"})
        self.assertEqual(self.api.calls[-1], ("shutdown",))
        self.assertEqual(set(self.api.visible),
                         set(FX_28) - {"EURNZD", "GBPNZD", "CHFJPY"})

    def test_02_realistic_two_missing_rollover_bars_in_two_crosses(self):
        for sym in ("GBPNZD", "CHFJPY"):
            self.api.data[sym] = [
                row for i, row in enumerate(self.api.data[sym])
                if i not in (8, 9)]
        r = self.probe()
        self.safe(r)
        self.assertEqual(r["state"], "LAB_FX28_NY17_D1_HISTORICAL_GAPS_NO_GO")
        self.assertEqual(r["pairs_with_complete_history"], 26)
        self.assertEqual(r["missing_candles_total"], 4)
        self.assertEqual(r["pairs_with_gaps_or_invalid_data"],
                         ["GBPNZD", "CHFJPY"])
        self.assertFalse(r["all_28_d1_m15_histories_structurally_complete"])
        self.assertEqual(r["pair_diagnostics"]["CHFJPY"]["returned_bars"], 94)
        self.assertEqual(r["pair_diagnostics"]["GBPNZD"]["returned_bars"], 94)
        self.assertEqual(
            r["pair_diagnostics"]["CHFJPY"]["first_missing_utc"],
            ["2026-11-11T00:00:00+00:00",
             "2026-11-11T00:15:00+00:00"])
        self.assertEqual(r["bounded_history_warmup_attempted"],
                         ["GBPNZD", "CHFJPY"])

    def test_03_one_empty_initial_read_warms_cache_only_readonly(self):
        self.api.lazy_once.add("GBPNZD")
        r = self.probe()
        self.safe(r)
        self.assertTrue(r["all_28_d1_m15_histories_structurally_complete"])
        self.assertEqual(r["bounded_history_warmup_attempted"], ["GBPNZD"])
        gbp = [c for c in self.api.calls
               if c[0] == "copy_rates_range" and c[1] == "GBPNZD"]
        self.assertEqual(len(gbp), 3)
        self.assertEqual(gbp[1][3], START - timedelta(days=2))
        self.assertEqual(gbp[2][3], START)

    def test_04_missing_real_pair_metadata_blocks_pair_not_silent_27_roster(self):
        del self.api.specs["CADCHF"]
        r = self.probe()
        self.safe(r)
        self.assertEqual(r["pairs_checked"], 28)
        self.assertEqual(r["pairs_with_complete_history"], 27)
        self.assertEqual(r["pairs_with_gaps_or_invalid_data"], ["CADCHF"])
        self.assertFalse(r["all_28_d1_m15_histories_structurally_complete"])

    def test_05_wrong_base_quote_currency_or_point_blocks(self):
        for field, bad in (("currency_base", "USD"), ("currency_profit", "JPY"),
                           ("point", 0.01)):
            with self.subTest(field=field):
                self.api = FakeFX28()
                self.api.specs["EURNZD"][field] = bad
                r = self.probe()
                self.safe(r)
                self.assertEqual(r["pair_diagnostics"]["EURNZD"]["reason"],
                                 "SYMBOL_BASE_QUOTE_POINT_OR_DIGITS_INVALID")

    def test_06_duplicate_and_wrong_epoch_are_never_filled(self):
        for value in (EPOCHS[8], EPOCHS[8] + 1, EPOCHS[8] - 900):
            with self.subTest(t=value):
                self.api = FakeFX28()
                self.api.data["EURJPY"][9]["time"] = value
                r = self.probe()
                self.safe(r)
                self.assertEqual(r["pair_diagnostics"]["EURJPY"]["reason"],
                                 "DUPLICATE_OUT_OF_WINDOW_OR_UNSORTED_CANDLE")
                self.assertFalse(r["all_28_d1_m15_histories_structurally_complete"])

    def test_07_bad_ohlc_nan_and_zero_tick_volume_block(self):
        for field, bad in (("high", 0.1), ("close", float("nan")),
                           ("tick_volume", 0), ("spread", -1)):
            with self.subTest(field=field):
                self.api = FakeFX28()
                self.api.data["EURCHF"][0][field] = bad
                r = self.probe()
                self.safe(r)
                self.assertEqual(r["pair_diagnostics"]["EURCHF"]["reason"],
                                 "M15_PRICE_OR_VOLUME_INVALID")
                self.assertEqual(r["pairs_with_complete_history"], 27)

    def test_08_no_future_or_unsupported_session_read(self):
        for day, when in (("2026-11-13", NOW),
                          ("2026-11-10", END-timedelta(microseconds=1)),
                          ("2026-11-11", END),
                          (None, NOW), ("../2026-11-10", NOW),
                          ("2026-11-10", NOW.replace(tzinfo=None))):
            with self.subTest(day=day, clock=when):
                self.api = FakeFX28()
                r = self.probe(day=day, now=when)
                self.safe(r)
                self.assertEqual(r["state"], "LAB_FX28_NY17_D1_PREFLIGHT_BLOCKED")
                self.assertEqual(self.api.calls, [])

    def test_09_terminal_disconnected_never_requests_price(self):
        self.api.connected = False
        r = self.probe()
        self.safe(r)
        self.assertEqual(r["reason"], "MT5_TERMINAL_NOT_CONNECTED")
        self.assertEqual([c[0] for c in self.api.calls], ["initialize"])

    def test_10_binary_float_noise_normalizes_to_valid_quote_tick(self):
        self.api.data["EURUSD"][0]["open"] = 1.1234499999999998
        r = self.probe()
        self.safe(r)
        self.assertTrue(r["all_28_d1_m15_histories_structurally_complete"])

    def test_11_outside_broker_tick_grid_does_not_round(self):
        self.api.data["EURUSD"][0]["close"] = 1.123456
        r = self.probe()
        self.safe(r)
        self.assertEqual(r["pair_diagnostics"]["EURUSD"]["reason"],
                         "M15_PRICE_OR_VOLUME_INVALID")

    def test_12_extra_bar_does_not_count_as_more_than_complete(self):
        extra = deepcopy(self.api.data["USDJPY"][0])
        extra["time"] = EPOCHS[-1] + 900
        self.api.data["USDJPY"].append(extra)
        r = self.probe()
        self.safe(r)
        self.assertEqual(r["pair_diagnostics"]["USDJPY"]["reason"],
                         "EXCESS_ROWS_OR_UNEXPECTED_TIMEFRAME")
        self.assertFalse(r["all_28_d1_m15_histories_structurally_complete"])


if __name__ == "__main__":
    unittest.main()
