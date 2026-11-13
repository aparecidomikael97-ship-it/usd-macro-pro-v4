"""One-off PPI collection tests with SYNTHETIC BLS HTML; no network."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from contextlib import redirect_stdout
import io
import json
import unittest

from atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    OFFICIAL_URL, RELEASE_UTC, MAX_BYTES,
)
from atlasquant_trader_us_ppi_oct2026_original_capture_lab import (
    SCHEMA, capture_oct2026_bls_original_once_lab as capture,
    replay_oct2026_bls_original_capture_lab as replay,
    main,
)
from test_atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import raw

UTC = timezone.utc
START = datetime(2026, 11, 13, 14, 0, tzinfo=UTC)
FINISH = START + timedelta(seconds=2)


class MockResponse:
    def __init__(self, body=None, status=200, url=OFFICIAL_URL,
                 mime="text/html; charset=UTF-8", encoding="identity"):
        self.payload = raw() if body is None else body
        self.status = status
        self.endpoint = url
        self.headers = {
            "Content-Type": mime, "Content-Encoding": encoding}
        self.count = 0
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def geturl(self):
        return self.endpoint
    def read(self, limit):
        self.count += 1
        assert limit == MAX_BYTES+1
        return self.payload


class BLSOriginalPpiCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.read = Mock(return_value=MockResponse())
        self.times = Mock(side_effect=[START, FINISH])

    def call(self, *, allow=True, root=None, read=None, times=None):
        return capture(
            allow_one_get=allow,
            local_appdata=self.temp.name if root is None else root,
            open_url=self.read if read is None else read,
            clock=self.times if times is None else times,
        )

    def folder(self, result):
        return (Path(self.temp.name)/"AtlasQuant"/"LAB"/
                "official_macro_receipts"/result["archive_directory_basename"])

    def safe(self, result):
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        for k in ("trade_authorized","publishable","live_alert_allowed",
                  "worker_enabled","scheduler_enabled",
                  "release_first_seen_independently_verified",
                  "bls_issuer_independently_authenticated",
                  "release_pit_vintage_authenticated",
                  "independent_pre_event_consensus_attested",
                  "original_source_licensed_for_redistribution",
                  "ppi_can_feed_fx28_directional_model"):
            self.assertFalse(result[k],k)
        self.assertIsNone(result["economic_impact_points"])
        self.assertIsNone(result["usd_directional_bias"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertTrue(result["post_event_retrieval_not_pre_event_forecast"])
        self.assertEqual(result["new_cost_brl"],0)

    def test_01_default_no_explicit_permission_is_zero_network_and_files(self):
        r = self.call(allow=False)
        self.safe(r)
        self.assertEqual(r["reason"], "EXPLICIT_ALLOW_ONE_GET_REQUIRED")
        self.assertEqual(r["capture_get_attempts"], 0)
        self.assertEqual(r["source_file_writes_attempted"],0)
        self.read.assert_not_called()
        self.assertFalse((Path(self.temp.name)/"AtlasQuant").exists())

    def test_02_valid_one_get_creates_original_bytes_and_sha_receipt(self):
        r = self.call()
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_US_PPI_OCT2026_BLS_RAW_BYTES_REPLAYED_LOCAL_ONLY_NO_GO")
        self.assertEqual(r["capture_get_attempts"],1)
        self.assertEqual(r["source_file_writes_attempted"],2)
        self.assertTrue(r["directory_created_once"])
        self.assertTrue(r["raw_bytes_and_receipt_replayed"])
        self.assertTrue(r["source_original_locally_retained_claim_only"])
        self.assertTrue(r["ppi_can_feed_research_only"])
        self.assertEqual(r["raw_document_sha256"],sha256(raw()).hexdigest())
        self.assertEqual(r["raw_document_bytes"],len(raw()))
        folder = self.folder(r)
        self.assertEqual((folder/"original.html").read_bytes(),raw())
        meta = json.loads((folder/"receipt.json").read_text())
        self.assertEqual(meta["raw_sha256"], sha256(raw()).hexdigest())
        self.assertEqual(meta["body_bytes"],len(raw()))
        self.assertEqual(meta["source_url"],OFFICIAL_URL)
        self.assertEqual(meta["status_code"],200)
        self.read.assert_called_once()
        req = self.read.call_args.args[0]
        self.assertEqual(req.full_url,OFFICIAL_URL)
        self.assertEqual(req.get_method(),"GET")
        self.assertEqual(self.read.call_args.kwargs["timeout"],15)

    def test_03_explicit_second_pass_replays_without_network(self):
        saved = self.call()
        result = replay(
            local_appdata=self.temp.name,
            archive_basename=saved["archive_directory_basename"],
            observed_at_utc=FINISH + timedelta(days=1))
        self.safe(result)
        self.assertEqual(result["state"],
                         "LAB_US_PPI_OCT2026_BLS_RAW_BYTES_REPLAYED_LOCAL_ONLY_NO_GO")
        self.assertEqual(result["capture_get_attempts"],0)
        self.assertTrue(result["raw_bytes_and_receipt_replayed"])
        self.read.assert_called_once()

    def test_04_same_timestamp_and_source_cannot_overwrite_a_prior_archive(self):
        first = self.call()
        path = self.folder(first)/"original.html"
        first_bytes = path.read_bytes()
        second = self.call(times=Mock(side_effect=[START,FINISH]))
        self.safe(second)
        self.assertEqual(second["state"],
                         "LAB_US_PPI_OCT2026_ORIGINAL_CAPTURE_BLOCKED")
        self.assertEqual(second["capture_get_attempts"],1)
        self.assertEqual(second["source_file_writes_attempted"],0)
        self.assertEqual(path.read_bytes(),first_bytes)
        self.assertEqual(self.read.call_count,2)

    def test_05_mutated_original_byte_replay_fails_closed(self):
        first = self.call()
        path=self.folder(first)/"original.html"
        path.write_bytes(raw()+b"tampered")
        result=replay(local_appdata=self.temp.name,
                      archive_basename=first["archive_directory_basename"],
                      observed_at_utc=FINISH)
        self.safe(result)
        self.assertFalse(result["raw_bytes_and_receipt_replayed"])
        self.assertFalse(result["ppi_can_feed_research_only"])

    def test_06_mutated_receipt_sha_replay_fails_closed(self):
        first = self.call()
        path = self.folder(first)/"receipt.json"
        obj=json.loads(path.read_text())
        obj["raw_sha256"] = "f"*64
        path.write_text(json.dumps(obj))
        result=replay(local_appdata=self.temp.name,
                      archive_basename=first["archive_directory_basename"],
                      observed_at_utc=FINISH)
        self.safe(result)
        self.assertFalse(result["raw_bytes_and_receipt_replayed"])

    def test_07_duplicate_receipt_json_keys_rejected(self):
        first=self.call()
        path=self.folder(first)/"receipt.json"
        good=path.read_text()
        body=good[:-2]+',"status_code":200}\n'
        path.write_text(body)
        result=replay(local_appdata=self.temp.name,
                      archive_basename=first["archive_directory_basename"],
                      observed_at_utc=FINISH)
        self.safe(result)
        self.assertFalse(result["raw_bytes_and_receipt_replayed"])

    def test_08_unsafe_paths_do_not_start_public_get(self):
        for candidate in ("","relative",True,42,"/nonexistent-atlasquant-2026"):
            with self.subTest(root=candidate):
                r=self.call(root=candidate)
                self.safe(r)
                self.assertEqual(r["capture_get_attempts"],0)
        self.read.assert_not_called()

    def test_09_symlinked_lab_folder_no_network_or_write(self):
        parent=Path(self.temp.name)
        real=parent/"storage";real.mkdir()
        (parent/"AtlasQuant").symlink_to(real,target_is_directory=True)
        r=self.call()
        self.safe(r)
        self.assertEqual(r["capture_get_attempts"],0)
        self.assertEqual(list(real.iterdir()),[])
        self.read.assert_not_called()

    def test_10_non200_redirect_wrong_mime_or_gzip_blocks(self):
        changes=[
            {"status":403},
            {"status":302},
            {"url":"https://bls.invalid/news.release"},
            {"mime":"text/plain"},
            {"encoding":"gzip"},
        ]
        for case in changes:
            with self.subTest(case=case):
                fake=Mock(return_value=MockResponse(**case))
                r=self.call(read=fake,times=Mock(side_effect=[START,FINISH]))
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_US_PPI_OCT2026_ORIGINAL_CAPTURE_BLOCKED")
                self.assertEqual(r["capture_get_attempts"],1)
                self.assertEqual(r["source_file_writes_attempted"],0)
        self.assertFalse((Path(self.temp.name)/"AtlasQuant").exists())

    def test_11_oversized_payload_and_non_blssource_rejected(self):
        for payload in (b"x"*(MAX_BYTES+1),b"",b"<html>Fake CPI</html>"):
            with self.subTest(size=len(payload)):
                response=MockResponse(body=payload)
                r=self.call(read=Mock(return_value=response),
                            times=Mock(side_effect=[START,FINISH]))
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_US_PPI_OCT2026_ORIGINAL_CAPTURE_BLOCKED")
                self.assertEqual(r["source_file_writes_attempted"],0)

    def test_12_time_before_release_and_clock_rewind_block_no_fallback(self):
        before=RELEASE_UTC-timedelta(seconds=1)
        a=self.call(times=Mock(side_effect=[before, FINISH]))
        self.safe(a)
        self.assertEqual(a["capture_get_attempts"],0)
        self.read.assert_not_called()
        bad=self.call(times=Mock(side_effect=[START,START-timedelta(seconds=1)]))
        self.safe(bad)
        self.assertEqual(bad["capture_get_attempts"],1)
        self.assertEqual(bad["source_file_writes_attempted"],0)

    def test_13_fetch_exception_never_retries(self):
        r=self.call(read=Mock(side_effect=OSError("simulated 403")))
        self.safe(r)
        self.assertEqual(r["capture_get_attempts"],1)
        self.assertEqual(r["source_file_writes_attempted"],0)

    def test_14_replay_wrong_directory_name_and_clock_cannot_recover_data(self):
        r=self.call()
        for name in (None,"../other",r["archive_directory_basename"].lower(),
                     r["archive_directory_basename"]+"_foo"):
            with self.subTest(name=name):
                report=replay(local_appdata=self.temp.name,
                              archive_basename=name,observed_at_utc=FINISH)
                self.safe(report)
                self.assertFalse(report["raw_bytes_and_receipt_replayed"])
        before = replay(local_appdata=self.temp.name,
                        archive_basename=r["archive_directory_basename"],
                        observed_at_utc=START)
        self.safe(before)
        self.assertFalse(before["raw_bytes_and_receipt_replayed"])

    def test_15_partial_write_does_not_autoreplace(self):
        with patch("atlasquant_trader_us_ppi_oct2026_original_capture_lab.os.fsync",
                   side_effect=OSError("simulated crash")):
            first = self.call()
        self.safe(first)
        self.assertTrue(first["directory_created_once"])
        self.assertEqual(first["source_file_writes_attempted"],1)
        archived = self.folder(first)
        self.assertTrue(archived.exists())
        later = self.call(times=Mock(side_effect=[START,FINISH]))
        self.safe(later)
        self.assertEqual(later["state"],
                         "LAB_US_PPI_OCT2026_ORIGINAL_CAPTURE_BLOCKED")
        self.assertEqual(later["source_file_writes_attempted"],0)
        self.assertTrue(archived.exists())

    def test_16_default_cli_without_flag_does_not_touch_network(self):
        with patch("atlasquant_trader_us_ppi_oct2026_original_capture_lab.capture_oct2026_bls_original_once_lab") as fetch:
            data=io.StringIO()
            with redirect_stdout(data):
                code=main([])
            self.assertEqual(code,2)
            fetch.assert_not_called()
            report=json.loads(data.getvalue())
            self.safe(report)
            self.assertEqual(report["capture_get_attempts"],0)

    def test_17_explicit_cli_performs_only_chosen_mode(self):
        mock=Mock(return_value={
            "raw_bytes_and_receipt_replayed":False,
            "state":"LAB_US_PPI_OCT2026_ORIGINAL_CAPTURE_BLOCKED"})
        with patch("atlasquant_trader_us_ppi_oct2026_original_capture_lab.capture_oct2026_bls_original_once_lab",
                   mock):
            with redirect_stdout(io.StringIO()):
                code=main(["--capture-official"])
        self.assertEqual(code,2)
        self.assertEqual(mock.call_args.kwargs["allow_one_get"],True)
        self.assertEqual(mock.call_count,1)

    def test_18_source_retention_cannot_validate_fx_direction_accuracy(self):
        r=self.call()
        self.safe(r)
        self.assertFalse(r["release_first_seen_independently_verified"])
        self.assertFalse(r["ppi_can_feed_fx28_directional_model"])
        self.assertIsNone(r["economic_impact_points"])
        self.assertIsNone(r["calibrated_probability"])

    def test_19_valid_checksum_but_swapped_bls_release_body_rejected(self):
        bad=raw().replace(
            b"PRODUCER PRICE INDEXES - OCTOBER 2026",
            b"PRODUCER PRICE INDEXES - SEPTEMBER 2026")
        response=MockResponse(body=bad)
        r=self.call(read=Mock(return_value=response))
        self.safe(r)
        self.assertEqual(r["source_file_writes_attempted"],0)

    def test_20_replay_consistent_but_retrospective_data_only(self):
        r=self.call()
        report=replay(local_appdata=self.temp.name,
                      archive_basename=r["archive_directory_basename"],
                      observed_at_utc=FINISH+timedelta(days=4))
        self.safe(report)
        self.assertTrue(report["raw_bytes_and_receipt_replayed"])
        self.assertTrue(report["ppi_can_feed_research_only"])
        self.assertFalse(report["post_event_retrieval_not_pre_event_forecast"] is False)

if __name__=="__main__":
    unittest.main()
