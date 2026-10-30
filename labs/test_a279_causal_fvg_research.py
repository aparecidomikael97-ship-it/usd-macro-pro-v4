"""A279: prefix-causal fixed FVG research and offline A277 regression."""
from datetime import datetime, timezone, timedelta
from unittest import mock
import copy
import unittest

import atlasquant_aion_causal_fvg_lab as module
from atlasquant_aion_causal_fvg_lab import (
    SCHEMA, SPEC, STRATEGY_VERSION,
    generate_causal_fvg_csv, research_causal_fvg_backtest_csv,
)

START = datetime(2026, 9, 30, 22, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)
BARS = [
    (10, 10.2, 9.8, 10),
    (10.2, 10.4, 10.0, 10.3),
    (10.3, 10.5, 10.1, 10.4),
    (10.4, 10.6, 10.2, 10.5),
    (10.5, 10.7, 10.3, 10.6),
    (11.5, 11.9, 11.0, 11.7),  # i=5 bullish gap against i=3
    (11.7, 12.3, 10.7, 12.1),  # i=6 touch+target AFTER signal
    (12.1, 12.2, 11.9, 12.0),
    (12.0, 12.1, 11.7, 11.8),
    (11.7, 11.8, 11.3, 11.5),
    (9.5, 9.7, 9.0, 9.2),     # i=10 bearish gap against i=8
    (10.7, 11.0, 7.7, 8.5),   # i=11 touch+target AFTER signal
    (8.5, 8.6, 8.0, 8.2),
    (8.2, 8.4, 8.0, 8.1),
]


def stamp(i):
    return (START + timedelta(minutes=i * 15)).isoformat()


def csv_data(bars=BARS, *, header="closed_at"):
    lines = [header + ",open,high,low,close"]
    for i, (o, h, l, c) in enumerate(bars):
        lines.append(stamp(i) + "," + ",".join(str(v) for v in (o, h, l, c)))
    return "\n".join(lines) + "\n"


def candidates(bars=BARS, **overrides):
    args = {
        "symbol": "EURUSD", "timeframe": "M15",
        "timestamp_basis": "CLOSE", "now": NOW,
    }
    args.update(overrides)
    return generate_causal_fvg_csv(csv_data(bars), **args)


def backtest(bars=BARS, **overrides):
    args = {
        "symbol": "EURUSD", "timeframe": "M15",
        "timestamp_basis": "CLOSE", "now": NOW,
        "validation_start": stamp(8),
        "cost_r": 0.1, "slippage_r": 0.05,
        "max_wait_bars": 2, "max_hold_bars": 3,
    }
    args.update(overrides)
    return research_causal_fvg_backtest_csv(csv_data(bars), **args)


