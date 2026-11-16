"""Offline pure synthetic regressions for TD PPI/CAD co-release guard.
The actual proprietary TD HTML is NOT bundled in tests or GitHub.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
import unittest

from atlasquant_trader_us_ppi_pre_event_preview_lab import EXPECTED_HEADER

from atlasquant_trader_ppi_td_same_minute_fx28_guard_lab import (
    _extract_from_parsed_rows, inspect_ppi_td_same_minute_fx28_lab, PASS, BLOCKED,
)

def fixture() -> list[tuple[str, ...]]:
    other = ("Nov 12", "10:00", "", "Routine Announcement", "Nov", "", "-", "-")
    return [
        ("Upcoming Economic Releases and Events",),
        tuple(EXPECTED_HEADER),
        ("United States",),
        *([other] * 5),
        ("Nov 13", "8:30", "", "PPI Final Demand", "Oct", "M/M % Chg.", "0.4", "1.3"),
        ("Nov 13", "8:30", "", "PPI Ex Food and Energy", "Oct", "M/M % Chg.", "0.3", "0.7"),
        ("Canada",),
        ("Nov 13", "8:30", "", "Manufacturing Sales", "Sep", "M/M % Chg.", "0.1", "1.5"),
        ("International",),
        other, other,
        ("*Eastern Standard Time. Source: Bloomberg, TD Economics",),
    ]

class TestCoReleaseGuard(unittest.TestCase):
    def test_two_macro_roots_not_three_metric_trials(self):
        self.assertEqual(
            _extract_from_parsed_rows(fixture()),
            ("US_PPI_OCT2026", "CAD_MANUFACTURING_SALES_SEP2026"))
    def test_unpinned_synthetic_html_fail_closed(self):
        r = inspect_ppi_td_same_minute_fx28_lab(td_original_html=b"<html>fabricated</html>")
        self.assertEqual(r["state"], BLOCKED)
        self.assertFalse(r["trade_authorized"])
    def test_missing_doc_fail_closed(self):
        self.assertEqual(inspect_ppi_td_same_minute_fx28_lab(td_original_html=None)["state"], BLOCKED)
    def test_missing_canada_section_rejects(self):
        rows=[r for r in fixture() if r!=("Canada",)]
        self.assertIsNone(_extract_from_parsed_rows(rows))
    def test_canadian_event_not_same_minute_rejects(self):
        rows=fixture()
        rows[11]=("Nov 13","8:45","","Manufacturing Sales","Sep","M/M % Chg.","0.1","1.5")
        self.assertIsNone(_extract_from_parsed_rows(rows))
    def test_canadian_event_changed_to_ppi_section_rejects(self):
        rows=fixture()
        rows[10]=("International",)
        self.assertIsNone(_extract_from_parsed_rows(rows))
    def test_mismatched_canadian_consensus_rejects(self):
        rows=fixture()
        rows[11]=("Nov 13","8:30","","Manufacturing Sales","Sep","M/M % Chg.","0.2","1.5")
        self.assertIsNone(_extract_from_parsed_rows(rows))
    def test_missing_est_timezone_footer_rejects(self):
        rows=fixture()
        rows[-1]=("*Eastern Daylight Time. Source TD",)
        self.assertIsNone(_extract_from_parsed_rows(rows))
    def test_ambiguous_extra_same_minute_event_rejects(self):
        rows=fixture()
        rows.insert(12,("Nov 13","8:30","","Second CAD Release","Sep","","0.1","1.0"))
        self.assertIsNone(_extract_from_parsed_rows(rows))
    def test_duplicate_ppi_root_rejects(self):
        rows=fixture()
        rows.insert(9,rows[8])
        self.assertIsNone(_extract_from_parsed_rows(rows))
    def test_malformed_field_types_reject(self):
        rows=fixture()
        rows[8]=("Nov 13", "8:30", "", "PPI Final Demand", "Oct", "M/M % Chg.", 0.4, "1.3")
        self.assertIsNone(_extract_from_parsed_rows(rows))
    def test_bad_header_rejects(self):
        rows=fixture()
        rows[1]=("Release Date", "Time")
        self.assertIsNone(_extract_from_parsed_rows(rows))
    @unittest.skipUnless(os.environ.get("ATLASQUANT_TD_ORIGINAL_FOR_TEST"), "Pinned original TD HTML only on authorized AM12")
    def test_real_td_orig_bytes_and_28pair_exposure(self):
        path=Path(os.environ["ATLASQUANT_TD_ORIGINAL_FOR_TEST"])
        result=inspect_ppi_td_same_minute_fx28_lab(td_original_html=path.read_bytes())
        self.assertEqual(result["state"],PASS)
        self.assertTrue(result["td_original_sha256_verified"])
        self.assertTrue(result["usd_cad_directly_exposed_to_two_roots"])
        self.assertEqual(len(result["cad_pairs_exposed_to_cad_release"]),7)
        self.assertEqual(len(result["usd_pairs_exposed_to_ppi"]),7)
        self.assertFalse(result["ppi_exclusive_causality_for_usdcad"])
        self.assertFalse(result["all_28_pairs_causally_clean"])
        self.assertFalse(result["trade_authorized"])
        self.assertEqual(result["independent_macro_event_count_verified"],0)

if __name__=="__main__":
    unittest.main(verbosity=2)
