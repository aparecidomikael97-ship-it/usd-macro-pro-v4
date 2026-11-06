"""Prove candidate-source documents never turn into FX outputs."""
from hashlib import sha256
from pathlib import Path
import json
import unittest

from atlasquant_trader_g8_cpi_source_feasibility_lab import (
    FIXED_CASEBOOK_SHA256, REQUIREMENTS,
    inspect_g8_cpi_source_feasibility_lab as inspect,
)

RAW = (Path(__file__).resolve().parent / "docs" / "continuidade" /
       "TRADER_G8_20261106_OECD_EUROSTAT_CPI_SOURCE_FEASIBILITY_LAB.json").read_bytes()


class G8CpiSourceFeasibilityTests(unittest.TestCase):
    def assert_no_operations(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["fx_bias"])
        self.assertIsNone(result["best_pair_of_day"])
        self.assertEqual(result["ranked_currencies"], [])
        self.assertEqual(result["validated_prediction_count"], 0)
        self.assertIsNone(result["validated_accuracy"])
        self.assertEqual((result["http_requests"], result["new_cost_brl"]), (0, 0))
        for flag in ("can_feed_live_radar", "trade_authorized", "publishable",
                     "worker_enabled", "scheduler_enabled",
                     "all_28_pairs_have_identical_frequency_and_method_verified",
                     "all_8_currencies_monthly_2026_verified",
                     "oecd_current_api_is_historical_pit_vintage",
                     "eurostat_first_published_is_full_historical_release_clock",
                     "oecd_currency_level_series_responses_verified",
                     "commercial_redistribution_verified"):
            self.assertIs(result[flag], False, flag)
        self.assertEqual(tuple(result["prerequisites_not_met"]), REQUIREMENTS)

    def test_official_documentation_candidates_only_no_payloads(self):
        r = inspect(RAW)
        self.assertEqual(r["state"], "LAB_G8_CPI_SOURCE_CANDIDATES_FOUND_BUT_NOT_PIT_READY")
        self.assertEqual((r["currency_count"], r["pair_count"],
                          r["candidate_source_count"]), (8, 28, 5))
        self.assertEqual(r["accepted_casebook_sha256"], FIXED_CASEBOOK_SHA256)
        self.assertEqual(r["accepted_casebook_sha256"], sha256(RAW).hexdigest())
        self.assert_no_operations(r)

    def test_two_oecd_coicop_versions_not_misrepresented_as_one(self):
        r = inspect(RAW)
        self.assertIn("OECD_CPI_COICOP_1999", r["candidate_source_identifiers"])
        self.assertIn("OECD_CPI_COICOP_2018", r["candidate_source_identifiers"])
        self.assertFalse(r["oecd_currency_level_series_responses_verified"])

    def test_eurostat_first_published_is_not_pit_time_receipt(self):
        r = inspect(RAW)
        self.assertEqual(r["currency_source_routes_are_hypothetical"]["EUR"],
                         "EUROSTAT_HICP_FIRST_PUBLISHED")
        self.assertEqual(r["next_experiment"],
                         "EUROSTAT_HICP_FIRST_PUBLISHED_SCHEMA_AND_GEO_EA21_READONLY_CHECK")
        self.assertFalse(r["eurostat_first_published_is_full_historical_release_clock"])
        self.assert_no_operations(r)

    def test_monthly_abs_and_quarterly_nz_do_not_get_overwritten_by_old_oecd_faq(self):
        r = inspect(RAW)
        self.assertEqual(r["currencies_with_domestic_quarterly_2026_cpi_claim"], ["NZD"])
        self.assertEqual(len(r["currencies_with_domestic_monthly_2026_cpi_claim"]), 7)
        self.assertIn("AUD", r["currencies_with_domestic_monthly_2026_cpi_claim"])
        self.assertEqual(r["currency_source_routes_are_hypothetical"]["AUD"],
                         "ABS_COMPLETE_MONTHLY_2025_TRANSITION")
        self.assertEqual(r["currency_source_routes_are_hypothetical"]["NZD"],
                         "STATSNZ_QUARTERLY_2026_MONTHLY_PLANNED_2027")

    def test_all_eight_routes_present_but_not_confirmed_oecd_series(self):
        r = inspect(RAW)
        self.assertEqual(set(r["currency_source_routes_are_hypothetical"]),
                         {"USD", "EUR", "JPY", "GBP", "CHF", "AUD", "CAD", "NZD"})
        self.assert_no_operations(r)

    def test_casebook_keeps_2027_nz_monthly_future_not_2026_current(self):
        case = json.loads(RAW)
        self.assertIs(case["future_nzd_monthly_2027_already_published_in_2026"], False)
        self.assertIn("NEW_ZEALAND_QUARTERLY_2026_NOT_MONTHLY_SEPTEMBER",
                      case["conflicts_and_limitations"])

    def test_oecd_aggregates_not_assumed_to_replace_euro_area_hicp(self):
        case = json.loads(RAW)
        self.assertIn("EUR_IS_EURO_AREA_HICP_NOT_A_SINGLE_NATIONAL_CPI_SERIES",
                      case["conflicts_and_limitations"])
        self.assert_no_operations(inspect(RAW))

    def test_reject_modified_source_document_url_dataset_or_frequency(self):
        for path, replacement in (("official_document_url", "https://example.com/fake"),
                                  ("dataset_id", "FAKE_SERIES"),
                                  ("dataset_family", "LIVE_FOREX_SIGNALS")):
            x = json.loads(RAW)
            x["sources"][0][path] = replacement
            r = inspect(json.dumps(x).encode())
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_operations(r)
        x = json.loads(RAW)
        x["routes"][7]["domestic_release_frequency_2026"] = "MONTHLY"
        self.assertEqual(inspect(json.dumps(x).encode())["state"], "LAB_BLOCKED")

    def test_refuse_bogus_current_pit_and_license_assertions(self):
        for key in ("source_api_responses_archived",
                    "source_dataset_coverage_per_currency_verified",
                    "original_historical_release_vintages_attested",
                    "source_redistribution_rights_verified"):
            x = json.loads(RAW)
            x[key] = True
            self.assertEqual(inspect(json.dumps(x).encode())["state"], "LAB_BLOCKED")

    def test_bad_raw_and_duplicate_keys_rejected(self):
        for raw in (None, "text", b"", b"\xff" * 500, b"a" * 16001,
                    RAW.replace(b'"kind":', b'"kind":"FAKE", "kind":', 1)):
            r = inspect(raw)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_operations(r)


if __name__ == "__main__":
    unittest.main()
