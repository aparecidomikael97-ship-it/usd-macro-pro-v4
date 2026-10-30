"""A277: offline/manual backtests, chrono holdout and no boundary leak."""
from datetime import datetime, timedelta, timezone
import math
import unittest

from atlasquant_aion_csv_backtest_lab import (
    SCHEMA, SETUPS, MAX_PLANS, research_backtest_csv,
)

BASE = datetime(2026, 9, 30, 22, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)
OHLC = [
    (10, 10.2, 9.8, 10),   # train 0 / BUY declared
    (10, 10.2, 9.9, 10),   # train 1 / BUY entry
    (10, 12.2, 10, 12),   # train 2 / BUY target
    (12, 12.1, 11.5, 12),
    (11, 11.4, 10.7, 11), # train 4 / SELL declared
    (11, 11.2, 10.8, 11), # train 5 / SELL entry
    (11, 11.2, 8.8, 9),   # train 6 / SELL target
    (9, 9.2, 8.7, 9),
    (10, 10.2, 9.8, 10),  # holdout 8 / BUY declared
    (10, 10.2, 9.9, 10),  # holdout 9 / BUY entry
    (10, 10.1, 8.8, 9),   # holdout 10 / stop
    (10, 10.2, 9.8, 10),  # holdout 11 / BUY declared
    (10, 10.1, 9.9, 10),  # holdout 12 / BUY entry
    (10, 12.2, 10, 12),   # holdout 13 / target
    (10, 10.2, 9.8, 10),
    (10, 10.2, 9.8, 10),
]


def stamp(i):
    return (BASE + timedelta(minutes=15 * i)).isoformat()


def csv_data(rows=OHLC):
    lines = ["closed_at,open,high,low,close"]
    for index, prices in enumerate(rows):
        lines.append(stamp(index) + "," + ",".join(str(x) for x in prices))
    return "\n".join(lines) + "\n"


def plan(i, setup="FVG", side="BUY", entry=10, stop=9, target=12):
    return {"signal_time": stamp(i), "setup": setup, "side": side,
            "entry": entry, "stop": stop, "target": target}


PLANS = [
    plan(0),
    plan(4, "OB", "SELL", 11, 12, 9),
    plan(8),
    plan(11, "OB"),
]


def study(plans=None, **overrides):
    kwargs = {
        "symbol": "EURUSD",
        "timeframe": "M15", "timestamp_basis": "CLOSE",
        "now": NOW, "validation_start": stamp(8),
        "manual_plans": PLANS if plans is None else plans,
        "cost_r": 0.10, "slippage_r": 0.05,
        "max_wait_bars": 2, "max_hold_bars": 3,
    }
    kwargs.update(overrides)
    return research_backtest_csv(csv_data(), **kwargs)


