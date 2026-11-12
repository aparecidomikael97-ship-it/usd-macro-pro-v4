"""Synthetic raw-byte receipt and revision chronology tests. No official bytes."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import unittest

from atlasquant_trader_gbp_nzd_official_pilot_lab import PILOT
from atlasquant_trader_gbp_nzd_vintage_chain_lab import (
    GENESIS, inspect_gbp_nzd_vintage_chain_lab as inspect,
)


def clock(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


DECISION = clock("2026-11-08T08:00:00Z")
EVALUATED = clock("2026-11-10T08:00:00Z")


def sample(*, key="NZD_CPI_2026_Q3", vintage="capture1",
           captured="2026-11-07T10:00:00Z", parent=GENESIS,
           raw=b"Synthetic non-official HTML receipt placeholder. " * 3):
    return {
        "document_id": key, "vintage_id": vintage,
        "source_url": PILOT[key]["document_url"],
        "claimed_capture_at_utc": captured,
        "claimed_http_status": 200,
        "claimed_content_type": "text/html",
        "raw_bytes": raw, "claimed_sha256": sha256(raw).hexdigest(),
        "previous_receipt_sha256": parent,
    }


def run(records, *, decision=DECISION, evaluated=EVALUATED):
    return inspect(records, decision_at_utc=decision, evaluated_at_utc=evaluated)


class VintageChainTests(unittest.TestCase):
    def assert_never_authorized(self, report):
        self.assertFalse(report["independent_http_response_attested"])
        self.assertFalse(report["publisher_tls_origin_verified"])
        self.assertFalse(report["externally_anchored_append_only_history"])
        self.assertFalse(report["original_historical_capture_attested"])
        self.assertFalse(report["point_in_time_backtest_approved"])
        self.assertEqual(report["operational_bias"], "AGUARDAR")
        self.assertFalse(report["trade_authorized"])
        self.assertFalse(report["scheduler_enabled"])
        self.assertIsNone(report["forecast_probability"])

    def test_one_matching_raw_snapshot_is_still_unattested(self):
        r = run([sample()])
        self.assertEqual(r["state"], "LAB_INTERNAL_VINTAGE_CHAIN_CONSISTENT_UNATTESTED")
        self.assertEqual(r["records_checked"], 1)
        self.assertTrue(r["bytes_internal_hash_verified"])
        self.assertEqual(r["candidates"]["NZD_CPI_2026_Q3"]["vintage_id"], "capture1")
        self.assertNotIn("raw_bytes", str(r))
        self.assert_never_authorized(r)

    def test_no_version_before_first_captured_time(self):
        r = run([sample()], decision=clock("2026-11-07T09:59:59Z"))
        self.assertEqual(r["candidates"], {})
        self.assert_never_authorized(r)

    def test_revision_not_retroactively_used_in_earlier_decision(self):
        first = sample()
        prior = run([first])["candidates"]["NZD_CPI_2026_Q3"]["receipt_sha256"]
        revised = sample(vintage="capture2", parent=prior,
                         captured="2026-11-09T10:00:00Z",
                         raw=b"Synthetic later revision is deliberately different. " * 3)
        before = run([first, revised], decision=DECISION)
        after = run([first, revised], decision=clock("2026-11-09T10:00:00Z"))
        self.assertEqual(before["records_checked"], 2)
        self.assertEqual(before["candidates"]["NZD_CPI_2026_Q3"]["vintage_id"], "capture1")
        self.assertEqual(after["candidates"]["NZD_CPI_2026_Q3"]["vintage_id"], "capture2")
        self.assertNotEqual(before["candidates"]["NZD_CPI_2026_Q3"]["content_sha256"],
                            after["candidates"]["NZD_CPI_2026_Q3"]["content_sha256"])
        self.assert_never_authorized(after)

    def test_unobserved_future_capture_refused_at_evaluation(self):
        r = run([sample(captured="2026-11-11T10:00:00Z")])
        self.assertEqual(r["reason"], "CAPTURE_CLOCK_OUT_OF_ORDER_OR_PREPUBLICATION")
        self.assert_never_authorized(r)

    def test_prepublication_captured_claim_refused(self):
        r = run([sample(captured="2026-10-21T21:44:59Z")])
        self.assertEqual(r["reason"], "CAPTURE_CLOCK_OUT_OF_ORDER_OR_PREPUBLICATION")

    def test_pin_rejects_other_official_document_url(self):
        bad = sample()
        bad["source_url"] = PILOT["GBP_CPI_2026_09"]["document_url"]
        self.assertEqual(run([bad])["reason"], "SOURCE_URL_NOT_PINNED_TO_RELEASE")

    def test_unknown_document_id_rejected(self):
        bad = sample()
        bad["document_id"] = "USD_CPI_NOT_CATALOGUED"
        self.assertEqual(run([bad])["reason"], "UNKNOWN_PINNED_DOCUMENT")

    def test_payload_hash_mismatch_blocks_tampering(self):
        bad = sample()
        bad["raw_bytes"] += b"extra byte"
        self.assertEqual(run([bad])["reason"], "PAYLOAD_SHA256_MISMATCH")

    def test_forged_prior_revision_hash_refused(self):
        first = sample()
        second = sample(vintage="capture2", captured="2026-11-09T10:00:00Z", parent="a" * 64)
        self.assertEqual(run([first, second])["reason"], "PER_DOCUMENT_REVISION_CHAIN_MISMATCH")

    def test_duplicate_vintage_and_out_of_order_refused(self):
        first = sample()
        prior = run([first])["candidates"]["NZD_CPI_2026_Q3"]["receipt_sha256"]
        repeated = sample(parent=prior, captured="2026-11-09T10:00:00Z")
        self.assertEqual(run([first, repeated])["reason"], "AMBIGUOUS_OR_UNSAFE_VINTAGE_ID")
        earlier = sample(vintage="capture2", parent=prior, captured="2026-11-07T09:59:00Z")
        self.assertEqual(run([first, earlier])["reason"], "CAPTURE_CLOCK_OUT_OF_ORDER_OR_PREPUBLICATION")

    def test_other_currency_document_can_be_in_same_chain(self):
        a = sample()
        b = sample(key="GBP_CPI_2026_09", vintage="first-uk")
        r = run([a, b])
        self.assertEqual(set(r["candidates"]), {"NZD_CPI_2026_Q3", "GBP_CPI_2026_09"})
        self.assertEqual(r["records_checked"], 2)
        self.assert_never_authorized(r)

    def test_bad_http_or_unhashable_mime_refused_not_crash(self):
        for field, value in (("claimed_http_status", 404), ("claimed_http_status", True),
                             ("claimed_content_type", "text/plain"),
                             ("claimed_content_type", ["text/html"])):
            with self.subTest(field=field, value=value):
                bad = sample()
                bad[field] = value
                self.assertEqual(run([bad])["reason"], "CALLER_HTTP_METADATA_INVALID")

    def test_malformed_capture_clocks_refused(self):
        for captured in ("2026-11-07T09:00:00-01:00", "2026-11-07", "2026-11-07T00:00:00.1Z"):
            bad = sample(captured=captured)
            self.assertEqual(run([bad])["reason"], "CAPTURE_CLOCK_OUT_OF_ORDER_OR_PREPUBLICATION")

    def test_bad_clocks_and_unsupported_collection_refused(self):
        for records, d, e in (({}, DECISION, EVALUATED),
                              ([sample()], datetime(2026, 11, 8), EVALUATED),
                              ([sample()], EVALUATED, DECISION)):
            self.assertEqual(run(records, decision=d, evaluated=e)["state"], "LAB_BLOCKED")

    def test_unknown_receipt_fields_refused(self):
        bad = sample()
        bad["inferred_bias"] = "BUY"
        self.assertEqual(run([bad])["reason"], "UNEXPECTED_RECEIPT_FIELDS")

    def test_empty_chain_still_does_not_certify_any_source(self):
        r = run([])
        self.assertEqual(r["records_checked"], 0)
        self.assertEqual(r["candidates"], {})
        self.assert_never_authorized(r)


if __name__ == "__main__":
    unittest.main()
