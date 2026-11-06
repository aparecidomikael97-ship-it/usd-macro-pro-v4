"""Two real survey references cannot become September CPI event consensus."""
from datetime import datetime, timezone
from pathlib import Path
import json
import unittest

from atlasquant_trader_eurusd_sep2026_expectations_mismatch_lab import (
    PINNED_EXPECTATIONS_SHA256,
    inspect_eurusd_sep2026_expectations_mismatch_lab as inspect,
)

DOCS = Path(__file__).resolve().parent / "docs" / "continuidade"
SURVEYS = (DOCS / "TRADER_EURUSD_SEP2026_EXPECTATIONS_MISMATCH_LAB_20261106.json").read_bytes()
POLICY = (DOCS / "TRADER_EURUSD_POLICY_DECISIONS_SEPOCT2026_LAB_20261106.json").read_bytes()
CPI = (DOCS / "TRADER_EURUSD_SEP2026_OFFICIAL_HEADLINE_CONTEXT_LAB_20261106.json").read_bytes()
UTC = timezone.utc
NOW = datetime(2026, 11, 6, 19, tzinfo=UTC)


def at(month, day, hour=0, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=UTC)


class SepCpiPreReleaseExpectationsMismatchTests(unittest.TestCase):
    def run_case(self, when=NOW, surveys=SURVEYS, policy=POLICY, cpi=CPI):
        return inspect(surveys, policy_casebook_raw=policy,
                       inflation_casebook_raw=cpi, as_of_utc=when)

    def assert_never_surprise_or_trade(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["validated_forward_prediction_count"], 0)
        self.assertIsNone(r["validated_accuracy"])
        self.assertEqual((r["http_requests"], r["new_cost_brl"]), (0, 0))
        self.assertEqual(r["matched_pre_release_september_cpi_consensus_by_currency"], {})
        self.assertEqual(r["september_cpi_surprise_by_currency"], {})
        for key in ("september_cpi_surprise_verified",
                    "september_policy_decision_sma_aggregate_pre_event",
                    "survey_publication_instant_independently_attested",
                    "survey_original_payload_bytes_archived",
                    "same_target_period_and_measure_confirmed",
                    "forecast_population_same_as_market_release_consensus",
                    "can_feed_live_radar", "trade_authorized", "publishable",
                    "worker_enabled", "scheduler_enabled"):
            self.assertFalse(r[key], key)

    def test_official_survey_numbers_visible_but_not_cpi_release_forecast(self):
        r = self.run_case()
        self.assertEqual(r["state"],
                         "LAB_OFFICIAL_SURVEY_CONTEXT_WITH_RELEASE_CONSENSUS_MISMATCH")
        self.assertEqual(r["expectations_casebook_sha256"], PINNED_EXPECTATIONS_SHA256)
        obs = {v["currency"]: v for v in r[
            "visible_official_survey_context_not_cpi_consensus"]}
        self.assertEqual(obs["EUR"]["median_survey_expectation_percent_not_cpi_event_consensus"], 3.2)
        self.assertEqual(obs["USD"]["median_survey_expectation_percent_not_cpi_event_consensus"], 3.9)
        self.assert_never_surprise_or_trade(r)

    def test_ecb_sma_is_quarterly_target_not_monthly_september_hicp(self):
        r = self.run_case()
        eur = r["visible_official_survey_context_not_cpi_consensus"][0]
        self.assertEqual((eur["currency"], eur["target_period"], eur["target_granularity"]),
                         ("EUR", "2026Q3", "QUARTERLY"))
        self.assertIn("QUARTERLY_HICP", eur["blocked_as_cpi_release_consensus_reason"])
        self.assert_never_surprise_or_trade(r)

    def test_nyfed_household_one_year_ahead_not_us_september_cpi(self):
        r = self.run_case()
        usd = r["visible_official_survey_context_not_cpi_consensus"][1]
        self.assertEqual((usd["currency"], usd["target_granularity"],
                          usd["respondent_population"]),
                         ("USD", "ROLLING_ONE_YEAR_AHEAD", "HOUSEHOLDS"))
        self.assertIn("NOT_SEPTEMBER_2026_US_CPI_U", usd[
            "blocked_as_cpi_release_consensus_reason"])
        self.assert_never_surprise_or_trade(r)

    def test_before_ecb_sma_aggregate_no_survey_visible(self):
        r = self.run_case(at(9, 11, 23, 59))
        self.assertEqual(r["visible_survey_currencies"], [])
        self.assert_never_surprise_or_trade(r)

    def test_sep12_sma_visible_but_not_pre_sep10_ecb_decision(self):
        r = self.run_case(at(9, 12))
        self.assertEqual(r["visible_survey_currencies"], ["EUR"])
        self.assertEqual(r["latest_documentary_cpi_currencies"], [])
        self.assertFalse(r["september_policy_decision_sma_aggregate_pre_event"])
        self.assert_never_surprise_or_trade(r)

    def test_oct7_nyfed_sce_is_not_yet_available_under_conservative_gate(self):
        r = self.run_case(at(10, 7, 23, 59))
        self.assertEqual(r["visible_survey_currencies"], ["EUR"])
        self.assert_never_surprise_or_trade(r)

    def test_oct8_both_surveys_pre_cpi_but_still_mismatched_target(self):
        r = self.run_case(at(10, 8))
        self.assertEqual(r["visible_survey_currencies"], ["EUR", "USD"])
        self.assertEqual(r["latest_documentary_cpi_currencies"], [])
        self.assert_never_surprise_or_trade(r)

    def test_oct15_us_cpi_visible_but_no_fake_3_7_minus_3_9_surprise(self):
        r = self.run_case(at(10, 15))
        self.assertEqual(r["latest_documentary_cpi_currencies"], ["USD"])
        self.assertEqual(r["september_cpi_surprise_by_currency"], {})
        self.assert_never_surprise_or_trade(r)

    def test_oct17_eur_cpi_visible_but_no_fake_3_8_minus_3_2_surprise(self):
        r = self.run_case(at(10, 17))
        self.assertEqual(r["latest_documentary_cpi_currencies"], ["USD", "EUR"])
        self.assertEqual(r["september_cpi_surprise_by_currency"], {})
        self.assert_never_surprise_or_trade(r)

    def test_tamper_any_forecast_source_date_or_unit_fail_closed(self):
        for currency, key, value in (("USD", "median_forecast_percent", 4.9),
                                     ("EUR", "forecast_target_period", "2026-09"),
                                     ("USD", "publication_calendar_date", "2026-10-14"),
                                     ("EUR", "september_2026_monthly_cpi_or_hicp_release_consensus", True)):
            obj = json.loads(SURVEYS)
            for row in obj["records"]:
                if row["currency"] == currency:
                    row[key] = value
            r = self.run_case(surveys=json.dumps(obj).encode())
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_never_surprise_or_trade(r)

    def test_parent_policy_or_inflation_casebook_tamper_blocks(self):
        for kw in ({"policy": POLICY + b" "}, {"cpi": CPI + b" "}):
            r = self.run_case(**kw)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_never_surprise_or_trade(r)

    def test_naive_clock_invalid_payload_and_duplicate_json_fail_closed(self):
        for when in (None, "2026-11-06", datetime(2026, 11, 6)):
            self.assertEqual(self.run_case(when)["state"], "LAB_BLOCKED")
        for data in (None, "str", {}, b"", SURVEYS + b" "):
            self.assertEqual(self.run_case(surveys=data)["state"], "LAB_BLOCKED")
        duplicate = SURVEYS.replace(b'"schema":', b'"schema":"x","schema":', 1)
        self.assertEqual(self.run_case(surveys=duplicate)["state"], "LAB_BLOCKED")


if __name__ == "__main__":
    unittest.main()
