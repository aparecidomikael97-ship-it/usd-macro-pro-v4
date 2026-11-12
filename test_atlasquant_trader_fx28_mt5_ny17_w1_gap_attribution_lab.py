"""Offline 28 Forex NY17 W1 shared-vs-idiosyncratic-gap tests (synthetic)."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from copy import deepcopy
import unittest

from atlasquant_instrument_registry import FX_28
from atlasquant_trader_fx28_mt5_ny17_w1_gap_attribution_lab import (
    inspect_fx28_w1_readonly_gap_audit_lab as inspect, W1_WINDOWS_UTC,
    W1_M15_COUNT,
)
from test_atlasquant_trader_fx28_mt5_ny17_d1_gap_guard_lab import (
    FakeFX28, TERMINAL,
)

UTC = timezone.utc
START = datetime(2026, 11, 1, 22, tzinfo=UTC)
END = START + timedelta(days=5)
NOW = datetime(2026, 11, 12, 23, 30, tzinfo=UTC)
EPOCHS = tuple(int(START.timestamp()) + 900 * i for i in range(W1_M15_COUNT))


class FakeWeek(FakeFX28):
    def __init__(self):
        super().__init__()
        for sym in FX_28:
            close = 150.123 if sym.endswith("JPY") else 1.12345
            self.data[sym] = [
                {"time": t, "open": close, "high": close,
                 "low": close, "close": close, "tick_volume": 9,
                 "spread": 0, "real_volume": 0}
                for t in EPOCHS
            ]
        self.visible -= {"NZDUSD", "USDCHF", "USDCAD"}

    def copy_rates_range(self, sym, tf, first, last):
        self.calls.append(("copy_rates_range", sym, tf, first, last))
        return deepcopy(self.data[sym])


class WeekGapAttributionTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeWeek()

    def run_probe(self, *, day="2026-11-01", clock=NOW, api=None):
        return inspect(
            self.api if api is None else api, terminal_path=TERMINAL,
            reference_sunday_ny=day, clock=lambda: clock,
        )

    def safety(self, report):
        self.assertEqual(report["operational_bias"], "AGUARDAR")
        self.assertFalse(report["trade_authorized"])
        self.assertFalse(report["publishable"])
        self.assertFalse(report["live_alert_allowed"])
        self.assertFalse(report["scheduler_enabled"])
        self.assertFalse(report["worker_enabled"])
        self.assertFalse(report["source_feed_independently_verified"])
        self.assertFalse(report["reference_market_schedule_independently_authenticated"])
        self.assertFalse(report["historic_first_seen_point_in_time_verified"])
        self.assertFalse(report["future_d1_w1_forecasts_preregistered"])
        self.assertIsNone(report["calibrated_probability"])
        self.assertIsNone(report["validated_directional_accuracy"])
        self.assertFalse(report["account_accessed"])
        self.assertFalse(report["orders_positions_accessed"])
        self.assertFalse(report["market_watch_modified"])
        self.assertEqual(report["files_written"], 0)
        self.assertEqual(report["new_cost_brl"], 0)
        self.assertTrue(report["no_candles_interpolated_or_forward_filled"])

    def test_exact_28x480_structural_pass_still_no_forecast_or_trade(self):
        result = self.run_probe()
        self.safety(result)
        self.assertEqual(result["state"], "LAB_FX28_W1_NY17_FULL_GRID_HISTORY_ONLY_NO_GO")
        self.assertTrue(result["all_expected_weekly_m15_slots_present"])
        self.assertTrue(result["all_pairs_timeseries_structurally_valid"])
        self.assertEqual(result["expected_pairs"], 28)
        self.assertEqual(result["expected_slots_per_pair"], 480)
        self.assertEqual(result["total_expected_m15_slots"], 13440)
        self.assertEqual(result["complete_480_pairs"], 28)
        self.assertEqual(result["missing_slots_total"], 0)
        self.assertEqual(result["shared_missing_utc_slot_count"], 0)
        self.assertEqual(result["shared_missing_pair_slots_total"], 0)
        self.assertEqual(result["pair_specific_missing_slots_total"], 0)
        self.assertEqual(result["max_missing_pairs_at_one_timestamp"], 0)
        self.assertEqual(
            {x[0] for x in self.api.calls},
            {"initialize", "terminal_info", "symbol_info",
             "copy_rates_range", "shutdown"},
        )
        self.assertEqual(self.api.calls[-1][0], "shutdown")

    def test_8_global_initial_slots_plus_two_pair_specific_holes(self):
        for sym in FX_28:
            self.api.data[sym] = self.api.data[sym][8:]
        for sym, gap_index in (("GBPNZD", 50), ("CHFJPY", 60)):
            self.api.data[sym] = [
                x for x in self.api.data[sym]
                if x["time"] != EPOCHS[gap_index]]
        r = self.run_probe()
        self.safety(r)
        self.assertEqual(r["state"], "LAB_FX28_W1_NY17_SHARED_AND_PAIR_GAPS_NO_GO")
        self.assertFalse(r["all_expected_weekly_m15_slots_present"])
        self.assertTrue(r["all_pairs_timeseries_structurally_valid"])
        self.assertEqual(r["missing_slots_total"], 8 * 28 + 2)
        self.assertEqual(r["shared_missing_utc_slot_count"], 8)
        self.assertEqual(r["shared_missing_pair_slots_total"], 224)
        self.assertEqual(r["pair_specific_missing_slots_total"], 2)
        self.assertEqual(r["pair_specific_missing_by_symbol"]["GBPNZD"], 1)
        self.assertEqual(r["pair_specific_missing_by_symbol"]["CHFJPY"], 1)
        self.assertEqual(r["pair_specific_missing_by_symbol"]["EURUSD"], 0)
        self.assertEqual(r["max_missing_pairs_at_one_timestamp"], 28)
        self.assertEqual(r["complete_480_pairs"], 0)
        self.assertEqual(r["bounded_history_warmup_attempted"], list(FX_28))
        self.assertEqual(
            r["shared_missing_utc_first"],
            [datetime.fromtimestamp(t, UTC).isoformat() for t in EPOCHS[:8]],
        )

    def test_one_missing_pair_slot_is_not_global_market_closed(self):
        self.api.data["GBPUSD"].pop(4)
        r = self.run_probe()
        self.safety(r)
        self.assertTrue(r["all_pairs_timeseries_structurally_valid"])
        self.assertEqual(r["missing_slots_total"], 1)
        self.assertEqual(r["shared_missing_utc_slot_count"], 0)
        self.assertEqual(r["pair_specific_missing_slots_total"], 1)
        self.assertEqual(r["max_missing_pairs_at_one_timestamp"], 1)
        self.assertFalse(r["all_expected_weekly_m15_slots_present"])

    def test_utc_dst_week_boundary_changes_without_invented_bar(self):
        pre, post = W1_WINDOWS_UTC["2026-10-25"], W1_WINDOWS_UTC["2026-11-01"]
        self.assertEqual(pre, (
            "2026-10-25T21:00:00+00:00", "2026-10-30T21:00:00+00:00"))
        self.assertEqual(post, (
            "2026-11-01T22:00:00+00:00", "2026-11-06T22:00:00+00:00"))
        for span in (pre, post):
            self.assertEqual(
                datetime.fromisoformat(span[1])-datetime.fromisoformat(span[0]),
                timedelta(days=5))

    def test_clock_and_future_boundary_must_be_closed_before_touch_mt5(self):
        for day, clock in (
            ("2026-11-01", END - timedelta(microseconds=1)),
            ("2026-11-01", NOW.replace(tzinfo=None)),
            ("2026-11-02", NOW),
            ("2026-11-08", NOW),
            ("2026-11-01", NOW + timedelta(microseconds=1)),
        ):
            with self.subTest(day=day,clock=clock):
                self.api = FakeWeek()
                r = self.run_probe(day=day, clock=clock)
                self.safety(r)
                self.assertEqual(r["state"], "LAB_FX28_W1_READONLY_AUDIT_BLOCKED")
                self.assertEqual(self.api.calls, [])

    def test_missing_broker_symbol_blocks_aggregation_completely(self):
        del self.api.specs["EURJPY"]
        r = self.run_probe()
        self.safety(r)
        self.assertEqual(r["state"], "LAB_FX28_W1_READONLY_AUDIT_BLOCKED")
        self.assertIsNone(r["missing_slots_total"])
        self.assertIsNone(r["shared_missing_utc_slot_count"])
        self.assertIsNone(r["max_missing_pairs_at_one_timestamp"])
        self.assertFalse(r["all_pairs_timeseries_structurally_valid"])

    def test_duplicate_and_out_of_window_bar_block_group_counts(self):
        for bad in (EPOCHS[10], EPOCHS[10]+1, EPOCHS[-1]+900):
            with self.subTest(bad=bad):
                self.api = FakeWeek()
                self.api.data["AUDNZD"][11]["time"] = bad
                r = self.run_probe()
                self.safety(r)
                self.assertEqual(r["state"], "LAB_FX28_W1_READONLY_AUDIT_BLOCKED")
                self.assertIsNone(r["shared_missing_utc_slot_count"])

    def test_invalid_quote_tick_price_or_metadata_blocks_entire_week(self):
        for violation in ("offtick","badvolume","inconsistent_meta"):
            with self.subTest(violation=violation):
                self.api=FakeWeek()
                if violation == "offtick":
                    self.api.data["CHFJPY"][1]["close"] = 150.1234
                elif violation == "badvolume":
                    self.api.data["CHFJPY"][1]["tick_volume"] = 0
                else:
                    self.api.specs["CHFJPY"]["currency_profit"] = "USD"
                r = self.run_probe()
                self.safety(r)
                self.assertEqual(r["state"], "LAB_FX28_W1_READONLY_AUDIT_BLOCKED")
                self.assertFalse(r["all_expected_weekly_m15_slots_present"])

    def test_missing_quotes_not_replaced_with_flat_candles(self):
        for sym in FX_28:
            self.api.data[sym] = self.api.data[sym][8:]
        r = self.run_probe()
        self.safety(r)
        self.assertEqual(r["shared_missing_utc_slot_count"], 8)
        self.assertEqual(r["pair_specific_missing_slots_total"], 0)
        self.assertFalse(r["all_expected_weekly_m15_slots_present"])
        self.assertEqual(r["complete_480_pairs"], 0)

    def test_visible_hidden_state_preserved_on_success(self):
        original = set(self.api.visible)
        r = self.run_probe()
        self.safety(r)
        self.assertEqual(self.api.visible, original)
        self.assertIn("NZDUSD", r["symbols_hidden_when_queried"])
        self.assertEqual(len([x for x in self.api.calls
                              if x[0] == "copy_rates_range"]), 28)


if __name__ == "__main__":
    unittest.main()
