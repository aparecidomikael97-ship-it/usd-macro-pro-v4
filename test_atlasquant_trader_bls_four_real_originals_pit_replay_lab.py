"""Synthetic ZIP/receipt tampering tests; optional real external artifact replay.

No fake HTML is presented as official. No HTTP, MT5, forecasts or trades.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED
import json
import unittest

import atlasquant_trader_bls_four_real_originals_pit_replay_lab as m

UTC = timezone.utc
DOCS = (
    ("US_CPI_SEP2026", "sep", "CPI", "2026-09", "2026-10-14T12:30:00+00:00", "2026-11-16T02:20:27+00:00"),
    ("US_PPI_SEP2026", "sep", "PPI", "2026-09", "2026-10-15T12:30:00+00:00", "2026-11-16T02:20:27+00:00"),
    ("US_CPI_OCT2026", "oct_cpi", "CPI", "2026-10", "2026-11-10T13:30:00+00:00", "2026-11-16T01:15:45+00:00"),
    ("US_PPI_OCT2026", "oct_ppi", "PPI", "2026-10", "2026-11-13T13:30:00+00:00", "2026-11-14T16:00:53+00:00"),
)


def h(b): return sha256(b).hexdigest()


def encode_zip(members):
    f=BytesIO()
    with ZipFile(f, "w", ZIP_DEFLATED) as z:
        for k,v in members.items(): z.writestr(k,v)
    return f.getvalue()


class FakeNestedArchive:
    def __init__(self, path):
        self.path=Path(path)
        receipts={}
        htmls={}
        self.pins={}
        self.archives={}
        self.manifest={"schema":m.MANIFEST_SCHEMA,
                       "independent_publisher_first_seen_attested":False,
                       "price_or_forex_forecast_verified":False,
                       "economic_originals":{},"actions_archives":[]}
        for root,group,kind,period,release,capture in DOCS:
            body=("SYNTHETIC ONLY " + root + "\n").encode()*3
            name=f"{group}/{root}_original.html"
            receipt_name=f"{group}/receipt.json"
            htmls[root]=(name,body,receipt_name)
            url="https://www.bls.gov/news.release/archives/synthetic_"+root.lower()+".htm"
            if group=="sep":
                receipts.setdefault(group,{"sources":{}})["sources"][kind]={
                    "raw_sha256":h(body),"raw_bytes":len(body),"http_status":200,
                    "url":url,"finished_utc":capture}
            else:
                receipts[group]={"body_sha256":h(body),"body_bytes":len(body),
                                 "status_code":200,"source_url":url,
                                 "finished_at_utc":capture}
            self.pins[root]=[group,name,receipt_name,h(body),"",capture,release,url,period]
            self.manifest["economic_originals"][period+"_"+kind]={
                "html_sha256":h(body),"html_bytes":len(body),
                "original_archive":f"arquivos_actions_originais/{group}.zip",
                "original_zip_inside_path":name,
                "source_url":url,"captured_after_release":True}
        by_archive={}
        for group,receipt in receipts.items():
            raw=json.dumps(receipt,sort_keys=True,separators=(",",":")).encode()
            members={f"{group}/receipt.json":raw}
            for root,(name,body,receipt_name) in htmls.items():
                if self.pins[root][0]==group:
                    self.pins[root][4]=h(raw)
                    members[name]=body
            by_archive[group]=encode_zip(members)
        outer={"LEIA_ME_PTBR.md":b"SYNTHETIC ONLY",
               "verificar_pacote.py":b"# synthetic test only"}
        for group,archive in by_archive.items():
            name=f"arquivos_actions_originais/{group}.zip"
            self.archives[group]=(name,h(archive))
            self.manifest["actions_archives"].append({"zip_path":name,"zip_sha256":h(archive)})
            for meta in self.manifest["economic_originals"].values():
                if meta["original_archive"]==name:meta["zip_sha256"]=h(archive)
            outer[name]=archive
        self.write_outer(outer)
        self.pins={k:tuple(x) for k,x in self.pins.items()}

    def write_outer(self,outer):
        outer["manifesto_sha256.json"]=json.dumps(self.manifest,sort_keys=True).encode()
        self.path.write_bytes(encode_zip(outer))

    def alter(self,fn):
        with ZipFile(self.path) as z:
            outer={name:z.read(name) for name in z.namelist()}
        outer["manifesto_sha256.json"]=json.dumps(self.manifest,sort_keys=True).encode()
        fn(outer)
        self.path.write_bytes(encode_zip(outer))


def safe(test,r):
    test.assertFalse(r["trade_authorized"])
    test.assertFalse(r["publishable"])
    test.assertFalse(r["publisher_first_seen_independently_attested"])
    test.assertFalse(r["consensus_pre_event_authenticated"])
    test.assertFalse(r["broker_prices_authenticated"])
    test.assertFalse(r["changes_to_fx28_672_slots"])
    test.assertEqual(r["event_denominator"],4)
    test.assertEqual((r["forecast_count_verified"],r["independent_out_of_sample_prediction_trials"]),(0,0))
    test.assertEqual((r["http_requests"],r["file_writes"],r["mt5_calls"]),(0,0,0))
    test.assertIsNone(r["accuracy"])
    test.assertIsNone(r["usd_bias"])
    test.assertEqual(r["operational_bias"],"AGUARDAR")


class FourActualBLSPITOfflineTests(unittest.TestCase):
    def setUp(self):
        self.t=TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.archive=FakeNestedArchive(Path(self.t.name)/"synthetic_bundle.zip")
        p1=patch.object(m,"PINS",self.archive.pins)
        p2=patch.object(m,"ARCHIVES",self.archive.archives)
        p1.start();p2.start()
        self.addCleanup(p1.stop);self.addCleanup(p2.stop)

    def run_at(self,t):
        r=m.inspect_four_real_bls_originals_lab(package_path=self.archive.path,as_of_utc=t)
        safe(self,r)
        return r

    def assert_visible(self,t,num):
        r=self.run_at(datetime.fromisoformat(t))
        self.assertEqual(r["state"],"LAB_BLS_FOUR_REAL_POSTRELEASE_ORIGINALS_PIT_DOCUMENTARY_NO_GO",r["reason"])
        self.assertEqual(r["visible_postrelease_originals"],num)
        self.assertEqual(r["not_yet_visible_originals"],4-num)
        self.assertEqual(len(r["events"]),4)
        self.assertEqual(sum(bool(e["document_original_verified"]) for e in r["events"]),num)
        for e in r["events"]:
            if not e["document_original_verified"]:
                self.assertIsNone(e["original_sha256"])
                self.assertIsNone(e["capture_at_utc"])
        return r

    def test_01_at_event_release_none_visible(self):
        self.assert_visible("2026-11-13T13:30:00+00:00",0)

    def test_02_at_one_microsecond_before_first_capture_none_visible(self):
        self.assert_visible("2026-11-14T16:00:52.999999+00:00",0)

    def test_03_at_exact_first_capture_one_visible(self):
        self.assert_visible("2026-11-14T16:00:53+00:00",1)

    def test_04_oct_cpi_right_before_capture_invisible(self):
        self.assert_visible("2026-11-16T01:15:44.999999+00:00",1)

    def test_05_oct_cpi_at_capture_two_visible(self):
        self.assert_visible("2026-11-16T01:15:45+00:00",2)

    def test_06_september_both_hidden_until_same_second_capture(self):
        self.assert_visible("2026-11-16T02:20:26.999999+00:00",2)

    def test_07_both_september_visible_together_never_inferred_order(self):
        self.assert_visible("2026-11-16T02:20:27+00:00",4)

    def test_08_all_visible_next_hour_still_no_forecast(self):
        self.assert_visible("2026-11-16T03:20:27+00:00",4)

    def test_09_cuiaba_utc_minus_four_same_instant(self):
        a=self.run_at(datetime(2026,11,16,2,20,27,tzinfo=UTC))
        b=self.run_at(datetime(2026,11,15,22,20,27,tzinfo=timezone(timedelta(hours=-4))))
        self.assertEqual(a,b)

    def test_10_naive_clock_fail_closed(self):
        r=self.run_at(datetime(2026,11,16,2,20,27))
        self.assertEqual(r["state"],"LAB_BLS_REAL_ORIGINALS_BLOCKED_HARD_NO_GO")

    def test_11_nonexistent_package_fail_closed(self):
        r=m.inspect_four_real_bls_originals_lab(package_path="/missing/bls.zip",
            as_of_utc=datetime(2026,11,16,tzinfo=UTC))
        safe(self,r)
        self.assertEqual(r["state"],"LAB_BLS_REAL_ORIGINALS_BLOCKED_HARD_NO_GO")

    def test_12_malformed_zip_fail_closed(self):
        self.archive.path.write_bytes(b"WRONG ARCHIVE")
        self.assertEqual(self.run_at(datetime(2026,11,16,3,tzinfo=UTC))["state"],
                         "LAB_BLS_REAL_ORIGINALS_BLOCKED_HARD_NO_GO")

    def test_13_manifest_false_first_seen_must_not_become_true(self):
        self.archive.manifest["independent_publisher_first_seen_attested"]=True
        self.archive.alter(lambda o:None)
        self.assertEqual(self.run_at(datetime(2026,11,16,3,tzinfo=UTC))["reason"],
                         "MANIFEST_SCHEMA_OR_AUTHORITY_INVALID")

    def test_14_manifest_false_fx_forecast_must_not_become_true(self):
        self.archive.manifest["price_or_forex_forecast_verified"]=True
        self.archive.alter(lambda o:None)
        self.assertEqual(self.run_at(datetime(2026,11,16,3,tzinfo=UTC))["reason"],
                         "MANIFEST_SCHEMA_OR_AUTHORITY_INVALID")

    def test_15_archive_corrupted_after_preservation_blocks(self):
        def alter(o):
            key=self.archive.archives["oct_ppi"][0]
            o[key]=o[key]+b"NOT_THE_SAME_ZIP"
        self.archive.alter(alter)
        self.assertEqual(self.run_at(datetime(2026,11,16,3,tzinfo=UTC))["reason"],
                         "ARCHIVE_ZIP_BYTES_CHANGED")

    def test_16_future_archive_corruption_does_not_leak_before_capture(self):
        def alter(o):
            key=self.archive.archives["sep"][0]
            o[key]=o[key]+b"NOT_THE_SAME_ZIP"
        self.archive.alter(alter)
        self.assert_visible("2026-11-16T02:20:26+00:00",2)
        self.assertEqual(self.run_at(datetime(2026,11,16,3,tzinfo=UTC))["reason"],
                         "ARCHIVE_ZIP_BYTES_CHANGED")

    def test_17_manifest_document_sha_tamper_blocks(self):
        self.archive.manifest["economic_originals"]["2026-10_PPI"]["html_sha256"]="0"*64
        self.archive.alter(lambda o:None)
        self.assertEqual(self.run_at(datetime(2026,11,16,3,tzinfo=UTC))["reason"],
                         "MANIFEST_DOCUMENT_IDENTITY_CHANGED")

    def test_18_manifest_zip_sha_tamper_blocks(self):
        self.archive.manifest["actions_archives"][0]["zip_sha256"]="0"*64
        self.archive.alter(lambda o:None)
        self.assertEqual(self.run_at(datetime(2026,11,16,3,tzinfo=UTC))["reason"],
                         "MANIFEST_ARCHIVE_HASH_CHANGED")

    def test_19_extra_malicious_member_blocks_before_any_parse(self):
        self.archive.alter(lambda o:o.update({"../outside":b"attack"}))
        self.assertEqual(self.run_at(datetime(2026,11,16,3,tzinfo=UTC))["reason"],
                         "UNKNOWN_OR_MISSING_ARCHIVE_MEMBER")

    def test_20_no_credential_or_network_code_side_effects(self):
        before=self.archive.path.read_bytes()
        self.assert_visible("2026-11-16T03:20:27+00:00",4)
        self.assertEqual(self.archive.path.read_bytes(),before)


if __name__=="__main__": unittest.main()
