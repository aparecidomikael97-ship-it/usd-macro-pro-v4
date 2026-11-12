"""Synthetic bias-trial quality accounting, never actual trading accuracy."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_fx_bias_quality_lab import (
    BiasTrial, inspect_fx_bias_quality_claims_lab as inspect,
)

START = datetime(2026, 11, 10, tzinfo=timezone.utc)
EVALUATED = START + timedelta(days=200)


def trial(number, *, side="UP", exit_price="1.01000", horizon="D1",
          pair="EUR/USD", offset_days=None):
    i = number if offset_days is None else offset_days
    start = START + timedelta(days=i)
    return BiasTrial(
        trial_id=f"EURUSD_TEST_{number:04d}", pair=pair, horizon=horizon,
        side=side, features_captured_at=start - timedelta(hours=2),
        entry_price_captured_at=start - timedelta(hours=2),
        prediction_issued_at=start - timedelta(hours=1),
        outcome_start_at=start, outcome_end_at=start + timedelta(days=1),
        outcome_captured_at=start + timedelta(days=1, minutes=1),
        entry_close_price_claim="1.00000", exit_close_price_claim=exit_price,
    )


def evaluate(rows, *, pair="EUR/USD", horizon="D1", at=EVALUATED,
             band="5"):
    return inspect(rows, pair=pair, horizon=horizon,
                   evaluated_at_utc=at, neutral_band_bps=band)


class BiasQualityLabTests(unittest.TestCase):
    def no_go(self, r):
        for key in ("features_independently_point_in_time_verified",
                    "broker_prices_independently_verified",
                    "outcomes_independently_verified",
                    "independent_out_of_sample_validation_completed",
                    "transaction_costs_accounted_for", "can_feed_live_radar",
                    "trade_authorized", "publishable", "scheduler_enabled",
                    "worker_enabled"):
            self.assertIs(r[key], False, key)
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["calibrated_probability"])
        self.assertIsNone(r["validated_accuracy"])
        self.assertEqual((r["http_requests"], r["file_writes"], r["new_cost_brl"]),
                         (0, 0, 0))

    def test_hit_rate_is_separate_from_coverage(self):
        r = evaluate([trial(0), trial(1, side="ABSTAIN"),
                      trial(2, side="ABSTAIN")])
        self.assertEqual(r["state"],
                         "LAB_BIAS_QUALITY_SYNTHETIC_OR_CALLER_CLAIM_ACCOUNTED_NO_GO")
        self.assertEqual((r["total_decision_opportunities"], r["emitted_biases"],
                          r["abstentions"], r["hits"]), (3, 1, 2, 1))
        self.assertEqual(r["research_claim_only_hit_rate_pct"], 100.0)
        self.assertEqual(r["research_claim_only_coverage_pct"], 33.33)
        self.assertIsNone(r["research_claim_only_wilson_lower_95_pct"])
        self.no_go(r)

    def test_only_abstentions_do_not_produce_a_hit_rate(self):
        r = evaluate([trial(0, side="ABSTAIN"), trial(1, side="ABSTAIN")])
        self.assertEqual(r["research_claim_only_coverage_pct"], 0.0)
        self.assertIsNone(r["research_claim_only_hit_rate_pct"])
        self.assertFalse(r["minimum_independent_signal_sample_reached"])
        self.no_go(r)

    def test_flat_forward_move_is_miss_not_excluded_sample(self):
        r = evaluate([trial(0, exit_price="1.00020")])
        self.assertEqual(r["neutral_forward_outcomes_counted_as_misses"], 1)
        self.assertEqual(r["misses"], 1)
        self.assertEqual(r["research_claim_only_hit_rate_pct"], 0.0)
        self.no_go(r)

    def test_one_hundred_synthetic_ninety_hits_not_validated_accuracy(self):
        rows = [trial(i, exit_price="1.01000" if i < 90 else "0.99000")
                for i in range(100)]
        r = evaluate(rows)
        self.assertEqual(r["hits"], 90)
        self.assertEqual(r["misses"], 10)
        self.assertEqual(r["research_claim_only_hit_rate_pct"], 90.0)
        self.assertTrue(r["minimum_emitted_sample_size_reached"])
        self.assertFalse(r["minimum_independent_signal_sample_reached"])
        self.assertFalse(r["wilson_iid_assumption_verified"])
        self.assertGreater(r["research_claim_only_wilson_lower_95_pct"], 80)
        self.assertTrue(r["research_claim_only_lower_bound_at_least_80pct"])
        self.no_go(r)

    def test_eighty_hits_in_one_hundred_has_lower_ci_below_eighty(self):
        rows = [trial(i, exit_price="1.01000" if i < 80 else "0.99000")
                for i in range(100)]
        r = evaluate(rows)
        self.assertEqual(r["research_claim_only_hit_rate_pct"], 80.0)
        self.assertLess(r["research_claim_only_wilson_lower_95_pct"], 80)
        self.assertFalse(r["research_claim_only_lower_bound_at_least_80pct"])
        self.no_go(r)

    def test_repeated_daily_updates_cannot_multicount_same_window(self):
        # Two independent IDs with the same forward label window is leakage.
        rows = [trial(0), trial(1, offset_days=0)]
        r = evaluate(rows)
        self.assertEqual(r["reason"], "OVERLAPPING_OUTCOME_WINDOWS_MULTICOUNTING")
        self.no_go(r)

    def test_duplicate_trial_ids_are_blocked_even_with_distinct_periods(self):
        rows = [trial(0), replace(trial(1), trial_id="EURUSD_TEST_0000")]
        r = evaluate(rows)
        self.assertEqual(r["state"], "LAB_BIAS_QUALITY_BLOCKED")
        self.no_go(r)

    def test_future_feature_or_entry_price_snapshot_is_not_available(self):
        for key in ("features_captured_at", "entry_price_captured_at"):
            with self.subTest(field=key):
                t = trial(0)
                bad = replace(t, **{key: t.prediction_issued_at + timedelta(seconds=1)})
                r = evaluate([bad])
                self.assertEqual(r["reason"], "FUTURE_LEAKAGE_OR_UNRESOLVED_OUTCOME")
                self.no_go(r)

    def test_future_or_unresolved_outcome_rejected(self):
        t = trial(0)
        cases = (replace(t, outcome_start_at=t.prediction_issued_at),
                 replace(t, outcome_captured_at=t.outcome_end_at - timedelta(seconds=1)),
                 replace(t, outcome_captured_at=EVALUATED + timedelta(seconds=1)))
        for case in cases:
            r = evaluate([case])
            self.assertEqual(r["reason"], "FUTURE_LEAKAGE_OR_UNRESOLVED_OUTCOME")
            self.no_go(r)

    def test_invalid_price_or_neutral_band_rejected(self):
        for value in ("0", "-1.0", "NaN", "Inf", "1,02", "1.000000000"):
            with self.subTest(value=value):
                r = evaluate([replace(trial(0), exit_close_price_claim=value)])
                self.assertEqual(r["reason"], "INVALID_PRICE_LEVEL_CLAIMS")
                self.no_go(r)
        self.assertEqual(evaluate([trial(0)], band="999")["state"],
                         "LAB_BIAS_QUALITY_BLOCKED")

    def test_invalid_universe_or_horizon_fails_closed(self):
        for kwargs in ({"pair": "XAU/USD"}, {"horizon": "M15"},
                       {"at": START.replace(tzinfo=None)}):
            with self.subTest(kwargs=kwargs):
                r = evaluate([trial(0)], **kwargs)
                self.assertEqual(r["state"], "LAB_BIAS_QUALITY_BLOCKED")
                self.no_go(r)

    def test_m1_minute_must_not_be_mistaken_for_mn1_monthly(self):
        row = trial(0, horizon="M1")
        result = evaluate([row], horizon="M1")
        self.assertEqual(result["state"], "LAB_BIAS_QUALITY_BLOCKED")
        self.assertEqual(result["reason"], "INVALID_TRIALS_OR_CLOCK")
        self.no_go(result)

    def test_monthly_trial_cannot_use_one_day_price_move(self):
        row = trial(0, horizon="MN1")
        result = evaluate([row], horizon="MN1")
        self.assertEqual(result["state"], "LAB_BIAS_QUALITY_BLOCKED")
        self.assertEqual(result["reason"], "MN1_OUTCOME_NOT_ONE_CALENDAR_MONTH_WINDOW")
        self.no_go(result)

    def test_monthly_documentary_30_day_window_is_not_real_accuracy(self):
        row = trial(0, horizon="MN1")
        month_end = row.outcome_start_at + timedelta(days=30)
        row = replace(row, outcome_end_at=month_end,
                      outcome_captured_at=month_end + timedelta(minutes=1))
        result = evaluate([row], horizon="MN1")
        self.assertEqual(result["state"],
                         "LAB_BIAS_QUALITY_SYNTHETIC_OR_CALLER_CLAIM_ACCOUNTED_NO_GO")
        self.assertEqual(result["horizon"], "MN1")
        self.assertEqual(result["hits"], 1)
        self.assertFalse(result["monthly_session_calendar_independently_verified"])
        self.no_go(result)

    def test_monthly_same_calendar_month_or_wrong_length_rejected(self):
        row = trial(0, horizon="MN1")
        for days in (24, 60):
            with self.subTest(days=days):
                month_end = row.outcome_start_at + timedelta(days=days)
                item = replace(row, outcome_end_at=month_end,
                               outcome_captured_at=month_end + timedelta(minutes=1))
                result = evaluate([item], horizon="MN1")
                self.assertEqual(result["reason"],
                                 "MN1_OUTCOME_NOT_ONE_CALENDAR_MONTH_WINDOW")
                self.no_go(result)
        # A 29-day period entirely within December is not a monthly
        # December-to-January label; length alone is insufficient.
        start = datetime(2026, 12, 1, tzinfo=timezone.utc)
        end = start + timedelta(days=29)
        same_month = replace(row, outcome_start_at=start,
                             outcome_end_at=end,
                             outcome_captured_at=end + timedelta(minutes=1))
        result = evaluate([same_month], horizon="MN1")
        self.assertEqual(result["reason"],
                         "MN1_OUTCOME_NOT_ONE_CALENDAR_MONTH_WINDOW")
        self.no_go(result)

    def test_monthly_crossover_december_to_january_can_pass_documentary(self):
        row = trial(30, horizon="MN1")  # December 10, 2026
        month_end = row.outcome_start_at + timedelta(days=31)
        row = replace(row, outcome_end_at=month_end,
                      outcome_captured_at=month_end + timedelta(minutes=1))
        result = evaluate([row], horizon="MN1")
        self.assertEqual(result["horizon"], "MN1")
        self.assertEqual(result["total_decision_opportunities"], 1)
        self.no_go(result)

    def test_empty_trial_set_is_not_a_backtest(self):
        r = evaluate([])
        self.assertEqual(r["state"], "LAB_BIAS_QUALITY_BLOCKED")
        self.assertIsNone(r["research_claim_only_hit_rate_pct"])
        self.no_go(r)


if __name__ == "__main__":
    unittest.main()
