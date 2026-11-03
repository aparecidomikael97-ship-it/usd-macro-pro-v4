"""Offline contract tests: official G8 source leads do not prove real receipts."""
import copy
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import urlsplit
import unittest

from atlasquant_fx_universe import CURRENCIES
from atlasquant_trader_g8_official_source_receipt_lab import (
    SCHEMA, SOURCES, FAMILIES, MAX_TEXT_BYTES,
    official_g8_source_catalog_lab, inspect_claimed_macro_receipt_lab,
)

CUTOFF = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
AFTER = datetime(2026, 11, 2, 12, 1, tzinfo=timezone.utc)
TEXT = "LAB-only synthetic fake calendar excerpt. It is NOT an official download."


def sample():
    return {
        "state": "LAB_CALLER_SUPPLIED_TEXT", "source_id": "US_BLS_CPI",
        "event_id": "CPI_202611", "kind": "SCHEDULED",
        "event_at_utc": "2026-11-10T13:30:00Z",
        "published_at_utc": "2026-11-01T12:00:00Z",
        "captured_at_utc": "2026-11-01T12:05:00Z",
        "document_url": "https://www.bls.gov/schedule/2026/",
        "excerpt_utf8": TEXT,
        "claimed_sha256": sha256(TEXT.encode()).hexdigest(),
    }


def inspect(item):
    return inspect_claimed_macro_receipt_lab(
        item, forecast_issued_at=CUTOFF, evaluated_at=AFTER,
    )


