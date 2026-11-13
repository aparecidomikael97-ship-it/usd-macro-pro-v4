"""Synthetic ECB DFR SDMX CSV raw source receipt and safe-collector tests."""
from __future__ import annotations

import csv,io,json,tempfile,unittest
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from copy import deepcopy

from atlasquant_trader_eur_ecb_dfr_sdmx_receipt_lab import (
    URL,KEY,COLUMNS,IDENTITY,MAX_BYTES,
    inspect_ecb_dfr_change_date_csv_receipt_lab as inspect,
)
from atlasquant_trader_eur_ecb_dfr_manual_capture_lab import (
    collect_ecb_dfr_once_lab as collect,save_ecb_dfr_lab as save,
)

UTC=timezone.utc
NOW=datetime(2026,11,13,2,15,tzinfo=UTC)

def rows():
    result=[]
    for date_,rate in (
        ("2025-06-11","2"),
        ("2026-06-17","2.25"),
        ("2026-09-16","2.5"),
    ):
        r={c:"" for c in COLUMNS}
        r.update(IDENTITY)
        r["TIME_PERIOD"]=date_
        r["OBS_VALUE"]=rate
        result.append(r)
    return result

def encode(records):
    buff=io.StringIO(newline="")
    wr=csv.DictWriter(buff,fieldnames=COLUMNS,lineterminator="\n")
    wr.writeheader()
    wr.writerows(records)
    return buff.getvalue().encode("utf-8")

def receipt(raw):
    return {
        "source_url":URL,"final_url":URL,
        "http_status":200,"content_type":"text/csv",
        "body_sha256":sha256(raw).hexdigest(),
        "started_at_utc":"2026-11-13T02:13:00Z",
        "finished_at_utc":"2026-11-13T02:13:04Z",
        "https_validation_claim":True,
        "redirects_followed":False,
    }

class DummyResponse:
    def __init__(self,raw):
        self.stream=io.BytesIO(raw)
        self.url=URL
        self.status=200
        self.headers={"Content-Type":"text/csv"}
    def __enter__(self):return self
    def __exit__(self,*args):self.stream.close()
    def geturl(self):return self.url
    def read(self,n=-1):return self.stream.read(n)

