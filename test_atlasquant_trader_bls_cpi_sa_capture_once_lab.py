"""Mocked network tests; never contact api.bls.gov from the test suite."""
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.error import URLError
from zipfile import ZipFile

from atlasquant_trader_bls_cpi_sa_capture_once_lab import (
    capture_current_bls_sa_cpi_once_lab as capture,
)
from atlasquant_trader_bls_cpi_sa_previous_bridge_lab import API_URL, SERIES_ID


def valid_body():
    return json.dumps({
        "status": "REQUEST_SUCCEEDED", "message": [],
        "Results": {"series": [{"seriesID": SERIES_ID, "data": [
            {"year": "2026", "period": "M09", "value": "336.298", "latest": "true"},
            {"year": "2026", "period": "M08", "value": "334.131"},
        ]}]},
    }, separators=(",", ":")).encode()


class FakeResponse:
    def __init__(self, *, body=None, status=200, url=API_URL,
                 content_type="application/json", encoding="identity"):
        self.body = valid_body() if body is None else body
        self.status = status
        self.url = url
        self.headers = {"Content-Type": content_type, "Content-Encoding": encoding}
        self.read_calls = 0

    def geturl(self):
        return self.url

    def read(self, count):
        self.read_calls += 1
        return self.body[:count]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class BLSCaptureTests(unittest.TestCase):
    def assert_no_go(self, output):
        self.assertEqual(output["operational_bias"], "AGUARDAR")
        self.assertFalse(output["bls_first_print_actual_authenticated"])
        self.assertFalse(output["first_publication_timestamp_independently_verified"])
        self.assertFalse(output["consensus_before_release_authenticated"])
        self.assertFalse(output["published_headline_mom_verified"])
        self.assertIsNone(output["fx_bias"])
        self.assertIsNone(output["index_bias"])
        self.assertIsNone(output["calibrated_direction_probability"])
        self.assertFalse(output["trade_authorized"])
        self.assertFalse(output["publishable"])
        self.assertFalse(output["live_alert_allowed"])
        self.assertFalse(output["worker_enabled"])
        self.assertFalse(output["scheduler_enabled"])
        self.assertEqual(output["new_cost_brl"], 0)
        self.assertTrue(output["research_only"])

    def test_no_network_without_explicit_opt_in(self):
        with patch("atlasquant_trader_bls_cpi_sa_capture_once_lab.build_opener") as mocked:
            r = capture()
            mocked.assert_not_called()
        self.assertEqual(r["state"], "LAB_BLS_SA_CAPTURE_BLOCKED")
        self.assertEqual(r["http_requests"], 0)
        self.assert_no_go(r)

    def test_invalid_timeout_skips_network(self):
        with patch("atlasquant_trader_bls_cpi_sa_capture_once_lab.build_opener") as mocked:
            for value in (0, True, 16, 2.5, -3):
                r = capture(manually_authorized=True, timeout_seconds=value)
                self.assertEqual(r["http_requests"], 0)
            mocked.assert_not_called()

    def test_mocked_exactly_one_get_and_quarantined_response(self):
        response = FakeResponse()
        with patch("atlasquant_trader_bls_cpi_sa_capture_once_lab.build_opener") as mocked:
            mocked.return_value.open.return_value = response
            r = capture(manually_authorized=True)
            self.assertEqual(mocked.return_value.open.call_count, 1)
            request = mocked.return_value.open.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request.full_url, API_URL)
        self.assertEqual(response.read_calls, 1)
        self.assertEqual(r["state"], "LAB_BLS_SA_SINGLE_HTTP_RESPONSE_QUARANTINED")
        self.assertEqual(r["http_requests"], 1)
        self.assertEqual(r["file_writes"], 0)
        self.assertEqual(r["latest_index_month"], "2026-09")
        self.assertEqual(r["latest_mom_sa_percent_derived_documentary"], "0.6")
        self.assertEqual(r["response_sha256"], sha256(valid_body()).hexdigest())
        self.assertTrue(r["tls_system_ca_verification_requested"])
        self.assertTrue(r["no_redirects_requested"])
        self.assert_no_go(r)

    def test_archive_contains_exact_original_and_receipt(self):
        with TemporaryDirectory() as directory:
            with patch("atlasquant_trader_bls_cpi_sa_capture_once_lab.build_opener") as mocked:
                mocked.return_value.open.return_value = FakeResponse()
                r = capture(manually_authorized=True, archive_dir=directory)
            self.assertEqual(r["state"], "LAB_BLS_SA_RAW_RESPONSE_ARCHIVED_UNATTESTED")
            self.assertEqual(r["file_writes"], 1)
            archive = Path(r["raw_archive_path"])
            self.assertTrue(archive.is_file())
            self.assertEqual(sha256(archive.read_bytes()).hexdigest(),
                             r["raw_archive_sha256"])
            with ZipFile(archive) as zipped:
                self.assertEqual(zipped.read("response.json"), valid_body())
                receipt = json.loads(zipped.read("receipt.json"))
            self.assertEqual(receipt["raw_response_sha256"],
                             sha256(valid_body()).hexdigest())
            self.assertTrue(receipt["source_is_current_mutable_API"])
            self.assertFalse(receipt["bls_original_release_first_print_authenticated"])
            self.assert_no_go(r)

    def test_archive_folder_must_preexist(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "missing"
            with patch("atlasquant_trader_bls_cpi_sa_capture_once_lab.build_opener") as mocked:
                r = capture(manually_authorized=True, archive_dir=path)
                mocked.assert_not_called()
            self.assertEqual(r["http_requests"], 0)
            self.assertEqual(r["state"], "LAB_BLS_SA_CAPTURE_BLOCKED")
            self.assert_no_go(r)

    def test_invalid_archive_argument_does_not_start_http(self):
        with patch("atlasquant_trader_bls_cpi_sa_capture_once_lab.build_opener") as mocked:
            r = capture(manually_authorized=True, archive_dir=12345)
            mocked.assert_not_called()
        self.assertEqual(r["state"], "LAB_BLS_SA_CAPTURE_BLOCKED")
        self.assertEqual(r["http_requests"], 0)
        self.assert_no_go(r)

    def test_symlink_archive_folder_rejected_without_network(self):
        with TemporaryDirectory() as directory:
            link = Path(directory) / "link"
            link.symlink_to(Path(directory), target_is_directory=True)
            with patch("atlasquant_trader_bls_cpi_sa_capture_once_lab.build_opener") as mocked:
                r = capture(manually_authorized=True, archive_dir=link)
                mocked.assert_not_called()
            self.assertEqual(r["state"], "LAB_BLS_SA_CAPTURE_BLOCKED")

    def test_unexpected_status_url_media_or_encoding_blocked(self):
        for mutation in (
            {"status": 404}, {"url": API_URL + "?redirected=1"},
            {"content_type": "text/html"}, {"encoding": "gzip"},
        ):
            with self.subTest(mutation=mutation):
                with patch("atlasquant_trader_bls_cpi_sa_capture_once_lab.build_opener") as mocked:
                    mocked.return_value.open.return_value = FakeResponse(**mutation)
                    r = capture(manually_authorized=True)
                self.assertEqual(r["state"], "LAB_BLS_SA_CAPTURE_BLOCKED")
                self.assertEqual(r["http_requests"], 1)
                self.assert_no_go(r)

    def test_bls_json_parse_failure_not_promoted(self):
        with patch("atlasquant_trader_bls_cpi_sa_capture_once_lab.build_opener") as mocked:
            mocked.return_value.open.return_value = FakeResponse(body=b"{bad json")
            r = capture(manually_authorized=True)
        self.assertEqual(r["state"], "LAB_BLS_SA_CAPTURE_BLOCKED")
        self.assertEqual(r["http_requests"], 1)
        self.assert_no_go(r)

    def test_http_exception_fails_closed_no_retry(self):
        with patch("atlasquant_trader_bls_cpi_sa_capture_once_lab.build_opener") as mocked:
            mocked.return_value.open.side_effect = URLError("offline synthetic")
            r = capture(manually_authorized=True)
            self.assertEqual(mocked.return_value.open.call_count, 1)
        self.assertEqual(r["state"], "LAB_BLS_SA_CAPTURE_BLOCKED")
        self.assertTrue(r["reason"].startswith("HTTPS_FAILED_"))
        self.assert_no_go(r)


if __name__ == "__main__":
    unittest.main()
