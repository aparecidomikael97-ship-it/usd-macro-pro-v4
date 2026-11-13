"""Synthetic MT5 API doubles, not real PPI-2026 price reactions."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta, timezone
from types import SimpleNamespace
import unittest

from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    EVENT_UTC, USD_FX, BASELINE_OPEN_UTC,
)
from atlasquant_trader_ppi7_m15_closed_observation_lab import (
    M15_CLOSE_UTC, observe_ppi7_closed_m15_lab as observe,
)

TERMINAL = r"C:\Program Files\MetaTrader 5\terminal64.exe"
NOW = M15_CLOSE_UTC + timedelta(minutes=3)


class FakeMT5:
    TIMEFRAME_M15 = 15

    def __init__(self):
        self.calls = []
        self.connected = True
        self.visible = set(USD_FX)
        self.change_visibility = False
        self.fail_shutdown = False
        self.specs = {
            sym: {"name": sym, "currency_base": sym[:3],
                  "currency_profit": sym[3:],
                  "digits": 3 if sym.endswith("JPY") else 5,
                  "point": 0.001 if sym.endswith("JPY") else 0.00001}
            for sym in USD_FX}
        self.history = {}
        for sym in USD_FX:
            initial = 150.0 if sym.endswith("JPY") else 1.20000
            after = initial
            if sym == "EURUSD":
                after = 1.19900
            elif sym == "USDJPY":
                after = 150.100
            elif sym == "GBPUSD":
                after = 1.20100
            self.history[sym] = [
                {"time": int(t.timestamp()),
                 "open": price, "high": price, "low": price, "close": price,
                 "tick_volume": 100, "spread": 2, "real_volume": 0}
                for t, price in ((BASELINE_OPEN_UTC, initial), (EVENT_UTC, after))
            ]
        self._info_calls = {}

    def initialize(self, *, path, timeout):
        self.calls.append(("initialize", path, timeout))
        return self.connected

    def terminal_info(self):
        self.calls.append(("terminal_info",))
        return SimpleNamespace(connected=self.connected)

    def symbol_info(self, sym):
        self.calls.append(("symbol_info", sym))
        self._info_calls[sym] = self._info_calls.get(sym, 0) + 1
        visible = sym in self.visible
        if self.change_visibility and sym == "EURUSD" and self._info_calls[sym] == 2:
            visible = not visible
        return SimpleNamespace(visible=visible, **self.specs[sym])

    def copy_rates_range(self, sym, timeframe, start, end):
        self.calls.append(("copy_rates_range", sym, timeframe, start, end))
        return deepcopy(self.history[sym])

    def shutdown(self):
        self.calls.append(("shutdown",))
        if self.fail_shutdown:
            raise RuntimeError("bad shutdown")


class Ppi7M15OnlyTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeMT5()

    def call(self, *, when=NOW, terminal=TERMINAL, api=None):
        return observe(
            self.api if api is None else api,
            terminal_path=terminal, clock=lambda: when)

    def safe(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        for field in ("trade_authorized", "publishable", "live_alert_allowed",
                      "worker_enabled", "scheduler_enabled",
                      "data_from_terminal_independently_authenticated",
                      "prices_first_available_at_event_independently_attested",
                      "ppi_release_first_print_independently_authenticated",
                      "execution_bidask_spread_slippage_verified",
                      "h1_window_closed_and_observed", "h4_window_closed_and_observed"):
            self.assertFalse(result[field], field)
        self.assertIsNone(result["directional_forecast"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertIsNone(result["historical_out_of_sample_accuracy"])
        self.assertEqual(result["files_written"], 0)
        self.assertEqual(result["new_cost_brl"], 0)

    def blocked(self, reason, *, when=NOW, terminal=TERMINAL):
        r = self.call(when=when, terminal=terminal)
        self.safe(r)
        self.assertEqual(r["reason"], reason)
        self.assertIsNone(r["usd_normalized_m15_bps_by_pair"])
        self.assertEqual(r["independent_economic_events_observed"], 0)
        return r

    def test_01_two_closed_bars_all_seven_yield_m15_only(self):
        r=self.call()
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_PPI7_CLOSED_M15_DOCUMENTARY_OBSERVATION_NO_GO")
        self.assertEqual(r["validated_m15_candles"], 14)
        self.assertEqual(r["validated_symbols"], 7)
        self.assertEqual(r["horizon_observed"], "M15_ONLY")
        self.assertEqual(r["independent_economic_events_observed"], 1)
        self.assertEqual(r["usd_stronger_pair_count"], 2)
        self.assertEqual(r["usd_weaker_pair_count"], 1)
        self.assertEqual(r["unchanged_pair_count"], 4)
        self.assertGreater(float(r["usd_normalized_m15_bps_by_pair"]["EURUSD"]), 0)
        self.assertGreater(float(r["usd_normalized_m15_bps_by_pair"]["USDJPY"]), 0)
        self.assertLess(float(r["usd_normalized_m15_bps_by_pair"]["GBPUSD"]), 0)
        self.assertTrue(r["seven_pairs_are_not_independent_events"])

    def test_02_preclose_no_mt5_access_even_one_microsecond_before(self):
        for when in (EVENT_UTC, M15_CLOSE_UTC-timedelta(microseconds=1)):
            with self.subTest(when=when):
                self.blocked("M15_WINDOW_NOT_YET_CLOSED", when=when)
        self.assertEqual(self.api.calls, [])

    def test_03_at_exact_close_M15_allowed_H1_and_H4_still_blocked(self):
        r=self.call(when=M15_CLOSE_UTC)
        self.safe(r)
        self.assertEqual(r["horizon_observed"], "M15_ONLY")

    def test_04_only_readonly_mt5_methods_exact_two_open_times(self):
        self.call()
        names={x[0] for x in self.api.calls}
        self.assertEqual(names,
            {"initialize", "terminal_info", "symbol_info",
             "copy_rates_range", "shutdown"})
        dates=[x for x in self.api.calls if x[0]=="copy_rates_range"]
        self.assertEqual(len(dates),7)
        self.assertTrue(all(x[3]==BASELINE_OPEN_UTC and x[4]==EVENT_UTC
                            for x in dates))
        self.assertEqual(self.api.calls[-1],("shutdown",))

    def test_05_reject_missing_or_extra_bars_never_partial(self):
        for sym, bad in (("EURUSD",[]),
                         ("GBPUSD",deepcopy(self.api.history["GBPUSD"])*2)):
            with self.subTest(sym=sym):
                old=self.api.history[sym]
                self.api.history[sym]=bad
                self.blocked("REQUIRE_EXACT_TWO_M15_CANDLES")
                self.api.history[sym]=old

    def test_06_wrong_timezone_or_duplicated_epoch_blocks(self):
        for change in (1,900,3600):
            rows=self.api.history["AUDUSD"]
            original=rows[1]["time"]
            rows[1]["time"]=original+change
            self.blocked("M15_EPOCH_DUPLICATE_GAP_OR_WRONG_TIMEZONE")
            rows[1]["time"]=original

    def test_07_invalid_ohlc_spread_volume_quote_blocks(self):
        for field, value, reason in (
            ("high", 0.5, "M15_OHLC_INCONSISTENT"),
            ("tick_volume", 0, "INVALID_VOLUME_OR_EPOCH"),
            ("spread", -1, "INVALID_VOLUME_OR_EPOCH"),
            ("close", float("nan"), "PRICE_OUTSIDE_FROZEN_CSV_CONTRACT"),
            ("close", 1.123456, "PRICE_OUTSIDE_FROZEN_CSV_CONTRACT"),
        ):
            with self.subTest(field=field):
                original=self.api.history["NZDUSD"][1][field]
                self.api.history["NZDUSD"][1][field]=value
                self.blocked(reason)
                self.api.history["NZDUSD"][1][field]=original

    def test_08_hidden_symbol_read_only_no_marketwatch_change(self):
        self.api.visible.remove("USDCHF")
        r=self.call()
        self.safe(r)
        self.assertEqual(r["validated_symbols"],7)
        self.assertNotIn("USDCHF",self.api.visible)

    def test_09_symbol_identity_or_visibility_change_blocks(self):
        self.api.specs["USDJPY"]["currency_base"]="EUR"
        self.blocked("SYMBOL_BASE_QUOTE_DIGITS_OR_POINT_INVALID")
        self.api.specs["USDJPY"]["currency_base"]="USD"
        # Prior subcase called EURUSD's symbol_info twice. Reset the
        # synthetic call counter so the next two calls model a change.
        self.api._info_calls.clear()
        self.api.change_visibility=True
        self.blocked("SYMBOL_VISIBILITY_CHANGED_OR_UNKNOWN")

    def test_10_shutdown_failure_cannot_promote_partial_success(self):
        self.api.fail_shutdown=True
        self.blocked("MT5_SHUTDOWN_EXCEPTION")

    def test_11_invalid_terminal_and_naive_clock_no_mt5(self):
        self.blocked("INVALID_TERMINAL_OR_CLOCK",terminal="relative.exe")
        self.blocked("INVALID_TERMINAL_OR_CLOCK",when=NOW.replace(tzinfo=None))
        self.assertEqual(self.api.calls,[])

    def test_12_disconnected_terminal_blocks_without_orders(self):
        self.api.connected=False
        self.blocked("MT5_NOT_CONNECTED")
        self.assertEqual([x[0] for x in self.api.calls], ["initialize"])

    def test_13_one_symbol_missing_fields_block_all_seven(self):
        original=self.api.history["EURUSD"][0].pop("tick_volume")
        self.blocked("M15_MISSING_OR_MALFORMED_FIELDS")
        self.api.history["EURUSD"][0]["tick_volume"]=original

    def test_14_still_no_h1_h4_even_when_run_late(self):
        r=self.call(when=M15_CLOSE_UTC+timedelta(hours=5))
        self.safe(r)
        self.assertEqual(r["horizon_observed"],"M15_ONLY")


if __name__=="__main__":
    unittest.main()
