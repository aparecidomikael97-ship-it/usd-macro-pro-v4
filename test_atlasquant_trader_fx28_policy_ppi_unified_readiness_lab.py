"""Integration: 8-bank original archive + BLS October PPI original replay.

Every issuer document is a SYNTHETIC test fixture. PPI fetch is mocked;
the downstream source parser, read-only replay and 28-pair auditor are
REAL Python functions, with real files in TemporaryDirectory. No broker,
HTTP, MT5, GitHub upload, trades or evidence of historical prediction.
"""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_fx28_policy_ppi_unified_readiness_lab import (
    SCHEMA, inspect_fx28_policy_ppi_readiness_lab as audit, main,
)
from atlasquant_trader_us_ppi_oct2026_original_capture_lab import (
    capture_oct2026_bls_original_once_lab as capture,
)
from test_atlasquant_trader_us_ppi_oct2026_original_capture_lab import (
    MockResponse, START, FINISH,
)
from test_atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import raw
from test_atlasquant_trader_fx28_policy_local_archive_replay_lab import (
    archive_dir, save_fixture,
)
from test_atlasquant_trader_fx28_eight_policy_raw_source_join_lab import (
    synthetic_packets,
)

UTC=timezone.utc
NOW=datetime(2026,11,13,14,5,tzinfo=UTC)


