"""FX28 panel must never turn BLS retrospective PPI vintage into a signal.

All mocked factor summaries/HTMLs are synthetic. Real BLS originals are
replayed separately in the GitHub E2E. Bank policy evidence is NOT invented.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from atlasquant_trader_fx28_single_readiness_panel_lab import (
    inspect_fx28_single_readiness_panel_lab as panel,
)
from atlasquant_trader_us_ppi_sep2026_two_real_vintages_lab import (
    SEP_HASH, OCT_HASH, SEP_CAPTURE, OCT_CAPTURE,
)
from test_atlasquant_trader_fx28_single_readiness_panel_lab import (
    mock_policy, mock_factors,
)
from test_atlasquant_trader_fx28_ppi_revision_source_admission_lab import (
    synthetic_success_vintage_claim,
)
from atlasquant_trader_fx28_32_factor_source_admission_lab import (
    inspect_fx28_32_factor_source_admission_lab as factor_admission,
)

FUTURE = SEP_CAPTURE + timedelta(days=1)
FAKE_BYTES = (b"S"*120_000, b"O"*120_000)


def synthetic_factor_report(*, revision=False, count=0):
    out=mock_factors(0)
    out.update({
        "ppi_sep2026_vintage_context_requested": revision,
        "ppi_sep2026_verified_original_count_at_local_cutoff": count,
        "ppi_sep2026_first_release_and_revision_reconciled_local_only": (
            revision and count == 2),
    })
    if revision:
        from atlasquant_trader_fx28_32_factor_source_admission_lab import (
            _blocked,
        )
        with TemporaryDirectory() as root:
            with patch(
                "atlasquant_trader_fx28_32_factor_source_admission_lab."
                "inspect_real_ppi_sep2026_release_vintages_lab",
                return_value=synthetic_success_vintage_claim()
                if count==2 else _partial_claim(count),
            ):
                # The **genuine** source-admission function creates the
                # factor roster and typed vintage context, but the positive
                # underlying vintage result is expressly a MOCK.
                actual=factor_admission(
                    local_appdata=root, decision_at_utc=FUTURE,
                    ppi_sep2026_two_vintage_originals=FAKE_BYTES,
                )
        assert actual["state"]=="LAB_FX28_32_FACTOR_DOCUMENTARY_GAP_RECONCILED_NO_GO",actual
        return actual
    return out


def _partial_claim(count):
    from atlasquant_trader_us_ppi_sep2026_two_real_vintages_lab import _blocked
    result=_blocked("ONE_OR_BOTH_ORIGINALS_NOT_YET_CAPTURED_AT_LOCAL_CUTOFF",
                    visible=count)
    return result


class PanelPpiVintageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def run_it(self, *, at=FUTURE, originals=None, factors=None, policy=None):
        f=synthetic_factor_report() if factors is None else factors
        with (patch(
            "atlasquant_trader_fx28_single_readiness_panel_lab."
            "inspect_fx28_official_policy_archive_replay_lab",
            return_value=mock_policy(()) if policy is None else policy),
              patch(
            "atlasquant_trader_fx28_single_readiness_panel_lab."
            "inspect_fx28_32_factor_source_admission_lab",
            return_value=f)):
            return panel(local_appdata=self.tmp.name,inspected_at_utc=at,
                         ppi_sep2026_two_vintage_originals=originals)

    def safe(self,r):
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["model_direction_calibrated"])
        self.assertFalse(r["ppi_sep2026_revision_available_to_oct15_model"])
        self.assertTrue(r["ppi_sep2026_revision_is_not_signed_fx_impact"])
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertIsNone(r["validated_fx28_accuracy"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertIsNone(r["directional_bias"])
        self.assertEqual(r["new_cost_brl"],0)
        self.assertEqual(r["http_requests"],0)

    def test_01_default_no_vintage_preserves_672_and_no_bias(self):
        r=self.run_it()
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_SINGLE_READINESS_PANEL_RECONCILED_NO_GO")
        self.assertEqual(r["slots_accounted"],672)
        self.assertEqual(r["factors_expected"],32)
        self.assertFalse(r["ppi_sep2026_vintage_input_requested"])
        self.assertEqual(r["ppi_sep2026_locally_verified_original_count"],0)
        self.assertIsNone(r["ppi_sep2026_revision_documentary_summary"])

    def test_02_mock_full_history_reports_both_issuance_dates_without_bias(self):
        r=self.run_it(originals=FAKE_BYTES,
                      factors=synthetic_factor_report(revision=True,count=2))
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_SINGLE_READINESS_PANEL_RECONCILED_NO_GO")
        self.assertEqual(r["slots_accounted"],672)
        self.assertTrue(r["ppi_sep2026_vintage_input_requested"])
        self.assertEqual(r["ppi_sep2026_locally_verified_original_count"],2)
        s=r["ppi_sep2026_revision_documentary_summary"]
        self.assertEqual(s["reference_period"],"2026-09")
        self.assertEqual((s["initial_release_date"],s["revised_release_date"]),
                         ("2026-10-15","2026-11-13"))
        self.assertEqual((s["initial_headline_pct"],s["revised_headline_pct"]),
                         ("1.3","1.4"))
        self.assertEqual((s["initial_core_ex_food_energy_pct"],
                          s["revised_core_ex_food_energy_pct"]),("0.7","0.8"))
        self.assertEqual(s["original_source_sha256_pair"],[SEP_HASH,OCT_HASH])
        self.assertFalse(s["first_seen_by_model_on_original_release_date_authenticated"])
        self.assertFalse(s["contributes_calibrated_signed_macro_impact"])

    def test_03_partial_vintage_zero_and_one_do_not_leak_revised_number(self):
        for count in (0,1):
            r=self.run_it(originals=FAKE_BYTES,
                          factors=synthetic_factor_report(revision=True,count=count))
            self.safe(r)
            self.assertEqual(r["state"],"LAB_FX28_SINGLE_READINESS_PANEL_RECONCILED_NO_GO")
            self.assertEqual(r["ppi_sep2026_locally_verified_original_count"],count)
            self.assertIsNone(r["ppi_sep2026_revision_documentary_summary"])

    def test_04_malformed_inputs_veto_before_read(self):
        for blobs in ((),(b"a",),["a","b"],("foo","bar"),
                      (b"x"*4_194_305,b"y"*120_000),True):
            r=self.run_it(originals=blobs)
            self.safe(r)
            self.assertEqual(r["state"],"LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")
            self.assertEqual(r["slots_accounted"],0)

    def test_05_claim_of_context_when_no_bytes_passed_is_rejected(self):
        f=synthetic_factor_report(revision=True,count=2)
        r=self.run_it(originals=None,factors=f)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")

    def test_06_caller_supplied_context_claim_not_verifier_is_rejected(self):
        f=synthetic_factor_report(revision=True,count=2)
        f["ppi_sep2026_vintage_context_requested"]=False
        r=self.run_it(originals=FAKE_BYTES,factors=f)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")

    def test_07_forged_revised_sha_rejected(self):
        f=synthetic_factor_report(revision=True,count=2)
        f["ppi_sep2026_vintage_research_context"]["later_release_revision"][
            "original_html_sha256"]="0"*64
        r=self.run_it(originals=FAKE_BYTES,factors=f)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")

    def test_08_wrong_revision_date_rejected(self):
        f=synthetic_factor_report(revision=True,count=2)
        f["ppi_sep2026_vintage_research_context"]["later_release_revision"][
            "release_date"]="2026-10-15"
        r=self.run_it(originals=FAKE_BYTES,factors=f)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")

    def test_09_wrong_currency_or_series_rejected(self):
        for key,value in (("currency","JPY"),
                          ("core_ex_food_energy_series_code","FD/49116")):
            f=synthetic_factor_report(revision=True,count=2)
            f["ppi_sep2026_vintage_research_context"][key]=value
            r=self.run_it(originals=FAKE_BYTES,factors=f)
            self.safe(r)
            self.assertEqual(r["state"],"LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")

    def test_10_revision_falsely_claimed_available_oct15_rejected(self):
        f=synthetic_factor_report(revision=True,count=2)
        f["ppi_sep2026_vintage_research_context"][
            "backtest_as_if_2026_10_15_known"]=True
        r=self.run_it(originals=FAKE_BYTES,factors=f)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")

    def test_11_duplicate_usd_inflation_context_rejected(self):
        f=synthetic_factor_report(revision=True,count=2)
        attached=[s for s in f["factor_slots"] if
                  s["ppi_sep2026_historical_two_release_revision_context"] is not None]
        self.assertEqual(len(attached),1)
        f["factor_slots"][0][
            "ppi_sep2026_historical_two_release_revision_context"]=(
                attached[0]["ppi_sep2026_historical_two_release_revision_context"])
        r=self.run_it(originals=FAKE_BYTES,factors=f)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")

    def test_12_context_attached_to_non_usd_slot_rejected(self):
        f=synthetic_factor_report(revision=True,count=2)
        for slot in f["factor_slots"]:
            if slot["ppi_sep2026_historical_two_release_revision_context"] is not None:
                slot["currency"]="CAD"
        r=self.run_it(originals=FAKE_BYTES,factors=f)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")

    def test_13_spoofed_signed_impact_in_vintage_slot_rejected(self):
        f=synthetic_factor_report(revision=True,count=2)
        for slot in f["factor_slots"]:
            if slot["ppi_sep2026_historical_two_release_revision_context"] is not None:
                slot["signed_impact_points_admitted"]=90
        r=self.run_it(originals=FAKE_BYTES,factors=f)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")

    def test_14_positive_revision_but_count_one_rejected(self):
        f=synthetic_factor_report(revision=True,count=2)
        f["ppi_sep2026_verified_original_count_at_local_cutoff"]=1
        r=self.run_it(originals=FAKE_BYTES,factors=f)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")

    def test_15_partial_count_with_leaked_revision_claim_rejected(self):
        f=synthetic_factor_report(revision=True,count=1)
        f["ppi_sep2026_vintage_research_context"]={
            "later_release_revision":{"headline_pct":"1.4"}}
        r=self.run_it(originals=FAKE_BYTES,factors=f)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")

    def test_16_default_ignores_future_vintage_provenance_no_preview(self):
        f=synthetic_factor_report()
        f["ppi_sep2026_verified_original_count_at_local_cutoff"]=2
        r=self.run_it(originals=None,factors=f)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")

    def test_17_mutating_retrospective_report_cannot_unlock_directional_bias(self):
        f=synthetic_factor_report(revision=True,count=2)
        f["factor_slots_with_calibrated_directional_effect"]=1
        r=self.run_it(originals=FAKE_BYTES,factors=f)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO")


if __name__=="__main__":
    unittest.main()
