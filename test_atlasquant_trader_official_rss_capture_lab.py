"""Official-looking RSS/Atom must stay documentary until feed custody is proven."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_official_rss_capture_lab import (
    DIFF_SCHEMA, SCHEMA, SOURCES, diff_official_rss_captures_lab,
    normalize_official_rss_lab,
)

AT = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
PUB = "Wed, 04 Nov 2026 11:00:00 +0000"
LINK = "https://www.bls.gov/news.release/empsit.nr0.htm"


def rss(*, title="Employment Situation: data released", description="First news text",
        guid="news-2026-11-04", published=PUB, link=LINK, extra=""):
    return (f'<rss version="2.0"><channel><title>BLS feed</title>'
            f'<item><guid>{guid}</guid><title>{title}</title>'
            f'<link>{link}</link><pubDate>{published}</pubDate>'
            f'<description>{description}</description></item>{extra}'
            f'</channel></rss>').encode("utf-8")


def atom():
    return (b'<feed xmlns="http://www.w3.org/2005/Atom">'
            b'<entry><id>eu-press-123</id><title>ECB press update</title>'
            b'<link rel="alternate" href="https://www.ecb.europa.eu/press/pressconf/2026/html/info.en.html" />'
            b'<published>2026-11-04T11:00:00Z</published>'
            b'<summary>Official announcement lead</summary></entry></feed>')


def read(xml=None, at=AT, source="US_BLS_EMPLOYMENT"):
    return normalize_official_rss_lab(source, rss() if xml is None else xml,
                                     captured_at=at)


class OfflineOfficialRssLabTests(unittest.TestCase):
    def test_official_leads_are_exact_and_not_an_active_connection(self):
        self.assertEqual(len(SOURCES), 5)
        self.assertEqual({s["currency"] for s in SOURCES.values()}, {"USD", "EUR"})
        self.assertEqual(SOURCES["US_BLS_EMPLOYMENT"]["feed_url"],
                         "https://www.bls.gov/feed/empsit.rss")
        self.assertEqual(SOURCES["US_FED_MONETARY"]["feed_url"],
                         "https://www.federalreserve.gov/feeds/press_monetary.xml")

    def test_rss_item_has_source_timestamp_revision_and_no_live_approval(self):
        original = rss()
        out = read(original)
        self.assertEqual(original, rss())
        self.assertEqual((out["schema"], out["state"]),
                         (SCHEMA, "LAB_DOCUMENTARY_NEWS_ITEMS_ONLY"))
        self.assertEqual(out["currency"], "USD")
        self.assertEqual(out["item_count"], 1)
        item = out["items"][0]
        self.assertEqual(item["publisher_claimed_at_utc"], AT.replace(
            hour=11).isoformat())
        self.assertEqual(item["claimed_pub_to_capture_seconds"], 3600)
        self.assertEqual(item["publisher_url"], LINK)
        self.assertEqual(len(item["revision_sha256"]), 64)
        self.assertFalse(item["source_attested"])
        self.assertEqual(item["market_direction"], "AGUARDAR")
        for key in ("source_bytes_authenticity_verified",
                    "source_original_bytes_archived", "commercial_reuse_license_verified",
                    "full_g8_news_coverage", "live_news",
                    "realtime_latency_verified", "can_feed_live_radar",
                    "trade_authorized", "scheduler_enabled", "worker_enabled"):
            self.assertFalse(out[key], key)
        self.assertEqual(out["external_http_requests"], 0)

    def test_atom_utc_is_normalized_without_directional_inference(self):
        out = read(atom(), source="EU_ECB_PRESS")
        self.assertEqual(out["state"], "LAB_DOCUMENTARY_NEWS_ITEMS_ONLY")
        self.assertEqual(out["currency"], "EUR")
        self.assertEqual(out["items"][0]["publisher_url"],
                         "https://www.ecb.europa.eu/press/pressconf/2026/html/info.en.html")
        self.assertEqual(out["items"][0]["market_direction"], "AGUARDAR")

    def test_empty_rss_is_not_evidence_of_no_news(self):
        empty = b'<rss><channel><title>Nothing</title></channel></rss>'
        out = read(empty)
        self.assertEqual(out["items"], [])
        self.assertTrue(out["feed_empty_does_not_prove_no_news"])

    def test_article_revision_diff_affects_context_seven_pairs_not_price(self):
        before = read(rss(description="Old text"), at=AT)
        after = read(rss(description="Revised text"),
                     at=AT + timedelta(hours=3))
        originals = deepcopy((before, after))
        diff = diff_official_rss_captures_lab(before, after)
        self.assertEqual((before, after), originals)
        self.assertEqual((diff["schema"], diff["state"]),
                         (DIFF_SCHEMA, "LAB_NEWS_CHANGE_REVIEW_ONLY"))
        self.assertEqual(diff["change_count"], 1)
        self.assertEqual(diff["changes"][0]["change"], "DOCUMENT_REVISED")
        self.assertEqual(len(diff["affected_pairs"]), 7)
        self.assertIn("USD/JPY", diff["affected_pairs"])
        self.assertEqual(diff["changes"][0]["directional_impact"], "AGUARDAR")
        self.assertFalse(diff["notification_sent"])
        self.assertFalse(diff["live_news"])

    def test_new_article_and_missing_in_partial_feed_not_retraction(self):
        older = read(b'<rss><channel/></rss>', at=AT)
        newer = read(at=AT + timedelta(hours=3))
        diff = diff_official_rss_captures_lab(older, newer)
        self.assertEqual(diff["changes"][0]["change"], "NEW_ARTICLE")
        vanished = diff_official_rss_captures_lab(
            newer, read(b'<rss><channel/></rss>',
                        at=AT + timedelta(hours=5)))
        self.assertEqual(vanished["change_count"], 0)
        self.assertEqual(len(vanished["missing_from_current_partial_feed"]), 1)
        self.assertTrue(vanished["news_item_disappearance_is_not_retraction"])

    def test_duplicate_guid_and_spoofed_url_refused(self):
        item = ('<item><guid>news-2026-11-04</guid><title>Second title</title>'
                f'<link>{LINK}</link><pubDate>{PUB}</pubDate></item>')
        self.assertEqual(read(rss(extra=item))["reason"], "DUPLICATE_NEWS_ID")
        for fake in ("https://www.bls.gov.evil.test/news",
                     "http://www.bls.gov/news",
                     "https://127.0.0.1/news",
                     "https://user@www.bls.gov/news"):
            with self.subTest(fake=fake):
                self.assertEqual(read(rss(link=fake))["state"], "LAB_REJECTED")

    def test_no_xml_entity_doctype_or_oversized_or_incomplete_item(self):
        for data in (b'<!DOCTYPE x [<!ENTITY y "hello">]><rss><channel/></rss>',
                     b'<!ENTITY evil SYSTEM "file:///etc/passwd">',
                     b'<rss><channel></rss>', b'x' * (257 * 1024),
                     rss(published="not-a-date"),
                     rss(published="Fri, 06 Nov 2026 11:00:00 +0000")):
            with self.subTest(data=data[:35]):
                self.assertEqual(read(data)["state"], "LAB_REJECTED")

    def test_no_retroactive_read_before_review_date(self):
        out = read(at=datetime(2026, 11, 3, 12, tzinfo=timezone.utc))
        self.assertEqual(out["reason"], "SOURCE_LEAD_NOT_RESEARCHED_AS_OF_DATE")

    def test_unreviewed_source_and_naive_capture_clock_refused(self):
        self.assertEqual(read(source="GLOBAL_PAID_NEWS")["state"], "LAB_REJECTED")
        with self.assertRaises(ValueError):
            read(at=AT.replace(tzinfo=None))

    def test_diff_forged_live_authority_or_clock_or_source_is_refused(self):
        before = read()
        after = read(at=AT + timedelta(hours=1))
        for kind in ("live_claim", "bad_source", "unmatched_clock",
                     "fake_payload_hash", "fake_link", "fake_item_direction"):
            with self.subTest(kind=kind):
                curr = deepcopy(after)
                if kind == "live_claim":
                    curr["live_news"] = True
                elif kind == "bad_source":
                    curr["source_id"] = ["no"]
                elif kind == "unmatched_clock":
                    curr["captured_at_utc"] = before["captured_at_utc"]
                elif kind == "fake_payload_hash":
                    curr["source_payload_sha256"] = "not a hash"
                elif kind == "fake_link":
                    curr["items"][0]["publisher_url"] = "https://fake.example/item"
                else:
                    curr["items"][0]["market_direction"] = "BUY_NOW"
                self.assertEqual(diff_official_rss_captures_lab(before, curr)
                                 ["state"], "LAB_REJECTED")


if __name__ == "__main__":
    unittest.main()