class OfficialSourceReceiptLabTests(unittest.TestCase):
    def test_8x2_catalog_completeness(self):
        cat = official_g8_source_catalog_lab()
        self.assertEqual(cat["schema"], SCHEMA)
        self.assertEqual(cat["state"], "LAB_DOCUMENTATION_LEADS_ONLY")
        self.assertEqual(cat["currency_count"], 8)
        self.assertEqual(cat["family_count"], 2)
        self.assertEqual(cat["lead_count"], 16)
        self.assertEqual(set(cat["sources"]), set(SOURCES))
        self.assertEqual({v["currency"] for v in SOURCES.values()}, set(CURRENCIES))
        self.assertEqual({v["family"] for v in SOURCES.values()}, set(FAMILIES))
        self.assertEqual({(v["currency"], v["family"]) for v in SOURCES.values()},
                         {(c, f) for c in CURRENCIES for f in FAMILIES})

    def test_urls_have_https_exact_host_and_no_credentials(self):
        for item in SOURCES.values():
            url = urlsplit(item["documentation_url"])
            self.assertEqual(url.scheme, "https")
            self.assertEqual(url.hostname, item["hostname"])
            self.assertIsNone(url.username)
            self.assertIsNone(url.password)

    def test_catalog_does_not_claim_real_data_or_license(self):
        cat = official_g8_source_catalog_lab()
        for key in ("historical_payloads_downloaded", "original_receipt_attested",
                    "intraday_availability_attested", "commercial_redistribution_rights_verified",
                    "real_forex_bias_verified", "trade_authorized",
                    "worker_enabled", "scheduler_enabled"):
            self.assertFalse(cat[key], key)

    def test_claimed_future_schedule_quarantined(self):
        result = inspect(sample())
        self.assertEqual(result["state"], "LAB_OFFICIAL_RECEIPT_QUARANTINED_UNATTESTED")
        self.assertTrue(result["structural_asof_consistent"])
        self.assertEqual(result["receipt"]["currency"], "USD")
        self.assertEqual(result["receipt"]["family"], "INFLATION")
        self.assertEqual(result["receipt"]["content_sha256"], sample()["claimed_sha256"])
        self.assertEqual(len(result["receipt"]["record_sha256"]), 64)

    def test_past_release_context_quarantined(self):
        item = sample()
        item["kind"] = "RELEASED_CONTEXT"
        item["event_at_utc"] = "2026-10-20T12:30:00Z"
        item["published_at_utc"] = "2026-10-20T12:31:00Z"
        item["captured_at_utc"] = "2026-10-20T13:10:00Z"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_QUARANTINED_UNATTESTED")

    def test_future_published_time_rejected(self):
        item = sample()
        item["published_at_utc"] = "2026-11-02T12:01:00Z"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_future_claimed_capture_rejected(self):
        item = sample()
        item["captured_at_utc"] = "2026-11-02T12:01:00Z"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_scheduled_event_already_occurred_rejected(self):
        item = sample()
        item["event_at_utc"] = "2026-11-02T11:00:00Z"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_release_context_published_before_event_rejected(self):
        item = sample()
        item["kind"] = "RELEASED_CONTEXT"
        item["event_at_utc"] = "2026-11-01T13:00:00Z"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_http_rejected(self):
        item = sample()
        item["document_url"] = "http://www.bls.gov/schedule/2026/"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_lookalike_subdomain_rejected(self):
        item = sample()
        item["document_url"] = "https://www.bls.gov.evil.example/schedule/2026/"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_official_different_host_rejected(self):
        item = sample()
        item["document_url"] = "https://www.federalreserve.gov/newsevents/pressreleases/2026-press-fomc.htm"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_url_credentials_and_nonstandard_port_rejected(self):
        for url in ("https://u:p@www.bls.gov/schedule/2026/",
                    "https://www.bls.gov:444/schedule/2026/"):
            with self.subTest(url=url):
                item = sample()
                item["document_url"] = url
                self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_wrong_text_hash_rejected(self):
        item = sample()
        item["claimed_sha256"] = "0" * 64
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_hash_not_attestation_even_when_valid(self):
        result = inspect(sample())
        for key in ("official_document_authenticity_verified",
                    "historical_capture_attested", "macro_direction_inferred",
                    "can_feed_exante_bias", "real_oos_authorized",
                    "trade_authorized", "worker_enabled", "scheduler_enabled"):
            self.assertFalse(result[key], key)

    def test_unknown_source_id_rejected(self):
        item = sample()
        item["source_id"] = "SOURCE_UNKNOWN"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_extra_retrospective_actual_rejected(self):
        item = sample()
        item["actual"] = 5.0
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_wrong_state_rejected(self):
        item = sample()
        item["state"] = "REAL_SOURCE_VERIFIED"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_empty_and_large_text_rejected(self):
        for value in ("", "X" * (MAX_TEXT_BYTES + 1)):
            with self.subTest(size=len(value)):
                item = sample()
                item["excerpt_utf8"] = value
                item["claimed_sha256"] = sha256(value.encode()).hexdigest()
                self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_timezone_ambiguity_rejected(self):
        item = sample()
        item["captured_at_utc"] = "2026-11-01T12:05:00-04:00"
        self.assertEqual(inspect(item)["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_future_issue_rejected(self):
        result = inspect_claimed_macro_receipt_lab(
            sample(),
            forecast_issued_at=datetime(2026, 11, 2, 12, 2, tzinfo=timezone.utc),
            evaluated_at=AFTER)
        self.assertEqual(result["state"], "LAB_OFFICIAL_RECEIPT_REFUSED")

    def test_naive_issuance_rejected(self):
        with self.assertRaises(ValueError):
            inspect_claimed_macro_receipt_lab(
                sample(), forecast_issued_at=datetime(2026, 11, 2, 12, 0),
                evaluated_at=AFTER)

    def test_snapshot_hash_is_reproducible_and_text_sensitive(self):
        original = inspect(sample())["receipt"]
        self.assertEqual(original, inspect(sample())["receipt"])
        modified = sample()
        modified["excerpt_utf8"] += "!"
        modified["claimed_sha256"] = sha256(modified["excerpt_utf8"].encode()).hexdigest()
        changed = inspect(modified)["receipt"]
        self.assertNotEqual(original["record_sha256"], changed["record_sha256"])


if __name__ == "__main__":
    unittest.main()
