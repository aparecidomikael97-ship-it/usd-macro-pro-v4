"""Mock-only transport tests: never contact the ECB, FRED or brokers."""
from __future__ import annotations

from hashlib import sha256
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import atlasquant_trader_eurusd_policy_capture_once_lab as capture

ECB_RAW = (
    b"KEY,FREQ,REF_AREA,CURRENCY,TIME_PERIOD,OBS_VALUE,OBS_STATUS\n"
    b"FM.D.U2.EUR.4F.KR.DFR.LEV,D,U2,EUR,2025-06-11,2.0000000,A\n"
)
FED_RAW = (
    b"observation_date,DFEDTARL,DFEDTARU\n"
    b"2026-11-01,3.75,4.00\n"
)


class FakeResponse:
    def __init__(self, *, url, raw, content_type="text/csv", status=200,
                 encoding="identity", final_url=None):
        self.status = status
        self.url = final_url or url
        self.raw = raw
        self.headers = {
            "Content-Type": content_type,
            "Content-Encoding": encoding,
            "Date": "Thu, 05 Nov 2026 00:00:00 GMT",
            "Last-Modified": "Wed, 04 Nov 2026 00:00:00 GMT",
        }
        self.read_limit = None

    def geturl(self):
        return self.url

    def read(self, n):
        self.read_limit = n
        return self.raw[:n]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def open(self, request, *, timeout):
        self.calls.append((request, timeout))
        return self.response


