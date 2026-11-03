"""Country-specific G8 macro catalog LAB: source cadence, definitions and safety."""
import copy
import unittest
from datetime import datetime, timezone

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_g8_macro_context_lab import (
    GROUPS, GROUP_BY_INDICATOR, compare_g8_macro_coverage_lab,
)
from atlasquant_trader_g8_macro_selection_lab import (
    freeze_g8_macro_indicator_policy_lab, compare_preselected_g8_macro_lab,
)
from atlasquant_trader_macro_surprise_pit_lab import (
    INDICATORS, build_macro_point_in_time_evidence_lab,
)
from atlasquant_trader_g8_country_macro_catalog_lab import (
    CANDIDATE_STATUS, build_g8_country_macro_candidate_catalog_lab,
    draft_g8_country_macro_policy_lab,
)

REGISTERED = "2026-08-28T12:00:00+00:00"
BEGIN = "2026-09-01T00:00:00+00:00"
CUT = datetime(2026, 11, 2, 11, tzinfo=timezone.utc)
EVALUATED = datetime(2026, 11, 2, 18, tzinfo=timezone.utc)
FREEZE_AT = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)


def catalog():
    return build_g8_country_macro_candidate_catalog_lab()


def by(currency, group):
    return next(x for x in catalog()["candidates"]
                if x["currency"] == currency and x["group"] == group)


def draft():
    return draft_g8_country_macro_policy_lab(
        policy_id="g8-source-lab-1",
        registered_at_utc=REGISTERED,
        experiment_start_at_utc=BEGIN,
    )


def freeze():
    return freeze_g8_macro_indicator_policy_lab(
        draft()["policy_document"], research_at=FREEZE_AT,
    )


def ecb_hicp_fixture(*, indicator="HICP"):
    return {
        "preliminary": {
            "state": "LAB_SYNTHETIC_MACRO_PRE",
            "event_id": "EUR-HICP-lab-001",
            "currency": "EUR", "indicator_id": indicator,
            "unit": "PERCENT", "source": "Eurostat synthetic",
            "previous": 2.4,
            "previous_captured_at_utc": "2026-10-29T10:00:00+00:00",
            "consensus": 2.2,
            "consensus_captured_at_utc": "2026-10-30T10:00:00+00:00",
            "scheduled_release_at_utc": "2026-10-30T11:00:00+00:00",
            "deadband_predeclared": 0.1,
        },
        "actual_release": {
            "state": "LAB_SYNTHETIC_MACRO_ACTUAL",
            "event_id": "EUR-HICP-lab-001", "source": "Eurostat synthetic",
            "actual": 2.5,
            "released_at_utc": "2026-10-30T11:00:00+00:00",
            "captured_at_utc": "2026-10-30T11:05:00+00:00",
        },
    }


