"""No-live-network tests for future explicit BoJ one-shot wrapper.
Everything under auto-deleted TemporaryDirectory. Do not invoke --capture.
"""
from __future__ import annotations
import json,unittest
from datetime import datetime,timezone
from tempfile import TemporaryDirectory
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
from atlasquant_trader_jpy_boj_one_attempt_diagnostic_runner_lab import (
    one_attempt_boj_policy_or_quarantine_lab as once,
    main, CLAIM_NAME,TARGET_DIR,
)
from atlasquant_trader_jpy_boj_guideline_source_receipt_lab import URL

AFTER=datetime(2026,11,15,22,30,0,tzinfo=timezone.utc)
EARLY=datetime(2026,11,15,22,19,59,tzinfo=timezone.utc)
HTML=("<!doctype html><html><body><main>BoJ SAMPLE REJECTED STRUCTURE</main>"+
      "<p>Unstructured research-only data. </p>"*30+
      "</body></html>").encode()
META={
    "source_url":URL,"final_url":URL,
    "http_status":200,"content_type":"text/html",
    "body_sha256":sha256(HTML).hexdigest(),
    "started_at_utc":"2026-11-15T22:29:58Z",
    "finished_at_utc":"2026-11-15T22:29:59Z",
    "https_validation_claim":True,
    "redirects_followed":False,
}
class BoJFutureOneAttemptTests(unittest.TestCase):
    def setUp(self):
        self.t=TemporaryDirectory(prefix="AQ_BOJ_FUTURE_ATTEMPT_MOCK_")
        self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name)
        self.folder=self.root/"AtlasQuant"/"LAB"/TARGET_DIR
        self.policy=self.root/"AtlasQuant"/"LAB"/"official_macro_receipts"
        self.calls=0
    def fetch(self):
        self.calls+=1
        return HTML,dict(META)
    def attempt(self,fetch=None,now=AFTER):
        return once(fetch_once=self.fetch if fetch is None else fetch,
                    local_appdata=str(self.root),now=lambda:now)
    def safe(self,r):
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["production_deployment"])
        self.assertFalse(r["scheduler_modified"])
        self.assertFalse(r["retry_or_alternate_url_allowed"])
        self.assertIsNone(r["calibrated_probability"])
    def test_01_pre_campaign_close_never_creates_claim_or_fetch(self):
        r=self.attempt(now=EARLY)
        self.safe(r)
        self.assertEqual(self.calls,0)
        self.assertFalse(self.folder.exists())
        self.assertFalse(r["one_attempt_claim_created"])
    def test_02_one_rejected_html_goes_to_quarantine_only(self):
        r=self.attempt()
        self.safe(r)
        self.assertEqual(self.calls,1)
        self.assertTrue(r["one_attempt_claim_created"])
        self.assertTrue(r["rejected_original_in_forensic_quarantine"])
        self.assertFalse(r["original_accepted_policy_source_archived"])
        self.assertFalse(self.policy.exists())
        self.assertEqual(len(list(self.folder.iterdir())),3)
        self.assertTrue((self.folder/CLAIM_NAME).exists())
    def test_03_repeat_never_calls_source_again(self):
        self.attempt()
        first=set(self.folder.iterdir())
        r=self.attempt()
        self.safe(r)
        self.assertTrue(r["attempt_already_reserved"])
        self.assertEqual(self.calls,1)
        self.assertEqual(set(self.folder.iterdir()),first)
    def test_04_fetch_failure_keeps_claim_prevents_retry(self):
        def failing():
            self.calls+=1
            raise OSError("synthetic failed fetch")
        r=self.attempt(fetch=failing)
        self.safe(r)
        self.assertTrue(r["one_attempt_claim_created"])
        self.assertTrue((self.folder/CLAIM_NAME).is_file())
        self.assertFalse(r["rejected_original_in_forensic_quarantine"])
        self.assertFalse(self.attempt()["one_attempt_claim_created"])
        self.assertEqual(self.calls,1)
        self.assertFalse(self.policy.exists())
    def test_05_false_issuer_url_rejected_never_contaminates_policy(self):
        def altered():
            self.calls+=1
            return HTML,dict(META,source_url="https://example.invalid")
        r=self.attempt(fetch=altered)
        self.safe(r)
        self.assertFalse(r["rejected_original_in_forensic_quarantine"])
        self.assertEqual(self.calls,1)
        self.assertFalse(self.policy.exists())
        self.assertTrue((self.folder/CLAIM_NAME).exists())
    def test_06_valid_policy_structural_acceptance_only_in_official_archive(self):
        # Simulated accepted result only, not real BoJ; archived fake HTML
        # remains in the TEST TEMP folder, never AM12 official archive.
        checked={"state":"LAB_JPY_BOJ_CURRENT_GUIDELINE_HTML_LOCALLY_CHECKED_NO_GO",
                 "trade_authorized":False,"publishable":False,
                 "operational_bias":"AGUARDAR"}
        with patch("atlasquant_trader_jpy_boj_one_attempt_diagnostic_runner_lab."
                   "inspect_boj_home_guideline_receipt_lab",return_value=checked):
            r=self.attempt()
        self.safe(r)
        self.assertEqual(self.calls,1)
        self.assertTrue(r["original_accepted_policy_source_archived"])
        self.assertFalse(r["rejected_original_in_forensic_quarantine"])
        self.assertTrue(self.policy.is_dir())
        self.assertEqual(len(list(self.policy.iterdir())),2)
        self.assertEqual(len(list(self.folder.iterdir())),1)
    def test_07_nonstructural_denial_only_reservation_no_fraudulent_source(self):
        with patch("atlasquant_trader_jpy_boj_one_attempt_diagnostic_runner_lab."
                   "inspect_boj_home_guideline_receipt_lab",
                   return_value={"reason":"NONOFFICIAL_BOJ_URL_OR_UNSAFE_TRANSPORT_CLAIM"}):
            r=self.attempt()
        self.safe(r)
        self.assertFalse(r["rejected_original_in_forensic_quarantine"])
        self.assertFalse(self.policy.exists())
        self.assertEqual(len(list(self.folder.iterdir())),1)
    def test_08_no_cli_flag_cannot_fetch(self):
        with patch("atlasquant_trader_jpy_boj_one_attempt_diagnostic_runner_lab."
                   "collect_boj_home_once_lab") as fetch:
            ret=main([])
            self.assertEqual(ret,2)
            fetch.assert_not_called()
    def test_09_missing_absolute_root_rejected_no_fetch(self):
        r=once(fetch_once=self.fetch,local_appdata="not-absolute",
               now=lambda:AFTER)
        self.safe(r)
        self.assertFalse(r["one_attempt_claim_created"])
        self.assertEqual(self.calls,0)
    def test_10_accepted_policy_is_not_trade_authorization(self):
        checked={"state":"LAB_JPY_BOJ_CURRENT_GUIDELINE_HTML_LOCALLY_CHECKED_NO_GO",
                 "trade_authorized":False,"publishable":False,
                 "operational_bias":"AGUARDAR"}
        with patch("atlasquant_trader_jpy_boj_one_attempt_diagnostic_runner_lab."
                   "inspect_boj_home_guideline_receipt_lab",return_value=checked):
            r=self.attempt()
        self.assertTrue(r["original_accepted_policy_source_archived"])
        self.safe(r)
    def test_11_unknown_now_clock_fails_without_fetch(self):
        r=once(fetch_once=self.fetch,local_appdata=str(self.root),
               now=lambda:None)
        self.safe(r)
        self.assertEqual(self.calls,0)
        self.assertFalse(self.folder.exists())
    def test_12_forged_valid_state_with_trade_flag_never_archives(self):
        forged={"state":"LAB_JPY_BOJ_CURRENT_GUIDELINE_HTML_LOCALLY_CHECKED_NO_GO",
                "trade_authorized":True,"publishable":False,
                "operational_bias":"AGUARDAR"}
        with patch("atlasquant_trader_jpy_boj_one_attempt_diagnostic_runner_lab."
                   "inspect_boj_home_guideline_receipt_lab",return_value=forged):
            r=self.attempt()
        self.safe(r)
        self.assertEqual(r["reason"],"FORGED_VALID_BOJ_STATUS_NO_POLICY_ARCHIVE")
        self.assertFalse(self.policy.exists())
        self.assertEqual(self.calls,1)
        self.assertEqual(len(list(self.folder.iterdir())),1)
    def test_13_claim_file_exactly_one_and_stays_after_rejection(self):
        r=self.attempt()
        self.safe(r)
        claim=json.loads((self.folder/CLAIM_NAME).read_text(encoding="utf-8"))
        self.assertEqual(claim["original_boj_url"],URL)
        self.assertTrue(claim["one_attempt"])
        self.assertFalse(claim["trade_authorized"])
        self.assertFalse(self.attempt()["one_attempt_claim_created"])

if __name__=="__main__":unittest.main(verbosity=2)
