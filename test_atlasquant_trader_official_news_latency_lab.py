"""Synthetic-only contracts for news delivery timing; NO real feed measurements."""
from __future__ import annotations

import hashlib
import unittest
from datetime import datetime, timezone

from atlasquant_trader_official_news_latency_lab import (
    STATE, DENIED, MIN_INDEPENDENT_REAL_EVENTS_FOR_PROVIDER_DECISION,
    assess_official_news_delays_lab as assess,
)

AT = datetime(2026, 11, 12, 15, tzinfo=timezone.utc)
EMP = "BLS_US_EMPLOYMENT_20261106"
CPI = "BLS_US_CPI_20261110"
BODY = b"<rss><channel>SYNTHETIC_NOT_AN_OFFICIAL_BLS_RESPONSE</channel></rss>"


def fixture(event=EMP):
    if event == CPI:
        sid, day, path, feed = "BLS_CPI_RSS", "2026-11-10", "cpi.toc.htm", "cpi.rss"
    else:
        sid, day, path, feed = "BLS_EMPLOYMENT_RSS", "2026-11-06", "empsit.toc.htm", "empsit.rss"
    start = day + "T13:30:"
    return {
        "event_id": event, "source_id": sid,
        "source_url": "https://www.bls.gov/feed/" + feed,
        "item_url": "https://www.bls.gov/news.release/" + path,
        "scheduled_release_at_utc": start + "00Z",
        "feed_published_at_utc": start + "02Z",
        "first_seen_at_utc": start + "05Z",
        "captured_at_utc": start + "08Z",
        "displayed_at_utc": start + "12Z",
        "capture_mode": "SYNTHETIC_CONTRACT_TEST",
        "http_status": 200, "content_type": "application/rss+xml",
        "raw_payload_bytes": BODY,
        "raw_payload_sha256": hashlib.sha256(BODY).hexdigest(),
    }


