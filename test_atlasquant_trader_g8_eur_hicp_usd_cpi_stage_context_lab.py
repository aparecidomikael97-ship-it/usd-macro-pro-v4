"""CPI USD model and EUR HICP flash cannot be called a comparable FX spread."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_g8_eur_hicp_usd_cpi_stage_context_lab import (
    EXPECTED_EUR_PAIRS,
    inspect_g8_eur_hicp_usd_cpi_stage_context_lab as inspect,
)

DOCS = Path(__file__).resolve().parent / "docs" / "continuidade"
OCT = (DOCS / "TRADER_US_OCT2026_CLEVELANDFED_FORWARD_NOWCAST_RECEIPT_20261106.json").read_bytes()
NOV = (DOCS / "TRADER_US_NOV2026_CLEVELANDFED_EARLY_NOWCAST_RECEIPT_20261106.json").read_bytes()
EURUSD = (DOCS / "TRADER_EURUSD_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json").read_bytes()
GBPJPY = (DOCS / "TRADER_GBPJPY_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json").read_bytes()
OTHER = (DOCS / "TRADER_G8_CHF_AUD_CAD_NZD_20261106_OFFICIAL_ASOF_CASE_LAB.json").read_bytes()


def at(month, day, hour=0, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=timezone.utc)


class G8EURFlashUSDModelStageTests(unittest.TestCase):
    def case(self, when=at(11, 8), oct_raw=OCT, nov_raw=NOV,
             eurusd=EURUSD, gbpjpy=GBPJPY, other=OTHER):
        return inspect(oct_us_nowcast_raw=oct_raw, nov_us_nowcast_raw=nov_raw,
                       eurusd_macro_casebook_raw=eurusd,
                       gbpjpy_macro_casebook_raw=gbpjpy,
                       remaining_four_macro_casebook_raw=other,
                       as_of_utc=when)

    def assert_no_macro_spread_or_direction(self, r):
        self.assertIsNone(r["eu_us_inflation_spread_pp"])
        self.assertIsNone(r["relative_eur_usd_strength"])
        self.assertEqual(r["methodologically_comparable_two_currency_events"], 0)
        self.assertEqual(r["verified_market_surprise_by_currency"], {})
        self.assertEqual(r["ranked_currencies"], [])
        self.assertIsNone(r["best_pair_of_day"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["validated_forward_prediction_count"], 0)
        self.assertIsNone(r["validated_accuracy"])
        self.assertEqual((r["http_requests"], r["new_cost_brl"]), (0, 0))
        for key in ("can_feed_live_radar", "trade_authorized", "publishable",
                    "worker_enabled", "scheduler_enabled"):
            self.assertFalse(r[key], key)
        for row in r["pair_rows"]:
            self.assertEqual((row["D1"], row["W1"]), ("AGUARDAR", "AGUARDAR"))
            self.assertIsNone(row["currency_strength_score"])
            self.assertFalse(row["can_subtract_two_percentages_as_macro_spread"])
            self.assertFalse(row["comparability_approved"])
            self.assertFalse(row["trade_authorized"])

    def test_exact_7_eur_7_usd_1_overlap_13_union_15_neither(self):
        r = self.case()
        self.assertEqual(r["state"], "LAB_TWO_CURRENCY_OCTOBER_DIFFERENT_STAGE_CONTEXT_NO_BIAS")
        self.assertEqual((r["pair_count"], r["eur_pair_count"], r["usd_pair_count"]),
                         (28, 7, 7))
        self.assertEqual((r["eur_crosses_with_flash_context"],
                          r["usd_crosses_with_model_context"],
                          r["two_sided_eur_usd_context_pairs"],
                          r["crosses_with_either_context"],
                          r["crosses_without_either_context"]), (7, 7, 1, 13, 15))
        self.assertEqual(len(r["pair_rows"]), 28)
        self.assertEqual({p["pair"] for p in r["pair_rows"]}, set(OFFICIAL_PAIRS))
        self.assert_no_macro_spread_or_direction(r)

    def test_eur_flash_only_on_seven_eur_pairs_and_not_other_twenty_one(self):
        r = self.case()
        self.assertEqual({p["pair"] for p in r["pair_rows"]
                          if p["eur_hicp_flash_context"] is not None}, EXPECTED_EUR_PAIRS)
        for row in r["pair_rows"]:
            if row["pair"] in EXPECTED_EUR_PAIRS:
                self.assertEqual(row["eur_hicp_flash_context"]["estimated_headline_yoy_percent"], 4.0)
                self.assertEqual(row["eur_hicp_flash_context"]["source"],
                                 "EUROSTAT_EA21_HICP_FLASH_NOT_FINAL")
                self.assertEqual(row["eur_hicp_flash_context"]["reference_month"], "2026-10")
                self.assertEqual(row["eur_hicp_flash_context"]["full_release_scheduled_calendar_date"],
                                 "2026-11-18")
            else:
                self.assertIsNone(row["eur_hicp_flash_context"])
        self.assert_no_macro_spread_or_direction(r)

    def test_eurusd_two_sides_same_month_but_different_measure_and_stage(self):
        r = self.case()
        eurusd = {row["pair"]: row for row in r["pair_rows"]}["EUR/USD"]
        self.assertTrue(eurusd["both_sides_show_oct2026_but_different_statistical_stage"])
        self.assertEqual(eurusd["eur_role"], "BASE")
        self.assertEqual(eurusd["usd_role"], "QUOTE")
        self.assertEqual(eurusd["eur_hicp_flash_context"]["estimated_headline_yoy_percent"], 4.0)
        self.assertEqual(eurusd["usd_cpi_model_context"][0]["model_forecast_yoy_percent"], 3.74)
        self.assertFalse(eurusd["can_subtract_two_percentages_as_macro_spread"])
        self.assert_no_macro_spread_or_direction(r)

    def test_usd_jpy_eur_jpy_and_gbp_jpy_keep_provenance_separate(self):
        rows = {r["pair"]: r for r in self.case()["pair_rows"]}
        self.assertIsNone(rows["USD/JPY"]["eur_hicp_flash_context"])
        self.assertTrue(rows["USD/JPY"]["usd_cpi_model_context"])
        self.assertIsNotNone(rows["EUR/JPY"]["eur_hicp_flash_context"])
        self.assertEqual(rows["EUR/JPY"]["usd_cpi_model_context"], [])
        self.assertIsNone(rows["GBP/JPY"]["eur_hicp_flash_context"])
        self.assertEqual(rows["GBP/JPY"]["usd_cpi_model_context"], [])
        self.assert_no_macro_spread_or_direction(self.case())

    def test_before_eurostat_flash_and_usd_forecasts_no_context(self):
        r = self.case(at(11, 4, 23, 59))
        self.assertEqual((r["eur_crosses_with_flash_context"],
                          r["usd_crosses_with_model_context"]), (0, 0))
        self.assertEqual(r["crosses_with_either_context"], 0)
        self.assert_no_macro_spread_or_direction(r)

    def test_after_eurostat_flash_before_us_forecast_only_eur_seven(self):
        r = self.case(at(11, 5))
        self.assertEqual(r["state"], "LAB_PARTIAL_EUR_USD_DOCUMENTARY_CONTEXT_NO_BIAS")
        self.assertEqual((r["eur_crosses_with_flash_context"],
                          r["usd_crosses_with_model_context"],
                          r["crosses_with_either_context"]), (7, 0, 7))
        self.assert_no_macro_spread_or_direction(r)

    def test_after_nov10_and_nov18_never_invent_actual_or_change_to_final(self):
        for when in (at(11, 10, 13, 30), at(11, 18), at(12, 11)):
            r = self.case(when)
            self.assertEqual(r["two_sided_eur_usd_context_pairs"], 1)
            eurusd = {row["pair"]: row for row in r["pair_rows"]}["EUR/USD"]
            self.assertEqual(eurusd["eur_hicp_flash_context"]["source"],
                             "EUROSTAT_EA21_HICP_FLASH_NOT_FINAL")
            self.assert_no_macro_spread_or_direction(r)

    def test_tamper_eur_or_usd_or_other_macro_receipts_blocks(self):
        for kw in ({"oct_raw": OCT + b" "}, {"nov_raw": NOV + b" "},
                   {"eurusd": EURUSD + b" "}, {"gbpjpy": None},
                   {"other": OTHER + b" "}):
            r = self.case(**kw)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assertEqual(r["pair_rows"], [])
            self.assert_no_macro_spread_or_direction(r)

    def test_naive_time_rejected_and_timezone_equivalent(self):
        for when in (None, "2026-11-08", datetime(2026, 11, 8)):
            r = self.case(when)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assertEqual(r["pair_rows"], [])
        local = datetime(2026, 11, 7, 20, tzinfo=timezone(timedelta(hours=-4)))
        self.assertEqual(self.case(local), self.case(at(11, 8)))


if __name__ == "__main__":
    unittest.main()
