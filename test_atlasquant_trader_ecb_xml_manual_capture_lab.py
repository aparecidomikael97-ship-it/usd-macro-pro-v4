"""All network calls are fake; no real download, deployment or trading."""
from contextlib import redirect_stdout
from io import StringIO
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from atlasquant_trader_ecb_xml_manual_capture_lab import (
    SCHEMA, SOURCE_URL, MAX_BYTES,
    capture_ecb_xml_manual_lab as capture, main,
)
from test_atlasquant_trader_ecb_g8_xml_reference_history_lab import xml


class FakeResponse:
    def __init__(self, raw=None, *, status=200, url=SOURCE_URL,
                 content_type="text/xml; charset=utf-8", encoding="identity",
                 length=None):
        self.raw = xml() if raw is None else raw
        self.status = status
        self._url = url
        self.headers = {
            "Content-Type": content_type,
            "Content-Encoding": encoding,
        }
        if length is not None:
            self.headers["Content-Length"] = length

    def geturl(self):
        return self._url

    def read(self, limit):
        return self.raw[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeOpener:
    def __init__(self, response=None, error=None):
        self.response = response or FakeResponse()
        self.error = error
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if self.error:
            raise self.error
        return self.response


class ManualXmlCaptureTests(unittest.TestCase):
    def assert_no_go(self, out):
        for name in (
            "source_origin_independently_attested",
            "historical_publication_instant_attested",
            "archive_vintage_point_in_time_verified",
            "source_licensing_for_commercial_use_verified",
            "broker_m15_execution_prices_verified",
            "historical_accuracy_verified",
            "trade_authorized", "can_feed_live_radar", "worker_enabled",
            "scheduler_enabled", "publishable", "automated_schedule",
        ):
            self.assertIs(out[name], False, name)
        self.assertIsNone(out["fx_bias"])
        self.assertEqual(out["operational_bias"], "AGUARDAR")
        self.assertEqual(out["new_cost_brl"], 0)

    def test_no_opt_in_makes_zero_requests_and_zero_files(self):
        opener = FakeOpener()
        with tempfile.TemporaryDirectory() as d:
            out = capture(output_dir=d, opener=opener)
            self.assertEqual(out["state"], "LAB_BLOCKED")
            self.assertEqual(out["reason"], "EXPLICIT_MANUAL_ONE_SHOT_OPT_IN_REQUIRED")
            self.assertEqual(out["http_request_count"], 0)
            self.assertEqual(opener.calls, [])
            self.assertEqual(list(Path(d).iterdir()), [])
            self.assert_no_go(out)

    def test_one_manual_fake_response_saves_exact_bytes_and_json_receipt(self):
        body = xml()
        opener = FakeOpener(FakeResponse(body, length=str(len(body))))
        with tempfile.TemporaryDirectory() as d:
            out = capture(output_dir=d, manual_one_shot=True, opener=opener)
            self.assertEqual(out["schema"], SCHEMA)
            self.assertEqual(out["state"], "LAB_MANUAL_HTTP_SNAPSHOT_LOCAL_UNATTESTED")
            self.assertEqual(out["source_url"], SOURCE_URL)
            self.assertEqual(out["final_url"], SOURCE_URL)
            self.assertEqual(out["http_status"], 200)
            self.assertEqual(out["content_type"], "text/xml")
            self.assertEqual(out["body_sha256"], sha256(body).hexdigest())
            self.assertEqual(out["body_bytes"], len(body))
            self.assertTrue(out["explicit_manual_invocation"])
            self.assertEqual(out["http_request_count"], 1)
            self.assertFalse(out["default_tls_certificate_validation_requested"])
            self.assertEqual(len(opener.calls), 1)
            self.assertEqual(opener.calls[0][0].full_url, SOURCE_URL)
            self.assertEqual(opener.calls[0][1], 15)
            self.assertEqual(opener.calls[0][0].get_method(), "GET")
            self.assertEqual((Path(d) / out["snapshot_filename"]).read_bytes(), body)
            receipt = json.loads((Path(d) / out["receipt_filename"]).read_text())
            self.assertEqual(receipt, out)
            self.assertEqual(len(list(Path(d).iterdir())), 2)
            self.assert_no_go(out)

    def test_forged_xml_still_not_independently_verified(self):
        with tempfile.TemporaryDirectory() as d:
            out = capture(output_dir=d, manual_one_shot=True, opener=FakeOpener())
            self.assertEqual(out["state"], "LAB_MANUAL_HTTP_SNAPSHOT_LOCAL_UNATTESTED")
            self.assertFalse(out["source_origin_independently_attested"])
            self.assertFalse(out["historical_publication_instant_attested"])
            self.assertFalse(out["archive_vintage_point_in_time_verified"])
            self.assert_no_go(out)

    def test_no_silent_redirect_or_fake_domain_accepted(self):
        for url in ("https://example.org/fake.xml",
                    SOURCE_URL + "?query=unsafe", "http://www.ecb.europa.eu/"):
            with self.subTest(url=url), tempfile.TemporaryDirectory() as d:
                fake = FakeResponse(url=url)
                out = capture(output_dir=d, manual_one_shot=True,
                              opener=FakeOpener(fake))
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertEqual(list(Path(d).iterdir()), [])
                self.assert_no_go(out)

    def test_status_not_200_is_blocked(self):
        for status in (201, 302, 404, 503, True):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as d:
                out = capture(output_dir=d, manual_one_shot=True,
                              opener=FakeOpener(FakeResponse(status=status)))
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertEqual(list(Path(d).iterdir()), [])

    def test_html_or_other_content_type_blocked(self):
        for content_type in ("text/html", "application/json", "",
                             "application/octet-stream"):
            with self.subTest(content_type=content_type), tempfile.TemporaryDirectory() as d:
                out = capture(output_dir=d, manual_one_shot=True,
                              opener=FakeOpener(FakeResponse(content_type=content_type)))
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertEqual(list(Path(d).iterdir()), [])

    def test_gzip_or_transform_encoding_rejected(self):
        for encoding in ("gzip", "br", "deflate"):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as d:
                out = capture(output_dir=d, manual_one_shot=True,
                              opener=FakeOpener(FakeResponse(encoding=encoding)))
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertEqual(list(Path(d).iterdir()), [])

    def test_header_content_length_over_limit_rejected_before_body(self):
        with tempfile.TemporaryDirectory() as d:
            out = capture(output_dir=d, manual_one_shot=True,
                          opener=FakeOpener(FakeResponse(length=str(MAX_BYTES+1))))
            self.assertEqual(out["state"], "LAB_BLOCKED")
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_invalid_content_length_denied(self):
        for value in ("oops", "-1", "1.2", ""):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as d:
                out = capture(output_dir=d, manual_one_shot=True,
                              opener=FakeOpener(FakeResponse(length=value)))
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertEqual(list(Path(d).iterdir()), [])

    def test_body_over_limit_detected_even_without_length_header(self):
        content = xml() + b" " * MAX_BYTES
        with tempfile.TemporaryDirectory() as d:
            out = capture(output_dir=d, manual_one_shot=True,
                          opener=FakeOpener(FakeResponse(raw=content)))
            self.assertEqual(out["state"], "LAB_BLOCKED")
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_invalid_or_spoofed_xml_no_files(self):
        good = xml()
        samples = (
            b"", b"<html>Not ECB</html>", b"<?xml version='1.0'?><bad/>",
            good.replace(b"European Central Bank", b"Someone Else"),
            good.replace(b"Reference rates", b"Immediate trade"),
            b"<!DOCTYPE evil>" + good,
            b"<!ENTITY fake 'x'>" + good,
            b"\x00" + good,
            b"\xff" + good,
        )
        for raw in samples:
            with self.subTest(raw=raw[:20]), tempfile.TemporaryDirectory() as d:
                out = capture(output_dir=d, manual_one_shot=True,
                              opener=FakeOpener(FakeResponse(raw=raw)))
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertEqual(list(Path(d).iterdir()), [])

    def test_missing_directory_and_invalid_paths_no_http_request(self):
        with tempfile.TemporaryDirectory() as d:
            for dest in (None, "", 0, Path(d)/"does-not-exist"):
                opener = FakeOpener()
                out = capture(output_dir=dest, manual_one_shot=True, opener=opener)
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertEqual(opener.calls, [])

    def test_symlink_directory_denied_before_fetch(self):
        with tempfile.TemporaryDirectory() as d:
            real = Path(d)/"real"
            real.mkdir()
            symlink = Path(d)/"link"
            symlink.symlink_to(real, target_is_directory=True)
            opener = FakeOpener()
            out = capture(output_dir=symlink, manual_one_shot=True, opener=opener)
            self.assertEqual(out["state"], "LAB_BLOCKED")
            self.assertEqual(opener.calls, [])

    def test_network_error_keeps_no_partial_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            opener = FakeOpener(error=OSError("offline"))
            out = capture(output_dir=d, manual_one_shot=True, opener=opener)
            self.assertEqual(out["state"], "LAB_BLOCKED")
            self.assertEqual(out["reason"], "MANUAL_HTTP_OR_FILESYSTEM_FAILURE")
            self.assertEqual(list(Path(d).iterdir()), [])
            self.assert_no_go(out)

    def test_cli_without_manual_flag_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            output = StringIO()
            with redirect_stdout(output):
                status = main(["--output-dir", d])
            self.assertEqual(status, 2)
            report = json.loads(output.getvalue())
            self.assertEqual(report["http_request_count"], 0)
            self.assertEqual(report["state"], "LAB_BLOCKED")
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_no_worker_scheduler_market_result_in_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            out = capture(output_dir=d, manual_one_shot=True, opener=FakeOpener())
            self.assert_no_go(out)
            self.assertNotIn("accuracy", out)
            self.assertNotIn("signal", out)

if __name__ == "__main__":
    unittest.main()
