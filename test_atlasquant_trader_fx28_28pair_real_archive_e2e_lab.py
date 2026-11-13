"""Full source-bytes -> on-disk receipts -> 8 real issuer parser gates
-> bilateral source coverage -> 28 WHY-AGUARDAR explanations -> manual CLI.

Only 8 SYNTHETIC issuer fixtures, local TemporaryDirectory, no real AM12
mount, no GitHub/HTTP requests, no trading signals and no proven source PIT.
Unlike the nearby mocked CLI tests, archive/explain call REAL functions.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_fx28_28pair_source_readiness_manual_lab import (
    inspect_28pair_source_readiness_once_lab as inspect,
    main,
)
from test_atlasquant_trader_fx28_policy_local_archive_replay_lab import (
    archive_dir, save_fixture,
)
from test_atlasquant_trader_fx28_eight_policy_raw_source_join_lab import (
    synthetic_packets,
)

NOW = datetime(2026, 11, 13, 11, 30, tzinfo=timezone.utc)
CODES = ("USD", "EUR", "CAD")


class EightBankTrueCodepathEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = synthetic_packets()

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def fixtures(self, codes=(), *, base=None):
        folder = archive_dir(self.temp.name if base is None else base)
        for code in codes:
            save_fixture(folder, code, self.sources[code])
        return folder

    def run_it(self, *, clock=None, mode="audit", capture=None):
        opts = {
            "mode": mode,
            "local_appdata": self.temp.name,
            "decision_clock": (lambda: NOW) if clock is None else clock,
        }
        if capture is not None:
            opts["capture"] = capture
        # NO archive/explain mocks. This is real disk -> issuer validator.
        return inspect(**opts)

    def safe(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        for flag in (
            "trade_authorized", "publishable", "live_alert_allowed",
            "worker_enabled", "scheduler_enabled",
            "first_seen_pit_authenticated",
            "central_bank_issuer_independently_authenticated",
            "bilateral_cpi_yoy_authenticated", "broker_m15_verified",
            "pre_event_forecasts_independently_witnessed",
            "forecast_or_accuracy_validated",
        ):
            self.assertFalse(result[flag], flag)
        self.assertTrue(result["source_coverage_is_not_currency_strength"])
        self.assertEqual(result["new_cost_brl"], 0)
        self.assertEqual(result["paid_data_requests"], 0)
        self.assertFalse("directional_bias" in result)
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        for row in result["per_pair"]:
            self.assertEqual(row["bias"], "AGUARDAR")
            self.assertFalse(row["trade_authorized"])
            self.assertTrue(row["why_wait_code"].startswith("POLICY_ORIGINAL"))

    def allowed(self, result):
        self.safe(result)
        self.assertEqual(result["state"],
                         "LAB_FX28_28PAIR_MANUAL_SOURCE_READINESS_NO_GO")
        self.assertEqual(result["pairs_explained"], 28)
        self.assertEqual(len(result["per_pair"]), 28)
        self.assertEqual([x["pair"] for x in result["per_pair"]],
                         list(OFFICIAL_PAIRS))

    def test_01_true_empty_archive_28_why_wait_no_fake_sources(self):
        self.fixtures()
        report = self.run_it()
        self.allowed(report)
        self.assertEqual(report["local_policy_sources_checked_codes"], [])
        self.assertEqual(report["local_policy_sources_checked_count"], 0)
        self.assertEqual(report["pairs_with_two_policy_sources_locally_checked"], 0)
        self.assertTrue(all(row["why_wait_code"] == "POLICY_ORIGINAL_MISSING"
                            for row in report["per_pair"]))

    def test_02_three_real_issuer_parsers_routed_into_28_pairs(self):
        self.fixtures(CODES)
        report = self.run_it()
        self.allowed(report)
        self.assertEqual(report["local_policy_sources_checked_codes"],
                         ["CAD", "EUR", "USD"])
        self.assertEqual(report["local_policy_sources_checked_count"], 3)
        self.assertEqual(report["pairs_with_two_policy_sources_locally_checked"],3)
        both = {r["pair"] for r in report["per_pair"]
                if r["local_policy_source_for_both"]}
        self.assertEqual(both, {"EUR/USD","EUR/CAD","USD/CAD"})
        self.assertEqual(report["policy_sources_missing_or_rejected_codes"],
                         ["AUD","CHF","GBP","JPY","NZD"])
        for pair in ("EUR/USD","EUR/CAD","USD/CAD"):
            r = next(x for x in report["per_pair"] if x["pair"]==pair)
            self.assertEqual(r["why_wait_code"],
                             "POLICY_ORIGINALS_LOCAL_ONLY_NO_BILATERAL_PIT_CPI")
            self.assertFalse(r["trade_authorized"])

    def test_03_all_eight_typed_source_parsers_still_28_no_go(self):
        self.fixtures(CURRENCIES)
        result=self.run_it()
        self.allowed(result)
        self.assertEqual(result["local_policy_sources_checked_codes"],
                         sorted(CURRENCIES))
        self.assertEqual(result["local_policy_sources_checked_count"],8)
        self.assertEqual(result["pairs_with_two_policy_sources_locally_checked"],28)
        self.assertEqual(result["suggested_next_collection_by_documentary_coverage"],[])
        self.assertTrue(all(row["local_policy_source_for_both"]
                            for row in result["per_pair"]))
        self.assertTrue(all(row["why_wait_code"] ==
                            "POLICY_ORIGINALS_LOCAL_ONLY_NO_BILATERAL_PIT_CPI"
                            for row in result["per_pair"]))
        self.assertFalse(result["broker_m15_verified"])

    def test_04_single_usd_source_is_not_any_two_source_pair(self):
        self.fixtures(("USD",))
        result=self.run_it()
        self.allowed(result)
        self.assertEqual(result["local_policy_sources_checked_count"],1)
        self.assertEqual(result["pairs_with_two_policy_sources_locally_checked"],0)

    def test_05_tamper_one_local_original_refuses_7_dependent_pairs(self):
        folder=self.fixtures(CURRENCIES)
        prefix="CAD_BOC_V39079_"
        matches=list(folder.glob(prefix+"*.json"))
        original=[x for x in matches if not x.name.endswith(".receipt.json")]
        self.assertEqual(len(original),1)
        original[0].write_bytes(original[0].read_bytes()+b"\nforged")
        result=self.run_it()
        self.allowed(result)
        self.assertEqual(result["local_policy_sources_checked_count"],7)
        self.assertEqual(result["pairs_with_two_policy_sources_locally_checked"],21)
        self.assertIn("CAD",result["policy_sources_missing_or_rejected_codes"])
        self.assertTrue(all(r["why_wait_code"]=="POLICY_ORIGINAL_REJECTED"
                            for r in result["per_pair"] if "CAD" in r["pair"]))

    def test_06_newest_bad_receipt_does_not_fallback_to_old_valid(self):
        folder=self.fixtures(CURRENCIES)
        modified=deepcopy(self.sources["USD"]["receipt"])
        modified["started_at_utc"]="2026-11-13T11:19:00Z"
        modified["finished_at_utc"]="2026-11-13T11:19:01Z"
        save_fixture(folder,"USD",self.sources["USD"],
                     override_receipt=modified,
                     override_stamp=modified["finished_at_utc"],
                     override_body=self.sources["USD"]["original_bytes"]+b"X")
        result=self.run_it()
        self.allowed(result)
        self.assertEqual(result["local_policy_sources_checked_count"],7)
        self.assertEqual(result["pairs_with_two_policy_sources_locally_checked"],21)
        self.assertIn("USD",result["policy_sources_missing_or_rejected_codes"])

    def test_07_only_future_local_receipt_does_not_backfill(self):
        folder=self.fixtures(("EUR","CAD"))
        modified=deepcopy(self.sources["USD"]["receipt"])
        modified["started_at_utc"]="2026-11-13T11:50:00Z"
        modified["finished_at_utc"]="2026-11-13T11:50:01Z"
        save_fixture(folder,"USD",self.sources["USD"],
                     override_receipt=modified)
        result=self.run_it()
        self.allowed(result)
        self.assertEqual(result["local_policy_sources_checked_codes"],["CAD","EUR"])
        self.assertEqual(result["pairs_with_two_policy_sources_locally_checked"],1)
        self.assertIn("USD",result["policy_sources_missing_or_rejected_codes"])

    def test_08_all_eight_checked_no_invented_accuracy_or_traffic(self):
        self.fixtures(CURRENCIES)
        with patch("urllib.request.urlopen",side_effect=AssertionError(
                "offline audit attempted HTTP")) as blocked:
            report=self.run_it()
        blocked.assert_not_called()
        self.allowed(report)
        self.assertNotIn("calibrated_probability",report)
        self.assertEqual(report["manual_capture_reported_http_attempts"],0)
        self.assertEqual(report["manual_capture_results"],{})

    def test_09_missing_folder_is_unknown_not_fake_0_8_documents(self):
        result=self.run_it()
        self.safe(result)
        self.assertEqual(result["state"],"LAB_FX28_28PAIR_READINESS_BLOCKED")
        self.assertEqual(result["reason"],"POLICY_ARCHIVE_ABSENT_OR_REJECTED")
        self.assertEqual(result["pairs_explained"],0)
        self.assertEqual(result["per_pair"],[])
        self.assertEqual(result["local_policy_sources_checked_count"],0)

    def test_10_no_forged_direct_report_from_real_bytes_that_only_show_rates(self):
        self.fixtures(("EUR","USD"))
        report=self.run_it()
        self.allowed(report)
        both=next(r for r in report["per_pair"] if r["pair"]=="EUR/USD")
        self.assertTrue(both["local_policy_source_for_both"])
        self.assertFalse(both["trade_authorized"])
        self.assertEqual(both["bias"],"AGUARDAR")
        self.assertEqual(both["why_wait_code"],
                         "POLICY_ORIGINALS_LOCAL_ONLY_NO_BILATERAL_PIT_CPI")

    def test_11_raw_receipts_not_modified_by_read_only_full_chain(self):
        folder=self.fixtures(CURRENCIES)
        before={p.name:sha256(p.read_bytes()).hexdigest()
                for p in folder.iterdir() if p.is_file()}
        result=self.run_it()
        self.allowed(result)
        after={p.name:sha256(p.read_bytes()).hexdigest()
               for p in folder.iterdir() if p.is_file()}
        self.assertEqual(before,after)

    def test_12_priority_list_is_documentary_graph_not_currency_rank(self):
        self.fixtures(CODES)
        report=self.run_it()
        self.allowed(report)
        priorities=report["suggested_next_collection_by_documentary_coverage"]
        self.assertEqual(set(p["currency"] for p in priorities),
                         set(CURRENCIES)-set(CODES))
        self.assertTrue(all(p[
            "hypothetical_additional_two_policy_source_pairs"]==3
            for p in priorities))
        self.assertTrue(all(not p["direction_or_trade_enabled_by_capture"]
                            for p in priorities))
        self.assertNotIn("moedas_mais_fortes",report)

    def test_13_command_line_read_only_audit_real_files_without_hidden_net(self):
        self.fixtures(CODES)
        with patch.dict("os.environ",{"LOCALAPPDATA":self.temp.name}):
            output=io.StringIO()
            with redirect_stdout(output):
                exit_code=main(["--audit"])
        self.assertEqual(exit_code,0)
        packet=json.loads(output.getvalue())
        self.allowed(packet)
        # CLI's own clock is now beyond synthetic source timestamp; that
        # does not mean the snapshot is first-seen attested or tradable.
        self.assertEqual(packet["pairs_with_two_policy_sources_locally_checked"],3)
        self.assertEqual(packet["manual_capture_reported_http_attempts"],0)

    def test_14_cli_default_sends_zero_network_calls_even_with_files(self):
        self.fixtures(CODES)
        with patch.dict("os.environ",{"LOCALAPPDATA":self.temp.name}):
            output=io.StringIO()
            with redirect_stdout(output):
                exit_code=main([])
        self.assertEqual(exit_code,2)
        packet=json.loads(output.getvalue())
        self.safe(packet)
        self.assertEqual(packet["per_pair"],[])

    def test_15_contaminated_receipt_preserves_no_go_for_mixed_pairs(self):
        folder=self.fixtures(CURRENCIES)
        meta=[p for p in folder.glob("GBP_BOE_*.receipt.json")]
        self.assertEqual(len(meta),1)
        meta[0].write_text("{\"http_status\":200,\"http_status\":200}")
        report=self.run_it()
        self.allowed(report)
        self.assertEqual(report["local_policy_sources_checked_count"],7)
        self.assertIn("GBP",report["policy_sources_missing_or_rejected_codes"])
        self.assertEqual(report["pairs_with_two_policy_sources_locally_checked"],21)

if __name__=="__main__":
    unittest.main()
