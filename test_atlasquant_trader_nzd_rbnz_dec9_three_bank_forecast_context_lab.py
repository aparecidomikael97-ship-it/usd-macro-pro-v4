"""Three bank opinions, never representative RBNZ market consensus."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import unittest

from atlasquant_trader_nzd_rbnz_dec9_three_bank_forecast_context_lab import (
    BANK_REPORTS, EVENT_UTC, RESEARCH_SAFE_VISIBLE_FROM_UTC,
    inspect_rbnz_dec9_three_bank_forecasts_lab as inspect,
)

UTC=timezone.utc
NOW=datetime(2026,11,15,10,0,tzinfo=UTC)


class ThreeBankDec9ForecastResearchTests(unittest.TestCase):
    def safe(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        for k in ("trade_authorized","live_alert_allowed","publishable",
                  "worker_enabled","scheduler_enabled",
                  "statistical_market_consensus_verified",
                  "market_implied_hike_probability_verified",
                  "publisher_document_original_bytes_retained",
                  "publisher_first_seen_independently_attested",
                  "consensus_universe_or_sample_frame_defined",
                  "fx_direction_from_ocr_expectations_established"):
            self.assertFalse(r[k],k)
        for k in ("calibrated_nzd_fx_probability","forecast_ocr_probability",
                  "expected_nzd_pair_direction","empirical_backtest_accuracy"):
            self.assertIsNone(r[k])
        self.assertTrue(r["forecast_sources_independent_banks_not_independent_events"])
        self.assertTrue(r["safe_day_floor_is_not_actual_first_seen"])
        self.assertTrue(r["publication_dates_are_calendar_only_claims"])
        self.assertTrue(r["forecast_is_not_actual_ocr_decision"])
        self.assertEqual(r["economic_event_root_count"],1)
        self.assertEqual((r["http_requests"],r["file_writes"],
                          r["new_cost_brl"]),(0,0,0))

    def ready(self,now=NOW):
        r=inspect(as_of_utc=now)
        self.safe(r)
        self.assertEqual(r["state"],
            "LAB_RBNZ_DEC9_THREE_PUBLISHER_FORECASTS_UPCOMING_NO_GO")
        self.assertTrue(r["event_is_still_upcoming"])
        self.assertEqual(r["expected_rate_claim_if_25bp_hike_pct"],"3.00")
        self.assertEqual(r["publisher_forecast_count"],3)
        self.assertEqual(set(r["publisher_names"]),{"ANZ","BNZ","WESTPAC"})
        self.assertEqual(r["direct_pair_count"],7)
        self.assertEqual(r["d1_w1_event_exposure_slots"],14)
        return r

    def test_01_three_publishers_not_thirty_percent_or_hundred_percent_confidence(self):
        r=self.ready()
        self.assertEqual(len(r["bank_forecast_rows"]),3)
        self.assertFalse(r["market_implied_hike_probability_verified"])
        self.assertIsNone(r["forecast_ocr_probability"])
        self.assertIsNone(r["calibrated_nzd_fx_probability"])
        self.assertEqual(r["economic_event_root_count"],1)

    def test_02_issuer_document_days_are_publication_claims_not_first_seen(self):
        r=self.ready()
        by={x["publisher"]:x for x in r["bank_forecast_rows"]}
        self.assertEqual(by["ANZ"]["publisher_calendar_date_claim"],"2026-11-11")
        self.assertEqual(by["BNZ"]["publisher_calendar_date_claim"],"2026-10-29")
        self.assertEqual(by["WESTPAC"]["publisher_calendar_date_claim"],"2026-11-09")
        for row in r["bank_forecast_rows"]:
            self.assertEqual(row["kind"],
                             "PUBLISHER_DATED_BANK_FORECAST_NOT_MARKET_SURVEY")
            self.assertFalse(row["source_captured_original_retained"])
            self.assertFalse(row["first_read_observed_at_pre_event_authenticated"])
            self.assertFalse(
                row["exact_issuer_publication_timestamp_independently_verified"])
            self.assertIsNone(row["source_original_sha256"])
            self.assertIsNone(row["signed_nzd_fx_effect"])

    def test_03_all_forecast_policy_hike_not_fx_direction(self):
        r=self.ready()
        for row in r["bank_forecast_rows"]:
            self.assertEqual(row["forecast_change_bps_claim"],25)
            self.assertEqual(row["expected_policy_action_claim"],"HIKE")
            self.assertEqual(row["expected_dec2026_ocr_pct_claim"],"3.00")
            self.assertEqual(row["forecast_target_event_utc"],EVENT_UTC.isoformat())
            self.assertIsNone(row["comparable_pre_event_market_price_quote"])
            self.assertFalse(row["has_population_representative_consensus_weight"])

    def test_04_westpac_risks_and_data_dependence_are_disclosed(self):
        r=self.ready()
        risk={x["publisher"]:x["risk_note"] for x in r["bank_forecast_rows"]}
        self.assertIn("far from done deal",risk["WESTPAC"])
        self.assertIn("global downside risks",risk["ANZ"])
        self.assertIn("not certainty",risk["BNZ"])

    def test_05_sunday_06_cuiaba_preflight_is_valid_as_research_context(self):
        r=self.ready(datetime(2026,11,15,10,0,tzinfo=UTC))
        self.assertEqual(r["research_day_floor_utc"],
                         "2026-11-15T00:00:00+00:00")
        self.assertEqual(r["direct_pair_count"],7)

    def test_06_no_retroactive_access_claim_14_nov_or_prior(self):
        for when in (
            datetime(2026,10,29,1,0,tzinfo=UTC),
            datetime(2026,11,14,11,55,tzinfo=UTC),
            RESEARCH_SAFE_VISIBLE_FROM_UTC-timedelta(seconds=1),
        ):
            with self.subTest(when=when):
                r=inspect(as_of_utc=when)
                self.safe(r)
                self.assertEqual(r["state"],
                    "LAB_RBNZ_DEC9_THREE_BANK_FORECAST_RESEARCH_BLOCKED_NO_GO")
                self.assertEqual(r["publisher_forecast_count"],0)

    def test_07_exact_research_day_floor_safe_to_show_research(self):
        self.ready(RESEARCH_SAFE_VISIBLE_FROM_UTC)

    def test_08_second_before_and_at_dec9_event(self):
        a=self.ready(EVENT_UTC-timedelta(seconds=1))
        b=inspect(as_of_utc=EVENT_UTC)
        self.safe(b)
        self.assertFalse(b["event_is_still_upcoming"])
        self.assertEqual(b["state"],
            "LAB_RBNZ_DEC9_FORECAST_RESEARCH_EVENT_ALREADY_ELAPSED_NO_GO")
        self.assertEqual(b["publisher_forecast_count"],3)
        self.assertIn("AFTER_EVENT",b["reason"])
        self.assertFalse(b["statistical_market_consensus_verified"])

    def test_09_invalid_naive_or_microsecond_clock_rejects(self):
        for when in (None,"2026-11-15T10:00:00Z",
                     NOW.replace(tzinfo=None),
                     NOW+timedelta(microseconds=1)):
            with self.subTest(when=when):
                r=inspect(as_of_utc=when)
                self.safe(r)
                self.assertEqual(r["publisher_forecast_count"],0)

    def test_10_detect_duplicate_publisher_or_duplicate_source(self):
        original=BANK_REPORTS
        with patch("atlasquant_trader_nzd_rbnz_dec9_three_bank_forecast_context_lab."
                   "BANK_REPORTS", (original[0],original[0],original[2])):
            r=inspect(as_of_utc=NOW)
        self.safe(r)
        self.assertEqual(r["state"],
            "LAB_RBNZ_DEC9_THREE_BANK_FORECAST_RESEARCH_BLOCKED_NO_GO")
        dup=(original[0],replace(original[1],source_url=original[0].source_url),
             original[2])
        with patch("atlasquant_trader_nzd_rbnz_dec9_three_bank_forecast_context_lab."
                   "BANK_REPORTS", dup):
            r=inspect(as_of_utc=NOW)
        self.safe(r)
        self.assertEqual(r["publisher_forecast_count"],0)

    def test_11_mismatched_rate_action_or_undated_future_report_block(self):
        original=BANK_REPORTS
        for damaged in (
            replace(original[0],expected_dec2026_ocr_pct_claim="2.75"),
            replace(original[0],expected_change_bps=0),
            replace(original[0],expected_action="HOLD"),
            replace(original[0],publication_day_claim=
                    RESEARCH_SAFE_VISIBLE_FROM_UTC.date()),
        ):
            with self.subTest(damaged=damaged):
                with patch("atlasquant_trader_nzd_rbnz_dec9_three_bank_forecast_context_lab."
                           "BANK_REPORTS", (damaged,)+original[1:]):
                    r=inspect(as_of_utc=NOW)
                self.safe(r)
                self.assertEqual(r["publisher_forecast_count"],0)

    def test_12_only_seven_direct_nzd_pairs_and_two_horizons(self):
        r=self.ready()
        self.assertEqual(len(r["direct_nzd_pairs_in_fx28"]),7)
        self.assertTrue(all("NZD" in x for x in r["direct_nzd_pairs_in_fx28"]))
        self.assertEqual(r["d1_w1_event_exposure_slots"],14)
        self.assertEqual(r["economic_event_root_count"],1)

    def test_13_event_research_does_not_authorize_real_28pair_bias(self):
        r=self.ready()
        self.assertTrue(r["research_only"])
        self.assertTrue(r["research_only_not_live_expectations"])
        self.assertTrue(r["forecast_might_be_revised_before_decision"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertIsNone(r["expected_nzd_pair_direction"])


if __name__=="__main__":
    unittest.main()
