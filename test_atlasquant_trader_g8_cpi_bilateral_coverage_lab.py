"""Pure offline, synthetic coverage tests. No live market or source calls."""
from copy import deepcopy
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_g8_cpi_bilateral_coverage_lab import (
    inspect_g8_cpi_bilateral_coverage_lab as inspect,
)
from atlasquant_trader_g8_cpi_eurostat_semantics_lab import (
    interpret_eurostat_flash_html_lab,
)
from test_atlasquant_trader_g8_cpi_eurostat_semantics_lab import html_doc


def fixture(*, include_eur=True):
    rows = {currency: None for currency in CURRENCIES}
    if include_eur:
        doc = interpret_eurostat_flash_html_lab(html_doc(), period="2026-10")
        doc["local_archive_integrity_verified"] = True  # synthetic receipt
        rows["EUR"] = doc
    return rows


class BilateralCPICoverageTests(unittest.TestCase):
    def no_go(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIs(result["trade_authorized"], False)
        self.assertIs(result["publishable"], False)
        self.assertIs(result["worker_enabled"], False)
        self.assertIs(result["scheduler_enabled"], False)
        self.assertIs(result["value_independently_verified"], False)
        self.assertIs(result["historical_point_in_time_verified"], False)
        self.assertIs(result["two_sided_macro_comparison_allowed"], False)
        self.assertIs(result["economic_value_used_for_direction"], False)
        self.assertIsNone(result["directional_probability"])
        self.assertIsNone(result["score_0_to_10"])
        self.assertEqual(result["http_requests"], 0)
        self.assertEqual(result["file_writes"], 0)
        self.assertEqual(result["new_cost_brl"], 0)

    def test_eur_document_appears_one_sided_in_exactly_seven_crosses(self):
        r = inspect(fixture(), horizon="D1")
        self.assertEqual(r["state"], "LAB_CPI_DOCUMENT_COVERAGE_REPORTED_NO_BIAS")
        self.assertEqual(r["pair_count"], 28)
        self.assertEqual(set(r["pairs"]), set(OFFICIAL_PAIRS))
        self.assertEqual(r["documented_currencies"], ["EUR"])
        self.assertEqual(r["one_sided_pairs"], 7)
        self.assertEqual(r["two_sided_pairs"], 0)
        self.assertEqual(r["no_document_pairs"], 21)
        for pair, item in r["pairs"].items():
            if "EUR" in (item["base"], item["quote"]):
                self.assertEqual(item["coverage_state"], "ONE_SIDE_DOCUMENTARY_ONLY")
                self.assertEqual(item["documented_currencies"], ["EUR"])
            else:
                self.assertEqual(item["coverage_state"], "NO_CPI_DOCUMENTS")
            self.assertFalse(item["two_sided_comparison_allowed"], pair)
            self.assertFalse(item["trade_authorized"], pair)
        self.no_go(r)

    def test_no_document_mean_28_uncovered_pairs(self):
        r = inspect(fixture(include_eur=False), horizon="W1")
        self.assertEqual(r["pair_count"], 28)
        self.assertEqual(r["one_sided_pairs"], 0)
        self.assertEqual(r["no_document_pairs"], 28)
        self.assertEqual(r["documented_currencies"], [])
        self.no_go(r)

    def test_monthly_horizon_is_coverage_only(self):
        r = inspect(fixture(), horizon="M1")
        self.assertEqual(r["horizon"], "M1")
        self.assertEqual(r["one_sided_pairs"], 7)
        self.no_go(r)

    def test_duplicate_or_wrong_currency_set_is_rejected(self):
        for item in ({}, {"EUR": None}, [], None,
                     dict(fixture(), NOK=None)):
            with self.subTest(value=str(type(item))):
                r = inspect(item, horizon="D1")
                self.assertEqual(r["state"], "LAB_CPI_COVERAGE_BLOCKED")
                self.no_go(r)

    def test_unsupported_currency_document_is_rejected(self):
        r = fixture()
        r["USD"] = deepcopy(r["EUR"])
        out = inspect(r, horizon="D1")
        self.assertEqual(out["reason"], "OTHER_CURRENCY_ISSUER_ADAPTER_NOT_YET_VALIDATED")
        self.no_go(out)

    def test_wrong_horizon_fail_closed(self):
        for h in ("M15", "H1", "M5", "MONTH", None, []):
            with self.subTest(h=h):
                out = inspect(fixture(), horizon=h)
                self.assertEqual(out["state"], "LAB_CPI_COVERAGE_BLOCKED")
                self.no_go(out)

    def test_claim_of_authenticated_release_is_rejected(self):
        for key in ("value_independently_verified", "issuer_first_release_authenticated",
                    "clock_independently_authenticated", "historical_point_in_time_eligible",
                    "can_feed_macro_bias", "trade_authorized", "publishable",
                    "scheduler_enabled", "worker_enabled"):
            with self.subTest(field=key):
                rows = fixture()
                rows["EUR"][key] = True
                out = inspect(rows, horizon="D1")
                self.assertEqual(out["state"], "LAB_CPI_COVERAGE_BLOCKED")
                self.no_go(out)

    def test_damaged_value_or_unsupported_period_is_rejected(self):
        cases = (("documentary_cpi_yoy_percent", "NaN"),
                 ("documentary_cpi_yoy_percent", "4,0"),
                 ("documentary_previous_yoy_percent", "999"),
                 ("reference_period", "2026-09"),
                 ("publication_stage", "FINAL"),
                 ("local_archive_integrity_verified", False),
                 ("same_document_value_consistent", False),
                 ("schema", "wrong"))
        for key, value in cases:
            with self.subTest(key=key):
                rows = fixture()
                rows["EUR"][key] = value
                out = inspect(rows, horizon="D1")
                self.assertEqual(out["state"], "LAB_CPI_COVERAGE_BLOCKED")
                self.no_go(out)

    def test_input_is_not_mutated_and_no_values_enter_pair_views(self):
        rows = fixture()
        before = deepcopy(rows)
        out = inspect(rows, horizon="D1")
        self.assertEqual(rows, before)
        for item in out["pairs"].values():
            self.assertNotIn("documentary_cpi_yoy_percent", item)
            self.assertNotIn("score", item)
            self.assertNotIn("side", item)
        self.no_go(out)


if __name__ == "__main__":
    unittest.main()
