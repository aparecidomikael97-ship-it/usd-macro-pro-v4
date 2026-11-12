"""Documentary-research-only CPI preview; receipts are synthetic bytes."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from atlasquant_trader_us_cpi_pre_event_brief_lab import (
    inspect_us_cpi_oct2026_pre_event_brief_lab as brief,
)
from atlasquant_trader_us_cpi_source_custody_lab import (
    CONSENSUS_ID, OFFICIAL_PREVIOUS_PUBLICATION_CLAIM, OFFICIAL_PREVIOUS_URL,
    PREVIOUS_ID, build_us_cpi_source_receipt_lab as build,
)


ROOT = Path(__file__).resolve().parent
CASEBOOK = (ROOT / "docs" / "continuidade" /
            "TRADER_US_CPI_SEPAUG2026_PREVIOUS_MOM_RESEARCH_LAB_20261108.json").read_bytes()
UTC = timezone.utc
OBSERVED = datetime(2026, 11, 9, 12, 30, tzinfo=UTC)
POLL_URL = "https://www.reuters.com/business/take-five/global-markets-themes-graphic-2026-11-06/"


def make_receipt(source_id, start="2026-11-09T12:00:00Z", finish="2026-11-09T12:00:02Z"):
    return build(
        source_id, b"Synthetic test fixture, not actual news source content",
        source_url=OFFICIAL_PREVIOUS_URL if source_id == PREVIOUS_ID else POLL_URL,
        published_at_claim_utc=(OFFICIAL_PREVIOUS_PUBLICATION_CLAIM
                                if source_id == PREVIOUS_ID else "2026-11-06T08:30:00Z"),
        started_at_claim_utc=start, finished_at_claim_utc=finish,
    )


class USCPIPreEventBriefTests(unittest.TestCase):
    def inspect(self, when=OBSERVED, raw=CASEBOOK, **kwargs):
        return brief(previous_casebook_raw=raw, as_of_utc=when, **kwargs)

    def assert_never_signal(self, result):
        self.assertIsNone(result["official_october_mom_actual"])
        self.assertIsNone(result["actual_minus_consensus_surprise"])
        self.assertIsNone(result["market_reaction_probability"])
        self.assertIsNone(result["forecast_value"])
        self.assertIsNone(result["directional_accuracy"])
        self.assertIsNone(result["fx_bias"])
        self.assertIsNone(result["index_bias"])
        self.assertFalse(result["source_document_origin_verified"])
        self.assertFalse(result["poll_exact_event_semantics_independently_audited"])
        self.assertFalse(result["point_in_time_conclusively_witnessed"])
        self.assertFalse(result["pre_event_operational_ready"])
        self.assertTrue(result["research_only"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["worker_enabled"])
        self.assertFalse(result["scheduler_enabled"])
        self.assertEqual((result["network_requests"], result["new_cost_brl"]), (0, 0))

    def test_0_3_reported_consensus_vs_0_6_previous_is_minus_0_3_pp(self):
        result = self.inspect()
        self.assertEqual(result["state"], "LAB_DOCUMENTARY_PRE_EVENT_EXPECTED_SLOWING_ONLY")
        self.assertEqual(result["previous_mom_sa_percent_documentary"], 0.6)
        self.assertEqual(result["reported_event_poll_mom_sa_percent_documentary"], 0.3)
        self.assertEqual(result["consensus_minus_previous_percentage_points_documentary"], -0.3)
        self.assertEqual(result["documentary_interpretation"],
                         "ANALYSTS_EXPECTED_SLOWER_MONTHLY_CPI_VS_SEPTEMBER")
        self.assert_never_signal(result)

    def test_no_research_backfill_before_nov9(self):
        result = self.inspect(datetime(2026, 11, 8, 23, 59, tzinfo=UTC))
        self.assertEqual(result["reason"], "RESEARCH_NOT_VISIBLE_BEFORE_NOV9_UTC")
        self.assertIsNone(result["reported_event_poll_mom_sa_percent_documentary"])
        self.assert_never_signal(result)

    def test_bad_or_modified_research_casebook_cannot_feed_documentary_brief(self):
        for raw in (None, CASEBOOK + b" ", CASEBOOK.replace(b'"0.6"', b'"0.4"')):
            with self.subTest(kind=str(type(raw))):
                result = self.inspect(raw=raw)
                self.assertEqual(result["state"], "LAB_BRIEF_BLOCKED")
                self.assertIsNone(result["previous_mom_sa_percent_documentary"])
                self.assert_never_signal(result)

    def test_after_release_without_authenticated_actual_is_not_live_prediction(self):
        result = self.inspect(datetime(2026, 11, 10, 13, 30, tzinfo=UTC))
        self.assertEqual(result["state"], "LAB_RELEASE_CLOCK_PASSED_WITHOUT_AUTHENTICATED_ACTUAL")
        self.assertEqual(result["documentary_interpretation"],
                         "PAST_POLL_NOT_A_CURRENT_OR_VERIFIED_ACTUAL")
        self.assert_never_signal(result)

    def test_timezone_aware_equivalence_and_naive_rejection(self):
        m4 = timezone(timedelta(hours=-4))
        self.assertEqual(self.inspect(OBSERVED.astimezone(m4)), self.inspect())
        self.assertEqual(self.inspect(datetime(2026, 11, 9, 12, 30))["state"], "LAB_BRIEF_BLOCKED")
        self.assert_never_signal(self.inspect(datetime(2026, 11, 9, 12, 30)))

    def test_synthetic_source_receipts_do_not_upgrade_origin_claim(self):
        result = self.inspect(previous_source_receipt=make_receipt(PREVIOUS_ID),
                              consensus_source_receipt=make_receipt(CONSENSUS_ID))
        self.assertTrue(result["source_bytes_self_consistent_unattested"])
        self.assertEqual(result["source_evidence_state"],
                         "LAB_TWO_SOURCE_DOCUMENTARY_CANDIDATE_UNATTESTED")
        self.assert_never_signal(result)

    def test_missing_consensus_bytes_cannot_make_source_bundle_complete(self):
        result = self.inspect(previous_source_receipt=make_receipt(PREVIOUS_ID))
        self.assertFalse(result["source_bytes_self_consistent_unattested"])
        self.assertEqual(result["source_evidence_state"], "LAB_SOURCE_CUSTODY_BLOCKED")
        self.assert_never_signal(result)

    def test_poll_captured_after_forecast_is_not_pit_candidate(self):
        late = make_receipt(CONSENSUS_ID, start="2026-11-09T12:31:00Z",
                            finish="2026-11-09T12:31:02Z")
        result = self.inspect(previous_source_receipt=make_receipt(PREVIOUS_ID),
                              consensus_source_receipt=late)
        self.assertFalse(result["source_bytes_self_consistent_unattested"])
        self.assert_never_signal(result)

    def test_future_capture_with_future_asof_does_not_imply_first_seen_at_release(self):
        later = datetime(2026, 11, 10, 12, tzinfo=UTC)
        result = self.inspect(later)
        self.assertFalse(result["point_in_time_conclusively_witnessed"])
        self.assertEqual(result["state"], "LAB_DOCUMENTARY_PRE_EVENT_EXPECTED_SLOWING_ONLY")
        self.assert_never_signal(result)

    def test_source_urls_are_separate_and_not_a_prediction_service(self):
        result = self.inspect()
        self.assertEqual(result["bls_previous_source_url"],
                         "https://www.bls.gov/news.release/archives/cpi_10142026.htm")
        self.assertEqual(result["reuters_reported_poll_source_url"], POLL_URL)
        self.assert_never_signal(result)


if __name__ == "__main__":
    unittest.main()
