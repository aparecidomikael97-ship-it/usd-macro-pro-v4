"""Offline CPI HTML capture/replay tests: ALL HTTP responses are mocks."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from urllib.error import HTTPError

from atlasquant_trader_us_oct2026_cpi_original_capture_once_lab import (
    RECEIPT_SCHEMA, URL, capture_cpi_oct2026_original_once_lab as capture,
    replay_cpi_oct2026_original_lab as replay,
)
from test_atlasquant_trader_us_oct2026_cpi_release_text_guard_lab import raw

UTC = timezone.utc
BEGIN = datetime(2026, 11, 15, 21, 0, tzinfo=UTC)
FINISH = BEGIN + timedelta(seconds=2)


class Response:
    def __init__(self, *, body=None, status=200, url=URL,
                 mime="text/html; charset=utf-8", encoding="identity",
                 length=None):
        self.body=raw() if body is None else body
        self.status=status
        self.url=url
        self.headers={
            "Content-Type": mime,
            "Content-Encoding": encoding,
            "Content-Length": str(len(self.body) if length is None else length),
        }
        self.read_calls=0
    def geturl(self):
        return self.url
    def read(self, limit):
        self.read_calls+=1
        return self.body[:limit]
    def __enter__(self):
        return self
    def __exit__(self,*a):
        return False


class FakeHTTP:
    def __init__(self, response=None, failure=None):
        self.response=Response() if response is None else response
        self.failure=failure
        self.calls=0
    def __call__(self, request, *, timeout):
        self.calls+=1
        assert self.calls <= 1, "RETRY_FORBIDDEN"
        assert request.full_url == URL
        assert request.get_method() == "GET"
        assert timeout == 15
        assert request.get_header("Accept-encoding") == "identity"
        if self.failure:
            raise self.failure
        return self.response


def clock():
    stamps=iter((BEGIN, FINISH))
    return lambda: next(stamps)


class CpiOneOffCaptureLabTests(unittest.TestCase):
    def safe(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["first_release_original_independently_attested"])
        self.assertFalse(r["publisher_first_seen_clock_independently_attested"])
        self.assertFalse(r["macro_surprise_qualified"])
        self.assertFalse(r["month_oct2026_yoy_available"])
        self.assertFalse(r["original_672_campaign_slots_modified"])
        self.assertIsNone(r["fx_direction"])
        self.assertIsNone(r["validated_fx_accuracy"])

    def run_capture(self, directory, *, response=None, opted=True,
                    failure=None, timer=None):
        fake=FakeHTTP(response=response, failure=failure)
        r=capture(allow_one_get=opted, output_root=directory,
                  open_url=fake, clock=timer or clock())
        self.safe(r)
        return r,fake

    def test_01_requires_explicit_opt_in_no_get_no_files(self):
        with TemporaryDirectory() as td:
            r,f=self.run_capture(td,opted=False)
            self.assertEqual((f.calls,r["capture_get_attempts"]),(0,0))
            self.assertFalse(r["original_local_replayed"])
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_02_real_format_fixture_captures_single_get_and_replays(self):
        with TemporaryDirectory() as td:
            r,f=self.run_capture(td)
            self.assertEqual((f.calls,r["capture_get_attempts"]),(1,1))
            self.assertTrue(r["original_local_replayed"])
            self.assertEqual(r["documentary_headline_sa_mom_pct"],"0.4")
            self.assertEqual(r["documentary_core_sa_mom_pct"],"0.3")
            folder=Path(td)/r["archive_directory_basename"]
            self.assertEqual((folder/"original.html").read_bytes(),raw())
            meta=json.loads((folder/"receipt.json").read_text())
            self.assertEqual(meta["schema"],RECEIPT_SCHEMA)
            self.assertEqual(meta["body_bytes"],len(raw()))
            self.assertEqual(meta["source_url"],URL)
            self.assertFalse(meta["original_available_at_release_independently_attested"])
            self.assertEqual(replay(output_root=td, archive_basename=folder.name,
                                    as_of_utc=FINISH)["original_local_replayed"],True)

    def test_03_mutated_original_bytes_replay_fails(self):
        with TemporaryDirectory() as td:
            r,_=self.run_capture(td)
            file=Path(td)/r["archive_directory_basename"]/"original.html"
            file.write_bytes(file.read_bytes()+b"tampered")
            check=replay(output_root=td,archive_basename=r["archive_directory_basename"],
                         as_of_utc=FINISH)
            self.assertFalse(check["original_local_replayed"])
            self.safe(check)

    def test_04_mutated_receipt_hash_replay_fails(self):
        with TemporaryDirectory() as td:
            r,_=self.run_capture(td)
            file=Path(td)/r["archive_directory_basename"]/"receipt.json"
            meta=json.loads(file.read_text())
            meta["body_sha256"]="f"*64
            file.write_text(json.dumps(meta))
            check=replay(output_root=td,archive_basename=r["archive_directory_basename"],
                         as_of_utc=FINISH)
            self.assertFalse(check["original_local_replayed"])
            self.safe(check)

    def test_05_duplicate_receipt_key_refused(self):
        with TemporaryDirectory() as td:
            r,_=self.run_capture(td)
            file=Path(td)/r["archive_directory_basename"]/"receipt.json"
            meta=file.read_text()
            file.write_text(meta.replace('"schema":', '"schema":"FAKE","schema":'))
            check=replay(output_root=td,archive_basename=r["archive_directory_basename"],
                         as_of_utc=FINISH)
            self.assertFalse(check["original_local_replayed"])
            self.safe(check)

    def test_06_redirect_final_url_not_official_fails_without_writing(self):
        with TemporaryDirectory() as td:
            r,f=self.run_capture(td,response=Response(url="https://example.com/cpi"))
            self.assertEqual(f.calls,1)
            self.assertFalse(r["original_local_replayed"])
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_07_http403_fails_no_fallback_no_artifact(self):
        with TemporaryDirectory() as td:
            r,f=self.run_capture(td,failure=HTTPError(URL,403,"Forbidden",{},None))
            self.assertEqual(f.calls,1)
            self.assertEqual(r["reason"],"BLS_GET_OR_LOCAL_CAPTURE_FAILED_NO_FALLBACK")
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_08_fake_html_is_not_original_cpi_evidence(self):
        with TemporaryDirectory() as td:
            r,_=self.run_capture(td,response=Response(body=b"<html>2026 CPI 0.4</html>"))
            self.assertEqual(r["reason"],"BLS_HTTP_OR_BODY_SIZE_OR_CAPTURE_TIME_INVALID")
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_09_html_large_but_without_official_document_id_rejected(self):
        with TemporaryDirectory() as td:
            r,_=self.run_capture(td,response=Response(body=b"<html>fake CPI 0.4</html>"*100))
            self.assertEqual(r["reason"],"BLS_CPI_BODY_SEMANTIC_PARSER_REJECTED")
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_10_wrong_cpi_identifier_is_rejected(self):
        with TemporaryDirectory() as td:
            r,_=self.run_capture(td,response=Response(
                body=raw().replace(b"USDL-26-1685",b"USDL-99-9999")))
            self.assertEqual(r["reason"],"BLS_CPI_BODY_SEMANTIC_PARSER_REJECTED")

    def test_11_encoded_transfer_without_identity_rejected(self):
        with TemporaryDirectory() as td:
            r,_=self.run_capture(td,response=Response(encoding="gzip"))
            self.assertEqual(r["reason"],"BLS_HTTP_OR_BODY_SIZE_OR_CAPTURE_TIME_INVALID")

    def test_12_content_length_mismatch_rejected(self):
        with TemporaryDirectory() as td:
            r,_=self.run_capture(td,response=Response(length=333))
            self.assertEqual(r["reason"],"BLS_HTTP_OR_BODY_SIZE_OR_CAPTURE_TIME_INVALID")

    def test_13_wrong_mime_type_rejected(self):
        with TemporaryDirectory() as td:
            r,_=self.run_capture(td,response=Response(mime="application/json"))
            self.assertEqual(r["reason"],"BLS_HTTP_OR_BODY_SIZE_OR_CAPTURE_TIME_INVALID")

    def test_14_pre_release_clock_blocks_get(self):
        timer=lambda: datetime(2026,11,10,13,29,59,tzinfo=UTC)
        with TemporaryDirectory() as td:
            r,f=self.run_capture(td,timer=timer)
            self.assertEqual(f.calls,0)
            self.assertEqual(r["reason"],"INVALID_OR_PRE_RELEASE_CAPTURE_CLOCK")

    def test_15_future_cutoff_does_not_expose_replayed_bytes(self):
        with TemporaryDirectory() as td:
            r,_=self.run_capture(td)
            earlier=replay(output_root=td,archive_basename=r["archive_directory_basename"],
                           as_of_utc=FINISH-timedelta(seconds=1))
            self.assertFalse(earlier["original_local_replayed"])
            self.safe(earlier)

    def test_16_path_traversal_archive_name_refused(self):
        with TemporaryDirectory() as td:
            out=replay(output_root=td,archive_basename="../malicious",
                       as_of_utc=FINISH)
            self.assertFalse(out["original_local_replayed"])
            self.safe(out)

    def test_17_oversized_document_blocked_without_file(self):
        with TemporaryDirectory() as td:
            r,_=self.run_capture(td,response=Response(body=b"x"*(2*1024*1024+1)))
            self.assertEqual(r["reason"],"BLS_HTTP_OR_BODY_SIZE_OR_CAPTURE_TIME_INVALID")
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_18_invalid_output_directory_no_get(self):
        fake=FakeHTTP()
        out=capture(allow_one_get=True, output_root="/this-dir-does-not-exist/abc",
                    open_url=fake,clock=clock())
        self.safe(out)
        self.assertEqual(fake.calls,0)

    def test_19_capture_clock_end_less_than_start_fails(self):
        ticks=iter((FINISH, BEGIN))
        with TemporaryDirectory() as td:
            r,_=self.run_capture(td,timer=lambda:next(ticks))
            self.assertEqual(r["reason"],"BLS_HTTP_OR_BODY_SIZE_OR_CAPTURE_TIME_INVALID")

    def test_20_source_claim_cannot_establish_pre_event_first_seen(self):
        with TemporaryDirectory() as td:
            r,_=self.run_capture(td)
            self.assertTrue(r["original_local_replayed"])
            self.assertFalse(r["first_release_original_independently_attested"])
            self.assertFalse(r["consensus_pre_release_authenticated"])
            self.assertFalse(r["macro_surprise_qualified"])

    def test_21_no_cpi_2026_yoy_made_up_from_2025_missing_base(self):
        with TemporaryDirectory() as td:
            r,_=self.run_capture(td)
            self.assertIsNone(r["fx_direction"])
            self.assertFalse(r["month_oct2026_yoy_available"])
            self.assertIsNone(r["validated_fx_accuracy"])

    def test_22_closed_capture_state_no_live_trading(self):
        with TemporaryDirectory() as td:
            r,f=self.run_capture(td)
            self.assertEqual(f.calls,1)
            self.safe(r)


if __name__ == "__main__":
    unittest.main()
