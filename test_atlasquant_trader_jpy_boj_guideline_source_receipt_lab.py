"""Synthetic BoJ policy guideline vs realized call market rate (offline LAB)."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from io import BytesIO
import json
import tempfile
from pathlib import Path
import unittest

from atlasquant_trader_jpy_boj_guideline_source_receipt_lab import (
    URL, STATEMENT_URL, MAX_BYTES,
    inspect_boj_home_guideline_receipt_lab as inspect,
)
from atlasquant_trader_jpy_boj_guideline_manual_capture_lab import (
    collect_boj_home_once_lab as collect,
    save_boj_home_in_lab as save,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 13, 10, 11, tzinfo=UTC)


def homepage(*, policy="1.25", deposit="1.25", loan="1.5",
             dissent="1.5", duplicate_policy=False,
             title="The Bank's Market Operations", footer=True):
    guideline = (
        "The Bank will encourage the uncollateralized overnight call rate "
        f"to remain at around {policy} percent."
    )
    # Rejected/dissent phrase outside market operations must never win.
    other = (
        "<p>A dissenting proposal around " + dissent +
        " percent was rejected and is NOT the guideline.</p>"
    )
    return (
        "<!doctype html><html><head><title>日本銀行 Bank of Japan</title>"
        "<script>fake source 7.00 percent</script></head><body>"
        "<h1>Bank of Japan</h1>" + other +
        "<section><h2>" + title + "</h2>"
        "<p>Uncollateralized Overnight Call Rate(average) %</p>"
        "<p>Interest Rate Applied to the Complementary Deposit Facility " +
        deposit + "% since September 24, 2026</p>"
        "<p>Basic Loan Rate " + loan + "% since September 24, 2026</p>"
        "<h3>Guideline</h3><p>" + guideline + "</p>" +
        (f"<p>{guideline}</p>" if duplicate_policy else "") +
        ("<a>Bank of Japan Operations</a>" if footer else "") +
        "</section></body></html>"
    ).encode("utf-8")


def receipt(body):
    return {
        "source_url": URL,
        "final_url": URL,
        "http_status": 200,
        "content_type": "text/html; charset=utf-8",
        "body_sha256": sha256(body).hexdigest(),
        "started_at_utc": "2026-11-13T10:09:59Z",
        "finished_at_utc": "2026-11-13T10:10:00Z",
        "https_validation_claim": True,
        "redirects_followed": False,
    }


class FakeResponse:
    def __init__(self, body):
        self.raw = BytesIO(body)
        self.status = 200
        self.headers = {"Content-Type": "text/html; charset=utf-8"}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.raw.close()
    def read(self, n=-1):
        return self.raw.read(n)
    def geturl(self):
        return URL


class BoJGuidelineReceiptTests(unittest.TestCase):
    def setUp(self):
        self.body = homepage()
        self.rec = receipt(self.body)

    def check(self, *, body=None, rec=None, now=NOW):
        return inspect(
            original_html=self.body if body is None else body,
            receipt=self.rec if rec is None else rec,
            decision_at_utc=now,
        )

    def safe(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["original_oct30_policy_pdf_bytes_captured"])
        self.assertFalse(r["oct30_issuer_release_time_independently_attested"])
        self.assertFalse(r["historic_first_seen_source_vintage_authenticated"])
        self.assertFalse(r["historical_boj_decision_cutoff_authenticated"])
        self.assertFalse(r["g8_policy_sources_complete"])
        self.assertFalse(r["fx28_bilateral_macro_authenticated"])
        self.assertFalse(r["dissent_or_rejected_proposal_used_as_policy"])
        self.assertFalse(r["realized_overnight_call_rate_used_as_policy_guideline"])
        self.assertIsNone(r["calibrated_directional_probability"])
        self.assertIsNone(r["validated_accuracy"])
        self.assertEqual(r["network_calls"], 0)
        self.assertEqual(r["files_written"], 0)
        self.assertEqual(r["new_cost_brl"], 0)

    def test_policy_is_guideline_while_deposit_and_loan_rates_separately_typed(self):
        out = self.check()
        self.safe(out)
        self.assertEqual(out["state"],
            "LAB_JPY_BOJ_CURRENT_GUIDELINE_HTML_LOCALLY_CHECKED_NO_GO")
        self.assertEqual(out["policy_guideline_target_pct_claim"], "1.25")
        self.assertEqual(out["complementary_deposit_pct_claim"], "1.25")
        self.assertEqual(out["basic_loan_rate_pct_claim"], "1.5")
        self.assertTrue(out["supplementary_rates_separately_typed"])
        self.assertTrue(out["visible_market_operations_guideline_parsed"])
        self.assertEqual(out["official_statement_reference_url"], STATEMENT_URL)
        self.assertTrue(out["html_sha256_matches_local_receipt"])

    def test_rejected_rate_on_page_does_not_become_operational_policy(self):
        body = homepage(dissent="2.75")
        out = self.check(body=body, rec=receipt(body))
        self.safe(out)
        self.assertEqual(out["policy_guideline_target_pct_claim"], "1.25")

    def test_policy_and_deposit_rate_not_forced_to_match(self):
        body = homepage(policy="1.25", deposit="1.00", loan="1.50")
        out = self.check(body=body, rec=receipt(body))
        self.safe(out)
        self.assertEqual(out["policy_guideline_target_pct_claim"], "1.25")
        self.assertEqual(out["complementary_deposit_pct_claim"], "1.00")

    def test_missing_market_heading_guideline_footer_or_ambiguous_repeat_blocks(self):
        for opts in (
            {"title": "Financial news"},
            {"footer": False},
            {"duplicate_policy": True},
            {"policy": "NaN"},
            {"deposit": "1e2"},
            {"loan": "40.0"},
        ):
            with self.subTest(opts=opts):
                body = homepage(**opts)
                out = self.check(body=body, rec=receipt(body))
                self.safe(out)
                self.assertEqual(out["state"],
                                 "LAB_JPY_BOJ_GUIDELINE_SOURCE_BLOCKED")

    def test_fake_host_redirect_http_status_or_contenttype_rejected(self):
        for k, v in (
            ("source_url", "https://www.boj.or.jp.evil.test/en/"),
            ("final_url", "https://other.test/"),
            ("http_status", 302),
            ("http_status", True),
            ("content_type", "application/pdf"),
            ("https_validation_claim", False),
            ("redirects_followed", True),
        ):
            with self.subTest(k=k):
                rec = deepcopy(self.rec)
                rec[k] = v
                out = self.check(rec=rec)
                self.safe(out)
                self.assertEqual(out["state"],
                                 "LAB_JPY_BOJ_GUIDELINE_SOURCE_BLOCKED")

    def test_body_change_cannot_fake_sha(self):
        body = self.body.replace(b"1.25 percent", b"1.50 percent", 1)
        r = self.check(body=body)
        self.safe(r)
        self.assertEqual(r["reason"], "BOJ_ORIGINAL_HTML_SHA256_MISMATCH")

    def test_after_decision_capture_does_not_become_point_in_time(self):
        for first, last in (
            ("2026-11-13T10:11:03Z", "2026-11-13T10:11:04Z"),
            ("2026-11-13T10:10:00Z", "2026-11-13T10:09:59Z"),
            ("2026-11-13T10:08:00Z", "2026-11-13T10:10:00Z"),
        ):
            with self.subTest(first=first, last=last):
                rec = deepcopy(self.rec)
                rec["started_at_utc"] = first
                rec["finished_at_utc"] = last
                out = self.check(rec=rec)
                self.safe(out)
                self.assertEqual(out["reason"],
                                 "BOJ_CAPTURE_CLOCK_AFTER_DECISION_OR_INVALID")

    def test_clock_naive_microseconds_and_malformed_receipt_rejected(self):
        for now in (NOW.replace(tzinfo=None), NOW.replace(microsecond=1)):
            out = self.check(now=now)
            self.safe(out)
            self.assertEqual(out["state"],
                             "LAB_JPY_BOJ_GUIDELINE_SOURCE_BLOCKED")
        rec = deepcopy(self.rec)
        rec["account_number"] = "private"
        out = self.check(rec=rec)
        self.safe(out)
        self.assertEqual(out["state"],
                         "LAB_JPY_BOJ_GUIDELINE_SOURCE_BLOCKED")

    def test_original_source_decoding_bad_or_oversized_blocks(self):
        for raw in (b"", b"x" * (MAX_BYTES + 1), self.body + b"\xff"):
            out = self.check(body=raw, rec=receipt(raw))
            self.safe(out)
            self.assertEqual(out["state"],
                             "LAB_JPY_BOJ_GUIDELINE_SOURCE_BLOCKED")

    def test_single_http_request_and_offline_replay(self):
        calls = []
        time = iter(("2026-11-13T10:09:59Z", "2026-11-13T10:10:00Z"))
        def opener(req, *, timeout):
            calls.append((req.full_url, timeout))
            return FakeResponse(self.body)
        raw, rec = collect(open_url=opener, now_utc=lambda: next(time))
        self.assertEqual(calls, [(URL, 12)])
        self.assertEqual(raw, self.body)
        self.assertEqual(rec["body_sha256"], sha256(self.body).hexdigest())
        check = self.check(body=raw, rec=rec)
        self.safe(check)
        self.assertEqual(check["state"],
                         "LAB_JPY_BOJ_CURRENT_GUIDELINE_HTML_LOCALLY_CHECKED_NO_GO")

    def test_save_public_bytes_only_in_isolated_lab_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            a, b = save(body=self.body, receipt=self.rec, local_appdata=td)
            self.assertEqual(a.read_bytes(), self.body)
            self.assertEqual(json.loads(b.read_text())["body_sha256"],
                             sha256(self.body).hexdigest())
            self.assertIn("LAB", a.parts)
            with self.assertRaises(FileExistsError):
                save(body=self.body, receipt=self.rec, local_appdata=td)

    def test_oversize_response_rejected_before_file_write(self):
        def opener(req, *, timeout):
            return FakeResponse(b"z" * (MAX_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "RESPONSE_TOO_LARGE"):
            collect(open_url=opener, now_utc=lambda: "2026-11-13T10:10:00Z")

    def test_today_page_claim_cannot_attest_october_statement_release(self):
        out = self.check()
        self.safe(out)
        self.assertTrue(out["boJ_current_policy_source_current_only"])
        self.assertFalse(out["oct30_issuer_release_time_independently_attested"])
        self.assertIsNone(out["calibrated_directional_probability"])


if __name__ == "__main__":
    unittest.main()
