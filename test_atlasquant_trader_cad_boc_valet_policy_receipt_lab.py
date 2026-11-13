"""Offline tests for official BoC V39079 captured bytes (synthetic payloads)."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from atlasquant_trader_cad_boc_valet_policy_receipt_lab import (
    URL, inspect_boc_valet_policy_receipt_lab as inspect,
)
from atlasquant_trader_cad_boc_valet_manual_capture_lab import (
    collect_boc_valet_once_lab as collect,
    save_boc_receipt_in_isolated_lab as save,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 13, 1, 31, tzinfo=UTC)


def payload():
    return {
        "terms": {"url": "https://www.bankofcanada.ca/terms/"},
        "seriesDetail": {
            "V39079": {
                "label": "Target for the overnight rate (business daily)",
                "description": "Canadian monetary policy target",
                "dimension": {"key": "d", "name": "Date"},
                "dateFormat": "daily",
                "metadata": {"unit": "Percent", "frequency": "Business daily"},
            }
        },
        "observations": [
            {"d": "2026-11-11", "V39079": {"v": "2.50"}},
            {"d": "2026-11-10", "V39079": {"v": "2.50"}},
            {"d": "2026-11-09", "V39079": {"v": "2.50"}},
            {"d": "2026-11-06", "V39079": {"v": "2.50"}},
            {"d": "2026-11-05", "V39079": {"v": "2.50"}},
        ],
    }


def encode(data):
    return json.dumps(data,ensure_ascii=True,separators=(",", ":")).encode()


def receipt(data):
    return {
        "source_url":URL,
        "final_url":URL,
        "http_status":200,
        "content_type":"application/json; charset=utf-8",
        "body_sha256":sha256(data).hexdigest(),
        "started_at_utc":"2026-11-13T01:30:00Z",
        "finished_at_utc":"2026-11-13T01:30:01Z",
        "https_validation_claim":True,
        "redirects_followed":False,
    }


class FakeResponse:
    def __init__(self, data, url=URL, status=200):
        self.data = BytesIO(data)
        self.url = url
        self.status = status
        self.headers = {"Content-Type":"application/json; charset=utf-8"}
    def __enter__(self):return self
    def __exit__(self,*a):self.data.close()
    def read(self,n=-1):return self.data.read(n)
    def geturl(self):return self.url


class BoCValetReceiptTests(unittest.TestCase):
    def setUp(self):
        self.body = encode(payload())
        self.receipt = receipt(self.body)

    def probe(self, *, body=None, rec=None, decision=NOW):
        return inspect(
            original_body=self.body if body is None else body,
            receipt=self.receipt if rec is None else rec,
            decision_at_utc=decision,
        )

    def safety(self,result):
        self.assertEqual(result["operational_bias"],"AGUARDAR")
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["live_alert_allowed"])
        self.assertFalse(result["worker_enabled"])
        self.assertFalse(result["scheduler_enabled"])
        self.assertFalse(result["original_source_first_seen_independently_verified"])
        self.assertFalse(result["historical_point_in_time_vintage_verified"])
        self.assertFalse(result["series_values_authenticated_by_issuer_at_release"])
        self.assertFalse(result["issuer_policy_decision_timestamp_verified"])
        self.assertFalse(result["all_eight_currencies_ready"])
        self.assertFalse(result["macro_bilateral_completeness"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertIsNone(result["relative_strength_or_carry_signal"])
        self.assertEqual(result["http_requests"],0)
        self.assertEqual(result["files_written"],0)
        self.assertEqual(result["new_cost_brl"],0)

    def test_five_official_shape_observations_are_locally_valid_but_not_live_bias(self):
        r=self.probe()
        self.safety(r)
        self.assertEqual(r["state"],"LAB_CAD_BOC_ORIGINAL_BYTES_LOCALLY_CHECKED_NO_GO")
        self.assertEqual(r["api_series"],"V39079")
        self.assertEqual(r["currency"],"CAD")
        self.assertEqual(r["observed_business_day_rows"],5)
        self.assertEqual(r["latest_observation_date_claim"],"2026-11-11")
        self.assertEqual(r["latest_target_rate_pct_claim"],"2.50")
        self.assertTrue(r["source_bytes_sha256_verified_locally"])
        self.assertTrue(r["series_meaning_and_unit_consistent"])
        self.assertTrue(r["receipt_transport_claim_consistent"])
        self.assertEqual(r["source_captured_at_utc_claim"],"2026-11-13T01:30:01+00:00")

    def test_observation_order_does_not_create_future_or_old_bias(self):
        data=payload()
        data["observations"].reverse()
        raw=encode(data)
        r=self.probe(body=raw,rec=receipt(raw))
        self.safety(r)
        self.assertEqual(r["latest_observation_date_claim"],"2026-11-11")
        self.assertEqual(r["latest_target_rate_pct_claim"],"2.50")

    def test_duplicate_json_field_not_silently_overridden(self):
        raw=self.body.replace(b'"seriesDetail":{',b'"seriesDetail":{},"seriesDetail":{',1)
        r=self.probe(body=raw,rec=receipt(raw))
        self.safety(r)
        self.assertEqual(r["reason"],"BOC_RAW_JSON_DECODING_INVALID")

    def test_duplicate_or_future_business_day_observation_blocks(self):
        for bad in ("DUP","FUTURE"):
            with self.subTest(bad=bad):
                d=payload()
                if bad=="DUP":d["observations"][2]["d"]="2026-11-11"
                else:d["observations"][0]["d"]="2026-11-14"
                raw=encode(d)
                r=self.probe(body=raw,rec=receipt(raw))
                self.safety(r)
                self.assertEqual(r["reason"],
                    "BOC_OBSERVATION_DUPLICATE_FUTURE_OR_VALUE_INVALID")

    def test_unrelated_series_bank_rate_or_unit_cannot_enter_policy_target(self):
        for bad in ("V39078","CORRA","Basis points","monthly"):
            with self.subTest(bad=bad):
                d=payload()
                if bad=="V39078":
                    d["seriesDetail"]["V39078"]=d["seriesDetail"].pop("V39079")
                elif bad=="CORRA":
                    d["seriesDetail"]["V39079"]["label"]="CORRA Overnight Benchmark"
                elif bad=="Basis points":
                    d["seriesDetail"]["V39079"]["metadata"]["unit"]="Basis points"
                else:
                    d["seriesDetail"]["V39079"]["metadata"]["frequency"]="Monthly"
                raw=encode(d)
                r=self.probe(body=raw,rec=receipt(raw))
                self.safety(r)
                self.assertEqual(r["state"],"LAB_CAD_BOC_RAW_CAPTURE_BLOCKED")

    def test_source_url_redirect_or_status_cannot_fake_bank(self):
        for key,value in (
            ("source_url","https://bankofcanada.ca.evil.test/valet/observations/V39079/json?recent=5"),
            ("final_url","https://other.test/"),
            ("http_status",302),
            ("redirects_followed",True),
            ("https_validation_claim",False),
            ("content_type","text/html"),
        ):
            with self.subTest(key=key):
                rcv=deepcopy(self.receipt)
                rcv[key]=value
                r=self.probe(rec=rcv)
                self.safety(r)
                self.assertEqual(r["reason"],"NONOFFICIAL_URL_UNSAFE_TRANSPORT_OR_NON_JSON_RESPONSE")

    def test_modified_body_does_not_match_original_sha(self):
        raw=self.body.replace(b'"v":"2.50"',b'"v":"2.51"',1)
        r=self.probe(body=raw)
        self.safety(r)
        self.assertEqual(r["reason"],"ORIGINAL_BODY_SHA256_MISMATCH")

    def test_nonfinite_or_out_of_range_rate_is_blocked(self):
        for bad in (float("nan"),"NaN","Infinity","200.00",2.50,None):
            with self.subTest(bad=bad):
                d=payload()
                d["observations"][0]["V39079"]["v"]=bad
                raw=encode(d)
                r=self.probe(body=raw,rec=receipt(raw))
                self.safety(r)
                self.assertEqual(r["state"],"LAB_CAD_BOC_RAW_CAPTURE_BLOCKED")

    def test_bad_local_clock_decision_cutoff_does_not_backdate_capture(self):
        for decision in (NOW.replace(tzinfo=None),
                         datetime(2026,11,13,1,30,tzinfo=UTC),
                         NOW.replace(microsecond=1)):
            with self.subTest(decision=decision):
                r=self.probe(decision=decision)
                self.safety(r)
                self.assertEqual(r["state"],"LAB_CAD_BOC_RAW_CAPTURE_BLOCKED")

    def test_capture_interval_must_be_monotone_and_bounded(self):
        for start,end in (
            ("2026-11-13T01:30:02Z","2026-11-13T01:30:01Z"),
            ("2026-11-13T01:25:00Z","2026-11-13T01:30:01Z"),
            ("2026-11-13T01:30:00Z","2026-11-14T01:30:01Z"),
        ):
            with self.subTest(start=start,end=end):
                rec=deepcopy(self.receipt)
                rec["started_at_utc"]=start
                rec["finished_at_utc"]=end
                r=self.probe(rec=rec)
                self.safety(r)
                self.assertEqual(r["reason"],
                    "CAPTURE_AFTER_DECISION_OR_INCONSISTENT_CLOCK")

    def test_schema_has_no_account_or_order_fields(self):
        rec=deepcopy(self.receipt)
        rec["account_number"]="should-not-be-present"
        r=self.probe(rec=rec)
        self.safety(r)
        self.assertEqual(r["reason"],"INVALID_RECEIPT_BODY_OR_DECISION_CLOCK")

    def test_bounded_raw_payload_and_empty_failure(self):
        for raw in (b"", b"x"*48001):
            r=self.probe(body=raw,rec=receipt(raw))
            self.safety(r)
            self.assertEqual(r["state"],"LAB_CAD_BOC_RAW_CAPTURE_BLOCKED")

    def test_manual_collector_requires_single_fixed_exact_issuer_url(self):
        called=[]
        stamps=iter(("2026-11-13T01:30:00Z","2026-11-13T01:30:01Z"))
        def opener(request, *, timeout):
            called.append((request.full_url,timeout))
            return FakeResponse(self.body)
        body,meta=collect(open_url=opener,now_utc=lambda:next(stamps))
        self.assertEqual(called,[(URL,12)])
        self.assertEqual(body,self.body)
        self.assertEqual(meta["body_sha256"],sha256(self.body).hexdigest())
        r=self.probe(body=body,rec=meta)
        self.safety(r)
        self.assertEqual(r["state"],"LAB_CAD_BOC_ORIGINAL_BYTES_LOCALLY_CHECKED_NO_GO")

    def test_manual_collector_bounded_read_no_accept_oversize(self):
        def opener(request, *, timeout):
            return FakeResponse(b"x"*49000)
        with self.assertRaisesRegex(ValueError,"BOC_BODY_TOO_LARGE"):
            collect(open_url=opener,now_utc=lambda:"2026-11-13T01:30:00Z")

    def test_public_original_bytes_and_receipt_saved_only_under_isolated_lab(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            orig,rec=save(body=self.body,receipt=self.receipt,local_appdata=str(base))
            self.assertTrue(orig.exists())
            self.assertTrue(rec.exists())
            self.assertEqual(orig.read_bytes(),self.body)
            meta=json.loads(rec.read_text())
            self.assertEqual(meta["body_sha256"],sha256(orig.read_bytes()).hexdigest())
            self.assertIn("AtlasQuant",orig.parts)
            self.assertIn("LAB",orig.parts)
            with self.assertRaises(FileExistsError):
                save(body=self.body,receipt=self.receipt,local_appdata=str(base))
            self.assertEqual(orig.read_bytes(),self.body)


if __name__=="__main__":
    unittest.main()
