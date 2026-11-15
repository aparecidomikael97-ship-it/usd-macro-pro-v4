"""Synthetic-only QA for rejected-BoJ-home quarantine. TemporaryDirectory.
No HTTP, MT5, live original, trading, cron or source publication.
"""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json,unittest
from atlasquant_trader_jpy_boj_rejected_home_quarantine_lab import (
    SCHEMA,LABEL,DENIED,quarantine_rejected_boj_home_lab as archive,
)
from atlasquant_trader_jpy_boj_guideline_source_receipt_lab import URL

END=datetime(2026,11,15,5,51,0,tzinfo=timezone.utc)
HTML=("<!doctype html><html><body><h1>Bank of Japan</h1>"
      "<section>Monetary policy information available.</section>"
      "<p>Format under investigation. No parser target to match.</p>"
      "<div>Symbolic dataset: "+("safe sample text "*35)+"</div>"
      "</body></html>").encode("utf-8")

class RejectedBoJHomeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(prefix="AQ_BOJ_HOME_REJECT_SYNTHETIC_")
        self.addCleanup(self.tmp.cleanup)
        self.app=Path(self.tmp.name)
        self.dir=self.app/"AtlasQuant"/"LAB"/"BoJ_Home_Quarantine_20261115"
        self.original_archive=self.app/"AtlasQuant"/"LAB"/"official_macro_receipts"
        self.receipt={
            "source_url":URL,"final_url":URL,
            "http_status":200,"content_type":"text/html; charset=utf-8",
            "body_sha256":sha256(HTML).hexdigest(),
            "started_at_utc":"2026-11-15T05:50:59Z",
            "finished_at_utc":"2026-11-15T05:51:00Z",
            "https_validation_claim":True,"redirects_followed":False,
        }
    def attempt(self,body=HTML,receipt=None,now=END,app=None):
        return archive(original_html=body,
            receipt=dict(self.receipt) if receipt is None else receipt,
            local_appdata=str(self.app) if app is None else app,
            decision_at_utc=now)
    def assert_safe(self,r):
        self.assertEqual(r["schema"],SCHEMA)
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["current_policy_source_admitted"])
        self.assertFalse(r["source_html_saved_to_official_macro_receipts"])
        self.assertFalse(r["source_first_seen_independently_authenticated"])
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertEqual((r["http_requests"],r["mt5_calls"],r["trade_calls"]),(0,0,0))
        self.assertFalse(self.original_archive.exists())
    def test_01_rejected_html_preserved_exactly_with_receipt_separate_from_policy(self):
        r=self.attempt()
        self.assert_safe(r)
        self.assertTrue(r["quarantined"])
        self.assertEqual(r["state"],"LAB_JPY_BOJ_REJECTED_HOME_ORIGINAL_QUARANTINED_NO_GO")
        self.assertEqual(r["file_writes"],2)
        filenames={p.name for p in self.dir.iterdir()}
        self.assertEqual(len(filenames),2)
        self.assertEqual((self.dir/r["original_filename"]).read_bytes(),HTML)
        doc=json.loads((self.dir/r["receipt_filename"]).read_text(encoding="utf-8"))
        self.assertEqual(doc["reason"],DENIED)
        self.assertFalse(doc["current_policy_source_admitted"])
        self.assertEqual(doc["original_sha256"],sha256(HTML).hexdigest())
        self.assertEqual(doc["original_receipt"],self.receipt)
        self.assertEqual(len(doc["marker_presence_in_raw_original"]),6)
    def test_02_same_receipt_never_overwritten(self):
        self.attempt()
        before={p.name:p.read_bytes() for p in self.dir.iterdir()}
        r=self.attempt()
        self.assert_safe(r)
        self.assertFalse(r["quarantined"])
        self.assertEqual(r["reason"],"DUPLICATE_OR_PARTIAL_QUARANTINE_DENIED_NO_OVERWRITE")
        self.assertEqual({p.name:p.read_bytes() for p in self.dir.iterdir()},before)
    def test_03_wrong_hash_rejected_before_write(self):
        meta=dict(self.receipt,body_sha256="0"*64)
        self.assertFalse(self.attempt(receipt=meta)["quarantined"])
        self.assertFalse(self.dir.exists())
    def test_04_nonissuer_source_rejected(self):
        self.assertFalse(self.attempt(receipt=dict(self.receipt,source_url="https://example.invalid"))["quarantined"])
        self.assertFalse(self.dir.exists())
    def test_05_redirect_to_unsupported_page_rejected(self):
        self.assertFalse(self.attempt(receipt=dict(self.receipt,final_url=URL+"market-foo"))["quarantined"])
        self.assertFalse(self.dir.exists())
    def test_06_http_403_not_archived_as_issuer_original(self):
        self.assertFalse(self.attempt(receipt=dict(self.receipt,http_status=403))["quarantined"])
        self.assertFalse(self.dir.exists())
    def test_07_wrong_content_type_rejected(self):
        self.assertFalse(self.attempt(receipt=dict(self.receipt,content_type="application/pdf"))["quarantined"])
        self.assertFalse(self.dir.exists())
    def test_08_missing_or_extra_receipt_field_rejected(self):
        missing=dict(self.receipt)
        missing.pop("http_status")
        added=dict(self.receipt,unexpected_extra="not allowed")
        for m in (missing,added):
            self.assertFalse(self.attempt(receipt=m)["quarantined"])
        self.assertFalse(self.dir.exists())
    def test_09_clock_in_future_not_backdated(self):
        r=self.attempt(now=END-timedelta(seconds=1))
        self.assertEqual(r["reason"],"BOJ_QUARANTINE_CAPTURE_CLOCK_INVALID")
        self.assertFalse(self.dir.exists())
    def test_10_31_second_collection_blocked(self):
        r=self.attempt(receipt=dict(self.receipt,started_at_utc="2026-11-15T05:50:28Z"))
        self.assertEqual(r["reason"],"BOJ_QUARANTINE_CAPTURE_CLOCK_INVALID")
        self.assertFalse(self.dir.exists())
    def test_11_malformed_timestamp_rejected(self):
        r=self.attempt(receipt=dict(self.receipt,finished_at_utc="2026-11-15 05:51:00"))
        self.assertEqual(r["reason"],"BOJ_QUARANTINE_CAPTURE_CLOCK_INVALID")
    def test_12_unsupported_data_type_rejected(self):
        r=self.attempt(body=b"short")
        self.assertFalse(r["quarantined"])
        self.assertFalse(self.dir.exists())
    def test_13_no_capture_from_relative_appdata(self):
        r=self.attempt(app="relative-directory")
        self.assertFalse(r["quarantined"])
        self.assertFalse(self.dir.exists())
    def test_14_valid_rate_response_must_not_go_into_rejected_quarantine(self):
        fake={"state":"LAB_JPY_BOJ_CURRENT_GUIDELINE_HTML_LOCALLY_CHECKED_NO_GO"}
        with patch("atlasquant_trader_jpy_boj_rejected_home_quarantine_lab."
                   "inspect_boj_home_guideline_receipt_lab",return_value=fake):
            r=self.attempt()
        self.assertEqual(r["reason"],"VALID_BOJ_HOME_NO_NEED_FOR_QUARANTINE")
        self.assertFalse(self.dir.exists())
    def test_15_non_structure_denial_no_quarantine(self):
        fake={"reason":"BOJ_ORIGINAL_HTML_SHA256_MISMATCH"}
        with patch("atlasquant_trader_jpy_boj_rejected_home_quarantine_lab."
                   "inspect_boj_home_guideline_receipt_lab",return_value=fake):
            r=self.attempt()
        self.assertEqual(r["reason"],"REJECTION_NOT_CONFIRMED_AS_HTML_STRUCTURE_ERROR")
        self.assertFalse(self.dir.exists())
    def test_16_forged_trade_permission_must_block(self):
        fake={"reason":DENIED,"html_sha256_matches_local_receipt":True,
              "transport_claim_structurally_consistent":True,
              "trade_authorized":True,"publishable":False}
        with patch("atlasquant_trader_jpy_boj_rejected_home_quarantine_lab."
                   "inspect_boj_home_guideline_receipt_lab",return_value=fake):
            r=self.attempt()
        self.assertEqual(r["reason"],"UNSAFE_VALIDATOR_STATUS")
        self.assertFalse(self.dir.exists())
    def test_17_existing_partial_html_alone_blocks(self):
        self.dir.mkdir(parents=True)
        name=LABEL+"_20261115T055100Z_"+sha256(HTML).hexdigest()[:12]
        orphan=self.dir/(name+".html")
        orphan.write_bytes(b"orphan")
        r=self.attempt()
        self.assertEqual(r["reason"],"DUPLICATE_OR_PARTIAL_QUARANTINE_DENIED_NO_OVERWRITE")
        self.assertEqual(orphan.read_bytes(),b"orphan")
    def test_18_symlink_root_refused_if_enabled(self):
        target=self.app/"target-folder";target.mkdir()
        self.dir.parent.mkdir(parents=True,exist_ok=True)
        try:self.dir.symlink_to(target,target_is_directory=True)
        except (OSError,NotImplementedError) as exc:self.skipTest(str(exc))
        r=self.attempt()
        self.assertFalse(r["quarantined"])
        self.assertEqual(r["reason"],"UNSAFE_QUARANTINE_ROOT")
    def test_19_root_does_not_exist_until_successful_first_write(self):
        bad=self.attempt(receipt=dict(self.receipt,http_status=500))
        self.assertFalse(bad["quarantined"])
        self.assertFalse(self.dir.exists())
        good=self.attempt()
        self.assertTrue(good["quarantined"])
    def test_20_wrong_clock_type_blocks(self):
        r=self.attempt(now="2026-11-15T05:51:00Z")
        self.assertFalse(r["quarantined"])
        self.assertFalse(self.dir.exists())

if __name__=="__main__":unittest.main(verbosity=2)
