"""Offline adversarial RBNZ issuer XML feed tests, synthetic bytes only."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import json
from unittest.mock import patch
from urllib.error import HTTPError
import unittest

from atlasquant_trader_nzd_rbnz_xml_news_feed_lab import (
    URL, USER_AGENT, MAX_BYTES, MAX_ITEMS,
    inspect_rbnz_news_xml_bytes_lab as inspect,
    collect_rbnz_news_xml_once_lab as collect,
    main,
)

UTC=timezone.utc
NOW=datetime(2026,11,14,11,14,0,tzinfo=UTC)
ARTICLE=("https://www.rbnz.govt.nz/news-and-events/news/2026/10/"
         "monetary-policy-review-and-official-cash-rate")


def rss(*, title="October OCR decision 2.75%", link=ARTICLE,
        date="Wed, 28 Oct 2026 01:00:00 +0000",
        guid="urn:rbnz:ocr:2026:oct", channel="Reserve Bank of New Zealand",
        extra=""):
    return (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0">'
        "<channel><title>"+channel+"</title>"
        "<item><title>"+title+"</title><link>"+link+"</link>"
        "<guid>"+guid+"</guid><pubDate>"+date+"</pubDate>"
        "<description>Future commentary is not the OCR decision.</description>"
        "</item>"+extra+"</channel></rss>"
    ).encode("utf-8")


def atom(*, date="2026-10-28T01:00:00Z",link=ARTICLE,
         title="Monetary Policy Review and OCR"):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        "<title>Reserve Bank of New Zealand news</title>"
        "<entry><title>"+title+"</title>"
        '<link rel="alternate" href="'+link+'"/>'
        "<id>tag:rbnz.govt.nz,2026:ocr:oct</id>"
        "<published>"+date+"</published>"
        "</entry></feed>"
    ).encode("utf-8")


def receipt(raw):
    return {
        "source_url":URL,"final_url":URL,
        "status":200,"content_type":"text/xml; charset=utf-8",
        "body_sha256":sha256(raw).hexdigest(),
        "started_at_utc":"2026-11-14T11:13:59Z",
        "finished_at_utc":"2026-11-14T11:14:00Z",
        "https_validation_claim":True,
        "redirects_followed":False,
    }


class FakeResponse:
    def __init__(self, body, url=URL, status=200, mime="text/xml"):
        self.stream=BytesIO(body)
        self.url=url
        self.status=status
        self.headers={"Content-Type":mime+"; charset=utf-8"}
    def __enter__(self):
        return self
    def __exit__(self,*a):
        self.stream.close()
    def read(self,n=-1):
        return self.stream.read(n)
    def geturl(self):
        return self.url


class RbnzOfficialXmlFeedTests(unittest.TestCase):
    def audit(self, raw=None, meta=None, clock=NOW):
        raw=rss() if raw is None else raw
        return inspect(original_xml=raw,
                       receipt=receipt(raw) if meta is None else meta,
                       inspected_at_utc=clock)
    def safe(self, r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        for k in ("trade_authorized","live_alert_allowed","publishable",
                  "scheduler_enabled","worker_enabled",
                  "original_xml_retained","am12_ocr_original_archived",
                  "historical_first_seen_authenticated",
                  "pre_event_market_consensus_verified",
                  "signed_nzd_fx_effect_verified"):
            self.assertFalse(r[k],k)
        self.assertTrue(r["feed_metadata_is_not_first_seen_timestamp"])
        self.assertTrue(r["topic_match_is_not_ocr_decision_proof"])
        self.assertIsNone(r["actual_ocr_percent_verified"])
        self.assertEqual(r["file_writes"],0)
        self.assertEqual(r["new_cost_brl"],0)
    def valid(self, r, kind="RSS"):
        self.safe(r)
        self.assertEqual(r["state"],"LAB_RBNZ_XML_FEED_STRUCTURE_CHECKED_NO_GO")
        self.assertEqual(r["parsed_format"],kind)
        self.assertEqual(r["items_in_feed"],1)

    def test_01_rss_ocr_related_headline_not_ocr_actual(self):
        r=self.audit()
        self.valid(r)
        self.assertEqual(r["ocr_related_title_matches"],1)
        item=r["ocr_related_articles"][0]
        self.assertEqual(item["official_article_url"],ARTICLE)
        self.assertIsNone(item["actual_ocr_pct"])
        self.assertFalse(item["first_seen_by_issuer_or_prior_reader_attested"])
        self.assertNotIn("2.75",json.dumps(r))
        self.assertEqual(r["feed_body_sha256_local"],sha256(rss()).hexdigest())

    def test_02_atom_namespaces_and_rfc3339(self):
        body=atom()
        r=self.audit(raw=body)
        self.valid(r,"ATOM")
        self.assertEqual(r["ocr_related_title_matches"],1)
        self.assertEqual(r["ocr_related_articles"][0][
            "published_utc_issuer_feed_claim"],"2026-10-28T01:00:00+00:00")

    def test_03_unrelated_news_does_not_become_policy_decision(self):
        body=rss(title="Financial Stability Report and employment",guid="not-ocr")
        r=self.audit(raw=body)
        self.valid(r)
        self.assertEqual(r["ocr_related_title_matches"],0)

    def test_04_speech_about_ocr_is_topic_match_not_signed_fx_event(self):
        body=rss(title="Governor speaks on the OCR outlook",guid="speech")
        r=self.audit(raw=body)
        self.valid(r)
        self.assertEqual(r["ocr_related_title_matches"],1)
        self.assertEqual(r["ocr_related_articles"][0]["classification"],
                         "OCR_RELATED_HEADLINE_NOT_AUTHENTICATED_DECISION")
        self.assertFalse(r["pre_event_market_consensus_verified"])

    def test_05_ocr_number_in_title_never_used_as_rate(self):
        body=rss(title="OCR decision 99.99 percent? market speculation")
        r=self.audit(raw=body)
        self.valid(r)
        self.assertIsNone(r["actual_ocr_percent_verified"])
        self.assertNotIn("99.99",json.dumps(r))

    def test_06_all_real_source_checks_sha_tls_url_status(self):
        raw=rss()
        for key,bad in (
            ("source_url","https://www.rbnz.govt.nz.bad.example/feeds/news"),
            ("final_url","https://www.rbnz.govt.nz/another/path"),
            ("status",302),("status",True),("content_type","text/html"),
            ("body_sha256","f"*64),("https_validation_claim",False),
            ("redirects_followed",True),
        ):
            with self.subTest(key=key):
                rec=receipt(raw)
                rec[key]=bad
                r=self.audit(raw=raw,meta=rec)
                self.safe(r)
                self.assertEqual(r["state"],"LAB_RBNZ_XML_FEED_BLOCKED_NO_GO")
                self.assertEqual(r["reason"],
                                 "UNTRUSTED_URL_UTC_TLS_CONTENT_TYPE_OR_SHA")

    def test_07_untrusted_clock_or_timestamp_is_blocked(self):
        for value in (NOW.replace(tzinfo=None),NOW+timedelta(microseconds=1),
                      "2026-11-14T11:14:00Z",None):
            with self.subTest(value=value):
                r=self.audit(clock=value)
                self.safe(r)
                self.assertEqual(r["state"],"LAB_RBNZ_XML_FEED_BLOCKED_NO_GO")
        for key,stamp in (
            ("finished_at_utc","2026-11-14T11:14:01Z"),
            ("started_at_utc","2026-11-14T11:14:02Z"),
            ("started_at_utc","2026-11-14T11:12:30Z"),
            ("finished_at_utc","2026-11-14T11:14:00+00:00"),
        ):
            with self.subTest(stamp=stamp):
                rec=receipt(rss());rec[key]=stamp
                r=self.audit(meta=rec)
                self.safe(r)
                self.assertEqual(r["state"],"LAB_RBNZ_XML_FEED_BLOCKED_NO_GO")

    def test_08_xml_doctype_entity_rejected_before_parser(self):
        prefix=b'<!DOCTYPE rss [<!ENTITY abc "fraud">]>'
        raw=prefix+rss()
        r=self.audit(raw=raw)
        self.safe(r)
        self.assertEqual(r["reason"],"XML_DTD_OR_ENTITY_DECLARATION_PROHIBITED")

    def test_09_malformed_xml_and_unsupported_root(self):
        for raw in (b"not xml", b"<foo>not rss</foo>",
                    b"<rss version='2.0'><channel>incomplete"):
            with self.subTest(raw=raw[:30]):
                r=self.audit(raw=raw)
                self.safe(r)
                self.assertEqual(r["state"],"LAB_RBNZ_XML_FEED_BLOCKED_NO_GO")

    def test_10_fake_channel_and_duplicate_id_blocked(self):
        bad=rss(channel="Someone Else Investment Tips")
        self.assertEqual(self.audit(raw=bad)["reason"],
                         "ISSUER_CHANNEL_NOT_IDENTIFIED_OR_TOO_MANY_ENTRIES")
        second=(b'<item><title>OCR rates</title><link>'+ARTICLE.encode()+
                b'</link><guid>urn:rbnz:ocr:2026:oct</guid>'
                b'<pubDate>Wed, 28 Oct 2026 01:00:00 +0000</pubDate></item>')
        bad=rss(extra=second.decode())
        self.assertEqual(self.audit(raw=bad)["reason"],"DUPLICATE_NEWS_ITEM_ID")

    def test_11_spoof_item_links_blocked(self):
        for url in ("https://www.rbnz.govt.nz.evil.test/news",
                    "https://evil.test/news",
                    "http://www.rbnz.govt.nz/news",
                    "https://user@www.rbnz.govt.nz/news",
                    "https://www.rbnz.govt.nz:8080/news",
                    "https://www.rbnz.govt.nz/news#hash",
                    "https://www.rbnz.govt.nz/news\nHeader: injected"):
            with self.subTest(url=url):
                body=rss(link=url)
                r=self.audit(raw=body)
                self.safe(r)
                self.assertEqual(r["state"],"LAB_RBNZ_XML_FEED_BLOCKED_NO_GO")

    def test_12_future_dated_and_naive_feed_publication_rejected(self):
        for date in ("Sun, 15 Nov 2026 22:00:00 +0000",
                     "Wed, 28 Oct 2026 01:00:00",
                     "INVALID DATE"):
            with self.subTest(date=date):
                raw=rss(date=date)
                r=self.audit(raw=raw)
                self.safe(r)
                self.assertEqual(r["reason"],
                                 "UNVERIFIED_FEED_ITEM_TITLE_LINK_OR_PUBLICATION_DATE")

    def test_13_duplicate_title_nodes_and_missing_link_rejected(self):
        raw=rss().replace(b"<title>October",b"<title>other</title><title>October",1)
        self.assertEqual(self.audit(raw=raw)["state"],
                         "LAB_RBNZ_XML_FEED_BLOCKED_NO_GO")
        raw=rss(link="")
        self.assertEqual(self.audit(raw=raw)["state"],
                         "LAB_RBNZ_XML_FEED_BLOCKED_NO_GO")

    def test_14_extra_receipt_fields_and_oversize_fail_closed(self):
        rcp=receipt(rss());rcp["private_account"]="secret"
        self.assertEqual(self.audit(meta=rcp)["state"],
                         "LAB_RBNZ_XML_FEED_BLOCKED_NO_GO")
        raw=b"x"*(MAX_BYTES+1)
        self.assertEqual(self.audit(raw=raw)["state"],
                         "LAB_RBNZ_XML_FEED_BLOCKED_NO_GO")

    def test_15_max_items_201_fails_closed(self):
        raw=rss(extra="<item><title>Other</title></item>"*(MAX_ITEMS))
        r=self.audit(raw=raw)
        self.safe(r)
        self.assertEqual(r["reason"],
                         "ISSUER_CHANNEL_NOT_IDENTIFIED_OR_TOO_MANY_ENTRIES")

    def test_16_collector_explicit_flag_required_zero_http(self):
        calls=[]
        def opener(req,*,timeout):
            calls.append(req.full_url);raise AssertionError("No GET allowed")
        r=collect(explicit_request=False,request_open=opener)
        self.safe(r)
        self.assertEqual(calls,[])
        self.assertEqual(r["http_requests"],0)

    def test_17_single_exact_issuer_xml_get_with_compliant_agent(self):
        calls=[]
        raw=rss()
        times=iter(("2026-11-14T11:13:59Z","2026-11-14T11:14:00Z"))
        def opener(req,*,timeout):
            calls.append((req.full_url,req.get_method(),
                          req.get_header("User-agent"),timeout))
            return FakeResponse(raw)
        r=collect(explicit_request=True,request_open=opener,
                  now_stamp=lambda:next(times))
        self.valid(r)
        self.assertEqual(r["http_requests"],1)
        self.assertEqual(calls,[(URL,"GET",USER_AGENT,12)])
        self.assertFalse(r["original_xml_retained"])

    def test_18_redirect_html_or_403_does_not_retry(self):
        for problem in ("redirect","html","403"):
            with self.subTest(problem=problem):
                calls=[]
                def opener(req,*,timeout):
                    calls.append(req.full_url)
                    if problem=="403":
                        raise HTTPError(req.full_url,403,"Denied",None,None)
                    return FakeResponse(rss(),
                        url="https://www.rbnz.govt.nz/news" if
                            problem=="redirect" else URL,
                        mime="text/html" if problem=="html" else "text/xml")
                r=collect(explicit_request=True,request_open=opener,
                          now_stamp=lambda:"2026-11-14T11:14:00Z")
                self.safe(r)
                self.assertEqual(r["state"],"LAB_RBNZ_XML_FEED_BLOCKED_NO_GO")
                self.assertEqual(calls,[URL])

    def test_19_rss_no_valid_ocr_headline_still_not_first_seen(self):
        body=rss(title="General banking and supervision update",guid="supervision")
        r=self.audit(raw=body)
        self.valid(r)
        self.assertEqual(r["ocr_related_title_matches"],0)
        self.assertFalse(r["historical_first_seen_authenticated"])

    def test_20_cli_default_is_off_no_automatic_network(self):
        with patch("atlasquant_trader_nzd_rbnz_xml_news_feed_lab.build_opener") as op:
            self.assertEqual(main([]),2)
            op.assert_not_called()


if __name__=="__main__":
    unittest.main()