class ManualPolicyCaptureTests(unittest.TestCase):
    def _run_fake(self, source, raw, folder, **response_options):
        url = capture.SOURCES[source][0]
        response = FakeResponse(url=url, raw=raw, **response_options)
        opener = FakeOpener(response)
        with patch.object(capture, "build_opener", return_value=opener):
            result = capture.capture_policy_csv_once_lab(
                source, manually_authorized=True, archive_dir=folder)
        return result, opener, response

    def test_no_opt_in_means_zero_requests(self):
        with patch.object(capture, "build_opener") as opening:
            result = capture.capture_policy_csv_once_lab(
                "ECB_EUR_DFR_EFFECTIVE", manually_authorized=False)
            opening.assert_not_called()
        self.assertEqual(result["reason"], "MANUAL_OPT_IN_REQUIRED")
        self.assertEqual(result["external_http_requests"], 0)

    def test_cli_does_not_request_network_without_explicit_flag(self):
        with TemporaryDirectory() as d, patch.object(capture, "build_opener") as opening:
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = capture.main(["--source", "ECB_EUR_DFR_EFFECTIVE",
                                     "--archive-dir", d])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(stdout.getvalue())["reason"],
                             "MANUAL_OPT_IN_REQUIRED")
            opening.assert_not_called()

    def test_requires_exact_source_and_existing_directory(self):
        with patch.object(capture, "build_opener") as opening:
            for source, timeout, folder in (
                ("unknown", 8, "/tmp"),
                ("ECB_EUR_DFR_EFFECTIVE", 0, "/tmp"),
                ("ECB_EUR_DFR_EFFECTIVE", True, "/tmp"),
                ("ECB_EUR_DFR_EFFECTIVE", 16, "/tmp"),
                ("ECB_EUR_DFR_EFFECTIVE", 8, None),
            ):
                with self.subTest(source=source, timeout=timeout, folder=folder):
                    out = capture.capture_policy_csv_once_lab(
                        source, manually_authorized=True, archive_dir=folder,
                        timeout_seconds=timeout)
                    self.assertEqual(out["state"], "LAB_CAPTURE_BLOCKED")
            opening.assert_not_called()

    def test_ecb_archive_contains_original_csv_and_receipt(self):
        with TemporaryDirectory() as d:
            out, opener, response = self._run_fake(
                "ECB_EUR_DFR_EFFECTIVE", ECB_RAW, d,
                content_type="application/vnd.ecb.data+csv;version=1.0.0")
            self.assertEqual(out["state"], "LAB_CAPTURE_PARSER_ACCEPTED_QUARANTINED")
            self.assertEqual(out["parser_state"],
                             "LAB_ECB_DFR_EFFECTIVE_LEVEL_QUARANTINED")
            self.assertEqual(out["raw_response_sha256"], sha256(ECB_RAW).hexdigest())
            self.assertEqual(out["external_http_requests"], 1)
            self.assertEqual(len(opener.calls), 1)
            self.assertEqual(opener.calls[0][0].full_url,
                             capture.SOURCES["ECB_EUR_DFR_EFFECTIVE"][0])
            self.assertEqual(response.read_limit, capture.MAX_BYTES + 1)
            path = Path(out["raw_snapshot_archive_path"])
            self.assertTrue(path.is_file())
            self.assertEqual(sha256(path.read_bytes()).hexdigest(),
                             out["raw_snapshot_archive_sha256"])
            with ZipFile(path) as z:
                self.assertEqual(z.read("response.csv"), ECB_RAW)
                receipt = json.loads(z.read("observation_receipt.json"))
                self.assertEqual(receipt["parser_receipt"]["rate_percent"], "2.0000000")
                self.assertIsNone(receipt["raw_snapshot_archive_path"])
                self.assertFalse(receipt["publication_instant_independently_verified"])

    def test_fed_range_capture_stays_quarantined(self):
        with TemporaryDirectory() as d:
            out, opener, _ = self._run_fake(
                "FED_USD_TARGET_RANGE_EFFECTIVE", FED_RAW, d,
                content_type="application/octet-stream")
            self.assertEqual(out["state"], "LAB_CAPTURE_PARSER_ACCEPTED_QUARANTINED")
            self.assertEqual(out["parser_receipt"]["upper_bound_percent"], "4.00")
            self.assertEqual(len(opener.calls), 1)
            self.assertFalse(out["consensus_before_decision_verified"])
            self.assertFalse(out["trade_authorized"])
            self.assertFalse(out["can_feed_live_radar"])
            self.assertFalse(out["worker_enabled"])
            self.assertFalse(out["scheduler_enabled"])
            self.assertEqual(out["new_cost_brl"], 0)

    def test_invalid_csv_archived_as_invalid_not_valid_rate(self):
        with TemporaryDirectory() as d:
            out, _opener, _ = self._run_fake(
                "ECB_EUR_DFR_EFFECTIVE", b"not,a,policy,rate\n", d)
            self.assertEqual(out["state"], "LAB_CAPTURE_RAW_FORMAT_REJECTED_QUARANTINED")
            self.assertEqual(out["parser_state"], "LAB_BLOCKED")
            self.assertFalse(out["trade_authorized"])
            with ZipFile(out["raw_snapshot_archive_path"]) as z:
                self.assertEqual(z.read("response.csv"), b"not,a,policy,rate\n")

    def test_http_status_redirect_and_media_fail_closed(self):
        for options in (
            {"status": 404},
            {"final_url": "https://example.net/redirected"},
            {"content_type": "text/html"},
            {"encoding": "gzip"},
        ):
            with self.subTest(options=options), TemporaryDirectory() as d:
                out, opener, _ = self._run_fake(
                    "ECB_EUR_DFR_EFFECTIVE", ECB_RAW, d, **options)
                self.assertEqual(out["state"], "LAB_CAPTURE_BLOCKED")
                self.assertIsNone(out["raw_snapshot_archive_path"])
                self.assertEqual(len(opener.calls), 1)
                self.assertEqual(list(Path(d).iterdir()), [])

    def test_oversized_or_null_body_rejected_before_archive(self):
        for raw in (b"x" * (capture.MAX_BYTES + 2), b"", ECB_RAW + b"\0"):
            with self.subTest(size=len(raw)), TemporaryDirectory() as d:
                out, _opener, response = self._run_fake(
                    "ECB_EUR_DFR_EFFECTIVE", raw, d)
                self.assertEqual(out["state"], "LAB_CAPTURE_BLOCKED")
                self.assertEqual(response.read_limit, capture.MAX_BYTES + 1)
                self.assertEqual(list(Path(d).iterdir()), [])

    def test_archive_directory_must_exist_no_implicit_mkdir(self):
        with TemporaryDirectory() as d:
            nowhere = Path(d) / "missing"
            with patch.object(capture, "build_opener") as opening:
                out = capture.capture_policy_csv_once_lab(
                    "ECB_EUR_DFR_EFFECTIVE", manually_authorized=True,
                    archive_dir=nowhere)
                opening.assert_not_called()
            self.assertEqual(out["reason"], "ARCHIVE_DIR_MISSING_OR_SYMLINK")
            self.assertFalse(nowhere.exists())

    def test_system_and_headers_are_not_independent_clock_evidence(self):
        with TemporaryDirectory() as d:
            out, _, _ = self._run_fake("ECB_EUR_DFR_EFFECTIVE", ECB_RAW, d)
            self.assertIn("http_date_header_claim", out)
            self.assertIn("observed_at_local_system_utc", out)
            self.assertFalse(out["source_origin_independently_authenticated"])
            self.assertFalse(out["historical_point_in_time_availability_verified"])
            self.assertIsNone(out["market_surprise_bps"])
            self.assertIsNone(out["fx_bias"])


if __name__ == "__main__":
    unittest.main()
