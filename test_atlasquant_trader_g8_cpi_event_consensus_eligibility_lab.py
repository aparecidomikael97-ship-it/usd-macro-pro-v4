"""Model nowcasts and horizon-mismatched surveys are never CPI release surprise."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_g8_cpi_event_consensus_eligibility_lab import (
    EVENT_CONSENSUS_BLOCKERS,
    inspect_g8_cpi_event_consensus_eligibility_lab as inspect,
)

DOCS = Path(__file__).resolve().parent / "docs" / "continuidade"
FN = {
    "five": "TRADER_G8_OCT2026_FIVE_OFFICIAL_NEXT_CPI_CALENDAR_LAB_20261106.json",
    "three": "TRADER_G8_JPY_CHF_NZD_NEXT_CPI_SCHEDULES_LAB_20261106.json",
    "eurusd": "TRADER_EURUSD_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json",
    "gbpjpy": "TRADER_GBPJPY_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json",
    "other": "TRADER_G8_CHF_AUD_CAD_NZD_20261106_OFFICIAL_ASOF_CASE_LAB.json",
    "oct": "TRADER_US_OCT2026_CLEVELANDFED_FORWARD_NOWCAST_RECEIPT_20261106.json",
    "nov": "TRADER_US_NOV2026_CLEVELANDFED_EARLY_NOWCAST_RECEIPT_20261106.json",
    "surveys": "TRADER_EURUSD_SEP2026_EXPECTATIONS_MISMATCH_LAB_20261106.json",
    "policy": "TRADER_EURUSD_POLICY_DECISIONS_SEPOCT2026_LAB_20261106.json",
    "cpi": "TRADER_EURUSD_SEP2026_OFFICIAL_HEADLINE_CONTEXT_LAB_20261106.json",
}
DATA = {key: (DOCS / name).read_bytes() for key, name in FN.items()}


def at(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


class G8ExactEventConsensusEligibilityTests(unittest.TestCase):
    def case(self, when=at(2026, 11, 7), **override):
        data = {**DATA, **override}
        return inspect(
            five_calendar_casebook_raw=data["five"],
            three_calendar_casebook_raw=data["three"],
            eurusd_macro_casebook_raw=data["eurusd"],
            gbpjpy_macro_casebook_raw=data["gbpjpy"],
            remaining_four_macro_casebook_raw=data["other"],
            october_us_model_receipt_raw=data["oct"],
            november_us_model_receipt_raw=data["nov"],
            survey_expectations_casebook_raw=data["surveys"],
            september_policy_casebook_raw=data["policy"],
            september_cpi_casebook_raw=data["cpi"],
            as_of_utc=when,
        )

    def assert_guard(self, result):
        self.assertEqual(result["exact_pre_event_market_consensus_by_currency"], {})
        self.assertEqual(result["official_cpi_actual_for_upcoming_events"], {})
        self.assertEqual(result["market_surprises"], {})
        self.assertEqual(result["model_forecast_errors"], {})
        self.assertEqual(result["ranked_currencies"], [])
        self.assertIsNone(result["best_pair_of_day"])
        self.assertEqual((result["validated_forward_prediction_count"],
                          result["validated_accuracy"]), (0, None))
        self.assertIsNone(result["fx_bias"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertEqual((result["http_requests"], result["new_cost_brl"]), (0, 0))
        for k in ("can_feed_live_radar", "trade_authorized", "publishable",
                  "worker_enabled", "scheduler_enabled",
                  "point_in_time_document_origins_independently_witnessed"):
            self.assertFalse(result[k], k)
        for row in result["pair_rows"]:
            self.assertEqual((row["D1"], row["W1"]), ("AGUARDAR", "AGUARDAR"))
            self.assertIsNone(row["fx_bias"])
            self.assertIsNone(row["relative_macro_score"])
            self.assertFalse(row["trade_authorized"])
            self.assertIsNone(row["actual_minus_market_consensus_percentage_points"])
            self.assertIsNone(row["model_nowcast_ex_post_error_percentage_points"])
            self.assertEqual(row["market_consensus_for_exact_next_cpi_release_by_role"],
                             {"BASE": None, "QUOTE": None})
            for blocker in EVENT_CONSENSUS_BLOCKERS:
                self.assertIn(blocker, row["missing_prerequisites"])
            for context in row["candidate_expectations_context_by_role"].values():
                for item in context:
                    self.assertFalse(item["qualifies_as_exact_market_event_consensus"])

    def test_28_pairs_2_model_forecasts_2_mismatched_surveys(self):
        r = self.case()
        self.assertEqual(r["state"],
                         "LAB_TWO_MODEL_HORIZONS_TWO_MISMATCHED_SURVEYS_NO_CPI_EVENT_CONSENSUS")
        self.assertEqual((r["pair_count"], r["source_model_forecast_count"],
                          r["source_mismatched_survey_count"]), (28, 2, 2))
        self.assertEqual((r["pairs_with_usd_model_context"],
                          r["pairs_with_eur_survey_context"],
                          r["pairs_with_usd_household_context"],
                          r["pairs_with_either_usd_or_eur_context"],
                          r["pairs_without_either_context"]), (7, 7, 7, 13, 15))
        self.assertEqual({row["pair"] for row in r["pair_rows"]}, set(OFFICIAL_PAIRS))
        self.assert_guard(r)

    def test_eurusd_has_two_model_horizons_one_household_one_analyst_survey(self):
        row = {x["pair"]: x for x in self.case()["pair_rows"]}["EUR/USD"]
        self.assertEqual(len(row["candidate_expectations_context_by_role"]["BASE"]), 1)
        self.assertEqual(len(row["candidate_expectations_context_by_role"]["QUOTE"]), 3)
        self.assertEqual(row["next_cpi_date_for_pair"], "2026-11-10")
        self.assertEqual(row["base_cpi_documentary_reference_period"], "2026-10")
        self.assertEqual(row["quote_cpi_documentary_reference_period"], "2026-09")
        self.assert_guard(self.case())

    def test_usd_forecast_oct_3_74_and_nov_3_88_are_separate_not_consensus(self):
        row = {x["pair"]: x for x in self.case()["pair_rows"]}["USD/JPY"]
        models = row["candidate_expectations_context_by_role"]["BASE"][:2]
        self.assertEqual([(m["target_period"], m["forecast_percent_model_documentary_only"])
                          for m in models], [("2026-10", 3.74), ("2026-11", 3.88)])
        self.assertTrue(all(m["source_kind"].endswith("NOT_CONSENSUS") for m in models))
        self.assertTrue(all(m["source_url"] ==
                            "https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting"
                            for m in models))
        self.assertTrue(all(m["release_window"] == "BEFORE_SCHEDULED_RELEASE" for m in models))
        self.assertEqual(row["candidate_expectations_context_by_role"]["QUOTE"], [])

    def test_usd_household_one_year_expectations_not_next_month_cpi(self):
        row = {x["pair"]: x for x in self.case()["pair_rows"]}["GBP/USD"]
        household = row["candidate_expectations_context_by_role"]["QUOTE"][2]
        self.assertEqual(household["source_kind"],
                         "NYFED_SCE_HOUSEHOLD_ONE_YEAR_NOT_MONTHLY_EVENT_CONSENSUS")
        self.assertEqual(household["target_period"],
                         "ONE_YEAR_AHEAD_FROM_SEPTEMBER_2026")
        self.assertEqual(household["forecast_percent_survey_documentary_only"], 3.9)
        self.assertNotEqual(household["target_period"], "2026-10")

    def test_eur_analyst_quarterly_q3_not_eur_october_hicp_consensus(self):
        row = {x["pair"]: x for x in self.case()["pair_rows"]}["EUR/CHF"]
        sma = row["candidate_expectations_context_by_role"]["BASE"][0]
        self.assertEqual((sma["target_period"], sma["reference_period_type"],
                          sma["forecast_percent_survey_documentary_only"]),
                         ("2026Q3", "QUARTERLY", 3.2))
        self.assertIn("NOT_MONTHLY_EVENT_CONSENSUS", sma["source_kind"])
        self.assertEqual(row["candidate_expectations_context_by_role"]["QUOTE"], [])

    def test_other_15_pairs_do_not_inherit_usd_or_eur_expected_inflation(self):
        r = self.case()
        without = [row for row in r["pair_rows"]
                   if not {"EUR", "USD"}.intersection((row["base"], row["quote"]))]
        self.assertEqual(len(without), 15)
        for row in without:
            self.assertEqual(row["candidate_expectations_context_by_role"],
                             {"BASE": [], "QUOTE": []})
        self.assert_guard(r)

    def test_after_bls_oct_release_time_schedule_does_not_create_actual(self):
        r = self.case(at(2026, 11, 10, 13, 30))
        row = {x["pair"]: x for x in r["pair_rows"]}["USD/JPY"]
        model = row["candidate_expectations_context_by_role"]["BASE"][0]
        self.assertEqual(model["release_window"],
                         "AFTER_SCHEDULED_RELEASE_NO_AUTHENTICATED_ACTUAL")
        self.assertEqual(model["forecast_percent_model_documentary_only"], 3.74)
        self.assert_guard(r)

    def test_after_dec10_both_schedules_pass_without_actual_or_surprise(self):
        r = self.case(at(2026, 12, 10, 13, 30))
        row = {x["pair"]: x for x in r["pair_rows"]}["USD/CHF"]
        for model in row["candidate_expectations_context_by_role"]["BASE"][:2]:
            self.assertEqual(model["release_window"],
                             "AFTER_SCHEDULED_RELEASE_NO_AUTHENTICATED_ACTUAL")
        self.assert_guard(r)

    def test_before_nov7_no_research_context(self):
        for when in (at(2026, 11, 6, 23, 59), at(2026, 10, 20)):
            r = self.case(when)
            self.assertEqual(r["state"], "LAB_CONSENSUS_RESEARCH_NOT_VISIBLE_ASOF")
            self.assertEqual(r["pair_rows"], [])
            self.assert_guard(r)

    def test_naive_time_rejected_and_timezone_equivalence(self):
        local = datetime(2026, 11, 6, 20, tzinfo=timezone(timedelta(hours=-4)))
        self.assertEqual(self.case(local), self.case(at(2026, 11, 7)))
        for when in (None, "2026-11-07", datetime(2026, 11, 7)):
            r = self.case(when)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assertEqual(r["pair_rows"], [])
            self.assert_guard(r)

    def test_every_parent_evidence_receipt_is_required(self):
        for key in DATA:
            r = self.case(**{key: DATA[key] + b" "})
            self.assertEqual(r["state"], "LAB_BLOCKED", key)
            self.assertEqual(r["pair_rows"], [], key)
            self.assert_guard(r)


if __name__ == "__main__":
    unittest.main()
