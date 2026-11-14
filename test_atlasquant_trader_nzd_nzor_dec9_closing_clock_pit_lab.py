"""Deterministic IANA DST and source-claim anti-lookahead tests for NZOR."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfoNotFoundError
import unittest

from atlasquant_trader_nzd_nzor_dec9_closing_clock_pit_lab import (
    NZORCloseTimingClaim,
    inspect_nzor_dec9_preevent_clock_lab as audit,
)
from atlasquant_trader_nzd_rbnz_dec9_three_bank_forecast_context_lab import (
    EVENT_UTC, RESEARCH_SAFE_VISIBLE_FROM_UTC,
)

UTC=timezone.utc
SUNDAY=datetime(2026,11,15,10,0,tzinfo=UTC)
PRE_CLOSE=datetime(2026,12,8,3,32,tzinfo=UTC)
PRE_VENDOR=datetime(2026,12,8,3,55,tzinfo=UTC)
POST_CLOSE=datetime(2026,12,9,3,32,tzinfo=UTC)
PRE_CAPTURE=datetime(2026,12,8,4,0,tzinfo=UTC)
CANDIDATE=NZORCloseTimingClaim(
    benchmark_code="NZOR",
    nz_trade_date="2026-12-08",
    nz_meeting_date="2026-12-09",
    rate_type="NZOR_CLOSING_MID",
    issuer_published_at_utc_claim=PRE_VENDOR,
    locally_captured_at_utc_claim=PRE_CAPTURE,
    source_sha256_claim="a"*64,
)


class NzorPreeventClosingClockTests(unittest.TestCase):
    def safe(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        for field in (
            "nz_business_day_or_public_holiday_independently_validated",
            "original_quote_bytes_independently_verified",
            "original_source_issuer_first_seen_authenticated",
            "correct_nzor_maturity_and_ocr_meeting_pair_verified",
            "quote_rates_or_bid_ask_authenticated",
            "nzfma_data_license_verified",
            "vendor_redistribution_rights_verified",
            "current_OCR_and_next_OCR_expectation_solved",
            "pre_event_OIS_quote_sufficient_to_price_binary_25bp_probability",
            "policy_actual_at_dec9_authenticated",
            "trade_authorized","live_alert_allowed","publishable",
            "worker_enabled","scheduler_enabled",
        ):
            self.assertFalse(r[field],field)
        self.assertTrue(r["nominal_issuer_closing_is_not_realtime_tick"])
        self.assertTrue(
            r["nominal_vendor_distribution_is_not_authenticated_delivery_time"])
        self.assertIsNone(r["actual_policy_surprise_basis_points"])
        self.assertIsNone(r["calibrated_directional_fx_probability"])
        self.assertEqual((r["http_requests"],r["file_writes"],r["new_cost_brl"]),
                         (0,0,0))
        self.assertTrue(r["research_only"])

    def schedule(self,at=SUNDAY):
        r=audit(inspected_at_utc=at)
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_NZOR_PREEVENT_SCHEDULE_CLOCK_ONLY_NO_GO")
        return r

    def test_01_dec8_close_is_before_and_dec9_close_is_after_ocr(self):
        r=self.schedule()
        self.assertEqual(r["event_utc"],"2026-12-09T01:00:00+00:00")
        self.assertEqual(
            r["last_prior_day_closing_utc"],"2026-12-08T03:32:00+00:00")
        self.assertEqual(
            r["last_prior_day_nominal_distribution_utc"],
            "2026-12-08T03:55:00+00:00")
        self.assertEqual(
            r["dec09_same_day_closing_utc"],"2026-12-09T03:32:00+00:00")
        self.assertEqual(r["last_prior_day_distribution_to_event_minutes"],1265)
        self.assertTrue(PRE_CLOSE < PRE_VENDOR < EVENT_UTC < POST_CLOSE)

    def test_02_nominal_distribution_not_verified_live_delivery(self):
        r=self.schedule()
        self.assertEqual(r["nz_closing_snap_nominal_local"],"16:32")
        self.assertEqual(r["nz_distributed_by_nominal_local"],"16:55")
        self.assertFalse(
            r["nz_business_day_or_public_holiday_independently_validated"])
        self.assertIn("January-2026.pdf",
                      r["source_january_2026_methodology_url"])

    def test_03_dec8_time_order_claim_only_never_licensed_or_predictive(self):
        r=audit(inspected_at_utc=PRE_CAPTURE,claim=CANDIDATE)
        self.safe(r)
        self.assertEqual(r["state"],
            "LAB_NZOR_CLOSE_CLOCK_CLAIMS_CHRONOLOGICALLY_PREEVENT_NO_GO")
        self.assertTrue(r["temporal_pre_event_eligibility_only"])
        self.assertEqual(r["source_trade_date_nz"],"2026-12-08")
        self.assertEqual(r["source_closing_utc_calculated"],
                         "2026-12-08T03:32:00+00:00")
        self.assertFalse(r["original_quote_bytes_independently_verified"])
        self.assertFalse(r["nzfma_data_license_verified"])

    def test_04_same_day_1632_close_is_lookahead_even_if_real(self):
        after=replace(CANDIDATE,nz_trade_date="2026-12-09",
                      issuer_published_at_utc_claim=
                          datetime(2026,12,9,3,55,tzinfo=UTC),
                      locally_captured_at_utc_claim=
                          datetime(2026,12,9,4,0,tzinfo=UTC))
        r=audit(inspected_at_utc=after.locally_captured_at_utc_claim,
                claim=after)
        self.safe(r)
        self.assertEqual(
            r["reason"],"SAME_DAY_CLOSING_POST_RBNZ_DECISION_LOOKAHEAD")
        self.assertFalse(r["temporal_pre_event_eligibility_only"])

    def test_05_early_same_day_quote_cannot_be_nzor_1632_close(self):
        after=replace(CANDIDATE,nz_trade_date="2026-12-09",
                      issuer_published_at_utc_claim=
                          datetime(2026,12,8,23,0,tzinfo=UTC),
                      locally_captured_at_utc_claim=
                          datetime(2026,12,8,23,1,tzinfo=UTC))
        r=audit(inspected_at_utc=datetime(2026,12,8,23,2,tzinfo=UTC),
                claim=after)
        self.safe(r)
        self.assertEqual(
            r["reason"],"SAME_DAY_CLOSING_POST_RBNZ_DECISION_LOOKAHEAD")

    def test_06_dec8_vendor_first_observed_after_decision_invalid(self):
        late=replace(CANDIDATE,locally_captured_at_utc_claim=
                     EVENT_UTC+timedelta(seconds=1))
        r=audit(inspected_at_utc=EVENT_UTC+timedelta(seconds=1),claim=late)
        self.safe(r)
        self.assertEqual(r["reason"],
                         "QUOTE_OBSERVED_AFTER_EVENT_NOT_PREEVENT")

    def test_07_dec8_publish_after_event_invalid(self):
        late=replace(CANDIDATE,issuer_published_at_utc_claim=
                     EVENT_UTC+timedelta(seconds=1),
                     locally_captured_at_utc_claim=
                     EVENT_UTC+timedelta(seconds=2))
        r=audit(inspected_at_utc=EVENT_UTC+timedelta(seconds=3),claim=late)
        self.safe(r)
        self.assertEqual(r["reason"],
                         "QUOTE_OBSERVED_AFTER_EVENT_NOT_PREEVENT")

    def test_08_capture_after_report_asof_is_not_historical_receipt(self):
        r=audit(inspected_at_utc=PRE_VENDOR,claim=CANDIDATE)
        self.safe(r)
        self.assertEqual(
            r["reason"],"PUBLICATION_CAPTURE_OR_ASOF_TIME_ORDER_INVALID")

    def test_09_publishing_before_close_is_fake(self):
        wrong=replace(CANDIDATE,issuer_published_at_utc_claim=
                      PRE_CLOSE-timedelta(minutes=1),
                      locally_captured_at_utc_claim=PRE_VENDOR)
        r=audit(inspected_at_utc=PRE_VENDOR,claim=wrong)
        self.safe(r)
        self.assertEqual(
            r["reason"],"PUBLICATION_CAPTURE_OR_ASOF_TIME_ORDER_INVALID")

    def test_10_capture_before_publication_is_fake(self):
        wrong=replace(CANDIDATE,locally_captured_at_utc_claim=
                      PRE_CLOSE+timedelta(seconds=1))
        r=audit(inspected_at_utc=PRE_VENDOR,claim=wrong)
        self.safe(r)
        self.assertEqual(
            r["reason"],"PUBLICATION_CAPTURE_OR_ASOF_TIME_ORDER_INVALID")

    def test_11_wrong_benchmark_code_or_meeting_or_type_blocked(self):
        for mutated in (
            replace(CANDIDATE,benchmark_code="NZOS"),
            replace(CANDIDATE,benchmark_code="BKBM"),
            replace(CANDIDATE,nz_meeting_date="2026-12-10"),
            replace(CANDIDATE,rate_type="B2_TWO_YEAR_SWAP"),
        ):
            with self.subTest(mutated=mutated):
                r=audit(inspected_at_utc=PRE_CAPTURE,claim=mutated)
                self.safe(r)
                self.assertEqual(r["reason"],"CLAIM_MISSING_OR_INVALID")

    def test_12_bad_sha_and_source_synthetic_hash_not_authentic(self):
        for sha in ("","0"*63,"x"*64,True):
            with self.subTest(sha=sha):
                r=audit(inspected_at_utc=PRE_CAPTURE,
                        claim=replace(CANDIDATE,source_sha256_claim=sha))
                self.safe(r)
                self.assertEqual(r["reason"],"CLAIM_MISSING_OR_INVALID")
        r=audit(inspected_at_utc=PRE_CAPTURE,claim=CANDIDATE)
        self.safe(r)
        self.assertTrue(r["temporal_pre_event_eligibility_only"])
        self.assertFalse(r["original_source_issuer_first_seen_authenticated"])

    def test_13_future_date_weekend_or_invalid_calendar_day_blocked(self):
        for value in ("2026-12-12","2026-12-13","2026-02-30",
                      "2026-12-00","2026-12-8","2026-13-08"):
            with self.subTest(value=value):
                r=audit(inspected_at_utc=PRE_CAPTURE,
                        claim=replace(CANDIDATE,nz_trade_date=value))
                self.safe(r)
                self.assertFalse(r["temporal_pre_event_eligibility_only"])
                self.assertEqual(
                    r["state"],"LAB_NZOR_CLOSE_CLAIM_TIME_ORDER_REJECTED_NO_GO")

    def test_14_invalid_inspection_utc_and_before_floor_blocked(self):
        for value in (None,True,"2026-12-08T04:00:00Z",
                      PRE_CAPTURE.replace(tzinfo=None),
                      PRE_CAPTURE+timedelta(microseconds=1),
                      RESEARCH_SAFE_VISIBLE_FROM_UTC-timedelta(seconds=1)):
            with self.subTest(value=value):
                r=audit(inspected_at_utc=value,claim=CANDIDATE)
                self.safe(r)
                self.assertEqual(r["reason"],
                    "INVALID_CLOCK_OR_BEFORE_RESEARCH_VISIBILITY")

    def test_15_first_sunday_preflight_has_no_future_data(self):
        r=self.schedule(SUNDAY)
        self.assertIsNone(r["source_trade_date_nz"])
        self.assertIsNone(r["claim_local_capture_utc"])
        r=audit(inspected_at_utc=SUNDAY,claim=CANDIDATE)
        self.safe(r)
        self.assertFalse(r["temporal_pre_event_eligibility_only"])
        self.assertEqual(r["reason"],
                         "PUBLICATION_CAPTURE_OR_ASOF_TIME_ORDER_INVALID")

    def test_16_missing_iana_timezone_fails_closed(self):
        with patch(
            "atlasquant_trader_nzd_nzor_dec9_closing_clock_pit_lab.ZoneInfo",
            side_effect=ZoneInfoNotFoundError
        ):
            r=audit(inspected_at_utc=SUNDAY)
        self.safe(r)
        self.assertEqual(r["reason"],"NZ_TIMEZONE_REFERENCE_UNAVAILABLE")

    def test_17_exact_cutoff_boundary_at_ocr_time_rejects_afterclose(self):
        r=self.schedule(EVENT_UTC)
        self.assertEqual(
            r["dec09_same_day_closing_utc"],"2026-12-09T03:32:00+00:00")
        self.assertLess(EVENT_UTC,
                        datetime(2026,12,9,3,32,tzinfo=UTC))
        r=audit(inspected_at_utc=EVENT_UTC,claim=CANDIDATE)
        self.safe(r)
        # Dec8 claim would be temporally eligible, but this does not prove
        # a historic first-seen: no price, evidence hash or trading.
        self.assertTrue(r["temporal_pre_event_eligibility_only"])
        self.assertFalse(r["trade_authorized"])

    def test_18_no_claim_is_literally_only_calendar_math(self):
        r=self.schedule()
        self.assertFalse(r["temporal_pre_event_eligibility_only"])
        self.assertIsNone(r["actual_policy_surprise_basis_points"])
        self.assertIsNone(r["calibrated_directional_fx_probability"])


if __name__=="__main__":
    unittest.main()
