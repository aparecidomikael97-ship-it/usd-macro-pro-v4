"""Offline evidence-grade audit with explicit no-go outcomes."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import unittest

from atlasquant_fx_universe import CURRENCIES
from atlasquant_trader_g8_publication_evidence_audit_lab import (
    PREVIOUSLY_REPORTED_POST_RELEASE_LOCAL_FILES,
    inspect_g8_publication_evidence_lab,
)


def at(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class PublicationEvidenceAuditTests(unittest.TestCase):
    def audit(self, stamp: str = "2026-11-08T12:00:00Z", horizon: str = "D1") -> dict:
        return inspect_g8_publication_evidence_lab(decision_at_utc=at(stamp), horizon=horizon)

    def test_count_17_researched_issuer_observations(self) -> None:
        self.assertEqual(self.audit()["catalogued_records"], 17)

    def test_six_exact_publisher_times_not_capture_proofs(self) -> None:
        r = self.audit()
        self.assertEqual(r["exact_publisher_time_records"], 6)
        self.assertTrue(all(not x["historical_vintage_attested"] for x in r["sources"].values()))

    def test_ten_date_only_cuts(self) -> None:
        self.assertEqual(self.audit()["date_only_conservative_records"], 10)

    def test_one_ocr_current_page_update_not_original(self) -> None:
        r = self.audit()
        self.assertEqual(r["current_update_not_original_records"], 1)
        self.assertEqual(r["sources"]["NZD_OCR_2026_10"]["publisher_time_precision_grade"],
                         "CURRENT_PAGE_UPDATE_NOT_ORIGINAL_ISSUE")

    def test_rotating_japan_statistics_latest_page_flagged(self) -> None:
        r = self.audit()
        self.assertEqual(r["known_mutable_publication_pages"], 1)
        self.assertTrue(r["sources"]["JPY_NATIONAL_CPI_2026_09"]["known_mutable_latest_page"])

    def test_no_other_page_claims_revision_free(self) -> None:
        r = self.audit()
        self.assertTrue(all(not x["mutability_independently_excluded"] for x in r["sources"].values()))

    def test_three_prior_local_capture_claims_not_reverified_here(self) -> None:
        r = self.audit()
        counted = {k for k, x in r["sources"].items()
                   if x["post_release_local_capture_reported_not_reverified"]}
        self.assertEqual(counted, PREVIOUSLY_REPORTED_POST_RELEASE_LOCAL_FILES)
        self.assertFalse(r["source_body_reverified_on_am12_now"])

    def test_all_current_research_reached_publisher_boundary(self) -> None:
        r = self.audit()
        self.assertEqual(r["research_available_records"], 17)
        self.assertEqual(set(r["per_currency"]), set(CURRENCIES))

    def test_a_decision_before_first_release_has_no_available_research(self) -> None:
        r = self.audit("2026-08-01T00:00:00Z")
        self.assertEqual(r["research_available_records"], 0)

    def test_boj_one_second_before_and_at_exact_floor(self) -> None:
        a = self.audit("2026-10-30T03:01:59Z")
        b = self.audit("2026-10-30T03:02:00Z")
        key = "JPY_BOJ_OVERNIGHT_GUIDELINE_2026_10"
        self.assertFalse(a["sources"][key]["research_by_publisher_boundary"])
        self.assertTrue(b["sources"][key]["research_by_publisher_boundary"])

    def test_eur_flash_not_available_until_conservative_floor(self) -> None:
        a = self.audit("2026-11-04T23:59:59Z")
        b = self.audit("2026-11-05T00:00:00Z")
        self.assertFalse(a["sources"]["EUR_HICP_2026_10_FLASH"]["research_by_publisher_boundary"])
        self.assertTrue(b["sources"]["EUR_HICP_2026_10_FLASH"]["research_by_publisher_boundary"])

    def test_no_numeric_value_or_strength_in_source_output(self) -> None:
        for r in self.audit()["sources"].values():
            self.assertNotIn("value_percent", r)
            self.assertNotIn("strength", r)
            self.assertNotIn("score", r)

    def test_unattested_cannot_feed_backtest_or_produce_bias(self) -> None:
        r = self.audit()
        self.assertEqual(r["independently_attested_historical_vintages"], 0)
        self.assertEqual(r["fully_certified_currencies"], 0)
        self.assertEqual(r["backtest_ready_pairs"], 0)
        self.assertFalse(r["historical_backtest_approved"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["probability"])
        self.assertFalse(r["trade_authorized"])

    def test_d1_and_w1_are_both_research_only(self) -> None:
        d, w = self.audit(horizon="D1"), self.audit(horizon="W1")
        self.assertEqual(d["sources"], w["sources"])
        self.assertFalse(d["historical_backtest_approved"] or w["historical_backtest_approved"])

    def test_invalid_horizon_blocks(self) -> None:
        r = self.audit(horizon="M15")
        self.assertEqual(r["state"], "LAB_EVIDENCE_AUDIT_BLOCKED")

    def test_naive_datetime_blocks(self) -> None:
        r = inspect_g8_publication_evidence_lab(
            decision_at_utc=datetime(2026, 11, 8), horizon="D1")
        self.assertEqual(r["state"], "LAB_EVIDENCE_AUDIT_BLOCKED")

    def test_microseconds_block(self) -> None:
        r = inspect_g8_publication_evidence_lab(
            decision_at_utc=at("2026-11-08T12:00:00Z").replace(microsecond=1), horizon="D1")
        self.assertEqual(r["state"], "LAB_EVIDENCE_AUDIT_BLOCKED")

    def test_aware_offset_normalized(self) -> None:
        a = self.audit("2026-11-08T12:00:00Z")
        b = inspect_g8_publication_evidence_lab(decision_at_utc=datetime(
            2026, 11, 8, 8, tzinfo=timezone(timedelta(hours=-4))), horizon="D1")
        self.assertEqual(a, b)

    def test_no_network_cost_or_worker(self) -> None:
        r = self.audit()
        self.assertEqual(r["http_requests"], 0)
        self.assertEqual(r["new_cost_brl"], 0)
        self.assertFalse(r["worker_enabled"] or r["scheduler_enabled"])


if __name__ == "__main__":
    unittest.main()
