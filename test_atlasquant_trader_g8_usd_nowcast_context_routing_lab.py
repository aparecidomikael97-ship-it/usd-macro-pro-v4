"""One-currency CPI model context touches 7 USD crosses, never all 28 signals."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_g8_usd_nowcast_context_routing_lab import (
    EXPECTED_USD_PAIRS,
    inspect_g8_usd_nowcast_context_routing_lab as inspect,
)

DOCS = Path(__file__).resolve().parent / "docs" / "continuidade"
OCT = (DOCS / "TRADER_US_OCT2026_CLEVELANDFED_FORWARD_NOWCAST_RECEIPT_20261106.json").read_bytes()
NOV = (DOCS / "TRADER_US_NOV2026_CLEVELANDFED_EARLY_NOWCAST_RECEIPT_20261106.json").read_bytes()
EURUSD = (DOCS / "TRADER_EURUSD_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json").read_bytes()
GBPJPY = (DOCS / "TRADER_GBPJPY_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json").read_bytes()
OTHER = (DOCS / "TRADER_G8_CHF_AUD_CAD_NZD_20261106_OFFICIAL_ASOF_CASE_LAB.json").read_bytes()


def at(month, day, hour=0, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=timezone.utc)


class G8USDModelNowcastContextRoutingTests(unittest.TestCase):
    def case(self, when=at(11, 8), oct_raw=OCT, nov_raw=NOV,
             eurusd=EURUSD, gbpjpy=GBPJPY, other=OTHER):
        return inspect(oct_nowcast_receipt_raw=oct_raw,
                       nov_nowcast_receipt_raw=nov_raw,
                       eurusd_macro_casebook_raw=eurusd,
                       gbpjpy_macro_casebook_raw=gbpjpy,
                       remaining_four_macro_casebook_raw=other,
                       as_of_utc=when)

    def assert_no_fx_strength_or_trade(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["fx_bias"])
        self.assertEqual(result["ranked_currencies"], [])
        self.assertIsNone(result["best_pair_of_day"])
        self.assertEqual(result["relative_macro_comparisons_verified"], 0)
        self.assertEqual(result["eligible_for_fx_bias_count"], 0)
        self.assertEqual(result["validated_forward_prediction_count"], 0)
        self.assertIsNone(result["validated_accuracy"])
        self.assertEqual((result["http_requests"], result["new_cost_brl"]), (0, 0))
        for key in ("can_feed_live_radar", "trade_authorized", "publishable",
                    "worker_enabled", "scheduler_enabled"):
            self.assertFalse(result[key], key)
        for row in result["pair_rows"]:
            self.assertEqual((row["D1"], row["W1"]), ("AGUARDAR", "AGUARDAR"))
            self.assertIsNone(row["currency_strength_score"])
            self.assertIsNone(row["relative_macro_score"])
            self.assertFalse(row["trade_authorized"])
            self.assertFalse(row["matched_other_currency_same_event_consensus"])
            self.assertFalse(row["both_currency_pit_forecasts_and_policy_harmonized"])

    def test_all_28_present_exactly_seven_usd_crosses(self):
        r = self.case()
        self.assertEqual(r["state"], "LAB_USD_DOCUMENTARY_CONTEXT_ROUTED_TO_7_CROSSES_NO_FX_BIAS")
        self.assertEqual((r["pair_count"], r["usd_pair_count"], r["non_usd_pair_count"]),
                         (28, 7, 21))
        self.assertEqual(len(r["pair_rows"]), 28)
        self.assertEqual({x["pair"] for x in r["pair_rows"]}, set(OFFICIAL_PAIRS))
        self.assertEqual({x["pair"] for x in r["pair_rows"] if x["usd_role"] != "NONE"},
                         EXPECTED_USD_PAIRS)
        self.assertEqual(r["usd_crosses_with_visible_context"], 7)
        self.assertEqual(r["non_usd_crosses_with_usd_context"], 0)
        self.assert_no_fx_strength_or_trade(r)

    def test_usd_context_only_on_seven_parents_and_same_two_months(self):
        r = self.case()
        for row in r["pair_rows"]:
            context = row["usd_pre_cpi_model_context_documentary_only"]
            if row["pair"] in EXPECTED_USD_PAIRS:
                self.assertEqual([x["forecast_month"] for x in context], ["2026-10", "2026-11"])
                self.assertEqual([x["model_forecast_yoy_percent"] for x in context], [3.74, 3.88])
                self.assertEqual(row["current_pre_release_usd_forecast_months"],
                                 ["2026-10", "2026-11"])
            else:
                self.assertEqual(context, [])
                self.assertEqual(row["current_pre_release_usd_forecast_months"], [])
        self.assert_no_fx_strength_or_trade(r)

    def test_base_and_quote_usd_role_do_not_flip_into_buy_sell(self):
        rows = {x["pair"]: x for x in self.case()["pair_rows"]}
        self.assertEqual(rows["EUR/USD"]["usd_role"], "QUOTE")
        self.assertEqual(rows["GBP/USD"]["usd_role"], "QUOTE")
        self.assertEqual(rows["USD/JPY"]["usd_role"], "BASE")
        self.assertEqual(rows["USD/CAD"]["usd_role"], "BASE")
        self.assertEqual(rows["EUR/JPY"]["usd_role"], "NONE")
        self.assert_no_fx_strength_or_trade(self.case())

    def test_before_nov7_no_forecast_context_on_any_pair(self):
        for when in (at(10, 31), at(11, 6), at(11, 6, 23, 59)):
            r = self.case(when)
            self.assertEqual(r["state"], "LAB_28_PAIRS_NO_PRE_CPI_FORECAST_VISIBLE_ASOF")
            self.assertEqual(r["source_forecast_months"], [])
            self.assertEqual(r["usd_crosses_with_visible_context"], 0)
            self.assertTrue(all(not x["usd_pre_cpi_model_context_documentary_only"]
                                for x in r["pair_rows"]))
            self.assert_no_fx_strength_or_trade(r)

    def test_oct_release_does_not_relabel_november_as_released(self):
        r = self.case(at(11, 10, 13, 30))
        for row in r["pair_rows"]:
            if row["usd_role"] != "NONE":
                self.assertEqual(row["current_pre_release_usd_forecast_months"], ["2026-11"])
                forecasts = row["usd_pre_cpi_model_context_documentary_only"]
                self.assertEqual(forecasts[0]["release_window"],
                                 "AFTER_SCHEDULED_RELEASE_NO_AUTHENTICATED_ACTUAL")
                self.assertEqual(forecasts[1]["release_window"], "BEFORE_SCHEDULED_RELEASE")
        self.assert_no_fx_strength_or_trade(r)

    def test_both_release_schedules_passed_forecasts_stay_historical_only(self):
        r = self.case(at(12, 11))
        self.assertEqual(r["source_forecast_months"], ["2026-10", "2026-11"])
        self.assertEqual(r["usd_crosses_with_visible_context"], 7)
        for x in r["pair_rows"]:
            self.assertEqual(x["current_pre_release_usd_forecast_months"], [])
        self.assert_no_fx_strength_or_trade(r)

    def test_period_audit_preserved_without_pretending_forecasts_comparable(self):
        rows = {x["pair"]: x for x in self.case()["pair_rows"]}
        self.assertEqual(rows["EUR/USD"]["historical_cpi_period_audit"],
                         "MONTHLY_DIFFERENT_PERIOD")
        self.assertEqual(rows["AUD/NZD"]["historical_cpi_period_audit"],
                         "MONTHLY_VS_QUARTERLY")
        self.assert_no_fx_strength_or_trade(self.case())

    def test_any_modified_source_receipt_blocks_entire_28_pair_route(self):
        for kw in ({"oct_raw": OCT + b" "}, {"nov_raw": NOV + b" "},
                   {"eurusd": EURUSD + b" "}, {"gbpjpy": None},
                   {"other": OTHER + b" "}):
            r = self.case(**kw)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assertEqual(r["pair_rows"], [])
            self.assert_no_fx_strength_or_trade(r)

    def test_invalid_clock_and_timezone_normalization(self):
        for when in (None, "2026-11-08", datetime(2026, 11, 8)):
            r = self.case(when)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assertEqual(r["pair_rows"], [])
        local = datetime(2026, 11, 7, 20, tzinfo=timezone(timedelta(hours=-4)))
        self.assertEqual(self.case(local), self.case(at(11, 8)))


if __name__ == "__main__":
    unittest.main()
