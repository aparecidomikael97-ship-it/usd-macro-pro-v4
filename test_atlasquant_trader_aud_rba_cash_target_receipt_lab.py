"""Synthetic-only RBA cash target current HTML original-byte receipt tests."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import tempfile
import unittest

from atlasquant_trader_aud_rba_cash_target_receipt_lab import (
    URL, MAX_BYTES, inspect_rba_cash_target_current_receipt_lab as inspect,
)
from atlasquant_trader_aud_rba_cash_target_manual_capture_lab import (
    collect_rba_cash_target_once_lab as collect,
    save_rba_target_public_receipt_lab as save,
)

UTC=timezone.utc
NOW=datetime(2026,11,13,11,0,tzinfo=UTC)

def html_page(*,rate="4.85",effective="4 November 2026",
              next_update="2.30 pm, 8 December 2026",
              title="Cash rate target – the key monetary policy decision",
              extra="",aonia="4.99",multiple=False):
    row=(
       "<div><h2>Cash rate target</h2><p>"+rate+" %</p>"
       "<p>Effective date "+effective+"</p>"
       "<p>Next update "+next_update+"</p></div>"
    )
    return (
       "<!DOCTYPE html><html><head><title>RBA cash target</title>"
       "<script>Cash rate target 42.50 % Effective date 4 November 2026 "
       "Next update 2.30 pm, 8 December 2026</script>"
       "</head><body><main><h1>"+title+"</h1>"
       +row+(row if multiple else "")+
       "<h2>What is the cash rate?</h2><p>The realised overnight cash rate "
       "is sometimes referred to as AONIA: "+aonia+"%.</p>"
       +extra+"</main></body></html>"
    ).encode("utf-8")

def receipt(body):
    return {
        "source_url":URL,"final_url":URL,"http_status":200,
        "content_type":"text/html; charset=utf-8",
        "body_sha256":sha256(body).hexdigest(),
        "started_at_utc":"2026-11-13T10:58:10Z",
        "finished_at_utc":"2026-11-13T10:58:11Z",
        "https_validation_claim":True,"redirects_followed":False,
    }

class FakeResponse:
    def __init__(self,body):
        self.buf=BytesIO(body)
        self.status=200
        self.headers={"Content-Type":"text/html; charset=utf-8"}
    def __enter__(self):return self
    def __exit__(self,*args):self.buf.close()
    def read(self,n=-1):return self.buf.read(n)
    def geturl(self):return URL

class AUDSourceTests(unittest.TestCase):
    def setUp(self):
        self.body=html_page()
        self.rec=receipt(self.body)

    def check(self,*,body=None,rec=None,now=NOW):
        return inspect(
            original_html=self.body if body is None else body,
            receipt=self.rec if rec is None else rec,
            decision_at_utc=now)

    def safe(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["overnight_aonia_realized_rate_mistaken_for_target"])
        self.assertFalse(r["effective_date_treated_as_publication_instant"])
        self.assertFalse(r["sydney_1430_assumed_utc_without_timezone"])
        self.assertFalse(r["release_first_seen_independently_attested"])
        self.assertFalse(r["historical_policy_vintage_authenticated"])
        self.assertFalse(r["rba_screenshot_or_html_original_captured"])
        self.assertFalse(r["last_mpc_statement_timestamp_authenticated"])
        self.assertFalse(r["issuer_monetary_policy_model_calibrated"])
        self.assertFalse(r["bilateral_fx28_macro_complete"])
        self.assertFalse(r["g8_policy_sources_ready"])
        self.assertIsNone(r["fx_bias"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertIsNone(r["validated_accuracy"])
        self.assertEqual(r["network_calls"],0)
        self.assertEqual(r["files_written"],0)
        self.assertEqual(r["new_cost_brl"],0)

    def test_official_target_and_effective_date_preserved_not_announcement(self):
        r=self.check()
        self.safe(r)
        self.assertEqual(r["state"],
            "LAB_AUD_RBA_CASH_TARGET_HTML_LOCALLY_CHECKED_NO_GO")
        self.assertTrue(r["raw_html_sha256_matches_local_receipt"])
        self.assertTrue(r["target_page_semantics_consistent"])
        self.assertEqual(r["target_cash_rate_pct_claim"],"4.85")
        self.assertEqual(r["target_effective_date_claim"],"2026-11-04")
        self.assertEqual(r["issuer_next_update_sydney_local_claim"],
                         "2.30 pm, 8 December 2026")

    def test_realized_aonia_market_rate_cannot_replace_policy_target(self):
        body=html_page(aonia="12.35")
        r=self.check(body=body,rec=receipt(body))
        self.safe(r)
        self.assertEqual(r["target_cash_rate_pct_claim"],"4.85")

    def test_hidden_js_target_rate_cannot_override_visible_target(self):
        r=self.check()
        self.safe(r)
        self.assertEqual(r["target_cash_rate_pct_claim"],"4.85")
        self.assertNotEqual(r["target_cash_rate_pct_claim"],"42.50")

    def test_impostor_domain_redirect_status_and_media_block(self):
        for field,val in (
            ("source_url","https://www.rba.gov.au.evil.test/cash-rate-target-overview.html"),
            ("final_url","https://other.example/"),
            ("http_status",302),("http_status",True),
            ("content_type","application/json"),
            ("https_validation_claim",False),("redirects_followed",True),
        ):
            with self.subTest(field=field,val=val):
                rc=deepcopy(self.rec)
                rc[field]=val
                r=self.check(rec=rc)
                self.safe(r)
                self.assertEqual(r["state"],
                    "LAB_AUD_RBA_CASH_TARGET_RECEIPT_BLOCKED")

    def test_altered_body_sha_mismatch_blocks(self):
        bad=self.body.replace(b"4.85 %",b"4.75 %",1)
        r=self.check(body=bad)
        self.safe(r)
        self.assertEqual(r["reason"],"RBA_ORIGINAL_HTML_SHA256_MISMATCH")

    def test_duplicate_policy_target_card_blocks_ambiguous_source(self):
        body=html_page(multiple=True)
        r=self.check(body=body,rec=receipt(body))
        self.safe(r)
        self.assertEqual(r["reason"],
                         "RBA_CASH_TARGET_CARD_RATE_EFFECTIVE_OR_NEXT_UPDATE_INVALID")

    def test_wrong_title_or_target_card_in_other_topic_block(self):
        for opts in ({"title":"Sydney Markets Daily"},
                     {"rate":"NaN"},{"rate":"Infinity"},
                     {"rate":"30.50"},{"rate":"-2.00"},{"rate":"4e0"}):
            with self.subTest(opts=opts):
                body=html_page(**opts)
                r=self.check(body=body,rec=receipt(body))
                self.safe(r)
                self.assertEqual(r["state"],
                    "LAB_AUD_RBA_CASH_TARGET_RECEIPT_BLOCKED")

    def test_future_or_same_day_effective_date_blocks_lookahead(self):
        for day in ("13 November 2026","14 November 2026",
                    "31 February 2026","5 January 2027"):
            with self.subTest(day=day):
                body=html_page(effective=day)
                r=self.check(body=body,rec=receipt(body))
                self.safe(r)
                self.assertEqual(r["state"],
                    "LAB_AUD_RBA_CASH_TARGET_RECEIPT_BLOCKED")

    def test_expired_next_update_does_not_claim_current_validity(self):
        for upcoming in ("2.30 pm, 12 November 2026",
                         "2.30 pm, 13 November 2026",
                         "2.30 pm, 31 February 2027"):
            with self.subTest(upcoming=upcoming):
                body=html_page(next_update=upcoming)
                r=self.check(body=body,rec=receipt(body))
                self.safe(r)
                self.assertEqual(r["state"],
                    "LAB_AUD_RBA_CASH_TARGET_RECEIPT_BLOCKED")

    def test_local_capture_clock_cannot_be_future_or_backdated(self):
        for begin,end in (
            ("2026-11-13T11:01:00Z","2026-11-13T11:01:02Z"),
            ("2026-11-13T10:58:15Z","2026-11-13T10:58:10Z"),
            ("2026-11-13T10:57:00Z","2026-11-13T10:58:11Z"),
            ("bad","2026-11-13T10:58:11Z"),
        ):
            with self.subTest(begin=begin,end=end):
                rc=deepcopy(self.rec)
                rc["started_at_utc"]=begin
                rc["finished_at_utc"]=end
                r=self.check(rec=rc)
                self.safe(r)
                self.assertEqual(r["reason"],
                    "RBA_CAPTURE_CLOCK_AFTER_CUTOFF_OR_INCOHERENT")

    def test_receipt_schema_and_decision_clock_invalid(self):
        rec=deepcopy(self.rec)
        rec["account_number"]="do-not-accept"
        r=self.check(rec=rec)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_AUD_RBA_CASH_TARGET_RECEIPT_BLOCKED")
        for now in (None,NOW.replace(tzinfo=None),NOW.replace(microsecond=1)):
            r=self.check(now=now)
            self.safe(r)
            self.assertEqual(r["state"],
                             "LAB_AUD_RBA_CASH_TARGET_RECEIPT_BLOCKED")

    def test_collector_one_fixed_https_request_with_mock(self):
        calls=[]
        stamps=iter(("2026-11-13T10:58:10Z","2026-11-13T10:58:11Z"))
        def fake(req,*,timeout):
            calls.append((req.full_url,timeout))
            return FakeResponse(self.body)
        raw,rc=collect(open_url=fake,now_utc=lambda:next(stamps))
        self.assertEqual(calls,[(URL,12)])
        self.assertEqual(rc["body_sha256"],sha256(raw).hexdigest())
        r=self.check(body=raw,rec=rc)
        self.safe(r)
        self.assertEqual(r["state"],
            "LAB_AUD_RBA_CASH_TARGET_HTML_LOCALLY_CHECKED_NO_GO")

    def test_html_and_receipt_saved_only_local_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            a,b=save(body=self.body,receipt=self.rec,local_appdata=td)
            self.assertEqual(a.read_bytes(),self.body)
            self.assertEqual(json.loads(b.read_text())["body_sha256"],
                             sha256(self.body).hexdigest())
            self.assertIn("AtlasQuant",a.parts)
            self.assertIn("LAB",a.parts)
            with self.assertRaises(FileExistsError):
                save(body=self.body,receipt=self.rec,local_appdata=td)

    def test_oversized_html_never_saved(self):
        def fake(req,*,timeout):
            return FakeResponse(b"x"*(MAX_BYTES+1))
        with self.assertRaisesRegex(ValueError,"RBA_SOURCE_BODY_TOO_LARGE"):
            collect(open_url=fake,now_utc=lambda:"2026-11-13T10:58:10Z")

if __name__=="__main__":unittest.main()
