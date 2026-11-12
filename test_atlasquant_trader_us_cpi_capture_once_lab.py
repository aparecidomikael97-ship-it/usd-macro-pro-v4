"""Network-free tests: fake HTTPS replies, real only-in-temp files."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from atlasquant_trader_us_cpi_capture_once_lab import (
    PREVIOUS_ID, CONSENSUS_ID, SOURCE_CONFIG,
    capture_us_cpi_document_once_lab as capture,
    verify_us_cpi_local_pair_lab as verify,
)


UTC = timezone.utc
START = datetime(2026, 11, 9, 12, 0, 0, tzinfo=UTC)
FINISH = START + timedelta(seconds=2)
INSPECT = FINISH + timedelta(minutes=30)
RAW = b"SYNTHETIC HTML FIXTURE FOR TESTING, NEVER AN OFFICIAL SOURCE" * 3


class FakeReply:
    def __init__(self, url, *, body=RAW, status=200, media="text/html",
                 encoding="identity", final=None, length=None):
        self.status = status
        self.url = url if final is None else final
        self.body = body
        self.headers = {"Content-Type": media, "Content-Encoding": encoding}
        if length is not None:
            self.headers["Content-Length"] = length

    def geturl(self):
        return self.url

    def read(self, limit):
        return self.body[:limit]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def open(self, request, *, timeout):
        self.calls.append((request.full_url, request.get_method(), timeout,
                           request.get_header("Accept-encoding")))
        return self.response


class CaptureOnceTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)

    def one(self, source_id=PREVIOUS_ID, *, response=None, manual=True,
            start=START, finish=FINISH, folder=None):
        endpoint = SOURCE_CONFIG[source_id][0] if source_id in SOURCE_CONFIG else ""
        opener = FakeOpener(response or FakeReply(endpoint))
        times = iter((start, finish))
        result = capture(source_id, output_dir=self.folder if folder is None else folder,
                         manual_one_shot=manual, opener=opener, clock=lambda: next(times))
        return result, opener

    def assert_never_tradable(self, result):
        self.assertFalse(result["publisher_origin_independently_attested"])
        self.assertFalse(result["collector_clock_independently_attested"])
        self.assertFalse(result["analyst_poll_methodology_verified"])
        self.assertFalse(result["document_numeric_contents_verified"])
        self.assertFalse(result["historical_pit_eligible"])
        self.assertFalse(result["ready_for_news_nowcast"])
        self.assertFalse(result["can_feed_live_radar"])
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["worker_enabled"])
        self.assertFalse(result["scheduler_enabled"])
        self.assertFalse(result["publishable"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")

    def test_no_opt_in_no_http_no_files(self):
        result, opener = self.one(manual=False)
        self.assertEqual(result["reason"], "EXPLICIT_MANUAL_ONE_SHOT_OPT_IN_REQUIRED")
        self.assertEqual(len(opener.calls), 0)
        self.assertEqual(list(self.folder.iterdir()), [])
        self.assert_never_tradable(result)

    def test_exactly_one_get_and_two_exclusive_files(self):
        result, opener = self.one()
        self.assertEqual(result["state"], "LAB_MANUAL_CAPTURE_SAVED_UNATTESTED")
        self.assertEqual(result["external_http_requests"], 1)
        self.assertEqual(result["file_writes"], 2)
        self.assertTrue(result["local_file_readback_matched"])
        self.assertEqual(opener.calls, [(SOURCE_CONFIG[PREVIOUS_ID][0], "GET", 12, "identity")])
        self.assertEqual(len(list(self.folder.iterdir())), 2)
        self.assertEqual((self.folder / result["local_snapshot_filename"]).read_bytes(), RAW)
        receipt = json.loads((self.folder / result["local_receipt_filename"]).read_text("utf-8"))
        self.assertEqual(receipt["source_id"], PREVIOUS_ID)
        self.assert_never_tradable(result)

    def test_readback_only_local_pair_matches_but_remains_unattested(self):
        result, _ = self.one()
        verified = verify(output_dir=self.folder,
                          snapshot_filename=result["local_snapshot_filename"],
                          as_of_utc=INSPECT, forecast_cutoff_utc=INSPECT)
        self.assertEqual(verified["state"], "LAB_LOCAL_RAW_AND_RECEIPT_HASH_MATCH_UNATTESTED")
        self.assertEqual(verified["external_http_requests"], 0)
        self.assertEqual(verified["body_sha256"], result["body_sha256"])
        self.assert_never_tradable(verified)

    def test_reuters_exact_article_only_stays_unverified(self):
        result, opener = self.one(CONSENSUS_ID)
        self.assertEqual(result["state"], "LAB_MANUAL_CAPTURE_SAVED_UNATTESTED")
        self.assertEqual(opener.calls[0][0], SOURCE_CONFIG[CONSENSUS_ID][0])
        self.assert_never_tradable(result)

    def test_pre_nov9_has_no_network_and_no_backdating(self):
        early = datetime(2026, 11, 8, 12, tzinfo=UTC)
        result, opener = self.one(start=early)
        self.assertEqual(result["reason"], "RESEARCH_WINDOW_NOT_OPEN_YET")
        self.assertEqual(len(opener.calls), 0)
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_wrong_destination_never_fetches(self):
        bad_dir = self.folder / "does-not-exist"
        result, opener = self.one(folder=bad_dir)
        self.assertEqual(result["reason"], "EXISTING_ISOLATED_REAL_FOLDER_REQUIRED")
        self.assertEqual(len(opener.calls), 0)

    def test_redirect_or_wrong_final_url_never_saved(self):
        url = SOURCE_CONFIG[PREVIOUS_ID][0]
        result, _ = self.one(response=FakeReply(url, final="https://evil.example/redirect"))
        self.assertEqual(result["reason"], "HTTP_URL_STATUS_OR_HEADER_MISMATCH")
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_wrong_status_headers_and_fake_length_not_saved(self):
        url = SOURCE_CONFIG[PREVIOUS_ID][0]
        cases = (FakeReply(url, status=404), FakeReply(url, status=True),
                 FakeReply(url, media="application/json"),
                 FakeReply(url, encoding="gzip"),
                 FakeReply(url, length="not-a-number"),
                 FakeReply(url, length=str(2 * 1024 * 1024)))
        for fake in cases:
            with self.subTest(case=str(fake.headers) + str(fake.status)):
                result, _ = self.one(response=fake)
                self.assertEqual(result["reason"], "HTTP_URL_STATUS_OR_HEADER_MISMATCH")
                self.assertEqual(list(self.folder.iterdir()), [])

    def test_length_mismatch_or_empty_body_not_saved(self):
        url = SOURCE_CONFIG[PREVIOUS_ID][0]
        for fake in (FakeReply(url, body=b""), FakeReply(url, body=RAW, length="999")):
            with self.subTest(length=fake.headers.get("Content-Length")):
                result, _ = self.one(response=fake)
                self.assertEqual(result["reason"], "HTTP_BODY_TOO_LARGE_EMPTY_OR_LENGTH_MISMATCH")
                self.assertEqual(list(self.folder.iterdir()), [])

    def test_oversized_http_body_not_saved(self):
        url = SOURCE_CONFIG[PREVIOUS_ID][0]
        result, _ = self.one(response=FakeReply(url, body=b"A" * (1024 * 1024 + 1)))
        self.assertEqual(result["reason"], "HTTP_BODY_TOO_LARGE_EMPTY_OR_LENGTH_MISMATCH")
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_second_identical_snapshot_cannot_overwrite_first(self):
        first, _ = self.one()
        second, _ = self.one()
        self.assertEqual(second["state"], "LAB_MANUAL_CAPTURE_BLOCKED")
        self.assertEqual(second["reason"], "CAPTURE_FAILED_FileExistsError")
        self.assertEqual(len(list(self.folder.iterdir())), 2)
        self.assertEqual((self.folder / first["local_snapshot_filename"]).read_bytes(), RAW)

    def test_tampered_snapshot_rejected_by_readback(self):
        result, _ = self.one()
        (self.folder / result["local_snapshot_filename"]).write_bytes(b"CORRUPT")
        checked = verify(output_dir=self.folder,
                         snapshot_filename=result["local_snapshot_filename"],
                         as_of_utc=INSPECT, forecast_cutoff_utc=INSPECT)
        self.assertEqual(checked["state"], "LAB_MANUAL_CAPTURE_BLOCKED")
        self.assert_never_tradable(checked)

    def test_changed_receipt_hash_rejected_by_readback(self):
        result, _ = self.one()
        path = self.folder / result["local_receipt_filename"]
        receipt = json.loads(path.read_text("utf-8"))
        receipt["captured_body_sha256"] = "f" * 64
        path.write_text(json.dumps(receipt), encoding="utf-8")
        checked = verify(output_dir=self.folder,
                         snapshot_filename=result["local_snapshot_filename"],
                         as_of_utc=INSPECT, forecast_cutoff_utc=INSPECT)
        self.assertEqual(checked["state"], "LAB_MANUAL_CAPTURE_BLOCKED")

    def test_post_release_capture_remains_research_only(self):
        start = datetime(2026, 11, 11, 12, tzinfo=UTC)
        result, _ = self.one(start=start, finish=start + timedelta(seconds=1))
        self.assertEqual(result["state"], "LAB_MANUAL_CAPTURE_SAVED_UNATTESTED")
        self.assertTrue(result["research_capture_after_release"])
        self.assert_never_tradable(result)

    def test_unknown_source_without_network_or_files(self):
        result = capture([PREVIOUS_ID], output_dir=self.folder, manual_one_shot=True)
        self.assertEqual(result["reason"], "UNKNOWN_SOURCE_ID")
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_invalid_naive_clock_never_saves_files(self):
        naive = datetime(2026, 11, 9, 12)
        result, opener = self.one(start=naive)
        self.assertEqual(result["reason"], "CAPTURE_FAILED_ValueError")
        self.assertEqual(len(opener.calls), 0)
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_traversal_filename_cannot_be_read_back(self):
        checked = verify(output_dir=self.folder, snapshot_filename="../stolen.html",
                         as_of_utc=INSPECT, forecast_cutoff_utc=INSPECT)
        self.assertEqual(checked["state"], "LAB_MANUAL_CAPTURE_BLOCKED")

    def test_pair_renamed_to_different_source_id_cannot_impersonate_it(self):
        result, _ = self.one()
        old = result["local_snapshot_filename"]
        wrong = old.replace(PREVIOUS_ID, CONSENSUS_ID, 1)
        (self.folder / old).rename(self.folder / wrong)
        (self.folder / (old + ".receipt.json")).rename(self.folder / (wrong + ".receipt.json"))
        checked = verify(output_dir=self.folder, snapshot_filename=wrong,
                         as_of_utc=INSPECT, forecast_cutoff_utc=INSPECT)
        self.assertEqual(checked["state"], "LAB_MANUAL_CAPTURE_BLOCKED")
        self.assert_never_tradable(checked)


if __name__ == "__main__":
    unittest.main()
