"""A280: delayed pivots, BOS/CHOCH chronology and FVG filter in LAB."""
from datetime import datetime, timedelta, timezone
from unittest import mock
import unittest

import atlasquant_aion_causal_structure_lab as structure
from atlasquant_aion_causal_structure_lab import (
    SCHEMA, STRUCTURE_SPEC, generate_causal_structure_csv,
    research_structure_filtered_backtest_csv,
)
from atlasquant_aion_causal_fvg_lab import generate_causal_fvg_csv

START = datetime(2026, 9, 30, 22, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)

# Each row: (close, high, low); open=close, all geometry consistent.
# Confirm swing high at 3 on close of 5; break UP at 6 (INITIAL).
# Confirm high at 8 on close of 10; break UP at 11 (BOS).
# Confirm low at 14 on close of 16; break DOWN at 17 (CHOCH).
ROWS = [
    (10, 10.4, 9.6), (11, 11.4, 10.6), (12, 12.4, 11.6),
    (14, 15.0, 13.5), (12, 12.5, 11.5), (11, 11.5, 10.5),
    (16, 16.5, 15.5), (17, 17.5, 16.5), (18, 19.0, 17.5),
    (16, 16.5, 15.5), (15, 15.5, 14.5), (20, 20.5, 19.5),
    (19, 19.5, 18.5), (18, 18.5, 17.5), (15, 15.5, 14.0),
    (18, 18.5, 17.5), (19, 19.5, 18.5), (13, 13.5, 12.5),
    (12, 12.5, 11.5), (11, 11.5, 10.5),
]


def stamp(i):
    return (START + timedelta(minutes=15*i)).isoformat()


def csv_data(rows=ROWS):
    lines = ["closed_at,open,high,low,close"]
    for i, (close, high, low) in enumerate(rows):
        lines.append(f"{stamp(i)},{close},{high},{low},{close}")
    return "\n".join(lines) + "\n"


def report(rows=ROWS, **kw):
    args = {"symbol": "EURUSD", "timeframe": "M15",
            "timestamp_basis": "CLOSE", "now": NOW}
    args.update(kw)
    return generate_causal_structure_csv(csv_data(rows), **args)


def backtest(rows=ROWS, **kw):
    args = {"symbol": "EURUSD", "timeframe": "M15",
            "timestamp_basis": "CLOSE", "now": NOW,
            "validation_start": stamp(8),
            "cost_r": 0.1, "slippage_r": 0.05,
            "max_wait_bars": 3, "max_hold_bars": 4}
    args.update(kw)
    return research_structure_filtered_backtest_csv(csv_data(rows), **args)


def event_at(result, index):
    return next(x for x in result["structure_events"]
                if x["detected_at"] == stamp(index))


def decision_at(result, index):
    return next(x for x in result["filter_decisions"]
                if x["signal_time"] == stamp(index))


