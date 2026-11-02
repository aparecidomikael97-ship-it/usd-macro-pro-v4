"""Synthetic-only backtest of forecast timestamps versus future outcome labels."""
import unittest
from datetime import datetime, timedelta, timezone
from math import exp

from atlasquant_trader_bias_oos_lab import evaluate_bias_out_of_sample_lab

SPLIT = datetime(2026, 9, 1, tzinfo=timezone.utc)
NOW = datetime(2026, 11, 2, 15, tzinfo=timezone.utc)
DATES_TRAIN = ("2026-06-01", "2026-06-05", "2026-06-10")
DATES_TEST = ("2026-09-02", "2026-09-05", "2026-09-10")
LENGTHS = {"D1": 2, "W1": 7, "MN1": 30}


def fixture(*, horizon="D1", side="ALTA", realized="ALTA",
            dates_train=DATES_TRAIN, dates_test=DATES_TEST):
    forecasts, settlements = [], []
    for partition, dates in (("tr", dates_train), ("te", dates_test)):
        for i, day in enumerate(dates):
            issued = datetime.fromisoformat(day + "T12:00:00+00:00")
            entry = issued + timedelta(days=1)
            exit_at = entry + timedelta(days=LENGTHS[horizon])
            fid = f"{partition}-{horizon}-{i}"
            forecasts.append({
                "forecast_id": fid, "state": "LAB_SYNTHETIC_BIAS",
                "pair": "USD/JPY", "horizon": horizon, "bias": side,
                "method_id": "fixed-baseline-v1",
                "issued_at_utc": issued.isoformat(),
                "evidence_at_utc": (issued - timedelta(hours=1)).isoformat(),
            })
            amplitude = {"ALTA": 30, "BAIXA": -30, "NEUTRO": 0}[realized]
            settlements.append({
                "forecast_id": fid, "state": "LAB_SYNTHETIC_SPOT_OUTCOME",
                "pair": "USD/JPY", "entry_at_utc": entry.isoformat(),
                "exit_at_utc": exit_at.isoformat(),
                "entry_price": 100.0,
                "exit_price": 100.0 * exp(amplitude / 10000),
            })
    return forecasts, settlements


def evaluate(f, s, **kwargs):
    return evaluate_bias_out_of_sample_lab(
        f, s, split_at=SPLIT, at=NOW, min_train=3,
        min_test=3, min_test_days=3, **kwargs)


