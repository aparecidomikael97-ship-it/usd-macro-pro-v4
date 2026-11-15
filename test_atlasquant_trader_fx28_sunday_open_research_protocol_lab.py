"""Synthetic, caller-supplied aggregate fixtures; no prices or MT5."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest import TestCase, main
from copy import deepcopy

from atlasquant_trader_fx28_sunday_open_research_protocol_lab import (
    FIRST_SEPARATE_SUNDAY,
    inspect_fx28_sunday_open_research_protocol_lab as inspect,
)

UTC=timezone.utc


def historical_fixture():
    distributions=(
        {"180":24, "210":2, "225":1, "240":1},
        {"120":17, "135":10, "180":1},
        {"120":22, "135":5, "165":1},
    )
    days=("2026-10-25","2026-11-01","2026-11-08")
    opens=(
        datetime(2026,10,25,21,tzinfo=UTC),
        datetime(2026,11,1,22,tzinfo=UTC),
        datetime(2026,11,8,22,tzinfo=UTC),
    )
    return [{
        "historical_sunday":day,
        "frozen_start_utc_in_sample":start.isoformat(),
        "window_checked_hours":5,
        "queried_28":28,
        "valid_nonempty_series_count":28,
        "first_nominal_m15_present_count":0,
        "first_nominal_m15_missing_count_among_valid":28,
        "first_actual_m15_lag_minute_distribution":d,
        "mt5_api_none_count":0,
        "symbols_without_metadata_count":0,
        "empty_or_invalid_count":0,
        "visibility_changes_count":0,
        "not_proof_future_market_open":True,
        "min_observed_lag_min":min(map(int,d)),
        "max_observed_lag_min":max(map(int,d)),
    } for day,start,d in zip(days,opens,distributions)]


class SundayResearchProtocolTests(TestCase):
    def check(self, samples=None, at=FIRST_SEPARATE_SUNDAY):
        return inspect(
            historical_sunday_summaries=(
                historical_fixture() if samples is None else samples),
            separate_research_sunday_utc=at)

    def safe(self, r):
        self.assertIsNone(r["validated_accuracy"])
        self.assertIsNone(r["calibrated_probability"])
        for k in ("trade_authorized","publishable",
                  "can_run_market_probe","automatic_scheduler_enabled",
                  "retime_frozen_campaign","backfill_missing_20261115_candle",
                  "score_missing_as_prediction_error",
                  "score_missing_as_prediction_hit",
                  "independent_broker_session_hours_attested",
                  "future_market_open_lag_guaranteed",
                  "absence_of_nominal_bar_proves_market_closed"):
            self.assertFalse(r[k],k)
        self.assertEqual((r["mt5_calls"],r["http_requests"],
                          r["file_writes"],r["new_cost_brl"]),(0,0,0))
        self.assertTrue(r["historical_data_are_caller_claims_not_broker_attestation"])
        self.assertEqual(r["operational_bias"],"AGUARDAR")

    def test_01_historical_3_sundays_84_pairs_not_84_independent_events(self):
        r=self.check()
        self.safe(r)
        self.assertEqual(r["state"],
            "LAB_FX28_SUNDAY_OPEN_3_HISTORICAL_SAMPLES_PLAN_ONLY_NO_GO")
        self.assertEqual(r["historical_sunday_sessions"],3)
        self.assertEqual(r["pair_series_observed_claim_only"],84)
        self.assertEqual(r["historical_nominal_start_bars_claim_only"],0)
        self.assertEqual(r["historical_min_lag_min"],120)
        self.assertEqual(r["historical_max_lag_min"],240)
        self.assertEqual(r["distinct_weekly_sessions_not_84_independent_trials"],3)
        self.assertEqual(r["aggregated_first_bar_lags_minutes_claim_only"],
            {"120":39,"135":15,"165":1,"180":25,"210":2,"225":1,"240":1})
        self.assertEqual(r["candidate_separate_research_sunday_utc"],
                         "2026-12-13T22:00:00+00:00")
        self.assertEqual(r["separate_research_history_window_end_utc"],
                         "2026-12-14T03:00:00+00:00")
        self.assertTrue(r["future_probe_requires_new_explicit_authorization"])
        self.assertEqual(len(r["historical_samples_documentary"]),3)

    def test_02_inside_frozen_campaign_cannot_schedule_future_research(self):
        r=self.check(at=datetime(2026,11,22,22,tzinfo=UTC))
        self.safe(r)
        self.assertEqual(r["state"],
            "LAB_FX28_SUNDAY_OPEN_RESEARCH_PROTOCOL_BLOCKED_NO_GO")

    def test_03_just_after_campaign_not_a_sunday(self):
        self.safe(self.check(at=datetime(2026,12,12,22,tzinfo=UTC)))
        self.assertIsNone(
            self.check(at=datetime(2026,12,12,22,tzinfo=UTC))[
                "candidate_separate_research_sunday_utc"])

    def test_04_wrong_ny17_hour_does_not_shift_to_nearest_bar(self):
        for hour in (21,23):
            with self.subTest(hour=hour):
                r=self.check(at=datetime(2026,12,13,hour,tzinfo=UTC))
                self.safe(r)
                self.assertEqual(r["state"],
                    "LAB_FX28_SUNDAY_OPEN_RESEARCH_PROTOCOL_BLOCKED_NO_GO")

    def test_05_future_sunday_still_only_research_plan(self):
        r=self.check(at=datetime(2026,12,20,22,tzinfo=UTC))
        self.safe(r)
        self.assertEqual(r["state"],
            "LAB_FX28_SUNDAY_OPEN_3_HISTORICAL_SAMPLES_PLAN_ONLY_NO_GO")
        self.assertEqual(r["candidate_separate_research_sunday_utc"],
                         "2026-12-20T22:00:00+00:00")

    def test_06_oct25_dst_boundary_wrong_nominal_utc_rejected(self):
        x=historical_fixture()
        x[0]["frozen_start_utc_in_sample"] = "2026-10-25T22:00:00+00:00"
        r=self.check(x)
        self.safe(r)
        self.assertEqual(r["reason"],
            "HISTORICAL_SOURCE_ERRORS_OR_INCONSISTENT_COUNTS")

    def test_07_duplicate_week_or_missing_week_rejected(self):
        x=historical_fixture()
        x[1] = deepcopy(x[0])
        self.assertEqual(self.check(x)["reason"],
                         "HISTORICAL_SOURCE_ERRORS_OR_INCONSISTENT_COUNTS")
        self.assertEqual(self.check(x[:2])["state"],
            "LAB_FX28_SUNDAY_OPEN_RESEARCH_PROTOCOL_BLOCKED_NO_GO")

    def test_08_mt5_none_cannot_be_a_missing_market_bar(self):
        x=historical_fixture()
        x[0]["mt5_api_none_count"]=1
        r=self.check(x)
        self.safe(r)
        self.assertEqual(r["reason"],
            "HISTORICAL_SOURCE_ERRORS_OR_INCONSISTENT_COUNTS")

    def test_09_missing_symbol_metadata_blocks(self):
        x=historical_fixture()
        x[2]["symbols_without_metadata_count"]=1
        self.assertEqual(self.check(x)["reason"],
                         "HISTORICAL_SOURCE_ERRORS_OR_INCONSISTENT_COUNTS")

    def test_10_market_watch_visibility_drift_blocks(self):
        x=historical_fixture()
        x[1]["visibility_changes_count"]=1
        self.assertEqual(self.check(x)["reason"],
                         "HISTORICAL_SOURCE_ERRORS_OR_INCONSISTENT_COUNTS")

    def test_11_empty_history_in_five_hours_is_unknown_not_lag(self):
        x=historical_fixture()
        x[1]["empty_or_invalid_count"]=1
        self.assertEqual(self.check(x)["reason"],
                         "HISTORICAL_SOURCE_ERRORS_OR_INCONSISTENT_COUNTS")

    def test_12_distribution_29_pairs_rejected(self):
        x=historical_fixture()
        x[0]["first_actual_m15_lag_minute_distribution"]["180"]=25
        r=self.check(x)
        self.safe(r)
        self.assertEqual(r["reason"],
            "HISTORICAL_FIRST_BAR_LAGS_DISAGREE_WITH_CENSUS")

    def test_13_lag_not_m15_aligned_rejected(self):
        x=historical_fixture()
        x[0]["first_actual_m15_lag_minute_distribution"]["179"]=1
        self.assertEqual(self.check(x)["reason"],"INVALID_LAG_BUCKET_OR_COUNT")

    def test_14_300min_outside_observed_5h_window_rejected(self):
        x=historical_fixture()
        x[0]["first_actual_m15_lag_minute_distribution"]["300"]=1
        self.assertEqual(self.check(x)["reason"],"INVALID_LAG_BUCKET_OR_COUNT")

    def test_15_nominal_bar_false_claim_cannot_overrule_distribution(self):
        x=historical_fixture()
        x[1]["first_nominal_m15_present_count"]=1
        x[1]["first_nominal_m15_missing_count_among_valid"]=27
        self.assertEqual(self.check(x)["reason"],
            "HISTORICAL_FIRST_BAR_LAGS_DISAGREE_WITH_CENSUS")

    def test_16_no_72_or_84_independent_forecast_claims(self):
        x=historical_fixture()
        x[0]["not_proof_future_market_open"]=False
        r=self.check(x)
        self.safe(r)
        self.assertEqual(r["reason"],
            "HISTORICAL_SOURCE_ERRORS_OR_INCONSISTENT_COUNTS")

    def test_17_invalid_bool_counts_rejected(self):
        x=historical_fixture()
        x[0]["mt5_api_none_count"]=False
        self.assertEqual(self.check(x)["reason"],
                         "HISTORICAL_SOURCE_ERRORS_OR_INCONSISTENT_COUNTS")

    def test_18_naive_future_timestamp_rejected(self):
        self.assertEqual(self.check(
            at=datetime(2026,12,13,22))["state"],
            "LAB_FX28_SUNDAY_OPEN_RESEARCH_PROTOCOL_BLOCKED_NO_GO")

    def test_19_fractional_second_future_timestamp_rejected(self):
        self.assertEqual(self.check(
            at=datetime(2026,12,13,22,0,1,tzinfo=UTC))["state"],
            "LAB_FX28_SUNDAY_OPEN_RESEARCH_PROTOCOL_BLOCKED_NO_GO")


if __name__=="__main__":
    main(verbosity=2)