class A280CausalStructureTests(unittest.TestCase):
    def test_01_structure_is_only_mechanical_historical_research(self):
        result = report()
        self.assertEqual(result["schema"], SCHEMA)
        self.assertTrue(result["valid"])
        self.assertTrue(result["historical_only"])
        self.assertTrue(result["research_only"])
        self.assertFalse(result["actual_ict_structure_verified"])
        self.assertFalse(result["actual_fvg_validity_verified"])
        self.assertFalse(result["external_structure_attested"])
        self.assertFalse(result["reversal_is_a_forecast"])
        self.assertTrue(result["no_future_pivot_confirmation"])
        self.assertTrue(result["no_new_data_calls"])
        self.assertTrue(result["no_orders"])
        self.assertFalse(result["authorizes_send"])
        self.assertEqual(result["p0_homologated"], 0)

    def test_02_pivot_confirmed_two_bars_later_never_backdated(self):
        result = report()
        first = event_at(result, 6)
        self.assertEqual(first["kind"], "INITIAL_BREAK")
        self.assertEqual(first["direction"], "UP")
        self.assertEqual(first["pivot_time"], stamp(3))
        self.assertEqual(first["pivot_confirmed_at"], stamp(5))
        self.assertEqual(first["pivot_confirmed_index"], 5)
        self.assertEqual(first["bar_index"], 6)
        self.assertEqual(first["observed_closed_bars"], 7)
        self.assertTrue(first["no_future_confirmation"])

    def test_03_second_up_break_is_bos_not_first_break(self):
        second = event_at(report(), 11)
        self.assertEqual(second["kind"], "BOS")
        self.assertEqual(second["direction"], "UP")
        self.assertEqual(second["pivot_time"], stamp(8))
        self.assertEqual(second["pivot_confirmed_at"], stamp(10))
        self.assertEqual(second["pivot_level"], 19.0)

    def test_04_opposite_break_marks_choch_not_future_prediction(self):
        result = report()
        last = event_at(result, 17)
        self.assertEqual(last["kind"], "CHOCH")
        self.assertEqual(last["direction"], "DOWN")
        self.assertEqual(last["pivot_time"], stamp(14))
        self.assertEqual(last["pivot_confirmed_at"], stamp(16))
        self.assertEqual(result["reversal_context_records"], [last])
        self.assertFalse(result["reversal_is_a_forecast"])
        self.assertTrue(result["no_alerts"])

    def test_05_only_bos_aligned_fvg_is_promoted_to_research_candidate(self):
        result = report()
        self.assertGreaterEqual(result["original_fvg_candidate_count"], 3)
        first = decision_at(result, 6)
        self.assertFalse(first["accepted"])
        self.assertEqual(first["last_structure_kind"], "INITIAL_BREAK")
        self.assertEqual(first["reason"], "LATEST_STRUCTURE_NOT_BOS")
        continuation = decision_at(result, 11)
        self.assertTrue(continuation["accepted"])
        self.assertEqual(continuation["reason"], "BOS_ALIGNED_FIXED_FILTER")
        self.assertEqual(continuation["last_structure_direction"], "UP")
        reversal = decision_at(result, 17)
        self.assertFalse(reversal["accepted"])
        self.assertEqual(reversal["last_structure_kind"], "CHOCH")
        self.assertTrue(any(p["signal_time"] == stamp(11)
                            for p in result["filtered_candidate_plans"]))
        self.assertFalse(any(p["signal_time"] == stamp(17)
                             for p in result["filtered_candidate_plans"]))

    def test_06_all_pivots_must_precede_break_detection(self):
        result = report()
        self.assertTrue(all(event["pivot_confirmed_index"] < event["bar_index"]
                            for event in result["structure_events"]))
        self.assertTrue(all(event["pivot_confirmed_at"] < event["detected_at"]
                            for event in result["structure_events"]))

    def test_07_prefix_invariance_after_appending_future_candles(self):
        full = report()
        prefix = report(ROWS[:12])
        old_events = [e for e in full["structure_events"]
                      if e["bar_index"] <= 11]
        old_decisions = [e for e in full["filter_decisions"]
                         if e["signal_time"] <= stamp(11)]
        self.assertEqual(prefix["structure_events"], old_events)
        self.assertEqual(prefix["filter_decisions"], old_decisions)
        self.assertNotEqual(prefix["last_prefix_sha256"],
                            full["last_prefix_sha256"])

    def test_08_future_candle_mutation_cannot_change_old_bos_or_filter(self):
        future = list(ROWS)
        future[18] = (12, 15, 10)
        before, after = report(), report(future)
        old_breaks = [x for x in before["structure_events"]
                      if x["bar_index"] <= 11]
        new_breaks = [x for x in after["structure_events"]
                      if x["bar_index"] <= 11]
        self.assertEqual(old_breaks, new_breaks)
        self.assertEqual(decision_at(before, 11), decision_at(after, 11))

    def test_09_same_pivot_cannot_create_multiple_breaks(self):
        result = report()
        first_pivot = stamp(3)
        breaks = [x for x in result["structure_events"]
                  if x["pivot_time"] == first_pivot]
        self.assertEqual(len(breaks), 1)

    def test_10_flat_prices_do_not_invent_market_structure(self):
        flat = [(10, 10.2, 9.8)] * 20
        result = report(flat)
        self.assertTrue(result["valid"])
        self.assertEqual(result["structure_events"], [])
        self.assertEqual(result["reversal_context_records"], [])
        self.assertEqual(result["filtered_candidate_plans"], [])

    def test_11_short_history_keeps_empty_context_not_fake_bos(self):
        result = report(ROWS[:5])
        self.assertTrue(result["valid"])
        self.assertEqual(result["structure_events"], [])
        self.assertEqual(result["filtered_candidate_count"], 0)

    def test_12_filtered_causal_plans_reach_sealed_a277_holdout_only(self):
        result = backtest()
        self.assertTrue(result["valid"])
        self.assertEqual(result["validation_start_utc"], stamp(8))
        self.assertEqual(result["train"]["candle_count"], 8)
        self.assertEqual(result["holdout"]["candle_count"], 12)
        self.assertEqual(result["train"]["summary"]["trades"], 0)
        self.assertGreaterEqual(result["holdout"]["summary"]["trades"], 1)
        self.assertFalse(result["authorizes_send"])
        self.assertTrue(result["no_orders"])
        self.assertEqual(result["p0_homologated"], 0)

    def test_13_bad_boundary_or_friction_remains_failclosed(self):
        wrong = backtest(validation_start="2026-10-01T00:07:00+00:00")
        self.assertFalse(wrong["valid"])
        self.assertIsNone(wrong["train"])
        self.assertIsNone(wrong["holdout"])
        self.assertFalse(wrong["authorizes_send"])
        bad_cost = backtest(cost_r=-1)
        self.assertFalse(bad_cost["valid"])
        self.assertIsNone(bad_cost["train"])

    def test_14_unknown_symbols_or_futures_contract_aliases_rejected(self):
        for symbol in ("US100", "EUR/USD", "WINZ26", "WDOX26", "BTCUSD"):
            with self.subTest(symbol=symbol):
                result = report(symbol=symbol)
                self.assertFalse(result["valid"])
                self.assertEqual(result["filtered_candidate_plans"], [])

    def test_15_nonfx_radar_identifiers_are_research_only(self):
        for symbol in ("DXY", "US30", "NAS100", "SPX500", "IBOV", "WIN", "WDO"):
            with self.subTest(symbol=symbol):
                result = report(symbol=symbol)
                self.assertTrue(result["valid"])
                self.assertFalse(result["external_structure_attested"])
                self.assertFalse(result["actual_ict_structure_verified"])
                self.assertFalse(result["authorizes_send"])

    def test_16_no_fake_a278_receipt_or_reversal_alert(self):
        result = backtest()
        self.assertFalse(result["plans_captured_when_generated"])
        self.assertFalse(result["external_structure_attested"])
        self.assertFalse(result["actual_ict_structure_verified"])
        self.assertNotIn("plan_journal_head_sha256", result)
        self.assertTrue(result["no_alerts"])

    def test_17_invalid_csv_blocks_both_detectors_without_partial_output(self):
        bad = csv_data().replace("16,16.5,15.5,16", "16,NaN,15.5,16")
        result = generate_causal_structure_csv(
            bad, symbol="EURUSD", timeframe="M15",
            timestamp_basis="CLOSE", now=NOW,
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["structure_events"], [])
        self.assertEqual(result["filtered_candidate_plans"], [])
        self.assertTrue(result["error"].startswith("INVALID_HISTORICAL_CSV:"))

    def test_18_fvg_and_structure_share_exact_historical_prefix_hash(self):
        result = report()
        fvg = generate_causal_fvg_csv(
            csv_data(), symbol="EURUSD", timeframe="M15",
            timestamp_basis="CLOSE", now=NOW,
        )
        by_time = {a["signal_time"]: a["prefix_sha256"]
                   for a in fvg["candidate_audit"]}
        self.assertEqual(
            [x["fvg_prefix_sha256"] for x in result["filter_decisions"]],
            [by_time[x["signal_time"]] for x in result["filter_decisions"]],
        )
        self.assertEqual(result["normalized_candles_sha256"],
                         fvg["normalized_candles_sha256"])

    def test_19_filter_parameters_fixed_no_adaptive_holdout_optimization(self):
        result = report()
        self.assertEqual(STRUCTURE_SPEC["pivot_left_closed_bars"], 2)
        self.assertEqual(STRUCTURE_SPEC["pivot_right_closed_bars"], 2)
        self.assertEqual(STRUCTURE_SPEC["fvg_filter"],
                         "LATEST_BOS_SAME_SIDE_WITHIN_8_BARS")
        self.assertEqual(len(result["structure_spec_sha256"]), 64)
        self.assertEqual(result["structure_spec_sha256"],
                         report()["structure_spec_sha256"])

    def test_20_stale_bos_does_not_authorize_delayed_fvg(self):
        normal = report()
        # Bar 12 itself is a bullish FVG after BOS at bar 11.
        self.assertTrue(decision_at(normal, 12)["accepted"])
        with mock.patch.object(structure, "MAX_BOS_AGE_BARS", 0):
            strict = report()
        self.assertFalse(decision_at(strict, 12)["accepted"])
        self.assertEqual(decision_at(strict, 12)["reason"], "STALE_BOS")
        self.assertFalse(strict["authorizes_send"])


if __name__ == "__main__":
    unittest.main()
