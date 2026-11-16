"""Data cannot be relabelled using a consensus header appended AFTER it.

Reproduces real parser ordering vulnerabilities using entirely SYNTHETIC
CPI/PPI TD/TE HTML. This is not real December consensus or a forex forecast.
"""
from __future__ import annotations

from hashlib import sha256
from dataclasses import replace
import unittest

import test_atlasquant_trader_us_dec2026_consensus_semantic_candidate_lab as fixture
from atlasquant_trader_us_dec2026_consensus_semantic_candidate_lab import (
    inspect_dec2026_consensus_semantic_candidate_lab as inspect,
)

CPI, PPI = fixture.CPI, fixture.PPI
GOOD="LAB_DEC2026_TWO_SOURCE_PROVISIONAL_SEMANTICS_ONLY_HARD_NO_GO"
BAD="LAB_DEC2026_CONSENSUS_SEMANTICS_BLOCKED_HARD_NO_GO"


def _row(raw: bytes, text: bytes) -> tuple[int,int,bytes]:
    p=raw.index(text)
    start=raw.rfind(b"<tr>",0,p)
    assert start>=0
    end=raw.index(b"</tr>",p)+len(b"</tr>")
    return start,end,raw[start:end]


def _reorder(raw: bytes, *, segment: tuple[int,int,bytes],
             before: bytes | None = None, after: bytes | None = None) -> bytes:
    start,end,part=segment
    stripped=raw[:start]+raw[end:]
    if before is not None:
        at=stripped.index(before)
    else:
        assert after is not None
        at=stripped.index(after)+len(after)
    return stripped[:at]+part+stripped[at:]


def _td_header(raw: bytes) -> tuple[int,int,bytes]:
    return _row(raw,b"Release Date")


def _td_title(raw: bytes, root: str) -> tuple[int,int,bytes]:
    return _row(raw,fixture.ROOT[root]["title"].encode("ascii"))


def _td_metric(raw: bytes, root: str, core: bool) -> tuple[int,int,bytes]:
    name=fixture.ROOT[root]["td_core" if core else "td_head"]
    return _row(raw,name.encode("ascii"))


def _te_header(raw: bytes) -> tuple[int,int,bytes]:
    start=raw.index(b"<thead>")
    end=raw.index(b"</thead>",start)+len(b"</thead>")
    return start,end,raw[start:end]


def _te_shift_header(raw: bytes, *, before: bytes | None = None) -> bytes:
    head=_te_header(raw)
    return _reorder(raw,segment=head,
                    before=before if before is not None else b"</table>")


def _claim(root: str, provider: str, raw: bytes):
    one=fixture.original(root,provider)
    return replace(one,html_original_bytes=raw,
                   original_sha256_claim=sha256(raw).hexdigest())


def _review(root=CPI,*,td:bytes|None=None,te:bytes|None=None,other=False):
    docs=(
        _claim(root,"TD_ECONOMICS",td) if td is not None
        else fixture.original(root,"TD_ECONOMICS"),
        _claim(root,"TRADING_ECONOMICS",te) if te is not None
        else fixture.original(root,"TRADING_ECONOMICS"),
    )
    if other:
        docs+=fixture.pair(PPI if root==CPI else CPI)
    return inspect(source_snapshots=docs,inspected_at_utc=fixture.POST)


