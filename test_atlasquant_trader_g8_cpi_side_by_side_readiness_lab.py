"""Side-by-side documentary CPI claims must not turn into D1/W1 trades."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_g8_cpi_side_by_side_readiness_lab import (
    ALWAYS_MISSING_GATES,
    inspect_g8_cpi_side_by_side_readiness_lab as inspect,
)

DOCS = Path(__file__).resolve().parent / "docs" / "continuidade"
FIVE = (DOCS / "TRADER_G8_OCT2026_FIVE_OFFICIAL_NEXT_CPI_CALENDAR_LAB_20261106.json").read_bytes()
THREE = (DOCS / "TRADER_G8_JPY_CHF_NZD_NEXT_CPI_SCHEDULES_LAB_20261106.json").read_bytes()
EURUSD = (DOCS / "TRADER_EURUSD_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json").read_bytes()
GBPJPY = (DOCS / "TRADER_GBPJPY_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json").read_bytes()
OTHER = (DOCS / "TRADER_G8_CHF_AUD_CAD_NZD_20261106_OFFICIAL_ASOF_CASE_LAB.json").read_bytes()


def at(y, m, d, hh=0, minute=0):
    return datetime(y, m, d, hh, minute, tzinfo=timezone.utc)


class G8CPIDocumentaryReadinessTests(unittest.TestCase):
    def case(self, when=at(2026, 11, 7), five=FIVE, three=THREE,
             eurusd=EURUSD, gbpjpy=GBPJPY, other=OTHER):
        return inspect(five_calendar_casebook_raw=five,
                       three_calendar_casebook_raw=three,
                       eurusd_macro_casebook_raw=eurusd,
                       gbpjpy_macro_casebook_raw=gbpjpy,
                       remaining_four_macro_casebook_raw=other,
                       as_of_utc=when)

    def assert_guard(self, r):
        self.assertEqual(r["ranked_currencies"], [])
        self.assertIsNone(r["best_pair_of_day"])
        self.assertEqual(r["market_surprises"], {})
        self.assertEqual(r["tradable_relative_cpi_spreads"], {})
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertEqual((r["validated_forward_prediction_count"],
                          r["validated_accuracy"]), (0, None))
        self.assertEqual((r["http_requests"], r["new_cost_brl"]), (0, 0))
        for key in ("can_feed_live_radar", "trade_authorized", "publishable",
                    "worker_enabled", "scheduler_enabled",
                    "source_original_bytes_independently_attested",
                    "historical_point_in_time_vintages_attested",
                    "pre_event_consensus_attested",
                    "cross_country_methods_harmonized"):
            self.assertFalse(r[key], key)
        for row in r["pair_rows"]:
            self.assertEqual((row["D1"], row["W1"]), ("AGUARDAR", "AGUARDAR"))
            self.assertFalse(row["can_compute_cross_currency_inflation_spread"])
            self.assertIsNone(row["currency_strength_score"])
            self.assertIsNone(row["fx_bias"])
            self.assertFalse(row["trade_authorized"])
            for blocker in ALWAYS_MISSING_GATES:
                self.assertIn(blocker, row["missing_prerequisites"])
            for side in ("base_last_documentary_cpi", "quote_last_documentary_cpi"):
                self.assertIsInstance(row[side]["annual_rate_percent_as_source_page_text_only"], str)
                self.assertFalse(row[side]["historical_point_in_time_attested"])
                self.assertFalse(row[side]["original_source_response_archived"])

    def test_28_rows_16_macro_docs_8_next_events_partition_11_10_7(self):
        r = self.case()
        self.assertEqual(r["state"],
                         "LAB_28_PAIRS_WITH_TWO_SIDED_CPI_DOCUMENTS_AND_NEXT_EVENTS_NO_BIAS")
        self.assertEqual((r["documented_currencies"], r["source_page_references"],
                          r["calendar_event_references"], r["pair_count"]), (8, 16, 8, 28))
        self.assertEqual((r["monthly_same_period_pair_count"],
                          r["monthly_different_period_pair_count"],
                          r["monthly_vs_quarterly_pair_count"]), (11, 10, 7))
        self.assertEqual({x["pair"] for x in r["pair_rows"]}, set(OFFICIAL_PAIRS))
        self.assert_guard(r)

    def test_each_pair_display_has_base_quote_cpi_and_two_calendar_events(self):
        r = self.case()
        for row in r["pair_rows"]:
            self.assertEqual(row["base_last_documentary_cpi"]["currency"], row["base"])
            self.assertEqual(row["quote_last_documentary_cpi"]["currency"], row["quote"])
            self.assertEqual(len(row["all_calendar_events_in_this_snapshot"]), 2)
            self.assertEqual({e["currency"] for e in row["all_calendar_events_in_this_snapshot"]},
                             {row["base"], row["quote"]})
            self.assertTrue(row["base_policy_document_reference_present"])
            self.assertTrue(row["quote_policy_document_reference_present"])
        self.assert_guard(r)

    def test_eurusd_different_months_and_eur_flash_not_a_spread(self):
        row = {r["pair"]: r for r in self.case()["pair_rows"]}["EUR/USD"]
        self.assertEqual(row["inflation_reference_period_audit"], "MONTHLY_DIFFERENT_PERIOD")
        self.assertEqual(row["base_last_documentary_cpi"]["reference_period"], "2026-10")
        self.assertEqual(row["base_last_documentary_cpi"]["annual_rate_percent_as_source_page_text_only"], "4.0")
        self.assertTrue(row["base_last_documentary_cpi"]["is_provisional_flash_estimate"])
        self.assertEqual(row["quote_last_documentary_cpi"]["reference_period"], "2026-09")
        self.assertEqual(row["quote_last_documentary_cpi"]["annual_rate_percent_as_source_page_text_only"], "3.7")
        self.assertEqual(row["next_cpi_date_for_pair"], "2026-11-10")
        self.assertIn("DIFFERENT_CPI_REFERENCE_MONTHS", row["missing_prerequisites"])
        self.assertFalse(row["can_compute_cross_currency_inflation_spread"])

    def test_eurchf_same_month_flash_vs_swiss_national_not_comparable(self):
        row = {r["pair"]: r for r in self.case()["pair_rows"]}["EUR/CHF"]
        self.assertEqual(row["inflation_reference_period_audit"],
                         "MONTHLY_SAME_PERIOD_DOCUMENT_ONLY")
        self.assertEqual(row["base_last_documentary_cpi"]["reference_period"], "2026-10")
        self.assertEqual(row["quote_last_documentary_cpi"]["reference_period"], "2026-10")
        self.assertEqual(row["quote_last_documentary_cpi"]["annual_rate_percent_as_source_page_text_only"], "1.5")
        self.assertEqual(row["quote_last_documentary_cpi"]["measurement_kind"],
                         "SWISS_NATIONAL_CPI_MONTHLY_AND_ANNUAL_DEC2025_BASE")
        self.assertTrue(row["base_last_documentary_cpi"]["is_provisional_flash_estimate"])
        self.assertIn("MATCHING_MONTH_DOES_NOT_HARMONIZE_CPI", row["missing_prerequisites"])
        self.assertEqual(row["next_cpi_date_for_pair"], "2026-11-18")

    def test_gbpjpy_both_september_still_no_validated_direction(self):
        row = {r["pair"]: r for r in self.case()["pair_rows"]}["GBP/JPY"]
        self.assertEqual(row["inflation_reference_period_audit"],
                         "MONTHLY_SAME_PERIOD_DOCUMENT_ONLY")
        self.assertEqual(row["base_last_documentary_cpi"]["annual_rate_percent_as_source_page_text_only"], "3.5")
        self.assertEqual(row["quote_last_documentary_cpi"]["annual_rate_percent_as_source_page_text_only"], "2.1")
        self.assertEqual(row["next_cpi_date_for_pair"], "2026-11-18")
        self.assertFalse(row["can_compute_cross_currency_inflation_spread"])

    def test_audcad_same_month_no_implicit_4_3_minus_3_1(self):
        row = {r["pair"]: r for r in self.case()["pair_rows"]}["AUD/CAD"]
        self.assertEqual(row["inflation_reference_period_audit"],
                         "MONTHLY_SAME_PERIOD_DOCUMENT_ONLY")
        self.assertEqual(row["base_last_documentary_cpi"]["annual_rate_percent_as_source_page_text_only"], "4.3")
        self.assertEqual(row["quote_last_documentary_cpi"]["annual_rate_percent_as_source_page_text_only"], "3.1")
        self.assertEqual(row["next_cpi_date_for_pair"], "2026-11-16")
        self.assert_guard(self.case())

    def test_nzdchf_quarter_vs_month_never_fake_monthly_cpi(self):
        row = {r["pair"]: r for r in self.case()["pair_rows"]}["NZD/CHF"]
        self.assertEqual(row["inflation_reference_period_audit"], "MONTHLY_VS_QUARTERLY")
        self.assertEqual(row["base_last_documentary_cpi"]["reference_period"], "2026-Q3")
        self.assertEqual(row["base_last_documentary_cpi"]["frequency"], "QUARTERLY")
        self.assertEqual(row["quote_last_documentary_cpi"]["reference_period"], "2026-10")
        self.assertEqual(row["quote_last_documentary_cpi"]["frequency"], "MONTHLY")
        self.assertEqual(row["next_cpi_date_for_pair"], "2026-12-02")
        self.assertIn("QUARTERLY_VS_MONTHLY_CPI_FREQ_MISMATCH",
                      row["missing_prerequisites"])

    def test_eurgbp_two_next_events_same_date_not_collapsed(self):
        row = {r["pair"]: r for r in self.case()["pair_rows"]}["EUR/GBP"]
        self.assertEqual(row["next_cpi_date_for_pair"], "2026-11-18")
        self.assertEqual([e["currency"] for e in row["next_cpi_events"]],
                         ["EUR", "GBP"])

    def test_future_date_passes_without_filling_cpi_or_price_backtest(self):
        r = self.case(at(2027, 2, 2))
        self.assertEqual(r["pair_count"], 28)
        self.assertTrue(all(x["next_cpi_date_for_pair"] is None for x in r["pair_rows"]))
        self.assert_guard(r)

    def test_research_join_never_visible_before_nov7(self):
        for when in (at(2026, 11, 6, 23, 59), at(2026, 11, 1), at(2026, 10, 20)):
            r = self.case(when)
            self.assertEqual(r["state"], "LAB_JOIN_NOT_ADMISSIBLE_ASOF")
            self.assertEqual(r["pair_rows"], [])
            self.assert_guard(r)

    def test_naive_clock_rejected_and_timezone_equivalent(self):
        local = datetime(2026, 11, 6, 20, tzinfo=timezone(timedelta(hours=-4)))
        self.assertEqual(self.case(local), self.case(at(2026, 11, 7)))
        for when in (None, "2026-11-07", datetime(2026, 11, 7)):
            r = self.case(when)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assertEqual(r["pair_rows"], [])
            self.assert_guard(r)

    def test_tampered_or_missing_source_casebook_fails_closed(self):
        for kwargs in ({"five": FIVE + b" "}, {"three": THREE + b" "},
                       {"eurusd": EURUSD + b" "}, {"gbpjpy": GBPJPY + b" "},
                       {"other": OTHER + b" "}, {"other": None}):
            r = self.case(**kwargs)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assertEqual(r["pair_rows"], [])
            self.assert_guard(r)


if __name__ == "__main__":
    unittest.main()
