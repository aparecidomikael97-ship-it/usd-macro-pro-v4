"""Audit: prevent header laundering across unrelated HTML tables (synthetic)."""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import unittest

import test_atlasquant_trader_us_dec2026_consensus_semantic_candidate_lab as fixture
from atlasquant_trader_us_dec2026_consensus_semantic_candidate_lab import (
    inspect_dec2026_consensus_semantic_candidate_lab as inspect,
)

CPI=fixture.CPI
PPI=fixture.PPI
AFTER=fixture.POST


def split_at(raw: bytes, marker: bytes) -> bytes:
    at=raw.find(marker)
    assert at>=0, "synthetic test fixture not found"
    return raw[:at]+b"</table><table>"+raw[at:]


def move_header_to_other_table_td(raw: bytes) -> bytes:
    head=b"<tr><td>Release Date</td>"
    start=raw.index(head)
    end=raw.index(b"</tr>",start)+len(b"</tr>")
    # Title = table A, header = table B, metric rows = table C.
    return raw[:start]+b"</table><table>"+raw[start:end]+b"</table><table>"+raw[end:]


def assert_blocking(test: unittest.TestCase, *,
                    root: str = CPI, td: bytes | None = None,
                    te: bytes | None = None, include_other: bool = False) -> None:
    originals=fixture.pair(root,td=td,te=te)
    if include_other:
        originals+=fixture.pair(PPI if root==CPI else CPI)
    result=inspect(source_snapshots=originals,inspected_at_utc=AFTER)
    test.assertEqual(result["state"],
                     "LAB_DEC2026_CONSENSUS_SEMANTICS_BLOCKED_HARD_NO_GO")
    test.assertEqual(result["local_two_source_candidate_event_count"],0)
    test.assertEqual(result["frozen_economic_event_denominator"],2)
    test.assertTrue(all(
        x["provisional_consensus_headline_mom_sa_pct"] is None
        for x in result["events"]))
    test.assertEqual(result["registered_directional_fx_predictions"],0)
    test.assertEqual(result["independent_fx_oos_trials"],0)
    test.assertFalse(result["trade_authorized"])
    test.assertFalse(result["publishable"])


