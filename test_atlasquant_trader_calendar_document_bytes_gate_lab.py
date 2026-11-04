"""Content hashes can be verified locally, not publisher authenticity."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import unittest

from atlasquant_trader_calendar_document_bytes_gate_lab import (
    MAX_DOCUMENT_BYTES, SCHEMA, audit_three_daily_calendar_document_bytes_lab,
)
from test_atlasquant_trader_calendar_three_daily_review_lab import (
    NOW, SLOTS, STAMPS, cap, nz_observed,
)
from test_atlasquant_trader_official_change_detection_lab import event

OLD_BODY = b"Synthetic RBNZ calendar document prior revision - untrusted"
NEW_BODY = b"Synthetic RBNZ calendar document rescheduled - untrusted"
PUBLISHED = ("2026-11-03T12:00:00Z", "2026-11-04T13:00:00Z",
             "2026-11-04T19:00:00Z")
RECEIVED = ("2026-11-04T09:38:00Z", "2026-11-04T13:48:00Z",
            "2026-11-04T20:18:00Z")


def with_document(index=0, body=OLD_BODY, *, when=None):
    when = when or ("2026-11-10T20:00:00Z" if index == 0
                    else "2026-11-16T20:00:00Z")
    ev = event(when=when, digest=sha256(body).hexdigest(),
               updated=PUBLISHED[index])
    book = nz_observed(index, events=[ev])
    capture = cap(index, [book])
    capture["document_receipts"] = [{
        "source_id": book["source_id"], "event_id": ev["event_id"],
        "effective_url": ev["source_url"],
        "received_at_utc": RECEIVED[index], "body": body,
    }]
    return capture


def empty_slot(index):
    return {**cap(index), "document_receipts": []}


def verify(captures):
    return audit_three_daily_calendar_document_bytes_lab(captures, at=NOW)


class CalendarDocumentBytesGateLabTests(unittest.TestCase):
    def test_hash_recomputed_from_two_document_bodies_and_change_review(self):
        captures = [with_document(0), with_document(1, NEW_BODY)]
        before = deepcopy(captures)
        out = verify(captures)
        self.assertEqual(captures, before)
        self.assertEqual((out["schema"], out["state"]),
                         (SCHEMA, "LAB_DOCUMENT_BYTES_CONSISTENT_UNATTESTED"))
        self.assertEqual(out["checked_document_count"], 2)
        self.assertEqual(out["checked_document_receipts"][0]["body_sha256"],
                         sha256(OLD_BODY).hexdigest())
        self.assertEqual(out["calendar_review"]["change_count"], 1)
        self.assertIn("DATE_RESCHEDULED", out["calendar_review"]["review_queue"][0]
                      ["changed_fields"])
        self.assertTrue(out["supplied_bytes_match_declared_digest"])
        self.assertFalse(out["original_publisher_bytes_authenticated"])
        self.assertFalse(out["receipt_timestamps_independently_verified"])

    def test_no_sources_has_no_raw_bytes_but_never_proves_three_daily_runs(self):
        out = verify([empty_slot(i) for i in range(3)])
        self.assertEqual(out["state"], "LAB_DOCUMENT_BYTES_CONSISTENT_UNATTESTED")
        self.assertEqual(out["checked_document_count"], 0)
        self.assertTrue(out["calendar_review"]["three_claimed_slots_seen"])
        self.assertFalse(out["three_daily_updates_verified"])
        self.assertFalse(out["local_chain_independently_witnessed"])
        self.assertEqual(len(out["local_chain_head_sha256"]), 64)

    def test_document_change_cannot_pass_unchanged_claimed_hash(self):
        c = with_document(0)
        c["document_receipts"][0]["body"] = NEW_BODY
        out = verify([c])
        self.assertEqual((out["state"], out["reason"]),
                         ("LAB_BLOCKED", "CALLER_DOCUMENT_DIGEST_MISMATCH"))
        self.assertIsNone(out["calendar_review"])

    def test_tampered_document_url_or_event_identity_is_rejected(self):
        for name, value in (
            ("effective_url", "https://www.rbnz.govt.nz.evil.test/rss"),
            ("event_id", "DIFFERENT_EVENT"),
            ("source_id", "DIFFERENT_SOURCE"),
        ):
            with self.subTest(name=name):
                c = with_document(0)
                c["document_receipts"][0][name] = value
                self.assertEqual(verify([c])["state"], "LAB_BLOCKED")

    def test_missing_duplicate_or_unexpected_receipts_are_refused(self):
        c = with_document(0)
        no_docs = deepcopy(c)
        no_docs["document_receipts"] = []
        dup = deepcopy(c)
        dup["document_receipts"].append(deepcopy(dup["document_receipts"][0]))
        for sample in (no_docs, dup):
            with self.subTest(sample=sample):
                self.assertEqual(verify([sample])["state"], "LAB_BLOCKED")

    def test_document_received_before_declared_publication_is_refused(self):
        c = with_document(1, NEW_BODY)
        c["document_receipts"][0]["received_at_utc"] = "2026-11-04T12:59:00Z"
        out = verify([c])
        self.assertEqual(out["reason"], "MISSING_BYTES_URL_OR_CLOCK_INCONSISTENT")

    def test_document_received_after_snapshot_or_capture_is_refused(self):
        for dt in ("2026-11-04T13:50:10Z", "2026-11-05T10:00:00Z"):
            with self.subTest(dt=dt):
                c = with_document(1, NEW_BODY)
                c["document_receipts"][0]["received_at_utc"] = dt
                self.assertEqual(verify([c])["state"], "LAB_BLOCKED")

    def test_large_nonbytes_and_malformed_documents_rejected(self):
        for body in ("not raw bytes", b"", b"a" * (MAX_DOCUMENT_BYTES + 1)):
            with self.subTest(type=type(body).__name__):
                c = with_document(0)
                c["document_receipts"][0]["body"] = body
                self.assertEqual(verify([c])["state"], "LAB_BLOCKED")
        c = with_document(0)
        c["document_receipts"][0]["origin_verified"] = True
        self.assertEqual(verify([c])["state"], "LAB_BLOCKED")

    def test_content_and_slot_changes_affect_only_local_unwitnessed_hash_chain(self):
        first = verify([with_document(0), with_document(1, NEW_BODY)])
        second = verify([with_document(0), with_document(1, NEW_BODY), empty_slot(2)])
        self.assertNotEqual(first["local_chain_head_sha256"],
                            second["local_chain_head_sha256"])
        self.assertFalse(first["local_chain_independently_witnessed"])
        self.assertFalse(second["local_chain_independently_witnessed"])

    def test_disappearing_partial_event_does_not_require_raw_body_and_is_not_cancelled(self):
        old = with_document(0)
        new = cap(1, [nz_observed(1, events=[])])
        new["document_receipts"] = []
        out = verify([old, new])
        self.assertEqual(out["state"], "LAB_DOCUMENT_BYTES_CONSISTENT_UNATTESTED")
        self.assertEqual(out["calendar_review"]["change_count"], 0)
        self.assertEqual(len(out["calendar_review"]["omissions_not_cancellations"]), 1)

    def test_invalid_capture_or_source_snapshot_blocks_all_output(self):
        invalid = [dict(with_document(0), live=True)]
        self.assertEqual(verify(invalid)["state"], "LAB_BLOCKED")
        invalid2 = with_document(0)
        invalid2["snapshots"][0]["original_source_bytes_attested"] = True
        self.assertEqual(verify([invalid2])["state"], "LAB_BLOCKED")
        self.assertEqual(verify([with_document(0)] * 4)["state"], "LAB_BLOCKED")

    def test_no_worker_no_new_costs_no_real_bias_and_naive_clock_refused(self):
        out = verify([with_document(0)])
        for key in ("publisher_identity_verified", "tls_response_custody_attested",
                    "publishable", "trade_authorized", "worker_enabled",
                    "scheduler_enabled", "real_time_calendar_verified",
                    "notifications_sent"):
            self.assertFalse(out[key], key)
        self.assertEqual(out["operational_bias"], "AGUARDAR")
        self.assertEqual((out["external_http_requests"], out["new_cost_brl"]), (0, 0))
        with self.assertRaises(ValueError):
            audit_three_daily_calendar_document_bytes_lab(
                [], at=datetime(2026, 11, 4, 21))


if __name__ == "__main__":
    unittest.main()
