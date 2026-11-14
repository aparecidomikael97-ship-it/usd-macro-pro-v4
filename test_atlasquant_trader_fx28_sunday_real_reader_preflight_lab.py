"""Sunday 15 Nov FX28 preflight using REAL local reader over SYNTHETIC files.

This integration suite calls the UNMOCKED:
  local source replay -> 8-bank policy join -> 32-factor source admission
  -> frozen 672-slot ledger -> single readiness panel.
Only tempdir fixtures, not AM12, actual banking data, trading or network.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from atlasquant_trader_fx28_single_readiness_panel_lab import (
    inspect_fx28_single_readiness_panel_lab as panel,
)
from atlasquant_trader_fx28_policy_local_archive_replay_lab import (
    inspect_fx28_official_policy_archive_replay_lab as replay,
)
from atlasquant_trader_nzd_rbnz_oct_article_local_capture_lab import (
    save_october_rbnz_release_local_lab as save_nzd,
)
from test_atlasquant_trader_fx28_policy_local_archive_replay_lab import (
    archive_dir, save_fixture,
)
from test_atlasquant_trader_fx28_eight_policy_raw_source_join_lab import (
    synthetic_packets,
)
from test_atlasquant_trader_nzd_rbnz_ocr_decision_article_lab import (
    page, receipt as article_receipt,
)

UTC = timezone.utc
SUNDAY_PREFLIGHT = datetime(2026,11,15,10,0,0,tzinfo=UTC) # 06 Cuiaba
FIRST_NY17_OPEN = datetime(2026,11,15,22,0,0,tzinfo=UTC) # 18 Cuiaba
NZD_CAPTURE = datetime(2026,11,14,11,50,0,tzinfo=UTC)
SIX_SOURCE_CURRENCIES = {"AUD","CAD","EUR","GBP","USD","NZD"}
FIVE_SOURCE_CURRENCIES = SIX_SOURCE_CURRENCIES-{"NZD"}


def synth_folder(local_appdata: str, *, nzd: bool = True,
                 eight: bool = False) -> tuple[Path, str | None]:
    """Create *fake* local originals/receipts with the real archive format."""
    folder = archive_dir(local_appdata)
    sources = synthetic_packets()
    names = {"AUD","CAD","EUR","GBP","USD"}
    if eight:
        names.update(("CHF","JPY"))
    for c in sorted(names):
        save_fixture(folder,c,sources[c])
    nzd_receipt_name = None
    if nzd:
        raw=page("2026-10")
        receipt=article_receipt("2026-10",raw)
        _filename,nzd_receipt_name=save_nzd(
            original_html=raw, receipt=receipt,
            local_appdata=local_appdata, as_of_utc=NZD_CAPTURE)
    return folder,nzd_receipt_name


class SundayRealReaderPreflightTests(unittest.TestCase):
    def safe(self, r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["witnesses_independently_authenticated"])
        self.assertFalse(r["issuer_identity_and_first_seen_independently_authenticated"])
        self.assertFalse(r["broker_m15_independently_authenticated"])
        self.assertFalse(r["model_direction_calibrated"])
        self.assertTrue(r["source_page_link_is_not_source_byte_capture"])
        self.assertTrue(r["empty_witness_input_does_not_prove_external_absence"])
        for k in ("validated_fx28_accuracy","calibrated_probability","directional_bias"):
            self.assertIsNone(r[k])
        self.assertEqual(r["factors_with_independently_accepted_signed_effect"],0)
        self.assertEqual(r["factors_with_independent_pre_event_consensus"],0)
        self.assertEqual(r["factors_with_calibrated_directional_effect"],0)
        self.assertEqual((r["http_requests"],r["file_writes"],r["new_cost_brl"]),
                         (0,0,0))

    def ready(self,local_appdata,now=SUNDAY_PREFLIGHT):
        result=panel(local_appdata=local_appdata,inspected_at_utc=now)
        self.safe(result)
        self.assertEqual(
            result["state"],"LAB_FX28_SINGLE_READINESS_PANEL_RECONCILED_NO_GO")
        self.assertEqual(result["slots_expected"],672)
        self.assertEqual(result["slots_accounted"],672)
        return result

    def test_01_sunday_preflight_real_six_file_join_one_recent_only(self):
        with TemporaryDirectory() as td:
            synth_folder(td)
            result=self.ready(td)
        self.assertEqual(result["issuer_policy_document_count"],6)
        self.assertEqual(result["issuer_policy_currencies_locally_checked"],
                         sorted(SIX_SOURCE_CURRENCIES))
        self.assertEqual(result["pairs_with_both_policy_documents"],15)
        self.assertEqual(result["pairs_lacking_policy_document"],13)
        self.assertEqual(result["issuer_policy_missing_currencies"],["CHF","JPY"])
        self.assertEqual(result["recent_24h_local_receipt_claim_currencies"],["NZD"])
        self.assertEqual(result["recent_24h_local_receipt_claim_count"],1)
        self.assertEqual(result["recent_24h_bilateral_policy_pair_count"],0)
        self.assertEqual(result["stale_over_24h_local_receipt_claim_currencies"],
                         sorted(FIVE_SOURCE_CURRENCIES))
        self.assertEqual(result["slots_future_no_supplied_witness"],672)
        self.assertEqual(result["slots_past_no_supplied_witness"],0)
        self.assertEqual(result["next_frozen_start_utc"],
                         FIRST_NY17_OPEN.isoformat())

    def test_02_five_old_originals_never_become_recent_when_nzd_missing(self):
        with TemporaryDirectory() as td:
            synth_folder(td,nzd=False)
            r=self.ready(td)
        self.assertEqual(r["issuer_policy_document_count"],5)
        self.assertEqual(r["pairs_with_both_policy_documents"],10)
        self.assertEqual(r["issuer_policy_missing_currencies"],["CHF","JPY","NZD"])
        self.assertEqual(r["recent_24h_local_receipt_claim_count"],0)
        self.assertEqual(r["recent_24h_bilateral_policy_pair_count"],0)

    def test_03_exact_24h_boundary_then_one_second_stale(self):
        with TemporaryDirectory() as td:
            synth_folder(td)
            same=self.ready(td, NZD_CAPTURE+timedelta(hours=24))
            late=self.ready(td, NZD_CAPTURE+timedelta(hours=24,seconds=1))
        self.assertEqual(same["issuer_policy_document_count"],6)
        self.assertEqual(late["issuer_policy_document_count"],6)
        self.assertEqual(same["recent_24h_local_receipt_claim_currencies"],["NZD"])
        self.assertEqual(late["recent_24h_local_receipt_claim_currencies"],[])
        self.assertEqual(late["recent_24h_bilateral_policy_pair_count"],0)

    def test_04_ny17_open_56_due_but_no_actual_witness_authenticated(self):
        with TemporaryDirectory() as td:
            synth_folder(td)
            r=self.ready(td,FIRST_NY17_OPEN)
        self.assertEqual(r["issuer_policy_document_count"],6)
        self.assertEqual(r["slots_future_no_supplied_witness"],616)
        self.assertEqual(r["slots_past_no_supplied_witness"],56)
        self.assertEqual(r["recent_24h_local_receipt_claim_count"],0)
        self.assertTrue(r["empty_witness_input_does_not_prove_external_absence"])

    def test_05_tampered_latest_nzd_receipt_never_counts_as_sixth(self):
        with TemporaryDirectory() as td:
            folder,receipt_file=synth_folder(td)
            (folder/receipt_file).write_text('{"forged":"no"}',encoding="utf-8")
            r=self.ready(td)
        self.assertEqual(r["issuer_policy_document_count"],5)
        self.assertEqual(r["pairs_with_both_policy_documents"],10)
        self.assertEqual(r["issuer_policy_rejected_currencies"],["NZD"])
        self.assertEqual(r["recent_24h_local_receipt_claim_count"],0)

    def test_06_missing_real_folder_is_blocked_not_assumed_five_sources(self):
        with TemporaryDirectory() as td:
            r=panel(local_appdata=td,inspected_at_utc=SUNDAY_PREFLIGHT)
        self.assertEqual(r["state"],"LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")
        self.assertEqual(r["issuer_policy_document_count"],0)
        self.assertEqual(r["pairs_with_both_policy_documents"],0)
        self.assertFalse(r["trade_authorized"])

    def test_07_eight_synthetic_originals_never_equal_real_fx_bias(self):
        with TemporaryDirectory() as td:
            synth_folder(td,eight=True)
            r=self.ready(td)
        self.assertEqual(r["issuer_policy_document_count"],8)
        self.assertEqual(r["pairs_with_both_policy_documents"],28)
        self.assertEqual(r["recent_24h_local_receipt_claim_count"],1)
        self.assertEqual(r["recent_24h_bilateral_policy_pair_count"],0)
        self.assertFalse(r["model_direction_calibrated"])

    def test_08_october_article_has_capture_date_not_issuer_first_seen(self):
        with TemporaryDirectory() as td:
            synth_folder(td)
            original=replay(local_appdata=td,decision_at_utc=SUNDAY_PREFLIGHT)
            r=self.ready(td)
        self.assertEqual(original["currency_archive_status"]["NZD"]["status"],
                         "LOCALLY_CHECKED_ONLY_NOT_SOURCE_ATTESTATION")
        self.assertEqual(
            original["currency_archive_status"]["NZD"][
                "selected_local_capture_utc_claim"],"2026-11-14T11:50:00Z")
        self.assertFalse(
            original["true_first_seen_time_independently_attested"])
        self.assertFalse(
            original["source_original_bytes_from_AM12_independently_attested"])
        self.assertFalse(
            r["issuer_identity_and_first_seen_independently_authenticated"])

    def test_09_after_dec9_october_nzd_must_be_missing_not_a_fresh_policy(self):
        with TemporaryDirectory() as td:
            synth_folder(td)
            out=replay(local_appdata=td,decision_at_utc=datetime(
                2026,12,9,1,0,0,tzinfo=UTC))
        self.assertIn("NZD",out["currencies_rejected"])
        self.assertNotIn("NZD",out["currencies_locally_checked"])
        self.assertFalse(out["trade_authorized"])

    def test_10_same_sunday_one_recent_currency_never_a_bilateral_pair(self):
        with TemporaryDirectory() as td:
            synth_folder(td)
            r=self.ready(td)
        self.assertEqual(
            r["recent_24h_bilateral_policy_pair_count"],
            1*(1-1)//2)
        self.assertEqual(r["pairs_with_both_policy_documents"],15)
        self.assertIsNone(r["directional_bias"])
        self.assertFalse(r["trade_authorized"])


if __name__=="__main__":
    unittest.main()
