"""Synthetic-only custody checks; no issuer network, accounts or files."""
from datetime import datetime, timezone, timedelta
import unittest

from atlasquant_fx_universe import CURRENCIES
from atlasquant_trader_g8_issuer_custody_chain_lab import (
    DOCS, MAX_BODY_BYTES, build_local_policy_document_receipt_lab as build,
    inspect_local_policy_document_receipt_lab as inspect,
    inspect_local_policy_document_chain_lab as inspect_chain,
)

START = "2026-11-09T12:00:00Z"
FINISH = "2026-11-09T12:00:02Z"
NOW = datetime(2026, 11, 9, 12, 0, 10, tzinfo=timezone.utc)
SYNTHETIC = b"Synthetic LAB-only text. NOT central-bank source bytes."


class IssuerCustodyTests(unittest.TestCase):
    def one(self, currency="USD", body=SYNTHETIC, **kw):
        return build(currency, body, started_at_utc=kw.get("start", START),
                     finished_at_utc=kw.get("finish", FINISH),
                     sequence=kw.get("sequence", 1),
                     previous_record_sha256=kw.get("previous", None))

    def assert_never_live(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["validated_directional_accuracy"])
        self.assertEqual((r["network_requests"], r["file_writes"], r["new_cost_brl"]), (0, 0, 0))
        for field in (
            "original_publisher_bytes_at_release_attested",
            "issuer_origin_independently_authenticated",
            "collector_clock_independently_authenticated",
            "historical_point_in_time_eligible", "eligible_to_feed_macro_bias",
            "trade_authorized", "worker_enabled", "scheduler_enabled", "publishable",
        ):
            self.assertFalse(r[field], field)

    def test_eight_restricted_official_document_endpoints(self):
        self.assertEqual(set(DOCS), set(CURRENCIES))
        self.assertEqual(len(DOCS), 8)
        for currency, (_, url, mime) in DOCS.items():
            with self.subTest(currency=currency):
                self.assertTrue(url.startswith("https://"))
                self.assertIn(mime, ("text/html", "application/pdf"))

    def test_local_bytes_have_consistent_hash_without_origin_attestation(self):
        receipt = self.one()
        self.assertEqual(receipt["currency"], "USD")
        self.assertTrue(receipt["caller_supplied_and_not_independently_attested"])
        r = inspect(receipt, as_of_utc=NOW)
        self.assertEqual(r["state"], "LAB_LOCAL_RECEIPT_BYTES_SELF_CONSISTENT_UNATTESTED")
        self.assertTrue(r["chain_integrity_check"])
        self.assertEqual(r["byte_count"], len(SYNTHETIC))
        self.assert_never_live(r)

    def test_only_future_capture_end_can_be_visible_to_future_asof(self):
        receipt = self.one()
        before = inspect(receipt, as_of_utc=datetime(2026, 11, 9, 12, 0, 1, tzinfo=timezone.utc))
        self.assertEqual(before["state"], "LAB_RECEIPT_NOT_YET_VISIBLE_ASOF")
        self.assert_never_live(before)
        after = inspect(receipt, as_of_utc=NOW.astimezone(timezone(timedelta(hours=-4))))
        self.assertEqual(after["state"], "LAB_LOCAL_RECEIPT_BYTES_SELF_CONSISTENT_UNATTESTED")

    def test_previous_day_research_cannot_be_backdated_into_release_day(self):
        receipt = self.one()
        old = inspect(receipt, as_of_utc=datetime(2026, 11, 8, 23, 59, tzinfo=timezone.utc))
        self.assertEqual(old["state"], "LAB_RESEARCH_NOT_VISIBLE_ASOF")
        self.assert_never_live(old)
        self.assertEqual(self.one(start="2026-10-28T18:00:00Z",
                                  finish="2026-10-28T18:00:02Z")["state"], "LAB_RECEIPT_BLOCKED")

    def test_synthetic_two_version_chain_links_and_never_becomes_a_vintage(self):
        first = self.one()
        second = self.one(body=b"Synthetic updated body v2", start="2026-11-09T12:01:00Z",
                          finish="2026-11-09T12:01:02Z", sequence=2,
                          previous=first["record_sha256"])
        future = datetime(2026, 11, 9, 12, 2, tzinfo=timezone.utc)
        result = inspect_chain([first, second], as_of_utc=future)
        self.assertEqual(result["state"], "LAB_LOCAL_APPEND_CHAIN_SELF_CONSISTENT_UNATTESTED")
        self.assertEqual((result["receipt_count"], result["currency"]), (2, "USD"))
        self.assertEqual(result["record_sha256"], second["record_sha256"])
        self.assert_never_live(result)

    def test_reordering_or_forging_link_fails_closed(self):
        first = self.one()
        second = self.one(body=b"v2", start="2026-11-09T12:01:00Z",
                          finish="2026-11-09T12:01:02Z", sequence=2,
                          previous=first["record_sha256"])
        at = datetime(2026, 11, 9, 12, 2, tzinfo=timezone.utc)
        self.assertEqual(inspect_chain([second, first], as_of_utc=at)["state"], "LAB_RECEIPT_BLOCKED")
        forged = self.one(body=b"v2", start="2026-11-09T12:01:00Z",
                          finish="2026-11-09T12:01:02Z", sequence=2,
                          previous="a" * 64)
        self.assertEqual(inspect_chain([first, forged], as_of_utc=at)["state"], "LAB_RECEIPT_BLOCKED")

    def test_cross_currency_revision_chain_is_disallowed(self):
        first = self.one(currency="USD")
        second = self.one(currency="EUR", body=b"synthetic second", start="2026-11-09T12:01:00Z",
                          finish="2026-11-09T12:01:01Z", sequence=2,
                          previous=first["record_sha256"])
        at = datetime(2026, 11, 9, 12, 2, tzinfo=timezone.utc)
        result = inspect_chain([first, second], as_of_utc=at)
        self.assertEqual(result["state"], "LAB_RECEIPT_BLOCKED")
        self.assert_never_live(result)

    def test_payload_corruption_and_metadata_rewrite_both_fail(self):
        receipt = self.one()
        corrupt = {**receipt, "body_base64": "QQ=="}
        changed_clock = {**receipt, "collector_finished_at_utc": "2026-11-09T12:00:03Z"}
        wrong_url = {**receipt, "document_url": "https://evil.example/press/release"}
        for altered in (corrupt, changed_clock, wrong_url):
            result = inspect(altered, as_of_utc=NOW)
            self.assertEqual(result["state"], "LAB_RECEIPT_BLOCKED")
            self.assert_never_live(result)

    def test_wrong_status_redirect_missing_schema_and_spoofed_boolean_fail(self):
        receipt = self.one()
        cases = (
            {**receipt, "source_http_status_claim": 404},
            {**receipt, "redirects_followed_claim": True},
            {**receipt, "source_http_status_claim": True},
            {**receipt, "caller_supplied_and_not_independently_attested": False},
            {k: v for k, v in receipt.items() if k != "body_sha256"},
        )
        for case in cases:
            self.assertEqual(inspect(case, as_of_utc=NOW)["state"], "LAB_RECEIPT_BLOCKED")

    def test_reject_oversize_bodies_and_invalid_capture_windows(self):
        self.assertEqual(self.one(body=b"x" * (MAX_BODY_BYTES + 1))["state"], "LAB_RECEIPT_BLOCKED")
        self.assertEqual(self.one(body=b"")["state"], "LAB_RECEIPT_BLOCKED")
        self.assertEqual(self.one(start="2026-11-09T12:00:02Z", finish=START)["state"], "LAB_RECEIPT_BLOCKED")
        self.assertEqual(self.one(start=START, finish="2026-11-09T12:02:01Z")["state"], "LAB_RECEIPT_BLOCKED")
        self.assertEqual(self.one(start="2026-11-09T12:00:00", finish=FINISH)["state"], "LAB_RECEIPT_BLOCKED")

    def test_bad_asof_and_noncanonical_timezone_rejected(self):
        receipt = self.one()
        for at in (None, datetime(2026, 11, 9), "2026-11-09T12:00:10Z"):
            self.assertEqual(inspect(receipt, as_of_utc=at)["state"], "LAB_RECEIPT_BLOCKED")


if __name__ == "__main__":
    unittest.main()
