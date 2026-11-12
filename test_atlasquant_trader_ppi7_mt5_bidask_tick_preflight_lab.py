"""PPI7 bounded 20-second historic tick quality test fixtures; no MT5 calls."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from copy import deepcopy
import unittest

from atlasquant_trader_ppi7_mt5_bidask_tick_preflight_lab import (
    inspect_ppi7_historical_bidask_ticks_lab as inspect,
    _tick_aggregate, MAX_TICKS_PER_PAIR,
)
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import USD_FX
from test_atlasquant_trader_ppi_mt5_m15_capture_lab import FakeMT5, TERMINAL

UTC = timezone.utc
START = datetime(2026, 11, 11, 13, 29, 50, tzinfo=UTC)
NOW = datetime(2026, 11, 12, 22, tzinfo=UTC)


class TickFake(FakeMT5):
    COPY_TICKS_INFO = 7

    def __init__(self):
        super().__init__()
        self.ticks = {}
        self.visible -= {"NZDUSD", "USDCHF", "USDCAD"}
        for sym in USD_FX:
            price = 150.123 if sym.endswith("JPY") else 1.11373
            add = 0.001 if sym.endswith("JPY") else 0.00001
            self.ticks[sym] = [
                {
                    "time": int(START.timestamp()) + i * 9,
                    "time_msc": int(START.timestamp() * 1000) + i * 9000 + 333,
                    "bid": price,
                    "ask": round(price + 2 * add, 5 if add < .001 else 3),
                    "flags": 6,
                }
                for i in range(3)
            ]

    def copy_ticks_range(self, sym, start, end, flag):
        self.calls.append(("copy_ticks_range", sym, start, end, flag))
        return deepcopy(self.ticks[sym])


class QuoteQualityTests(unittest.TestCase):
    def setUp(self):
        self.api = TickFake()

    def probe(self, *, api=None, day="2026-11-11", now=NOW):
        return inspect(
            self.api if api is None else api,
            terminal_path=TERMINAL, reference_day=day, clock=lambda: now)

    def safe(self, x):
        self.assertEqual(x["price_direction_bias"], "AGUARDAR")
        self.assertFalse(x["trade_authorized"])
        self.assertFalse(x["publishable"])
        self.assertFalse(x["scheduler_enabled"])
        self.assertFalse(x["worker_enabled"])
        self.assertFalse(x["historical_quotes_authenticated"])
        self.assertFalse(x["historical_first_available_instant_attested"])
        self.assertFalse(x["bidask_execution_spread_independently_verified"])
        self.assertFalse(x["commissions_or_swap_verified"])
        self.assertFalse(x["slippage_or_fill_verifiable"])
        self.assertFalse(x["cost_adjusted_forecast_or_reaction_ready"])
        self.assertEqual(x["file_writes"], 0)
        self.assertEqual(x["new_cost_brl"], 0)
        self.assertFalse(x["account_info_accessed"])
        self.assertFalse(x["orders_positions_accessed"])
        self.assertFalse(x["market_watch_changed_by_script"])

    def test_seven_pairs_and_only_readonly_mt5_methods(self):
        r = self.probe()
        self.safe(r)
        self.assertEqual(r["state"], "LAB_REAL_LOCAL_BIDASK_TICK_SAMPLE_UNATTESTED")
        self.assertEqual(r["pairs_checked"], 7)
        self.assertEqual(r["pairs_with_ticks"], 7)
        self.assertEqual(r["total_quote_snapshots"], 21)
        self.assertEqual(r["total_strictly_positive_spread_snapshots"], 21)
        self.assertEqual(r["total_zero_spread_snapshots"], 0)
        self.assertTrue(r["all_pairs_had_ticks"])
        self.assertTrue(r["all_ticks_had_strictly_positive_spread"])
        self.assertTrue(r["sample_quote_coverage_near_both_endpoints"])
        self.assertEqual(
            {call[0] for call in self.api.calls},
            {"initialize", "terminal_info", "symbol_info",
             "copy_ticks_range", "shutdown"})
        self.assertEqual(len([x for x in self.api.calls
                              if x[0] == "copy_ticks_range"]), 7)
        self.assertEqual(self.api.calls[-1], ("shutdown",))
        self.assertEqual(
            self.api.visible, set(USD_FX) - {"NZDUSD", "USDCHF", "USDCAD"})

    def test_zero_bid_ask_spread_is_not_free_trading(self):
        self.api.ticks["EURUSD"][0]["ask"] = self.api.ticks["EURUSD"][0]["bid"]
        r = self.probe()
        self.safe(r)
        self.assertEqual(r["state"], "LAB_REAL_LOCAL_BIDASK_TICK_SAMPLE_UNATTESTED")
        self.assertEqual(r["total_zero_spread_snapshots"], 1)
        self.assertFalse(r["all_ticks_had_strictly_positive_spread"])
        self.assertEqual(r["pair_results"]["EURUSD"]["positive_spread_snapshots"], 2)
        self.assertEqual(r["pair_results"]["EURUSD"]["zero_spread_snapshots"], 1)
        self.assertTrue(
            r["pair_results"]["EURUSD"]["spread_samples_are_not_verified_execution_costs"])

    def test_crossed_quote_and_off_tick_price_fail_closed(self):
        for value in (1.11376, 1.113736, 0.0, float("nan")):
            with self.subTest(bid=value):
                self.api = TickFake()
                self.api.ticks["EURUSD"][0]["bid"] = value
                r = self.probe()
                self.safe(r)
                self.assertEqual(r["state"], "LAB_HISTORIC_TICK_SAMPLE_BLOCKED")
                self.assertEqual(r["failed_symbol"], "EURUSD")

    def test_ieee754_transport_noise_is_quantized_only_to_real_tick(self):
        self.api.ticks["EURUSD"][0]["bid"] = 1.1137299999999999
        r = self.probe()
        self.safe(r)
        self.assertEqual(r["pairs_with_ticks"], 7)

    def test_unsorted_or_outside_timestamp_rejected(self):
        for bad in (int(START.timestamp() * 1000) - 1,
                    int((START + timedelta(minutes=1)).timestamp() * 1000)):
            with self.subTest(ms=bad):
                self.api = TickFake()
                self.api.ticks["EURUSD"][1]["time_msc"] = bad
                r = self.probe()
                self.safe(r)
                self.assertEqual(r["state"], "LAB_HISTORIC_TICK_SAMPLE_BLOCKED")
                self.assertEqual(r["failed_symbol"], "EURUSD")

    def test_stored_unix_seconds_must_match_milliseconds(self):
        self.api.ticks["USDJPY"][0]["time"] += 10
        r = self.probe()
        self.safe(r)
        self.assertEqual(r["failed_symbol"], "USDJPY")
        self.assertIn("TICK_TIME_ORDER_OR_WINDOW", r["reason"])

    def test_empty_pair_rejected_no_spread_fabricated(self):
        self.api.ticks["USDCHF"] = []
        r = self.probe()
        self.safe(r)
        self.assertEqual(r["failed_symbol"], "USDCHF")
        self.assertEqual(r["state"], "LAB_HISTORIC_TICK_SAMPLE_BLOCKED")
        self.assertEqual(r["total_quote_snapshots"], 15)

    def test_cap_overrun_rejected_in_pure_parser(self):
        row = self.api.ticks["EURUSD"][0]
        with self.assertRaisesRegex(ValueError, "OVERSIZED"):
            _tick_aggregate(
                [row] * (MAX_TICKS_PER_PAIR + 1), digits=5,
                start_ms=int(START.timestamp() * 1000),
                end_ms=int((START + timedelta(seconds=20)).timestamp() * 1000))

    def test_no_future_reference_or_open_window_accesses_mt5(self):
        for day, now in (
            ("2026-11-13", NOW), ("2026-11-12", NOW),
            ("2026-11-11", START + timedelta(seconds=10)),
            ("2026-11-11", NOW.replace(tzinfo=None)),
        ):
            with self.subTest(day=day, now=now):
                self.api = TickFake()
                r = self.probe(day=day, now=now)
                self.safe(r)
                self.assertEqual(r["state"], "LAB_HISTORIC_TICK_SAMPLE_BLOCKED")
                self.assertEqual(self.api.calls, [])

    def test_hidden_symbol_spec_bad_blocks_without_selection(self):
        self.api.specs["NZDUSD"]["currency_profit"] = "JPY"
        r = self.probe()
        self.safe(r)
        self.assertEqual(r["failed_symbol"], "NZDUSD")
        self.assertEqual(r["reason"], "CANONICAL_SYMBOL_SPEC_NOT_VALID")
        self.assertFalse(any(x[0] == "symbol_select" for x in self.api.calls))


if __name__ == "__main__":
    unittest.main()