class Fx28BankAndPPIOfflineBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.banks=synthetic_packets()

    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def banks_on_disk(self, currencies=()):
        folder=archive_dir(self.tmp.name)
        for currency in currencies:
            save_fixture(folder,currency,self.banks[currency])
        return folder

    def ppi_on_disk(self, *, body=None):
        transport=Mock(return_value=MockResponse(
            body=raw(head="0.3",core="0.3",extra="0.5")
                 if body is None else body))
        clock=Mock(side_effect=[START,FINISH])
        stored=capture(
            allow_one_get=True,local_appdata=self.tmp.name,
            open_url=transport,clock=clock)
        transport.assert_called_once()
        self.assertEqual(stored["state"],
                         "LAB_US_PPI_OCT2026_BLS_RAW_BYTES_REPLAYED_LOCAL_ONLY_NO_GO")
        self.assertTrue(stored["raw_bytes_and_receipt_replayed"])
        return stored["archive_directory_basename"]

    def run_it(self, *, ppi=None, at=NOW, root=None):
        return audit(local_appdata=self.tmp.name if root is None else root,
                     decision_at_utc=at,
                     ppi_archive_basename=ppi)

    def safe(self, r):
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["ppi_can_be_fx28_directional_factor"])
        self.assertFalse(r["central_bank_issuer_first_seen_independently_authenticated"])
        self.assertFalse(r["bls_first_seen_independently_authenticated"])
        self.assertFalse(r["historical_macro_point_in_time_authenticated"])
        self.assertFalse(r["bilateral_cpi_for_eight_currencies_authenticated"])
        self.assertFalse(r["policy_expectations_authenticated"])
        self.assertFalse(r["broker_m15_authenticated"])
        self.assertFalse(r["pre_event_fx28_rosters_independently_witnessed"])
        self.assertFalse(r["model_calibrated_for_fx28"])
        self.assertIsNone(r["directional_bias"])
        self.assertIsNone(r["usd_strength_score"])
        self.assertIsNone(r["economic_impact_points"])
        self.assertIsNone(r["fx28_probability"])
        self.assertIsNone(r["validated_hit_rate"])
        self.assertEqual(r["http_requests"],0)
        self.assertEqual(r["file_writes"],0)
        self.assertEqual(r["new_cost_brl"],0)
        self.assertTrue(r["ppi_is_one_shared_catalyst_not_seven_independent_news"])
        self.assertTrue(r["ppi_oct2026_is_post_release_documentary_context"])
        self.assertTrue(r["policy_local_recency_is_not_realtime_economic_freshness"])
        for row in r["per_pair"]:
            self.assertEqual(row["bias"],"AGUARDAR")
            self.assertFalse(row["trade_authorized"])
            self.assertFalse(row["ppi_counts_as_independent_issuer_catalyst_for_this_pair"])
            self.assertFalse(row["ppi_validated_pre_event_consensus_available"])
            self.assertFalse(row["ppi_fx_impact_calculated"])
            self.assertIsNone(row["directional_bias"])
            self.assertIsNone(row["calibrated_probability"])
            self.assertTrue(row["need_bilateral_cpi_point_in_time"])
            self.assertTrue(row["need_broker_m15_authenticated"])

    def complete(self,r):
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_POLICY_PPI_COMBINED_READONLY_NO_GO")
        self.assertEqual(r["fx28_pairs_reported"],28)
        self.assertEqual([row["pair"] for row in r["per_pair"]],
                         list(OFFICIAL_PAIRS))
        self.assertEqual(sum(x["ppi_direct_usd_issuer_leg"]
                             for x in r["per_pair"]),7)

    def test_01_no_file_folder_28_unknown_no_forecast_invented(self):
        r=self.run_it()
        self.complete(r)
        self.assertEqual(r["policy_source_audit_state"],
                         "LAB_FX28_28PAIR_READINESS_BLOCKED")
        self.assertEqual(r["policy_source_documents_locally_checked"],0)
        self.assertEqual(r["ppi_source_replay_state"],"NOT_REQUESTED")
        self.assertEqual(r["ppi_documentary_series"],[])
        self.assertTrue(all(x["source_readiness_blocking_reason"] ==
            "POLICY_ARCHIVE_UNAVAILABLE_OR_UNVERIFIED" for x in r["per_pair"]))
        self.assertFalse(r["ppi_source_replay_attempted"])

    def test_02_three_real_bank_parsers_show_3_pairs_not_strength(self):
        self.banks_on_disk(("USD","EUR","CAD"))
        r=self.run_it()
        self.complete(r)
        self.assertEqual(r["policy_source_documents_locally_checked"],3)
        self.assertEqual(r["policy_source_recent_local_receipt_claims"],3)
        self.assertEqual(r["policy_pairs_with_two_originals"],3)
        self.assertEqual(r["policy_pairs_with_two_recent_local_receipt_claims"],3)
        pairs={x["pair"] for x in r["per_pair"]
               if x["two_policy_originals_locally_checked"]}
        self.assertEqual(pairs,{"EUR/USD","EUR/CAD","USD/CAD"})
        self.assertEqual(r["ppi_documentary_series_count"],0)

    def test_03_all_eight_bank_originals_only_do_not_admit_one_signal(self):
        self.banks_on_disk(CURRENCIES)
        r=self.run_it()
        self.complete(r)
        self.assertEqual(r["policy_source_documents_locally_checked"],8)
        self.assertEqual(r["policy_pairs_with_two_originals"],28)
        self.assertEqual(r["policy_pairs_with_two_recent_local_receipt_claims"],28)
        self.assertTrue(all(row["two_policy_originals_locally_checked"]
                            for row in r["per_pair"]))
        self.assertEqual(r["ppi_documentary_series"],[])
        self.assertFalse(r["ppi_can_be_fx28_directional_factor"])

    def test_04_ppi_original_bytes_without_policy_files_is_not_8bank_cover(self):
        ppi=self.ppi_on_disk()
        r=self.run_it(ppi=ppi)
        self.complete(r)
        self.assertEqual(r["policy_source_documents_locally_checked"],0)
        self.assertEqual(r["policy_pairs_with_two_originals"],0)
        self.assertEqual(r["ppi_documentary_series_count"],3)
        self.assertEqual(r["ppi_direct_usd_leg_pairs_with_source_replayed"],7)
        self.assertTrue(all(not row["two_policy_originals_locally_checked"]
                            for row in r["per_pair"]))
        self.assertTrue(all(row["source_readiness_blocking_reason"] ==
                            "ONE_OR_BOTH_POLICY_DOCUMENTS_MISSING_OR_REJECTED"
                            for row in r["per_pair"]))

    def test_05_full_real_disk_bank_and_ppi_replay_same_report_no_go(self):
        self.banks_on_disk(CURRENCIES)
        ppi=self.ppi_on_disk()
        result=self.run_it(ppi=ppi)
        self.complete(result)
        self.assertEqual(result["policy_source_documents_locally_checked"],8)
        self.assertEqual(result["policy_pairs_with_two_originals"],28)
        self.assertEqual(result["ppi_source_replay_state"],
                         "LAB_US_PPI_OCT2026_BLS_RAW_BYTES_REPLAYED_LOCAL_ONLY_NO_GO")
        self.assertEqual(result["ppi_documentary_series_count"],3)
        self.assertEqual([row["fd_commodity_code"]
                          for row in result["ppi_documentary_series"]],
                         ["4","49104","49116"])
        self.assertEqual([row["actual_pct_local_documentary_claim"]
                          for row in result["ppi_documentary_series"]],
                         ["0.3","0.3","0.5"])
        self.assertEqual(result["ppi_direct_usd_leg_pairs_with_source_replayed"],7)
        self.assertEqual(result["reason"],
                         "BOTH_LOCAL_SOURCE_READERS_CHECKED_RESEARCH_ONLY")
        self.assertFalse(result["pre_event_fx28_rosters_independently_witnessed"])

    def test_06_usd_ppi_applies_only_directly_to_seven_usd_leg_pairs(self):
        self.banks_on_disk(CURRENCIES)
        ppi=self.ppi_on_disk()
        r=self.run_it(ppi=ppi)
        self.complete(r)
        enriched=[x for x in r["per_pair"] if x[
            "ppi_direct_usd_issuer_leg_documentary_context_replayed"]]
        other=[x for x in r["per_pair"] if not x[
            "ppi_direct_usd_issuer_leg_documentary_context_replayed"]]
        self.assertEqual(len(enriched),7)
        self.assertEqual(len(other),21)
        self.assertEqual({x["ppi_postrelease_source_sha256_for_direct_usd_leg_only"]
                          for x in enriched},{r["ppi_source_raw_sha256"]})
        self.assertTrue(all(x[
            "ppi_postrelease_source_sha256_for_direct_usd_leg_only"] is None
            for x in other))
        self.assertTrue(any(x["pair"]=="EUR/USD" for x in enriched))
        self.assertTrue(any(x["pair"]=="USD/CAD" for x in enriched))
        self.assertTrue(any(x["pair"]=="EUR/GBP" for x in other))
        self.assertFalse(any(x["ppi_fx_impact_calculated"]
                             for x in enriched))

    def test_07_only_three_policy_files_and_ppi_does_not_invent_rank(self):
        self.banks_on_disk(("USD","EUR","CAD"))
        ppi=self.ppi_on_disk()
        result=self.run_it(ppi=ppi)
        self.complete(result)
        self.assertEqual(result["policy_pairs_with_two_originals"],3)
        self.assertEqual(result["ppi_direct_usd_leg_pairs_with_source_replayed"],7)
        self.assertEqual(result["economic_impact_points"],None)
        self.assertEqual(result["fx28_probability"],None)
        self.assertNotIn("top10",result)
        self.assertNotIn("strongest_currency",result)

    def test_08_stale_bank_receipts_not_rescued_by_recent_ppi(self):
        self.banks_on_disk(CURRENCIES)
        ppi=self.ppi_on_disk()
        r=self.run_it(ppi=ppi,at=NOW+timedelta(hours=48))
        self.complete(r)
        self.assertEqual(r["policy_source_recent_local_receipt_claims"],0)
        self.assertEqual(r["policy_pairs_with_two_recent_local_receipt_claims"],0)
        self.assertEqual(r["ppi_documentary_series_count"],3)
        self.assertEqual(r["ppi_direct_usd_leg_pairs_with_source_replayed"],7)
        self.assertFalse(any(row["two_policy_recent_local_receipt_claims"]
                             for row in r["per_pair"]))

    def test_09_tampered_ppi_source_drops_all_ppi_series_only(self):
        self.banks_on_disk(CURRENCIES)
        ppi=self.ppi_on_disk()
        p=(Path(self.tmp.name)/"AtlasQuant"/"LAB"/
           "official_macro_receipts"/ppi/"original.html")
        p.write_bytes(p.read_bytes()+b"altered")
        result=self.run_it(ppi=ppi)
        self.complete(result)
        self.assertEqual(result["policy_source_documents_locally_checked"],8)
        self.assertEqual(result["ppi_documentary_series_count"],0)
        self.assertIsNone(result["ppi_source_raw_sha256"])
        self.assertEqual(result["ppi_direct_usd_leg_pairs_with_source_replayed"],0)
        self.assertFalse(any(row[
            "ppi_direct_usd_issuer_leg_documentary_context_replayed"]
            for row in result["per_pair"]))

    def test_10_fake_ppi_receipt_rejects_without_discarding_banks(self):
        self.banks_on_disk(("USD","EUR","CAD"))
        ppi=self.ppi_on_disk()
        path=(Path(self.tmp.name)/"AtlasQuant"/"LAB"/
              "official_macro_receipts"/ppi/"receipt.json")
        m=json.loads(path.read_text())
        m["raw_sha256"]="f"*64
        path.write_text(json.dumps(m))
        result=self.run_it(ppi=ppi)
        self.complete(result)
        self.assertEqual(result["policy_source_documents_locally_checked"],3)
        self.assertEqual(result["ppi_documentary_series_count"],0)
        self.assertFalse(result["ppi_source_replay_state"].endswith(
            "REPLAYED_LOCAL_ONLY_NO_GO"))

    def test_11_ppi_future_capture_at_decision_clock_is_not_seen(self):
        self.banks_on_disk(CURRENCIES)
        ppi=self.ppi_on_disk()
        at=START+timedelta(seconds=1)
        r=self.run_it(ppi=ppi,at=at)
        self.complete(r)
        self.assertEqual(r["ppi_documentary_series_count"],0)
        self.assertEqual(r["ppi_direct_usd_leg_pairs_with_source_replayed"],0)
        self.assertFalse(r["bls_first_seen_independently_authenticated"])

    def test_12_path_traversal_archive_is_rejected_not_bypassed(self):
        self.banks_on_disk(CURRENCIES)
        ppi=self.ppi_on_disk()
        report=self.run_it(ppi="../"+ppi)
        self.complete(report)
        self.assertEqual(report["policy_source_documents_locally_checked"],8)
        self.assertEqual(report["ppi_documentary_series_count"],0)
        self.assertIsNone(report["ppi_source_raw_sha256"])
        self.assertTrue(report["ppi_source_replay_attempted"])

    def test_13_bank_original_sha_change_does_not_count_seven_dependent(self):
        folder=self.banks_on_disk(CURRENCIES)
        ppi=self.ppi_on_disk()
        allcad=[p for p in folder.glob("CAD_BOC_*.json")
                if not p.name.endswith(".receipt.json")]
        self.assertEqual(len(allcad),1)
        allcad[0].write_bytes(allcad[0].read_bytes()+b"corruption")
        report=self.run_it(ppi=ppi)
        self.complete(report)
        self.assertEqual(report["policy_source_documents_locally_checked"],7)
        self.assertEqual(report["policy_pairs_with_two_originals"],21)
        self.assertEqual(report["ppi_documentary_series_count"],3)
        self.assertEqual(report["ppi_direct_usd_leg_pairs_with_source_replayed"],7)
        cad=[x for x in report["per_pair"] if "CAD" in x["pair"]]
        self.assertEqual(len(cad),7)
        self.assertTrue(all(not row["two_policy_originals_locally_checked"]
                            for row in cad))

    def test_14_read_only_join_does_not_write_or_open_any_http(self):
        folder=self.banks_on_disk(CURRENCIES)
        ppi=self.ppi_on_disk()
        before={str(path.relative_to(folder)):sha256(path.read_bytes()).hexdigest()
                for path in folder.rglob("*") if path.is_file()}
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("unexpected HTTP GET")) as web:
            out=self.run_it(ppi=ppi)
        web.assert_not_called()
        self.complete(out)
        after={str(path.relative_to(folder)):sha256(path.read_bytes()).hexdigest()
               for path in folder.rglob("*") if path.is_file()}
        self.assertEqual(before,after)
        self.assertEqual(out["http_requests"],0)
        self.assertEqual(out["file_writes"],0)

    def test_15_wrong_clock_or_root_fails_closed_without_pseudo_28(self):
        for wrong in (None,NOW.replace(tzinfo=None),
                      NOW.replace(microsecond=1),
                      "2026-11-13T14:05Z"):
            with self.subTest(clock=wrong):
                r=self.run_it(at=wrong)
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_FX28_POLICY_PPI_UNIFIED_READINESS_BLOCKED_NO_GO")
                self.assertEqual(r["fx28_pairs_reported"],0)
        for wrong in ("relative","/definitely/nonexistent/root",True):
            with self.subTest(root=wrong):
                r=self.run_it(root=wrong)
                self.safe(r)
                self.assertEqual(r["fx28_pairs_reported"],0)

    def test_16_wrong_ppi_name_or_missing_ppi_source_never_fakes_forecast(self):
        self.banks_on_disk(CURRENCIES)
        r=self.run_it(ppi="US_BLS_PPI_OCT2026_20261113T140002Z_bad")
        self.complete(r)
        self.assertEqual(r["ppi_documentary_series_count"],0)
        self.assertEqual(r["ppi_direct_usd_leg_pairs_with_source_replayed"],0)

    def test_17_readonly_cli_no_flag_produces_no_file_or_http_access(self):
        self.banks_on_disk(CURRENCIES)
        with patch("atlasquant_trader_fx28_policy_ppi_unified_readiness_lab.inspect_fx28_policy_ppi_readiness_lab") as spy:
            output=io.StringIO()
            with redirect_stdout(output):
                status=main([])
        self.assertEqual(status,2)
        spy.assert_not_called()
        jsonout=json.loads(output.getvalue())
        self.safe(jsonout)
        self.assertEqual(jsonout["fx28_pairs_reported"],0)
        self.assertEqual(jsonout["reason"],"EXPLICIT_READONLY_AUDIT_FLAG_REQUIRED")

    def test_18_cli_audit_real_local_files_outputs_28_without_trade(self):
        self.banks_on_disk(CURRENCIES)
        ppi=self.ppi_on_disk()
        with patch.dict(os.environ,{"LOCALAPPDATA":self.tmp.name}):
            output=io.StringIO()
            with redirect_stdout(output):
                status=main(["--audit","--ppi-archive",ppi])
        self.assertEqual(status,0)
        report=json.loads(output.getvalue())
        self.complete(report)
        self.assertEqual(report["policy_source_documents_locally_checked"],8)
        self.assertEqual(report["ppi_documentary_series_count"],3)
        self.assertEqual(report["ppi_direct_usd_leg_pairs_with_source_replayed"],7)
        self.assertEqual(report["broker_m15_authenticated"],False)
        self.assertEqual(report["operational_bias"],"AGUARDAR")

    def test_19_ppi_report_has_no_spurious_consensus_or_trade_service_swap(self):
        self.banks_on_disk(CURRENCIES)
        ppi=self.ppi_on_disk()
        result=self.run_it(ppi=ppi)
        self.complete(result)
        series=result["ppi_documentary_series"]
        self.assertEqual([x["series_label"] for x in series],[
            "Final demand",
            "Final demand less foods and energy",
            "Final demand less foods, energy, and trade services"])
        self.assertTrue(all(x["pre_event_consensus_pct"] is None
                            and x["surprise_percentage_points"] is None
                            for x in series))
        self.assertFalse(result["ppi_can_be_fx28_directional_factor"])

    def test_20_no_ppi_arg_does_not_call_ppi_replay(self):
        self.banks_on_disk(CURRENCIES)
        with patch(
            "atlasquant_trader_fx28_policy_ppi_unified_readiness_lab.replay_oct2026_bls_original_capture_lab",
            side_effect=AssertionError("PPI read must be opt in")
        ) as spy:
            r=self.run_it()
        spy.assert_not_called()
        self.complete(r)
        self.assertFalse(r["ppi_source_replay_attempted"])
        self.assertEqual(r["ppi_documentary_series_count"],0)



    def test_21_blS_public_oct2026_first_print_three_values_reconciled(self):
        # The mock files themselves remain synthetic. This check uses
        # independently read PUBLIC BLS 2026-11-13 Table 1 numbers:
        # FD/4 +0.3, FD/49104 +0.3, FD/49116 +0.5, all MoM SA.
        self.banks_on_disk(CURRENCIES)
        folder=self.ppi_on_disk()
        out=self.run_it(ppi=folder)
        self.complete(out)
        self.assertEqual(out["ppi_first_print_reference_url"],
            "https://www.bls.gov/news.release/archives/ppi_11132026.htm")
        self.assertEqual(out["ppi_public_first_print_sa_oct2026_pct_by_fd_code"],
            {"4":"0.3","49104":"0.3","49116":"0.5"})
        self.assertTrue(out["ppi_local_original_matches_public_first_print_values"])
        self.assertFalse(out["ppi_local_replay_valid_but_first_print_values_disagree"])
        self.assertTrue(out["ppi_public_first_print_numeric_crosscheck_not_authentication"])
        self.assertEqual(out["ppi_documentary_series_count"],3)
        self.assertEqual(out["ppi_direct_usd_leg_pairs_with_source_replayed"],7)
        self.assertFalse(out["bls_first_seen_independently_authenticated"])
        self.assertFalse(out["trade_authorized"])

    def test_22_replayed_syntactically_valid_unofficial_headline_is_quarantined(self):
        self.banks_on_disk(CURRENCIES)
        name=self.ppi_on_disk(body=raw(head="0.4",core="0.3",extra="0.5"))
        out=self.run_it(ppi=name)
        self.complete(out)
        self.assertEqual(out["policy_source_documents_locally_checked"],8)
        self.assertEqual(out["policy_pairs_with_two_originals"],28)
        self.assertTrue(out["ppi_local_replay_valid_but_first_print_values_disagree"])
        self.assertFalse(out["ppi_local_original_matches_public_first_print_values"])
        self.assertEqual(out["ppi_documentary_series_count"],0)
        self.assertIsNone(out["ppi_source_raw_sha256"])
        self.assertEqual(out["ppi_direct_usd_leg_pairs_with_source_replayed"],0)
        self.assertTrue(all(row["ppi_single_document_sha256_in_bundle_if_usd"]
                            is None for row in out["per_pair"]))
        self.assertFalse(out["model_calibrated_for_fx28"])

    def test_23_two_core_definitions_are_not_interchangeable(self):
        self.banks_on_disk(("USD","EUR","CAD"))
        for headline,core,extra in (
            ("0.3","0.4","0.5"),    # wrong ex-foods-energy 49104
            ("0.3","0.3","0.4"),    # wrong ex-trade 49116
            ("0.4","0.3","0.3"),    # wrong headline + wrong ex-trade
        ):
            with self.subTest(values=(headline,core,extra)):
                ppi=self.ppi_on_disk(
                    body=raw(head=headline,core=core,extra=extra))
                r=self.run_it(ppi=ppi)
                self.complete(r)
                self.assertTrue(r[
                    "ppi_local_replay_valid_but_first_print_values_disagree"])
                self.assertEqual(r["ppi_documentary_series_count"],0)
                self.assertEqual(r["policy_pairs_with_two_originals"],3)
                self.assertFalse(r["ppi_can_be_fx28_directional_factor"])

    def test_24_equivalent_decimal_representation_is_not_false_rejection(self):
        self.banks_on_disk(CURRENCIES)
        ppi=self.ppi_on_disk(body=raw(
            head="0.30",core="0.30",extra="0.50"))
        result=self.run_it(ppi=ppi)
        self.complete(result)
        self.assertTrue(result["ppi_local_original_matches_public_first_print_values"])
        self.assertEqual(result["ppi_documentary_series_count"],3)
        self.assertEqual(result["ppi_direct_usd_leg_pairs_with_source_replayed"],7)
        self.assertFalse(result["historical_macro_point_in_time_authenticated"])

    def test_25_missing_ppi_and_stale_banks_never_use_public_values_as_bytes(self):
        self.banks_on_disk(CURRENCIES)
        result=self.run_it(at=NOW+timedelta(days=2))
        self.complete(result)
        self.assertEqual(result["policy_source_recent_local_receipt_claims"],0)
        self.assertEqual(result["ppi_source_replay_state"],"NOT_REQUESTED")
        self.assertFalse(result["ppi_local_original_matches_public_first_print_values"])
        self.assertEqual(result["ppi_documentary_series_count"],0)
        self.assertIsNone(result["ppi_source_raw_sha256"])
        self.assertEqual(result["ppi_direct_usd_leg_pairs_with_source_replayed"],0)
        self.assertEqual(result["ppi_public_first_print_sa_oct2026_pct_by_fd_code"],
            {"4":"0.3","49104":"0.3","49116":"0.5"})

    def test_26_seven_usd_legs_share_exactly_one_reconciled_ppi_source(self):
        self.banks_on_disk(CURRENCIES)
        ppi=self.ppi_on_disk()
        r=self.run_it(ppi=ppi)
        self.complete(r)
        accepted=[x for x in r["per_pair"]
                  if x["ppi_direct_usd_issuer_leg_documentary_context_replayed"]]
        self.assertEqual(len(accepted),7)
        self.assertEqual({x["ppi_single_document_sha256_in_bundle_if_usd"]
                          for x in accepted},{r["ppi_source_raw_sha256"]})
        self.assertFalse(any(x["ppi_counts_as_independent_issuer_catalyst_for_this_pair"]
                             for x in accepted))
        self.assertEqual(r["ppi_documentary_series_count"],3)
        self.assertTrue(all(row["pre_event_consensus_pct"] is None
                            for row in r["ppi_documentary_series"]))
        self.assertIsNone(r["economic_impact_points"])
        self.assertIsNone(r["directional_bias"])


if __name__=="__main__":
    unittest.main()
