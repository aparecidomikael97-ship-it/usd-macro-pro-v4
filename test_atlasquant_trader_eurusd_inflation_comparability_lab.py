"""Offline EUR/USD inflation-context tests: no ranking from mixed indices."""
from copy import deepcopy
import unittest

from atlasquant_trader_eurusd_inflation_comparability_lab import (
    compare_eurusd_inflation_context_lab as compare,
)
from atlasquant_trader_eurostat_eur_hicp_once_lab import (
    parse_current_eur_hicp_jsonstat_lab,
)
from atlasquant_trader_bls_us_cpiu_once_lab import parse_current_bls_cpiu_lab
from test_atlasquant_trader_eurostat_eur_hicp_once_lab import (
    raw as eur_raw, NOW as EUR_NOW,
)
from test_atlasquant_trader_bls_us_cpiu_once_lab import (
    raw as us_raw, NOW as US_NOW,
)


def pair():
    eur = parse_current_eur_hicp_jsonstat_lab(eur_raw(), observed_at_utc=EUR_NOW)
    usd = parse_current_bls_cpiu_lab(us_raw(), observed_at_utc=US_NOW)
    assert eur["state"] == "LAB_EUR_HICP_CURRENT_JSONSTAT_QUARANTINED"
    assert usd["state"] == "LAB_CURRENT_US_BLS_CPIU_INDEX_QUARANTINED"
    return eur, usd


class EuUsdInflationCompatibilityLabTests(unittest.TestCase):
    def test_oos_trading_and_direction_always_forbidden(self):
        eur, usd = pair()
        out = compare(eur, usd)
        self.assertEqual(out["state"], "LAB_TWO_CURRENCY_INFLATION_EVIDENCE_ONLY")
        self.assertEqual(out["pair"], "EUR/USD")
        self.assertEqual(out["eur"]["month"], "2026-10")
        self.assertEqual(out["usd"]["month"], "2026-09")
        self.assertFalse(out["observation_months_aligned"])
        self.assertEqual(out["eur"]["observed_yoy_percent_claim"], 4.0)
        self.assertEqual(out["usd"]["derived_yoy_percent_claim"], "5.2938")
        self.assertTrue(out["eur"]["estimate_not_final"])
        self.assertFalse(out["methodologically_comparable"])
        self.assertIn("LATEST_EURO_AND_US_MONTHS_DIFFER", out["comparison_blockers"])
        self.assertIn("HICP_VS_CPI_U_METHODS_NOT_EQUIVALENT", out["comparison_blockers"])
        self.assertIn("EUR_LAST_HICP_OBSERVATION_ESTIMATED", out["comparison_blockers"])
        self.assertIsNone(out["comparison_difference_percentage_points"])
        self.assertIsNone(out["inflation_ranking_of_currencies"])
        self.assertEqual(out["operational_bias"], "AGUARDAR")
        self.assertFalse(out["trade_authorized"])

    def test_aligned_periods_still_not_equivalent_or_tradeable(self):
        eur, usd = pair()
        usd["latest_period"] = "2026-10"
        out = compare(eur, usd)
        self.assertTrue(out["observation_months_aligned"])
        self.assertFalse(out["methodologically_comparable"])
        self.assertFalse(out["currency_direction_proven"])
        self.assertIsNone(out["comparison_difference_percentage_points"])
        self.assertFalse(out["trade_authorized"])

    def test_no_yoy_due_missing_us_denominator_reports_gap_not_zero(self):
        eur, usd = pair()
        usd["derived_yoy_percent_from_same_month_indices"] = None
        usd["prior_year_month_observed"] = False
        out = compare(eur, usd)
        self.assertEqual(out["state"], "LAB_TWO_CURRENCY_INFLATION_EVIDENCE_ONLY")
        self.assertIn("US_SAME_MONTH_PRIOR_YEAR_NOT_AVAILABLE", out["comparison_blockers"])
        self.assertIsNone(out["usd"]["derived_yoy_percent_claim"])
        self.assertFalse(out["can_feed_live_radar"])

    def test_unflagged_euro_is_not_promoted_to_final(self):
        eur, usd = pair()
        eur["historical_months_observed_not_historical_vintages"][-1]["status_flag"] = ""
        out = compare(eur, usd)
        self.assertFalse(out["eur"]["estimate_not_final"])
        self.assertFalse(out["release_instant_comparison_proven"])
        self.assertFalse(out["point_in_time_vintage_verified"])
        self.assertFalse(out["consensus_attested"])

    def test_caller_supplied_parsed_data_is_not_network_authentication(self):
        eur, usd = pair()
        out = compare(eur, usd)
        self.assertEqual(out["source_http_observations_declared"], {
            "EUR": False, "USD": False,
        })
        self.assertEqual(out["external_http_requests"], 0)
        self.assertFalse(out["causal_macro_explanation_proven"])

    def test_wrong_currency_source_and_unavailable_input_fail_closed(self):
        eur, usd = pair()
        for a, b in ((None, usd), (eur, None), ({"state":"LIVE"}, usd)):
            self.assertEqual(compare(a, b)["state"], "LAB_BLOCKED")
        tampered = deepcopy(eur)
        tampered["source_dataset"] = "prc_hicp_manr"
        self.assertEqual(compare(tampered, usd)["reason"],
                         "EURO_HICP_SOURCE_OR_STATUS_INVALID")
        tampered = deepcopy(usd)
        tampered["series_id"] = "SUUR0000SA0"
        self.assertEqual(compare(eur, tampered)["reason"],
                         "US_CPIU_SOURCE_OR_STATUS_INVALID")

    def test_invalid_month_annual_percent_and_denominator_guarded(self):
        eur, usd = pair()
        for bad in ("2026-13", "notmonth"):
            a = deepcopy(eur)
            a["historical_months_observed_not_historical_vintages"][-1]["period"] = bad
            self.assertEqual(compare(a, usd)["state"], "LAB_BLOCKED")
        a = deepcopy(eur)
        a["historical_months_observed_not_historical_vintages"][-1]["annual_inflation_percent"] = float("nan")
        self.assertEqual(compare(a, usd)["reason"],
                         "BAD_PERIOD_OR_EURO_INFLATION_VALUE")
        b = deepcopy(usd)
        b["prior_year_month_observed"] = False
        self.assertEqual(compare(eur, b)["reason"],
                         "DERIVED_US_RATE_WITHOUT_PRIOR_YEAR_MONTH")

    def test_no_automatic_http_workers_deploy_costs_or_trading(self):
        eur, usd = pair()
        out = compare(eur, usd)
        for field in ("worker_enabled", "scheduler_enabled", "publishable",
                      "trade_authorized", "can_feed_live_radar", "consensus_attested",
                      "economic_fundamentals_fully_covered", "news_or_geopolitics_verified"):
            self.assertFalse(out[field], field)
        self.assertEqual((out["new_cost_brl"], out["external_http_requests"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