class ECBPolicyReceiptTests(unittest.TestCase):
    def setUp(self):
        self.data=encode(rows())
        self.rc=receipt(self.data)
    def check(self,*,body=None,rc=None,now=NOW):
        return inspect(
            original_csv=self.data if body is None else body,
            receipt=self.rc if rc is None else rc,
            decision_at_utc=now,
        )
    def safety(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["issuer_first_publication_time_independently_verified"])
        self.assertFalse(r["historical_point_in_time_vintage_authenticated"])
        self.assertFalse(r["issuer_rate_for_past_decision_authenticated"])
        self.assertFalse(r["all_eight_currencies_macro_complete"])
        self.assertFalse(r["central_bank_rate_measures_harmonized"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertIsNone(r["validated_directional_accuracy"])
        self.assertEqual(r["http_requests"],0)
        self.assertEqual(r["files_written"],0)

    def test_three_change_events_type_and_rate_not_fx_signal(self):
        r=self.check()
        self.safety(r)
        self.assertEqual(r["state"],
            "LAB_EUR_ECB_SDMX_ORIGINAL_BYTES_LOCALLY_CHECKED_NO_GO")
        self.assertTrue(r["raw_source_sha256_locally_matching"])
        self.assertTrue(r["source_series_identity_consistent"])
        self.assertEqual(r["rate_change_event_count"],3)
        self.assertEqual(r["latest_deposit_rate_pct_claim"],"2.5")
        self.assertEqual(r["last_effective_change_date_claim"],"2026-09-16")
        self.assertEqual(r["measure"],"ECB_DEPOSIT_FACILITY_RATE")

    def test_wrong_rate_type_or_series_key_blocked(self):
        for field,val in (
            ("KEY","FM.B.U2.EUR.4F.KR.MRR_FR.LEV"),
            ("PROVIDER_FM_ID","MRR_FR"),("INSTRUMENT_FM","IR"),
            ("FREQ","D"),("UNIT","BASIS_POINTS"),("UNIT_MULT","2"),
            ("CURRENCY","USD"),("OBS_STATUS","E"),("COLLECTION","M"),
        ):
            with self.subTest(field=field):
                vals=rows();vals[-1][field]=val
                raw=encode(vals)
                r=self.check(body=raw,rc=receipt(raw))
                self.safety(r)
                self.assertEqual(r["reason"],
                                 "ECBSOURCE_SDMX_SERIES_IDENTITY_OR_UNIT_INVALID")

    def test_bad_url_or_redirect_or_http_status_not_official_receipt(self):
        for field,val in (
            ("source_url",URL.replace("data-api.ecb.europa.eu","ecb.europa.eu.evil.test")),
            ("final_url","https://other.org/"),
            ("http_status",302),("redirects_followed",True),
            ("https_validation_claim",False),("content_type","text/html"),
        ):
            with self.subTest(field=field):
                rc=deepcopy(self.rc);rc[field]=val
                r=self.check(rc=rc)
                self.safety(r)
                self.assertEqual(r["reason"],
                                 "BAD_ECB_API_URL_CONTENT_TYPE_OR_TRANSPORT_CLAIM")

    def test_bytes_adulterated_fail_hash(self):
        b=self.data.replace(b"2.25",b"2.26")
        r=self.check(body=b)
        self.safety(r)
        self.assertEqual(r["reason"],"ECBSOURCE_ORIGINAL_BODY_SHA256_MISMATCH")

    def test_header_changed_duplicate_or_extra_row_blocks(self):
        for raw in (
            self.data.replace(b"PROVIDER_FM_ID",b"PROVIDER_ID",1),
            self.data.replace(b"KEY,FREQ",b"KEY,KEY,FREQ",1),
            encode(rows()+rows()[:1]),
            self.data[:30],
        ):
            with self.subTest(length=len(raw)):
                r=self.check(body=raw,rc=receipt(raw))
                self.safety(r)
                self.assertEqual(r["state"],"LAB_EUR_ECB_SDMX_RECEIPT_BLOCKED")

    def test_duplicates_future_same_day_and_unordered_change_events_block(self):
        for mode in ("duplicate","future","today","unordered"):
            with self.subTest(mode=mode):
                vals=rows()
                if mode=="duplicate":vals[1]["TIME_PERIOD"]=vals[0]["TIME_PERIOD"]
                if mode=="future":vals[2]["TIME_PERIOD"]="2026-11-14"
                if mode=="today":vals[2]["TIME_PERIOD"]="2026-11-13"
                if mode=="unordered":vals.reverse()
                raw=encode(vals)
                r=self.check(body=raw,rc=receipt(raw))
                self.safety(r)
                self.assertEqual(r["state"],"LAB_EUR_ECB_SDMX_RECEIPT_BLOCKED")

    def test_negative_nan_exponent_offscale_or_empty_rate_blocks(self):
        for bad in ("NaN","Infinity","2e0","200.0","",2.5,"1.12345678"):
            with self.subTest(bad=bad):
                vals=rows(); vals[-1]["OBS_VALUE"]=str(bad)
                raw=encode(vals)
                r=self.check(body=raw,rc=receipt(raw))
                self.safety(r)
                self.assertEqual(r["reason"],
                                 "ECBSOURCE_EVENT_FUTURE_DUPLICATE_OR_BAD_RATE")

    def test_time_forged_after_decision_stale_or_negative_duration(self):
        for start,end in (
            ("2026-11-13T02:16:00Z","2026-11-13T02:17:00Z"),
            ("2026-11-13T02:14:00Z","2026-11-13T02:13:00Z"),
            ("2026-11-13T02:11:00Z","2026-11-13T02:13:04Z"),
        ):
            with self.subTest(start=start,end=end):
                rc=deepcopy(self.rc)
                rc["started_at_utc"]=start;rc["finished_at_utc"]=end
                r=self.check(rc=rc)
                self.safety(r)
                self.assertEqual(r["reason"],
                                 "ECBSOURCE_RECEIVED_AFTER_DECISION_OR_CLOCK_INVALID" if False else
                                 "ECBSOURCE_RECEIVED_AFTER_DECISION_OR_CLOCK_INVALID")

    def test_schema_extra_field_and_naive_asof_fail(self):
        rc=deepcopy(self.rc);rc["account"]="hidden"
        r=self.check(rc=rc)
        self.safety(r)
        self.assertEqual(r["state"],"LAB_EUR_ECB_SDMX_RECEIPT_BLOCKED")
        r=self.check(now=NOW.replace(tzinfo=None))
        self.safety(r)
        self.assertEqual(r["state"],"LAB_EUR_ECB_SDMX_RECEIPT_BLOCKED")

    def test_collector_single_call_fixed_source_and_receipt_in_lab_only(self):
        calls=[]
        times=iter(("2026-11-13T02:13:00Z","2026-11-13T02:13:04Z"))
        def opener(req,*,timeout):
            calls.append((req.full_url,timeout))
            return DummyResponse(self.data)
        body,rc=collect(open_url=opener,now_utc=lambda:next(times))
        self.assertEqual(calls,[(URL,12)])
        self.assertEqual(body,self.data)
        self.assertEqual(rc["body_sha256"],sha256(self.data).hexdigest())
        r=self.check(body=body,rc=rc)
        self.safety(r)
        self.assertEqual(r["state"],
                         "LAB_EUR_ECB_SDMX_ORIGINAL_BYTES_LOCALLY_CHECKED_NO_GO")
        with tempfile.TemporaryDirectory() as td:
            f,g=save(body=body,receipt=rc,local_appdata=td)
            self.assertEqual(f.read_bytes(),self.data)
            self.assertEqual(json.loads(g.read_text())["body_sha256"],rc["body_sha256"])
            self.assertIn("LAB",f.parts)
            with self.assertRaises(FileExistsError):
                save(body=body,receipt=rc,local_appdata=td)

    def test_oversized_response_rejected_before_receipt(self):
        def opener(req,*,timeout):
            return DummyResponse(b"a"*(MAX_BYTES+3))
        with self.assertRaisesRegex(ValueError,"ECB_RESPONSE_OVERSIZE"):
            collect(open_url=opener,now_utc=lambda:"2026-11-13T02:13:00Z")

if __name__=="__main__": unittest.main()
