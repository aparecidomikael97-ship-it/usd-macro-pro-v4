"""True issuer-file & BLS original replay -> D1/W1 prewindow veto.

All bank files and PPI HTML are synthetic temporary TEST fixtures.
The forecast generator is NEVER called; no MACRO directional assertions,
no web requests, no broker, no validated outcomes or prior witness.
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

from atlasquant_fx_universe import CURRENCIES
from atlasquant_trader_fx28_pre_window_source_gate_lab import (
    SCHEMA, inspect_fx28_pre_window_source_gate_lab as preflight, main,
)
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    FROZEN_START_UTC, FROZEN_END_UTC, _nominal_windows,
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
FIRST=FROZEN_START_UTC
PRE=FIRST-timedelta(minutes=30)
AHEAD=FIRST-timedelta(hours=12)
TOO_EARLY=AHEAD-timedelta(seconds=1)
MONDAY_START=_nominal_windows("D1")[1][0]


class PreWindowFX28SourceVetoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources=synthetic_packets()

    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def banks(self, codes=()):
        folder=archive_dir(self.temp.name)
        for code in codes:
            save_fixture(folder,code,self.sources[code])
        return folder

    def ppi(self):
        transport=Mock(return_value=MockResponse(
            body=raw(head="0.3",core="0.3",extra="0.5")))
        clock=Mock(side_effect=[START,FINISH])
        saved=capture(allow_one_get=True,local_appdata=self.temp.name,
                      open_url=transport,clock=clock)
        self.assertTrue(saved["raw_bytes_and_receipt_replayed"])
        transport.assert_called_once()
        return saved["archive_directory_basename"]

    def run_it(self,at=PRE,ppi=None,root=None):
        return preflight(local_appdata=self.temp.name if root is None else root,
                         inspected_at_utc=at,ppi_archive_basename=ppi)

    def safe(self,r):
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["expected_nominal_opportunities"],672)
        self.assertEqual(r["expected_d1_nominal_opportunities"],560)
        self.assertEqual(r["expected_w1_nominal_opportunities"],112)
        self.assertEqual(r["max_source_preflight_hours_before_start"],12)
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["issuer_first_seen_authenticated"])
        self.assertFalse(r["bilateral_cpi_pit_authenticated"])
        self.assertFalse(r["policy_expectations_pit_authenticated"])
        self.assertFalse(r["economic_impact_model_calibrated"])
        self.assertFalse(r["broker_m15_authenticated"])
        self.assertFalse(r["real_prior_forecast_rosters_authenticated"])
        self.assertFalse(r["pre_event_28_forecast_rosters_generated"])
        self.assertFalse(r["github_pre_event_hash_witness_posted"])
        self.assertFalse(r["ready_for_d1_forecast"])
        self.assertFalse(r["ready_for_w1_forecast"])
        self.assertIsNone(r["out_of_sample_hit_rate"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertIsNone(r["directional_bias"])
        self.assertEqual(r["http_requests"],0)
        self.assertEqual(r["file_writes"],0)
        self.assertEqual(r["new_cost_brl"],0)
        self.assertTrue(r["source_replay_not_issuer_identity_or_pit_proof"])
        self.assertTrue(r["ppi_post_event_context_not_pre_event_forecast"])
        for horizon in r["next_nominal_windows"]:
            self.assertFalse(horizon["forecast_issuance_authorized"])
            for row in horizon["pairs"]:
                self.assertFalse(row["forecast_issued"])
                self.assertFalse(row["forecast_authorized"])
                self.assertFalse(row["forecast_sha_witness_posted"])
                self.assertFalse(row["ppi_as_signed_currency_factor"])
                self.assertIsNone(row["calibrated_probability"])
                self.assertFalse(row["trade_authorized"])
                self.assertEqual(row["bias"],"AGUARDAR")
                self.assertIn("BILATERAL_CPI_AND_MACRO_VINTAGE_MISSING",
                              row["blocking_reasons"])

    def active(self,r,count=2):
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_PREWINDOW_28_SOURCE_VETOES_NO_GO")
        self.assertTrue(r["source_reader_was_called"])
        self.assertEqual(r["nominal_windows_in_active_preflight"],count)
        self.assertEqual(r["potential_slots_now_audited"],count*28)
        self.assertEqual(sum(len(x["pairs"]) for x in r["next_nominal_windows"]),
                         count*28)

    def test_01_friday_prewindow_not_open_no_source_reads_or_fake_forecasts(self):
        with patch(
            "atlasquant_trader_fx28_pre_window_source_gate_lab.inspect_fx28_policy_ppi_readiness_lab",
            side_effect=AssertionError("do not read sources until preflight")
        ) as spy:
            r=self.run_it(at=datetime(2026,11,13,20,tzinfo=UTC))
        spy.assert_not_called()
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_PREWINDOW_NOT_ACTIVE_NO_GO")
        self.assertFalse(r["source_reader_was_called"])
        self.assertEqual(r["nominal_windows_in_active_preflight"],0)
        self.assertEqual(r["potential_slots_now_audited"],0)
        self.assertEqual([x["horizon"] for x in r["next_nominal_windows"]],
                         ["D1","W1"])
        self.assertTrue(all(not x["pairs"] for x in r["next_nominal_windows"]))

    def test_02_exact_twelve_hour_boundary_56_slots_but_zero_go(self):
        r=self.run_it(at=AHEAD)
        self.active(r)
        self.assertEqual(r["unified_source_audit_state"],
                         "LAB_FX28_POLICY_PPI_COMBINED_READONLY_NO_GO")
        self.assertEqual(r["policy_original_documents_locally_checked"],0)
        self.assertEqual(r["policy_recent_local_capture_claims"],0)
        self.assertFalse(r["ppi_oct2026_documentary_source_replayed"])
        self.assertTrue(all(x["next_start_utc"]==FIRST.isoformat()
                            for x in r["next_nominal_windows"]))

    def test_03_before_twelve_hour_boundary_is_not_eager_launch(self):
        r=self.run_it(at=TOO_EARLY)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_PREWINDOW_NOT_ACTIVE_NO_GO")
        self.assertEqual(r["potential_slots_now_audited"],0)
        self.assertFalse(r["source_reader_was_called"])

    def test_04_eight_valid_originals_replayed_on_sunday_are_stale_not_live(self):
        self.banks(CURRENCIES)
        ppi=self.ppi()
        r=self.run_it(ppi=ppi)
        self.active(r)
        self.assertEqual(r["policy_original_documents_locally_checked"],8)
        # Bank receipt fixture captured on Friday; Sunday is >24h later.
        self.assertEqual(r["policy_recent_local_capture_claims"],0)
        self.assertTrue(r["ppi_oct2026_documentary_source_replayed"])
        for horizon in r["next_nominal_windows"]:
            self.assertTrue(all("ONE_OR_BOTH_POLICY_RECEIPT_CLAIMS_STALE"
                                in row["blocking_reasons"]
                                for row in horizon["pairs"]))
            self.assertFalse(any(row["forecast_authorized"]
                                 for row in horizon["pairs"]))

    def test_05_only_ppi_no_bank_source_cannot_authorize_any_usd_pair(self):
        ppi=self.ppi()
        r=self.run_it(ppi=ppi)
        self.active(r)
        self.assertEqual(r["policy_original_documents_locally_checked"],0)
        self.assertEqual(r["policy_recent_local_capture_claims"],0)
        self.assertTrue(r["ppi_oct2026_documentary_source_replayed"])
        for horizon in r["next_nominal_windows"]:
            usd=[x for x in horizon["pairs"] if "USD" in x["pair"]]
            non=[x for x in horizon["pairs"] if "USD" not in x["pair"]]
            self.assertEqual(len(usd),7)
            self.assertEqual(len(non),21)
            self.assertTrue(all(
                "USD_PPI_POST_RELEASE_DOCUMENTARY_ONLY_NO_CONSENSUS" in
                x["supplemental_context_notes"] for x in usd))
            self.assertTrue(all(not x["supplemental_context_notes"] for x in non))
            self.assertTrue(all("ONE_OR_BOTH_POLICY_DOCUMENTS_NOT_VALIDATED"
                                in x["blocking_reasons"] for x in horizon["pairs"]))

    def test_06_at_exact_open_no_backfill_first_d1_w1(self):
        with patch(
            "atlasquant_trader_fx28_pre_window_source_gate_lab.inspect_fx28_policy_ppi_readiness_lab",
            side_effect=AssertionError("must not replay future at prior open")
        ) as spy:
            r=self.run_it(at=FIRST)
        spy.assert_not_called()
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_PREWINDOW_NOT_ACTIVE_NO_GO")
        self.assertEqual(r["potential_slots_now_audited"],0)
        self.assertTrue(all(x["next_start_utc"]!=FIRST.isoformat()
                            for x in r["next_nominal_windows"]))
        self.assertFalse(r["pre_event_28_forecast_rosters_generated"])

    def test_07_one_second_before_open_still_readonly_56_slots(self):
        r=self.run_it(at=FIRST-timedelta(seconds=1))
        self.active(r)
        self.assertTrue(all(x["next_start_utc"]==FIRST.isoformat()
                            for x in r["next_nominal_windows"]))
        self.assertEqual(len(r["next_nominal_windows"][0]["pairs"]),28)
        self.assertEqual(len(r["next_nominal_windows"][1]["pairs"]),28)

    def test_08_november16_next_d1_only_w1_not_in_12h(self):
        r=self.run_it(at=MONDAY_START-timedelta(minutes=20))
        self.active(r,count=1)
        self.assertEqual(r["next_nominal_windows"][0]["horizon"],"D1")
        self.assertEqual(r["next_nominal_windows"][0]["status"],
                         "BLOCKED_SOURCES_INSUFFICIENT_FOR_28_FORECASTS")
        self.assertEqual(r["next_nominal_windows"][1]["horizon"],"W1")
        self.assertEqual(r["next_nominal_windows"][1]["status"],
                         "NOT_YET_IN_PREWINDOW_SOURCE_PREFLIGHT")
        self.assertEqual(r["next_nominal_windows"][1]["pairs"],[])

    def test_09_after_all_windows_no_prelaunch_and_no_backfill(self):
        r=self.run_it(at=FROZEN_END_UTC+timedelta(days=1))
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_PREWINDOW_NOT_ACTIVE_NO_GO")
        self.assertFalse(r["source_reader_was_called"])
        self.assertEqual(r["potential_slots_now_audited"],0)
        self.assertTrue(all(x["status"]==
                            "NO_FUTURE_FROZEN_WINDOWS_NO_BACKFILL"
                            for x in r["next_nominal_windows"]))

    def test_10_utc_and_mato_grosso_clock_same_source_vetoes(self):
        local=timezone(timedelta(hours=-4))
        a=self.run_it(at=PRE)
        b=self.run_it(at=PRE.astimezone(local))
        self.active(a)
        self.active(b)
        self.assertEqual(a,b)

    def test_11_bad_time_and_types_fail_closed_without_source_reads(self):
        for value in (None,"2026-11-15T21:30:00Z",PRE.replace(tzinfo=None),
                      PRE.replace(microsecond=1),0,True,
                      datetime(2026,11,11,20,tzinfo=UTC)):
            with self.subTest(value=value):
                with patch(
                    "atlasquant_trader_fx28_pre_window_source_gate_lab.inspect_fx28_policy_ppi_readiness_lab"
                ) as reader:
                    r=self.run_it(at=value)
                reader.assert_not_called()
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_FX28_PREWINDOW_SOURCE_GATE_BLOCKED_NO_GO")
                self.assertEqual(r["next_nominal_windows"],[])

    def test_12_strange_archive_names_and_root_types_never_fake_sources(self):
        for bad in (42, True, "", [], {}):
            with self.subTest(archive=bad):
                r=self.run_it(ppi=bad)
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_FX28_PREWINDOW_SOURCE_GATE_BLOCKED_NO_GO")
                self.assertFalse(r["source_reader_was_called"])
        for bad in (True,42, "relative"):
            with self.subTest(root=bad):
                r=self.run_it(root=bad)
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_FX28_PREWINDOW_SOURCE_GATE_BLOCKED_NO_GO")

    def test_13_corrupted_ppi_document_is_not_a_signed_usd_event(self):
        ppi=self.ppi()
        path=(Path(self.temp.name)/"AtlasQuant"/"LAB"/
              "official_macro_receipts"/ppi/"original.html")
        path.write_bytes(path.read_bytes()+b"tampered")
        r=self.run_it(ppi=ppi)
        self.active(r)
        self.assertFalse(r["ppi_oct2026_documentary_source_replayed"])
        for h in r["next_nominal_windows"]:
            usd=[x for x in h["pairs"] if "USD" in x["pair"]]
            self.assertTrue(all("USD_PPI_LOCAL_DOCUMENT_NOT_REPLAYED"
                                in x["supplemental_context_notes"]
                                for x in usd))

    def test_14_unified_reader_error_is_not_silent_success(self):
        with patch(
            "atlasquant_trader_fx28_pre_window_source_gate_lab.inspect_fx28_policy_ppi_readiness_lab",
            side_effect=OSError("synthetic failure")
        ) as reader:
            r=self.run_it()
        reader.assert_called_once()
        self.safe(r)
        self.assertTrue(r["source_reader_was_called"])
        self.assertEqual(r["state"],"LAB_FX28_PREWINDOW_SOURCE_GATE_BLOCKED_NO_GO")
        self.assertEqual(r["reason"],
                         "SOURCE_READER_EXCEPTION_NOT_AN_ISSUED_FORECAST")
        self.assertEqual(sum(len(x["pairs"]) for x in r["next_nominal_windows"]),0)

    def test_15_synthetic_tampered_go_report_must_not_authorize_forecasts(self):
        fake={
            "schema":"ATLASQUANT_TRADER_FX28_POLICY_PPI_UNIFIED_READINESS_LAB_V1",
            "state":"LIVE_GO",
            "operational_bias":"COMPRA",
            "trade_authorized":True,
            "publishable":True,
            "fx28_pairs_reported":28,
            "per_pair":[{"pair":"EUR/USD","bias":"COMPRA"}]*28,
        }
        with patch(
            "atlasquant_trader_fx28_pre_window_source_gate_lab.inspect_fx28_policy_ppi_readiness_lab",
            return_value=fake
        ) as reader:
            r=self.run_it()
        reader.assert_called_once()
        self.safe(r)
        self.assertEqual(r["reason"],
                         "SOURCE_READER_BLOCKED_OR_CLAIMS_NOT_COHERENT")
        self.assertEqual(r["potential_slots_now_audited"],56)
        self.assertFalse(r["ready_for_d1_forecast"])
        self.assertEqual(sum(len(x["pairs"]) for x in r["next_nominal_windows"]),0)

    def test_16_all_eight_docs_still_missing_cpi_and_broker_model(self):
        self.banks(CURRENCIES)
        r=self.run_it()
        self.active(r)
        for h in r["next_nominal_windows"]:
            for x in h["pairs"]:
                self.assertIn("ISSUER_FIRST_SEEN_NOT_INDEPENDENTLY_AUTHENTICATED",
                              x["blocking_reasons"])
                self.assertIn("FX28_DIRECTION_MODEL_NOT_CALIBRATED",
                              x["blocking_reasons"])
                self.assertIn("BROKER_M15_PRICES_NOT_AUTHENTICATED",
                              x["blocking_reasons"])
                self.assertIn("MONETARY_EXPECTATIONS_AND_CALENDAR_PIT_MISSING",
                              x["blocking_reasons"])
        self.assertFalse(r["ready_for_w1_forecast"])

    def test_17_cli_without_flag_is_readonly_with_zero_source_access(self):
        out=io.StringIO()
        with patch(
            "atlasquant_trader_fx28_pre_window_source_gate_lab.inspect_fx28_pre_window_source_gate_lab",
            side_effect=AssertionError("no implicit local file scan")
        ) as spy:
            with redirect_stdout(out):
                code=main([])
        spy.assert_not_called()
        self.assertEqual(code,2)
        r=json.loads(out.getvalue())
        self.safe(r)
        self.assertFalse(r["source_reader_was_called"])

    def test_18_cli_explicit_sunday_preflight_reports_56_blocked_no_net(self):
        self.banks(CURRENCIES)
        ppi=self.ppi()
        with patch.dict(os.environ,{"LOCALAPPDATA":self.temp.name}), patch(
            "atlasquant_trader_fx28_pre_window_source_gate_lab._now",
            return_value=PRE
        ), patch(
            "urllib.request.urlopen",
            side_effect=AssertionError("no HTTP")
        ) as web:
            out=io.StringIO()
            with redirect_stdout(out):
                status=main(["--preflight","--ppi-archive",ppi])
        web.assert_not_called()
        self.assertEqual(status,2)
        r=json.loads(out.getvalue())
        self.active(r)
        self.assertEqual(r["ppi_oct2026_documentary_source_replayed"],True)
        self.assertEqual(r["policy_original_documents_locally_checked"],8)

    def test_19_source_audit_does_not_change_disk_sha(self):
        folder=self.banks(CURRENCIES)
        ppi=self.ppi()
        before={p.name:sha256(p.read_bytes()).hexdigest()
                for p in folder.glob("*") if p.is_file()}
        r=self.run_it(ppi=ppi)
        self.active(r)
        after={p.name:sha256(p.read_bytes()).hexdigest()
               for p in folder.glob("*") if p.is_file()}
        self.assertEqual(before,after)
        self.assertEqual(r["file_writes"],0)

    def test_20_ppi_optional_does_not_fetch_network_or_require_usd_event(self):
        self.banks(CURRENCIES)
        with patch(
            "atlasquant_trader_fx28_policy_ppi_unified_readiness_lab.replay_oct2026_bls_original_capture_lab",
            side_effect=AssertionError("PPI reader should not be called")
        ) as reader:
            r=self.run_it()
        reader.assert_not_called()
        self.active(r)
        self.assertFalse(r["ppi_oct2026_documentary_source_replayed"])
        for h in r["next_nominal_windows"]:
            self.assertFalse(any(x["ppi_as_signed_currency_factor"]
                                 for x in h["pairs"]))


if __name__=="__main__":
    unittest.main()