class A277ManualBacktestTests(unittest.TestCase):
    def assert_rejected(self, plans=None, reason=None, **kw):
        result = study(plans, **kw)
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "INVALID_OR_UNATTESTED_BACKTEST_INPUT")
        self.assertIsNone(result["train"])
        self.assertIsNone(result["holdout"])
        self.assertTrue(result["no_orders"])
        self.assertFalse(result["authorizes_send"])
        self.assertEqual(result["p0_homologated"], 0)
        if reason is not None:
            self.assertEqual(result["error"], reason)

    def test_01_reuses_engine_with_explicit_manual_plans_only(self):
        report = study()
        self.assertEqual(report["schema"], SCHEMA)
        self.assertTrue(report["valid"])
        self.assertEqual(report["status"], "HISTORICAL_MANUAL_BACKTEST_UNATTESTED")
        self.assertFalse(report["signal_generation"])
        self.assertTrue(report["manual_plans_unattested"])
        self.assertFalse(report["holdout_is_independently_attested"])
        self.assertTrue(report["no_lookahead_execution"])
        self.assertTrue(report["single_position_per_asset"])
        self.assertTrue(report["no_new_data_calls"])
        self.assertFalse(report["authorizes_send"])
        self.assertEqual(report["p0_homologated"], 0)

    def test_02_monthly_train_vs_holdout_are_never_mixed(self):
        result = study()
        self.assertEqual(result["train"]["candle_count"], 8)
        self.assertEqual(result["holdout"]["candle_count"], 8)
        self.assertEqual(result["validation_start_utc"], stamp(8))
        self.assertEqual(result["train"]["summary"]["trades"], 2)
        self.assertEqual(result["holdout"]["summary"]["trades"], 2)
        self.assertEqual(result["train"]["summary"]["net_r"], 3.7)
        self.assertEqual(result["holdout"]["summary"]["net_r"], 0.7)
        self.assertEqual([m["month_utc"] for m in result["train"]["monthly_utc"]],
                         ["2026-09"])
        self.assertEqual([m["month_utc"] for m in result["holdout"]["monthly_utc"]],
                         ["2026-10"])

    def test_03_friction_subtracted_from_each_execution_in_r(self):
        result = study()
        row = result["train"]["ledger"][0]
        self.assertEqual(row["status"], "TARGET")
        self.assertEqual(row["gross_r"], 2.0)
        self.assertAlmostEqual(row["net_r"], 1.85)
        self.assertAlmostEqual(row["cost_r"], 0.10)
        self.assertAlmostEqual(row["slippage_r"], 0.05)
        self.assertEqual(result["train"]["summary"]["gross_r"], 4.0)
        self.assertEqual(result["train"]["summary"]["cost_r"], 0.2)
        self.assertEqual(result["train"]["summary"]["slippage_r"], 0.1)

    def test_04_stressed_friction_has_lower_net_without_changing_entries(self):
        report = study()
        scenarios = report["holdout"]["friction_scenarios"]
        self.assertEqual([x["scenario"] for x in scenarios],
                         ["ZERO_FRICTION", "CONFIGURED", "STRESS_X2"])
        self.assertEqual([round(x["net_r"], 2) for x in scenarios],
                         [1.0, 0.7, 0.4])
        self.assertEqual([x["executed_trades"] for x in scenarios], [2, 2, 2])

    def test_05_descriptive_setups_not_ranked_as_predictions(self):
        report = study()
        self.assertEqual(SETUPS, {"FVG", "OB", "PULLBACK"})
        comparison = report["holdout"]["setups"]
        self.assertEqual([row["setup"] for row in comparison],
                         ["FVG", "OB", "PULLBACK"])
        self.assertEqual([row["trades"] for row in comparison], [1, 1, 0])
        self.assertTrue(all(x["sample_status"] == "INSUFFICIENT_SAMPLE"
                            for x in comparison))
        self.assertNotIn("probability", repr(report).lower())

    def test_06_candle_that_forms_the_signal_is_not_traded(self):
        altered = list(OHLC)
        altered[0] = (10, 20, 1, 10)  # would hit stop+target at the signal
        kwargs = {
            "symbol": "EURUSD", "timeframe": "M15",
            "timestamp_basis": "CLOSE", "now": NOW,
            "validation_start": stamp(8), "manual_plans": [plan(0)],
            "cost_r": 0.0, "slippage_r": 0.0,
            "max_wait_bars": 2, "max_hold_bars": 3,
        }
        report = research_backtest_csv(csv_data(altered), **kwargs)
        self.assertTrue(report["valid"])
        self.assertEqual(report["train"]["ledger"][0]["status"], "TARGET")
        self.assertEqual(report["train"]["ledger"][0]["entry_time"], stamp(1))

    def test_07_train_plan_cannot_use_holdout_bar_for_exit(self):
        report = study([plan(6, "PULLBACK", "BUY", 9, 7, 14)])
        result = report["train"]["ledger"][0]
        self.assertEqual(result["status"], "CENSORED_AT_PARTITION_END")
        self.assertEqual(result["outcome"], "NO_TRADE")
        self.assertEqual(result["reason"], "HOLD_WINDOW_NOT_OBSERVED")
        self.assertIsNone(result["net_r"])
        self.assertIsNone(result["gross_r"])
        self.assertIsNone(result["exit_time"])
        self.assertEqual(report["train"]["summary"]["trades"], 0)
        self.assertEqual(report["train"]["censored_trades"], 1)

    def test_08_holdout_censored_plan_blocks_later_overlap(self):
        report = study([
            plan(14, "PULLBACK", "BUY", 10, 8, 15),
            plan(15, "FVG", "BUY", 10, 8, 15),
        ])
        ledger = report["holdout"]["ledger"]
        self.assertEqual(ledger[0]["status"], "CENSORED_AT_PARTITION_END")
        self.assertEqual(ledger[1]["status"], "OVERLAP_BLOCKED")
        self.assertEqual(ledger[1]["reason"], "UNRESOLVED_PRIOR_POSITION")
        self.assertEqual(report["holdout"]["summary"]["trades"], 0)

    def test_09_overlapping_manual_plans_do_not_double_trade(self):
        report = study([plan(8), plan(9, "OB")])
        ledger = report["holdout"]["ledger"]
        self.assertEqual(ledger[0]["status"], "STOP")
        self.assertEqual(ledger[1]["status"], "OVERLAP_BLOCKED")
        self.assertEqual(report["holdout"]["summary"]["trades"], 1)

    def test_10_empty_plan_list_yields_no_trades_not_an_invented_signal(self):
        report = study([])
        self.assertTrue(report["valid"])
        for part in ("train", "holdout"):
            self.assertEqual(report[part]["summary"]["trades"], 0)
            self.assertEqual(report[part]["ledger"], [])
            self.assertTrue(all(x["trades"] == 0 for x in report[part]["monthly_utc"]))

    def test_11_user_plans_must_be_native_and_complete(self):
        class Hostile(dict):
            def items(self):
                raise AssertionError("should not invoke custom mapping")
        self.assert_rejected(plans=[Hostile(plan(0))], reason="INVALID_MANUAL_PLANS")
        self.assert_rejected(plans="signals", reason="INVALID_MANUAL_PLANS")
        self.assert_rejected(plans=[{"signal_time": stamp(0)}],
                             reason="INVALID_MANUAL_PLANS")
        self.assert_rejected(plans=[{**plan(0), "authorize": True}],
                             reason="INVALID_MANUAL_PLANS")

    def test_12_only_canonical_setup_side_and_timezone_are_accepted(self):
        for bad in (plan(0, "RSI"), plan(0, side="LONG"),
                    plan(0, setup="fvg"),
                    {**plan(0), "signal_time": stamp(0).replace("+00:00", "")},
                    {**plan(0), "signal_time": "2026-09-29T00:00:00+00:00"}):
            with self.subTest(bad=bad):
                self.assert_rejected(plans=[bad], reason="INVALID_MANUAL_PLANS")

    def test_13_side_geometry_and_nonfinite_or_oversized_levels(self):
        for bad in (plan(0, stop=11), plan(0, target=9),
                    plan(0, entry=float("nan")), plan(0, entry=float("inf")),
                    plan(0, entry=10**1000), plan(0, entry=True)):
            with self.subTest(type=type(bad["entry"]).__name__):
                self.assert_rejected(plans=[bad], reason="INVALID_MANUAL_PLANS")

    def test_14_duplicate_plan_refused(self):
        self.assert_rejected(plans=[plan(0), plan(0)], reason="INVALID_MANUAL_PLANS")

    def test_15_plan_count_is_bounded(self):
        self.assert_rejected(plans=[plan(0)] * (MAX_PLANS + 1),
                             reason="INVALID_MANUAL_PLANS")

    def test_16_cost_and_slippage_must_be_explicit_finite_r(self):
        for cost, slip in ((-0.1, 0), (0, -1), (math.nan, 0),
                           (0, math.inf), (True, 0), (10**1000, 0),
                           (0, 6), (None, 0)):
            with self.subTest(cost=cost if type(cost) is not int else str(cost)[:8]):
                self.assert_rejected(cost_r=cost, slippage_r=slip,
                                     reason="INVALID_COST_OR_SLIPPAGE_R")

    def test_17_strict_positive_bounded_windows(self):
        for waits, holds in ((0, 3), (2, 0), (True, 3), (2, 241),
                             (2.0, 3), (-1, 4)):
            self.assert_rejected(max_wait_bars=waits, max_hold_bars=holds,
                                 reason="INVALID_WAIT_OR_HOLD_WINDOW")

    def test_18_holdout_date_exact_on_a_closed_bar_and_enough_data(self):
        self.assert_rejected(validation_start="2026-10-01T00:07:00+00:00",
                             reason="INVALID_HOLDOUT_BOUNDARY")
        self.assert_rejected(validation_start=stamp(1),
                             reason="INSUFFICIENT_SPLIT_CANDLES")
        self.assert_rejected(validation_start=stamp(15),
                             reason="INSUFFICIENT_SPLIT_CANDLES")
        self.assert_rejected(validation_start="2026-10-01T00:00:00",
                             reason="INVALID_HOLDOUT_BOUNDARY")

    def test_19_invalid_csv_prevents_all_backtest_outputs(self):
        result = study()
        malformed = csv_data().replace("10,10.2,9.9,10", "10,NaN,9.9,10")
        kwargs = {
            "symbol": "EURUSD", "timeframe": "M15",
            "timestamp_basis": "CLOSE", "now": NOW,
            "validation_start": stamp(8), "manual_plans": PLANS,
            "cost_r": 0.1, "slippage_r": 0.05,
        }
        bad = research_backtest_csv(malformed, **kwargs)
        self.assertTrue(result["valid"])
        self.assertFalse(bad["valid"])
        self.assertIsNone(bad["train"])
        self.assertIsNone(bad["holdout"])
        self.assertTrue(bad["error"].startswith("INVALID_HISTORICAL_CSV:"))

    def test_20_symbol_universe_supports_nonfx_without_contract_claims(self):
        for symbol in ("EURUSD", "DXY", "NAS100", "SPX500", "US30",
                       "IBOV", "WIN", "WDO"):
            with self.subTest(symbol=symbol):
                report = study(symbol=symbol)
                self.assertTrue(report["valid"])
                self.assertFalse(report["holdout_is_independently_attested"])
                self.assertFalse(report["authorizes_send"])

    def test_21_hashes_retain_input_provenance_without_claiming_attestation(self):
        report = study()
        self.assertEqual(len(report["raw_csv_sha256"]), 64)
        self.assertEqual(len(report["normalized_candles_sha256"]), 64)
        self.assertFalse(report["holdout_is_independently_attested"])
        self.assertTrue(report["research_only"])

    def test_22_no_plans_or_data_cross_into_the_live_radar(self):
        report = study()
        self.assertNotIn("market_evidence", report)
        self.assertNotIn("fetched_at", report)
        self.assertNotIn("fresh_m15_pairs", report)
        self.assertFalse(report["authorizes_send"])
        self.assertTrue(report["no_orders"])


if __name__ == "__main__":
    unittest.main()
