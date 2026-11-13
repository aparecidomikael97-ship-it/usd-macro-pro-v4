"""Synthetic-only SNB policy vs sight-deposit/SARON source receipt tests."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import tempfile
import unittest

from atlasquant_trader_chf_snb_current_policy_receipt_lab import (
    URL, MAX_BYTES, inspect_snb_current_policy_receipt_lab as inspect,
)
from atlasquant_trader_chf_snb_current_policy_manual_capture_lab import (
    collect_snb_current_policy_once_lab as collect,
    save_snb_policy_public_bytes_lab as save,
)

UTC=timezone.utc
NOW=datetime(2026,11,13,11,0,tzinfo=UTC)

def html_page(*,policy="0.00",up="0.00",above="-0.25",discount="25",
              date="20.06.2025",up_date=None,above_date=None,
              heading="Current interest rates and exchange rates",
              saron="-0.04",extra=""):
    return (
        "<!doctype html><html><head><title>Swiss National Bank</title>"
        "<script>SNB policy rate 99.00% valid from 20.06.2025</script>"
        "</head><body><h1>"+heading+"</h1>"
        "<main><h2>Interest rates</h2><p>SNB policy rate "+policy+
        "% valid from "+date+"</p>"
        "<p>Special rate (liquidity-shortage financing facility) 0.25%</p>"
        "<p>Interest rate on sight deposits up to threshold "+up+
        "% valid from "+(up_date or date)+"</p>"
        "<p>Interest rate on sight deposits above threshold "+above+
        "% valid from "+(above_date or date)+"</p>"
        "<p>Discount: "+discount+" basis points</p>"
        "<p>SARON "+saron+"% fixing at the close of the trading day</p>"
        "<p>1 EUR in CHF 0.9228 (third party market snapshot)</p>"+
        extra+"</main></body></html>"
    ).encode("utf-8")

def receipt(body):
    return {
        "source_url":URL,"final_url":URL,"http_status":200,
        "content_type":"text/html; charset=UTF-8",
        "body_sha256":sha256(body).hexdigest(),
        "started_at_utc":"2026-11-13T10:58:00Z",
        "finished_at_utc":"2026-11-13T10:58:02Z",
        "https_validation_claim":True,
        "redirects_followed":False,
    }

class FakeResponse:
    def __init__(self,raw):
        self.raw=BytesIO(raw)
        self.status=200
        self.headers={"Content-Type":"text/html; charset=utf-8"}
    def __enter__(self):return self
    def __exit__(self,*args):self.raw.close()
    def read(self,n=-1):return self.raw.read(n)
    def geturl(self):return URL

class SNBSourceReceiptTests(unittest.TestCase):
    def setUp(self):
        self.body=html_page()
        self.rc=receipt(self.body)

    def check(self,*,body=None,rc=None,clock=NOW):
        return inspect(original_html=self.body if body is None else body,
                       receipt=self.rc if rc is None else rc,
                       decision_at_utc=clock)

    def safe(self,out):
        self.assertEqual(out["operational_bias"],"AGUARDAR")
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["publishable"])
        self.assertFalse(out["worker_enabled"])
        self.assertFalse(out["scheduler_enabled"])
        self.assertFalse(out["live_alert_allowed"])
        self.assertFalse(out["saron_benchmark_extracted_or_republished"])
        self.assertFalse(out["bfix_exchange_rate_extracted_or_republished"])
        self.assertFalse(out["market_saron_conflated_with_policy_rate"])
        self.assertFalse(out["special_liquidity_facility_rate_conflated"])
        self.assertFalse(out["sight_deposit_above_threshold_conflated"])
        self.assertFalse(out["issuer_policy_announcement_utc_verified"])
        self.assertFalse(out["historical_issuer_first_release_verified"])
        self.assertFalse(out["current_page_is_historical_pit_vintage"])
        self.assertFalse(out["september_release_original_bytes_captured"])
        self.assertFalse(out["all_eight_g8_macro_sources_complete"])
        self.assertFalse(out["bilateral_fx28_macroeconomics_authenticated"])
        self.assertIsNone(out["calibrated_directional_probability"])
        self.assertIsNone(out["validated_fx_accuracy"])
        self.assertEqual(out["network_calls"],0)
        self.assertEqual(out["files_written"],0)
        self.assertEqual(out["new_cost_brl"],0)

    def test_current_policy_policy_rate_and_deposit_rates_remain_distinct(self):
        out=self.check()
        self.safe(out)
        self.assertEqual(out["state"],
            "LAB_CHF_SNB_CURRENT_POLICY_HTML_LOCALLY_CHECKED_NO_GO")
        self.assertTrue(out["original_html_sha256_locally_matching"])
        self.assertTrue(out["snb_policy_rate_semantic_claim_consistent"])
        self.assertEqual(out["current_snb_policy_rate_pct_claim"],"0.00")
        self.assertEqual(out["sight_deposit_up_to_threshold_pct_claim"],"0.00")
        self.assertEqual(out["sight_deposit_above_threshold_pct_claim"],"-0.25")
        self.assertEqual(out["discount_basis_points_claim"],25)
        self.assertEqual(out["policy_valid_from_date_claim"],"2025-06-20")

    def test_saron_and_bfix_spoof_does_not_change_policy_semantics_or_output(self):
        raw=html_page(saron="99.99",extra="<p>1 USD in CHF 999.9999</p>")
        out=self.check(body=raw,rc=receipt(raw))
        self.safe(out)
        self.assertEqual(out["current_snb_policy_rate_pct_claim"],"0.00")
        self.assertNotIn("saron_rate_pct",out)
        self.assertNotIn("exchange_rate",out)
        self.assertFalse(out["bfix_exchange_rate_extracted_or_republished"])

    def test_negative_policy_rate_is_structurally_possible_without_saron_confusion(self):
        raw=html_page(policy="-0.50",up="-0.50",above="-0.75")
        out=self.check(body=raw,rc=receipt(raw))
        self.safe(out)
        self.assertEqual(out["state"],
                         "LAB_CHF_SNB_CURRENT_POLICY_HTML_LOCALLY_CHECKED_NO_GO")
        self.assertEqual(out["current_snb_policy_rate_pct_claim"],"-0.50")

    def test_fake_snb_domain_redirect_and_non_html_type_blocked(self):
        for k,v in (
            ("source_url","https://www.snb.ch.evil.test/en/srv/current_interest_exchange_rates"),
            ("final_url","https://other.example/"),
            ("http_status",302),
            ("http_status",True),
            ("content_type","application/json"),
            ("https_validation_claim",False),
            ("redirects_followed",True),
        ):
            with self.subTest(k=k,value=v):
                rec=deepcopy(self.rc)
                rec[k]=v
                result=self.check(rc=rec)
                self.safe(result)
                self.assertEqual(result["state"],"LAB_CHF_SNB_POLICY_RECEIPT_BLOCKED")

    def test_changed_original_bytes_never_pass_old_receipt_hash(self):
        raw=self.body.replace(b"policy rate 0.00%",b"policy rate 0.25%",1)
        out=self.check(body=raw)
        self.safe(out)
        self.assertEqual(out["reason"],"SNB_ORIGINAL_HTML_HASH_MISMATCH")

    def test_above_threshold_must_follow_basis_point_discount(self):
        for kwargs in (
            {"above":"-0.20"},{"above":"0.25"},
            {"discount":"40"},{"discount":"101"},
            {"discount":"-25"},{"discount":"NaN"},
            {"discount":"0"},
        ):
            with self.subTest(kwargs=kwargs):
                raw=html_page(**kwargs)
                out=self.check(body=raw,rc=receipt(raw))
                self.safe(out)
                self.assertEqual(out["state"],"LAB_CHF_SNB_POLICY_RECEIPT_BLOCKED")

    def test_up_to_threshold_rate_must_equal_policy_not_special_facility(self):
        raw=html_page(up="0.25")
        out=self.check(body=raw,rc=receipt(raw))
        self.safe(out)
        self.assertEqual(out["state"],"LAB_CHF_SNB_POLICY_RECEIPT_BLOCKED")

    def test_wrong_dated_or_same_day_no_intraday_release_claim(self):
        for kwargs in (
            {"date":"13.11.2026"},
            {"date":"14.11.2026"},
            {"date":"31.02.2026"},
            {"up_date":"21.06.2025"},
            {"above_date":"19.06.2025"},
        ):
            with self.subTest(kwargs=kwargs):
                raw=html_page(**kwargs)
                out=self.check(body=raw,rc=receipt(raw))
                self.safe(out)
                self.assertEqual(out["state"],"LAB_CHF_SNB_POLICY_RECEIPT_BLOCKED")

    def test_missing_heading_duplicate_policy_and_spoofed_js_blocked(self):
        for kwargs in (
            {"heading":"Market Rates Report"},
            {"policy":"Infinity"},
            {"policy":"NaN"},
            {"policy":"1e3"},
            {"policy":"99.00"},
            {"extra":"<p>SNB policy rate 0.00% valid from 20.06.2025</p>"},
        ):
            with self.subTest(kwargs=kwargs):
                raw=html_page(**kwargs)
                out=self.check(body=raw,rc=receipt(raw))
                self.safe(out)
                self.assertEqual(out["state"],"LAB_CHF_SNB_POLICY_RECEIPT_BLOCKED")

    def test_receipt_captured_after_decision_is_rejected(self):
        for begin,end in (
            ("2026-11-13T11:01:00Z","2026-11-13T11:01:03Z"),
            ("2026-11-13T10:58:04Z","2026-11-13T10:58:01Z"),
            ("2026-11-13T10:54:00Z","2026-11-13T10:58:02Z"),
            ("bad","2026-11-13T10:58:02Z"),
        ):
            with self.subTest(begin=begin,end=end):
                rec=deepcopy(self.rc)
                rec["started_at_utc"]=begin
                rec["finished_at_utc"]=end
                out=self.check(rc=rec)
                self.safe(out)
                self.assertEqual(out["reason"],
                                 "SNB_CAPTURE_AFTER_DECISION_OR_BAD_LOCAL_CLOCK")

    def test_clock_must_be_timezone_aware_no_microseconds(self):
        for c in (None,NOW.replace(tzinfo=None),NOW.replace(microsecond=1)):
            out=self.check(clock=c)
            self.safe(out)
            self.assertEqual(out["state"],"LAB_CHF_SNB_POLICY_RECEIPT_BLOCKED")

    def test_nonissuer_receipt_and_account_field_rejected(self):
        rec=deepcopy(self.rc)
        rec["account_id"]="private"
        out=self.check(rc=rec)
        self.safe(out)
        self.assertEqual(out["state"],"LAB_CHF_SNB_POLICY_RECEIPT_BLOCKED")
        rec=deepcopy(self.rc)
        rec["body_sha256"]="notahash"
        out=self.check(rc=rec)
        self.safe(out)
        self.assertEqual(out["state"],"LAB_CHF_SNB_POLICY_RECEIPT_BLOCKED")

    def test_collector_one_request_only_and_hash_roundtrip(self):
        calls=[]
        times=iter(("2026-11-13T10:58:00Z","2026-11-13T10:58:02Z"))
        def fake(req,*,timeout):
            calls.append((req.full_url,timeout))
            return FakeResponse(self.body)
        body,meta=collect(open_url=fake,now_utc=lambda:next(times))
        self.assertEqual(calls,[(URL,12)])
        self.assertEqual(body,self.body)
        self.assertEqual(meta["body_sha256"],sha256(body).hexdigest())
        out=self.check(body=body,rc=meta)
        self.safe(out)
        self.assertEqual(out["state"],
                         "LAB_CHF_SNB_CURRENT_POLICY_HTML_LOCALLY_CHECKED_NO_GO")

    def test_public_html_isolated_local_save_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            body,meta=save(body=self.body,receipt=self.rc,local_appdata=td)
            self.assertEqual(body.read_bytes(),self.body)
            self.assertEqual(json.loads(meta.read_text())["body_sha256"],
                             sha256(self.body).hexdigest())
            self.assertIn("AtlasQuant",body.parts)
            self.assertIn("LAB",body.parts)
            with self.assertRaises(FileExistsError):
                save(body=self.body,receipt=self.rc,local_appdata=td)

    def test_oversized_capture_rejected_prewrite(self):
        def fake(req,*,timeout):
            return FakeResponse(b"X"*(MAX_BYTES+1))
        with self.assertRaisesRegex(ValueError,"OVERSIZE"):
            collect(open_url=fake,now_utc=lambda:"2026-11-13T10:58:00Z")

if __name__=="__main__":
    unittest.main()
