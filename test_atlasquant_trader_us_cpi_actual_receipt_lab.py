"""Synthetic offline US October CPI post-release provenance fence tests."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from atlasquant_trader_us_cpi_actual_receipt_lab import (
    ClaimedActualDocument, inspect_us_oct_cpi_actual_receipt_lab as inspect,
)
from atlasquant_trader_us_cpi_source_custody_lab import (
    CONSENSUS_ID, METRIC, OFFICIAL_PREVIOUS_PUBLICATION_CLAIM,
    OFFICIAL_PREVIOUS_URL, PREVIOUS_ID, RELEASE,
    build_us_cpi_source_receipt_lab,
)
from atlasquant_trader_us_oct2026_cpi_metric_availability_consensus_lab import REUTERS_URL

UTC = timezone.utc
CUTOFF = datetime(2026, 11, 9, 13, tzinfo=UTC)
BEFORE = datetime(2026, 11, 9, 14, tzinfo=UTC)
AFTER = RELEASE + timedelta(hours=1)
START = datetime(2026, 11, 9, 12, tzinfo=UTC)
END = START + timedelta(seconds=10)
BODY = (b"<html><body>Consumer Price Index - October 2026 "
        b"SYNTHETIC FIXTURE NOT A REAL BLS RELEASE " + b"x" * 128 + b"</body></html>")


def iso(v):
    return v.strftime("%Y-%m-%dT%H:%M:%SZ")


def sources():
    p = build_us_cpi_source_receipt_lab(
        PREVIOUS_ID, b"<html>SIMULATED PRIOR BLS</html>",
        source_url=OFFICIAL_PREVIOUS_URL,
        published_at_claim_utc=OFFICIAL_PREVIOUS_PUBLICATION_CLAIM,
        started_at_claim_utc=iso(START), finished_at_claim_utc=iso(END),
    )
    c = build_us_cpi_source_receipt_lab(
        CONSENSUS_ID, b"<html>SIMULATED ANALYST CONSENSUS</html>",
        source_url=REUTERS_URL,
        published_at_claim_utc="2026-11-06T23:59:59Z",
        started_at_claim_utc=iso(START), finished_at_claim_utc=iso(END),
    )
    return p, c


def actual_document():
    return ClaimedActualDocument(
        source_url="https://www.bls.gov/news.release/cpi.htm",
        response_status=200, content_type="text/html", body=BODY,
        body_sha256=sha256(BODY).hexdigest(),
        started_at=RELEASE + timedelta(seconds=10),
        finished_at=RELEASE + timedelta(seconds=20),
        claimed_first_published_at=RELEASE,
        reference_month="2026-10", metric=METRIC,
        extracted_actual_mom_percent_claim="0.4",
    )


class ActualCpiFenceTests(unittest.TestCase):
    def case(self, candidate=None, *, now=AFTER, cutoff=CUTOFF,
             prior=None, consensus=None):
        good_prior, good_consensus = sources()
        return inspect(candidate=candidate,
                       previous_receipt=good_prior if prior is None else prior,
                       consensus_receipt=good_consensus if consensus is None else consensus,
                       forecast_cutoff_utc=cutoff, as_of_utc=now)

    def no_live(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["official_actual_verified"])
        self.assertIsNone(result["actual_minus_pre_release_consensus"])
        self.assertIsNone(result["pre_event_forecast_score"])
        self.assertIsNone(result["market_reaction_probability"])
        self.assertIsNone(result["fx_bias"])
        self.assertIsNone(result["index_bias"])
        self.assertFalse(result["source_publisher_independently_attested"])
        self.assertFalse(result["first_publication_clock_independently_attested"])
        self.assertFalse(result["value_extracted_from_original_independently_verified"])
        self.assertFalse(result["prerelease_consensus_methodology_verified"])
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["live_alert_allowed"])
        self.assertFalse(result["worker_enabled"])
        self.assertFalse(result["scheduler_enabled"])
        self.assertEqual((result["http_requests"], result["file_writes"],
                          result["new_cost_brl"]), (0, 0, 0))

    def test_real_calendar_before_release_has_no_october_actual(self):
        result = self.case(now=BEFORE)
        self.assertEqual(result["state"], "LAB_WAIT_SCHEDULED_CPI_RELEASE")
        self.assertTrue(result["pre_event_sources_self_consistent_only"])
        self.assertFalse(result["post_release_body_self_consistent_only"])
        self.no_live(result)

    def test_earlier_research_clock_rejects_future_candidate(self):
        result = self.case(actual_document(), now=BEFORE)
        self.assertEqual(result["reason"], "ACTUAL_DOCUMENT_MUST_NOT_EXIST_BEFORE_SCHEDULED_RELEASE")
        self.no_live(result)

    def test_after_release_without_captured_actual_stays_waiting(self):
        result = self.case()
        self.assertEqual(result["state"], "LAB_WAIT_OFFICIAL_CPI_ACTUAL_DOCUMENT")
        self.assertIsNone(result["actual_documentary_claim_unattested"])
        self.no_live(result)

    def test_synthetic_actual_hash_match_is_not_bls_verification(self):
        result = self.case(actual_document())
        self.assertEqual(result["state"], "LAB_POST_RELEASE_RAW_CPI_CANDIDATE_UNATTESTED")
        self.assertTrue(result["pre_event_sources_self_consistent_only"])
        self.assertTrue(result["post_release_body_self_consistent_only"])
        self.assertEqual(result["actual_documentary_claim_unattested"], "0.4")
        self.assertEqual(result["actual_body_sha256"], sha256(BODY).hexdigest())
        self.no_live(result)

    def test_tampered_body_cannot_reuse_hash(self):
        bad = replace(actual_document(), body=BODY + b"tampered")
        result = self.case(bad)
        self.assertEqual(result["state"], "LAB_CPI_ACTUAL_BLOCKED")
        self.no_live(result)

    def test_wrong_source_url_cannot_serve_as_october_actual(self):
        bad = replace(actual_document(), source_url=OFFICIAL_PREVIOUS_URL)
        self.assertEqual(self.case(bad)["state"], "LAB_CPI_ACTUAL_BLOCKED")

    def test_september_body_cannot_be_claimed_as_october_even_with_matching_hash(self):
        raw = BODY.replace(b"October 2026", b"September 2026")
        bad = replace(actual_document(), body=raw, body_sha256=sha256(raw).hexdigest())
        self.assertEqual(self.case(bad)["state"], "LAB_CPI_ACTUAL_BLOCKED")

    def test_future_capture_not_visible_at_earlier_asof(self):
        bad = replace(actual_document(), finished_at=AFTER + timedelta(seconds=1))
        self.assertEqual(self.case(bad)["state"], "LAB_CPI_ACTUAL_BLOCKED")

    def test_captured_or_declared_published_before_release_blocked(self):
        for mutation in ({"started_at": RELEASE - timedelta(seconds=1)},
                         {"claimed_first_published_at": RELEASE - timedelta(seconds=1)}):
            with self.subTest(mutation=mutation):
                self.assertEqual(self.case(replace(actual_document(), **mutation))["state"],
                                 "LAB_CPI_ACTUAL_BLOCKED")

    def test_data_unit_and_period_cannot_switch_to_yoy_or_september(self):
        for mutation in ({"metric": "CPI_U_HEADLINE_YOY_UNADJUSTED"},
                         {"reference_month": "2026-09"},
                         {"reference_month": "2026-11"}):
            with self.subTest(mutation=mutation):
                self.assertEqual(self.case(replace(actual_document(), **mutation))["state"],
                                 "LAB_CPI_ACTUAL_BLOCKED")

    def test_bad_mime_http_status_and_clock_span_blocked(self):
        for mutation in ({"content_type": "application/json"},
                         {"response_status": 404},
                         {"response_status": True},
                         {"finished_at": RELEASE + timedelta(minutes=5)}):
            with self.subTest(mutation=mutation):
                self.assertEqual(self.case(replace(actual_document(), **mutation))["state"],
                                 "LAB_CPI_ACTUAL_BLOCKED")

    def test_invalid_or_out_of_range_numeric_claim_not_promoted(self):
        for claim in ("NaN", "Infinity", "500", "-101", "not_a_number", True):
            with self.subTest(claim=claim):
                self.assertEqual(self.case(replace(actual_document(),
                           extracted_actual_mom_percent_claim=claim))["state"],
                           "LAB_CPI_ACTUAL_BLOCKED")

    def test_missing_numeric_claim_preserves_raw_but_no_official_actual(self):
        result = self.case(replace(actual_document(), extracted_actual_mom_percent_claim=None))
        self.assertEqual(result["state"], "LAB_POST_RELEASE_RAW_CPI_CANDIDATE_UNATTESTED")
        self.assertIsNone(result["actual_documentary_claim_unattested"])
        self.no_live(result)

    def test_invalid_forecast_cutoff_postrelease_does_not_retroactively_fit(self):
        result = self.case(actual_document(), cutoff=RELEASE + timedelta(minutes=1))
        self.assertEqual(result["reason"], "FORECAST_CUTOFF_NOT_A_VALID_PRERELEASE_INSTANT")
        self.no_live(result)

    def test_pre_release_consensus_not_previously_captured_is_not_verified(self):
        bad_prior, good_consensus = sources()
        late_prior = dict(bad_prior, collector_finished_at_claim_utc=iso(
            CUTOFF + timedelta(seconds=1)))
        result = self.case(actual_document(), prior=late_prior, consensus=good_consensus)
        self.assertFalse(result["pre_event_sources_self_consistent_only"])
        self.no_live(result)

    def test_no_verified_reuters_poll_even_with_raw_receipts(self):
        result = self.case(actual_document())
        self.assertFalse(result["prerelease_consensus_methodology_verified"])
        self.assertIsNone(result["actual_minus_pre_release_consensus"])
        self.no_live(result)

    def test_research_not_visible_before_nov9(self):
        result = self.case(now=datetime(2026, 11, 8, 23, tzinfo=UTC))
        self.assertEqual(result["reason"], "RESEARCH_NOT_VISIBLE_BEFORE_NOV9")
        self.no_live(result)


if __name__ == "__main__":
    unittest.main()