class ConsensusHeaderDocumentOrderTests(unittest.TestCase):
    def assert_safe(self,r):
        self.assertEqual(r["frozen_economic_event_denominator"],2)
        self.assertEqual(r["registered_directional_fx_predictions"],0)
        self.assertEqual(r["independent_fx_oos_trials"],0)
        self.assertIsNone(r["win_rate"])
        self.assertIsNone(r["fx_bias"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["fx28_original_672_slots_modified"])
        for e in r["events"]:
            self.assertFalse(e["source_semantic_schema_approved_on_real_december_html"])
            self.assertFalse(e["consensus_eligible_for_fx_prediction"])

    def reject(self,root=CPI,*,td=None,te=None,other=False):
        r=_review(root,td=td,te=te,other=other)
        self.assert_safe(r)
        self.assertEqual(r["state"],BAD)
        self.assertEqual(r["local_two_source_candidate_event_count"],0)
        self.assertTrue(all(
            e["provisional_consensus_headline_mom_sa_pct"] is None
            and e["provisional_consensus_core_mom_sa_pct"] is None
            and e["td_html_sha256_local_claim"] is None
            and e["te_html_sha256_local_claim"] is None
            for e in r["events"]))
        return r

    def accept_provisionally(self,root=CPI,*,td=None,te=None):
        r=_review(root,td=td,te=te)
        self.assert_safe(r)
        self.assertEqual(r["state"],GOOD)
        self.assertEqual(r["local_two_source_candidate_event_count"],1)
        self.assertFalse(r["events"][0 if root==CPI else 1]
                         ["consensus_eligible_for_fx_prediction"])
        return r

    def test_01_original_cpi_header_precedes_data_td_and_te(self):
        self.accept_provisionally()

    def test_02_original_ppi_header_precedes_data_td_and_te(self):
        self.accept_provisionally(PPI)

    def test_03_td_cpi_header_appended_after_both_metric_rows_rejected(self):
        raw=fixture.td_html(CPI)
        mutation=_reorder(raw,segment=_td_header(raw),before=b"</table>")
        self.reject(td=mutation)

    def test_04_td_ppi_header_appended_after_both_metric_rows_rejected(self):
        raw=fixture.td_html(PPI)
        mutation=_reorder(raw,segment=_td_header(raw),before=b"</table>")
        self.reject(PPI,td=mutation)

    def test_05_td_header_placed_between_headline_and_core_rejected(self):
        raw=fixture.td_html(CPI)
        core=_td_metric(raw,CPI,True)
        mutation=_reorder(raw,segment=_td_header(raw),before=core[2])
        self.reject(td=mutation)

    def test_06_td_title_after_consensus_header_rejected(self):
        raw=fixture.td_html(CPI)
        title=_td_title(raw,CPI)
        mutation=_reorder(raw,segment=title,after=_td_header(raw)[2])
        self.reject(td=mutation)

    def test_07_td_title_after_metric_rows_rejected(self):
        raw=fixture.td_html(CPI)
        title=_td_title(raw,CPI)
        mutation=_reorder(raw,segment=title,before=b"</table>")
        self.reject(td=mutation)

    def test_08_td_ppi_title_after_header_rejected(self):
        raw=fixture.td_html(PPI)
        title=_td_title(raw,PPI)
        mutation=_reorder(raw,segment=title,after=_td_header(raw)[2])
        self.reject(PPI,td=mutation)

    def test_09_td_core_row_precedes_consensus_header_rejected(self):
        raw=fixture.td_html(PPI)
        core=_td_metric(raw,PPI,True)
        mutation=_reorder(raw,segment=core,before=_td_header(raw)[2])
        self.reject(PPI,td=mutation)

    def test_10_td_headline_row_precedes_consensus_header_rejected(self):
        raw=fixture.td_html(CPI)
        headline=_td_metric(raw,CPI,False)
        mutation=_reorder(raw,segment=headline,before=_td_header(raw)[2])
        self.reject(td=mutation)

    def test_11_td_multiple_indistinguishable_week_titles_rejected(self):
        raw=fixture.td_html(CPI)
        title=_td_title(raw,CPI)
        mutation=raw.replace(title[2],title[2]+title[2],1)
        self.reject(td=mutation)

    def test_12_te_cpi_header_at_end_of_table_rejected(self):
        raw=fixture.te_html(CPI)
        mutation=_te_shift_header(raw)
        self.reject(te=mutation)

    def test_13_te_ppi_header_at_end_of_table_rejected(self):
        raw=fixture.te_html(PPI)
        mutation=_te_shift_header(raw)
        self.reject(PPI,te=mutation)

    def test_14_te_header_after_headline_but_before_core_rejected(self):
        raw=fixture.te_html(CPI)
        core=(b'<tr data-url="'+fixture.ROOT[CPI]["url_core"].encode()+b'"')
        mutation=_te_shift_header(raw,before=core)
        self.reject(te=mutation)

    def test_15_te_header_after_ppi_headline_before_core_rejected(self):
        raw=fixture.te_html(PPI)
        core=(b'<tr data-url="'+fixture.ROOT[PPI]["url_core"].encode()+b'"')
        mutation=_te_shift_header(raw,before=core)
        self.reject(PPI,te=mutation)

    def test_16_both_source_origins_invalid_blocks_other_good_event(self):
        raw=fixture.td_html(PPI)
        mutation=_reorder(raw,segment=_td_header(raw),before=b"</table>")
        self.reject(PPI,td=mutation,other=True)

    def test_17_two_good_events_remain_two_macro_not_four_fx_predictions(self):
        docs=fixture.pair(CPI)+fixture.pair(PPI)
        r=inspect(source_snapshots=docs,inspected_at_utc=fixture.POST)
        self.assert_safe(r)
        self.assertEqual(r["state"],GOOD)
        self.assertEqual(r["local_two_source_candidate_event_count"],2)
        self.assertEqual(r["independent_fx_oos_trials"],0)

    def test_18_td_ordered_preamble_noise_row_ignored(self):
        raw=fixture.td_html(CPI)
        insert=b"<tr><td>INTRODUCTORY RESEARCH DISCLAIMER</td></tr>"
        mutation=raw.replace(b"<table>",b"<table>"+insert,1)
        self.accept_provisionally(td=mutation)

    def test_19_te_header_first_with_irrelevant_preamble_row_still_provisional(self):
        raw=fixture.te_html(CPI)
        insert=(b"<tr><td>OTHER NON EVENT</td><td>NO FORECAST</td></tr>")
        mutation=raw.replace(b"<table>",b"<table>"+insert,1)
        self.accept_provisionally(te=mutation)

    def test_20_consensus_is_still_not_a_directional_usd_precommit(self):
        r=self.accept_provisionally()
        self.assertEqual(r["economic_consensus_pre_event_independently_authenticated"],0)
        self.assertEqual(r["registered_directional_fx_predictions"],0)


if __name__=="__main__":
    unittest.main()
