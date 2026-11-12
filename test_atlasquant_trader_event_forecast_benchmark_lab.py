"""Fully synthetic, unverified historical forecast benchmark regression tests."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_event_forecast_benchmark_lab import (
    BenchmarkCase, evaluate_event_forecast_cohort_lab as evaluate,
)
from atlasquant_trader_event_forecast_lock_lab import (
    ActualClaim, ForecastDraft, freeze_pre_event_forecast_lab,
)
from atlasquant_trader_forecast_anchor_lab import (
    AnchorTarget, ClaimedGitHubComment, prepare_pre_event_anchor_lab,
)

UTC = timezone.utc
ASOF = datetime(2026, 11, 8, 20, tzinfo=UTC)


def event(i: int, *, actual="0.4", model="0.35", consensus="0.3",
          metric="CPI_MOM", event_id_override=None,
          currency="USD") -> BenchmarkCase:
    # These are deliberately invented data, not historical economic releases.
    year, month = 2023 + i // 12, 1 + i % 12
    release = datetime(year, month, 10, 13, 30, tzinfo=UTC)
    captured = release - timedelta(days=2)
    draft = ForecastDraft(
        event_id=event_id_override or f"SYNTH_{year}_{month:02d}",
        currency=currency, metric=metric,
        target_period=f"{year}-{month:02d}", unit="PERCENT_MOM_SA",
        scheduled_release_at=release, forecast_captured_at=captured,
        previous_value="0.6", previous_available_at=captured - timedelta(days=10),
        consensus_value=consensus,
        consensus_available_at=captured - timedelta(hours=1),
        model_estimate=model, model_version="v1.0" if model is not None else None,
        previous_source_sha256_claim="a" * 64,
        consensus_source_sha256_claim="b" * 64,
    )
    locked = freeze_pre_event_forecast_lab(draft, as_of_utc=captured)["lock"]
    claim = ActualClaim(
        event_id=draft.event_id, currency=currency, metric=metric,
        target_period=draft.target_period, unit=draft.unit, value=actual,
        first_published_at=release, captured_at=release + timedelta(minutes=2),
        source_sha256_claim="c" * 64,
    )
    return BenchmarkCase(locked, claim)


def cohort(n=30, **kwargs):
    return [event(i, **kwargs) for i in range(n)]


class BenchmarkTests(unittest.TestCase):
    def assert_no_go(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertFalse(result["publishable"])
        self.assertFalse(result["live_alert_allowed"])
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["worker_enabled"])
        self.assertFalse(result["scheduler_enabled"])
        self.assertIsNone(result["calibrated_direction_probability"])
        self.assertIsNone(result["validated_accuracy"])
        self.assertEqual(result["validated_prediction_count"], 0)
        self.assertEqual(result["independent_pre_event_forecast_witnesses_verified"], 0)
        self.assertEqual(result["independently_authenticated_actual_count"], 0)
        self.assertFalse(result["dataset_point_in_time_independently_verified"])
        self.assertFalse(result["no_selection_bias_verified"])
        self.assertIsNone(result["fx_bias"])
        self.assertIsNone(result["index_bias"])
        self.assertEqual((result["http_requests"], result["file_writes"],
                          result["new_cost_brl"]), (0, 0, 0))
        self.assertTrue(result["research_only"])

    def test_30_synthetic_events_paired_mae_and_coverage(self):
        r = evaluate(cohort(), as_of_utc=ASOF)
        self.assertEqual(r["state"], "LAB_DOCUMENTARY_PAIRED_BENCHMARK_UNVERIFIED")
        self.assertEqual(r["registered_events"], 30)
        self.assertEqual(r["currency"], "USD")
        self.assertEqual(r["scored_events_documentary"], 30)
        self.assertEqual(r["matched_model_and_consensus_scored"], 30)
        self.assertEqual(r["anchor_claim_missing"], 30)
        self.assertEqual(r["mae_model_matched_documentary"], "0.05")
        self.assertEqual(r["mae_consensus_matched_documentary"], "0.1")
        self.assertEqual(r["mae_previous_matched_documentary"], "0.2")
        self.assertEqual(r["paired_model_skill_vs_consensus_documentary"], "0.5")
        self.assertEqual(r["paired_model_closer_count_documentary"], 30)
        self.assertEqual(r["paired_model_tie_count_documentary"], 0)
        self.assertEqual(r["paired_model_worse_count_documentary"], 0)
        self.assertEqual(r["paired_model_closer_share_documentary"], "1")
        self.assertTrue(r["fully_scored_registered_cohort"])
        self.assert_no_go(r)

    def test_small_cohort_masks_all_aggregated_metrics(self):
        r = evaluate(cohort(29), as_of_utc=ASOF)
        self.assertEqual(r["state"], "LAB_INCOMPLETE_OR_SMALL_COHORT_NO_PERFORMANCE_CLAIM")
        self.assertFalse(r["minimum_matched_sample_reached"])
        self.assertIsNone(r["mae_model_matched_documentary"])
        self.assertIsNone(r["paired_model_closer_share_documentary"])
        self.assert_no_go(r)

    def test_missing_actual_cannot_be_silently_excluded(self):
        c = cohort(31)
        c[4] = replace(c[4], actual_claim=None)
        r = evaluate(c, as_of_utc=ASOF)
        self.assertEqual(r["registered_events"], 31)
        self.assertEqual(r["scored_events_documentary"], 30)
        self.assertEqual(r["missing_actual_after_release"], 1)
        self.assertEqual(r["matched_model_and_consensus_scored"], 30)
        self.assertFalse(r["fully_scored_registered_cohort"])
        self.assertIsNone(r["mae_model_matched_documentary"])
        self.assertEqual(r["rows"][4]["state"], "LAB_MISSING_POST_RELEASE_ACTUAL")
        self.assert_no_go(r)

    def test_missing_model_estimate_disables_matched_performance_claim(self):
        c = cohort(31)
        c[3] = event(3, model=None)
        r = evaluate(c, as_of_utc=ASOF)
        self.assertEqual(r["without_model_estimate_registered"], 1)
        self.assertEqual(r["with_model_estimate_registered"], 30)
        self.assertEqual(r["matched_model_and_consensus_scored"], 30)
        self.assertEqual(r["scored_events_documentary"], 31)
        self.assertIsNone(r["mae_model_matched_documentary"])
        self.assert_no_go(r)

    def test_upcoming_registered_event_is_counted_not_scored(self):
        c = cohort(30)
        future = event(46)
        # event(46) lands in November 2026; its prediction predates ASOF.
        c.append(replace(future, actual_claim=None))
        r = evaluate(c, as_of_utc=ASOF)
        self.assertEqual(r["waiting_for_release"], 1)
        self.assertFalse(r["fully_scored_registered_cohort"])
        self.assertIsNone(r["mae_consensus_matched_documentary"])
        self.assert_no_go(r)

    def test_future_actual_must_not_leak_into_earlier_asof(self):
        c = cohort(30)
        c.append(event(46))
        r = evaluate(c, as_of_utc=ASOF)
        self.assertEqual(r["state"], "LAB_BENCHMARK_BLOCKED")
        self.assertEqual(r["reason"], "POST_RELEASE_ACTUAL_PROVIDED_BEFORE_RELEASE")
        self.assert_no_go(r)

    def test_future_forecast_cannot_be_seen_in_earlier_research_clock(self):
        c = cohort(30)
        # 2023 captures are valid; the research clock below predates all.
        r = evaluate(c, as_of_utc=datetime(2022, 12, 31, tzinfo=UTC))
        self.assertEqual(r["reason"], "FORECAST_CAPTURE_AFTER_RESEARCH_ASOF")
        self.assert_no_go(r)

    def test_duplicate_event_id_and_period_are_rejected(self):
        c = cohort(30)
        c.append(c[7])
        r = evaluate(c, as_of_utc=ASOF)
        self.assertEqual(r["state"], "LAB_BENCHMARK_BLOCKED")
        self.assertEqual(r["reason"], "DUPLICATE_ECONOMIC_EVENT_IN_COHORT")
        self.assert_no_go(r)

    def test_same_observation_under_an_alias_cannot_be_double_counted(self):
        c = cohort(30)
        c.append(event(7, event_id_override="SYNTH_ALIAS_OF_07"))
        r = evaluate(c, as_of_utc=ASOF)
        self.assertEqual(r["reason"], "DUPLICATE_ECONOMIC_EVENT_IN_COHORT")
        self.assert_no_go(r)

    def test_reused_event_id_for_another_period_cannot_be_counted_twice(self):
        c = cohort(30)
        c.append(event(35, event_id_override="SYNTH_2023_08"))
        r = evaluate(c, as_of_utc=ASOF)
        self.assertEqual(r["reason"], "DUPLICATE_ECONOMIC_EVENT_IN_COHORT")
        self.assert_no_go(r)

    def test_different_currency_same_metric_unit_must_not_pool_forecast_errors(self):
        cases = cohort(30)
        # The prior comparator grouped by metric/unit alone, so it could
        # average a synthetic EUR CPI observation with USD CPI observations.
        cases[7] = event(7, currency="EUR")
        result = evaluate(cases, as_of_utc=ASOF)
        self.assertEqual(result["state"], "LAB_BENCHMARK_BLOCKED")
        self.assertEqual(result["reason"],
                         "MIXED_CURRENCY_FORECAST_ERRORS_NOT_COMPARABLE")
        self.assertIsNone(result["mae_model_matched_documentary"])
        self.assertIsNone(result["paired_model_closer_share_documentary"])
        self.assertIsNone(result["currency"])
        self.assert_no_go(result)

    def test_single_eur_cohort_is_permitted_only_as_synthetic_documentary(self):
        cases = cohort(30, currency="EUR")
        result = evaluate(cases, as_of_utc=ASOF)
        self.assertEqual(result["currency"], "EUR")
        self.assertEqual(result["metric"], "CPI_MOM")
        self.assertEqual(result["unit"], "PERCENT_MOM_SA")
        self.assertEqual(result["matched_model_and_consensus_scored"], 30)
        self.assertEqual(result["state"],
                         "LAB_DOCUMENTARY_PAIRED_BENCHMARK_UNVERIFIED")
        self.assert_no_go(result)

    def test_mixed_incompatible_indicators_cannot_average_mae(self):
        c = cohort(30)
        c[5] = event(5, metric="PCE_MOM")
        r = evaluate(c, as_of_utc=ASOF)
        self.assertEqual(r["reason"], "MIXED_METRIC_OR_UNIT_MAE_NOT_COMPARABLE")
        self.assert_no_go(r)

    def test_invalid_actual_timestamp_causes_whole_cohort_to_block(self):
        c = cohort(30)
        cl = c[8].actual_claim
        release = cl.first_published_at
        c[8] = replace(c[8], actual_claim=replace(cl,
            first_published_at=release-timedelta(seconds=1)))
        r = evaluate(c, as_of_utc=ASOF)
        self.assertEqual(r["reason"], "INVALID_POST_RELEASE_ACTUAL_CLAIM")
        self.assert_no_go(r)

    def test_actual_equals_consensus_makes_relative_skill_undefined(self):
        r = evaluate(cohort(consensus="0.4"), as_of_utc=ASOF)
        self.assertEqual(r["mae_consensus_matched_documentary"], "0.0")
        self.assertIsNone(r["paired_model_skill_vs_consensus_documentary"])
        self.assertEqual(r["paired_model_worse_count_documentary"], 30)
        self.assert_no_go(r)

    def test_model_tied_with_consensus_is_not_a_win(self):
        r = evaluate(cohort(model="0.3"), as_of_utc=ASOF)
        self.assertEqual(r["paired_model_closer_count_documentary"], 0)
        self.assertEqual(r["paired_model_tie_count_documentary"], 30)
        self.assertEqual(r["paired_model_closer_share_documentary"], "0")
        self.assert_no_go(r)

    def test_anchor_chronology_candidate_only_never_authenticated(self):
        c = cohort(30)
        first = c[0]
        payload = first.locked_forecast
        target = AnchorTarget("aparecidomikael97-ship-it/usd-macro-pro-v4", 1851)
        # All timestamps and the comment are synthetic, not retrieved from GitHub.
        captured = datetime(2023, 1, 8, 13, 30, tzinfo=UTC)
        prepared = prepare_pre_event_anchor_lab(payload, target, as_of_utc=captured)
        published = captured + timedelta(minutes=1)
        candidate = ClaimedGitHubComment(
            comment_id=12, api_url="https://api.github.com/repos/"
            "aparecidomikael97-ship-it/usd-macro-pro-v4/issues/comments/12",
            html_url="https://github.com/aparecidomikael97-ship-it/"
            "usd-macro-pro-v4/pull/1851#issuecomment-12",
            body=prepared["anchor_body_documentary"], created_at=published,
            updated_at=published, fetched_at=published+timedelta(seconds=1),
        )
        c[0] = replace(first, anchor_target=target, anchor_comment_claim=candidate)
        r = evaluate(c, as_of_utc=ASOF)
        self.assertEqual(r["anchor_chronology_candidates_unattested"], 1)
        self.assertEqual(r["anchor_claim_missing"], 29)
        self.assertEqual(r["independent_pre_event_forecast_witnesses_verified"], 0)
        self.assert_no_go(r)

    def test_only_one_anchor_field_is_rejected(self):
        c = cohort(30)
        c[1] = replace(c[1], anchor_target=AnchorTarget("owner/repo", 1))
        r = evaluate(c, as_of_utc=ASOF)
        self.assertEqual(r["reason"], "INCOMPLETE_ANCHOR_PAIR")
        self.assert_no_go(r)

    def test_invalid_anchor_claim_blocks_all_metrics(self):
        c = cohort(30)
        c[0] = replace(c[0], anchor_target=AnchorTarget("owner/repo", 1),
                       anchor_comment_claim="made-up")
        r = evaluate(c, as_of_utc=ASOF)
        self.assertEqual(r["reason"], "INVALID_CLAIMED_EXTERNAL_ANCHOR")
        self.assert_no_go(r)

    def test_invalid_cohort_shapes_do_not_crash(self):
        for value in (None, {}, [], [None], "events", [event(0)]*1001):
            with self.subTest(value_type=type(value)):
                r = evaluate(value, as_of_utc=ASOF)
                self.assertEqual(r["state"], "LAB_BENCHMARK_BLOCKED")
                self.assert_no_go(r)

    def test_rejects_unreasonable_minimum_and_nan_time(self):
        for minimum in (0, 1, 1001, True, "30"):
            self.assertEqual(evaluate(cohort(30), as_of_utc=ASOF,
                             minimum_matched_sample=minimum)["state"],
                             "LAB_BENCHMARK_BLOCKED")
        self.assertEqual(evaluate(cohort(30),
                         as_of_utc=ASOF.replace(tzinfo=None))["state"],
                         "LAB_BENCHMARK_BLOCKED")

    def test_threshold_can_be_configured_but_stays_documentary(self):
        r = evaluate(cohort(10), as_of_utc=ASOF, minimum_matched_sample=10)
        self.assertEqual(r["state"], "LAB_DOCUMENTARY_PAIRED_BENCHMARK_UNVERIFIED")
        self.assert_no_go(r)


if __name__ == "__main__":
    unittest.main()
