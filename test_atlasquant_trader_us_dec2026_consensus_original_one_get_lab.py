"""Offline one-GET tests for prospective CPI/PPI; mock HTTP only."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
import json
import unittest

from atlasquant_trader_us_dec2026_consensus_original_one_get_lab import (
    SCHEMA, capture_dec2026_one_get_original_lab as capture,
    replay_dec2026_one_get_original_lab as replay,
)
from atlasquant_trader_us_dec2026_pre_event_consensus_custody_lab import EVENTS

UTC=timezone.utc
CPI=EVENTS[0][0]
PPI=EVENTS[1][0]
RELEASE={root:utc for root,_,_,utc in EVENTS}
TD="https://economics.td.com/domains/economics.td.com/documents/reports/bottom-line/tables/2026-12-08/upcoming.htm"
TE="https://tradingeconomics.com/united-states/calendar"
MARK=datetime(2026,12,8,10,0,0,123456,tzinfo=UTC)


def data():
    return (b"<html><body>LAB SYNTHETIC TD / TE SOURCE CONSENSUS "
            +b"99.9% NOT AUTHENTICATED "*12+b"</body></html>")


class MockResponse:
    def __init__(self,*,url=TD,content=None,status=200,mime="text/html; charset=utf-8",
                 encoding="identity",date=None,length=None):
        self.url=url
        self.body=data() if content is None else content
        self.status=status
        self.headers={
            "Content-Type":mime,
            "Content-Encoding":encoding,
            "Date":date or format_datetime(MARK.replace(microsecond=0),usegmt=True),
            "Content-Length":str(len(self.body) if length is None else length),
        }
    def geturl(self):
        return self.url
    def read(self,max_bytes):
        return self.body[:max_bytes]
    def __enter__(self):
        return self
    def __exit__(self,*_):
        return False


class FakeHTTP:
    def __init__(self,response=None,error=None):
        self.response=response or MockResponse()
        self.error=error
        self.calls=[]
    def __call__(self,request,*,timeout):
        self.calls.append((request.full_url,request.get_method(),timeout,
                           request.get_header("Accept-encoding")))
        assert len(self.calls)==1, "NO_HTTP_RETRY"
        if self.error:
            raise self.error
        return self.response


def ticks(start=MARK,end=None):
    last=start+timedelta(seconds=1) if end is None else end
    seq=iter((start,last))
    return lambda:next(seq)


class DecOneGetOriginalTests(unittest.TestCase):
    def safe(self,out):
        self.assertEqual(out["schema"],SCHEMA)
        self.assertEqual(out["operational_bias"],"AGUARDAR")
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["publishable"])
        self.assertFalse(out["scheduler_enabled"])
        self.assertFalse(out["worker_enabled"])
        self.assertFalse(out["numerical_consensus_semantics_authenticated"])
        self.assertFalse(out["original_source_first_seen_independently_authenticated"])
        self.assertFalse(out["bls_schedule_independently_reconfirmed"])
        self.assertFalse(out["original_fx28_672_slots_modified"])
        self.assertIsNone(out["fx_direction"])
        self.assertIsNone(out["fx_accuracy"])
        self.assertIsNone(out["economic_surprise"])
        self.assertIsNone(out["official_actual"])

    def capture_one(self,root,*,event=CPI,provider="TD_ECONOMICS",url=TD,http=None,
                    optin=True,schedule=True,clock=None):
        fake=http or FakeHTTP(response=MockResponse(url=url))
        result=capture(
            allow_one_official_get=optin,
            confirm_bls_schedule_reviewed=schedule,
            event_root=event,provider=provider,source_url=url,
            output_root=root,open_url=fake,clock=clock or ticks())
        self.safe(result)
        return result,fake

    def test_01_no_explicit_opt_in_zero_network(self):
        with TemporaryDirectory() as td:
            out,fake=self.capture_one(td,optin=False)
            self.assertEqual(fake.calls,[])
            self.assertFalse(out["original_replayed_from_disk"])

    def test_02_schedule_not_manually_reviewed_zero_network(self):
        with TemporaryDirectory() as td:
            out,fake=self.capture_one(td,schedule=False)
            self.assertEqual(fake.calls,[])
            self.assertEqual(out["reason"],"EXPLICIT_CAPTURE_AND_SCHEDULE_REVIEW_OPT_IN_REQUIRED")

    def test_03_valid_td_one_get_original_file_sha_and_utc(self):
        with TemporaryDirectory() as td:
            out,fake=self.capture_one(td)
            self.assertTrue(out["original_replayed_from_disk"])
            self.assertEqual(len(fake.calls),1)
            self.assertEqual(fake.calls[0],(TD,"GET",15,"identity"))
            self.assertEqual(out["http_get_attempts"],1)
            self.assertEqual(out["source_original_bytes"],len(data()))
            self.assertEqual(out["source_original_sha256"],sha256(data()).hexdigest())
            folder=Path(td)/out["archive_basename"]
            self.assertEqual((folder/"original.html").read_bytes(),data())
            rec=json.loads((folder/"receipt.json").read_text("utf-8"))
            self.assertEqual(rec["finished_at_utc"],(MARK+timedelta(seconds=1)).isoformat())
            self.assertFalse(rec["numerical_consensus_semantics_authenticated"])
            self.assertTrue(replay(output_root=td,archive_basename=out["archive_basename"],
                                   research_cutoff_utc=MARK+timedelta(seconds=1))
                            ["original_replayed_from_disk"])

    def test_04_valid_trading_economics_one_get_not_a_forecast(self):
        with TemporaryDirectory() as td:
            out,fake=self.capture_one(td,provider="TRADING_ECONOMICS",url=TE)
            self.assertTrue(out["original_replayed_from_disk"])
            self.assertEqual(out["provider"],"TRADING_ECONOMICS")
            self.assertEqual(fake.calls[0][0],TE)
            self.assertFalse(out["numerical_consensus_semantics_authenticated"])

    def test_05_valid_ppi_one_get_inside_its_later_window(self):
        with TemporaryDirectory() as td:
            start=RELEASE[PPI]-timedelta(days=2)
            http=FakeHTTP(response=MockResponse(
                url=TE,date=format_datetime(start, usegmt=True)))
            out,fake=self.capture_one(td,event=PPI,provider="TRADING_ECONOMICS",
                                      url=TE,http=http,clock=ticks(start))
            self.assertTrue(out["original_replayed_from_disk"])
            self.assertEqual(out["event_root"],PPI)

    def test_06_td_2024_upcoming_doc_not_in_event_week(self):
        old=TD.replace("2026-12-08","2024-12-08")
        with TemporaryDirectory() as td:
            out,fake=self.capture_one(td,url=old)
            self.assertEqual(fake.calls,[])
            self.assertEqual(out["reason"],"UNSUPPORTED_EVENT_OR_PROVIDER_URL")

    def test_07_td_future_2027_edition_not_current_week(self):
        url=TD.replace("2026-12-08","2027-12-08")
        with TemporaryDirectory() as td:
            out,fake=self.capture_one(td,url=url)
            self.assertEqual(fake.calls,[])
            self.assertFalse(out["original_replayed_from_disk"])

    def test_08_unsanctioned_consensus_url_rejected_before_network(self):
        with TemporaryDirectory() as td:
            out,fake=self.capture_one(td,url="https://tradingeconomics.com/other")
            self.assertEqual(fake.calls,[])
            self.assertFalse(out["original_replayed_from_disk"])

    def test_09_unsupported_event_rejected_before_network(self):
        with TemporaryDirectory() as td:
            out,fake=self.capture_one(td,event="US_CPI_OCT2026")
            self.assertEqual(fake.calls,[])
            self.assertFalse(out["original_replayed_from_disk"])

    def test_10_capture_before_seven_day_window_zero_requests(self):
        with TemporaryDirectory() as td:
            start=RELEASE[CPI]-timedelta(days=8)
            out,fake=self.capture_one(td,clock=ticks(start))
            self.assertEqual(fake.calls,[])
            self.assertEqual(out["reason"],"PRE_EVENT_CAPTURE_WINDOW_NOT_OPEN_OR_ALREADY_FROZEN")

    def test_11_one_hour_freeze_boundary_allowed(self):
        with TemporaryDirectory() as td:
            start=RELEASE[CPI]-timedelta(hours=1,seconds=2)
            http=FakeHTTP(response=MockResponse(
                date=format_datetime(start.replace(microsecond=0),usegmt=True)))
            out,_=self.capture_one(td,clock=ticks(start),http=http)
            self.assertTrue(out["original_replayed_from_disk"])

    def test_12_one_second_after_freeze_blocks_before_get(self):
        with TemporaryDirectory() as td:
            start=RELEASE[CPI]-timedelta(hours=1)+timedelta(seconds=1)
            out,fake=self.capture_one(td,clock=ticks(start))
            self.assertEqual(fake.calls,[])
            self.assertFalse(out["original_replayed_from_disk"])

    def test_13_request_started_before_deadline_but_completed_after_blocks(self):
        with TemporaryDirectory() as td:
            start=RELEASE[CPI]-timedelta(hours=1,seconds=1)
            end=RELEASE[CPI]-timedelta(hours=1)+timedelta(seconds=1)
            http=FakeHTTP(response=MockResponse(date=format_datetime(start,usegmt=True)))
            out,_=self.capture_one(td,http=http,clock=ticks(start,end))
            self.assertEqual(out["reason"],"OFFICIAL_PAGE_HTTP_OR_CAPTURE_WINDOW_INVALID")
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_14_final_url_redirect_refused_without_writing(self):
        with TemporaryDirectory() as td:
            http=FakeHTTP(response=MockResponse(url="https://example.com/changed"))
            out,_=self.capture_one(td,http=http)
            self.assertFalse(out["original_replayed_from_disk"])
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_15_http_403_no_retry(self):
        with TemporaryDirectory() as td:
            fake=FakeHTTP(error=HTTPError(TD,403,"Forbidden",{},None))
            out,_=self.capture_one(td,http=fake)
            self.assertEqual(len(fake.calls),1)
            self.assertEqual(out["reason"],"SOURCE_GET_OR_LOCAL_WRITE_FAILED_NO_RETRY")

    def test_16_wrong_mime_content_type_blocks(self):
        with TemporaryDirectory() as td:
            fake=FakeHTTP(response=MockResponse(mime="application/json"))
            out,_=self.capture_one(td,http=fake)
            self.assertFalse(out["original_replayed_from_disk"])

    def test_17_compressed_content_not_raw_html(self):
        with TemporaryDirectory() as td:
            fake=FakeHTTP(response=MockResponse(encoding="gzip"))
            out,_=self.capture_one(td,http=fake)
            self.assertFalse(out["original_replayed_from_disk"])

    def test_18_content_length_incorrect_blocks(self):
        with TemporaryDirectory() as td:
            fake=FakeHTTP(response=MockResponse(length=99999))
            out,_=self.capture_one(td,http=fake)
            self.assertFalse(out["original_replayed_from_disk"])

    def test_19_oversize_beyond_td_limit_blocks(self):
        with TemporaryDirectory() as td:
            fake=FakeHTTP(response=MockResponse(content=b"X"*(256*1024+10)))
            out,_=self.capture_one(td,http=fake)
            self.assertFalse(out["original_replayed_from_disk"])

    def test_20_undersized_looks_like_a_short_warning_not_consensus(self):
        with TemporaryDirectory() as td:
            fake=FakeHTTP(response=MockResponse(content=b"<h1>403</h1>"))
            out,_=self.capture_one(td,http=fake)
            self.assertFalse(out["original_replayed_from_disk"])

    def test_21_bogus_http_date_fails_custody_gate(self):
        with TemporaryDirectory() as td:
            fake=FakeHTTP(response=MockResponse(date="not-a-date"))
            out,_=self.capture_one(td,http=fake)
            self.assertEqual(out["reason"],"ORIGINAL_SOURCE_CUSTODY_GATE_REJECTED")

    def test_22_url_query_not_allowed_on_fixed_provider(self):
        with TemporaryDirectory() as td:
            out,fake=self.capture_one(td,provider="TRADING_ECONOMICS",
                                      url=TE+"?backfill=2027")
            self.assertEqual(fake.calls,[])
            self.assertFalse(out["original_replayed_from_disk"])

    def test_23_future_raw_bytes_not_replayed_at_past_cutoff(self):
        with TemporaryDirectory() as td:
            out,_=self.capture_one(td)
            old=replay(output_root=td,archive_basename=out["archive_basename"],
                       research_cutoff_utc=MARK+timedelta(milliseconds=999))
            self.safe(old)
            self.assertFalse(old["original_replayed_from_disk"])
            self.assertIsNone(old["source_original_sha256"])

    def test_24_original_bytes_tamper_replay_fails_closed(self):
        with TemporaryDirectory() as td:
            out,_=self.capture_one(td)
            f=Path(td)/out["archive_basename"]/"original.html"
            f.write_bytes(f.read_bytes()+b"corrupted")
            old=replay(output_root=td,archive_basename=out["archive_basename"],
                       research_cutoff_utc=MARK+timedelta(seconds=2))
            self.safe(old)
            self.assertFalse(old["original_replayed_from_disk"])

    def test_25_receipt_forged_digest_replay_fails(self):
        with TemporaryDirectory() as td:
            out,_=self.capture_one(td)
            f=Path(td)/out["archive_basename"]/"receipt.json"
            obj=json.loads(f.read_text("utf-8"))
            obj["original_html_sha256"]="e"*64
            f.write_text(json.dumps(obj),encoding="utf-8")
            old=replay(output_root=td,archive_basename=out["archive_basename"],
                       research_cutoff_utc=MARK+timedelta(seconds=2))
            self.assertFalse(old["original_replayed_from_disk"])

    def test_26_receipt_forged_numeric_consensus_authentication_rejected(self):
        with TemporaryDirectory() as td:
            out,_=self.capture_one(td)
            f=Path(td)/out["archive_basename"]/"receipt.json"
            obj=json.loads(f.read_text("utf-8"))
            obj["numerical_consensus_semantics_authenticated"]=True
            f.write_text(json.dumps(obj),encoding="utf-8")
            old=replay(output_root=td,archive_basename=out["archive_basename"],
                       research_cutoff_utc=MARK+timedelta(seconds=2))
            self.assertFalse(old["original_replayed_from_disk"])

    def test_27_duplicate_json_receipt_key_blocks_replay(self):
        with TemporaryDirectory() as td:
            out,_=self.capture_one(td)
            f=Path(td)/out["archive_basename"]/"receipt.json"
            value=f.read_text("utf-8").replace('"schema":','"schema":"FAKE","schema":')
            f.write_text(value,encoding="utf-8")
            old=replay(output_root=td,archive_basename=out["archive_basename"],
                       research_cutoff_utc=MARK+timedelta(seconds=2))
            self.assertFalse(old["original_replayed_from_disk"])

    def test_28_archive_path_traversal_rejected(self):
        with TemporaryDirectory() as td:
            old=replay(output_root=td,archive_basename="../../elsewhere",
                       research_cutoff_utc=MARK+timedelta(seconds=2))
            self.assertFalse(old["original_replayed_from_disk"])

    def test_29_changed_archive_basename_rejected(self):
        with TemporaryDirectory() as td:
            out,_=self.capture_one(td)
            old=replay(output_root=td,
                       archive_basename=out["archive_basename"].replace("TD_ECONOMICS",
                                                                      "TRADING_ECONOMICS"),
                       research_cutoff_utc=MARK+timedelta(seconds=2))
            self.assertFalse(old["original_replayed_from_disk"])

    def test_30_missing_output_root_does_not_send_get(self):
        fake=FakeHTTP()
        out=capture(allow_one_official_get=True,
                    confirm_bls_schedule_reviewed=True,
                    event_root=CPI,provider="TD_ECONOMICS",source_url=TD,
                    output_root="/does-not-exist-atlasquant-2026",
                    open_url=fake,clock=ticks())
        self.safe(out)
        self.assertEqual(fake.calls,[])

    def test_31_microseconds_not_rounded_backward(self):
        with TemporaryDirectory() as td:
            out,_=self.capture_one(td)
            end=MARK+timedelta(seconds=1)
            self.assertEqual(out["local_receipt_finished_utc_claim"],end.isoformat())
            early=replay(output_root=td,archive_basename=out["archive_basename"],
                         research_cutoff_utc=end-timedelta(microseconds=1))
            self.assertFalse(early["original_replayed_from_disk"])

    def test_32_untrusted_30_day_future_snapshot_rejected_before_get(self):
        with TemporaryDirectory() as td:
            out,fake=self.capture_one(td,clock=ticks(RELEASE[CPI]+timedelta(days=30)))
            self.assertEqual(fake.calls,[])
            self.assertFalse(out["original_replayed_from_disk"])

    def test_33_wrong_provider_type_rejected_before_get(self):
        with TemporaryDirectory() as td:
            out,fake=self.capture_one(td,provider="TD_AUTHENTICATED_100_PERCENT")
            self.assertEqual(fake.calls,[])
            self.assertFalse(out["original_replayed_from_disk"])

    def test_34_unparseable_td_edition_date_rejected_before_get(self):
        weird=TD.replace("2026-12-08","2026-99-08")
        with TemporaryDirectory() as td:
            out,fake=self.capture_one(td,url=weird)
            self.assertEqual(fake.calls,[])
            self.assertFalse(out["original_replayed_from_disk"])

    def test_35_no_inference_from_fake_99_point_9_percent(self):
        with TemporaryDirectory() as td:
            out,_=self.capture_one(td)
            self.assertTrue(out["original_replayed_from_disk"])
            self.assertIsNone(out["economic_surprise"])
            self.assertIsNone(out["fx_direction"])
            self.assertFalse(out["numerical_consensus_semantics_authenticated"])


if __name__=="__main__":
    unittest.main()
