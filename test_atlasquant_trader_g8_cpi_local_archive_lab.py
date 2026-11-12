"""Local temporary-file tests; no real HTTP, MT5, account or orders."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from atlasquant_trader_g8_cpi_http_probe_lab import HTTPProbeLabResult
from atlasquant_trader_g8_cpi_local_archive_lab import (
    archive_one_g8_cpi_current_page_lab as archive,
    verify_g8_cpi_current_archive_lab as verify,
)

URL = "https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-04112026-ap"
BODY = b"SYNTHETIC, NOT REAL EUROSTAT BYTES"


def fake_probe(body=BODY, *, url=URL, state="LAB_CURRENT_ISSUER_PAGE_HTTP_BYTES_CAPTURED_UNATTESTED"):
    report = {
        "state": state, "source_url_claim": url, "final_url_observed": url,
        "response_status": 200, "body_bytes": len(body),
        "body_sha256": sha256(body).hexdigest(), "content_type": "text/html",
        "response_date_header": "Tue, 10 Nov 2026 01:12:59 GMT",
        "last_modified_header": None,
        "local_started_utc_claim": "2026-11-10T01:12:51.008458+00:00",
        "local_finished_utc_claim": "2026-11-10T01:12:54.078503+00:00",
        "default_tls_verification_requested": False,
    }
    return HTTPProbeLabResult(report, body)


def invoke(path, *, currency="EUR", stage="FLASH", period="2026-10",
           url=URL, result=None):
    if result is None:
        result = fake_probe()
    return archive(currency, url, period, stage, directory=path,
                   probe=lambda currency, url: result)


class CPIArchiveLabTests(unittest.TestCase):
    def assert_no_go(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        for field in ("issuer_first_release_authenticated",
                      "clock_independently_authenticated",
                      "historical_point_in_time_eligible",
                      "economic_value_extracted", "trade_authorized",
                      "publishable", "scheduler_enabled", "worker_enabled"):
            self.assertFalse(r[field], field)
        self.assertEqual(r["new_cost_brl"], 0)

    def test_archive_and_reopen_two_original_synthetic_files(self):
        with tempfile.TemporaryDirectory() as directory:
            r = invoke(directory)
            self.assertEqual(r["state"], "LAB_CURRENT_CPI_ARCHIVE_CREATED_UNATTESTED")
            self.assertEqual(r["file_writes"], 2)
            self.assertEqual(r["body_sha256"], sha256(BODY).hexdigest())
            self.assertEqual(Path(r["body_path"]).read_bytes(), BODY)
            self.assertEqual(len(list(Path(directory).iterdir())), 2)
            with Path(r["manifest_path"]).open(encoding="utf-8") as f:
                manifest = json.load(f)
            self.assertEqual(manifest["source_url"], URL)
            self.assertFalse(manifest["historical_point_in_time_eligible"])
            reread = verify(r["manifest_path"])
            self.assertEqual(reread["state"],
                             "LAB_LOCAL_ARCHIVE_BYTES_SELF_CONSISTENT_UNATTESTED")
            self.assertTrue(reread["local_integrity_verified"])
            self.assert_no_go(r)
            self.assert_no_go(reread)

    def test_repeated_same_body_and_clock_cannot_overwrite_first_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            first = invoke(directory)
            second = invoke(directory)
            self.assertEqual(first["state"], "LAB_CURRENT_CPI_ARCHIVE_CREATED_UNATTESTED")
            self.assertEqual(second["reason"], "CAPTURE_NAME_COLLISION_NO_OVERWRITE")
            self.assertEqual(second["file_writes"], 0)
            self.assertEqual(Path(first["body_path"]).read_bytes(), BODY)
            self.assertEqual(len(list(Path(directory).iterdir())), 2)
            self.assert_no_go(second)

    def test_edited_captured_document_is_detected_by_reopening_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            r = invoke(directory)
            Path(r["body_path"]).write_bytes(b"tampered only in isolated test tempdir")
            check = verify(r["manifest_path"])
            self.assertEqual(check["state"], "LAB_ARCHIVE_BLOCKED")
            self.assert_no_go(check)

    def test_edited_manifest_hash_or_traversal_path_is_rejected(self):
        for field, value in (("body_sha256", "a" * 64),
                             ("body_filename", "../other.html"),
                             ("trade_authorized", True)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                r = invoke(directory)
                path = Path(r["manifest_path"])
                with path.open(encoding="utf-8") as f:
                    manifest = json.load(f)
                manifest[field] = value
                path.write_text(json.dumps(manifest), encoding="utf-8")
                check = verify(path)
                self.assertEqual(check["state"], "LAB_ARCHIVE_BLOCKED")
                self.assert_no_go(check)

    def test_wrong_currency_period_and_bad_destination_block_before_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            for currency, period, url in (("EUR", "2026-Q3", URL),
                                          ("NZD", "2026-10", URL),
                                          ("USD", "2026-10", URL),
                                          ([], "2026-10", URL)):
                with self.subTest(currency=currency):
                    r = invoke(directory, currency=currency, period=period, url=url)
                    self.assertEqual(r["state"], "LAB_ARCHIVE_BLOCKED")
                    self.assert_no_go(r)
            self.assertEqual(len(list(Path(directory).iterdir())), 0)
        r = invoke("Z:/nonexistent_dir_1000")
        self.assertEqual(r["state"], "LAB_ARCHIVE_BLOCKED")
        self.assert_no_go(r)

    def test_unavailable_http_probe_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            result = fake_probe(state="LAB_HTTPS_PROBE_BLOCKED")
            r = invoke(directory, result=result)
            self.assertEqual(r["reason"], "HTTP_PROBE_DID_NOT_RETURN_ACCEPTABLE_BYTES")
            self.assertEqual(len(list(Path(directory).iterdir())), 0)
            self.assert_no_go(r)

    def test_mutable_website_bytes_do_not_prove_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            first = invoke(directory, result=fake_probe(body=b"first"))
            second = invoke(directory, result=fake_probe(body=b"second"))
            self.assertNotEqual(first["body_sha256"], second["body_sha256"])
            self.assertEqual(len(list(Path(directory).iterdir())), 4)
            self.assertFalse(verify(first["manifest_path"])["issuer_first_release_authenticated"])
            self.assertFalse(verify(second["manifest_path"])["issuer_first_release_authenticated"])
            self.assert_no_go(first)
            self.assert_no_go(second)


if __name__ == "__main__":
    unittest.main()
