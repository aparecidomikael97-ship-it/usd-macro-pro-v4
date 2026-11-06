"""Synthetic chronology tests against dated documentary BoE MaPS casebook."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import unittest

from atlasquant_trader_boe_maps_nov5_pit_lab import (
    DECISION, EXPECTED, FRESHNESS_RESEARCH_DAYS, KIND, SCHEMA, SURVEYS,
    inspect_boe_maps_nov5_public_vintages_lab as inspect,
)

RAW = Path(__file__).resolve().parent.joinpath(
    "docs/continuidade/TRADER_BOE_MAPS_NOV5_PUBLIC_VINTAGES_LAB_20261106.json"
).read_bytes()
Z = timezone.utc


def at(day, month=11, hour=12, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=Z)


def encoded(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def audited(obj=None, *, clock=None):
    return inspect(RAW if obj is None else encoded(obj),
                   as_of_utc=clock or at(7))


class BoeMapsPublicVintagesTests(unittest.TestCase):
    def assert_hard_no_go(self, result):
        for key in ("source_publication_instant_independently_verified",
                    "source_original_bytes_independently_authenticated",
                    "historical_survey_capture_independently_verified",
                    "pre_event_contemporaneous_market_consensus_verified",
                    "policy_surprise_verified", "market_implied_probabilities_verified",
                    "survey_subjective_probabilities_are_fx_probabilities",
                    "point_in_time_eligible_for_backtest",
                    "can_feed_live_radar", "trade_authorized", "publishable",
                    "worker_enabled", "scheduler_enabled"):
            self.assertIs(result[key], False, key)
        self.assertIsNone(result["market_surprise_bps"])
        self.assertIsNone(result["validated_accuracy"])
        self.assertIsNone(result["fx_bias"])
        self.assertIsNone(result["gbp_bias"])
        self.assertEqual(result["validated_prediction_count"], 0)
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertEqual((result["http_requests"], result["new_cost_brl"]), (0, 0))

    def test_book_frozen_matches_evidence_transcribed_without_raw_html(self):
        self.assertEqual(json.loads(RAW), EXPECTED)
        self.assertEqual(EXPECTED["schema"], SCHEMA)
        self.assertEqual(EXPECTED["data_kind"], KIND)
        self.assertEqual(DECISION["actual_bank_rate_percent"], "4.00")
        self.assertEqual(DECISION["prior_bank_rate_percent"], "3.75")
        self.assertEqual(SURVEYS[0]["median_modal_post_meeting_bank_rate_percent"], "3.75")
        self.assertEqual(SURVEYS[1]["median_modal_post_meeting_bank_rate_percent"], "4.00")
        self.assertTrue(all(x["source_raw_bytes_archived"] is False for x in SURVEYS))

    def test_before_september_publication_no_pre_event_survey_context(self):
        r = audited(clock=at(18, month=9, hour=23))
        self.assertEqual(r["survey_ids_chronologically_visible_at_asof"], [])
        self.assertIsNone(r["pre_event_historical_median_percent_claim"])
        self.assertFalse(r["decision_visible_after_document_date_only"])
        self.assert_hard_no_go(r)

    def test_september_old_public_result_only_after_conservative_day_cutoff(self):
        r = audited(clock=at(19, month=9, hour=0))
        self.assertEqual(r["survey_ids_chronologically_visible_at_asof"],
                         ["MAPS_SEPTEMBER_2026_PUBLIC_RESULTS"])
        self.assertEqual(r["pre_event_historical_median_percent_claim"], "3.75")
        self.assertIsNone(r["old_survey_vs_actual_arithmetic_gap_bps_not_surprise"])
        self.assert_hard_no_go(r)

    def test_before_november_decision_date_only_release_stays_hidden(self):
        r = audited(clock=at(5, hour=23))
        self.assertFalse(r["decision_visible_after_document_date_only"])
        self.assertEqual(r["pre_event_historical_median_percent_claim"], "3.75")
        self.assertIsNone(r["post_event_november_median_percent_documentary"])
        self.assert_hard_no_go(r)

    def test_decision_day_after_conservative_midnight_old_gap_not_surprise(self):
        r = audited(clock=at(6, hour=0))
        self.assertTrue(r["decision_visible_after_document_date_only"])
        self.assertEqual(r["old_survey_vs_actual_arithmetic_gap_bps_not_surprise"], "25.00")
        self.assertIsNone(r["post_event_november_median_percent_documentary"])
        self.assertIsNone(r["market_surprise_bps"])
        self.assert_hard_no_go(r)

    def test_new_survey_not_visible_by_document_clock_until_november_seven(self):
        pre = audited(clock=at(6, hour=23, minute=59))
        post = audited(clock=at(7, hour=0))
        self.assertEqual(len(pre["survey_ids_chronologically_visible_at_asof"]), 1)
        self.assertEqual(len(post["survey_ids_chronologically_visible_at_asof"]), 2)
        self.assertEqual(post["post_event_november_median_percent_documentary"], "4.00")
        self.assertFalse(post["nov_survey_public_before_decision_by_document_date"])
        self.assertTrue(post["post_event_november_result_must_not_be_backfilled"])
        self.assert_hard_no_go(post)

    def test_pre_event_september_survey_48_days_old_and_fails_research_freshness(self):
        r = audited()
        self.assertTrue(r["sep_survey_public_before_decision_by_document_date"])
        self.assertEqual(r["pre_event_historical_survey_age_days"], 48)
        self.assertEqual(FRESHNESS_RESEARCH_DAYS, 30)
        self.assertIs(r["pre_event_historical_survey_research_fresh"], False)
        self.assert_hard_no_go(r)

    def test_survey_probabilities_and_counts_are_not_confused_with_fx_probabilities(self):
        self.assertEqual((SURVEYS[0]["mean_subjective_probability_4pct_percent"],
                          SURVEYS[0]["probability_question_respondents"]), ("35.0", 90))
        self.assertEqual((SURVEYS[1]["mean_subjective_probability_4pct_percent"],
                          SURVEYS[1]["probability_question_respondents"]), ("86.0", 78))
        self.assertNotEqual(SURVEYS[0]["modal_question_respondents"],
                            SURVEYS[0]["probability_question_respondents"])
        self.assertNotEqual(SURVEYS[1]["modal_question_respondents"],
                            SURVEYS[1]["probability_question_respondents"])
        self.assert_hard_no_go(audited())

    def test_schema_mismatch_or_value_mutation_never_reuses_same_authority(self):
        for who, field, value in ((0, "median_modal_post_meeting_bank_rate_percent", "4.00"),
                                  (1, "results_published_date", "2026-11-04"),
                                  (1, "earliest_conservative_after_publication_utc", "2026-11-05T00:00:00Z"),
                                  (1, "source_url", "https://other.example"),
                                  (1, "source_raw_bytes_archived", True),
                                  (1, "responses_closed_date", "2026-11-07")):
            obj = deepcopy(EXPECTED)
            obj["public_survey_results"][who][field] = value
            r = audited(obj)
            self.assertEqual(r["state"], "LAB_BLOCKED", field)
            self.assert_hard_no_go(r)

    def test_changing_decision_date_or_actual_rate_is_rejected(self):
        for field, value in (("actual_bank_rate_percent", "3.75"),
                             ("meeting_date", "2026-11-06"),
                             ("published_date", "2026-11-04")):
            obj = deepcopy(EXPECTED)
            obj["decision"][field] = value
            self.assertEqual(audited(obj)["state"], "LAB_BLOCKED")

    def test_survey_window_close_before_event_is_not_result_publication(self):
        r = audited()
        self.assertEqual(SURVEYS[1]["responses_closed_date"], "2026-10-23")
        self.assertEqual(SURVEYS[1]["results_published_date"], "2026-11-06")
        self.assertFalse(r["nov_survey_public_before_decision_by_document_date"])
        self.assert_hard_no_go(r)

    def test_tampered_json_duplicate_keys_and_nan_are_rejected(self):
        for b in (b'{', b'\xff', b'{"schema":NaN}',
                  RAW[:-2] + b',"schema":"OVERRIDE"}'):
            r = inspect(b, as_of_utc=at(7))
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_hard_no_go(r)

    def test_naive_clock_and_wrong_clock_types_rejected(self):
        for clock in (at(7).replace(tzinfo=None), None, "2026-11-07", 0):
            r = inspect(RAW, as_of_utc=clock)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_hard_no_go(r)

    def test_aware_offset_clock_normalized_to_utc(self):
        brt = timezone(timedelta(hours=-4))
        r = inspect(RAW, as_of_utc=at(7, hour=0).astimezone(brt))
        self.assertEqual(len(r["survey_ids_chronologically_visible_at_asof"]), 2)
        self.assertEqual(r["casebook_sha256"], sha256(RAW).hexdigest())
        self.assert_hard_no_go(r)


if __name__ == "__main__":
    unittest.main()
