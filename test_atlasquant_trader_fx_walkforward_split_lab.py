"""Synthetic, offline chronological OOS fold tests. No real backtesting."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_fx_bias_quality_lab import BiasTrial
from atlasquant_trader_fx_walkforward_split_lab import (
    WalkForwardPlan, inspect_fx_walkforward_split_lab as inspect,
)

UTC = timezone.utc
EVALUATED = datetime(2026, 4, 1, tzinfo=UTC)


def plan(*, embargo=1):
    return WalkForwardPlan(
        train_start_at=datetime(2026, 1, 1, tzinfo=UTC),
        train_end_at=datetime(2026, 1, 31, tzinfo=UTC),
        validation_start_at=datetime(2026, 2, 2, tzinfo=UTC),
        validation_end_at=datetime(2026, 2, 15, tzinfo=UTC),
        test_start_at=datetime(2026, 2, 17, tzinfo=UTC),
        test_end_at=datetime(2026, 3, 1, tzinfo=UTC),
        candidate_model_frozen_at=datetime(2026, 1, 31, 1, tzinfo=UTC),
        final_model_frozen_at=datetime(2026, 2, 15, 1, tzinfo=UTC),
        candidate_model_sha256_claim="a" * 64,
        final_model_sha256_claim="b" * 64,
        embargo_days=embargo,
    )


def row(id_text, start, *, days=1, horizon="D1", pair="EUR/USD"):
    return BiasTrial(
        trial_id=id_text, pair=pair, horizon=horizon, side="UP",
        features_captured_at=start - timedelta(hours=2),
        entry_price_captured_at=start - timedelta(hours=2),
        prediction_issued_at=start - timedelta(hours=1),
        outcome_start_at=start,
        outcome_end_at=start + timedelta(days=days),
        outcome_captured_at=start + timedelta(days=days, minutes=1),
        entry_close_price_claim="1.00000", exit_close_price_claim="1.01000",
    )


def base_rows():
    return [row("TRAIN_01", datetime(2026, 1, 10, tzinfo=UTC)),
            row("VALIDATION_01", datetime(2026, 2, 5, tzinfo=UTC)),
            row("TEST_01", datetime(2026, 2, 20, tzinfo=UTC))]


def run(rows=None, p=None, *, pair="EUR/USD", horizon="D1", at=EVALUATED):
    return inspect(base_rows() if rows is None else rows, plan() if p is None else p,
                   pair=pair, horizon=horizon, evaluated_at_utc=at)


class WalkForwardSplitLabTests(unittest.TestCase):
    def no_go(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        for field in ("timestamps_independently_authenticated",
                      "features_point_in_time_verified",
                      "price_outcomes_independently_verified",
                      "cross_pair_correlation_audited",
                      "out_of_sample_accuracy_validated",
                      "training_or_model_fit_performed", "trade_authorized",
                      "publishable", "worker_enabled", "scheduler_enabled"):
            self.assertIs(result[field], False, field)
        self.assertIsNone(result["validated_accuracy"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertEqual((result["http_requests"], result["file_writes"],
                          result["new_cost_brl"]), (0, 0, 0))

    def test_three_folds_are_structurally_separate_but_not_real_oos(self):
        r = run()
        self.assertEqual(r["state"],
                         "LAB_WALK_FORWARD_FOLDS_STRUCTURALLY_ISOLATED_UNATTESTED")
        self.assertEqual((r["training_trial_count"], r["validation_trial_count"],
                          r["test_trial_count"]), (1, 1, 1))
        self.assertTrue(r["caller_supplied_model_hashes_only"])
        self.no_go(r)

    def test_future_prediction_or_label_crossing_fold_is_rejected(self):
        rows = base_rows()
        crossing = replace(rows[0],
                           outcome_end_at=datetime(2026, 2, 1, tzinfo=UTC),
                           outcome_captured_at=datetime(2026, 2, 1, 0, 1, tzinfo=UTC))
        r = run([crossing, *rows[1:]])
        self.assertEqual(r["state"], "LAB_WALK_FORWARD_BLOCKED")
        self.no_go(r)

    def test_trial_issued_in_gap_is_not_assigned_to_nearest_fold(self):
        rows = base_rows()
        gap_case = row("GAP_01", datetime(2026, 2, 1, 12, tzinfo=UTC))
        r = run([*rows, gap_case])
        self.assertEqual(r["reason"], "TRIAL_ISSUED_IN_EMBARGO_GAP_OR_OUTSIDE_PLAN")
        self.no_go(r)

    def test_model_must_be_frozen_after_validation_and_before_test(self):
        for changes in ({"candidate_model_frozen_at": datetime(2026, 2, 4, tzinfo=UTC)},
                        {"final_model_frozen_at": datetime(2026, 2, 18, tzinfo=UTC)},
                        {"final_model_frozen_at": datetime(2026, 2, 14, tzinfo=UTC)}):
            with self.subTest(changes=changes):
                r = run(p=replace(plan(), **changes))
                self.assertEqual(r["reason"],
                                 "SPLIT_EMBARGO_OR_MODEL_FREEZE_CHRONOLOGY_INVALID")
                self.no_go(r)

    def test_insufficient_embargo_between_folds_rejected(self):
        r = run(p=replace(plan(), embargo_days=3))
        self.assertEqual(r["reason"], "SPLIT_EMBARGO_OR_MODEL_FREEZE_CHRONOLOGY_INVALID")
        self.no_go(r)

    def test_weekly_requires_longer_embargo_and_label(self):
        rows = [replace(v, horizon="W1") for v in base_rows()]
        r = run(rows, horizon="W1")
        self.assertEqual(r["state"], "LAB_WALK_FORWARD_BLOCKED")
        p = replace(plan(),
                    validation_start_at=datetime(2026, 2, 10, tzinfo=UTC),
                    validation_end_at=datetime(2026, 2, 25, tzinfo=UTC),
                    test_start_at=datetime(2026, 3, 5, tzinfo=UTC),
                    test_end_at=datetime(2026, 3, 25, tzinfo=UTC),
                    final_model_frozen_at=datetime(2026, 2, 26, tzinfo=UTC),
                    embargo_days=7)
        rows = [row("TRAIN_01", datetime(2026, 1, 10, tzinfo=UTC), days=7, horizon="W1"),
                row("VALIDATION_01", datetime(2026, 2, 12, tzinfo=UTC), days=7, horizon="W1"),
                row("TEST_01", datetime(2026, 3, 10, tzinfo=UTC), days=7, horizon="W1")]
        result = run(rows, p=p, horizon="W1")
        self.assertEqual(result["state"],
                         "LAB_WALK_FORWARD_FOLDS_STRUCTURALLY_ISOLATED_UNATTESTED")
        self.no_go(result)

    def test_monthly_cannot_be_evaluated_with_one_day_forward_label(self):
        rows = [replace(v, horizon="M1") for v in base_rows()]
        r = run(rows, horizon="M1", p=replace(plan(), embargo_days=31))
        self.assertEqual(r["state"], "LAB_WALK_FORWARD_BLOCKED")
        self.no_go(r)

    def test_monthly_is_valid_only_with_long_folds_and_month_sized_labels(self):
        p = WalkForwardPlan(
            train_start_at=datetime(2025, 1, 1, tzinfo=UTC),
            train_end_at=datetime(2025, 4, 1, tzinfo=UTC),
            validation_start_at=datetime(2025, 5, 5, tzinfo=UTC),
            validation_end_at=datetime(2025, 8, 1, tzinfo=UTC),
            test_start_at=datetime(2025, 9, 5, tzinfo=UTC),
            test_end_at=datetime(2025, 12, 1, tzinfo=UTC),
            candidate_model_frozen_at=datetime(2025, 4, 2, tzinfo=UTC),
            final_model_frozen_at=datetime(2025, 8, 2, tzinfo=UTC),
            candidate_model_sha256_claim="a" * 64,
            final_model_sha256_claim="b" * 64,
            embargo_days=31,
        )
        rows = [row("TRAIN_M1", datetime(2025, 2, 10, tzinfo=UTC), days=30, horizon="M1"),
                row("VALIDATION_M1", datetime(2025, 6, 10, tzinfo=UTC), days=30, horizon="M1"),
                row("TEST_M1", datetime(2025, 10, 10, tzinfo=UTC), days=30, horizon="M1")]
        valid = run(rows, p=p, horizon="M1")
        self.assertEqual(valid["state"],
                         "LAB_WALK_FORWARD_FOLDS_STRUCTURALLY_ISOLATED_UNATTESTED")
        too_short = run([replace(rows[0],
                                 outcome_end_at=rows[0].outcome_start_at + timedelta(days=1),
                                 outcome_captured_at=rows[0].outcome_start_at + timedelta(days=1, minutes=1)),
                         *rows[1:]], p=p, horizon="M1")
        self.assertEqual(too_short["reason"], "FORWARD_LABEL_DURATION_NOT_MATCHING_HORIZON")
        self.no_go(valid)
        self.no_go(too_short)

    def test_repeated_overlapping_labels_inside_fold_rejected(self):
        rows = base_rows()
        repeated = replace(rows[0], trial_id="TRAIN_02")
        r = run([*rows, repeated])
        self.assertEqual(r["reason"], "TRIAL_QUALITY_GATE_FAILED_TRAIN")
        self.no_go(r)

    def test_empty_validation_fold_rejected(self):
        rows = base_rows()
        r = run([rows[0], rows[2],
                 row("TRAIN_02", datetime(2026, 1, 12, tzinfo=UTC))])
        self.assertEqual(r["reason"], "EMPTY_FOLD_CANNOT_CLAIM_WALK_FORWARD")
        self.no_go(r)

    def test_invalid_model_digest_pair_or_naive_clock_rejected(self):
        for kwargs in ({"p": replace(plan(), final_model_sha256_claim="bad")},
                       {"pair": "XAU/USD"},
                       {"at": EVALUATED.replace(tzinfo=None)}):
            with self.subTest(kwargs=kwargs):
                r = run(**kwargs)
                self.assertEqual(r["state"], "LAB_WALK_FORWARD_BLOCKED")
                self.no_go(r)

    def test_train_prediction_feature_captured_after_issue_rejected(self):
        rows = base_rows()
        bad = replace(rows[0],
                      features_captured_at=rows[0].prediction_issued_at + timedelta(seconds=1))
        r = run([bad, *rows[1:]])
        self.assertEqual(r["reason"], "TRIAL_QUALITY_GATE_FAILED_TRAIN")
        self.no_go(r)


if __name__ == "__main__":
    unittest.main()
