"""Temporal/source adversarial tests. Real local reader; no market predictions."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from contextlib import redirect_stdout
import io
import json
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import _nominal_windows
from atlasquant_trader_fx28_32_factor_source_admission_lab import (
    inspect_fx28_32_factor_source_admission_lab as factor_reader,
)
from atlasquant_trader_fx28_pre_window_32_factor_source_veto_lab import (
    SCHEMA, inspect_fx28_32_factor_pre_window_lab as inspect, main,
)

UTC = timezone.utc
START = _nominal_windows("D1")[0][0]
PRE = START - timedelta(hours=2)


class Fx28Prewindow32FactorSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def run_it(self, *, at=PRE, ppi=None, cpi=None, root=None):
        return inspect(
            local_appdata=self.tmp.name if root is None else root,
            inspected_at_utc=at, ppi_archive_basename=ppi,
            cpi_archive_basename=cpi)

    def real_factor(self):
        return factor_reader(
            local_appdata=self.tmp.name, decision_at_utc=PRE,
            ppi_archive_basename=None, cpi_archive_basename=None,
            hypothetical_factors=None)

    def safe(self, r):
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["expected_pair_horizon_opportunities"], 672)
        self.assertEqual(r["expected_d1_opportunities"], 560)
        self.assertEqual(r["expected_w1_opportunities"], 112)
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["pre_event_forecast_issued"])
        self.assertFalse(r["forecasts_precommitted_to_github"])
        self.assertFalse(r["broker_m15_authenticated"])
        self.assertFalse(r["directional_impact_calibrated"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertIsNone(r["out_of_sample_accuracy"])
        self.assertIsNone(r["forecast_direction"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertEqual((r["network_requests"], r["file_writes"],
                          r["new_cost_brl"]), (0, 0, 0))
        for w in r["windows"]:
            for row in w["pairs"]:
                self.assertEqual(row["operational_bias"], "AGUARDAR")
                self.assertIsNone(row["forecast_direction"])
                self.assertIsNone(row["calibrated_probability"])
                self.assertFalse(row["trade_authorized"])
                self.assertFalse(row["forecast_issued"])

    def test_01_before_12h_no_archive_reader(self):
        at = START - timedelta(hours=12, seconds=1)
        with patch(
            "atlasquant_trader_fx28_pre_window_32_factor_source_veto_lab."
            "inspect_fx28_32_factor_source_admission_lab",
            side_effect=AssertionError("should not scan before the 12h window")
        ) as spy:
            out = self.run_it(at=at)
        spy.assert_not_called()
        self.safe(out)
        self.assertEqual(out["state"], "LAB_FX28_32_PREWINDOW_INACTIVE_NO_GO")
        self.assertEqual(out["active_nominal_windows"], 0)
        self.assertEqual(out["potential_pair_horizon_slots"], 0)

    def test_02_first_exact_12h_gate_uses_real_local_reader(self):
        out = self.run_it(at=START-timedelta(hours=12))
        self.safe(out)
        self.assertEqual(out["state"], "LAB_FX28_32_PREWINDOW_DOCUMENTARY_VETO_NO_GO")
        self.assertTrue(out["source_reader_was_called"])
        self.assertEqual(out["active_nominal_windows"], 2)
        self.assertEqual(out["potential_pair_horizon_slots"], 56)
        self.assertEqual(out["factor_slots_inspected"], 32)
        self.assertEqual(sum(len(w["pairs"]) for w in out["windows"]), 56)
        self.assertEqual(out["factor_slots_with_verified_signed_impact"], 0)
        self.assertEqual(out["factor_slots_with_local_documentary_context"], 0)

    def test_03_real_empty_archive_audit_has_all_pairs_and_factor_reasons(self):
        out = self.run_it()
        self.safe(out)
        self.assertEqual(out["source_replayed_eight_banks_count"], 0)
        self.assertEqual(out["source_replayed_ppi_count"], 0)
        self.assertEqual(out["source_replayed_cpi_count"], 0)
        self.assertEqual(out["factor_slots_with_verified_pre_event_consensus"], 0)
        for win in out["windows"]:
            self.assertEqual([x["pair"] for x in win["pairs"]], list(OFFICIAL_PAIRS))
            self.assertTrue(all(len(x["base_factor_gaps"]) == 4
                                and len(x["quote_factor_gaps"]) == 4
                                for x in win["pairs"]))
            self.assertFalse(any(x["usd_cpi_documentary_context_only"]
                                 or x["usd_ppi_documentary_context_only"]
                                 for x in win["pairs"]))

    def test_04_at_window_open_no_backdated_forecast_or_archive_read(self):
        with patch(
            "atlasquant_trader_fx28_pre_window_32_factor_source_veto_lab."
            "inspect_fx28_32_factor_source_admission_lab",
            side_effect=AssertionError("cannot backfill")
        ) as spy:
            out = self.run_it(at=START)
        spy.assert_not_called()
        self.safe(out)
        self.assertEqual(out["state"], "LAB_FX28_32_PREWINDOW_INACTIVE_NO_GO")
        self.assertEqual(out["potential_pair_horizon_slots"], 0)

    def test_05_malformed_or_future_clock_fails_closed(self):
        for at in (None, "2026-11-15T20:00:00+00:00",
                   PRE.replace(tzinfo=None), PRE.replace(microsecond=1),
                   datetime(2026,11,12,18,0,tzinfo=UTC)):
            with self.subTest(at=at):
                out = self.run_it(at=at)
                self.safe(out)
                self.assertEqual(out["state"], "LAB_FX28_32_PREWINDOW_BLOCKED_NO_GO")
                self.assertFalse(out["source_reader_was_called"])

    def test_06_unsafe_fake_go_is_rejected_not_forecasted(self):
        fake = self.real_factor()
        fake["state"] = "LIVE_GO"
        fake["real_directional_forecast_authorized"] = True
        with patch(
            "atlasquant_trader_fx28_pre_window_32_factor_source_veto_lab."
            "inspect_fx28_32_factor_source_admission_lab", return_value=fake
        ) as spy:
            out = self.run_it()
        spy.assert_called_once()
        self.safe(out)
        self.assertEqual(out["state"], "LAB_FX28_32_PREWINDOW_BLOCKED_NO_GO")
        self.assertEqual(sum(len(x["pairs"]) for x in out["windows"]), 0)

    def test_07_one_signed_impact_or_duplicate_slot_is_fatal(self):
        for attack in ("positive-impact", "duplicate-slot", "unverified-cpi"):
            with self.subTest(attack=attack):
                fake = deepcopy(self.real_factor())
                if attack == "positive-impact":
                    fake["factor_slots"][0]["signed_impact_points_admitted"] = 98
                elif attack == "duplicate-slot":
                    fake["factor_slots"][1] = deepcopy(fake["factor_slots"][0])
                else:
                    fake["locally_replayed_cpi_u_nsa_document_count"] = 1
                    fake["factor_slots_with_any_relevant_local_document"] = 1
                    fake["distinct_original_document_sha_claim_count"] = 1
                    fake["cpi_reference_archive_reconciled_with_local_api_levels"] = False
                with patch(
                    "atlasquant_trader_fx28_pre_window_32_factor_source_veto_lab."
                    "inspect_fx28_32_factor_source_admission_lab",
                    return_value=fake):
                    out = self.run_it()
                self.safe(out)
                self.assertEqual(out["state"], "LAB_FX28_32_PREWINDOW_BLOCKED_NO_GO")
                self.assertEqual(out["factor_slots_inspected"], 0)

    def test_08_reader_failure_does_not_invent_source_readiness(self):
        with patch(
            "atlasquant_trader_fx28_pre_window_32_factor_source_veto_lab."
            "inspect_fx28_32_factor_source_admission_lab",
            side_effect=OSError("offline demo")):
            out = self.run_it()
        self.safe(out)
        self.assertTrue(out["source_reader_was_called"])
        self.assertEqual(out["reason"], "SOURCE_READER_EXCEPTION_NO_FORECAST")

    def test_09_missing_sources_cannot_be_rebranded_as_no_market_data(self):
        root = str(Path(self.tmp.name)/"missing-no-files")
        out = self.run_it(root=root)
        self.safe(out)
        self.assertEqual(out["state"], "LAB_FX28_32_PREWINDOW_BLOCKED_NO_GO")
        self.assertEqual(out["reason"], "SOURCE_AUDIT_MALFORMED_OR_UNSAFE_NO_FORECAST")
        self.assertEqual(out["factor_slots_inspected"], 0)

    def test_10_manual_cli_flag_required_never_authorizes(self):
        buf = io.StringIO()
        with patch(
            "atlasquant_trader_fx28_pre_window_32_factor_source_veto_lab."
            "inspect_fx28_32_factor_pre_window_lab",
            side_effect=AssertionError("no implicit audit")) as spy:
            with redirect_stdout(buf):
                code = main([])
        spy.assert_not_called()
        self.assertEqual(code, 2)
        out = json.loads(buf.getvalue())
        self.safe(out)
        self.assertEqual(out["reason"], "EXPLICIT_PREFLIGHT_REQUIRED")

    def test_11_readonly_archive_state_and_no_network(self):
        before = sorted(Path(self.tmp.name).rglob("*"))
        with patch("urllib.request.urlopen", side_effect=AssertionError("HTTP forbidden")) as web:
            out = self.run_it()
        web.assert_not_called()
        self.safe(out)
        self.assertEqual(before, sorted(Path(self.tmp.name).rglob("*")))


if __name__ == "__main__":
    unittest.main()
