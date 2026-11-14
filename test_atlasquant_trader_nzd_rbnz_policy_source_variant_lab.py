"""Synthetic RBNZ article variant through REAL eight-bank archive replay.

These tests may write under an isolated TemporaryDirectory. They do NOT
capture the issuer, access AM12, or authenticate original market provenance.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from atlasquant_trader_nzd_rbnz_policy_source_variant_lab import (
    ADMITTED_STATE, VARIANT_OCTOBER, VARIANT_LEGACY,
    inspect_nzd_rbnz_policy_variant_lab as check,
)
from atlasquant_trader_nzd_rbnz_oct_article_local_capture_lab import (
    save_october_rbnz_release_local_lab as save,
)
from atlasquant_trader_fx28_policy_local_archive_replay_lab import (
    inspect_fx28_official_policy_archive_replay_lab as replay,
)
from atlasquant_trader_fx28_eight_policy_raw_source_join_lab import (
    inspect_eight_bank_policy_raw_source_join_lab as joined,
)
from test_atlasquant_trader_nzd_rbnz_ocr_decision_article_lab import (
    page, receipt as article_receipt,
)
from test_atlasquant_trader_nzd_rbnz_ocr_receipt_lab import (
    html_page as legacy_html, receipt as legacy_receipt,
)
from test_atlasquant_trader_fx28_policy_local_archive_replay_lab import (
    archive_dir,save_fixture,
)
from test_atlasquant_trader_fx28_eight_policy_raw_source_join_lab import (
    synthetic_packets,
)

UTC=timezone.utc
CAPTURE=datetime(2026,11,14,11,50,0,tzinfo=UTC)
PRE=datetime(2026,11,15,10,0,0,tzinfo=UTC)
CUT=datetime(2026,12,9,1,0,0,tzinfo=UTC)


def packet():
    html=page("2026-10")
    return {"original_bytes":html,"receipt":article_receipt("2026-10",html)}


class NzdPolicyVariantReplayTests(unittest.TestCase):
    def safe(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["historical_point_in_time_first_seen_authenticated"])
        self.assertFalse(r["actual_market_consensus_verified"])
        self.assertIsNone(r["calibrated_directional_fx_probability"])
        self.assertEqual((r["http_requests"],r["file_writes"],r["new_cost_brl"]),
                         (0,0,0))

    def inspect(self,p=None,cut=PRE):
        p=packet() if p is None else p
        return check(original_html=p["original_bytes"],
                     receipt=p["receipt"],decision_at_utc=cut)

    def test_01_oct_article_accepted_as_documentary_policy_until_decision(self):
        r=self.inspect()
        self.safe(r)
        self.assertEqual(r["state"],ADMITTED_STATE)
        self.assertEqual(r["source_variant"],VARIANT_OCTOBER)
        self.assertEqual(r["locally_checked_policy_event_month"],"2026-10")
        self.assertEqual(r["policy_action_claim"],"HOLD")
        self.assertEqual(r["policy_ocr_pct_claim"],"2.75")
        self.assertTrue(r["source_original_sha256_locally_reconciled"])
        self.assertTrue(r["policy_decided_rate_not_market_expectation"])

    def test_02_legacy_ocr_html_still_accepted_pre_next_update(self):
        raw=legacy_html()
        r=self.inspect({"original_bytes":raw,
                        "receipt":legacy_receipt(raw)})
        self.safe(r)
        self.assertEqual(r["state"],ADMITTED_STATE)
        self.assertEqual(r["source_variant"],VARIANT_LEGACY)
        self.assertIsNone(r["policy_action_claim"])
        self.assertEqual(r["policy_ocr_pct_claim"],"2.75")

    def test_03_oct_release_superseded_exactly_at_dec9_open(self):
        for now in (CUT,CUT+timedelta(seconds=1),
                    datetime(2027,1,1,tzinfo=UTC)):
            with self.subTest(now=now):
                r=self.inspect(cut=now)
                self.safe(r)
                self.assertEqual(
                    r["reason"],
                    "OCTOBER_POLICY_RELEASE_SUPERSEDED_AT_NEXT_DECISION")
                self.assertFalse(r["source_original_sha256_locally_reconciled"])

    def test_04_old_ocr_card_not_current_after_next_update_date(self):
        raw=legacy_html()
        p={"original_bytes":raw,"receipt":legacy_receipt(raw)}
        r=self.inspect(p,cut=CUT-timedelta(seconds=1))
        self.safe(r)
        self.assertEqual(r["state"],ADMITTED_STATE)
        r=self.inspect(p,cut=CUT)
        self.safe(r)
        self.assertEqual(r["reason"],
                         "LEGACY_OCR_CARD_SUPERSEDED_AT_NEXT_SCHEDULED_UPDATE")

    def test_05_wrong_issuer_article_or_september_old_hike_blocked(self):
        for url in (
            "https://www.rbnz.govt.nz.evil.test/news",
            "https://www.rbnz.govt.nz/news-and-events/news/2026/09/ocr-increased-by-25-basis-points-to-2-75",
            "https://www.rbnz.govt.nz/monetary-policy/unknown",
            None,
        ):
            with self.subTest(url=url):
                p=packet();p["receipt"]["source_url"]=url
                r=self.inspect(p)
                self.safe(r)
                self.assertEqual(r["state"],
                    "LAB_NZD_RBNZ_POLICY_SOURCE_VARIANT_BLOCKED_NO_GO")

    def test_06_oct_article_body_modified_sha_or_no_sentence_block(self):
        p=packet();p["original_bytes"]+=b"tamper"
        r=self.inspect(p);self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_NZD_RBNZ_POLICY_SOURCE_VARIANT_BLOCKED_NO_GO")
        p=packet();p["original_bytes"]=page(
            "2026-10",sentence="The RBNZ expects rates to change later.")
        p["receipt"]=article_receipt("2026-10",p["original_bytes"])
        r=self.inspect(p);self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_NZD_RBNZ_POLICY_SOURCE_VARIANT_BLOCKED_NO_GO")

    def test_07_cutoff_before_capture_and_invalid_clock_denied(self):
        for now in (CAPTURE-timedelta(seconds=1),CAPTURE.replace(tzinfo=None),
                    CAPTURE+timedelta(microseconds=1),"2026-11-15"):
            with self.subTest(now=now):
                r=self.inspect(cut=now);self.safe(r)
                self.assertNotEqual(r["state"],ADMITTED_STATE)

    def test_08_real_join_accepts_article_without_changing_forex_authority(self):
        packs=synthetic_packets()
        packs["NZD"]=packet()
        out=joined(source_packets_by_currency=packs,decision_at_utc=PRE)
        self.assertEqual(out["state"],
            "LAB_FX28_EIGHT_POLICY_ORIGINAL_BYTES_LOCAL_ONLY_NO_GO")
        self.assertEqual(len(out["locally_checked_currencies"]),8)
        self.assertEqual(out["pairs_with_both_policy_sources_locally_checked_count"],28)
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["full_bilateral_CPI_YOY_sources_authenticated"])
        self.assertIsNone(out["calibrated_directional_probability"])

    def test_09_end_to_end_tempdir_oct_release_and_5_sources_not_real_am12(self):
        with TemporaryDirectory() as td:
            folder=archive_dir(td)
            old=synthetic_packets()
            # Synthetic other 5 policy original files, no actual issuer.
            for c in ("AUD","CAD","EUR","GBP","USD"):
                save_fixture(folder,c,old[c])
            p=packet()
            saved=save(original_html=p["original_bytes"],
                       receipt=p["receipt"],local_appdata=td,
                       as_of_utc=CAPTURE)
            self.assertEqual(len(saved),2)
            r=replay(local_appdata=td,decision_at_utc=PRE)
        self.assertEqual(r["currencies_with_local_original_bytes_validated"],6)
        self.assertEqual(r["pairs_with_both_policy_originals_locally_checked"],15)
        self.assertEqual(r["currencies_missing"],["CHF","JPY"])
        self.assertEqual(r["currency_archive_status"]["NZD"]["status"],
                         "LOCALLY_CHECKED_ONLY_NOT_SOURCE_ATTESTATION")
        self.assertFalse(r["source_original_bytes_from_AM12_independently_attested"])
        self.assertFalse(r["trade_authorized"])

    def test_10_empty_local_folder_does_not_invent_nzd_archive(self):
        with TemporaryDirectory() as td:
            archive_dir(td)
            r=replay(local_appdata=td,decision_at_utc=PRE)
        self.assertEqual(r["currencies_with_local_original_bytes_validated"],0)
        self.assertIn("NZD",r["currencies_missing"])

    def test_11_real_archive_oct_release_becomes_rejected_after_dec9_cutoff(self):
        with TemporaryDirectory() as td:
            archive_dir(td)
            p=packet()
            save(original_html=p["original_bytes"],receipt=p["receipt"],
                 local_appdata=td,as_of_utc=CAPTURE)
            before=replay(local_appdata=td,decision_at_utc=CUT-timedelta(seconds=1))
            after=replay(local_appdata=td,decision_at_utc=CUT)
        self.assertEqual(before["currencies_with_local_original_bytes_validated"],1)
        self.assertEqual(after["currencies_with_local_original_bytes_validated"],0)
        self.assertIn("NZD",after["currencies_rejected"])
        self.assertEqual(after["pairs_with_both_policy_originals_locally_checked"],0)

    def test_12_wrong_original_after_newer_capture_does_not_fall_back_to_old(self):
        with TemporaryDirectory() as td:
            folder=archive_dir(td)
            old=legacy_html()
            old_p={"original_bytes":old,"receipt":legacy_receipt(old)}
            save_fixture(folder,"NZD",old_p)
            p=packet()
            _,meta=save(original_html=p["original_bytes"],receipt=p["receipt"],
                        local_appdata=td,as_of_utc=CAPTURE)
            # Disrupt the latest receipt; older candidate must NOT be used.
            (folder/meta).write_text('{"tampered":"bad"}',encoding="utf-8")
            r=replay(local_appdata=td,decision_at_utc=PRE)
        self.assertEqual(r["currencies_with_local_original_bytes_validated"],0)
        self.assertIn("NZD",r["currencies_rejected"])

    def test_13_corrupt_nzd_article_receipt_url_rejected_by_issuer_parser(self):
        with TemporaryDirectory() as td:
            folder=archive_dir(td)
            p=packet();p["receipt"]["final_url"]="https://evil.test/"
            # Archive folder helper does not perform external validation.
            save_fixture(folder,"NZD",p)
            r=replay(local_appdata=td,decision_at_utc=PRE)
        self.assertIn("NZD",r["currencies_rejected"])
        self.assertEqual(r["currencies_with_local_original_bytes_validated"],0)

    def test_14_rbnz_decisions_are_document_sources_not_fx_trade_signal(self):
        r=self.inspect()
        self.safe(r)
        self.assertTrue(r["policy_decided_rate_not_market_expectation"])
        self.assertTrue(r["upcoming_rbnz_forecast_not_issuer_ocr_actual"])
        self.assertFalse(r["source_bytes_saved_on_am12_by_this_function"])


if __name__=="__main__":
    unittest.main()
