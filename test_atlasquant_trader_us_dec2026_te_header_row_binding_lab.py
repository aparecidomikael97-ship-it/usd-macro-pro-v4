"""Reject TE Consensus header fragments across *rows* within one table.

All HTML, numeric values, source receipts and dates are synthetic. This is
source-parser structure QA, not November CPI/PPI market evidence.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import unittest

import test_atlasquant_trader_us_dec2026_consensus_semantic_candidate_lab as fx
from atlasquant_trader_us_dec2026_consensus_semantic_candidate_lab import (
    inspect_dec2026_consensus_semantic_candidate_lab as inspect,
)

CPI=fx.CPI
PPI=fx.PPI
BLOCKED="LAB_DEC2026_CONSENSUS_SEMANTICS_BLOCKED_HARD_NO_GO"
PROVISIONAL="LAB_DEC2026_TWO_SOURCE_PROVISIONAL_SEMANTICS_ONLY_HARD_NO_GO"


def te_with_html(root, raw):
    a,b=fx.pair(root)
    return a,replace(b,html_original_bytes=raw,
                     original_sha256_claim=sha256(raw).hexdigest())


def review(root=CPI,raw=None,include_other=False):
    docs=(fx.pair(root) if raw is None else te_with_html(root,raw))
    if include_other:
        docs+=fx.pair(PPI if root==CPI else CPI)
    return inspect(source_snapshots=docs,inspected_at_utc=fx.POST)


class TEHeaderPhysicalRowBindingTests(unittest.TestCase):
    def rejected(self,root=CPI,raw=None,include_other=False):
        result=review(root,raw,include_other)
        self.assertEqual(result["state"],BLOCKED)
        self.assertEqual(result["frozen_economic_event_denominator"],2)
        self.assertEqual(result["local_two_source_candidate_event_count"],0)
        self.assertTrue(all(
            row["provisional_consensus_headline_mom_sa_pct"] is None
            and row["provisional_consensus_core_mom_sa_pct"] is None
            and row["td_html_sha256_local_claim"] is None
            for row in result["events"]))
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertEqual(result["registered_directional_fx_predictions"],0)
        self.assertIsNone(result["win_rate"])
        return result

    def permitted_provisional(self,root=CPI,raw=None):
        result=review(root,raw)
        self.assertEqual(result["state"],PROVISIONAL)
        self.assertEqual(result["local_two_source_candidate_event_count"],1)
        self.assertEqual(result["economic_consensus_pre_event_independently_authenticated"],0)
        self.assertEqual(result["registered_directional_fx_predictions"],0)
        self.assertFalse(result["events"][0 if root==CPI else 1]
                         ["consensus_eligible_for_fx_prediction"])
        self.assertFalse(result["trade_authorized"])
        return result

    def test_01_original_cpi_header_in_single_tr_still_parses(self):
        self.permitted_provisional(CPI)

    def test_02_original_ppi_header_in_single_tr_still_parses(self):
        self.permitted_provisional(PPI)

    def test_03_two_header_trs_actual_previous_vs_consensus_forecast_rejected(self):
        raw=fx.te_html(CPI)
        needle=b"</th><th>Consensus</th>"
        self.assertIn(needle,raw)
        raw=raw.replace(needle,b"</th></tr><tr><th>Consensus</th>",1)
        self.rejected(raw=raw)

    def test_04_four_header_trs_laundered_into_one_global_sequence_rejected(self):
        raw=fx.te_html(CPI)
        for heading in (b"Previous",b"Consensus",b"Forecast"):
            needle=b"</th><th>"+heading+b"</th>"
            self.assertIn(needle,raw)
            raw=raw.replace(needle,b"</th></tr><tr><th>"+heading+b"</th>",1)
        self.rejected(raw=raw)

    def test_05_ppi_header_split_across_rows_rejected(self):
        raw=fx.te_html(PPI).replace(
            b"</th><th>Forecast</th>",
            b"</th></tr><tr><th>Forecast</th>",1)
        self.rejected(PPI,raw)

    def test_06_heading_th_without_physical_tr_is_not_a_valid_header(self):
        raw=fx.te_html(CPI)
        old=(b"<thead><tr><th>Actual</th><th>Previous</th>"
             b"<th>Consensus</th><th>Forecast</th></tr></thead>")
        new=(b"<thead><th>Actual</th><th>Previous</th>"
             b"<th>Consensus</th><th>Forecast</th></thead>")
        self.assertIn(old,raw)
        self.rejected(raw=raw.replace(old,new,1))

    def test_07_extra_leading_header_shifts_column_geometry_and_blocks(self):
        raw=fx.te_html(CPI)
        raw=raw.replace(b"<tr><th>Actual</th>",
                        b"<tr><th>Market</th><th>Actual</th>",1)
        self.rejected(raw=raw)

    def test_08_extra_trailing_header_shifts_column_geometry_and_blocks(self):
        raw=fx.te_html(CPI)
        raw=raw.replace(b"<th>Forecast</th></tr>",
                        b"<th>Forecast</th><th>Survey</th></tr>",1)
        self.rejected(raw=raw)

    def test_09_two_identical_header_rows_do_not_choose_favorable_one(self):
        raw=fx.te_html(CPI)
        h=(b"<tr><th>Actual</th><th>Previous</th>"
           b"<th>Consensus</th><th>Forecast</th></tr>")
        self.assertIn(h,raw)
        self.rejected(raw=raw.replace(h,h+h,1))

    def test_10_single_header_sequence_in_unrelated_table_does_not_replace_missing(self):
        raw=fx.te_html(CPI)
        h=(b"<tr><th>Actual</th><th>Previous</th>"
           b"<th>Consensus</th><th>Forecast</th></tr>")
        header_other=b"<table><thead>"+h+b"</thead></table>"
        raw=raw.replace(h,b"<tr><th>NotConsensus</th></tr>",1)
        raw=raw.replace(b"<html><body>",b"<html><body>"+header_other,1)
        self.rejected(raw=raw)

    def test_11_unrelated_table_noise_does_not_break_valid_scoped_header(self):
        raw=fx.te_html(CPI)
        unrelated=b"<table><thead><tr><th>Other</th></tr></thead></table>"
        raw=raw.replace(b"<html><body>",b"<html><body>"+unrelated,1)
        self.permitted_provisional(CPI,raw)

    def test_12_unrelated_complete_header_elsewhere_cannot_replace_same_table_binding(self):
        raw=fx.te_html(CPI)
        h=(b"<tr><th>Actual</th><th>Previous</th>"
           b"<th>Consensus</th><th>Forecast</th></tr>")
        unrelated=b"<table><thead>"+h+b"</thead></table>"
        raw=raw.replace(b"<html><body>",b"<html><body>"+unrelated,1)
        self.permitted_provisional(CPI,raw)

    def test_13_nested_country_table_inside_data_row_still_parses(self):
        raw=fx.te_html(CPI)
        self.assertIn(b"<td><table><tr><td>US</td></tr></table></td>",raw)
        self.permitted_provisional(CPI,raw)

    def test_14_unbalanced_tr_does_not_become_valid_consensus(self):
        raw=fx.te_html(CPI).replace(b"</thead>",b"</tr></thead>",1)
        self.rejected(raw=raw)

    def test_15_unclosed_table_header_row_does_not_pass(self):
        raw=fx.te_html(CPI)
        raw=raw.replace(b"<th>Forecast</th></tr></thead>",
                        b"<th>Forecast</th></thead>",1)
        self.rejected(raw=raw)

    def test_16_invalid_cpi_header_blocks_otherwise_provisional_ppi_too(self):
        raw=fx.te_html(CPI)
        raw=raw.replace(b"</th><th>Consensus</th>",
                        b"</th></tr><tr><th>Consensus</th>",1)
        self.rejected(raw=raw,include_other=True)

    def test_17_after_header_row_mutation_no_substitute_previous_or_forecast(self):
        raw=fx.te_html(PPI,head="0.4%",prev="0.2%",own="0.9%")
        raw=raw.replace(b"</th><th>Forecast</th>",
                        b"</th></tr><tr><th>Forecast</th>",1)
        result=self.rejected(PPI,raw)
        self.assertIsNone(result["events"][1]["td_previous_headline_mom_pct"])
        self.assertIsNone(result["events"][1]["te_provider_forecast_headline_mom_pct"])

    def test_18_four_events_remain_two_independent_economic_roots(self):
        result=inspect(source_snapshots=fx.pair(CPI)+fx.pair(PPI),
                       inspected_at_utc=fx.POST)
        self.assertEqual(result["state"],PROVISIONAL)
        self.assertEqual(result["local_two_source_candidate_event_count"],2)
        self.assertEqual(result["independent_fx_oos_trials"],0)
        self.assertIsNone(result["win_rate"])


if __name__=="__main__":
    unittest.main()
