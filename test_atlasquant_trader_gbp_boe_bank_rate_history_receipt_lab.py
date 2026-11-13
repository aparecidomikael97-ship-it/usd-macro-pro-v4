"""Pure synthetic Bank of England Bank Rate source receipt regression tests."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from atlasquant_trader_gbp_boe_bank_rate_history_receipt_lab import (
    URL, MAX_BYTES, inspect_boe_bank_rate_history_receipt_lab as inspect,
)
from atlasquant_trader_gbp_boe_bank_rate_manual_capture_lab import (
    collect_boe_rate_once_lab as collect,
    save_boe_source_in_lab as save,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 13, 11, 0, tzinfo=UTC)


def original(*, rows=None, header=("Date Changed", "Rate"),
             current_label="Current official Bank Rate",
             extra_table="", preamble="Bank of England | Database"):
    if rows is None:
        rows = [("05 Nov 26", "4.00"),
                ("18 Dec 25", "3.75"),
                ("07 Aug 25", "4.00"),
                ("08 May 25", "4.25")]
    return (
        "<!DOCTYPE html><html><head><title>" + preamble +
        "</title></head><body><h1>" + current_label +
        "</h1><p>4%</p><h2>Official Bank Rate</h2>"
        "<table class='pubtables'><thead><tr><th>" +
        header[0] + "</th><th>" + header[1] +
        "</th></tr></thead><tbody>" +
        "".join(f"<tr><td>{day}</td><td>{rate}</td></tr>"
                for day, rate in rows) +
        "</tbody></table>" + extra_table + "</body></html>"
    ).encode("utf-8")


def receipt(body):
    return {
        "source_url": URL,
        "final_url": URL,
        "http_status": 200,
        "content_type": "text/html; charset=UTF-8",
        "body_sha256": sha256(body).hexdigest(),
        "started_at_utc": "2026-11-13T10:59:10Z",
        "finished_at_utc": "2026-11-13T10:59:11Z",
        "https_validation_claim": True,
        "redirects_followed": False,
    }


class FakeResponse:
    def __init__(self, body):
        self.stream = BytesIO(body)
        self.status = 200
        self.headers = {"Content-Type": "text/html; charset=utf-8"}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.stream.close()
    def read(self, count=-1):
        return self.stream.read(count)
    def geturl(self):
        return URL


class GBPBoERawRateTests(unittest.TestCase):
    def setUp(self):
        self.body = original()
        self.rec = receipt(self.body)

    def probe(self, *, body=None, rec=None, decision=NOW):
        return inspect(
            original_html=self.body if body is None else body,
            receipt=self.rec if rec is None else rec,
            decision_at_utc=decision,
        )

    def safety(self, result):
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["worker_enabled"])
        self.assertFalse(result["scheduler_enabled"])
        self.assertFalse(result["live_alert_allowed"])
        self.assertFalse(result["historical_issuer_first_release_verified"])
        self.assertFalse(result["issuer_decision_announcement_timestamp_verified"])
        self.assertFalse(result["policy_rate_first_seen_vintage_authenticated"])
        self.assertFalse(result["bank_rate_daily_series_IUDBEDR_crosschecked"])
        self.assertFalse(result["macro_cpi_bilateral_sources_complete"])
        self.assertFalse(result["g8_policy_rate_sources_complete"])
        self.assertIsNone(result["fx28_directional_probability"])
        self.assertIsNone(result["validated_signal_accuracy"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertEqual(result["network_calls"], 0)
        self.assertEqual(result["files_written"], 0)
        self.assertEqual(result["new_cost_brl"], 0)

    def test_official_change_history_can_keep_rate_change_separate_from_release(self):
        out = self.probe()
        self.safety(out)
        self.assertEqual(out["state"],
            "LAB_GBP_BOE_ORIGINAL_HISTORY_HTML_LOCALLY_CHECKED_NO_GO")
        self.assertTrue(out["raw_html_sha256_matches_receipt"])
        self.assertTrue(out["original_html_table_structure_consistent"])
        self.assertEqual(out["latest_bank_rate_pct_claim"], "4.00")
        self.assertEqual(out["last_change_effective_date_claim"], "2026-11-05")
        self.assertEqual(out["change_events_parsed"], 4)

    def test_past_rate_change_dates_do_not_imply_fomc_or_mpc_announcement_clock(self):
        out = self.probe()
        self.safety(out)
        self.assertIsNone(out["snapshot_finished_at_utc_claim"]
                          if out["state"].endswith("BLOCKED") else
                          out["fx28_directional_probability"])

    def test_fake_issuer_url_redirect_or_media_or_tls_claim_rejected(self):
        for key, value in (
            ("source_url", "https://www.bankofengland.co.uk.bad.test/boeapps/database/Bank-Rate.asp"),
            ("final_url", "https://evil.test/"),
            ("http_status", 302),
            ("http_status", True),
            ("content_type", "application/json"),
            ("https_validation_claim", False),
            ("redirects_followed", True),
        ):
            with self.subTest(field=key, bad=value):
                rec = deepcopy(self.rec)
                rec[key] = value
                out = self.probe(rec=rec)
                self.safety(out)
                self.assertEqual(out["reason"],
                                 "NONOFFICIAL_URL_HTTP_OR_TRANSPORT_CLAIM")

    def test_altered_html_original_detected_by_hash(self):
        bad = self.body.replace(b"4.00", b"3.50", 1)
        out = self.probe(body=bad)
        self.safety(out)
        self.assertEqual(out["reason"], "BOE_ORIGINAL_HTML_HASH_MISMATCH")

    def test_wrong_history_header_does_not_promote_monthly_rate(self):
        for header in (
            ("Month End", "Official Bank Rate"),
            ("Date Changed", "Monthly Average"),
        ):
            with self.subTest(header=header):
                body = original(header=header)
                out = self.probe(body=body, rec=receipt(body))
                self.safety(out)
                self.assertEqual(out["state"],
                                 "LAB_GBP_BOE_BANK_RATE_RECEIPT_BLOCKED")

    def test_two_history_tables_or_deleted_current_rate_heading_block(self):
        table = ("<table><tr><th>Date Changed</th><th>Rate</th></tr>"
                 "<tr><td>05 Nov 26</td><td>4.00</td></tr></table>")
        for kwargs in ({"extra_table": table},
                       {"current_label": "Some other interest rate"}):
            body = original(**kwargs)
            out = self.probe(body=body, rec=receipt(body))
            self.safety(out)
            self.assertEqual(out["state"],
                             "LAB_GBP_BOE_BANK_RATE_RECEIPT_BLOCKED")

    def test_change_rows_must_be_descending_and_unique(self):
        rows = [("18 Dec 25", "3.75"),
                ("05 Nov 26", "4.00")]
        for bad in (rows, [("05 Nov 26", "4.00"),
                           ("05 Nov 26", "4.00")]):
            body = original(rows=bad)
            out = self.probe(body=body, rec=receipt(body))
            self.safety(out)
            self.assertEqual(out["reason"],
                             "BOE_RATE_INVALID_FUTURE_DUPLICATE_OR_UNORDERED")

    def test_same_day_and_future_date_cannot_be_accepted_without_release_time(self):
        for date_text in ("13 Nov 26", "14 Nov 26", "31 Feb 26"):
            with self.subTest(date=date_text):
                body = original(rows=[
                    (date_text, "4.00"), ("18 Dec 25", "3.75")])
                out = self.probe(body=body, rec=receipt(body))
                self.safety(out)
                self.assertEqual(out["state"],
                                 "LAB_GBP_BOE_BANK_RATE_RECEIPT_BLOCKED")

    def test_rate_nan_infinity_exponent_or_out_of_range_rejected(self):
        for rate in ("NaN", "Infinity", "4e0", "-4.00",
                     "42.00", "4,00", "", "4.00000"):
            with self.subTest(rate=rate):
                body = original(rows=[
                    ("05 Nov 26", rate), ("18 Dec 25", "3.75")])
                out = self.probe(body=body, rec=receipt(body))
                self.safety(out)
                self.assertEqual(out["reason"],
                                 "BOE_RATE_INVALID_FUTURE_DUPLICATE_OR_UNORDERED")

    def test_untrusted_receipt_clock_future_or_long_capture_blocked(self):
        for first, last in (
            ("2026-11-13T11:01:00Z", "2026-11-13T11:01:01Z"),
            ("2026-11-13T10:59:20Z", "2026-11-13T10:59:10Z"),
            ("2026-11-13T10:57:00Z", "2026-11-13T10:59:11Z"),
            ("2026-11-13T10:59:10Z", "2026-11-13T11:00:01Z"),
        ):
            with self.subTest(start=first, end=last):
                rec = deepcopy(self.rec)
                rec["started_at_utc"] = first
                rec["finished_at_utc"] = last
                out = self.probe(rec=rec)
                self.safety(out)
                self.assertEqual(out["reason"],
                                 "CAPTURE_FUTURE_OR_CLOCK_INCOHERENT")

    def test_invalid_type_or_extra_receipt_fields_fail_closed(self):
        for changes in (
            {"http_status": 200.0},
            {"account_number": "private"},
            {"body_sha256": "missing"},
        ):
            rec = deepcopy(self.rec)
            rec.update(changes)
            out = self.probe(rec=rec)
            self.safety(out)
            self.assertEqual(out["state"],
                             "LAB_GBP_BOE_BANK_RATE_RECEIPT_BLOCKED")
        out = self.probe(decision=NOW.replace(tzinfo=None))
        self.safety(out)
        self.assertEqual(out["state"],
                         "LAB_GBP_BOE_BANK_RATE_RECEIPT_BLOCKED")

    def test_collector_mock_reads_once_and_only_fixed_official_address(self):
        calls = []
        times = iter(("2026-11-13T10:59:10Z", "2026-11-13T10:59:11Z"))
        def open_fake(req, *, timeout):
            calls.append((req.full_url, timeout))
            return FakeResponse(self.body)
        body, rec = collect(open_url=open_fake, now_utc=lambda: next(times))
        self.assertEqual(calls, [(URL, 12)])
        self.assertEqual(body, self.body)
        self.assertEqual(rec["body_sha256"], sha256(body).hexdigest())
        check = self.probe(body=body, rec=rec)
        self.safety(check)
        self.assertEqual(check["change_events_parsed"], 4)

    def test_collector_refuses_unbounded_response_and_double_write(self):
        def open_fake(req, *, timeout):
            return FakeResponse(b"x" * (MAX_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "EXCEEDS_LIMIT"):
            collect(open_url=open_fake,
                    now_utc=lambda: "2026-11-13T10:59:10Z")
        with tempfile.TemporaryDirectory() as td:
            a, b = save(body=self.body, receipt=self.rec, local_appdata=td)
            self.assertEqual(a.read_bytes(), self.body)
            self.assertEqual(json.loads(b.read_text())["body_sha256"],
                             sha256(self.body).hexdigest())
            self.assertIn("LAB", a.parts)
            with self.assertRaises(FileExistsError):
                save(body=self.body, receipt=self.rec, local_appdata=td)

    def test_missing_page_html_or_duplicate_timestamp_does_not_publish(self):
        for body in (b"", b"<html>no tables</html>",
                     original(rows=[("05 Nov 26", "4.00")])):
            out = self.probe(body=body, rec=receipt(body))
            self.safety(out)
            self.assertEqual(out["state"],
                             "LAB_GBP_BOE_BANK_RATE_RECEIPT_BLOCKED")


if __name__ == "__main__":
    unittest.main()