class BiasOOSTests(unittest.TestCase):
    def test_accurate_daily_synthetic_outcomes_are_descriptive_not_proof(self):
        f, s = fixture()
        out = evaluate(f, s)
        d = out["metrics"]["D1"]
        self.assertEqual(d["state"], "SYNTHETIC_OOS_SAMPLE")
        self.assertEqual(d["directional_hit_rate_pct"], 100.0)
        self.assertEqual(d["always_up_baseline_hit_rate_pct"], 100.0)
        self.assertEqual(d["samples"], 3)
        self.assertFalse(out["oos_proven"])
        self.assertFalse(out["historical_data_verified"])
        self.assertFalse(out["trade_authorized"])

    def test_bearish_forecast_correct_even_when_always_up_wrong(self):
        f, s = fixture(side="BAIXA", realized="BAIXA")
        d = evaluate(f, s)["metrics"]["D1"]
        self.assertEqual(d["directional_hit_rate_pct"], 100.0)
        self.assertEqual(d["always_up_baseline_hit_rate_pct"], 0.0)

    def test_bad_forecast_is_not_mistaken_for_directional_hit(self):
        f, s = fixture(side="ALTA", realized="BAIXA")
        d = evaluate(f, s)["metrics"]["D1"]
        self.assertEqual(d["directional_hit_rate_pct"], 0.0)

    def test_different_horizons_evaluated_separately_with_correct_hold_period(self):
        f, s = [], []
        for horizon in ("D1", "W1", "MN1"):
            a, b = fixture(horizon=horizon)
            f.extend(a); s.extend(b)
        out = evaluate(f, s)
        for horizon in ("D1", "W1", "MN1"):
            self.assertEqual(out["metrics"][horizon]["directional_hit_rate_pct"], 100.0)
        self.assertEqual(out["holdout_rows"], 9)

    def test_abstentions_reduce_coverage_not_fabricate_hits(self):
        f, s = fixture()
        for row in f:
            if row["forecast_id"] == "te-D1-1":
                row["bias"] = "AGUARDAR"
            if row["forecast_id"] == "te-D1-2":
                row["bias"] = "NEUTRO"
        d = evaluate(f, s)["metrics"]["D1"]
        self.assertEqual(d["directional_predictions"], 1)
        self.assertEqual(d["neutral_forecasts"], 1)
        self.assertEqual(d["await_forecasts"], 1)
        self.assertAlmostEqual(d["coverage_pct"], 33.33)
        self.assertIsNone(d["directional_hit_rate_pct"])
        self.assertEqual(d["directional_hits"], 1)

    def test_flat_price_move_counts_as_non_hit_for_up_call(self):
        f, s = fixture(realized="NEUTRO")
        d = evaluate(f, s)["metrics"]["D1"]
        self.assertEqual(d["directional_hit_rate_pct"], 0.0)
        self.assertEqual(d["realized_flat"], 3)

    def test_too_few_test_days_hides_accuracy_even_with_three_predictions(self):
        f, s = fixture(dates_test=("2026-09-02", "2026-09-02", "2026-09-02"))
        out = evaluate(f, s)
        d = out["metrics"]["D1"]
        self.assertEqual(d["state"], "INSUFFICIENT_SYNTHETIC_SAMPLE")
        self.assertIsNone(d["directional_hit_rate_pct"])

    def test_training_outcome_crossing_split_is_purged(self):
        f, s = fixture(horizon="MN1")
        mid = datetime(2026, 8, 17, 12, tzinfo=timezone.utc)
        f[0]["issued_at_utc"] = mid.isoformat()
        f[0]["evidence_at_utc"] = (mid - timedelta(hours=1)).isoformat()
        s[0]["entry_at_utc"] = (mid + timedelta(days=1)).isoformat()
        s[0]["exit_at_utc"] = (mid + timedelta(days=31)).isoformat()
        out = evaluate(f, s)
        self.assertEqual(out["purged_boundary_rows"], 1)
        self.assertEqual(out["metrics"]["MN1"]["train_samples"], 2)
        self.assertIsNone(out["metrics"]["MN1"]["directional_hit_rate_pct"])

    def test_duplicate_forecast_id_rejects_whole_batch(self):
        f, s = fixture()
        f.append(dict(f[0]))
        self.assertEqual(evaluate(f, s)["state"], "INVALID_OR_INCOMPLETE_FIXTURE")

    def test_duplicate_or_unknown_settlement_id_rejects_whole_batch(self):
        f, s = fixture()
        s.append(dict(s[0]))
        self.assertEqual(evaluate(f, s)["state"], "INVALID_OR_INCOMPLETE_FIXTURE")
        f, s = fixture()
        s[1]["forecast_id"] = "foreign-ID"
        self.assertEqual(evaluate(f, s)["state"], "INVALID_OR_INCOMPLETE_FIXTURE")

    def test_missing_outcome_is_not_silently_discarded(self):
        f, s = fixture()
        s.pop()
        out = evaluate(f, s)
        self.assertEqual(out["state"], "INVALID_OR_INCOMPLETE_FIXTURE")
        self.assertEqual(out["metrics"], {})

    def test_outcome_start_must_follow_prediction(self):
        f, s = fixture()
        s[0]["entry_at_utc"] = f[0]["issued_at_utc"]
        self.assertEqual(evaluate(f, s)["state"], "INVALID_OR_INCOMPLETE_FIXTURE")

    def test_forecast_must_precede_its_evidence_cutoff(self):
        f, s = fixture()
        f[0]["evidence_at_utc"] = (datetime.fromisoformat(f[0]["issued_at_utc"]) +
                                   timedelta(hours=1)).isoformat()
        self.assertEqual(evaluate(f, s)["state"], "INVALID_OR_INCOMPLETE_FIXTURE")

    def test_future_outcome_rejected_when_asof_before_exit(self):
        f, s = fixture()
        future = (NOW + timedelta(days=1)).isoformat()
        s[0]["exit_at_utc"] = future
        self.assertEqual(evaluate(f, s)["state"], "INVALID_OR_INCOMPLETE_FIXTURE")

    def test_invalid_prices_and_boolean_rejected(self):
        for bad in (False, 0, float("inf"), float("nan"), -4, "100"):
            f, s = fixture()
            s[0]["entry_price"] = bad
            self.assertEqual(evaluate(f, s)["state"], "INVALID_OR_INCOMPLETE_FIXTURE")

    def test_wrong_pair_horizon_and_state_rejected(self):
        f, s = fixture()
        s[0]["pair"] = "EUR/USD"
        self.assertEqual(evaluate(f, s)["state"], "INVALID_OR_INCOMPLETE_FIXTURE")
        f, s = fixture()
        f[0]["horizon"] = "H1"
        self.assertEqual(evaluate(f, s)["state"], "INVALID_OR_INCOMPLETE_FIXTURE")
        f, s = fixture()
        f[0]["state"] = "REAL_VERIFIED"
        self.assertEqual(evaluate(f, s)["state"], "INVALID_OR_INCOMPLETE_FIXTURE")

    def test_mixed_methods_never_present_as_same_holdout(self):
        f, s = fixture()
        f[0]["method_id"] = "new-method"
        out = evaluate(f, s)
        self.assertEqual(out["state"], "INVALID_OR_INCOMPLETE_FIXTURE")

    def test_naive_forecast_timestamp_rejected(self):
        f, s = fixture()
        f[0]["issued_at_utc"] = "2026-06-01T12:00:00"
        self.assertEqual(evaluate(f, s)["state"], "INVALID_OR_INCOMPLETE_FIXTURE")

    def test_other_27_pairs_remain_unproven_even_when_usdjpy_has_three_hits(self):
        f, s = fixture()
        out = evaluate(f, s)
        self.assertEqual(out["pair_metrics"]["USD/JPY"]["D1"]["directional_hit_rate_pct"], 100.0)
        self.assertEqual(out["pair_metrics"]["EUR/USD"]["D1"]["state"], "INSUFFICIENT_SYNTHETIC_SAMPLE")
        self.assertIsNone(out["pair_metrics"]["EUR/USD"]["D1"]["directional_hit_rate_pct"])
        self.assertEqual(len(out["pair_metrics"]), 28)

    def test_all_abstentions_do_not_synthesize_accuracy(self):
        f, s = fixture()
        for item in f:
            if item["forecast_id"].startswith("te-"):
                item["bias"] = "AGUARDAR"
        d = evaluate(f, s)["metrics"]["D1"]
        self.assertEqual(d["coverage_pct"], 0.0)
        self.assertIsNone(d["directional_hit_rate_pct"])

    def test_invalid_split_and_sizes_fail(self):
        f, s = fixture()
        with self.assertRaises(ValueError):
            evaluate_bias_out_of_sample_lab(
                f, s, split_at=datetime(2026, 9, 1),
                at=NOW)
        with self.assertRaises(ValueError):
            evaluate_bias_out_of_sample_lab(
                f, s, split_at=NOW,
                at=NOW)
        with self.assertRaises(ValueError):
            evaluate_bias_out_of_sample_lab(
                f, s, split_at=SPLIT, at=NOW, min_test=True)
        with self.assertRaises(ValueError):
            evaluate_bias_out_of_sample_lab(
                f, s, split_at=SPLIT, at=NOW, deadband_bp=float("nan"))

    def test_horizon_shortcut_and_overly_late_entry_rejected(self):
        f, s = fixture(horizon="MN1")
        start = datetime.fromisoformat(s[0]["entry_at_utc"])
        s[0]["exit_at_utc"] = (start + timedelta(days=1)).isoformat()
        self.assertEqual(evaluate(f, s)["state"], "INVALID_OR_INCOMPLETE_FIXTURE")
        f, s = fixture()
        start = datetime.fromisoformat(f[0]["issued_at_utc"])
        s[0]["entry_at_utc"] = (start + timedelta(days=10)).isoformat()
        self.assertEqual(evaluate(f, s)["state"], "INVALID_OR_INCOMPLETE_FIXTURE")


if __name__ == "__main__":
    unittest.main()
