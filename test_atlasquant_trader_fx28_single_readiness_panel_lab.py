"""No live network: synthetic issuer/factor reports, real frozen census."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from atlasquant_fx_universe import CURRENCIES
from atlasquant_trader_fx28_single_readiness_panel_lab import (
    inspect_fx28_single_readiness_panel_lab as inspect, main,
)
from atlasquant_trader_fx28_policy_local_archive_replay_lab import (
    _base as policy_base,
)
from atlasquant_trader_fx28_32_factor_source_admission_lab import (
    _blocked as factor_base,
)

UTC=timezone.utc
NOW=datetime(2026,11,14,0,25,tzinfo=UTC)
FIRST=datetime(2026,11,15,22,tzinfo=UTC)


def mock_policy(currencies=("AUD","CAD","EUR","GBP","USD"), *, rejected=()):
    result=policy_base("SYNTHETIC_LOCAL_SOURCE_ONLY")
    checked=sorted(currencies)
    rej={code:"SYNTHETIC_VALIDATOR_REFUSED" for code in rejected}
    missing=sorted(set(CURRENCIES)-set(checked)-set(rej))
    pairs=len(checked)*(len(checked)-1)//2
    result.update(
        schema="ATLASQUANT_FX28_LOCAL_POLICY_SOURCE_ARCHIVE_REPLAY_LAB_V1",
        state="LAB_FX28_POLICY_ARCHIVE_PARTIAL_OR_REJECTED_NO_GO"
              if len(checked)!=8 else
              "LAB_FX28_POLICY_ARCHIVE_EIGHT_ORIGINALS_LOCAL_ONLY_NO_GO",
        currencies_locally_checked=checked,
        currencies_missing=missing,
        currencies_rejected=rej,
        currencies_with_local_original_bytes_validated=len(checked),
        pairs_with_both_policy_originals_locally_checked=pairs,
        pairs_lacking_at_least_one_policy_original=28-pairs,
    )
    return result


def mock_factors(count=5, *, ppi=False, cpi=False):
    result=factor_base("SYNTHETIC_CONTEXT_ONLY")
    result.update(
        state="LAB_FX28_32_FACTOR_DOCUMENTARY_GAP_RECONCILED_NO_GO",
        source_audit_state="LAB_FX28_POLICY_PPI_COMBINED_READONLY_NO_GO",
        locally_replayed_policy_issuer_count=count,
        locally_replayed_ppi_document_count=int(ppi),
        locally_replayed_cpi_u_nsa_document_count=int(cpi),
        factor_slots_inspected=32,
        factor_slots_with_any_relevant_local_document=
            count+int(ppi or cpi),
        factor_slots_with_signed_impact_independently_admissible=0,
        factor_slots_with_pre_event_consensus_verified=0,
        factor_slots_with_calibrated_directional_effect=0,
        real_directional_forecast_authorized=False,
    )
    return result


class Fx28ReadinessPanelTests(unittest.TestCase):
    def run_panel(self,*,now=NOW,policy=None,factors=None,
                  ppi_archive=None,cpi_archive=None):
        policy=mock_policy() if policy is None else policy
        factors=mock_factors() if factors is None else factors
        with (patch("atlasquant_trader_fx28_single_readiness_panel_lab."
                    "inspect_fx28_official_policy_archive_replay_lab",
                    return_value=policy),
              patch("atlasquant_trader_fx28_single_readiness_panel_lab."
                    "inspect_fx28_32_factor_source_admission_lab",
                    return_value=factors)):
            return inspect(local_appdata="/synthetic/isolated/lab",
                           inspected_at_utc=now,
                           ppi_archive_basename=ppi_archive,
                           cpi_archive_basename=cpi_archive)

    def safe(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertIsNone(r["validated_fx28_accuracy"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertIsNone(r["directional_bias"])
        self.assertTrue(r["source_page_link_is_not_source_byte_capture"])
        self.assertTrue(r["policy_rate_is_not_policy_expectation"])
        self.assertTrue(r["document_count_is_not_signed_forecast_count"])
        self.assertTrue(r["empty_witness_input_does_not_prove_external_absence"])
        for key in ("witnesses_independently_authenticated",
                    "issuer_identity_and_first_seen_independently_authenticated",
                    "broker_m15_independently_authenticated",
                    "model_direction_calibrated","trade_authorized","publishable",
                    "live_alert_allowed","worker_enabled","scheduler_enabled"):
            self.assertFalse(r[key],key)
        self.assertEqual((r["http_requests"],r["file_writes"],
                          r["new_cost_brl"]),(0,0,0))

    def successful(self,r):
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_SINGLE_READINESS_PANEL_RECONCILED_NO_GO")
        self.assertEqual(r["slots_accounted"],672)
        self.assertEqual(r["factors_expected"],32)
        self.assertEqual(r["factors_with_independently_accepted_signed_effect"],0)
        self.assertEqual(r["factors_with_independent_pre_event_consensus"],0)
        self.assertEqual(r["factors_with_calibrated_directional_effect"],0)

    def test_01_real_frozen_ledger_and_mock_five_sources_compact(self):
        r=self.run_panel()
        self.successful(r)
        self.assertEqual(r["issuer_policy_document_count"],5)
        self.assertEqual(r["pairs_with_both_policy_documents"],10)
        self.assertEqual(r["pairs_lacking_policy_document"],18)
        self.assertEqual(r["issuer_policy_missing_currencies"],["CHF","JPY","NZD"])
        self.assertEqual(len(r["missing_issuer_reference_urls"]),3)
        self.assertEqual(r["factors_with_any_relevant_local_document"],5)
        self.assertEqual(r["slots_future_no_supplied_witness"],672)
        self.assertEqual(r["slots_past_no_supplied_witness"],0)
        self.assertEqual(r["next_frozen_start_utc"],FIRST.isoformat())

    def test_02_missing_sixth_bank_reconciles_three_source_pairs(self):
        r=self.run_panel(
            policy=mock_policy(("EUR","GBP","USD")),
            factors=mock_factors(3))
        self.successful(r)
        self.assertEqual(r["pairs_with_both_policy_documents"],3)
        self.assertEqual(r["issuer_policy_document_count"],3)
        self.assertEqual(r["pairs_lacking_policy_document"],25)

    def test_03_all_eight_bank_documents_still_do_not_enable_bias(self):
        r=self.run_panel(policy=mock_policy(tuple(CURRENCIES)),
                         factors=mock_factors(8))
        self.successful(r)
        self.assertEqual(r["pairs_with_both_policy_documents"],28)
        self.assertEqual(r["issuer_policy_missing_currencies"],[])
        self.assertEqual(r["missing_issuer_reference_urls"],{})
        self.assertEqual(r["factors_with_calibrated_directional_effect"],0)

    def test_04_rejected_bank_status_separate_from_missing(self):
        r=self.run_panel(
            policy=mock_policy(rejected=("CHF",)),
            factors=mock_factors(5))
        self.successful(r)
        self.assertEqual(r["issuer_policy_rejected_currencies"],["CHF"])
        self.assertEqual(r["issuer_policy_missing_currencies"],["JPY","NZD"])

    def test_05_denied_fake_source_does_not_count_mismatched_factors(self):
        f=mock_factors(6)
        r=self.run_panel(factors=f)
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")
        self.assertEqual(r["slots_accounted"],0)

    def test_06_fake_calibrated_effect_fails_closed(self):
        f=mock_factors()
        f["factor_slots_with_calibrated_directional_effect"]=1
        r=self.run_panel(factors=f)
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")

    def test_07_forged_tradable_source_blocks_whole_panel(self):
        p=mock_policy()
        p["trade_authorized"]=True
        r=self.run_panel(policy=p)
        self.safe(r)
        self.assertEqual(r["slots_accounted"],0)

    def test_08_universe_coverage_counter_forgery_is_rejected(self):
        p=mock_policy()
        p["pairs_with_both_policy_originals_locally_checked"]=28
        r=self.run_panel(policy=p)
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")

    def test_09_duplicate_currency_and_missing_overlap_rejected(self):
        p=mock_policy()
        p["currencies_locally_checked"]=["AUD","CAD","EUR","GBP","USD","USD"]
        r=self.run_panel(policy=p)
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")

    def test_10_first_open_56_due_in_input_only_never_true_github_absence(self):
        r=self.run_panel(now=FIRST)
        self.successful(r)
        self.assertEqual(r["slots_future_no_supplied_witness"],616)
        self.assertEqual(r["slots_past_no_supplied_witness"],56)
        self.assertTrue(r["empty_witness_input_does_not_prove_external_absence"])

    def test_11_frozen_last_open_after_all_672_are_due_in_input(self):
        r=self.run_panel(now=datetime(2026,12,12,tzinfo=UTC))
        self.successful(r)
        self.assertEqual(r["slots_future_no_supplied_witness"],0)
        self.assertEqual(r["slots_past_no_supplied_witness"],672)
        self.assertIsNone(r["next_frozen_start_utc"])

    def test_12_naive_future_microsecond_bad_clock_rejected(self):
        for now in (NOW.replace(tzinfo=None),NOW+timedelta(microseconds=1),
                    "2026-11-14T00:25:00Z",None):
            with self.subTest(now=now):
                r=self.run_panel(now=now)
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")

    def test_13_real_empty_archive_never_misrepresented_as_document_ready(self):
        with TemporaryDirectory() as td:
            r=inspect(local_appdata=td,inspected_at_utc=NOW)
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")

    def test_14_no_flag_cli_has_no_reads_or_http(self):
        with (patch("atlasquant_trader_fx28_single_readiness_panel_lab."
                    "inspect_fx28_official_policy_archive_replay_lab") as a,
              patch("atlasquant_trader_fx28_single_readiness_panel_lab."
                    "inspect_fx28_32_factor_source_admission_lab") as b):
            self.assertEqual(main([]),2)
            a.assert_not_called()
            b.assert_not_called()

    def test_15_source_exception_no_partial_positive_dashboard(self):
        with patch("atlasquant_trader_fx28_single_readiness_panel_lab."
                   "inspect_fx28_official_policy_archive_replay_lab",
                   side_effect=OSError("synthetic read denied")):
            r=inspect(local_appdata="/synthetic/isolated/lab",
                      inspected_at_utc=NOW)
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")


    def test_16_two_recent_and_three_stale_are_not_five_realtime_sources(self):
        p=mock_policy()
        status={}
        for c in ("AUD","GBP"):
            status[c]={"selected_local_capture_utc_claim":"2026-11-14T00:00:00Z"}
        for c in ("USD","EUR","CAD"):
            status[c]={"selected_local_capture_utc_claim":"2026-11-12T22:00:00Z"}
        p["currency_archive_status"]=status
        r=self.run_panel(policy=p)
        self.successful(r)
        self.assertEqual(r["issuer_policy_document_count"],5)
        self.assertEqual(r["pairs_with_both_policy_documents"],10)
        self.assertEqual(r["recent_24h_local_receipt_claim_count"],2)
        self.assertEqual(r["recent_24h_bilateral_policy_pair_count"],1)
        self.assertEqual(r["recent_24h_local_receipt_claim_currencies"],
                         ["AUD","GBP"])
        self.assertEqual(r["stale_over_24h_local_receipt_claim_currencies"],
                         ["CAD","EUR","USD"])
        self.assertEqual(r["unknown_local_receipt_clock_currencies"],[])
        self.assertFalse(r["issuer_identity_and_first_seen_independently_authenticated"])

    def test_17_sunday_preflight_old_captures_do_not_remain_recent(self):
        p=mock_policy()
        p["currency_archive_status"]={
            c:{"selected_local_capture_utc_claim":
               "2026-11-13T23:56:00Z"} for c in p["currencies_locally_checked"]
        }
        sunday=datetime(2026,11,15,10,0,0,tzinfo=UTC)
        r=self.run_panel(now=sunday,policy=p)
        self.successful(r)
        self.assertEqual(r["recent_24h_local_receipt_claim_count"],0)
        self.assertEqual(r["recent_24h_bilateral_policy_pair_count"],0)
        self.assertEqual(len(r["stale_over_24h_local_receipt_claim_currencies"]),5)
        self.assertEqual(r["issuer_policy_document_count"],5)
        self.assertEqual(r["pairs_with_both_policy_documents"],10)
        self.assertEqual(r["slots_future_no_supplied_witness"],672)

    def test_18_exact_24h_boundary_is_recent_one_second_later_stale(self):
        p=mock_policy(("EUR","USD"))
        p["currency_archive_status"]={
            "EUR":{"selected_local_capture_utc_claim":"2026-11-13T00:25:00Z"},
            "USD":{"selected_local_capture_utc_claim":"2026-11-13T00:24:59Z"},
        }
        r=self.run_panel(policy=p,factors=mock_factors(2))
        self.successful(r)
        self.assertEqual(r["recent_24h_local_receipt_claim_currencies"],["EUR"])
        self.assertEqual(r["stale_over_24h_local_receipt_claim_currencies"],["USD"])
        self.assertEqual(r["recent_24h_bilateral_policy_pair_count"],0)

    def test_19_missing_clock_unknown_not_automatic_recent(self):
        p=mock_policy()
        r=self.run_panel(policy=p)
        self.successful(r)
        self.assertEqual(r["recent_24h_local_receipt_claim_count"],0)
        self.assertEqual(r["unknown_local_receipt_clock_currencies"],
                         ["AUD","CAD","EUR","GBP","USD"])
        self.assertTrue(r["capture_recency_is_not_rate_freshness_or_issuer_first_seen"])

    def test_20_malformed_future_and_spoofed_timestamp_all_fail_closed(self):
        for stamp in ("2026-11-14T00:25:01Z","2026-11-14T00:25:00+00:00",
                      "2026-13-14T00:25:00Z", "2026-11-14T00:25:00Z?fake",
                      "notatime", True):
            with self.subTest(stamp=stamp):
                p=mock_policy()
                p["currency_archive_status"]={"USD":{
                    "selected_local_capture_utc_claim":stamp}}
                r=self.run_panel(policy=p)
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")
                self.assertEqual(r["reason"],
                                 "POLICY_LOCAL_CAPTURE_RECEIPT_CLOCK_INCONSISTENT")

    def test_21_recent_policy_documents_still_zero_signed_macro_probabilities(self):
        p=mock_policy(tuple(CURRENCIES))
        p["currency_archive_status"]={
            c:{"selected_local_capture_utc_claim":"2026-11-14T00:20:00Z"}
            for c in CURRENCIES
        }
        r=self.run_panel(policy=p,factors=mock_factors(8))
        self.successful(r)
        self.assertEqual(r["recent_24h_local_receipt_claim_count"],8)
        self.assertEqual(r["recent_24h_bilateral_policy_pair_count"],28)
        self.assertEqual(r["factors_with_independently_accepted_signed_effect"],0)
        self.assertFalse(r["witnesses_independently_authenticated"])
        self.assertFalse(r["trade_authorized"])

    def test_22_clock_timestamp_cannot_be_credit_for_missing_currency(self):
        p=mock_policy()
        p["currency_archive_status"]={
            "CHF":{"selected_local_capture_utc_claim":"2026-11-14T00:20:00Z"},
            "AUD":{"selected_local_capture_utc_claim":"2026-11-14T00:20:00Z"},
        }
        r=self.run_panel(policy=p)
        self.successful(r)
        self.assertEqual(r["recent_24h_local_receipt_claim_currencies"],["AUD"])
        self.assertEqual(r["issuer_policy_missing_currencies"],["CHF","JPY","NZD"])

    def test_23_different_currency_receipt_age_types_and_none_fail_safely(self):
        p=mock_policy()
        p["currency_archive_status"]={"AUD":"2026-11-14T00:20:00Z"}
        r=self.run_panel(policy=p)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")
        p=mock_policy()
        p["currency_archive_status"]={"AUD":{
            "selected_local_capture_utc_claim":None}}
        r=self.run_panel(policy=p)
        self.successful(r)
        self.assertEqual(r["recent_24h_local_receipt_claim_count"],0)
        self.assertIn("AUD",r["unknown_local_receipt_clock_currencies"])


    def test_24_explicit_ppi_original_is_one_us_inflation_document_not_signal(self):
        r=self.run_panel(
            factors=mock_factors(ppi=True),
            ppi_archive="US_BLS_PPI_OCT2026_20261114T160053Z_5115165ee0d2")
        self.successful(r)
        self.assertTrue(r["ppi_original_local_replayed_for_context"])
        self.assertFalse(r["cpi_original_local_replayed_for_context"])
        self.assertEqual(r["factors_with_any_relevant_local_document"],6)
        self.assertTrue(r["ppi_cpi_documents_are_not_signed_usd_impacts"])
        self.assertIsNone(r["directional_bias"])

    def test_25_cpi_and_ppi_are_two_docs_but_one_us_inflation_factor_slot(self):
        r=self.run_panel(
            factors=mock_factors(ppi=True,cpi=True),
            ppi_archive="US_BLS_PPI_OCT2026_20261114T160053Z_5115165ee0d2",
            cpi_archive="US_BLS_CPI_U_NSA_SYNTHETIC_LAB")
        self.successful(r)
        self.assertTrue(r["ppi_original_local_replayed_for_context"])
        self.assertTrue(r["cpi_original_local_replayed_for_context"])
        self.assertEqual(r["factors_with_any_relevant_local_document"],6)
        self.assertEqual(r["factors_with_calibrated_directional_effect"],0)

    def test_26_requested_ppi_missing_or_forged_replay_is_blocked(self):
        for factors in (mock_factors(), mock_factors(ppi=True,cpi=True)):
            with self.subTest(counts=factors["locally_replayed_ppi_document_count"]):
                r=self.run_panel(
                    factors=factors,
                    ppi_archive="US_BLS_PPI_OCT2026_20261114T160053Z_5115165ee0d2")
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")
                self.assertFalse(r["ppi_original_local_replayed_for_context"])

    def test_27_no_default_ppi_or_cpi_read_and_invalid_inputs_denied(self):
        r=self.run_panel()
        self.successful(r)
        self.assertFalse(r["ppi_original_local_replayed_for_context"])
        self.assertFalse(r["cpi_original_local_replayed_for_context"])
        for value in ("",True,42):
            with self.subTest(value=value):
                r=self.run_panel(ppi_archive=value)
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")

    def test_28_explicit_archive_names_pass_through_to_real_factor_reader(self):
        ppi="US_BLS_PPI_OCT2026_20261114T160053Z_5115165ee0d2"
        with (patch("atlasquant_trader_fx28_single_readiness_panel_lab."
                    "inspect_fx28_official_policy_archive_replay_lab",
                    return_value=mock_policy()),
              patch("atlasquant_trader_fx28_single_readiness_panel_lab."
                    "inspect_fx28_32_factor_source_admission_lab",
                    return_value=mock_factors(ppi=True)) as factor_reader):
            report=inspect(
                local_appdata="/synthetic/isolated/lab",
                inspected_at_utc=NOW,ppi_archive_basename=ppi)
            self.successful(report)
            self.assertEqual(factor_reader.call_args.kwargs["ppi_archive_basename"],ppi)
            self.assertIsNone(factor_reader.call_args.kwargs["cpi_archive_basename"])
            self.assertIsNone(factor_reader.call_args.kwargs["hypothetical_factors"])


if __name__ == "__main__":
    unittest.main()
