"""Synthetic exact-boundary PPI7 bid/ask stress tests (no external market calls)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from copy import deepcopy
import unittest

from atlasquant_trader_ppi7_mt5_pre_post_event_bidask_lab import (
    inspect_ppi7_pre_post_bidask_lab as inspect, EVENT_DAY, _bounds,
)
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import EVENT_UTC, USD_FX
from test_atlasquant_trader_ppi_mt5_m15_capture_lab import FakeMT5, TERMINAL

UTC = timezone.utc
NOW = datetime(2026, 11, 12, 22, 30, tzinfo=UTC)
ANALOG = "2026-11-11"
BEFORE, BEFORE_END, AFTER, AFTER_END, READY = _bounds(ANALOG)


def quotes(*, at: datetime, bid: float, point: float, spreads=(2, 2, 2)):
    rows = []
    base = Decimal(str(bid))
    increment = Decimal(str(point))
    for i, points in enumerate(spreads):
        t = at + timedelta(seconds=(1, 9, 19)[i])
        rows.append({
            "time": int(t.timestamp()),
            "time_msc": int(t.timestamp()) * 1000 + 300,
            "bid": float(base),
            "ask": float(base + increment * points),
        })
    return rows


class BoundaryFake(FakeMT5):
    COPY_TICKS_INFO = 13

    def __init__(self):
        super().__init__()
        self.visible -= {"NZDUSD", "USDCHF", "USDCAD"}
        self.segments = {}
        for sym in USD_FX:
            point = self.specs[sym]["point"]
            bid = 150.123 if sym.endswith("JPY") else 1.11373
            self.segments[sym] = {
                "pre": quotes(at=BEFORE, bid=bid, point=point),
                "post": quotes(at=AFTER, bid=bid, point=point,
                               spreads=(6, 6, 6) if sym == "GBPUSD" else (2, 2, 2)),
            }

    def copy_ticks_range(self, sym, start, end, flag):
        self.calls.append(("copy_ticks_range", sym, start, end, flag))
        return deepcopy(self.segments[sym]["pre" if start == BEFORE else "post"])


class PPIEventBidAskBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.api = BoundaryFake()

    def probe(self, *, api=None, day=ANALOG, now=NOW):
        return inspect(
            self.api if api is None else api,
            terminal_path=TERMINAL, reference_day=day, clock=lambda: now)

    def safe(self, r):
        self.assertEqual(r["price_direction_bias"], "AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["official_ppi_actual_authenticated"])
        self.assertFalse(r["broker_quote_origin_independently_authenticated"])
        self.assertFalse(r["quotes_original_first_availability_independently_attested"])
        self.assertFalse(r["execution_spread_commission_slippage_verified"])
        self.assertFalse(r["post_event_blackout_or_trade_signal_authorized"])
        self.assertIsNone(r["directional_probability"])
        self.assertIsNone(r["statistical_accuracy"])
        self.assertEqual((r["file_writes"], r["http_requests"], r["new_cost_brl"]),
                         (0, 0, 0))
        self.assertFalse(r["account_accessed"])
        self.assertFalse(r["positions_orders_accessed"])
        self.assertFalse(r["market_watch_modified_by_script"])

    def test_historical_analog_compares_bounded_pre_and_post_readonly(self):
        r = self.probe()
        self.safe(r)
        self.assertEqual(r["state"], "LAB_PPI7_PRE_POST_BIDASK_QUALITY_DESCRIPTIVE_NO_GO")
        self.assertEqual(r["pairs_with_complete_local_samples"], 7)
        self.assertEqual(r["before_quote_snapshots"], 21)
        self.assertEqual(r["after_quote_snapshots"], 21)
        self.assertEqual(r["observed_sample_widened_2x_pair_count"], 1)
        self.assertTrue(r["all_pairs_have_complete_20s_boundaries"])
        self.assertEqual(r["pair_results"]["GBPUSD"]["sample_spread_ratio_post_over_pre"],
                         "3.000")
        self.assertEqual(
            r["pair_results"]["GBPUSD"]["observational_risk_state"],
            "POST_SAMPLE_SPREAD_AT_LEAST_2X_WIDER_NOT_TRADE_SIGNAL")
        self.assertEqual(r["research_window_kind"],
                         "PRE_EVENT_HISTORICAL_ANALOG_NOT_A_PPI_RELEASE")
        self.assertEqual({c[0] for c in self.api.calls},
                         {"initialize", "terminal_info", "symbol_info",
                          "copy_ticks_range", "shutdown"})
        ticks = [x for x in self.api.calls if x[0] == "copy_ticks_range"]
        self.assertEqual(len(ticks), 14)
        self.assertEqual(ticks[0][2:4], (BEFORE, BEFORE_END))
        self.assertEqual(ticks[1][2:4], (AFTER, AFTER_END))
        self.assertEqual(self.api.calls[-1][0], "shutdown")

    def test_exact_post_event_time_gate_before_any_mt5_access(self):
        pre, pre_end, post, post_end, ready = _bounds(EVENT_DAY)
        self.assertEqual(post, EVENT_UTC)
        self.assertEqual(pre_end, post - timedelta(milliseconds=1))
        self.assertEqual(post_end, ready - timedelta(milliseconds=1))
        for now in (EVENT_UTC - timedelta(days=1),
                    EVENT_UTC,
                    ready - timedelta(seconds=1)):
            with self.subTest(now=now):
                self.api = BoundaryFake()
                r = self.probe(day=EVENT_DAY, now=now)
                self.safe(r)
                self.assertEqual(r["state"], "LAB_PPI7_EVENT_BIDASK_BLOCKED")
                self.assertEqual(r["reason"], "BOTH_PRE_AND_POST_WINDOWS_MUST_BE_CLOSED")
                self.assertEqual(self.api.calls, [])

    def test_only_explicit_days_and_aware_clock_allowed(self):
        for day, now in (("2026-11-12", NOW), ("2026-11-14", NOW),
                         ("2026-10-30", NOW), ("2026-11-13", NOW.replace(tzinfo=None)),
                         (None, NOW)):
            with self.subTest(day=day,now=now):
                self.api = BoundaryFake()
                r = self.probe(day=day, now=now)
                self.safe(r)
                self.assertEqual(r["state"], "LAB_PPI7_EVENT_BIDASK_BLOCKED")
                self.assertEqual(self.api.calls, [])

    def test_missing_second_sample_is_not_no_widening(self):
        self.api.segments["AUDUSD"]["post"] = []
        r = self.probe()
        self.safe(r)
        self.assertEqual(r["state"], "LAB_PPI7_EVENT_BIDASK_BLOCKED")
        self.assertEqual(r["failed_symbol"], "AUDUSD")
        self.assertIsNone(r["observed_sample_widened_2x_pair_count"])
        self.assertEqual(r["pair_results"], {})
        self.assertEqual(r["pairs_with_complete_local_samples"], 0)
        self.assertEqual(r["before_quote_snapshots"], 0)
        self.assertEqual(r["after_quote_snapshots"], 0)

    def test_missing_last_pair_discards_first_six_stats(self):
        self.api.segments["USDCAD"]["post"] = []
        r = self.probe()
        self.safe(r)
        self.assertEqual(r["state"], "LAB_PPI7_EVENT_BIDASK_BLOCKED")
        self.assertEqual(r["failed_symbol"], "USDCAD")
        self.assertEqual(r["pair_results"], {})
        self.assertIsNone(r["observed_sample_widened_2x_pair_count"])
        self.assertEqual(r["before_quote_snapshots"], 0)
        self.assertEqual(r["after_quote_snapshots"], 0)

    def test_zero_spreads_reduce_confidence_not_cost(self):
        self.api.segments["GBPUSD"]["pre"] = quotes(
            at=BEFORE, bid=1.11373, point=0.00001,
            spreads=(0, 0, 2))
        r = self.probe()
        self.safe(r)
        self.assertEqual(r["state"], "LAB_PPI7_PRE_POST_BIDASK_QUALITY_DESCRIPTIVE_NO_GO")
        self.assertEqual(r["before_zero_spread_snapshots"], 2)
        self.assertEqual(r["pair_results"]["GBPUSD"]["before_zero_spread_snapshots"], 2)
        self.assertIsNone(r["pair_results"]["GBPUSD"]["sample_spread_ratio_post_over_pre"])
        self.assertIn("GBPUSD", r["pairs_insufficient_for_ratio"])
        self.assertIsNone(r["observed_sample_widened_2x_pair_count"])
        self.assertFalse(r["all_pairs_have_complete_20s_boundaries"])
        self.assertFalse(r["post_event_blackout_or_trade_signal_authorized"])

    def test_outside_window_or_crossed_bidask_rejected(self):
        for mutation in ("wrong_time", "crossed", "off_tick"):
            with self.subTest(mutation=mutation):
                self.api = BoundaryFake()
                row = self.api.segments["USDJPY"]["post"][0]
                if mutation == "wrong_time":
                    row["time_msc"] -= 1000 * 30
                elif mutation == "crossed":
                    row["ask"] = row["bid"] - 0.001
                else:
                    row["bid"] = 150.1235
                r = self.probe()
                self.safe(r)
                self.assertEqual(r["state"], "LAB_PPI7_EVENT_BIDASK_BLOCKED")
                self.assertEqual(r["failed_symbol"], "USDJPY")

    def test_spread_widening_is_descriptive_not_probability_or_trade(self):
        r = self.probe()
        self.safe(r)
        self.assertIsNone(r["directional_probability"])
        self.assertIsNone(r["statistical_accuracy"])
        self.assertFalse(r["post_event_blackout_or_trade_signal_authorized"])
        self.assertEqual(r["pair_results"]["EURUSD"]["sample_spread_ratio_post_over_pre"],
                         "1.000")

    def test_symbol_metadata_inconsistency_blocks(self):
        self.api.specs["USDCHF"]["currency_base"] = "USD"
        self.api.specs["USDCHF"]["digits"] = 3
        r = self.probe()
        self.safe(r)
        self.assertEqual(r["failed_symbol"], "USDCHF")
        self.assertEqual(r["reason"], "CANONICAL_SYMBOL_METADATA_INVALID")

    def test_disconnected_terminal_blocks_without_reading_prices(self):
        self.api.connected = False
        r = self.probe()
        self.safe(r)
        self.assertEqual(r["reason"], "MT5_NOT_CONNECTED")
        self.assertEqual([x[0] for x in self.api.calls], ["initialize"])

    def test_shallow_event_window_not_same_as_four_hour_price_reaction(self):
        r = self.probe()
        self.safe(r)
        self.assertNotIn("profit", str(r).lower())
        self.assertNotIn("entry_price", str(r).lower())
        self.assertEqual(r["no_event_time_lookahead"], True)


if __name__ == "__main__":
    unittest.main()