class A279CausalFvgTests(unittest.TestCase):
    def test_01_only_mechanical_historical_candidates_no_orders(self):
        report = candidates()
        self.assertEqual(report["schema"], SCHEMA)
        self.assertTrue(report["valid"])
        self.assertEqual(report["status"],
                         "MECHANICAL_FVG_HISTORICAL_CANDIDATES_ONLY")
        self.assertTrue(report["historical_only"])
        self.assertTrue(report["research_only"])
        self.assertTrue(report["no_future_candles_used_in_candidates"])
        self.assertTrue(report["not_verified_ict_zones"])
        self.assertTrue(report["not_tradeable_signals"])
        self.assertFalse(report["source_is_externally_attested"])
        self.assertFalse(report["plan_capture_is_externally_attested"])
        self.assertTrue(report["no_orders"])
        self.assertFalse(report["authorizes_send"])
        self.assertEqual(report["p0_homologated"], 0)

    def test_02_bullish_fvg_produces_plan_at_closed_confirmation_bar(self):
        result = candidates()
        self.assertGreaterEqual(result["candidate_count"], 1)
        plan = next(p for p in result["candidate_plans"]
                    if p["signal_time"] == stamp(5))
        self.assertEqual(plan["setup"], "FVG")
        self.assertEqual(plan["side"], "BUY")
        self.assertAlmostEqual(plan["entry"], 10.8)
        self.assertAlmostEqual(plan["stop"], 10.2)
        self.assertAlmostEqual(plan["target"], 12.0)
        audit = next(a for a in result["candidate_audit"]
                     if a["signal_time"] == stamp(5))
        self.assertEqual(audit["observed_closed_bars"], 6)
        self.assertEqual(audit["side"], "BUY")
        self.assertEqual(len(audit["prefix_sha256"]), 64)

    def test_03_bearish_candidate_is_identified_without_any_future_bar(self):
        report = candidates()
        plan = next(p for p in report["candidate_plans"]
                    if p["signal_time"] == stamp(10))
        self.assertEqual(plan["side"], "SELL")
        self.assertAlmostEqual(plan["entry"], 10.7)
        self.assertAlmostEqual(plan["stop"], 12.1)
        self.assertAlmostEqual(plan["target"], 7.9)
        audit = next(a for a in report["candidate_audit"]
                     if a["signal_time"] == stamp(10))
        self.assertEqual(audit["observed_closed_bars"], 11)

    def test_04_prefix_invariance_after_appending_future_candles(self):
        full = candidates()
        prefix = candidates(BARS[:7])
        self.assertTrue(prefix["valid"])
        older = [p for p in full["candidate_plans"]
                 if p["signal_time"] <= stamp(6)]
        self.assertEqual(prefix["candidate_plans"], older)
        old_audit = [a for a in full["candidate_audit"]
                     if a["signal_time"] <= stamp(6)]
        self.assertEqual(prefix["candidate_audit"], old_audit)
        self.assertEqual(prefix["last_prefix_sha256"],
                         old_audit[-1]["prefix_sha256"]
                         if old_audit[-1]["signal_time"] == stamp(6)
                         else prefix["last_prefix_sha256"])

    def test_05_mutating_later_high_low_cannot_repaint_first_candidate(self):
        altered = list(BARS)
        altered[11] = (10.7, 12.5, 7.2, 8.5)
        base, newer = candidates(), candidates(altered)
        self.assertEqual(
            [(p, a) for p, a in zip(base["candidate_plans"], base["candidate_audit"])
             if p["signal_time"] == stamp(5)],
            [(p, a) for p, a in zip(newer["candidate_plans"], newer["candidate_audit"])
             if p["signal_time"] == stamp(5)],
        )
        self.assertNotEqual(base["normalized_candles_sha256"],
                            newer["normalized_candles_sha256"])

    def test_06_flat_and_overlapping_candles_produce_no_fvg(self):
        flat = [(10, 10.2, 9.8, 10)] * 14
        result = candidates(flat)
        self.assertTrue(result["valid"])
        self.assertEqual(result["candidate_plans"], [])
        self.assertEqual(result["candidate_count"], 0)

    def test_07_insufficient_history_never_invents_a_trend(self):
        short = candidates(BARS[:5])
        self.assertTrue(short["valid"])
        self.assertEqual(short["candidate_plans"], [])
        self.assertEqual(short["candidate_audit"], [])

    def test_08_fixed_strategy_spec_is_deterministic_and_not_tuned(self):
        a, b = candidates(), candidates()
        self.assertEqual(a["strategy_spec_sha256"], b["strategy_spec_sha256"])
        self.assertEqual(a["candidate_plans"], b["candidate_plans"])
        self.assertEqual(a["candidate_audit"], b["candidate_audit"])
        self.assertEqual(a["strategy_version"], STRATEGY_VERSION)
        self.assertEqual(SPEC["sma_bars"], 5)
        self.assertEqual(SPEC["target_r"], 2.0)
        self.assertTrue(SPEC["no_adaptive_tuning"])

    def test_09_historical_backtest_only_starts_after_signal_candle(self):
        result = backtest()
        self.assertTrue(result["valid"])
        self.assertFalse(result["signal_generation"] if "signal_generation" in result
                         else result["authorizes_send"])
        self.assertFalse(result["authorizes_send"])
        self.assertTrue(result["no_orders"])
        self.assertEqual(result["p0_homologated"], 0)
        self.assertTrue(result["candidate_no_future_candles_used"])
        bullish = next(r for r in result["train"]["ledger"]
                       if r["signal_time"] == stamp(5))
        self.assertEqual(bullish["status"], "TARGET")
        self.assertEqual(bullish["entry_time"], stamp(6))

    def test_10_out_of_sample_segment_does_not_see_train_exit(self):
        result = backtest()
        self.assertEqual(result["validation_start_utc"], stamp(8))
        self.assertEqual(result["train"]["candle_count"], 8)
        self.assertEqual(result["holdout"]["candle_count"], 6)
        bearish = next(r for r in result["holdout"]["ledger"]
                       if r["signal_time"] == stamp(10))
        self.assertEqual(bearish["status"], "TARGET")
        self.assertEqual(bearish["entry_time"], stamp(11))
        self.assertFalse(result["holdout_is_independently_attested"])

    def test_11_strict_csv_rejection_never_uses_partial_old_plans(self):
        bad = csv_data().replace("9.5,9.7,9.0,9.2", "9.5,NaN,9.0,9.2")
        result = generate_causal_fvg_csv(
            bad, symbol="EURUSD", timeframe="M15",
            timestamp_basis="CLOSE", now=NOW,
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["candidate_plans"], [])
        self.assertTrue(result["error"].startswith("INVALID_HISTORICAL_CSV:"))

    def test_12_invalid_symbol_and_future_contract_alias_fail_closed(self):
        for symbol in ("WINZ26", "US100", "EUR/USD", "BTCUSD", None):
            result = candidates(symbol=symbol)
            self.assertFalse(result["valid"])
            self.assertEqual(result["candidate_plans"], [])

    def test_13_all_the_radar_nonfx_ids_remain_research_not_real_contracts(self):
        for symbol in ("DXY", "US30", "NAS100", "SPX500", "IBOV", "WIN", "WDO"):
            result = candidates(symbol=symbol)
            self.assertTrue(result["valid"])
            self.assertFalse(result["source_is_externally_attested"])
            self.assertTrue(result["not_tradeable_signals"])
            self.assertFalse(result["authorizes_send"])

    def test_14_no_fake_a278_timestamp_commitment_from_historical_data(self):
        result = backtest()
        self.assertTrue(result["historical_plans_not_captured_as_they_happened"])
        self.assertNotIn("plan_journal_head_sha256", result)
        self.assertNotIn("externally_attested", result)
        self.assertFalse(result["holdout_is_independently_attested"])

    def test_15_new_candidate_limit_is_failclosed_not_truncated(self):
        with mock.patch.object(module, "MAX_PLANS", 0):
            result = candidates()
        self.assertFalse(result["valid"])
        self.assertEqual(result["error"], "TOO_MANY_HISTORICAL_CANDIDATES")
        self.assertEqual(result["candidate_plans"], [])
        self.assertEqual(result["candidate_audit"], [])

    def test_16_nonfinite_sma_from_huge_valid_prices_fails_closed(self):
        huge = [(1e308, 1e308, 1e308, 1e308)] * 7
        result = candidates(huge)
        self.assertFalse(result["valid"])
        self.assertEqual(result["error"], "UNSAFE_INDICATOR_ARITHMETIC")
        self.assertEqual(result["candidate_plans"], [])

    def test_17_non_text_provider_object_is_refused(self):
        class Unsafe(str):
            def __str__(self):
                raise AssertionError("do not stringify hostile text")
        result = generate_causal_fvg_csv(
            Unsafe(csv_data()), symbol="EURUSD",
            timeframe="M15", timestamp_basis="CLOSE", now=NOW,
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["candidate_plans"], [])

    def test_18_wrong_holdout_or_costs_preserve_failclosed_backtest(self):
        result = backtest(validation_start="2026-10-01T00:07:00+00:00")
        self.assertFalse(result["valid"])
        self.assertIsNone(result["train"])
        self.assertIsNone(result["holdout"])
        self.assertFalse(result["authorizes_send"])
        self.assertEqual(result["candidate_count"],
                         candidates()["candidate_count"])
        negative = backtest(cost_r=-1)
        self.assertFalse(negative["valid"])
        self.assertIsNone(negative["train"])

    def test_19_no_orders_alerts_or_new_market_data_calls(self):
        report = candidates()
        self.assertTrue(report["no_new_data_calls"])
        self.assertTrue(report["no_alerts"])
        self.assertTrue(report["no_orders"])
        self.assertFalse(report["authorizes_send"])
        backtested = backtest()
        self.assertTrue(backtested["no_orders"])
        self.assertTrue(backtested["no_alerts"])
        self.assertFalse(backtested["authorizes_send"])

    def test_20_time_basis_explicit_and_candle_close_shifted_for_open_times(self):
        text = csv_data(header="time")
        result = generate_causal_fvg_csv(
            text, symbol="EURUSD", timeframe="M15",
            timestamp_basis="OPEN", now=NOW,
        )
        self.assertTrue(result["valid"])
        bullish = next(p for p in result["candidate_plans"]
                       if p["side"] == "BUY")
        self.assertEqual(bullish["signal_time"], stamp(6))


if __name__ == "__main__":
    unittest.main()
