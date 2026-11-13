"""Pure mock tests for historical native-W1 vs NY17 closing anchor mismatch."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from atlasquant_instrument_registry import FX_28
from atlasquant_trader_fx28_native_w1_ny17_close_anchor_lab import (
    inspect_fx28_native_w1_vs_ny17_close_lab as inspect,
    WEEKS,
)
from test_atlasquant_trader_fx28_mt5_ny17_d1_gap_guard_lab import (
    FakeFX28, TERMINAL,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 12, 23, 45, tzinfo=UTC)


def row(epoch, *, close, digits):
    point = Decimal(1).scaleb(-digits)
    c = Decimal(str(close))
    return {
        "time": int(epoch.timestamp()), "open": float(c-point),
        "high": float(c+point), "low": float(c-point),
        "close": float(c), "tick_volume": 8, "spread": 2,
        "real_volume": 0,
    }


class NativeAnchorFake(FakeFX28):
    TIMEFRAME_W1 = 10080

    def __init__(self):
        super().__init__()
        self.native = {}
        self.ny17 = {}
        self.late = {}
        for key, (_, end, last_open) in WEEKS.items():
            sunday = datetime.fromisoformat(key + "T00:00:00+00:00")
            ny_end = datetime.fromisoformat(end)
            ny_open = ny_end - timedelta(minutes=15)
            late_open = datetime.fromisoformat(last_open)
            for sym in FX_28:
                digits = self.specs[sym]["digits"]
                point = Decimal(1).scaleb(-digits)
                base = Decimal("150.123") if digits == 3 else Decimal("1.12345")
                close = base + point
                self.native[(sym, sunday)] = row(sunday, close=close, digits=digits)
                self.ny17[(sym, ny_open)] = row(ny_open, close=base, digits=digits)
                self.late[(sym, late_open)] = row(late_open, close=close, digits=digits)

    def copy_rates_range(self, symbol, timeframe, start, end):
        self.calls.append(("copy_rates_range", symbol, timeframe, start, end))
        if start != end:
            return None
        if timeframe == self.TIMEFRAME_W1:
            found = self.native.get((symbol, start))
        elif timeframe == self.TIMEFRAME_M15:
            found = (self.ny17.get((symbol, start))
                     or self.late.get((symbol, start)))
        else:
            return None
        return deepcopy([found]) if found is not None else []


class NativeW1NY17AnchorTests(unittest.TestCase):
    def setUp(self):
        self.api = NativeAnchorFake()

    def probe(self, *, api=None, now=NOW):
        return inspect(
            self.api if api is None else api,
            terminal_path=TERMINAL, now_utc=now)

    def safety(self, r):
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["native_weekly_candles_equivalent_to_ny17"])
        self.assertFalse(r["native_weekly_close_permitted_as_ny17_outcome"])
        self.assertFalse(r["historical_session_calendar_authenticated"])
        self.assertFalse(r["historic_original_feed_point_in_time_verified"])
        self.assertFalse(r["broker_utc_offset_for_historic_period_attested"])
        self.assertFalse(r["missing_ny17_m15_slots_waived"])
        self.assertFalse(r["price_values_exported"])
        self.assertFalse(r["historic_backfill_permitted"])
        self.assertFalse(r["causal_signal_verified"])
        self.assertFalse(r["directional_prediction_validated"])
        self.assertFalse(r["probability_calibrated"])
        self.assertFalse(r["market_watch_modified_by_script"])
        self.assertFalse(r["account_data_accessed"])
        self.assertFalse(r["orders_or_positions_accessed"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertEqual(r["files_written"], 0)

    def test_all_56_synthetic_closed_weeks_exhibit_late_vs_ny17_difference(self):
        result = self.probe()
        self.safety(result)
        self.assertEqual(result["state"],
                         "LAB_FX28_W1_CLOSE_REFERENCE_MISMATCH_DOCUMENTED_NO_GO")
        self.assertEqual(result["week_count"], 2)
        self.assertEqual(result["pair_week_comparisons"], 56)
        self.assertEqual(result["native_w1_close_equals_late_friday_m15"], 56)
        self.assertEqual(result["native_w1_close_equals_ny17_m15"], 0)
        self.assertEqual(result["native_w1_disagrees_with_ny17_pair_weeks"], 56)
        self.assertTrue(result["all_comparisons_structurally_available"])
        self.assertTrue(result["native_w1_sunday_utc_midnight_stamps_verified_locally"])
        self.assertEqual(
            result["weekly_diagnostics"]["2026-10-25"][
                "native_w1_candidate_late_close_offset_after_ny17_minutes"], 180)
        self.assertEqual(
            result["weekly_diagnostics"]["2026-11-01"][
                "native_w1_candidate_late_close_offset_after_ny17_minutes"], 120)
        self.assertEqual(
            {c[0] for c in self.api.calls},
            {"initialize", "terminal_info", "symbol_info", "copy_rates_range",
             "shutdown"})
        self.assertEqual(len([x for x in self.api.calls
                              if x[0] == "copy_rates_range"]), 56 * 3)
        self.assertEqual(self.api.calls[-1], ("shutdown",))

    def test_matching_price_does_not_confer_timestamp_equivalence(self):
        for k, v in self.api.ny17.items():
            matching = self.api.late[k[0],
                datetime.fromisoformat(
                    WEEKS["2026-10-25" if k[1].month == 10 else "2026-11-01"][2])]
            v["close"] = matching["close"]
            v["high"] = max(v["high"], v["close"])
        result = self.probe()
        self.safety(result)
        self.assertEqual(result["native_w1_close_equals_ny17_m15"], 56)
        self.assertTrue(result["all_comparisons_structurally_available"])
        self.assertFalse(result["native_weekly_close_permitted_as_ny17_outcome"])

    def test_missing_final_pair_week_blocks_and_discards_partial_counts(self):
        key = ( "CHFJPY", datetime(2026, 11, 1, tzinfo=UTC))
        self.api.native.pop(key)
        r = self.probe()
        self.safety(r)
        self.assertEqual(r["state"], "LAB_FX28_NATIVE_W1_NY17_ANCHOR_BLOCKED")
        self.assertIn("CHFJPY", r["pairs_with_incomplete_or_bad_native_data"])
        self.assertEqual(r["week_count"], 0)
        self.assertEqual(r["pair_week_comparisons"], 0)
        self.assertEqual(r["weekly_diagnostics"], {})

    def test_missing_any_one_ny17_bar_is_not_replaced_by_native_w1(self):
        self.api.ny17.pop(
            ("GBPNZD", datetime(2026, 10, 30, 20, 45, tzinfo=UTC)))
        r = self.probe()
        self.safety(r)
        self.assertEqual(r["state"], "LAB_FX28_NATIVE_W1_NY17_ANCHOR_BLOCKED")
        self.assertIn("GBPNZD", r["pairs_with_incomplete_or_bad_native_data"])

    def test_changed_native_w1_epoch_blocks(self):
        key = ("EURUSD", datetime(2026, 10, 25, tzinfo=UTC))
        self.api.native[key]["time"] += 3600
        r = self.probe()
        self.safety(r)
        self.assertEqual(r["state"], "LAB_FX28_NATIVE_W1_NY17_ANCHOR_BLOCKED")

    def test_offgrid_broker_quote_and_nan_are_rejected(self):
        for new_value in (1.123456, float("nan"), 0):
            with self.subTest(value=new_value):
                self.api = NativeAnchorFake()
                key = ("EURUSD", datetime(2026, 10, 25, tzinfo=UTC))
                self.api.native[key]["close"] = new_value
                r = self.probe()
                self.safety(r)
                self.assertEqual(r["state"], "LAB_FX28_NATIVE_W1_NY17_ANCHOR_BLOCKED")

    def test_corrupt_ohlc_or_tick_volume_block(self):
        for field, bad in (("high", 0.1), ("spread", -1), ("tick_volume", 0)):
            with self.subTest(field=field):
                self.api = NativeAnchorFake()
                key = ("USDJPY", datetime(2026, 10, 25, tzinfo=UTC))
                self.api.native[key][field] = bad
                r = self.probe()
                self.safety(r)
                self.assertIn("USDJPY", r["pairs_with_incomplete_or_bad_native_data"])

    def test_symbol_identity_and_quote_grid_must_stay_valid(self):
        self.api.specs["GBPCHF"]["currency_base"] = "EUR"
        r = self.probe()
        self.safety(r)
        self.assertEqual(r["reason"], "CANONICAL_SYMBOL_PRICE_GRID_INVALID")

    def test_market_watch_hidden_state_unchanged(self):
        before = set(self.api.visible)
        r = self.probe()
        self.safety(r)
        self.assertEqual(before, self.api.visible)
        self.assertTrue(r["all_comparisons_structurally_available"])
        self.assertFalse(any(c[0] == "symbol_select" for c in self.api.calls))

    def test_m15_late_different_from_native_is_still_not_trade_signal(self):
        key = ("AUDUSD", datetime(2026, 10, 30, 23, 45, tzinfo=UTC))
        data = self.api.late[key]
        data["close"] -= 0.00001
        r = self.probe()
        self.safety(r)
        self.assertEqual(r["native_w1_close_equals_late_friday_m15"], 55)
        self.assertTrue(r["all_comparisons_structurally_available"])
        self.assertFalse(r["native_weekly_close_permitted_as_ny17_outcome"])

    def test_future_or_naive_clock_blocks_before_any_terminal_access(self):
        for now in (
            datetime(2026, 11, 6, 23, 59, 59, tzinfo=UTC),
            NOW.replace(tzinfo=None),
            NOW + timedelta(microseconds=1),
        ):
            with self.subTest(when=now):
                self.api = NativeAnchorFake()
                r = self.probe(now=now)
                self.safety(r)
                self.assertEqual(r["state"], "LAB_FX28_NATIVE_W1_NY17_ANCHOR_BLOCKED")
                self.assertEqual(self.api.calls, [])

    def test_disconnected_terminal_never_accesses_prices(self):
        self.api.connected = False
        r = self.probe()
        self.safety(r)
        self.assertEqual(r["reason"], "MT5_TERMINAL_DISCONNECTED")
        self.assertEqual([x[0] for x in self.api.calls], ["initialize"])


if __name__ == "__main__":
    unittest.main()
