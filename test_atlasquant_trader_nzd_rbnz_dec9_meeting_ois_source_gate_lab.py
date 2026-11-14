"""Offline source admissibility tests: never substitute B2 for NZD meeting OIS."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import unittest

from atlasquant_trader_nzd_rbnz_dec9_meeting_ois_source_gate_lab import (
    CANDIDATES, EVENT_UTC, RESEARCH_SAFE_VISIBLE_FROM_UTC,
    NZFMA_SOURCE_URL, RBNZ_B2_SOURCE_URL,
    inspect_rbnz_dec9_ois_sources_lab as inspect,
)

UTC=timezone.utc
NOW=datetime(2026,11,15,10,0,tzinfo=UTC)


class RbnzOisSourceReadinessTests(unittest.TestCase):
    def safe(self,r):
        self.assertEqual(r["fx28_operational_bias"],"AGUARDAR")
        for k in (
            "meeting_date_ois_license_independently_verified",
            "paid_subscription_active_or_committed",
            "issuer_market_quote_original_retained",
            "meeting_date_ois_quote_exists_in_atlasquant",
            "market_quote_bid_ask_settlement_reconciled",
            "quote_published_timestamp_independently_authenticated",
            "quote_capture_clock_before_event_verified",
            "vendor_redistribution_rights_confirmed",
            "provider_issued_price_and_convention_checked",
            "immediate_pre_dec9_expectation_available",
            "dec09_ocr_actual_already_announced",
            "trade_authorized","publishable","live_alert_allowed",
            "scheduler_enabled","worker_enabled",
        ):
            self.assertFalse(r[k],k)
        for k in ("actual_policy_surprise_basis_points",
                  "dec09_25bps_hike_probability","nzd_direction_probability"):
            self.assertIsNone(r[k])
        self.assertEqual((r["http_requests"],r["file_writes"],
                          r["new_cost_brl"]),(0,0,0))
        self.assertTrue(r["research_only"])
        self.assertEqual(r["economic_event_roots"],1)

    def ready(self,kind=None,now=NOW):
        r=inspect(as_of_utc=now,selected_source_key=kind)
        self.safe(r)
        self.assertEqual(
            r["state"],"LAB_RBNZ_DEC09_OIS_PROVENANCE_READY_FOR_RESEARCH_NO_GO")
        self.assertEqual(r["source_candidates_count"],6)
        self.assertEqual(r["correct_instrument_sources_known"],1)
        self.assertEqual(r["direct_nzd_fx28_pair_count"],7)
        self.assertEqual(r["d1_w1_potential_event_exposures"],14)
        return r

    def test_01_six_documented_sources_never_six_quotes(self):
        r=self.ready()
        self.assertEqual(len(r["issuer_source_catalog"]),6)
        self.assertEqual(r["correct_instrument_sources_known"],1)
        self.assertFalse(any(s["can_supply_dec09_ois_quote_now"]
                             for s in r["issuer_source_catalog"]))
        self.assertFalse(any(s["source_original_bytes_or_quote_authenticated"]
                             for s in r["issuer_source_catalog"]))

    def test_02_right_nzfma_instrument_exists_but_is_subscription_only(self):
        r=self.ready("NZFMA_MEETING_DATE_OIS_LICENSED")
        self.assertEqual(
            r["source_requested_classification"],"OCR_OIS_ONE_RBNZ_MEETING")
        self.assertEqual(
            r["source_requested_reason"],
            "CORRECT_INSTRUMENT_BUT_ATLASQUANT_HAS_NO_VERIFIED_ENTITLEMENT_OR_QUOTE")
        s=next(s for s in r["issuer_source_catalog"]
               if s["is_exact_meeting_date_ois_kind"])
        self.assertEqual(s["official_or_publisher_reference_url"],
                         NZFMA_SOURCE_URL)
        self.assertEqual(s["access_tier_as_officially_documented"],
                         "SUBSCRIPTION_REQUIRED_NOT_CONNECTED")
        self.assertFalse(r["immediate_pre_dec9_expectation_available"])

    def test_03_b2_decided_ocr_cannot_be_the_expectation(self):
        r=self.ready("RBNZ_B2_DAILY_OCR_DECIDED")
        self.assertEqual(r["source_requested_classification"],
                         "POLICY_ACTUAL_OCR_NOT_MARKET_EXPECTATION")
        self.assertEqual(r["source_requested_reason"],
                         "DECIDED_OCR_IS_NOT_PRE_EVENT_EXPECTED_OCR")
        row=next(x for x in r["issuer_source_catalog"]
                 if x["source_key"]=="RBNZ_B2_DAILY_OCR_DECIDED")
        self.assertEqual(row["official_or_publisher_reference_url"],
                         RBNZ_B2_SOURCE_URL)
        self.assertTrue(row["is_backward_looking_rate"])
        self.assertFalse(row["is_exact_meeting_date_ois_kind"])

    def test_04_b2_two_year_swap_uses_bank_bill_not_meeting_ois(self):
        r=self.ready("RBNZ_B2_2Y_BANK_BILL_SWAP")
        self.assertIn("TWO_YEAR_SWAP",r["source_requested_classification"])
        self.assertIn("BKBM_CREDIT_PREMIA",r["source_requested_reason"])
        self.assertFalse(r["meeting_date_ois_quote_exists_in_atlasquant"])

    def test_05_free_compound_ocr_is_realized_nzonia_not_future(self):
        r=self.ready("NZFMA_FREE_OCR_COMPOUND_INDEX_DELAYED")
        row=next(x for x in r["issuer_source_catalog"]
                 if x["source_key"]=="NZFMA_FREE_OCR_COMPOUND_INDEX_DELAYED")
        self.assertEqual(row["access_tier_as_officially_documented"],
                         "FREE_WITH_24_HOUR_DELAY")
        self.assertTrue(row["is_backward_looking_rate"])
        self.assertIn("BACKWARD_LOOKING",row["source_rejection_reason"])

    def test_06_delayed_free_one_three_year_swaps_not_meeting_ois(self):
        r=self.ready("NZFMA_FREE_1Y_3Y_SWAP_DELAYED")
        self.assertIn("NOT_MEETING_OIS",r["source_requested_reason"])

    def test_07_bnz_65_percent_is_secondary_report_not_raw_quote(self):
        r=self.ready("BNZ_REPORTED_65PCT_DEC09_NOV09")
        row=next(x for x in r["issuer_source_catalog"]
                 if x["source_key"]=="BNZ_REPORTED_65PCT_DEC09_NOV09")
        self.assertTrue(row["is_secondary_market_commentary"])
        self.assertFalse(row["is_exact_meeting_date_ois_kind"])
        self.assertFalse(r["market_quote_bid_ask_settlement_reconciled"])
        self.assertIsNone(r["dec09_25bps_hike_probability"])

    def test_08_preflight_sunday_6am_cuiaba_is_only_research(self):
        r=self.ready()
        self.assertEqual(r["policy_event_utc"],"2026-12-09T01:00:00+00:00")
        self.assertEqual(len(r["direct_nzd_fx28_pairs"]),7)
        self.assertTrue(all("NZD" in x for x in r["direct_nzd_fx28_pairs"]))
        self.assertFalse(r["trade_authorized"])

    def test_09_no_retroactive_source_visibility_before_research_floor(self):
        for when in (
            datetime(2026,11,14,12,25,tzinfo=UTC),
            datetime(2026,10,29,1,tzinfo=UTC),
            RESEARCH_SAFE_VISIBLE_FROM_UTC-timedelta(seconds=1),
        ):
            with self.subTest(when=when):
                r=inspect(as_of_utc=when)
                self.safe(r)
                self.assertEqual(r["state"],
                    "LAB_RBNZ_MEETING_OIS_SOURCE_GATE_BLOCKED_NO_GO")
                self.assertEqual(r["source_candidates_count"],0)

    def test_10_exact_floor_allows_research_not_live_price(self):
        self.ready(now=RESEARCH_SAFE_VISIBLE_FROM_UTC)

    def test_11_after_event_no_backfilled_pre_event_quote(self):
        for when in (EVENT_UTC,EVENT_UTC+timedelta(days=1)):
            with self.subTest(when=when):
                r=inspect(as_of_utc=when)
                self.safe(r)
                self.assertEqual(
                    r["state"],
                    "LAB_RBNZ_DEC09_OIS_EVENT_ELAPSED_NO_RETRO_SNAPSHOT_NO_GO")
                self.assertIsNone(r["actual_policy_surprise_basis_points"])

    def test_12_invalid_utc_clocks_and_imprecise_early_rejected(self):
        for value in (
            None,"2026-11-15T10:00:00Z",NOW.replace(tzinfo=None),
            NOW+timedelta(microseconds=1),False,
        ):
            with self.subTest(value=value):
                r=inspect(as_of_utc=value)
                self.safe(r)
                self.assertEqual(r["source_candidates_count"],0)

    def test_13_bad_key_or_user_supplied_fake_price_source_rejected(self):
        for source in ("", "SOME_FAKE_FREE_OIS", "NZFMA_OIS_UNLIMITED",
                       22,True,[],{}):
            with self.subTest(source=source):
                r=inspect(as_of_utc=NOW,selected_source_key=source)
                self.safe(r)
                self.assertEqual(r["reason"],"UNKNOWN_OR_UNSUPPORTED_SOURCE_KEY")

    def test_14_all_six_valid_keys_are_still_no_go(self):
        for candidate in CANDIDATES:
            with self.subTest(key=candidate.source_key):
                r=self.ready(candidate.source_key)
                self.assertFalse(r["trade_authorized"])
                self.assertFalse(r["meeting_date_ois_quote_exists_in_atlasquant"])
                self.assertIsNone(r["nzd_direction_probability"])

    def test_15_duplicate_source_id_cannot_pass_catalog(self):
        forged=(CANDIDATES[0],CANDIDATES[0])+CANDIDATES[2:]
        with patch(
            "atlasquant_trader_nzd_rbnz_dec9_meeting_ois_source_gate_lab."
            "CANDIDATES",forged
        ):
            r=inspect(as_of_utc=NOW)
        self.safe(r)
        self.assertEqual(r["reason"],"SOURCE_CATALOG_OR_UNIVERSE_INCONSISTENT")

    def test_16_no_subscription_or_new_cost_is_triggered(self):
        r=self.ready("NZFMA_MEETING_DATE_OIS_LICENSED")
        self.assertFalse(r["paid_subscription_active_or_committed"])
        self.assertEqual(r["new_cost_brl"],0)
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["worker_enabled"])

    def test_17_correct_nzor_benchmark_midrate_not_immediate_tick(self):
        r=self.ready("NZFMA_MEETING_DATE_OIS_LICENSED")
        self.assertEqual(r["correct_benchmark_nzfbf_identifier"],"NZOR")
        self.assertEqual(
            r["correct_benchmark_official_methodology_url"],
            "https://www.nzfbf.co.nz/benchmarks/closing-rates/nzor")
        self.assertTrue(
            r["nz_or_is_closing_midrate_between_consecutive_ocr_meetings"])
        self.assertTrue(
            r["a_closing_midrate_is_not_automatically_a_pre_event_tick"])
        self.assertFalse(r["quote_capture_clock_before_event_verified"])

    def test_18_one_policy_event_not_seven_or_fourteen_independent_roots(self):
        r=self.ready()
        self.assertEqual(r["economic_event_roots"],1)
        self.assertEqual(r["d1_w1_potential_event_exposures"],14)
        self.assertFalse(r["meeting_date_ois_license_independently_verified"])


if __name__=="__main__":
    unittest.main()
