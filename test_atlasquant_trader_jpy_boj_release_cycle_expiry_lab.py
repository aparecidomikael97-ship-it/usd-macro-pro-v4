"""Offline synthetic/claim-only BoJ context expiry QA, no market data/HTTP.

The historical overlay tests include only fixture metadata; they do NOT
include the actual October PDF retained on AM12. This is a contract test.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from copy import deepcopy
import unittest

from atlasquant_fx_universe import CURRENCIES
from atlasquant_trader_fx28_historical_release_overlay_lab import (
    combine_policy_coverage,
)
from atlasquant_trader_jpy_boj_release_cycle_expiry_lab import (
    SCHEMA, NEXT_SCHEDULED_MEETING_EARLIEST_UTC,
    DECISION_PUBLICATION_DATE_UTC,
    review_jpy_october_release_cycle_lab as review,
)
from test_atlasquant_trader_fx28_historical_release_overlay_lab import (
    baseline, documentary_claim,
)
UTC=timezone.utc
ASOF=datetime(2026,11,15,11,17,0,tzinfo=UTC)
CURRENT=("AUD","CAD","CHF","EUR","GBP","NZD","USD")

def build(current=CURRENT, history=True):
    r=baseline(current)
    return combine_policy_coverage(
        current_policy_report=r,
        historical_docs={"JPY":documentary_claim("JPY")} if history else {},
    )

class BoJExpiryTests(unittest.TestCase):
    def run_guard(self,*,report=None,at=ASOF):
        r=review(
            historical_overlay_report=build() if report is None else report,
            inspected_at_utc=at,
        )
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["signed_fx_effects_calibrated"],0)
        self.assertIsNone(r["usd_jpy_or_seven_yen_crosses_directional_bias"])
        self.assertIsNone(r["fx_accuracy"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertFalse(r["issuer_latest_policy_independently_authenticated"])
        self.assertFalse(r["issuer_current_policy_homepage_accepted"])
        self.assertFalse(r["intermeeting_unscheduled_policy_decision_excluded_by_calendar"])
        self.assertEqual((r["http_calls"],r["mt5_calls"],r["file_writes"]),(0,0,0))
        return r

    def test_01_actual_scheduled_context_nov15_only_never_current_homepage(self):
        r=self.run_guard()
        self.assertEqual(r["state"],
            "LAB_JPY_BOJ_ARCHIVED_CONTEXT_WITHIN_SCHEDULED_CYCLE_ONLY_NO_GO")
        self.assertTrue(r["archived_october_documentary_source_locally_checked_claim"])
        self.assertTrue(r["scheduled_context_window_not_expired"])
        self.assertEqual(r["reason"],
            "OCT30_DOCUMENT_CHECKED_BUT_LATEST_POLICY_NOT_AUTHENTICATED")

    def test_02_seven_current_pages_plus_jpy_archival_not_eight_current(self):
        prior=build()
        self.assertEqual(prior["current_issuer_current_page_accepted_count"],7)
        self.assertEqual(prior["pairs_with_both_current_policy_source_packets_count"],21)
        self.assertEqual(prior["currencies_with_any_checked_policy_document_count"],8)
        self.assertEqual(prior["pairs_with_both_any_checked_policy_documents_count"],28)
        r=self.run_guard(report=prior)
        self.assertFalse(r["issuer_current_policy_homepage_accepted"])

    def test_03_before_oct30_publication_never_retrofits(self):
        r=self.run_guard(at=DECISION_PUBLICATION_DATE_UTC-timedelta(seconds=1))
        self.assertEqual(r["reason"],"BEFORE_OCT30_DECISION_PUBLICATION_CANNOT_USE_HINDSIGHT")
        self.assertFalse(r["scheduled_context_window_not_expired"])

    def test_04_at_exact_oct30_publication_not_an_issuer_first_seen_proof(self):
        r=self.run_guard(at=DECISION_PUBLICATION_DATE_UTC)
        self.assertTrue(r["scheduled_context_window_not_expired"])
        self.assertFalse(r["source_was_captured_before_oct30_release_authenticated"])

    def test_05_before_next_meeting_local_midnight_barely_candidate(self):
        r=self.run_guard(at=NEXT_SCHEDULED_MEETING_EARLIEST_UTC-timedelta(microseconds=1))
        self.assertTrue(r["scheduled_context_window_not_expired"])

    def test_06_at_first_day_of_next_meeting_expired(self):
        r=self.run_guard(at=NEXT_SCHEDULED_MEETING_EARLIEST_UTC)
        self.assertEqual(r["state"],"LAB_JPY_BOJ_ARCHIVED_CONTEXT_EXPIRED_NO_GO")
        self.assertFalse(r["scheduled_context_window_not_expired"])

    def test_07_next_meeting_day_two_still_expired(self):
        r=self.run_guard(at=NEXT_SCHEDULED_MEETING_EARLIEST_UTC+timedelta(days=1))
        self.assertFalse(r["scheduled_context_window_not_expired"])

    def test_08_after_new_year_still_expired(self):
        r=self.run_guard(at=datetime(2027,1,5,tzinfo=UTC))
        self.assertEqual(r["reason"],
            "NEXT_SCHEDULED_POLICY_MEETING_HAS_BEGUN_REVALIDATE_SOURCE")

    def test_09_invalid_no_jpy_archive_is_not_a_checked_decision(self):
        r=self.run_guard(report=build(history=False))
        self.assertEqual(r["reason"],"JPY_ARCHIVED_RELEASE_NOT_CHECKED")

    def test_10_rejected_wrong_sha_metadata_never_counts_as_context(self):
        cur=baseline(CURRENT)
        claim=documentary_claim("JPY")
        claim["sha256"]="0"*64
        report=combine_policy_coverage(
            current_policy_report=cur,historical_docs={"JPY":claim})
        self.assertIn("JPY",report["new_historical_docs_rejected"])
        r=self.run_guard(report=report)
        self.assertFalse(r["scheduled_context_window_not_expired"])

    def test_11_current_jpy_claim_is_separate_from_archival(self):
        report=combine_policy_coverage(
            current_policy_report=baseline(CURRENCIES),
            historical_docs={"JPY":documentary_claim("JPY")})
        r=self.run_guard(report=report)
        self.assertEqual(r["reason"],
            "JPY_CURRENT_HOMEPAGE_MUST_BE_A_SEPARATE_SOURCE_CONTRACT")
        self.assertFalse(r["issuer_current_policy_homepage_accepted"])

    def test_12_forged_trade_flag_blocks(self):
        report=build()
        report["trade_authorized"]=True
        r=self.run_guard(report=report)
        self.assertEqual(r["state"],"LAB_JPY_BOJ_RELEASE_CYCLE_INPUT_BLOCKED_NO_GO")

    def test_13_forged_probability_blocks(self):
        report=build()
        report["calibrated_probability"]=0.9
        r=self.run_guard(report=report)
        self.assertFalse(r["scheduled_context_window_not_expired"])

    def test_14_wrong_overlay_schema_blocks(self):
        report=build()
        report["schema"]="FAKE_SOURCE"
        r=self.run_guard(report=report)
        self.assertFalse(r["scheduled_context_window_not_expired"])

    def test_15_wrong_reject_status_blocks(self):
        report=build()
        report["new_historical_docs_rejected"]["JPY"]="REJECTED"
        r=self.run_guard(report=report)
        self.assertFalse(r["scheduled_context_window_not_expired"])

    def test_16_naive_asof_blocks(self):
        r=self.run_guard(at=datetime(2026,11,15,11,17))
        self.assertEqual(r["state"],"LAB_JPY_BOJ_RELEASE_CYCLE_INPUT_BLOCKED_NO_GO")

    def test_17_cuiaba_timezone_equivalent_to_utc(self):
        cuiaba=timezone(timedelta(hours=-4))
        r=self.run_guard(at=ASOF.astimezone(cuiaba))
        self.assertTrue(r["scheduled_context_window_not_expired"])

    def test_18_wrong_report_type_blocks(self):
        r=self.run_guard(report=[])
        self.assertEqual(r["reason"],"OVERLAY_OR_AS_OF_INVALID")

    def test_19_duplicated_jpy_history_label_blocks(self):
        report=build()
        report["new_historical_docs_checked"]=["JPY","JPY"]
        r=self.run_guard(report=report)
        self.assertEqual(r["state"],"LAB_JPY_BOJ_RELEASE_CYCLE_INPUT_BLOCKED_NO_GO")

    def test_20_rate_1_50_dissent_cannot_be_target(self):
        cur=baseline(CURRENT)
        claim=documentary_claim("JPY")
        claim["document"]["rate_target_pct"]=1.50
        report=combine_policy_coverage(current_policy_report=cur,historical_docs={"JPY":claim})
        r=self.run_guard(report=report)
        self.assertFalse(r["archived_october_documentary_source_locally_checked_claim"])
        self.assertEqual(r["reason"],"JPY_ARCHIVED_RELEASE_NOT_CHECKED")

if __name__=="__main__":unittest.main(verbosity=2)
