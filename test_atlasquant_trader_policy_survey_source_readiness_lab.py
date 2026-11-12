"""Only official-source taxonomy checks, never live rate or trading tests."""
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_policy_survey_source_readiness_lab import (
    RESEARCH_VISIBLE_FROM_UTC, SOURCES,
    inspect_policy_survey_sources_lab as inspect,
)

UTC = timezone.utc


class PolicySurveySourceReadinessTests(unittest.TestCase):
    def assert_no_market_or_trade(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["fx_bias"])
        self.assertIsNone(r["calibrated_direction_probability"])
        for field in (
            "publisher_bytes_independently_archived",
            "exact_publication_instants_independently_verified",
            "historical_point_in_time_access_attested",
            "market_ois_quotes_independently_authenticated",
            "survey_values_are_tradable_market_quotes",
            "intraday_three_updates_supported",
            "survey_can_feed_three_month_ois_vintages",
            "trade_authorized", "publishable", "scheduler_enabled",
        ):
            self.assertFalse(r[field], field)
        self.assertEqual((r["http_requests"], r["file_writes"], r["new_cost_brl"]), (0, 0, 0))

    def test_all_eight_currencies_and_28_pairs_are_catalogued_without_live_quotes(self):
        r = inspect(as_of_utc=RESEARCH_VISIBLE_FROM_UTC)
        self.assertEqual(r["state"], "LAB_SURVEY_SOURCE_TYPES_CATALOGUED_NOT_OIS")
        self.assertEqual((r["currency_count"], r["pair_count"]), (8, 28))
        self.assertEqual({x["currency"] for x in r["currency_rows"]}, set(CURRENCIES))
        self.assertEqual({x["pair"] for x in r["pair_rows"]}, set(OFFICIAL_PAIRS))
        self.assertTrue(all(not x["market_rate_expectation_pair_comparable"]
                            and (x["D1"], x["W1"]) == ("AGUARDAR", "AGUARDAR")
                            and not x["trade_authorized"] for x in r["pair_rows"]))
        self.assert_no_market_or_trade(r)

    def test_date_level_source_claims_are_not_exact_release_instants(self):
        r = inspect(as_of_utc=RESEARCH_VISIBLE_FROM_UTC)
        rows = {x["currency"]: x for x in r["currency_rows"]}
        self.assertEqual(r["survey_context_calendar_dates_researched"], 3)
        self.assertEqual(rows["CAD"]["published_calendar_day_research"], "2026-11-09")
        self.assertEqual(rows["CAD"]["conservative_calendar_publication_floor_utc"],
                         "2026-11-10T00:00:00+00:00")
        self.assertEqual(rows["EUR"]["published_calendar_day_research"], "2026-10-30")
        self.assertEqual(rows["NZD"]["published_calendar_day_research"], "2026-08-13")
        self.assertTrue(all(not x["exact_publication_instant_attested"]
                            and not x["can_feed_ois_quote_deltas"] for x in r["currency_rows"]))
        self.assert_no_market_or_trade(r)

    def test_survey_collection_period_never_backdates_public_visibility(self):
        # BoC Q3 responses closed in October; the web results are dated 9 Nov.
        historic = inspect(as_of_utc=datetime(2026, 10, 1, tzinfo=UTC))
        self.assertEqual(historic["state"], "LAB_RESEARCH_NOT_VISIBLE_AS_OF")
        self.assertEqual(historic["pair_rows"], [])
        self.assert_no_market_or_trade(historic)

    def test_research_itself_is_not_backdated_to_earlier_decisions(self):
        historic = inspect(as_of_utc=RESEARCH_VISIBLE_FROM_UTC - timedelta(seconds=1))
        self.assertEqual(historic["state"], "LAB_RESEARCH_NOT_VISIBLE_AS_OF")
        self.assertEqual((historic["currency_count"], historic["pair_count"]), (0, 0))
        self.assert_no_market_or_trade(historic)

    def test_all_source_kinds_are_non_ois_and_two_issuers_still_unverified(self):
        self.assertEqual(set(SOURCES), set(CURRENCIES))
        self.assertIsNone(SOURCES["JPY"].publisher_url)
        self.assertIsNone(SOURCES["CHF"].publisher_url)
        self.assertEqual(SOURCES["AUD"].source_kind, "RBA_FINANCIAL_CONDITIONS_COMMENTARY")
        self.assertEqual(SOURCES["USD"].cadence_class, "FOMC_RELATED_POST_MEETING_RESULT_LAG")
        self.assert_no_market_or_trade(inspect(as_of_utc=RESEARCH_VISIBLE_FROM_UTC))

    def test_aware_clock_equivalent_time_zone_is_supported(self):
        shifted = RESEARCH_VISIBLE_FROM_UTC.astimezone(timezone(timedelta(hours=-4)))
        self.assertEqual(inspect(as_of_utc=shifted),
                         inspect(as_of_utc=RESEARCH_VISIBLE_FROM_UTC))

    def test_invalid_clocks_are_rejected_without_releasing_pair_evidence(self):
        for invalid in (None, "2026-11-11", datetime(2026, 11, 11), [], 0):
            with self.subTest(invalid=invalid):
                r = inspect(as_of_utc=invalid)
                self.assertEqual(r["state"], "LAB_INVALID_AS_OF")
                self.assertEqual((r["currency_count"], r["pair_count"]), (0, 0))
                self.assert_no_market_or_trade(r)

    def test_far_future_clock_cannot_upgrade_survey_to_live_rate_quote(self):
        r = inspect(as_of_utc=datetime(2030, 1, 1, tzinfo=UTC))
        self.assertEqual(r["pair_count"], 28)
        self.assertFalse(r["market_ois_quotes_independently_authenticated"])
        self.assertFalse(r["survey_can_feed_three_month_ois_vintages"])
        self.assert_no_market_or_trade(r)


if __name__ == "__main__":
    unittest.main()
