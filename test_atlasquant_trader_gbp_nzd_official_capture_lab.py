"""No-network, temporary-directory tests for an official HTTP byte collector."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
import json
import unittest

from atlasquant_trader_gbp_nzd_official_capture_lab import (
    MAX_BYTES, TARGETS, SameHostHttpsRedirect,
    capture_one_lab, verify_capture_directory_lab,
)


RAW = b"Offline synthetic HTML fixture. This is not official publisher data. " * 5


class FakeResponse:
    def __init__(self, url, *, body=RAW, media="text/html; charset=UTF-8", status=200,
                 final=None):
        self.status = status
        self.body = body
        self.url = final or url
        self.headers = {
            "Content-Type": media,
            "Date": format_datetime(datetime.now(timezone.utc), usegmt=True),
            "Last-Modified": "Mon, 02 Nov 2026 12:00:00 GMT",
        }

    def read(self, max_bytes):
        return self.body[:max_bytes]

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class FakeOpener:
    def __init__(self, **kwargs):
        self.options = kwargs
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        return FakeResponse(request.full_url, **self.options)


class OfficialHttpCaptureTests(unittest.TestCase):
    def test_https_four_official_documents_pinned(self):
        self.assertEqual(len(TARGETS), 4)
        self.assertEqual({key.split("_")[0] for key in TARGETS}, {"GBP", "NZD"})
        self.assertTrue(all(url.startswith("https://") for url in TARGETS.values()))

    def test_byte_capture_creates_exclusive_files_and_readback_manifest(self):
        with TemporaryDirectory() as tmp:
            opener = FakeOpener()
            receipt = capture_one_lab("GBP_CPI_2026_09", Path(tmp), opener=opener)
            self.assertEqual(receipt["snapshot_bytes"], len(RAW))
            self.assertTrue(receipt["local_readback_hash_matched"])
            self.assertIsInstance(receipt["local_clock_minus_server_date_seconds"], int)
            self.assertFalse(receipt["historical_vintage_at_original_release_verified"])
            self.assertFalse(receipt["independent_timestamp_authority_verified"])
            self.assertFalse(receipt["trade_authorized"])
            self.assertEqual((Path(tmp) / receipt["snapshot_filename"]).read_bytes(), RAW)
            manifest = Path(tmp) / (receipt["snapshot_filename"] + ".receipt.json")
            self.assertEqual(json.loads(manifest.read_text())["snapshot_sha256"], receipt["snapshot_sha256"])
            self.assertEqual(verify_capture_directory_lab(Path(tmp))["status"], "LOCAL_INTEGRITY_PASS")
            self.assertEqual(opener.requests[0][0].get_method(), "GET")

    def test_modification_of_one_raw_byte_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)
            receipt = capture_one_lab("NZD_CPI_2026_Q3", path, opener=FakeOpener())
            body = path / receipt["snapshot_filename"]
            changed = bytearray(body.read_bytes())
            changed[10] ^= 1
            body.write_bytes(changed)
            result = verify_capture_directory_lab(path)
            self.assertEqual(result["status"], "LOCAL_INTEGRITY_FAIL")
            self.assertEqual(result["failed"], 1)
            self.assertFalse(result["historical_backtest_authorized"])

    def test_missing_receipt_is_an_explicitly_unvalidated_orphan(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)
            receipt = capture_one_lab("GBP_BANK_RATE_2026_11", path, opener=FakeOpener())
            (path / (receipt["snapshot_filename"] + ".receipt.json")).unlink()
            result = verify_capture_directory_lab(path)
            self.assertEqual(result["status"], "LOCAL_INTEGRITY_FAIL")
            self.assertEqual(result["failures"][0]["error"], "ORPHAN_SNAPSHOT_NO_RECEIPT")

    def test_empty_folder_is_not_a_pass(self):
        with TemporaryDirectory() as tmp:
            r = verify_capture_directory_lab(Path(tmp))
            self.assertEqual(r["status"], "LOCAL_NO_RECEIPTS")
            self.assertEqual(r["matched"], 0)

    def test_unknown_document_not_requested(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                capture_one_lab("USD_NOT_ALLOWED", Path(tmp), opener=FakeOpener())

    def test_wrong_http_status_refused_before_file_write(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                capture_one_lab("GBP_CPI_2026_09", Path(tmp), opener=FakeOpener(status=403))
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_non_html_response_refused(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                capture_one_lab("NZD_CPI_2026_Q3", Path(tmp), opener=FakeOpener(media="application/zip"))

    def test_bounded_download_refuses_oversized_payload(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                capture_one_lab("NZD_OCR_2026_10", Path(tmp),
                                opener=FakeOpener(body=b"x" * (MAX_BYTES + 20)))
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_empty_or_truncated_source_refused(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                capture_one_lab("GBP_CPI_2026_09", Path(tmp), opener=FakeOpener(body=b"small"))

    def test_cross_host_redirect_refused(self):
        from urllib.request import Request
        original = Request(TARGETS["GBP_CPI_2026_09"])
        with self.assertRaises(HTTPError):
            SameHostHttpsRedirect().redirect_request(
                original, None, 302, "Found", {}, "https://not-the-official-source.example/path")

    def test_https_to_http_downgrade_refused(self):
        from urllib.request import Request
        original = Request(TARGETS["GBP_CPI_2026_09"])
        with self.assertRaises(HTTPError):
            SameHostHttpsRedirect().redirect_request(
                original, None, 302, "Found", {}, "http://www.ons.gov.uk/path")

    def test_unique_filename_cannot_be_overwritten(self):
        with TemporaryDirectory() as tmp:
            opener = FakeOpener()
            first = capture_one_lab("NZD_OCR_2026_10", Path(tmp), opener=opener)
            body_path = Path(tmp) / first["snapshot_filename"]
            self.assertEqual(body_path.read_bytes(), RAW)
            # A second captured version with the same timestamp and digest is
            # not allowed to replace an existing source file.
            from unittest.mock import patch
            fixed = datetime(2026, 11, 8, 3, 0, tzinfo=timezone.utc)
            with patch("atlasquant_trader_gbp_nzd_official_capture_lab._now_utc", return_value=fixed):
                second = capture_one_lab("GBP_CPI_2026_09", Path(tmp), opener=opener)
                with self.assertRaises(FileExistsError):
                    capture_one_lab("GBP_CPI_2026_09", Path(tmp), opener=opener)
            self.assertEqual((Path(tmp) / second["snapshot_filename"]).read_bytes(), RAW)
            self.assertEqual(verify_capture_directory_lab(Path(tmp))["matched"], 2)

    def test_manifest_traversal_attempt_is_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)
            r = capture_one_lab("NZD_OCR_2026_10", path, opener=FakeOpener())
            receipt = path / (r["snapshot_filename"] + ".receipt.json")
            obj = json.loads(receipt.read_text())
            obj["snapshot_filename"] = "../outside.html"
            receipt.write_text(json.dumps(obj))
            self.assertEqual(verify_capture_directory_lab(path)["status"], "LOCAL_INTEGRITY_FAIL")


if __name__ == "__main__":
    unittest.main()
