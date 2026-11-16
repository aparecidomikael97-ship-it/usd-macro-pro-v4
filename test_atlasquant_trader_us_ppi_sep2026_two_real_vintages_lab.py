"""Offline revision/vintage guards, synthetic HTML only; no market evidence."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_us_ppi_sep2026_two_real_vintages_lab import (
    SEP_CAPTURE, OCT_CAPTURE, SEP_HASH, OCT_HASH,
    _ppi_table1_sep_2026_values, inspect_real_ppi_sep2026_release_vintages_lab,
)
from atlasquant_trader_us_ppi_sep2026_two_real_vintages_lab import LOWER

UTC = timezone.utc


def synthetic_table(*, edition="sep", headline="1.3", core="0.7",
                    month_swap=False, duplicate=False, wrong_code=False,
                    remove_core=False):
    h = LOWER[edition]
    if month_swap:
        h = tuple(reversed(h))
    top = ("Grouping", "Commodity code", "Relative Importance Dec. 2025 (1)",
           "Unadjusted 12-month percent change (2)",
           "Seasonally adjusted 1-month percent change (2)")
    lower = ("Group code", "Item code", "Sept. 2025 to Sept. 2026 (p)"
             if edition == "sep" else "Oct. 2025 to Oct. 2026 (p)", *h)
    def ths(xs):
        return "<tr>"+"".join(f"<th>{s}</th>" for s in xs)+"</tr>"
    def row(label, code, actual):
        monthly = ["0.1", "0.2", "0.3", "0.4", "0.5"]
        if edition == "sep":
            monthly[-1] = actual
        else:
            monthly[-2] = actual
        cols = ["FD", code, "100.000", "6.5", *monthly]
        return ("<tr><th>"+label+"</th>"
                + "".join(f"<td>{s}</td>" for s in cols) + "</tr>")
    rows = row("Final demand", "4", headline)
    if duplicate:
        rows += row("Final demand", "4", headline)
    if not remove_core:
        rows += row("Final demand less foods and energy (5)",
                    "99999" if wrong_code else "49104", core)
    rows += row("Final demand less foods, energy, and trade services (5)",
                "49116", "0.5")
    return (
        f"<html><body><p>Table 1. Producer price index percentage changes "
        f"and weights for Final Demand-Intermediate Demand groupings, "
        f"seasonally adjusted ["
        f"{'September 2026' if edition == 'sep' else 'October 2026'}]"
        f"</p><table><thead>{ths(top)}{ths(lower)}</thead>"
        f"<tbody>{rows}</tbody></table></body></html>"
    ).encode()


class RealPpiVintageRulesTests(unittest.TestCase):
    def assert_no_market(self, out):
        self.assertEqual(out["documentary_source_denominator"], 2)
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["publishable"])
        self.assertFalse(out["economic_consensus_pre_event_authenticated"])
        self.assertFalse(out["original_first_print_time_independently_authenticated"])
        self.assertEqual(out["independent_directional_fx_predictions"], 0)
        self.assertEqual(out["out_of_sample_forex_trials"], 0)
        self.assertIsNone(out["accuracy"])
        self.assertIsNone(out["bias_usd"])
        self.assertFalse(out["fx28_672_slots_changed"])
        self.assertEqual(out["operational_bias"], "AGUARDAR")

    def inspect(self, when, sep=b"fake sep", oct=b"fake oct"):
        return inspect_real_ppi_sep2026_release_vintages_lab(
            sep_original_html=sep, oct_original_html=oct,
            research_cutoff_utc=when,
        )

    def test_01_extract_named_september_mom_column_from_original_edition(self):
        result = _ppi_table1_sep_2026_values(
            synthetic_table(), edition="sep")
        self.assertEqual(str(result["headline"]), "1.3")
        self.assertEqual(str(result["core_ex_food_energy"]), "0.7")

    def test_02_extract_september_revision_not_october_current_column(self):
        result = _ppi_table1_sep_2026_values(
            synthetic_table(edition="oct", headline="1.4",core="0.8"),
            edition="oct")
        self.assertEqual(str(result["headline"]), "1.4")
        self.assertEqual(str(result["core_ex_food_energy"]), "0.8")

    def test_03_swapped_monthly_header_fails(self):
        for edition in ("sep","oct"):
            self.assertIsNone(_ppi_table1_sep_2026_values(
                synthetic_table(edition=edition,month_swap=True),
                edition=edition))

    def test_04_duplicated_headline_fd4_fails(self):
        self.assertIsNone(_ppi_table1_sep_2026_values(
            synthetic_table(duplicate=True),edition="sep"))

    def test_05_wrong_core_commodity_code_fails(self):
        self.assertIsNone(_ppi_table1_sep_2026_values(
            synthetic_table(wrong_code=True),edition="sep"))

    def test_06_missing_core_fails(self):
        self.assertIsNone(_ppi_table1_sep_2026_values(
            synthetic_table(remove_core=True),edition="sep"))

    def test_07_missing_table1_heading_fails(self):
        raw = synthetic_table().replace(b"Table 1.",b"Table 2.")
        self.assertIsNone(_ppi_table1_sep_2026_values(raw,edition="sep"))

    def test_08_bad_charset_or_type_fails(self):
        self.assertIsNone(_ppi_table1_sep_2026_values(b"\xff"*40,edition="sep"))
        self.assertIsNone(_ppi_table1_sep_2026_values("text",edition="sep"))
        self.assertIsNone(_ppi_table1_sep_2026_values(b"x",edition="wrong"))

    def test_09_before_both_local_captures_no_revision_visible(self):
        out = self.inspect(OCT_CAPTURE-timedelta(microseconds=1))
        self.assert_no_market(out)
        self.assertEqual(out["originals_visible_at_local_cutoff"],0)
        self.assertIsNone(out["later_revision_minus_first_release_headline_pp"])

    def test_10_at_oct_capture_only_one_original_is_visible(self):
        out = self.inspect(OCT_CAPTURE)
        self.assert_no_market(out)
        self.assertEqual(out["originals_visible_at_local_cutoff"],1)
        self.assertFalse(out["original_sep_release_visible"])
        self.assertTrue(out["oct_release_with_sep_revision_visible"])
        self.assertIsNone(out["oct_reported_revised_sep2026_sa_mom_headline_pct"])

    def test_11_just_before_sep_archive_no_lookahead(self):
        out = self.inspect(SEP_CAPTURE-timedelta(microseconds=1))
        self.assert_no_market(out)
        self.assertEqual(out["originals_visible_at_local_cutoff"],1)
        self.assertIsNone(out["sep_reported_sep2026_sa_mom_headline_pct"])

    def test_12_at_last_capture_synthetic_bytes_still_rejected(self):
        out = self.inspect(SEP_CAPTURE)
        self.assert_no_market(out)
        self.assertIn("SHA256",out["reason"])
        self.assertIsNone(out["later_revision_minus_first_release_headline_pp"])

    def test_13_swapped_real_source_bytes_fail_sha(self):
        out = self.inspect(SEP_CAPTURE+timedelta(days=1),
                           sep=b"fake oct",oct=b"fake sep")
        self.assert_no_market(out)
        self.assertEqual(out["originals_visible_at_local_cutoff"],2)
        self.assertIsNone(out["original_sep_release_html_sha256"])

    def test_14_naive_or_malformed_cutoff_rejected(self):
        for cutoff in (None, "2026-11-16", datetime(2026,11,16)):
            out = self.inspect(cutoff)
            self.assert_no_market(out)
            self.assertEqual(out["originals_visible_at_local_cutoff"],0)

    def test_15_independent_literal_SHA_pins_not_all_zeros(self):
        self.assertEqual(len(SEP_HASH),64)
        self.assertEqual(len(OCT_HASH),64)
        self.assertNotEqual(SEP_HASH,OCT_HASH)
        self.assertNotEqual(SEP_HASH,"0"*64)
        self.assertNotEqual(OCT_HASH,"0"*64)

    def test_16_no_fake_predictive_accuracy_when_sources_missing(self):
        for cutoff in (OCT_CAPTURE,SEP_CAPTURE):
            out = self.inspect(cutoff)
            self.assert_no_market(out)
            self.assertIsNone(out["oct2026_actual_headline_sa_mom_pct"])


if __name__ == "__main__":
    unittest.main()
