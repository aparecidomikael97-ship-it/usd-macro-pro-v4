"""Synthetic and optional archive-backed regression tests; no trading claims."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase, main, skipUnless
from unittest.mock import patch
import os

from atlasquant_cpi_archived_series_link_lab import inspect_archived_cpi_series_link_lab as inspect
from atlasquant_cpi_series_contract_lab import SCHEMA as SERIES_SCHEMA
from atlasquant_audnzd_cpi_archive_receipt_lab import AUD_SNAPSHOT_SHA256, NZD_SNAPSHOT_SHA256

ARCHIVE_DIR = Path(os.environ.get("ATLASQUANT_CPI_ARCHIVE_DIRECTORY", Path(__file__).parent))
AUD = ARCHIVE_DIR / "AUD_ABS_CPI_2026Q3_Table17.xlsx"
NZD = ARCHIVE_DIR / "NZD_CPI_2026Q3_StatsNZ_summary.pdf"
NOW = datetime(2026, 11, 7, 16, tzinfo=timezone.utc)


def sample():
    return {
        "schema": SERIES_SCHEMA,
        "pair": "AUD/NZD",
        "decision_at_utc": "2026-11-07T15:00:00Z",
        "records": [
            {"currency": "AUD", "atlasquant_series_key": "AUD_QUARTERLY_CPI_YOY",
             "frequency": "QUARTERLY", "observation_period": "2026-09",
             "value": "3.9", "published_at_utc": "2026-10-28T12:00:00Z",
             "captured_at_utc": "2026-10-29T10:00:00Z",
             "source_sha256": AUD_SNAPSHOT_SHA256,
             "source_url": "https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/sep-2026/6401017.xlsx"},
            {"currency": "NZD", "atlasquant_series_key": "NZD_QUARTERLY_CPI_YOY",
             "frequency": "QUARTERLY", "observation_period": "2026-09",
             "value": "3.7", "published_at_utc": "2026-10-22T12:00:00Z",
             "captured_at_utc": "2026-10-23T10:00:00Z",
             "source_sha256": NZD_SNAPSHOT_SHA256,
             "source_url": "https://www.stats.govt.nz/indicators/consumers-price-index-cpi/"},
        ],
    }


def synthetic_archive_receipt():
    return {
        "state": "LAB_TWO_DOCUMENT_VALUES_MATCH_ARCHIVED_BYTES_UNATTESTED",
        "reason": "DOCUMENT_BYTES_MATCH_ARCHIVE_NOT_HISTORICAL_AVAILABILITY",
        "source_receipts": {
            "AUD": {"archive_sha256": AUD_SNAPSHOT_SHA256,
                    "published_release_date_claim": "2026-10-28"},
            "NZD": {"archive_sha256": NZD_SNAPSHOT_SHA256,
                    "published_release_date_claim": "2026-10-22"},
        },
        "inflation_comparison": {
            "AUD_annual_yoy_pct_derived_from_rounded_index": "3.9",
            "NZD_annual_yoy_pct_publisher_reported": "3.7",
        },
    }


def test_audit(payload=None, *, data=None, asof=NOW):
    payload = sample() if payload is None else payload
    with patch("atlasquant_cpi_archived_series_link_lab.inspect_archived_audnzd_cpi_lab",
               return_value=synthetic_archive_receipt() if data is None else data):
        return inspect(aud_xlsx=b"synthetic", nzd_pdf=b"synthetic",
                       series_payload=payload, as_of_utc=asof)


class CPIArchivedSeriesLinkTests(TestCase):
    def assert_safe(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        for k in ("trade_authorized", "can_feed_live_radar", "automatic_alert_enabled",
                  "historical_point_in_time_verified", "issuer_origin_independently_authenticated",
                  "release_instant_independently_attested", "capture_instant_independently_attested",
                  "methodology_equivalent_proven", "out_of_sample_accuracy_verified"):
            self.assertIs(r[k], False, k)
        self.assertIsNone(r["probability_of_directional_move"])
        self.assertIsNone(r["score_0_to_10"])
        self.assertIsNone(r["broker_command"])
        self.assertEqual(r["new_cost_brl"], 0)

    def test_synthetic_claims_match_still_no_market_signal(self):
        r = test_audit()
        self.assertEqual(r["state"], "LAB_ARCHIVED_CPI_VALUES_LINKED_UNATTESTED")
        self.assertTrue(r["archive_values_linked_to_series"])
        self.assertEqual(r["research_comparison"]["difference_pp_descriptive_only"], "0.2")
        self.assertFalse(r["research_comparison"]["may_infer_fx_direction"])
        self.assert_safe(r)

    def test_wrong_aud_value_rejected(self):
        p = sample(); p["records"][0]["value"] = "4.3"
        self.assertEqual(test_audit(p)["reason"], "AUD:ECONOMIC_VALUE_NOT_LINKED")

    def test_wrong_nzd_value_rejected(self):
        p = sample(); p["records"][1]["value"] = "3.8"
        self.assertEqual(test_audit(p)["reason"], "NZD:ECONOMIC_VALUE_NOT_LINKED")

    def test_numeric_equivalent_format_still_matches(self):
        p = sample(); p["records"][1]["value"] = "3.70"
        self.assertEqual(test_audit(p)["state"], "LAB_ARCHIVED_CPI_VALUES_LINKED_UNATTESTED")

    def test_wrong_abs_hash_rejected(self):
        p = sample(); p["records"][0]["source_sha256"] = "a"*64
        self.assertEqual(test_audit(p)["reason"], "AUD:ARCHIVE_HASH_NOT_LINKED")

    def test_wrong_nzd_hash_rejected(self):
        p = sample(); p["records"][1]["source_sha256"] = "b"*64
        self.assertEqual(test_audit(p)["reason"], "NZD:ARCHIVE_HASH_NOT_LINKED")

    def test_wrong_economic_period_rejected(self):
        p = sample(); p["records"][0]["observation_period"] = "2026-06"
        self.assertEqual(test_audit(p)["reason"], "SERIES_GATE:CPI_PERIOD_OR_RELEASE_STALE")

    def test_older_quarter_during_allowed_freshness_still_fails_archive_link(self):
        p = sample()
        p["decision_at_utc"] = "2026-10-29T15:00:00Z"
        p["records"][0]["observation_period"] = "2026-06"
        asof = datetime(2026, 10, 29, 16, tzinfo=timezone.utc)
        self.assertEqual(test_audit(p, asof=asof)["reason"],
                         "AUD:WRONG_SERIES_OR_REFERENCE_PERIOD")

    def test_monthly_substitution_rejected(self):
        p = sample()
        p["records"][0]["atlasquant_series_key"] = "AUD_MONTHLY_CPI_YOY"
        p["records"][0]["frequency"] = "MONTHLY"
        self.assertTrue(test_audit(p)["reason"].startswith("SERIES_GATE:"))

    def test_wrong_released_date_claim_rejected(self):
        p = sample(); p["records"][0]["published_at_utc"] = "2026-10-29T12:00:00Z"
        p["records"][0]["captured_at_utc"] = "2026-10-29T14:00:00Z"
        self.assertEqual(test_audit(p)["reason"], "AUD:RELEASE_DATE_CLAIM_MISMATCH")

    def test_wrong_capture_chronology_rejected(self):
        p = sample(); p["records"][0]["captured_at_utc"] = "2026-10-28T11:59:59Z"
        self.assertEqual(test_audit(p)["reason"], "SERIES_GATE:LOOKAHEAD_OR_CHRONOLOGY")

    def test_future_capture_rejected(self):
        p = sample(); p["records"][0]["captured_at_utc"] = "2026-11-07T15:00:01Z"
        self.assertEqual(test_audit(p)["reason"], "SERIES_GATE:LOOKAHEAD_OR_CHRONOLOGY")

    def test_before_research_floor_rejected(self):
        p = sample(); p["decision_at_utc"] = "2026-10-28T23:59:00Z"
        r = test_audit(p, asof=datetime(2026, 10, 28, 23, 59, tzinfo=timezone.utc))
        self.assertTrue(r["reason"].startswith("SERIES_GATE:") or r["reason"].startswith("ARCHIVE_GATE:"))
        self.assert_safe(r)

    def test_malformed_payload_rejected(self):
        r = test_audit({"schema": "wrong"})
        self.assertTrue(r["reason"].startswith("SERIES_GATE:"))
        self.assert_safe(r)

    def test_archived_document_gate_denial_blocks(self):
        failure = {"state": "LAB_BLOCKED", "reason": "ARCHIVE_SNAPSHOT_DIGEST_MISMATCH"}
        r = test_audit(data=failure)
        self.assertEqual(r["reason"], "ARCHIVE_GATE:ARCHIVE_SNAPSHOT_DIGEST_MISMATCH")
        self.assert_safe(r)

    def test_malformed_positive_archive_receipt_fails_closed(self):
        malformed = {"state": "LAB_TWO_DOCUMENT_VALUES_MATCH_ARCHIVED_BYTES_UNATTESTED"}
        r = test_audit(data=malformed)
        self.assertEqual(r["reason"], "ARCHIVE_RECEIPT_SHAPE_OR_VALUE_INVALID")
        self.assert_safe(r)

    def test_no_independent_attestation_despite_matched_sources(self):
        r = test_audit()
        self.assertFalse(r["release_instant_independently_attested"])
        self.assertFalse(r["historical_point_in_time_verified"])
        self.assertFalse(r["out_of_sample_accuracy_verified"])
        self.assert_safe(r)

    @skipUnless(AUD.is_file() and NZD.is_file(), "Real archived documents absent in CI")
    def test_real_2026_q3_documents_link_to_claimed_series_without_signal(self):
        r = inspect(aud_xlsx=AUD.read_bytes(), nzd_pdf=NZD.read_bytes(),
                    series_payload=sample(), as_of_utc=NOW)
        self.assertEqual(r["state"], "LAB_ARCHIVED_CPI_VALUES_LINKED_UNATTESTED")
        self.assertTrue(r["archive_byte_integrity_verified"])
        self.assert_safe(r)

    @skipUnless(AUD.is_file() and NZD.is_file(), "Real archived documents absent in CI")
    def test_modified_aud_archive_blocks_even_with_correct_metadata(self):
        aud = bytearray(AUD.read_bytes()); aud[500] ^= 1
        r = inspect(aud_xlsx=bytes(aud), nzd_pdf=NZD.read_bytes(),
                    series_payload=sample(), as_of_utc=NOW)
        self.assertTrue(r["reason"].startswith("ARCHIVE_GATE:"))
        self.assert_safe(r)

    @skipUnless(AUD.is_file() and NZD.is_file(), "Real archived documents absent in CI")
    def test_modified_nzd_archive_blocks_even_with_correct_metadata(self):
        nzd = bytearray(NZD.read_bytes()); nzd[500] ^= 1
        r = inspect(aud_xlsx=AUD.read_bytes(), nzd_pdf=bytes(nzd),
                    series_payload=sample(), as_of_utc=NOW)
        self.assertTrue(r["reason"].startswith("ARCHIVE_GATE:"))
        self.assert_safe(r)


if __name__ == "__main__":
    main(verbosity=2)
