"""Contracts against fictitious relative-rate comparability and paid data use."""
from __future__ import annotations

import unittest

from atlasquant_trader_rate_source_suitability_lab import (
    SCHEMA, SOURCES, audit_rate_source_catalog_lab, assess_rate_source_pair_lab,
)


def compare(a, b):
    return assess_rate_source_pair_lab(a, b)


class RateSourceSuitabilityTests(unittest.TestCase):
    def test_five_reviewed_sources(self):
        output = audit_rate_source_catalog_lab()
        self.assertEqual(output["schema"], SCHEMA)
        self.assertEqual(output["source_count"], 5)
        self.assertEqual(len(output["sources"]), 5)
        self.assertEqual(output["usable_market_implied_fx_pair_count"], 0)

    def test_unique_ids(self):
        self.assertEqual(len({s["source_id"] for s in SOURCES}), len(SOURCES))

    def test_all_sources_have_https_official_urls(self):
        for row in SOURCES:
            self.assertTrue(row["source_url"].startswith("https://"))
            self.assertNotIn("@", row["source_url"])

    def test_boe_ois_is_forward_not_policy_rate(self):
        item = next(x for x in SOURCES if x["source_id"] == "BOE_GBP_OIS_DAILY_ARCHIVE")
        self.assertEqual(item["economic_meaning"], "MARKET_IMPLIED_FUTURE_OVERNIGHT_RATE")
        self.assertEqual(item["distribution"], "PUBLIC_DOWNLOAD_NO_API")
        self.assertFalse(item["rights_cleared_for_live_trader"])

    def test_boe_no_future_data_claim(self):
        item = next(x for x in SOURCES if x["currency"] == "GBP")
        self.assertFalse(item["actual_observation_ingested"])
        self.assertTrue(item["publication"].startswith("AIMS_NEXT_BUSINESS_DAY"))

    def test_ecb_estr_is_realized(self):
        item = next(x for x in SOURCES if x["source_id"] == "ECB_EUR_ESTR_OVERNIGHT")
        self.assertEqual(item["economic_meaning"], "REALIZED_OVERNIGHT_FUNDING_RATE")
        self.assertEqual(item["distribution"], "PUBLIC_NO_FEE_ECB")

    def test_ecb_government_forward_is_not_ois(self):
        item = next(x for x in SOURCES
                    if x["source_id"] == "ECB_EUR_SOVEREIGN_YIELD_FORWARD")
        self.assertEqual(item["economic_meaning"],
                         "SOVEREIGN_BOND_TERM_STRUCTURE_WITH_RISK_PREMIA")
        self.assertNotIn("OIS", item["instrument"])
        self.assertIn("TRADING", item["rights"])

    def test_cme_paid_api_blocked(self):
        item = next(x for x in SOURCES
                    if x["source_id"] == "CME_USD_FEDWATCH_PAID_API")
        self.assertTrue(item["paid_api_required"])
        self.assertIn("USD_25_MONTH", item["distribution"])

    def test_nyfed_sofr_is_realized_secured_not_policy_path(self):
        item = next(x for x in SOURCES if x["source_id"] == "NYFED_USD_SOFR_FIXING")
        self.assertEqual(item["economic_meaning"], "REALIZED_SECURED_OVERNIGHT_FUNDING_RATE")

    def test_cross_uk_ois_euro_gov_yield_rejected(self):
        out = compare("BOE_GBP_OIS_DAILY_ARCHIVE",
                      "ECB_EUR_SOVEREIGN_YIELD_FORWARD")
        self.assertIn("Incompatible economic measurements", out["reason"])
        self.assertIsNone(out["expectation_spread_bps"])

    def test_cross_eur_overnight_gbp_forward_rejected(self):
        out = compare("ECB_EUR_ESTR_OVERNIGHT", "BOE_GBP_OIS_DAILY_ARCHIVE")
        self.assertIn("Incompatible economic measurements", out["reason"])

    def test_cross_eur_overnight_usd_sofr_rejected(self):
        out = compare("ECB_EUR_ESTR_OVERNIGHT", "NYFED_USD_SOFR_FIXING")
        self.assertIn("Incompatible economic measurements", out["reason"])

    def test_uk_ois_us_fedwatch_paid_blocked(self):
        out = compare("BOE_GBP_OIS_DAILY_ARCHIVE", "CME_USD_FEDWATCH_PAID_API")
        self.assertIn("Paid source excluded", out["reason"])

    def test_eur_gov_us_fedwatch_paid_blocked(self):
        out = compare("ECB_EUR_SOVEREIGN_YIELD_FORWARD",
                      "CME_USD_FEDWATCH_PAID_API")
        self.assertIn("Paid source excluded", out["reason"])

    def test_unknown_id_is_never_assumed_safe(self):
        out = compare("UNVERIFIED_USD_OIS", "BOE_GBP_OIS_DAILY_ARCHIVE")
        self.assertEqual(out["state"], "LAB_RATE_SOURCE_SELECTION_BLOCKED")
        self.assertIn("Unknown", out["reason"])

    def test_unknown_string_injection_blocked(self):
        out = compare("https://free-price.invalid", "ECB_EUR_ESTR_OVERNIGHT")
        self.assertIn("Unknown", out["reason"])

    def test_non_string_rejected(self):
        out = compare([], "ECB_EUR_ESTR_OVERNIGHT")
        self.assertEqual(out["state"], "LAB_RATE_SOURCE_SELECTION_BLOCKED")

    def test_same_currency_different_series_rejected(self):
        out = compare("ECB_EUR_ESTR_OVERNIGHT", "ECB_EUR_SOVEREIGN_YIELD_FORWARD")
        self.assertIn("same currency", out["reason"])

    def test_same_source_rejected(self):
        out = compare("BOE_GBP_OIS_DAILY_ARCHIVE", "BOE_GBP_OIS_DAILY_ARCHIVE")
        self.assertIn("same currency", out["reason"])

    def test_no_source_has_approved_live_rights(self):
        self.assertTrue(all(not x["rights_cleared_for_live_trader"] for x in SOURCES))

    def test_no_source_has_real_capture_in_repository(self):
        self.assertTrue(all(not x["actual_observation_ingested"] for x in SOURCES))

    def test_audit_never_authorizes_production(self):
        out = audit_rate_source_catalog_lab()
        self.assertFalse(out["all_eight_currencies_covered"])
        self.assertFalse(out["rights_and_historical_receipts_verified"])
        self.assertIsNone(out["fx_bias"])
        self.assertIsNone(out["fx_probability"])
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["can_feed_live_radar"])
        self.assertFalse(out["paid_service_activated"])
        self.assertFalse(out["worker_enabled"])
        self.assertFalse(out["scheduler_enabled"])

    def test_every_possible_distinct_pair_blocked(self):
        for a in SOURCES:
            for b in SOURCES:
                out = compare(a["source_id"], b["source_id"])
                self.assertEqual(out["state"], "LAB_RATE_SOURCE_SELECTION_BLOCKED")
                self.assertFalse(out["market_expectation_comparable"])
                self.assertIsNone(out["fx_bias"])
                self.assertIsNone(out["fx_probability"])
                self.assertFalse(out["trade_authorized"])
                self.assertFalse(out["paid_service_activated"])
                self.assertFalse(out["worker_enabled"])

    def test_catalog_copy_does_not_mutate_internal_facts(self):
        out = audit_rate_source_catalog_lab()
        out["sources"][0]["currency"] = "FAKE"
        self.assertEqual(audit_rate_source_catalog_lab()["sources"][0]["currency"], "GBP")

    def test_no_autonomous_api_fetch(self):
        import inspect
        from atlasquant_trader_rate_source_suitability_lab import (
            assess_rate_source_pair_lab,
        )
        source = inspect.getsource(assess_rate_source_pair_lab)
        self.assertNotIn("requests.get", source)
        self.assertNotIn("urlopen", source)
        self.assertNotIn("subprocess", source)


if __name__ == "__main__":
    unittest.main()
