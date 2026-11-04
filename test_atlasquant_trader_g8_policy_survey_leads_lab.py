"""Official G8 survey lead coverage and stale BoE respondent probabilities, LAB."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_g8_policy_survey_leads_lab import (
    SCHEMA, LEADS, BOE_NOV5_BUCKETS, build_g8_policy_survey_leads_lab,
)

BEFORE = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


def audit(at=BEFORE, sources=None, buckets=None):
    return build_g8_policy_survey_leads_lab(
        at=at, sources=sources, boe_probabilities=buckets,
    )


def chosen(pair, horizon="D1"):
    return next(r for r in audit()["pair_horizons"]
                if r["pair"] == pair and r["horizon"] == horizon)


class G8SurveyLeadsLabTests(unittest.TestCase):
    def test_all_eight_currencies_and_exact_lead_counts(self):
        r = audit()
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["source_count"], 8)
        self.assertEqual(set(r["source_leads"]), set(CURRENCIES))
        self.assertEqual(r["survey_lead_count"], 5)
        self.assertEqual(r["commentary_only_count"], 1)
        self.assertEqual(r["no_comparable_survey_lead_count"], 2)

    def test_twenty_eight_pairs_three_horizons(self):
        r = audit()
        self.assertEqual(len(r["pair_horizons"]), 84)
        for h in ("D1", "W1", "MN1"):
            rows = [x for x in r["pair_horizons"] if x["horizon"] == h]
            self.assertEqual(len(rows), 28)
            self.assertEqual({x["pair"] for x in rows}, set(OFFICIAL_PAIRS))

    def test_survey_not_equal_to_market_implied_forward_curve(self):
        r = audit()
        self.assertEqual(r["state"], "LAB_G8_OFFICIAL_SURVEY_SOURCE_LEADS_ONLY")
        self.assertFalse(r["same_tenor_expectation_curves_verified"])
        self.assertFalse(r["market_quotes_verified"])
        self.assertFalse(r["raw_cross_bank_rate_paths_available"])
        self.assertFalse(r["maturity_matched"])

    def test_us_nyfed_after_fomc_publication_caveat(self):
        p = audit()["source_leads"]["USD"]
        self.assertEqual(p["source_id"], "NYFED_SME")
        self.assertEqual(p["publication_granularity"], "AFTER_FOMC_MINUTES")
        self.assertIn("after the corresponding FOMC", p["review_limitation"])

    def test_euro_sma_not_policy_decision(self):
        x = audit()["source_leads"]["EUR"]
        self.assertEqual(x["target_kind"], "DEPOSIT_FACILITY_RATE_BY_ECB_MEETING")
        self.assertNotEqual(x["category"], "NO_PUBLIC_MATCHED_EXPECTATION_SURVEY_FOUND")

    def test_gbp_meeting_probability_documented_not_fx_probability(self):
        x = audit()["boe_nov5_documentary"]
        self.assertEqual(x["respondents"], 90)
        self.assertEqual(x["probability_kind"], "MEAN_OF_SURVEY_RESPONDENT_OPINIONS")
        self.assertIsNone(x["currency_fx_probability"])
        self.assertFalse(x["market_implied_ois_distribution"])

    def test_boe_real_official_buckets_as_documented(self):
        bands = {x["rate_after_mpc_band"]:x["mean_respondent_probability_pct"]
                 for x in audit()["boe_nov5_documentary"]["rate_buckets"]}
        self.assertEqual(bands["3_75"], "60.4")
        self.assertEqual(bands["4_00"], "35.0")
        self.assertEqual(bands["3_50"], "1.7")
        self.assertEqual(bands["ABOVE_4_25"], "0.3")

    def test_rounding_total_is_1001_not_forced_100(self):
        self.assertEqual(audit()["boe_nov5_documentary"]["sum_after_one_decimal_rounding_pct"],
                         "100.1")

    def test_boe_old_september_not_fresh_market_price(self):
        x = audit()["boe_nov5_documentary"]
        self.assertEqual(x["sample_collected_through"], "2026-09-04")
        self.assertEqual(x["published_on"], "2026-09-18")
        self.assertEqual(x["target_mpc_on"], "2026-11-05")
        self.assertEqual(x["survey_state"],
                         "HISTORICAL_PRE_MEETING_SURVEY_NOT_CURRENT_CONSENSUS")

    def test_unknown_hour_on_mpc_day_is_guarded(self):
        r = audit(at=datetime(2026,11,5,18,tzinfo=timezone.utc))
        self.assertEqual(r["boe_nov5_documentary"]["survey_state"],
                         "MEETING_DAY_PUBLICATION_HOUR_UNATTESTED")

    def test_after_mpc_does_not_claim_pre_event(self):
        r = audit(at=datetime(2026,11,6,18,tzinfo=timezone.utc))
        self.assertEqual(r["boe_nov5_documentary"]["survey_state"],
                         "TARGET_MEETING_PASSED_NO_OUTCOME_IMPORTED")

    def test_older_than_research_compilation_refused(self):
        r = audit(at=datetime(2026,11,3,23,59,tzinfo=timezone.utc))
        self.assertEqual(r["state"], "LAB_SURVEY_LEADS_REFUSED")
        self.assertEqual(r["pair_horizons"], [])

    def test_non_timezone_clock_refused(self):
        with self.assertRaises(ValueError):
            audit(at=datetime(2026,11,4,12))

    def test_cad_survey_results_lag_and_nov9_not_backdated(self):
        x = audit()["source_leads"]["CAD"]
        self.assertEqual(x["publication_granularity"], "QUARTERLY_DELAYED")
        self.assertIn("November 9", x["review_limitation"])

    def test_nzd_quarter_end_not_d1_forward_curve(self):
        x = audit()["source_leads"]["NZD"]
        self.assertEqual(x["target_kind"], "OCR_QUARTER_END_AND_ONE_YEAR_MEAN")
        self.assertEqual(x["category"], "OFFICIAL_POLICY_EXPECTATIONS_SURVEY_LEAD")

    def test_aud_graph_not_raw_reusable_ois(self):
        x = audit()["source_leads"]["AUD"]
        self.assertEqual(x["category"],
                         "OFFICIAL_MARKET_EXPECTATIONS_SUMMARY_NO_RAW_CURVE")
        self.assertFalse(audit()["raw_cross_bank_rate_paths_available"])

    def test_jpy_money_market_functioning_not_rate_path(self):
        x = audit()["source_leads"]["JPY"]
        self.assertEqual(x["category"],
                         "NO_PUBLIC_MATCHED_EXPECTATION_SURVEY_FOUND")
        self.assertIn("not a public meeting-by-meeting", x["review_limitation"])

    def test_chf_conditional_forecast_not_market_expectation(self):
        x = audit()["source_leads"]["CHF"]
        self.assertEqual(x["category"],
                         "NO_PUBLIC_MATCHED_EXPECTATION_SURVEY_FOUND")
        self.assertEqual(x["target_kind"], "SNB_DECISION_NOT_MARKET_EXPECTATION")

    def test_usdjpy_missing_public_survey(self):
        self.assertEqual(chosen("USD/JPY")["research_gap"],
                         "MISSING_MEETING_RATE_EXPECTATION_LEAD")

    def test_eurusd_both_surveys_but_unmatched_vintage(self):
        self.assertEqual(chosen("EUR/USD")["research_gap"],
                         "SURVEY_TARGETS_AND_VINTAGES_NOT_COMPARABLE")

    def test_audusd_summary_not_market_curve(self):
        self.assertEqual(chosen("AUD/USD")["research_gap"],
                         "SUMMARY_WITHOUT_REUSABLE_MATCHED_CURVE")

    def test_cross_pair_missing_causes_abstention(self):
        for p in ("USD/JPY", "USD/CHF", "CHF/JPY", "EUR/JPY"):
            self.assertEqual(chosen(p)["directional_bias"], "AGUARDAR")

    def test_no_hypothetical_probability_promoted(self):
        r = audit()
        self.assertIsNone(r["probability_calibrated"])
        for x in r["pair_horizons"]:
            self.assertIsNone(x["expectation_gap_bp"])
            self.assertIsNone(x["probability_calibrated"])
            self.assertFalse(x["trade_authorized"])

    def test_tampered_source_url_refused(self):
        src = deepcopy(LEADS)
        src[0]["source_url"] = "https://evil.invalid"
        self.assertEqual(audit(sources=src)["state"], "LAB_SURVEY_LEADS_REFUSED")

    def test_tampered_report_classification_refused(self):
        src = deepcopy(LEADS)
        src[5]["category"] = "OFFICIAL_POLICY_EXPECTATIONS_SURVEY_LEAD"
        src[3]["category"] = "OFFICIAL_POLICY_EXPECTATIONS_SURVEY_LEAD"
        self.assertEqual(audit(sources=src)["state"], "LAB_SURVEY_LEADS_REFUSED")

    def test_missing_or_duplicate_source_refused(self):
        src = list(deepcopy(LEADS))
        src[-1] = deepcopy(src[0])
        self.assertEqual(audit(sources=src)["state"], "LAB_SURVEY_LEADS_REFUSED")
        self.assertEqual(audit(sources=src[:-1])["state"], "LAB_SURVEY_LEADS_REFUSED")

    def test_tampered_probability_refused(self):
        b = deepcopy(BOE_NOV5_BUCKETS)
        b[2]["mean_respondent_probability_pct"] = "90.0"
        self.assertEqual(audit(buckets=b)["state"], "LAB_SURVEY_LEADS_REFUSED")

    def test_forged_extra_probability_column_refused(self):
        b = deepcopy(BOE_NOV5_BUCKETS)
        b[0]["fx_probability"] = "90"
        self.assertEqual(audit(buckets=b)["state"], "LAB_SURVEY_LEADS_REFUSED")

    def test_real_historical_capture_not_attested(self):
        r = audit()
        self.assertFalse(r["independent_source_receipts_verified"])
        self.assertFalse(r["boe_nov5_documentary"]["publication_timestamp_independently_attested"])
        self.assertFalse(r["survey_source_reuse_rights_verified"])

    def test_no_go_everywhere(self):
        r = audit()
        for flag in ("market_quotes_verified", "fx_directional_oos_proven",
                     "accuracy_90_proven", "trade_authorized",
                     "can_feed_live_radar", "paid_services_enabled",
                     "worker_enabled", "scheduler_enabled"):
            with self.subTest(flag=flag):
                self.assertIs(r[flag], False)

    def test_source_urls_are_official_https(self):
        hosts = ("newyorkfed.org","ecb.europa.eu","bankofengland.co.uk",
                 "boj.or.jp","snb.ch","bankofcanada.ca","rba.gov.au","rbnz.govt.nz")
        for row in audit()["source_leads"].values():
            with self.subTest(currency=row["currency"]):
                self.assertTrue(row["source_url"].startswith("https://"))
                self.assertTrue(any(host in row["source_url"] for host in hosts))


if __name__ == "__main__":
    unittest.main()
