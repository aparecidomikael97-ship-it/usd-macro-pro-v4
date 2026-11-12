"""Synthetic receipts only: never request BLS/analyst URLs or trade."""
import unittest
from datetime import datetime, timedelta, timezone

from atlasquant_trader_us_cpi_source_custody_lab import (
    CONSENSUS_ID, MAX_BODY_BYTES, OFFICIAL_PREVIOUS_PUBLICATION_CLAIM,
    OFFICIAL_PREVIOUS_URL, PREVIOUS_ID,
    build_us_cpi_source_receipt_lab as build,
    inspect_us_cpi_source_receipt_lab as inspect,
    inspect_us_cpi_pre_event_bundle_lab as inspect_bundle,
)


UTC = timezone.utc
OBSERVED = datetime(2026, 11, 9, 12, 30, tzinfo=UTC)
CUTOFF = datetime(2026, 11, 9, 12, 15, tzinfo=UTC)
START = "2026-11-09T12:00:00Z"
FINISH = "2026-11-09T12:00:02Z"
POLL_URL = "https://www.reuters.com/world/us/synthetic-lab-poll-cpi/"
SYNTHETIC = b"SYNTHETIC FIXTURE - NEVER PUBLICLY CAPTURED NEWS SOURCE"


class USCPISourceCustodyLabTests(unittest.TestCase):
    def one(self, source_id=PREVIOUS_ID, **overrides):
        kwargs = dict(
            source_url=OFFICIAL_PREVIOUS_URL if source_id == PREVIOUS_ID else POLL_URL,
            published_at_claim_utc=(OFFICIAL_PREVIOUS_PUBLICATION_CLAIM if source_id == PREVIOUS_ID
                                    else "2026-11-09T11:50:00Z"),
            started_at_claim_utc=START,
            finished_at_claim_utc=FINISH,
        )
        kwargs.update({k: v for k, v in overrides.items() if k != "body"})
        return build(source_id, overrides.get("body", SYNTHETIC), **kwargs)

    def check(self, receipt, as_of=OBSERVED, cutoff=CUTOFF):
        return inspect(receipt, as_of_utc=as_of, forecast_cutoff_utc=cutoff)

    def assert_nonoperational(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertFalse(result["ready_for_news_nowcast"])
        self.assertFalse(result["historical_pit_eligible"])
        self.assertFalse(result["publisher_origin_independently_verified"])
        self.assertFalse(result["capture_clock_independently_witnessed"])
        self.assertFalse(result["source_publication_time_independently_witnessed"])
        self.assertFalse(result["event_poll_value_and_metric_parsed_from_original"])
        self.assertFalse(result["ready_for_fx_bias"])
        self.assertIsNone(result["probabilities"])
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["worker_enabled"])
        self.assertFalse(result["scheduler_enabled"])
        self.assertEqual((result["network_requests"], result["file_writes"], result["new_cost_brl"]),
                         (0, 0, 0))

    def test_caller_bytes_hash_consistent_is_explicitly_unattested(self):
        result = self.check(self.one())
        self.assertEqual(result["state"], "LAB_BYTES_CONSISTENT_CLAIMED_PRERELEASE_CAPTURE_UNATTESTED")
        self.assertTrue(result["body_bytes_self_consistent"])
        self.assert_nonoperational(result)

    def test_two_claimed_sources_never_unlock_nowcast(self):
        result = inspect_bundle(self.one(), self.one(CONSENSUS_ID),
                                as_of_utc=OBSERVED, forecast_cutoff_utc=CUTOFF)
        self.assertEqual(result["state"], "LAB_TWO_SOURCE_DOCUMENTARY_CANDIDATE_UNATTESTED")
        self.assert_nonoperational(result)

    def test_missing_poll_blocks_full_bundle(self):
        result = inspect_bundle(self.one(), None, as_of_utc=OBSERVED,
                                forecast_cutoff_utc=CUTOFF)
        self.assertEqual(result["state"], "LAB_SOURCE_CUSTODY_BLOCKED")
        self.assertIn(CONSENSUS_ID, result["reason"])
        self.assert_nonoperational(result)

    def test_duplicate_bls_document_cannot_impersonate_analyst_poll(self):
        result = inspect_bundle(self.one(), self.one(), as_of_utc=OBSERVED,
                                forecast_cutoff_utc=CUTOFF)
        self.assertEqual(result["reason"], "MISLABELED_OR_REUSED_NEWS_SOURCE")
        self.assert_nonoperational(result)

    def test_future_capture_cannot_be_backfilled_into_earlier_forecast(self):
        receipt = self.one()
        early = self.check(receipt, cutoff=datetime(2026, 11, 9, 11, tzinfo=UTC))
        self.assertEqual(early["reason"], "CAPTURE_FINISHED_AFTER_FORECAST_CUTOFF")
        self.assert_nonoperational(early)

    def test_research_created_nov9_is_not_historical_oct14_evidence(self):
        receipt = self.one()
        prior = self.check(receipt, as_of=datetime(2026, 10, 14, 15, tzinfo=UTC),
                           cutoff=datetime(2026, 10, 14, 14, tzinfo=UTC))
        self.assertEqual(prior["reason"], "RESEARCH_NOT_VISIBLE_BEFORE_NOV9")
        self.assert_nonoperational(prior)

    def test_capture_not_observed_at_inspection_time_fails(self):
        result = self.check(self.one(),
                            as_of=datetime(2026, 11, 9, 12, 0, 1, tzinfo=UTC),
                            cutoff=datetime(2026, 11, 9, 12, 0, 1, tzinfo=UTC))
        self.assertEqual(result["reason"], "CAPTURE_FINISHED_AFTER_INSPECTION_ASOF")

    def test_no_forecast_at_or_after_news_release(self):
        result = self.check(self.one(),
                            as_of=datetime(2026, 11, 11, tzinfo=UTC),
                            cutoff=datetime(2026, 11, 10, 13, 30, tzinfo=UTC))
        self.assertEqual(result["reason"], "FORECAST_CUTOFF_NOT_AN_OBSERVED_PRERELEASE_INSTANT")

    def test_no_pretend_forecast_with_future_cutoff(self):
        future = OBSERVED + timedelta(hours=1)
        self.assertEqual(self.check(self.one(), cutoff=future)["state"], "LAB_SOURCE_CUSTODY_BLOCKED")

    def test_original_byte_or_metadata_tampering_breaks_digest(self):
        receipt = self.one()
        modified = (
            {**receipt, "captured_body_base64": "QQ=="},
            {**receipt, "collector_finished_at_claim_utc": "2026-11-09T12:00:03Z"},
            {**receipt, "captured_body_sha256": "f" * 64},
            {**receipt, "metric": "CPI_U_HEADLINE_YOY_PERCENT_CHANGE"},
            {**receipt, "receipt_sha256": "a" * 64},
        )
        for fake in modified:
            with self.subTest(kind=set(fake.items()) - set(receipt.items())):
                self.assertEqual(self.check(fake)["state"], "LAB_SOURCE_CUSTODY_BLOCKED")

    def test_wrong_month_kind_and_renamed_source_rejected(self):
        receipt = self.one()
        for key, value in (("reference_month", "2026-08"),
                           ("source_kind_claim", "MODEL_NOWCAST"),
                           ("source_id", CONSENSUS_ID)):
            with self.subTest(key=key):
                self.assertEqual(self.check({**receipt, key: value})["state"],
                                 "LAB_SOURCE_CUSTODY_BLOCKED")

    def test_spoofed_content_type_status_schema_boolean_rejected(self):
        receipt = self.one()
        for key, value in (("http_status_claim", True), ("http_status_claim", 404),
                           ("source_content_type_claim", "text/plain"),
                           ("caller_supplied_unattested", False), ("schema", "other")):
            with self.subTest(key=key, value=value):
                self.assertEqual(self.check({**receipt, key: value})["state"],
                                 "LAB_SOURCE_CUSTODY_BLOCKED")

    def test_reject_wrong_official_url_and_malicious_poll_domain(self):
        self.assertEqual(self.one(source_url="https://bls.gov.evil.example/foo")["state"],
                         "LAB_SOURCE_CUSTODY_BLOCKED")
        for url in ("http://example.com/poll", "https://localhost/poll",
                    "https://fake.local/poll", "https://u:p@www.reuters.com/poll",
                    "https://www.reuters.com/poll#fragment", "https://www.bls.gov/poll"):
            with self.subTest(url=url):
                self.assertEqual(self.one(CONSENSUS_ID, source_url=url)["state"],
                                 "LAB_SOURCE_CUSTODY_BLOCKED")

    def test_wrong_or_late_publication_claim_rejected(self):
        self.assertEqual(self.one(published_at_claim_utc="2026-10-14T12:31:00Z")["state"],
                         "LAB_SOURCE_CUSTODY_BLOCKED")
        self.assertEqual(self.one(CONSENSUS_ID,
                                  published_at_claim_utc="2026-11-10T14:00:00Z")["state"],
                         "LAB_SOURCE_CUSTODY_BLOCKED")

    def test_poll_published_before_nov9_but_observed_nov9_is_still_a_candidate(self):
        receipt = self.one(CONSENSUS_ID, published_at_claim_utc="2026-11-06T16:00:00Z")
        result = self.check(receipt)
        self.assertEqual(result["state"],
                         "LAB_BYTES_CONSISTENT_CLAIMED_PRERELEASE_CAPTURE_UNATTESTED")
        self.assert_nonoperational(result)

    def test_non_string_source_id_and_wrong_type_fail_closed(self):
        self.assertEqual(self.one([PREVIOUS_ID])["state"], "LAB_SOURCE_CUSTODY_BLOCKED")
        self.assertEqual(self.check({**self.one(), "source_id": [PREVIOUS_ID]})["state"],
                         "LAB_SOURCE_CUSTODY_BLOCKED")

    def test_capture_clocks_must_be_utc_canonical_and_short(self):
        for start, finish in (("2026-11-09T12:00:00", FINISH),
                              ("2026-11-09T12:00:02Z", START),
                              (START, "2026-11-09T12:02:01Z"),
                              ("2026-10-14T15:00:00Z", "2026-10-14T15:00:02Z")):
            with self.subTest(start=start, finish=finish):
                self.assertEqual(self.one(started_at_claim_utc=start,
                                          finished_at_claim_utc=finish)["state"],
                                 "LAB_SOURCE_CUSTODY_BLOCKED")

    def test_no_bogus_empty_or_oversized_original_bytes(self):
        self.assertEqual(self.one(body=b"")["state"], "LAB_SOURCE_CUSTODY_BLOCKED")
        self.assertEqual(self.one(body=b"x" * (MAX_BODY_BYTES + 1))["state"],
                         "LAB_SOURCE_CUSTODY_BLOCKED")
        self.assertEqual(self.one(body="not bytes")["state"], "LAB_SOURCE_CUSTODY_BLOCKED")

    def test_both_clocks_must_be_timezone_aware(self):
        receipt = self.one()
        self.assertEqual(self.check(receipt, as_of=datetime(2026, 11, 9, 12, 30))["state"],
                         "LAB_SOURCE_CUSTODY_BLOCKED")
        self.assertEqual(self.check(receipt, cutoff=datetime(2026, 11, 9, 12, 15))["state"],
                         "LAB_SOURCE_CUSTODY_BLOCKED")

    def test_hash_cannot_be_mistaken_for_verified_economic_number(self):
        receipt = self.one(body=b"Completely fake CPI 0.6 and poll 0.3")
        result = self.check(receipt)
        self.assertTrue(result["body_bytes_self_consistent"])
        self.assertFalse(result["event_poll_value_and_metric_parsed_from_original"])
        self.assert_nonoperational(result)


if __name__ == "__main__":
    unittest.main()