class OfficialNewsLatencyContractTests(unittest.TestCase):
    def test_five_declared_delays_are_arithmetic_not_measured(self):
        r = assess([fixture()], evaluated_at=AT)
        self.assertEqual(r["state"], STATE)
        x = r["records"][0]
        self.assertEqual([x[k] for k in (
            "declared_schedule_to_feed_pubdate_seconds",
            "declared_feed_pubdate_to_first_seen_seconds",
            "declared_first_seen_to_capture_seconds",
            "declared_capture_to_display_seconds",
            "declared_schedule_to_display_seconds",
        )], [2, 3, 3, 4, 12])
        self.assertFalse(x["publication_to_detection_real_latency_proven"])

    def test_two_synthetic_examples_never_decide_on_paid_provider(self):
        r = assess([fixture(CPI), fixture(EMP)], evaluated_at=AT)
        self.assertEqual(r["state"], STATE)
        self.assertEqual(r["record_count"], 2)
        self.assertEqual(r["synthetic_contract_count"], 2)
        self.assertEqual(r["provider_decision_minimum_events"],
                         MIN_INDEPENDENT_REAL_EVENTS_FOR_PROVIDER_DECISION)
        self.assertEqual(r["independent_delivery_receipts"], 0)
        self.assertFalse(r["provider_comparison_evidence_sufficient"])
        self.assertFalse(r["paid_provider_recommended"])

    def test_manual_observation_is_also_unattested(self):
        r = fixture()
        r["capture_mode"] = "MANUAL_UNATTESTED"
        result = assess([r], evaluated_at=AT)
        self.assertEqual(result["state"], STATE)
        self.assertEqual(result["manual_unattested_count"], 1)
        self.assertFalse(result["capture_time_independently_attested"])

    def test_early_or_wrong_event_clock_fails_closed(self):
        for key,value in (
            ("scheduled_release_at_utc","2026-11-06T14:30:00Z"),
            ("feed_published_at_utc","2026-11-06T13:29:59Z"),
            ("first_seen_at_utc","2026-11-06T13:30:01Z"),
            ("captured_at_utc","2026-11-06T13:30:04Z"),
            ("displayed_at_utc","2026-11-06T13:30:07Z"),
        ):
            with self.subTest(field=key):
                r=fixture()
                r[key]=value
                self.assertEqual(assess([r],evaluated_at=AT)["state"],DENIED)

    def test_future_release_cannot_be_used_before_its_actual_day(self):
        self.assertEqual(assess([fixture()],evaluated_at=datetime(
            2026,11,3,14,tzinfo=timezone.utc))["state"],DENIED)

    def test_added_actual_or_consensus_is_refused(self):
        for key in ("actual", "consensus", "surprise", "trade_authorized"):
            r=fixture()
            r[key]=123
            self.assertEqual(assess([r],evaluated_at=AT)["state"],DENIED)

    def test_day_only_copom_and_boe_do_not_get_fake_minute_precision(self):
        for eid in ("BCB_COPOM_20261104", "BOE_MPC_20261105"):
            r=fixture()
            r["event_id"]=eid
            self.assertEqual(assess([r],evaluated_at=AT)["state"],DENIED)

    def test_changing_event_feed_identity_or_url_is_denied(self):
        for key,value in (
            ("source_id","BLS_CPI_RSS"),
            ("source_url","https://example.org/feed"),
            ("item_url","https://somewhere.example/news.release/empsit.toc.htm"),
            ("item_url","http://www.bls.gov/news.release/empsit.toc.htm"),
            ("item_url","https://www.bls.gov/news.release/empsit.toc.htm?token=secret"),
            ("item_url","https://www.bls.gov@evil.example/news.release/empsit.toc.htm"),
        ):
            with self.subTest(field=key,value=value):
                r=fixture()
                r[key]=value
                self.assertEqual(assess([r],evaluated_at=AT)["state"],DENIED)

    def test_tampering_is_detected_by_internal_sha(self):
        r=fixture()
        r["raw_payload_bytes"]=BODY+b"changed"
        self.assertEqual(assess([r],evaluated_at=AT)["state"],DENIED)

    def test_recomputed_digest_does_not_authenticate_fake_body(self):
        r=fixture()
        r["raw_payload_bytes"]=b"<rss>FORGED_BUT_MATCHING_SHA</rss>"
        r["raw_payload_sha256"]=hashlib.sha256(r["raw_payload_bytes"]).hexdigest()
        report=assess([r],evaluated_at=AT)
        self.assertEqual(report["state"],STATE)
        self.assertTrue(report["records"][0]["raw_payload_sha256_internally_matched"])
        self.assertFalse(report["feed_authenticity_cryptographically_verified"])
        self.assertFalse(report["source_publication_time_attested"])

    def test_invalid_bytes_and_unexpected_media_are_denied(self):
        for content in (None,b"",b"\x00",b"\xff","string",b"x"*200001):
            with self.subTest(kind=str(type(content))):
                r=fixture()
                r["raw_payload_bytes"]=content
                r["raw_payload_sha256"]=hashlib.sha256(content).hexdigest() if isinstance(content,bytes) else "0"*64
                self.assertEqual(assess([r],evaluated_at=AT)["state"],DENIED)
        r=fixture()
        r["content_type"]="application/json"
        self.assertEqual(assess([r],evaluated_at=AT)["state"],DENIED)

    def test_http_status_must_be_actual_integer_200(self):
        for status in (True,False,201,404,500,"200"):
            r=fixture()
            r["http_status"]=status
            self.assertEqual(assess([r],evaluated_at=AT)["state"],DENIED)

    def test_duplicates_cannot_select_fastest_capture(self):
        self.assertEqual(assess([fixture(),fixture()],evaluated_at=AT)["state"],DENIED)

    def test_collection_malformed_or_oversized_denied(self):
        for payload in (None,[],{},[None],[{}],[fixture()]*31):
            self.assertEqual(assess(payload,evaluated_at=AT)["state"],DENIED)

    def test_stale_captures_or_overlong_delay_denied(self):
        r=fixture()
        r["displayed_at_utc"]="2026-11-15T00:00:00Z"
        self.assertEqual(assess([r],evaluated_at=datetime(
            2026,11,16,0,tzinfo=timezone.utc))["state"],DENIED)
        r=fixture()
        r["captured_at_utc"]="2026-11-09T14:00:00Z"
        r["displayed_at_utc"]="2026-11-09T14:00:01Z"
        self.assertEqual(assess([r],evaluated_at=AT)["state"],DENIED)

    def test_backdate_before_research_cannot_be_used(self):
        self.assertEqual(assess([fixture()],evaluated_at=datetime(
            2026,11,2,12,tzinfo=timezone.utc))["state"],DENIED)

    def test_missing_timezone_is_rejected(self):
        with self.assertRaises(ValueError):
            assess([fixture()],evaluated_at=datetime(2026,11,12,15))

    def test_rejects_unapproved_live_capture_mode(self):
        r=fixture()
        r["capture_mode"]="LIVE_RSS"
        self.assertEqual(assess([r],evaluated_at=AT)["state"],DENIED)

    def test_no_provider_purchase_render_trade_worker_or_live_claim(self):
        result=assess([fixture()],evaluated_at=AT)
        for field in (
            "paid_provider_recommended", "paid_provider_approved",
            "provider_comparison_evidence_sufficient",
            "news_delay_verified","news_realtime_guaranteed",
            "raw_source_payloads_archived", "source_publication_time_attested",
            "capture_time_independently_attested", "can_feed_live_radar",
            "trade_authorized", "worker_enabled", "scheduler_enabled",
            "render_configuration_changed",
        ):
            self.assertFalse(result[field],field)
        self.assertIsNone(result["directional_bias"])
        self.assertFalse(result["prediction_accuracy_proven"])
        self.assertNotIn("raw_payload_bytes",result["records"][0])


if __name__=="__main__":
    unittest.main()
