"""Synthetic-only official RBNZ October/September decision article tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
from urllib.error import HTTPError
from unittest.mock import patch
import json
import unittest

from atlasquant_trader_nzd_rbnz_ocr_decision_article_lab import (
    SCHEMA, OCTOBER, SEPTEMBER, USER_AGENT,
    inspect_rbnz_ocr_decision_article_bytes_lab as inspect,
    check_both_official_articles_once_lab as check,
    main,
)

UTC=timezone.utc
NOW=datetime(2026,11,14,11,50,tzinfo=UTC)
SEPT_SENTENCE=(
    "The Monetary Policy Committee today reached consensus to increase "
    "the OCR by 25 basis points to 2.75 percent."
)
OCT_SENTENCE=(
    "The Monetary Policy Committee today voted 4 - 3 to hold "
    "the OCR at 2.75 percent."
)

def page(month, *, sentence=None, extra="", title=None):
    if sentence is None:
        sentence=SEPT_SENTENCE if month=="2026-09" else OCT_SENTENCE
    if title is None:
        title=(
            "OCR increased by 25 basis points to 2.75%" if month=="2026-09"
            else "OCR held at 2.75%"
        )
    return (
        '<!doctype html><html><head><title>Reserve Bank of New Zealand</title>'
        '<script>Fake market view to raise OCR to 99.0 percent.</script>'
        '</head><body><main><h1>'+title+'</h1>'
        '<p>'+sentence+'</p>'
        '<p>Inflation is expected to increase to 4.4 percent.</p>'
        '<p>Future OCR outlook: the committee may change rates later.</p>'
        +extra+'</main></body></html>'
    ).encode("utf-8")

def receipt(month, body):
    from atlasquant_trader_nzd_rbnz_ocr_decision_article_lab import RELEASES
    return {
        "source_url":RELEASES[month][0],"final_url":RELEASES[month][0],
        "http_status":200,"content_type":"text/html; charset=utf-8",
        "body_sha256":sha256(body).hexdigest(),
        "started_at_utc":"2026-11-14T11:49:59Z",
        "finished_at_utc":"2026-11-14T11:50:00Z",
        "https_validation_claim":True,"redirects_followed":False,
    }

class FakeResponse:
    def __init__(self, body, url):
        self.stream=BytesIO(body)
        self.status=200
        self.url=url
        self.headers={"Content-Type":"text/html; charset=utf-8"}
    def __enter__(self):return self
    def __exit__(self,*a):self.stream.close()
    def geturl(self):return self.url
    def read(self,n=-1):return self.stream.read(n)

class RbnzArticleReceiptTests(unittest.TestCase):
    def audit(self,month="2026-10",body=None,meta=None,now=NOW):
        body=page(month) if body is None else body
        meta=receipt(month,body) if meta is None else meta
        return inspect(event_month=month,original_html=body,
                       receipt=meta,inspected_at_utc=now)
    def safe(self,r):
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertTrue(r["policy_event_is_not_currency_direction"])
        self.assertFalse(r["market_economist_consensus_pre_event_verified"])
        self.assertFalse(r["issuer_first_release_seen_time_independently_authenticated"])
        self.assertFalse(r["current_ocr_as_of_future_release_verified"])
        for k in ("trade_authorized","publishable","live_alert_allowed",
                  "scheduler_enabled","worker_enabled",
                  "article_html_retained","am12_source_archived"):
            self.assertFalse(r[k],k)
        self.assertIsNone(r["calibrated_nzd_directional_probability"])
        self.assertIsNone(r["out_of_sample_accuracy"])
        self.assertEqual((r["file_writes"],r["new_cost_brl"]), (0,0))
    def accepted(self,r):
        self.safe(r)
        self.assertEqual(
            r["state"],
            "LAB_RBNZ_OCR_ACTUAL_DECISION_SENTENCE_EPHEMERAL_CHECKED_NO_GO")
        self.assertEqual(r["ocr_percent_claim"],"2.75")
        self.assertEqual(len(r["article_original_sha256_local"]),64)

    def test_01_october_held_4_3_not_rate_increase(self):
        r=self.audit()
        self.accepted(r)
        self.assertEqual(r["article_url"],OCTOBER)
        self.assertEqual(r["action"],"HOLD")
        self.assertEqual(r["rate_change_basis_points_claim"],0)
        self.assertEqual(r["committee_votes_to_hold"],4)
        self.assertEqual(r["committee_votes_against_hold"],3)
        self.assertFalse(r["committee_unanimity_phrase_detected"])
        self.assertEqual(r["policy_event_date_nz_from_feed_claim"],"2026-10-28")

    def test_02_september_hike_25bps_does_not_make_october_hike(self):
        r=self.audit("2026-09")
        self.accepted(r)
        self.assertEqual(r["article_url"],SEPTEMBER)
        self.assertEqual(r["action"],"HIKE")
        self.assertEqual(r["rate_change_basis_points_claim"],25)
        self.assertTrue(r["committee_unanimity_phrase_detected"])
        self.assertIsNone(r["committee_votes_to_hold"])
        self.assertEqual(r["policy_event_date_nz_from_feed_claim"],"2026-09-02")

    def test_03_same_rate_different_actions_not_misread(self):
        sept=self.audit("2026-09")
        octo=self.audit("2026-10")
        self.accepted(sept);self.accepted(octo)
        self.assertEqual(sept["ocr_percent_claim"],octo["ocr_percent_claim"])
        self.assertNotEqual(sept["action"],octo["action"])
        self.assertEqual(sept["rate_change_basis_points_claim"],25)
        self.assertEqual(octo["rate_change_basis_points_claim"],0)

    def test_04_script_fake_rate_and_inflation_do_not_replace_policy(self):
        for month in ("2026-09","2026-10"):
            with self.subTest(month=month):
                r=self.audit(month)
                self.accepted(r)
                self.assertNotIn("99.0",json.dumps(r))
                self.assertNotIn("4.4",json.dumps(r))

    def test_05_wrong_rate_in_actual_sentence_fails_closed(self):
        bad=page("2026-10",sentence=OCT_SENTENCE.replace("2.75","5.00"))
        r=self.audit(body=bad)
        self.safe(r)
        self.assertEqual(
            r["reason"],"OFFICIAL_OCR_ACTUAL_OR_VOTE_DIFFERS_FROM_RELEASE_CONTRACT")
        self.assertIsNone(r["ocr_percent_claim"])

    def test_06_change_vote_to_7_0_fails_closed(self):
        raw=page("2026-10",sentence=OCT_SENTENCE.replace("4 - 3","7 - 0"))
        r=self.audit(body=raw)
        self.safe(r)
        self.assertEqual(r["reason"],
                         "OFFICIAL_OCR_ACTUAL_OR_VOTE_DIFFERS_FROM_RELEASE_CONTRACT")

    def test_07_wrong_september_change_or_decision_word_fails(self):
        for text in (
            SEPT_SENTENCE.replace("25 basis points","50 basis points"),
            SEPT_SENTENCE.replace("increase","decrease"),
        ):
            with self.subTest(text=text):
                r=self.audit("2026-09",body=page("2026-09",sentence=text))
                self.safe(r)
                self.assertEqual(
                    r["state"],"LAB_RBNZ_OCR_DECISION_ARTICLE_BLOCKED_NO_GO")

    def test_08_duplicate_policy_sentence_is_not_extra_confirmation(self):
        for month in ("2026-09","2026-10"):
            sentence=SEPT_SENTENCE if month=="2026-09" else OCT_SENTENCE
            raw=page(month,extra="<p>"+sentence+"</p>")
            r=self.audit(month,body=raw)
            self.safe(r)
            self.assertEqual(r["reason"],
                "POLICY_DECISION_SENTENCE_MISSING_DUPLICATED_OR_AMBIGUOUS")

    def test_09_future_commentary_and_other_meeting_cannot_replace_actual(self):
        raw=page("2026-10",sentence=(
            "The Committee expects the OCR to rise by 100 bps soon."))
        r=self.audit(body=raw)
        self.safe(r)
        self.assertEqual(r["reason"],
            "POLICY_DECISION_SENTENCE_MISSING_DUPLICATED_OR_AMBIGUOUS")

    def test_10_exact_official_html_receipt_required(self):
        raw=page("2026-10")
        for key,val in (
            ("source_url","https://rbnz.govt.nz.evil.test/news"),
            ("final_url","https://www.rbnz.govt.nz/other"),
            ("http_status",302),("http_status",True),
            ("content_type","application/xml"),
            ("body_sha256","0"*64),
            ("https_validation_claim",False),
            ("redirects_followed",True),
        ):
            with self.subTest(key=key):
                rec=receipt("2026-10",raw);rec[key]=val
                r=self.audit(body=raw,meta=rec)
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_RBNZ_OCR_DECISION_ARTICLE_BLOCKED_NO_GO")

    def test_11_bad_utc_clock_future_overspan_and_timezone_missing(self):
        raw=page("2026-10")
        for key,val in (
            ("started_at_utc","2026-11-14T11:49:00Z"),
            ("finished_at_utc","2026-11-14T11:50:01Z"),
            ("finished_at_utc","2026-11-14T11:50:00+00:00"),
        ):
            with self.subTest(key=key):
                rec=receipt("2026-10",raw);rec[key]=val
                r=self.audit(body=raw,meta=rec)
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_RBNZ_OCR_DECISION_ARTICLE_BLOCKED_NO_GO")
        for now in (None,"2026-11-14T11:50:00Z",
                    NOW.replace(tzinfo=None),
                    NOW+timedelta(microseconds=1)):
            r=self.audit(now=now)
            self.safe(r)
            self.assertEqual(r["state"],
                             "LAB_RBNZ_OCR_DECISION_ARTICLE_BLOCKED_NO_GO")

    def test_12_missing_tzdb_fails_closed_not_guess_nz_date(self):
        with patch("atlasquant_trader_nzd_rbnz_ocr_decision_article_lab.ZoneInfo",
                   side_effect=ZoneInfoNotFoundError):
            r=self.audit()
        self.safe(r)
        self.assertEqual(r["reason"],"UNPARSEABLE_NZ_TIMEZONE_OR_HTML")

    def test_13_unknown_month_or_oversize_fails_closed(self):
        r=inspect(event_month="2026-12",
            original_html=page("2026-10"),
            receipt=receipt("2026-10",page("2026-10")),
            inspected_at_utc=NOW)
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_RBNZ_OCR_DECISION_ARTICLE_BLOCKED_NO_GO")
        r=self.audit(body=b"x"*400001)
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_RBNZ_OCR_DECISION_ARTICLE_BLOCKED_NO_GO")

    def test_14_empty_or_non_utf8_page_fails_without_fallback(self):
        r=self.audit(body=page("2026-10")+b"\xff")
        self.safe(r)
        self.assertEqual(r["reason"],"UNPARSEABLE_NZ_TIMEZONE_OR_HTML")
        r=self.audit(body=b"x")
        self.safe(r)
        self.assertEqual(r["reason"],"UNKNOWN_EVENT_OR_MISSING_RAW_SOURCE")

    def test_15_no_flag_means_no_requests(self):
        called=[]
        def opener(*args,**kwargs):
            called.append(True);raise AssertionError
        r=check(explicit_request=False,opener=opener)
        self.assertEqual(r["requests_started"],0)
        self.assertEqual(called,[])
        self.assertFalse(r["trade_authorized"])

    def test_16_two_requests_exact_urls_with_compliant_agent_and_no_3rd_get(self):
        calls=[]
        def opener(req,*,timeout):
            calls.append((req.full_url,req.get_header("User-agent"),timeout))
            month="2026-09" if req.full_url==SEPTEMBER else "2026-10"
            return FakeResponse(page(month),req.full_url)
        times=iter((
            "2026-11-14T11:49:59Z","2026-11-14T11:50:00Z",
            "2026-11-14T11:49:59Z","2026-11-14T11:50:00Z",
        ))
        r=check(explicit_request=True,opener=opener,
                now_stamp=lambda:next(times))
        self.assertEqual(r["state"],
                         "LAB_RBNZ_TWO_ORIGINAL_POLICY_RELEASES_CHECKED_NO_GO")
        self.assertTrue(r["both_articles_validated_ephemerally"])
        self.assertEqual(r["change_from_september_to_october_bps"],0)
        self.assertEqual(r["requests_started"],2)
        self.assertEqual(calls,[(SEPTEMBER,USER_AGENT,12),
                                (OCTOBER,USER_AGENT,12)])
        self.assertFalse(r["am12_originals_persisted"])
        self.assertFalse(r["paper_forecast_or_consensus_verified"])

    def test_17_second_article_http403_fails_no_retry_no_fallback(self):
        calls=[]
        def opener(req,*,timeout):
            calls.append(req.full_url)
            if req.full_url==OCTOBER:
                raise HTTPError(req.full_url,403,"Denied",None,None)
            return FakeResponse(page("2026-09"),req.full_url)
        times=iter(("2026-11-14T11:49:59Z","2026-11-14T11:50:00Z",
                    "2026-11-14T11:49:59Z"))
        r=check(explicit_request=True,opener=opener,
                now_stamp=lambda:next(times))
        self.assertEqual(r["requests_started"],2)
        self.assertEqual(calls,[SEPTEMBER,OCTOBER])
        self.assertFalse(r["both_articles_validated_ephemerally"])
        self.assertEqual(r["reason"],"OFFICIAL_ARTICLE_HTTP_DENIED_NO_RETRY")

    def test_18_cli_default_rejects_without_network(self):
        with patch("atlasquant_trader_nzd_rbnz_ocr_decision_article_lab."
                   "build_opener") as op:
            self.assertEqual(main([]),2)
            op.assert_not_called()


if __name__=="__main__":
    unittest.main()