class PhysicalTableBoundaryIntegrityTests(unittest.TestCase):
    def test_01_original_synthetic_td_te_cpi_still_accepted_as_provisional(self):
        result=inspect(source_snapshots=fixture.pair(CPI),inspected_at_utc=AFTER)
        self.assertEqual(result["local_two_source_candidate_event_count"],1)
        self.assertEqual(result["events"][0]["provisional_consensus_headline_mom_sa_pct"],"0.4")
        self.assertFalse(result["events"][0]["consensus_eligible_for_fx_prediction"])

    def test_02_original_synthetic_td_te_ppi_still_accepted_as_provisional(self):
        result=inspect(source_snapshots=fixture.pair(PPI),inspected_at_utc=AFTER)
        self.assertEqual(result["local_two_source_candidate_event_count"],1)
        self.assertEqual(result["events"][1]["provisional_consensus_core_mom_sa_pct"],"0.3")

    def test_03_td_header_laundered_from_separate_table_is_rejected(self):
        raw=move_header_to_other_table_td(fixture.td_html(CPI))
        assert_blocking(self,td=raw)

    def test_04_td_title_is_unrelated_to_header_metric_table(self):
        raw=fixture.td_html(CPI)
        # Week title in table A, true header/values in table B.
        pos=raw.index(b"</tr>")+len(b"</tr>")
        raw=raw[:pos]+b"</table><table>"+raw[pos:]
        assert_blocking(self,td=raw)

    def test_05_td_core_from_other_table_cannot_be_consensus_core(self):
        raw=fixture.td_html(CPI)
        core=raw.index(b"CPI Ex Food and Energy")
        prev=raw.rfind(b"<tr>",0,core)
        assert_blocking(self,td=raw[:prev]+b"</table><table>"+raw[prev:])

    def test_06_td_headline_from_other_table_cannot_be_consensus(self):
        raw=fixture.td_html(PPI)
        head=raw.index(b"PPI Final Demand")
        prev=raw.rfind(b"<tr>",0,head)
        assert_blocking(self,root=PPI,td=raw[:prev]+b"</table><table>"+raw[prev:])

    def test_07_td_header_outside_any_table_is_invalid(self):
        raw=fixture.td_html(CPI)
        start=raw.index(b"<tr><td>Release Date")
        end=raw.index(b"</tr>",start)+len(b"</tr>")
        raw=raw[:start]+b"</table>"+raw[start:end]+b"<table>"+raw[end:]
        assert_blocking(self,td=raw)

    def test_08_td_unclosed_table_scope_is_invalid(self):
        raw=fixture.td_html(CPI).replace(b"</table>",b"",1)
        assert_blocking(self,td=raw)

    def test_09_te_header_unrelated_table_and_bare_event_rows_rejected(self):
        raw=fixture.te_html(CPI)
        raw=raw.replace(b"</thead>",b"</thead></table><table>",1)
        assert_blocking(self,te=raw)

    def test_10_te_core_row_separate_table_even_if_numbers_match_rejected(self):
        raw=fixture.te_html(CPI)
        raw=split_at(raw,b'<tr data-url="/united-states/core-inflation-rate-mom"')
        assert_blocking(self,te=raw)

    def test_11_te_ppi_core_row_separate_table_is_rejected(self):
        raw=fixture.te_html(PPI)
        raw=split_at(raw,b'<tr data-url="/united-states/core-producer-prices-mom"')
        assert_blocking(self,root=PPI,te=raw)

    def test_12_te_heading_from_unrelated_table_does_not_count(self):
        raw=fixture.te_html(CPI)
        # Put an extra title/heading in an unrelated table without touching
        # the correctly scoped CPI table. It must still parse its OWN header.
        irrelevant=(b"<table><thead><tr><th>Fake</th><th>Other</th>"
                    b"</tr></thead><tr><td>Noise</td></tr></table>")
        raw=raw.replace(b"<table>",irrelevant+b"<table>",1)
        result=inspect(source_snapshots=fixture.pair(CPI,te=raw),
                       inspected_at_utc=AFTER)
        self.assertEqual(result["local_two_source_candidate_event_count"],1)
        self.assertEqual(result["events"][0]["provisional_consensus_headline_mom_sa_pct"],"0.4")

    def test_13_te_extra_matching_header_in_other_table_is_not_our_header(self):
        raw=fixture.te_html(CPI)
        same_header=(b"<table><thead><tr><th>Actual</th><th>Previous</th>"
                     b"<th>Consensus</th><th>Forecast</th></tr></thead></table>")
        raw=raw.replace(b"<table>",same_header+b"<table>",1)
        result=inspect(source_snapshots=fixture.pair(CPI,te=raw),
                       inspected_at_utc=AFTER)
        self.assertEqual(result["local_two_source_candidate_event_count"],1)
        self.assertFalse(result["events"][0]["consensus_eligible_for_fx_prediction"])

    def test_14_te_no_table_container_is_not_sufficient(self):
        raw=fixture.te_html(CPI).replace(b"<table>",b"").replace(b"</table>",b"")
        assert_blocking(self,te=raw)

    def test_15_te_unbalanced_table_scope_rejected(self):
        raw=fixture.te_html(CPI).replace(b"</table>",b"",1)
        assert_blocking(self,te=raw)

    def test_16_provisional_cpi_does_not_survive_bad_ppi_table_provenance(self):
        raw=move_header_to_other_table_td(fixture.td_html(PPI))
        assert_blocking(self,root=PPI,td=raw,include_other=True)

    def test_17_both_event_roots_with_correct_tables_produce_only_two_candidates(self):
        result=inspect(source_snapshots=fixture.pair(CPI)+fixture.pair(PPI),
                       inspected_at_utc=AFTER)
        self.assertEqual(result["local_two_source_candidate_event_count"],2)
        self.assertEqual(result["registered_directional_fx_predictions"],0)
        self.assertIsNone(result["win_rate"])

    def test_18_td_table_cannot_supply_te_header_even_if_numerics_match(self):
        raw=fixture.te_html(CPI)
        # Move the four required header cells outside TE's metric table.
        raw=raw.replace(b"</thead>",b"</thead></table><table>",1)
        assert_blocking(self,te=raw)
        
if __name__=="__main__":
    unittest.main()
