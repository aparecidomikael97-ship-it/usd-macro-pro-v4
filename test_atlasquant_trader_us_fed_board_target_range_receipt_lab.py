"""Synthetic-only Federal Reserve Board 2026 target-range source gate tests."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from atlasquant_trader_us_fed_board_target_range_receipt_lab import (
    URL, MAX_BYTES, inspect_fed_board_policy_target_range_receipt_lab as inspect,
)
from atlasquant_trader_us_fed_board_target_range_manual_capture_lab import (
    collect_fed_board_range_once_lab as collect,
    save_fed_board_range_lab as save,
)

UTC=timezone.utc
NOW=datetime(2026,11,13,2,16,tzinfo=UTC)


def html_table(*, low="3.75", high="4.00", date="September 17",
               increase="25", decrease="0", headers=True,
               second_year=True) -> bytes:
    cols = ("<tr><th>Date</th><th>Increase</th><th>Decrease</th>"
            "<th>Level (%)</th></tr>" if headers else
            "<tr><th>Day</th><th>Increase</th><th>Decrease</th>"
            "<th>Level (%)</th></tr>")
    html = (
        "<!DOCTYPE html><html><head><title>Open Market Operations</title></head>"
        "<body><h1>Open Market Operations</h1>"
        "<h4>FOMC's target federal funds rate or range</h4>"
        "<p><a href='#2026'>2026</a></p>"
        "<p><a id='2026' name='2026'></a></p><h4>2026</h4>"
        "<div class='data-table'><table class='pubtables'>"
        "<thead>" + cols + "</thead><tbody>"
        f"<tr><td>{date}</td><td>{increase}</td><td>{decrease}</td>"
        f"<td>{low}-{high}</td></tr>"
        "</tbody></table></div>"
        + ("<p><a id='2025' name='2025'></a></p><h4>2025</h4>" if second_year else "")
        + "</body></html>"
    )
    return html.encode("utf-8")


def receipt(body: bytes) -> dict:
    return {
        "source_url":URL,"final_url":URL,"http_status":200,
        "content_type":"text/html; charset=utf-8",
        "body_sha256":sha256(body).hexdigest(),
        "started_at_utc":"2026-11-13T02:14:00Z",
        "finished_at_utc":"2026-11-13T02:14:01Z",
        "https_validation_claim":True,"redirects_followed":False,
    }


class FakeResponse:
    def __init__(self,body):
        self.stream=BytesIO(body);self.status=200
        self.headers={"Content-Type":"text/html; charset=utf-8"}
    def __enter__(self):return self
    def __exit__(self,*args):self.stream.close()
    def read(self,n=-1):return self.stream.read(n)
    def geturl(self):return URL


class FedTargetRangeReceiptTests(unittest.TestCase):
    def setUp(self):
        self.body=html_table()
        self.rec=receipt(self.body)

    def run_probe(self, body=None, rec=None, decision=NOW):
        return inspect(
            original_html=self.body if body is None else body,
            receipt=self.rec if rec is None else rec,
            decision_at_utc=decision)

    def safety(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["issuer_first_publication_time_independently_attested"])
        self.assertFalse(r["historical_point_in_time_source_vintage_authenticated"])
        self.assertFalse(r["current_rate_from_issuer_independently_authenticated"])
        self.assertFalse(r["eight_currencies_macro_complete"])
        self.assertFalse(r["bilateral_fx28_macro_data_complete"])
        self.assertFalse(r["actual_effective_federal_funds_rate_conflated"])
        self.assertTrue(r["target_range_not_compressed_to_midpoint"])
        self.assertTrue(r["effective_date_is_not_release_timestamp"])
        self.assertIsNone(r["calibrated_directional_probability"])
        self.assertIsNone(r["directional_bias"])
        self.assertIsNone(r["validated_forecast_accuracy"])
        self.assertEqual(r["http_requests"],0)
        self.assertEqual(r["files_written"],0)
        self.assertEqual(r["new_cost_brl"],0)

    def test_exact_fed_year_table_preserves_lower_and_upper_bounds(self):
        r=self.run_probe()
        self.safety(r)
        self.assertEqual(r["state"],
            "LAB_USD_FED_BOARD_ORIGINAL_HTML_LOCALLY_CHECKED_NO_GO")
        self.assertEqual(r["target_lower_pct_claim"],"3.75")
        self.assertEqual(r["target_upper_pct_claim"],"4.00")
        self.assertEqual(r["most_recent_effective_date_claim"],"2026-09-17")
        self.assertEqual(r["most_recent_change_increase_bp_claim"],25)
        self.assertEqual(r["most_recent_change_decrease_bp_claim"],0)
        self.assertEqual(r["change_rows_checked"],1)
        self.assertTrue(r["exact_html_sha256_verified_locally"])
        self.assertTrue(r["table_structure_issuer_claim_consistent"])

    def test_single_midpoint_or_reversed_target_range_rejected(self):
        for lower,upper in (
            ("3.875","4.00"),("4.00","3.75"),("3.75","3.75"),
            ("3.75","0.00"),("nan","4.00"),("3.75","Infinity"),
            ("-1.00","0.00"),("100.00","100.01"),
        ):
            with self.subTest(lower=lower,upper=upper):
                body=html_table(low=lower,high=upper)
                r=self.run_probe(body=body,rec=receipt(body))
                self.safety(r)
                self.assertEqual(r["state"],"LAB_FED_BOARD_TARGET_RANGE_RECEIPT_BLOCKED")

    def test_fake_federal_reserve_subdomain_status_redirect_contenttype(self):
        for field,val in (
            ("source_url","https://www.federalreserve.gov.evil.test/monetarypolicy/openmarket.htm"),
            ("final_url","https://other.test/monetarypolicy/openmarket.htm"),
            ("http_status",302),("redirects_followed",True),
            ("https_validation_claim",False),("content_type","text/html-fake"),
        ):
            with self.subTest(field=field):
                rec=deepcopy(self.rec);rec[field]=val
                r=self.run_probe(rec=rec)
                self.safety(r)
                self.assertEqual(r["reason"],"NONOFFICIAL_URL_STATUS_OR_TRANSPORT_CLAIM")

    def test_hash_mismatch_if_html_table_changes(self):
        raw=self.body.replace(b"3.75-4.00",b"3.50-4.00",1)
        r=self.run_probe(body=raw)
        self.safety(r)
        self.assertEqual(r["reason"],"FED_ORIGINAL_HTML_SHA256_MISMATCH")

    def test_no_year_anchor_header_change_or_no_2025_boundary_block(self):
        for body in (
            html_table(headers=False),
            html_table(second_year=False),
            self.body.replace(b"id='2026'",b"id='2027'",1),
            self.body.replace(b"class='pubtables'",b"class='other'",1),
            self.body.replace(b"Open Market Operations",b"Fake Market Page"),
        ):
            with self.subTest(size=len(body)):
                r=self.run_probe(body=body,rec=receipt(body))
                self.safety(r)
                self.assertEqual(r["state"],"LAB_FED_BOARD_TARGET_RANGE_RECEIPT_BLOCKED")

    def test_duplicate_year_anchor_and_extra_pubtables_rejected(self):
        body=self.body.replace(
            b"<p><a id='2025'",
            b"<a id='2026'></a><p><a id='2025'",1)
        r=self.run_probe(body=body,rec=receipt(body))
        self.safety(r)
        self.assertEqual(r["state"],"LAB_FED_BOARD_TARGET_RANGE_RECEIPT_BLOCKED")
        body=self.body.replace(b"</tbody></table>",
            b"</tbody></table><table class='pubtables'><tr><td>evil</td></tr></table>",1)
        r=self.run_probe(body=body,rec=receipt(body))
        self.safety(r)
        self.assertEqual(r["state"],"LAB_FED_BOARD_TARGET_RANGE_RECEIPT_BLOCKED")

    def test_future_or_same_day_effective_date_not_used_without_intraday_release(self):
        for date_text in ("November 13","November 14","December 1"):
            with self.subTest(effective=date_text):
                body=html_table(date=date_text)
                r=self.run_probe(body=body,rec=receipt(body))
                self.safety(r)
                self.assertEqual(
                    r["reason"],"FED_RANGE_ROW_UNORDERED_DUPLICATE_FUTURE_OR_FORMAT_INVALID")

    def test_fomc_change_row_cannot_be_zero_both_or_increase_and_decrease(self):
        for increase,decrease in (("0","0"),("25","25"),("...","0"),("25","...")):
            body=html_table(increase=increase,decrease=decrease)
            r=self.run_probe(body=body,rec=receipt(body))
            self.safety(r)
            self.assertEqual(r["state"],"LAB_FED_BOARD_TARGET_RANGE_RECEIPT_BLOCKED")

    def test_malformed_receipt_clock_future_timestamp_not_allowed(self):
        for field,val in (
            ("started_at_utc","2026-11-13T02:15:00Z"),
            ("finished_at_utc","2026-11-13T02:16:01Z"),
            ("finished_at_utc","2026-11-14T02:14:01Z"),
            ("finished_at_utc","bad"),
        ):
            with self.subTest(field=field,val=val):
                rec=deepcopy(self.rec);rec[field]=val
                r=self.run_probe(rec=rec)
                self.safety(r)
                if field=="started_at_utc":
                    self.assertEqual(r["reason"],"FED_HTTP_OBSERVATION_AFTER_DECISION_OR_CLOCK_INVALID")
                else:
                    self.assertEqual(r["reason"],"FED_HTTP_OBSERVATION_AFTER_DECISION_OR_CLOCK_INVALID")

    def test_naive_clock_or_oversized_body_fails_before_parsing(self):
        for decision in (NOW.replace(tzinfo=None),NOW.replace(microsecond=1)):
            r=self.run_probe(decision=decision)
            self.safety(r)
            self.assertEqual(r["state"],"LAB_FED_BOARD_TARGET_RANGE_RECEIPT_BLOCKED")
        body=b"a"*(MAX_BYTES+1)
        r=self.run_probe(body=body,rec=receipt(body))
        self.safety(r)
        self.assertEqual(r["state"],"LAB_FED_BOARD_TARGET_RANGE_RECEIPT_BLOCKED")

    def test_not_a_genuine_2025_or_current_fomc_statement_vintage(self):
        r=self.run_probe()
        self.safety(r)
        self.assertIsNone(r["directional_bias"])
        self.assertFalse(r["issuer_first_publication_time_independently_attested"])
        self.assertEqual(r["currency"],"USD")
        self.assertEqual(r["instrument"],"FED_FUNDS_TARGET_RANGE")

    def test_collector_single_bounded_request_and_explicit_local_only_saving(self):
        opens=[]
        times=iter(("2026-11-13T02:14:00Z","2026-11-13T02:14:01Z"))
        def opener(req,*,timeout):
            opens.append((req.full_url,timeout))
            return FakeResponse(self.body)
        raw,rec=collect(open_url=opener,now_utc=lambda:next(times))
        self.assertEqual(opens,[(URL,12)])
        self.assertEqual(raw,self.body)
        self.assertEqual(rec["body_sha256"],sha256(self.body).hexdigest())
        checked=self.run_probe(body=raw,rec=rec)
        self.safety(checked)
        self.assertEqual(checked["state"],
            "LAB_USD_FED_BOARD_ORIGINAL_HTML_LOCALLY_CHECKED_NO_GO")
        with tempfile.TemporaryDirectory() as td:
            p,m=save(body=raw,receipt=rec,local_appdata=td)
            self.assertEqual(p.read_bytes(),self.body)
            self.assertEqual(json.loads(m.read_text())["body_sha256"],
                             sha256(self.body).hexdigest())
            self.assertIn("AtlasQuant",p.parts)
            self.assertIn("LAB",p.parts)
            with self.assertRaises(FileExistsError):
                save(body=raw,receipt=rec,local_appdata=td)

    def test_manual_collector_rejects_oversized_html(self):
        def opener(req,*,timeout):
            return FakeResponse(b"m"*(MAX_BYTES+10))
        with self.assertRaisesRegex(ValueError,"FED_HTML_BODY_TOO_LARGE"):
            collect(open_url=opener,now_utc=lambda:"2026-11-13T02:14:00Z")

    def test_schema_must_not_accept_account_number_or_float_http_status(self):
        rec=deepcopy(self.rec)
        rec["account_id"]="secret"
        r=self.run_probe(rec=rec)
        self.safety(r)
        self.assertEqual(r["state"],"LAB_FED_BOARD_TARGET_RANGE_RECEIPT_BLOCKED")
        rec=deepcopy(self.rec)
        rec["http_status"]=200.0
        r=self.run_probe(rec=rec)
        self.safety(r)
        self.assertEqual(r["state"],"LAB_FED_BOARD_TARGET_RANGE_RECEIPT_BLOCKED")

if __name__=="__main__":
    unittest.main()