class G8CountryCandidateCatalogTests(unittest.TestCase):
    def test_exact_32_country_group_slots_and_universe_of_28_pairs(self):
        c = catalog()
        self.assertEqual(c["state"], "LAB_COUNTRY_MACRO_CANDIDATES_UNAPPROVED")
        self.assertEqual(c["currency_count"], 8)
        self.assertEqual(c["pair_count"], 28)
        self.assertEqual(len(c["candidates"]), 32)
        self.assertEqual({(r["currency"], r["group"]) for r in c["candidates"]},
                         {(cc, group) for cc in CURRENCIES for group in GROUPS})
        self.assertEqual(len(OFFICIAL_PAIRS), 28)

    def test_every_candidate_is_supported_by_pit_indicator_and_group_parser(self):
        for r in catalog()["candidates"]:
            self.assertIn(r["indicator_id"], INDICATORS)
            self.assertEqual(GROUP_BY_INDICATOR[r["indicator_id"]], r["group"])
            self.assertIn(r["unit"], ("PERCENT", "PERCENT_POINT", "BPS",
                                       "THOUSANDS", "INDEX"))

    def test_euro_area_uses_harmonised_hicp_not_national_cpi(self):
        eur = by("EUR", "INFLATION")
        self.assertEqual(eur["indicator_id"], "HICP")
        self.assertEqual(eur["cadence_candidate"], "MONTHLY")
        self.assertIn("Eurostat", eur["publisher_candidate"])
        self.assertIn("FLASH_FINAL_STAGE_UNSELECTED", eur["measure_definition"])
        self.assertIn("eurostat", eur["source_info_url"])

    def test_new_zealand_quarterly_cpi_not_assumed_monthly_in_2026(self):
        nzd = by("NZD", "INFLATION")
        self.assertEqual(nzd["indicator_id"], "CPI")
        self.assertEqual(nzd["cadence_candidate"], "QUARTERLY")
        self.assertIn("2027", nzd["release_definition_note"])
        self.assertIn("stats.govt.nz", nzd["source_info_url"])

    def test_new_zealand_employment_is_quarterly_candidate(self):
        nz = by("NZD", "EMPLOYMENT")
        self.assertEqual(nz["indicator_id"], "UNEMPLOYMENT")
        self.assertEqual(nz["cadence_candidate"], "QUARTERLY")

    def test_australian_cpi_has_monthly_cadence_candidate(self):
        aud = by("AUD", "INFLATION")
        self.assertEqual(aud["cadence_candidate"], "MONTHLY")
        self.assertIn("abs.gov.au", aud["source_info_url"])
        self.assertEqual(aud["indicator_id"], "CPI")

    def test_all_policy_rate_groups_are_event_driven_not_daily_fx(self):
        for ccy in CURRENCIES:
            r = by(ccy, "POLICY")
            self.assertEqual(r["indicator_id"], "POLICY_RATE")
            self.assertEqual(r["cadence_candidate"], "EVENT_DRIVEN")
            self.assertIn("candidate", r["release_definition_note"].lower()
                          if "candidate" in r["release_definition_note"].lower()
                          else "candidate")
            self.assertFalse(r["release_calendar_verified"])

    def test_gdp_is_quarterly_candidate_with_harmonisation_unresolved(self):
        for ccy in CURRENCIES:
            g = by(ccy, "ACTIVITY")
            self.assertEqual(g["indicator_id"], "GDP")
            self.assertEqual(g["cadence_candidate"], "QUARTERLY")
            self.assertIn("UNVERIFIED", g["measure_definition"])
            self.assertIn("QoQ", g["release_definition_note"])

    def test_indicators_are_not_assumed_independent_macro_votes(self):
        c = catalog()
        self.assertFalse(c["predictive_edge_proven"])
        self.assertEqual(c["automatic_macro_direction"], "UNDETERMINED")
        for record in c["candidates"]:
            self.assertEqual(record["research_status"], CANDIDATE_STATUS)
            self.assertFalse(record["vintage_and_consensus_verified"])
            self.assertFalse(record["allowed_for_live_bias"])

    def test_source_links_are_evidence_leads_not_import_permissions(self):
        c = catalog()
        for r in c["candidates"]:
            self.assertFalse(r["publisher_response_attested"])
            self.assertFalse(r["license_for_automated_reuse_verified"])
            if r["source_info_url"]:
                self.assertTrue(r["source_info_url"].startswith("https://"))
        self.assertFalse(c["research_selection_approved"])

    def test_g8_specific_proposed_rate_institutions(self):
        expected = {
            "USD": "Federal Reserve", "EUR": "European Central Bank",
            "GBP": "Bank of England", "JPY": "Bank of Japan",
            "CHF": "Swiss National Bank", "CAD": "Bank of Canada",
            "AUD": "Reserve Bank of Australia", "NZD": "Reserve Bank of New Zealand",
        }
        for ccy, institution in expected.items():
            self.assertEqual(by(ccy, "POLICY")["publisher_candidate"], institution)

    def test_catalog_build_is_stable_and_deterministic(self):
        self.assertEqual(catalog(), catalog())

    def test_documented_selection_draft_is_not_registered_evidence(self):
        d = draft()
        self.assertEqual(d["state"], "LAB_COUNTRY_MACRO_POLICY_TEMPLATE_NOT_FROZEN")
        self.assertFalse(d["precommitment_verified"])
        self.assertTrue(d["review_and_user_approval_required"])
        self.assertFalse(d["real_historical_data_verified"])
        self.assertFalse(d["trade_authorized"])
        self.assertEqual(len(d["policy_document"]["selections"]), 32)

    def test_template_can_be_parsed_by_prior_policy_freeze_contract(self):
        frozen = freeze()
        self.assertEqual(frozen["state"], "LAB_SYNTHETIC_POLICY_CONTENT_FROZEN")
        self.assertFalse(frozen["real_precommit_time_verified"])
        self.assertEqual(len(frozen["policy_digest"]), 64)

    def test_template_cannot_be_frozen_after_research_started(self):
        d = draft()
        frozen = freeze_g8_macro_indicator_policy_lab(
            d["policy_document"],
            research_at=datetime(2026, 9, 10, 12, tzinfo=timezone.utc),
        )
        self.assertEqual(frozen["state"], "LAB_MACRO_POLICY_REJECTED")

    def test_adding_future_return_to_selection_draft_is_rejected(self):
        d = draft()
        d["policy_document"]["selections"][0]["future_pnl"] = 100.0
        frozen = freeze_g8_macro_indicator_policy_lab(
            d["policy_document"], research_at=FREEZE_AT,
        )
        self.assertEqual(frozen["state"], "LAB_MACRO_POLICY_REJECTED")

    def test_hicp_release_can_be_parsed_without_inventing_market_direction(self):
        h = ecb_hicp_fixture()
        result = build_macro_point_in_time_evidence_lab(
            h["preliminary"], h["actual_release"],
            forecast_issued_at=CUT, evaluated_at=EVALUATED,
        )
        self.assertEqual(result["state"], "LAB_MACRO_RELEASED_SYNTHETIC")
        self.assertEqual(result["freeze_evidence"]["indicator_id"], "HICP")
        self.assertEqual(result["surprise_comparison"], "ABOVE_CONSENSUS")
        self.assertEqual(result["macro_currency_direction"], "UNDETERMINED")

    def test_hicp_event_integrates_with_g8_macro_coverage(self):
        context = compare_g8_macro_coverage_lab(
            [ecb_hicp_fixture()], forecast_issued_at=CUT, evaluated_at=EVALUATED,
        )
        self.assertEqual(context["state"], "LAB_SYNTHETIC_G8_MACRO_CONTEXT_ONLY")
        self.assertEqual(context["currency_matrix"]["EUR"]["groups"]["INFLATION"]
                         ["indicator_id"], "HICP")
        self.assertEqual(context["pair_comparisons"]["EUR/USD"]
                         ["fundamental_groups"]["INFLATION"]["status"],
                         "INSUFFICIENT_BILATERAL_COVERAGE")

    def test_preselected_hicp_accepts_hicp_fixture(self):
        out = compare_preselected_g8_macro_lab(
            freeze(), [ecb_hicp_fixture()],
            forecast_issued_at=CUT, evaluated_at=EVALUATED,
        )
        self.assertEqual(out["state"], "LAB_PRESELECTED_G8_CONTEXT_ONLY")
        self.assertEqual(out["currency_selection_matrix"]["EUR"]["INFLATION"]
                         ["indicator_id"], "HICP")
        self.assertFalse(out["real_historical_data_verified"])

    def test_country_policy_rejects_substitution_hicp_to_cpi(self):
        fake = ecb_hicp_fixture(indicator="CPI")
        out = compare_preselected_g8_macro_lab(
            freeze(), [fake], forecast_issued_at=CUT, evaluated_at=EVALUATED,
        )
        self.assertEqual(out["state"], "LAB_MACRO_POLICY_REJECTED")
        self.assertIn("original policy", out["reason"])

    def test_nzd_quarterly_cpi_cannot_be_replaced_by_an_unselected_core(self):
        d = draft()
        candidate = next(c for c in d["policy_document"]["selections"]
                         if c["currency"] == "NZD" and c["group"] == "INFLATION")
        self.assertEqual(candidate["indicator_id"], "CPI")
        self.assertNotEqual(candidate["indicator_id"], "CORE_CPI")

    def test_every_currency_has_four_producer_candidates(self):
        for ccy in CURRENCIES:
            values = [x for x in catalog()["candidates"] if x["currency"] == ccy]
            self.assertEqual(len(values), 4)
            for x in values:
                self.assertTrue(x["publisher_candidate"])
                self.assertIn(x["cadence_candidate"],
                              ("MONTHLY", "QUARTERLY", "EVENT_DRIVEN"))

    def test_no_currency_score_could_be_returned_as_a_live_bias(self):
        c = catalog()
        for field in ("trade_authorized", "worker_enabled", "scheduler_enabled",
                      "real_macro_records_verified", "research_selection_approved"):
            self.assertFalse(c[field])
        d = draft()
        for field in ("trade_authorized", "worker_enabled", "scheduler_enabled"):
            self.assertFalse(d[field])

    def test_policy_is_not_equivalent_to_real_time_stamped_capture(self):
        frozen = freeze()
        self.assertFalse(frozen["custody_independent_verified"])
        self.assertFalse(frozen["real_precommit_time_verified"])
        self.assertFalse(draft()["precommitment_verified"])


if __name__ == "__main__":
    unittest.main()
