"""Security and state-boundary tests for pure offline official RSS HTTP contract."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import unittest
from unittest.mock import patch

from atlasquant_trader_official_http_collection_contract_lab import (
    CACHE_SCHEMA, PLAN_SCHEMA, RESPONSE_SCHEMA,
    plan_official_feed_request_lab, reconcile_official_feed_response_lab,
)
from atlasquant_trader_official_rss_capture_lab import SOURCES

NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
SOURCE = "US_BLS_EMPLOYMENT"
URL = SOURCES[SOURCE]["feed_url"]
RSS = (b'<rss><channel><item><guid>test-item-one</guid>'
       b'<title>Documentary labor update</title>'
       b'<link>https://www.bls.gov/news.release/empsit.nr0.htm</link>'
       b'<pubDate>Wed, 04 Nov 2026 11:00:00 +0000</pubDate>'
       b'</item></channel></rss>')


def response(*, status=200, xml=RSS, headers=None, url=URL):
    return {
        "status_code": status, "effective_url": url, "body": xml,
        "headers": {"Content-Type": "application/rss+xml; charset=utf-8"}
        if headers is None else headers,
    }


class OfficialHttpContractLabTests(unittest.TestCase):
    def test_plan_is_pinned_and_never_performs_network_or_scheduling(self):
        planned = plan_official_feed_request_lab(SOURCE, planned_at=NOW)
        self.assertEqual(planned["schema"], PLAN_SCHEMA)
        self.assertEqual(planned["state"], "LAB_NON_EXECUTABLE_REQUEST_PLAN")
        self.assertEqual((planned["method"], planned["url"]), ("GET", URL))
        self.assertEqual(planned["timeout_seconds"], 8)
        self.assertEqual(planned["max_response_bytes"], 256 * 1024)
        for flag in ("allow_redirects", "follow_redirects", "connect_to_network",
                     "request_executed", "scheduler_enabled", "worker_enabled",
                     "trade_authorized", "live_news"):
            self.assertFalse(planned[flag], flag)
        self.assertEqual(planned["external_http_requests"], 0)

    def test_synthetic_200_is_documentary_not_a_live_verified_feed(self):
        plan = plan_official_feed_request_lab(SOURCE, planned_at=NOW)
        original = RSS
        out = reconcile_official_feed_response_lab(
            plan, response(headers={
                "content-type": "application/rss+xml",
                "ETag": 'W/"news-1"',
                "Last-Modified": format_datetime(NOW - timedelta(hours=1), usegmt=True),
            }), received_at=NOW,
        )
        self.assertEqual(original, RSS)
        self.assertEqual((out["schema"], out["state"]),
                         (RESPONSE_SCHEMA, "LAB_DOCUMENTARY_RESPONSE_ACCEPTED_ONLY"))
        self.assertEqual(out["snapshot"]["item_count"], 1)
        self.assertEqual(out["cache"]["schema"], CACHE_SCHEMA)
        self.assertEqual(out["cache"]["etag"], 'W/"news-1"')
        self.assertIsNone(out["diff"])
        for key in ("response_origin_attested", "live_data_verified",
                    "news_current_verified", "live_news", "can_feed_live_radar",
                    "trade_authorized", "scheduler_enabled", "notification_sent"):
            self.assertFalse(out[key], key)
        self.assertEqual(out["currency_bias"], "AGUARDAR")

    def test_304_keeps_prior_hash_but_does_not_claim_news_freshness(self):
        first = reconcile_official_feed_response_lab(
            plan_official_feed_request_lab(SOURCE, planned_at=NOW),
            response(headers={"Content-Type": "application/rss+xml",
                              "ETag": '"r1"'}), received_at=NOW)
        later = NOW + timedelta(hours=3)
        plan = plan_official_feed_request_lab(
            SOURCE, planned_at=later, previous_cache=first["cache"])
        self.assertEqual(plan["headers"]["If-None-Match"], '"r1"')
        cached = reconcile_official_feed_response_lab(
            plan, response(status=304, xml=b"", headers={}, url=URL),
            received_at=later, previous_cache=first["cache"],
            previous_report=first["snapshot"])
        self.assertEqual(cached["state"], "LAB_UNATTESTED_NOT_MODIFIED_CLAIM")
        self.assertEqual(cached["previous_payload_sha256"],
                         first["cache"]["payload_sha256"])
        self.assertEqual(cached["cache"], first["cache"])
        self.assertIsNone(cached["snapshot"])
        self.assertFalse(cached["news_current_verified"])
        self.assertFalse(cached["live_news"])

    def test_200_revision_is_review_only_and_seven_usd_pairs(self):
        initial = reconcile_official_feed_response_lab(
            plan_official_feed_request_lab(SOURCE, planned_at=NOW),
            response(headers={"Content-Type": "application/rss+xml",
                              "ETag": '"v1"'}), received_at=NOW)
        at = NOW + timedelta(hours=3)
        plan = plan_official_feed_request_lab(
            SOURCE, planned_at=at, previous_cache=initial["cache"])
        revised = RSS.replace(b"Documentary labor update", b"Documentary labor revision")
        out = reconcile_official_feed_response_lab(
            plan, response(xml=revised), received_at=at,
            previous_cache=initial["cache"],
            previous_report=initial["snapshot"])
        self.assertEqual(out["state"], "LAB_DOCUMENTARY_RESPONSE_ACCEPTED_ONLY")
        self.assertEqual(out["diff"]["changes"][0]["change"], "DOCUMENT_REVISED")
        self.assertEqual(len(out["diff"]["affected_pairs"]), 7)
        self.assertFalse(out["diff"]["notification_sent"])
        self.assertEqual(out["diff"]["changes"][0]["directional_impact"], "AGUARDAR")

    def test_rate_limit_and_source_unavailable_never_retry_or_promote_cache(self):
        plan = plan_official_feed_request_lab(SOURCE, planned_at=NOW)
        for status, state in ((429, "LAB_SOURCE_RATE_LIMITED"),
                              (500, "LAB_SOURCE_UNAVAILABLE"),
                              (503, "LAB_SOURCE_UNAVAILABLE")):
            with self.subTest(status=status):
                out = reconcile_official_feed_response_lab(
                    plan, response(status=status, xml=b"", headers={}), received_at=NOW)
                self.assertEqual(out["state"], state)
                self.assertIsNone(out["cache"])
                self.assertFalse(out["retry_scheduled"])
                self.assertFalse(out["can_feed_live_radar"])

    def test_redirect_and_wrong_http_status_blocked(self):
        plan = plan_official_feed_request_lab(SOURCE, planned_at=NOW)
        for code in (301, 302, 307, 308):
            self.assertEqual(reconcile_official_feed_response_lab(
                plan, response(status=code, xml=b"", headers={}),
                received_at=NOW)["state"], "LAB_REDIRECT_BLOCKED")
        self.assertEqual(reconcile_official_feed_response_lab(
            plan, response(status=403, xml=b"", headers={}),
            received_at=NOW)["state"], "LAB_HTTP_STATUS_BLOCKED")

    def test_injected_headers_spoofed_host_and_html_content_blocked(self):
        plan = plan_official_feed_request_lab(SOURCE, planned_at=NOW)
        cases = (
            response(headers={"ETag": '"ok"\r\nX-Evil: true'}),
            response(headers={"Last-Modified": "Wed, 04 Nov 2026 12:00:00 GMT\r\nFake"}),
            response(headers={"Last-Modified": "Fri, 06 Nov 2026 12:00:00 GMT"}),
            response(headers={"ETag": '"r1"', "etag": '"r2"'}),
            response(headers={"Content-Type": "text/html"}),
            response(url="https://www.bls.gov.attacker.test/feed/empsit.rss"),
            response(xml=b"x" * (256 * 1024 + 1)),
            response(xml=b'<!DOCTYPE x [<!ENTITY p "hi">]><rss/>'),
        )
        for fake in cases:
            with self.subTest(response=fake["headers"]):
                self.assertEqual(reconcile_official_feed_response_lab(
                    plan, fake, received_at=NOW)["state"], "LAB_RESPONSE_REJECTED")

    def test_wrong_source_cache_and_forged_plan_blocked(self):
        initial_plan = plan_official_feed_request_lab(SOURCE, planned_at=NOW)
        first = reconcile_official_feed_response_lab(initial_plan, response(), received_at=NOW)
        old_cache = first["cache"]
        for kind in ("cross_source", "etag_injection", "future_cache", "unauthorized_live"):
            cache = deepcopy(old_cache)
            if kind == "cross_source":
                cache["source_id"] = "EU_ECB_PRESS"
            elif kind == "etag_injection":
                cache["etag"] = '"x"\nInjected: 1'
            elif kind == "future_cache":
                cache["received_at_utc"] = (NOW + timedelta(days=2)).isoformat()
            else:
                cache["response_origin_attested"] = True
            self.assertNotEqual(plan_official_feed_request_lab(
                SOURCE, planned_at=NOW + timedelta(hours=3),
                previous_cache=cache)["state"], "LAB_NON_EXECUTABLE_REQUEST_PLAN")
        bad = deepcopy(initial_plan)
        bad["url"] = "https://evil.test/fake.xml"
        self.assertEqual(reconcile_official_feed_response_lab(
            bad, response(), received_at=NOW)["state"], "LAB_RESPONSE_REJECTED")

    def test_unplanned_304_and_modified_304_body_blocked(self):
        plan = plan_official_feed_request_lab(SOURCE, planned_at=NOW)
        out = reconcile_official_feed_response_lab(
            plan, response(status=304, xml=b"", headers={}), received_at=NOW)
        self.assertEqual(out["reason"], "UNEXPECTED_OR_UNCONDITIONAL_304")
        first = reconcile_official_feed_response_lab(plan, response(headers={
            "Content-Type": "application/rss+xml", "ETag": '"v1"'}), received_at=NOW)
        later = NOW + timedelta(hours=3)
        p2 = plan_official_feed_request_lab(SOURCE, planned_at=later,
                                           previous_cache=first["cache"])
        altered = reconcile_official_feed_response_lab(
            p2, response(status=304, xml=b"not-empty", headers={}),
            received_at=later, previous_cache=first["cache"])
        self.assertEqual(altered["state"], "LAB_RESPONSE_REJECTED")

    def test_invalid_previous_report_refused_and_never_infer_currency_bias(self):
        first = reconcile_official_feed_response_lab(
            plan_official_feed_request_lab(SOURCE, planned_at=NOW),
            response(headers={"Content-Type": "application/rss+xml", "ETag": '"v1"'}),
            received_at=NOW)
        later = NOW + timedelta(hours=3)
        p2 = plan_official_feed_request_lab(SOURCE, planned_at=later,
                                           previous_cache=first["cache"])
        fake = deepcopy(first["snapshot"])
        fake["trade_authorized"] = True
        out = reconcile_official_feed_response_lab(
            p2, response(), received_at=later,
            previous_cache=first["cache"], previous_report=fake)
        self.assertEqual(out["reason"], "UNTRUSTED_PREVIOUS_NEWS_REPORT")

    def test_source_lead_date_and_naive_clock_refused(self):
        self.assertNotEqual(plan_official_feed_request_lab(
            "NO_SUCH_PROVIDER", planned_at=NOW)["state"],
            "LAB_NON_EXECUTABLE_REQUEST_PLAN")
        self.assertNotEqual(plan_official_feed_request_lab(
            SOURCE, planned_at=NOW - timedelta(days=1))["state"],
            "LAB_NON_EXECUTABLE_REQUEST_PLAN")
        with self.assertRaises(ValueError):
            plan_official_feed_request_lab(SOURCE, planned_at=NOW.replace(tzinfo=None))

    def test_offline_contract_never_invokes_http_even_in_reconciliation(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("network called")), \
                patch("socket.create_connection", side_effect=AssertionError("socket called")):
            plan = plan_official_feed_request_lab(SOURCE, planned_at=NOW)
            outcome = reconcile_official_feed_response_lab(
                plan, response(), received_at=NOW)
            self.assertEqual(outcome["external_http_requests"], 0)
            self.assertEqual(outcome["new_cost_brl"], 0)
            self.assertFalse(outcome["scheduler_enabled"])


if __name__ == "__main__":
    unittest.main()
