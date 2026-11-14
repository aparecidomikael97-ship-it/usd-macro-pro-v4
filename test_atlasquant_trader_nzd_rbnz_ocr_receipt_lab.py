"""Synthetic RBNZ official cash-rate OCR source and mocked collector tests."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from io import BytesIO
from unittest.mock import patch
from zoneinfo import ZoneInfoNotFoundError
import json,tempfile,unittest

from atlasquant_trader_nzd_rbnz_ocr_receipt_lab import (
    URL,MAX_BYTES,inspect_rbnz_official_ocr_receipt_lab as inspect,
)
from atlasquant_trader_nzd_rbnz_ocr_manual_capture_lab import (
    collect_rbnz_ocr_once_lab as collect,save_rbnz_ocr_public_lab as save,
)

UTC=timezone.utc
NOW=datetime(2026,11,13,11,0,tzinfo=UTC)

def html_page(*,rate="2.75",updated="2:00pm, 28 Oct 2026",
              next_ocr="2:00pm, 09 Dec 2026",
              title="The official cash rate (OCR)",
              description="We set the OCR to keep inflation low and stable.",
              duplicate=False,market_rate="0.55395",extra=""):
    block=(
        "<h3>Official Cash Rate</h3><p>"+rate+" %</p>"
        "<p>Updated: "+updated+"</p>"
        "<p>Next update: "+next_ocr+"</p>"
    )
    return (
        "<!DOCTYPE html><html><head><title>RBNZ - The Official Cash Rate</title>"
        "<script>Official Cash Rate 99.99 % Updated: 2:00pm, 28 Oct 2026 "
        "Next update: 2:00pm, 09 Dec 2026</script></head><body><main>"
        "<h1>"+title+"</h1><p>"+description+"</p>"
        +block+(block if duplicate else "")+
        "<h3>Our latest decision</h3><p>October OCR decision: "
        "We may need to increase the OCR in future, but this is a forecast.</p>"
        "<p>Inflation 3.7 y/y%</p>"
        "<p>Exchange rates: USD "+market_rate+"</p>"
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

class FakeResp:
    def __init__(self,body):
        self.stream=BytesIO(body)
        self.status=200
        self.headers={"Content-Type":"text/html; charset=UTF-8"}
    def __enter__(self):return self
    def __exit__(self,*args):self.stream.close()
    def geturl(self):return URL
    def read(self,n=-1):return self.stream.read(n)

class NZDSourceTests(unittest.TestCase):
    def setUp(self):
        self.raw=html_page()
        self.rc=receipt(self.raw)

    def check(self,*,raw=None,rc=None,clock=NOW):
        return inspect(
            original_html=self.raw if raw is None else raw,
            receipt=self.rc if rc is None else rc,
            decision_at_utc=clock,
        )

    def safe(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["october_hold_decision_independently_attested"])
        self.assertFalse(r["september_change_publication_time_attested"])
        self.assertFalse(r["forecast_or_commentary_used_as_actual_ocr"])
        self.assertFalse(r["issuer_1400_local_assumed_utc_without_timezone"])
        self.assertFalse(r["issuer_first_release_available_at_cutoff_verified"])
        self.assertFalse(r["historical_first_seen_vintage_authenticated"])
        self.assertFalse(r["inflation_rate_used_as_ocr"])
        self.assertFalse(r["exchange_rate_used_as_ocr"])
        self.assertFalse(r["g8_policy_sources_ready"])
        self.assertFalse(r["fx28_bilateral_macro_complete"])
        self.assertFalse(r["historical_accuracy_validated"])
        self.assertIsNone(r["calibrated_directional_probability"])
        self.assertEqual(r["network_calls"],0)
        self.assertEqual(r["files_written"],0)
        self.assertEqual(r["new_cost_brl"],0)

    def test_official_cash_rate_card_retains_local_release_time(self):
        r=self.check()
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_NZD_RBNZ_OCR_HTML_LOCALLY_CHECKED_NO_GO")
        self.assertEqual(r["official_cash_rate_pct_claim"],"2.75")
        self.assertEqual(r["ocr_updated_nz_local_claim"],"2:00pm, 28 Oct 2026")
        self.assertEqual(r["next_ocr_update_nz_local_claim"],"2:00pm, 09 Dec 2026")
        self.assertTrue(r["original_html_sha256_matches_local_receipt"])
        self.assertTrue(r["official_ocr_policy_card_locally_consistent"])

    def test_future_ocr_commentary_not_same_as_current_policy(self):
        raw=html_page(extra="<p>One committee member expects OCR 5.00% next year.</p>")
        r=self.check(raw=raw,rc=receipt(raw))
        self.safe(r)
        self.assertEqual(r["official_cash_rate_pct_claim"],"2.75")

    def test_inflation_and_exchange_rates_are_not_policy_rate(self):
        raw=html_page(market_rate="99999.0",extra="<p>Inflation 100.0 y/y%</p>")
        r=self.check(raw=raw,rc=receipt(raw))
        self.safe(r)
        self.assertEqual(r["official_cash_rate_pct_claim"],"2.75")

    def test_js_fake_ocr_does_not_count_as_visible_card(self):
        r=self.check()
        self.safe(r)
        self.assertNotEqual(r["official_cash_rate_pct_claim"],"99.99")

    def test_duplicate_ocr_card_cannot_choose_favorable_value(self):
        raw=html_page(duplicate=True)
        r=self.check(raw=raw,rc=receipt(raw))
        self.safe(r)
        self.assertEqual(r["state"],"LAB_NZD_RBNZ_OCR_RECEIPT_BLOCKED")

    def test_source_url_impostor_redirect_or_bad_http_block(self):
        for k,bad in (
            ("source_url","https://www.rbnz.govt.nz.evil.test/monetary-policy/"),
            ("final_url","https://other.example/"),
            ("http_status",302),("http_status",True),
            ("content_type","application/json"),
            ("https_validation_claim",False),
            ("redirects_followed",True),
        ):
            with self.subTest(k=k):
                rc=deepcopy(self.rc)
                rc[k]=bad
                r=self.check(rc=rc)
                self.safe(r)
                self.assertEqual(r["state"],"LAB_NZD_RBNZ_OCR_RECEIPT_BLOCKED")

    def test_original_html_modified_but_old_sha_stays_blocks(self):
        bad=self.raw.replace(b"2.75 %",b"3.00 %",1)
        r=self.check(raw=bad)
        self.safe(r)
        self.assertEqual(r["reason"],"RBNZ_ORIGINAL_HTML_SHA256_MISMATCH")

    def test_wrong_page_or_invalid_rate_fails(self):
        for opts in (
            {"title":"New Zealand Financial Market Rates"},
            {"description":"Unrelated financial commentary"},
            {"rate":"NaN"},{"rate":"Infinity"},
            {"rate":"30.75"},{"rate":"-0.25"},
            {"rate":"2e0"},
        ):
            with self.subTest(opts=opts):
                raw=html_page(**opts)
                r=self.check(raw=raw,rc=receipt(raw))
                self.safe(r)
                self.assertEqual(r["state"],"LAB_NZD_RBNZ_OCR_RECEIPT_BLOCKED")

    def test_future_updated_date_never_pit_witness(self):
        for updated in ("2:00pm, 14 Nov 2026",
                        "2:00pm, 31 Feb 2026","2:00pm, 28 Oct 2027"):
            with self.subTest(updated=updated):
                raw=html_page(updated=updated)
                r=self.check(raw=raw,rc=receipt(raw))
                self.safe(r)
                self.assertEqual(r["state"],"LAB_NZD_RBNZ_OCR_RECEIPT_BLOCKED")

    def test_nz_summer_1400_update_is_0100_utc_same_day(self):
        raw=html_page(updated="2:00pm, 13 Nov 2026")
        r=self.check(raw=raw,rc=receipt(raw))
        self.safe(r)
        self.assertEqual(r["state"],"LAB_NZD_RBNZ_OCR_HTML_LOCALLY_CHECKED_NO_GO")
        self.assertEqual(r["ocr_updated_utc_interpreted_from_nz_local_claim"],
                         "2026-11-13T01:00:00+00:00")
        self.assertTrue(r["nz_local_to_utc_interpretation_is_not_issuer_first_seen_proof"])
        self.assertFalse(r["issuer_first_release_available_at_cutoff_verified"])

    def test_nz_1400_exact_second_accepts_claim_not_true_first_seen(self):
        raw=html_page(updated="2:00pm, 13 Nov 2026")
        rc=receipt(raw)
        rc["started_at_utc"]="2026-11-13T00:59:59Z"
        rc["finished_at_utc"]="2026-11-13T01:00:00Z"
        r=self.check(raw=raw,rc=rc)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_NZD_RBNZ_OCR_HTML_LOCALLY_CHECKED_NO_GO")
        self.assertFalse(r["historical_first_seen_vintage_authenticated"])

    def test_one_second_before_nz_1400_update_is_blocked(self):
        raw=html_page(updated="2:00pm, 13 Nov 2026")
        rc=receipt(raw)
        rc["started_at_utc"]="2026-11-13T00:59:58Z"
        rc["finished_at_utc"]="2026-11-13T00:59:59Z"
        r=self.check(raw=raw,rc=rc)
        self.safe(r)
        self.assertEqual(r["reason"],"RBNZ_OCR_POLICY_CARD_OR_CHRONOLOGY_INVALID")

    def test_next_update_nz_1400_allows_before_but_not_at_cutoff(self):
        raw=html_page(next_ocr="2:00pm, 13 Nov 2026")
        for second,accepted in (("2026-11-13T00:59:59Z",True),
                                ("2026-11-13T01:00:00Z",False)):
            with self.subTest(second=second):
                rc=receipt(raw)
                at=datetime.strptime(second,"%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=UTC)
                rc["started_at_utc"]=(at-timedelta(seconds=1)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
                rc["finished_at_utc"]=second
                r=self.check(raw=raw,rc=rc)
                self.safe(r)
                self.assertEqual(r["state"]==
                    "LAB_NZD_RBNZ_OCR_HTML_LOCALLY_CHECKED_NO_GO",accepted)

    def test_nz_winter_1400_is_0200_utc_not_summer_offset(self):
        raw=html_page(updated="2:00pm, 12 Jun 2026")
        rc=receipt(raw)
        rc["started_at_utc"]="2026-06-12T01:59:59Z"
        rc["finished_at_utc"]="2026-06-12T02:00:00Z"
        r=self.check(raw=raw,rc=rc,clock=NOW)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_NZD_RBNZ_OCR_HTML_LOCALLY_CHECKED_NO_GO")
        self.assertEqual(r["ocr_updated_utc_interpreted_from_nz_local_claim"],
                         "2026-06-12T02:00:00+00:00")

    def test_nz_winter_1400_one_second_early_blocked(self):
        raw=html_page(updated="2:00pm, 12 Jun 2026")
        rc=receipt(raw)
        rc["started_at_utc"]="2026-06-12T01:59:58Z"
        rc["finished_at_utc"]="2026-06-12T01:59:59Z"
        r=self.check(raw=raw,rc=rc,clock=NOW)
        self.safe(r)
        self.assertEqual(r["reason"],"RBNZ_OCR_POLICY_CARD_OR_CHRONOLOGY_INVALID")

    def test_missing_iana_tzdb_fails_closed_not_fixed_offset(self):
        with patch("atlasquant_trader_nzd_rbnz_ocr_receipt_lab.ZoneInfo",
                   side_effect=ZoneInfoNotFoundError("test-only tzdb missing")):
            r=self.check()
        self.safe(r)
        self.assertEqual(r["state"],"LAB_NZD_RBNZ_OCR_RECEIPT_BLOCKED")
        self.assertEqual(r["reason"],"RBNZ_OCR_POLICY_CARD_OR_CHRONOLOGY_INVALID")

    def test_next_update_in_past_or_now_does_not_authorize_current(self):
        for next_ in ("2:00pm, 12 Nov 2026","2:00pm, 13 Nov 2026",
                      "2:00pm, 31 Feb 2027"):
            with self.subTest(next_=next_):
                raw=html_page(next_ocr=next_)
                r=self.check(raw=raw,rc=receipt(raw))
                self.safe(r)
                self.assertEqual(r["state"],"LAB_NZD_RBNZ_OCR_RECEIPT_BLOCKED")

    def test_capture_clock_future_or_bad_interval(self):
        for first,last in (
            ("2026-11-13T11:00:10Z","2026-11-13T11:00:12Z"),
            ("2026-11-13T10:58:15Z","2026-11-13T10:58:11Z"),
            ("2026-11-13T10:55:00Z","2026-11-13T10:58:11Z"),
            ("invalid","2026-11-13T10:58:11Z"),
        ):
            with self.subTest(first=first,last=last):
                rc=deepcopy(self.rc)
                rc["started_at_utc"]=first
                rc["finished_at_utc"]=last
                r=self.check(rc=rc)
                self.safe(r)
                self.assertEqual(r["reason"],
                    "RBNZ_LOCAL_CAPTURE_AFTER_DECISION_OR_BAD_CLOCK")

    def test_bad_schema_naive_clock_oversize_or_missing_bytes_block(self):
        rc=deepcopy(self.rc)
        rc["private_account_id"]="no"
        r=self.check(rc=rc)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_NZD_RBNZ_OCR_RECEIPT_BLOCKED")
        for clock in (None,NOW.replace(tzinfo=None),NOW.replace(microsecond=1)):
            r=self.check(clock=clock)
            self.safe(r)
            self.assertEqual(r["state"],"LAB_NZD_RBNZ_OCR_RECEIPT_BLOCKED")
        for raw in (b"",b"x"*(MAX_BYTES+1)):
            r=self.check(raw=raw,rc=receipt(raw))
            self.safe(r)
            self.assertEqual(r["state"],"LAB_NZD_RBNZ_OCR_RECEIPT_BLOCKED")

    def test_fake_collector_one_request_only(self):
        called=[]
        ticks=iter(("2026-11-13T10:58:10Z","2026-11-13T10:58:11Z"))
        def opener(req,*,timeout):
            called.append((req.full_url,timeout))
            return FakeResp(self.raw)
        b,rc=collect(open_url=opener,now_utc=lambda:next(ticks))
        self.assertEqual(called,[(URL,12)])
        self.assertEqual(b,self.raw)
        self.assertEqual(sha256(b).hexdigest(),rc["body_sha256"])
        checked=self.check(raw=b,rc=rc)
        self.safe(checked)
        self.assertEqual(checked["state"],"LAB_NZD_RBNZ_OCR_HTML_LOCALLY_CHECKED_NO_GO")

    def test_save_original_public_bytes_only_in_lab_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            source,meta=save(body=self.raw,receipt=self.rc,local_appdata=temp)
            self.assertEqual(source.read_bytes(),self.raw)
            self.assertEqual(json.loads(meta.read_text())["body_sha256"],
                             sha256(self.raw).hexdigest())
            self.assertIn("LAB",source.parts)
            with self.assertRaises(FileExistsError):
                save(body=self.raw,receipt=self.rc,local_appdata=temp)

    def test_oversize_collector_rejects_before_saving(self):
        def opener(req,*,timeout):
            return FakeResp(b"x"*(MAX_BYTES+1))
        with self.assertRaisesRegex(ValueError,"RBNZ_OCR_RESPONSE_TOO_LARGE"):
            collect(open_url=opener,now_utc=lambda:"2026-11-13T10:58:11Z")

if __name__=="__main__":
    unittest.main()
