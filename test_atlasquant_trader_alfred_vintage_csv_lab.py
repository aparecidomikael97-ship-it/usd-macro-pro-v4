"""Offline, strict two-vintage ALFRED CSV contract checks; not a historic download."""
import copy
import json
from pathlib import Path
import unittest

from atlasquant_trader_alfred_vintage_csv_lab import (
    EXPECTED_HEADER, inspect_alfred_cpi_vintages_csv_lab,
)

MANIFEST = (Path(__file__).resolve().parent / "docs" / "continuidade" /
            "TRADER_CPI_BLS_ALFRED_CASO_REAL_LAB_20261102.json")
HEADER = ",".join(EXPECTED_HEADER)
ROW = "2025-12-01,324.054,324.054"
CSV = HEADER + "\n2025-11-01,325.100,325.100\n" + ROW + "\n2026-01-01,,325.252\n"


def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def evaluate(content=CSV, case=None):
    return inspect_alfred_cpi_vintages_csv_lab(
        content, manifest() if case is None else case,
    )


class AlfredVintageCsvLabTests(unittest.TestCase):
    def test_two_declared_vintages_corroborate_bls_only_as_candidate(self):
        result = evaluate()
        self.assertEqual(result["state"], "LAB_ALFRED_TWO_VINTAGE_CANDIDATE_MATCH")
        self.assertEqual(result["observation_date"], "2025-12-01")
        self.assertEqual(result["jan13_dec2025_value"], "324.054")
        self.assertEqual(result["feb13_dec2025_value"], "324.054")
        self.assertTrue(result["candidate_values_match_bls"])

    def test_no_authenticated_source_or_real_backtest_even_when_values_agree(self):
        result = evaluate()
        for flag in ("source_content_authenticated",
                     "real_historical_custody_verified",
                     "exact_intraday_availability_verified",
                     "event_consensus_verified", "real_oos_authorized",
                     "trade_authorized", "worker_enabled", "scheduler_enabled"):
            self.assertFalse(result[flag], flag)

    def test_revised_value_mismatch_is_quarantined_not_silently_corrected(self):
        result = evaluate(CSV.replace(ROW, "2025-12-01,324.054,324.111"))
        self.assertEqual(result["state"], "LAB_ALFRED_BLS_DISAGREEMENT_REVIEW")
        self.assertFalse(result["candidate_values_match_bls"])
        self.assertEqual(result["feb13_dec2025_value"], "324.111")
        self.assertFalse(result["real_oos_authorized"])

    def test_initial_value_disagreement_preserved_without_fake_match(self):
        result = evaluate(CSV.replace(ROW, "2025-12-01,324.055,324.054"))
        self.assertEqual(result["state"], "LAB_ALFRED_BLS_DISAGREEMENT_REVIEW")
        self.assertFalse(result["candidate_values_match_bls"])

    def test_must_not_use_current_vintage_as_historical_vintage(self):
        bad = CSV.replace("CPIAUCNS_20260213", "CPIAUCNS_20261102")
        result = evaluate(bad)
        self.assertEqual(result["state"], "LAB_ALFRED_CSV_QUARANTINED")
        self.assertIn("EXACT", result["reason"])

    def test_swapped_vintage_headers_cannot_swap_observations(self):
        bad = CSV.replace(
            HEADER, "observation_date,CPIAUCNS_20260213,CPIAUCNS_20260113"
        )
        self.assertEqual(evaluate(bad)["state"], "LAB_ALFRED_CSV_QUARANTINED")

    def test_incorrect_or_seasonally_adjusted_series_refused(self):
        for new_series in ("CPIAUCSL", "CPI_U", "UNRATE"):
            bad = CSV.replace("CPIAUCNS_", new_series + "_")
            self.assertEqual(evaluate(bad)["state"], "LAB_ALFRED_CSV_QUARANTINED")

    def test_late_dataset_without_target_row_is_not_a_match(self):
        csvtext = HEADER + "\n2026-01-01,,325.252\n"
        result = evaluate(csvtext)
        self.assertEqual(result["state"], "LAB_ALFRED_CSV_QUARANTINED")
        self.assertIn("not in export", result["reason"])

    def test_missing_december_value_in_either_vintage_refused(self):
        for row in ("2025-12-01,,324.054",
                    "2025-12-01,324.054,",
                    "2025-12-01,.,324.054"):
            self.assertEqual(
                evaluate(CSV.replace(ROW, row))["state"],
                "LAB_ALFRED_CSV_QUARANTINED", row,
            )

    def test_nan_infinity_boolean_string_and_negative_values_refused(self):
        for number in ("nan", "inf", "-3.0", "0", "true", "1e9999"):
            result = evaluate(CSV.replace(ROW,
                                 "2025-12-01,324.054," + number))
            self.assertEqual(result["state"], "LAB_ALFRED_CSV_QUARANTINED", number)

    def test_duplicate_observation_period_refused(self):
        bad = CSV + ROW + "\n"
        self.assertEqual(evaluate(bad)["state"], "LAB_ALFRED_CSV_QUARANTINED")

    def test_future_after_selected_vintage_is_never_accepted(self):
        bad = CSV + "2026-03-01,,400.000\n"
        self.assertEqual(evaluate(bad)["state"], "LAB_ALFRED_CSV_QUARANTINED")
        self.assertIn("Future", evaluate(bad)["reason"])

    def test_malformed_csv_and_extra_value_column_rejected(self):
        for bad in (
            CSV.replace(ROW, ROW + ",BULLISH"),
            CSV.replace(ROW, '2025-12-01,"324.054,324.054'),
            CSV.replace(ROW, "not-a-date,324.054,324.054"),
            CSV + "\x00",
        ):
            self.assertEqual(evaluate(bad)["state"], "LAB_ALFRED_CSV_QUARANTINED")

    def test_empty_non_text_and_oversized_csv_refused(self):
        for bad in (None, "", b"2025-12-01,324.054", "A" * 150001):
            self.assertEqual(evaluate(bad)["state"], "LAB_ALFRED_CSV_QUARANTINED")

    def test_forged_manifest_or_wrong_series_refused(self):
        for replacement in (None, {}, {"schema": "FAKE_CASE"}):
            self.assertEqual(
                inspect_alfred_cpi_vintages_csv_lab(CSV, replacement)["state"],
                "LAB_ALFRED_CSV_QUARANTINED",
            )
        case = manifest()
        case["alfred"]["series"] = "CPIAUCSL"
        self.assertEqual(evaluate(CSV, case)["state"], "LAB_ALFRED_CSV_QUARANTINED")

    def test_manifest_with_missing_original_sources_refused(self):
        case = manifest()
        case["sources"] = [case["sources"][0]]
        self.assertEqual(evaluate(CSV, case)["state"], "LAB_ALFRED_CSV_QUARANTINED")
        case = manifest()
        case["sources"][0] = "post-hoc-source"
        self.assertEqual(evaluate(CSV, case)["state"], "LAB_ALFRED_CSV_QUARANTINED")

    def test_research_csv_proposal_does_not_modify_current_manifest(self):
        case = manifest()
        self.assertIsNone(case["alfred"]["feb13_dec2025_value"])
        self.assertFalse(case["alfred"]["vintage_csv_downloaded"])
        out = evaluate()
        self.assertEqual(out["state"], "LAB_ALFRED_TWO_VINTAGE_CANDIDATE_MATCH")
        after = manifest()
        self.assertEqual(after, case)


if __name__ == "__main__":
    unittest.main()
