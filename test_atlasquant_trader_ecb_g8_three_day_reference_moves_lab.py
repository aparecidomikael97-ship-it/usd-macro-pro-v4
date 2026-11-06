"""Laboratory tests for 3-day manually transcribed official reference values."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_ecb_g8_three_day_reference_moves_lab import (
    REFS, SOURCE_PAGES, build_ecb_g8_three_day_reference_moves_lab as build,
)

NOW = datetime(2026, 11, 5, 5, tzinfo=timezone.utc)


def get(report, symbol):
    return next(x for x in report["pairs"] if x["pair"] == symbol)


class ThreeDayObservedReferenceTests(unittest.TestCase):
    def assert_no_go(self, r):
        for field in ("original_http_bytes_obtained",
                      "publication_instant_attested",
                      "point_in_time_vintage_verified",
                      "independent_broker_m15_price_verified",
                      "executable_bid_ask_verified",
                      "historical_backtest_eligible",
                      "historical_predictive_accuracy_verified",
                      "is_predictive_fx_bias",
                      "trade_authorized",
                      "can_feed_live_radar",
                      "worker_enabled",
                      "scheduler_enabled",
                      "publishable"):
            self.assertIs(r[field], False, field)
        self.assertIsNone(r["original_source_sha256"])
        self.assertIsNone(r["fx_bias"])
        self.assertIsNone(r["currency_strength_rank"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertEqual((r["external_http_requests"], r["new_cost_brl"]), (0, 0))

    def test_fixed_pages_are_three_official_bank_of_italy_dates(self):
        self.assertEqual(list(REFS), ["2026-11-02", "2026-11-03", "2026-11-04"])
        for day in REFS:
            self.assertEqual(SOURCE_PAGES[day],
                "https://www.bancaditalia.it/compiti/operazioni-cambi/cambio/"
                f"cambi_rif_{day.replace('-', '')}/")

    def test_g8_all_currencies_each_day_with_official_transcribed_values(self):
        self.assertTrue(all(set(row) == set(CURRENCIES) for row in REFS.values()))
        self.assertEqual([REFS[d]["USD"] for d in REFS],
                         ["1.1216", "1.1179", "1.1267"])
        self.assertEqual([REFS[d]["JPY"] for d in REFS],
                         ["177.10", "176.95", "178.30"])
        self.assertEqual([REFS[d]["GBP"] for d in REFS],
                         ["0.83580", "0.83358", "0.83460"])
        self.assertEqual([REFS[d]["NZD"] for d in REFS],
                         ["1.9934", "1.9876", "1.9988"])

    def test_28_pairs_three_dates_and_84_retrospective_intervals(self):
        r = build(as_of_utc=NOW)
        self.assertEqual(r["state"], "LAB_ECB_G8_3DAY_OBSERVED_REFERENCE_MOVES_ONLY")
        self.assertEqual((r["currency_count"], r["pair_count"]), (8, 28))
        self.assertEqual(r["reference_observation_count"], 24)
        self.assertEqual(r["observed_interval_count"], 84)
        self.assertEqual({p["pair"] for p in r["pairs"]}, set(OFFICIAL_PAIRS))
        self.assert_no_go(r)

    def test_eur_usd_daily_references_and_observed_signs(self):
        x = get(build(as_of_utc=NOW), "EUR/USD")
        self.assertEqual(x["daily_references"], {
            "2026-11-02": "1.12160000", "2026-11-03": "1.11790000",
            "2026-11-04": "1.12670000"})
        self.assertLess(Decimal(x["observed_reference_moves_percent"][
            "2026-11-02_to_2026-11-03"]), 0)
        self.assertGreater(Decimal(x["observed_reference_moves_percent"][
            "2026-11-03_to_2026-11-04"]), 0)

    def test_eurusd_obs_move_formula_is_change_not_future_predictor(self):
        x = get(build(as_of_utc=NOW), "EUR/USD")
        actual = Decimal(x["observed_reference_moves_percent"][
            "2026-11-02_to_2026-11-04"])
        expected = (Decimal("1.1267") / Decimal("1.1216") - 1) * 100
        self.assertLess(abs(actual - expected), Decimal("0.00005"))
        self.assertTrue(x["moves_are_retrospective_not_predictions"])
        self.assertFalse(x["historical_signal_was_recorded_pre_move"])
        self.assertIsNone(x["fx_bias"])

    def test_usd_jpy_derived_three_times_without_inversion(self):
        x = get(build(as_of_utc=NOW), "USD/JPY")
        for day, row in REFS.items():
            rate = Decimal(x["daily_references"][day])
            expected = Decimal(row["JPY"]) / Decimal(row["USD"])
            self.assertLessEqual(abs(rate - expected), Decimal("0.000000005"))
        self.assertEqual(x["quoted_unit"], "JPY_PER_1_USD")

    def test_gbp_usd_uses_two_eur_based_quotes_not_broker(self):
        x = get(build(as_of_utc=NOW), "GBP/USD")
        for day, row in REFS.items():
            expected = Decimal(row["USD"]) / Decimal(row["GBP"])
            self.assertLessEqual(abs(Decimal(x["daily_references"][day]) - expected),
                                 Decimal("0.000000005"))
        self.assertFalse(x["independent_execution_price_verified"])

    def test_aud_nzd_is_derived_not_observed_directly(self):
        x = get(build(as_of_utc=NOW), "AUD/NZD")
        for day, row in REFS.items():
            expected = Decimal(row["NZD"]) / Decimal(row["AUD"])
            self.assertLessEqual(abs(Decimal(x["daily_references"][day]) - expected),
                                 Decimal("0.000000005"))

    def test_28_pair_arithmetic_correct_on_all_three_days(self):
        r = build(as_of_utc=NOW)
        for p in r["pairs"]:
            for day, row in REFS.items():
                e = Decimal(row[p["quote"]]) / Decimal(row[p["base"]])
                a = Decimal(p["daily_references"][day])
                self.assertLessEqual(abs(a - e), Decimal("0.000000005"))
            self.assertIsNone(p["currency_strength_rank"])
            self.assertEqual((p["D1"], p["W1"]), ("AGUARDAR", "AGUARDAR"))
            self.assertFalse(p["trade_authorized"])

    def test_returns_use_unrounded_base_quote_ratio(self):
        r = build(as_of_utc=NOW)
        for p in r["pairs"]:
            exact = {day: Decimal(row[p["quote"]]) / Decimal(row[p["base"]])
                     for day, row in REFS.items()}
            for first, last in (("2026-11-02", "2026-11-03"),
                                ("2026-11-03", "2026-11-04"),
                                ("2026-11-02", "2026-11-04")):
                change = (exact[last] / exact[first] - 1) * 100
                reported = Decimal(p["observed_reference_moves_percent"][
                    f"{first}_to_{last}"])
                self.assertLessEqual(abs(change - reported), Decimal("0.00005"))

    def test_no_percent_move_is_a_directional_signal(self):
        r = build(as_of_utc=NOW)
        for p in r["pairs"]:
            self.assertIsNone(p["fx_bias"])
            self.assertFalse(p["historical_signal_was_recorded_pre_move"])
            self.assertTrue(p["moves_are_retrospective_not_predictions"])
        self.assert_no_go(r)

    def test_missing_or_naive_asof_denied(self):
        for x in (None, "", 42, {}, datetime(2026, 11, 5)):
            r = build(as_of_utc=x)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_go(r)

    def test_asof_before_next_day_denied(self):
        for x in (datetime(2026,11,4,23,59,tzinfo=timezone.utc),
                  datetime(2026,11,2,11,tzinfo=timezone.utc)):
            r = build(as_of_utc=x)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assertEqual(r["pair_count"], 0)
            self.assert_no_go(r)

    def test_asof_at_next_day_is_still_not_release_proof(self):
        r = build(as_of_utc=datetime(2026,11,5,tzinfo=timezone.utc))
        self.assertEqual(r["state"], "LAB_ECB_G8_3DAY_OBSERVED_REFERENCE_MOVES_ONLY")
        self.assert_no_go(r)

    def test_utc_offset_is_normalized(self):
        r = build(as_of_utc=datetime(2026,11,5,1,tzinfo=timezone(timedelta(hours=-4))))
        self.assertEqual(r["research_as_of_utc"], NOW.isoformat())

    def test_2_to_4_is_not_falsely_summed_daily_returns(self):
        x = get(build(as_of_utc=NOW), "EUR/USD")
        changes = x["observed_reference_moves_percent"]
        total = Decimal(changes["2026-11-02_to_2026-11-04"])
        additive = (Decimal(changes["2026-11-02_to_2026-11-03"])
                    + Decimal(changes["2026-11-03_to_2026-11-04"]))
        self.assertNotEqual(total, additive)

    def test_repeated_build_is_deterministic_no_http(self):
        a = build(as_of_utc=NOW)
        b = build(as_of_utc=NOW)
        self.assertEqual(a, b)
        self.assert_no_go(a)


if __name__ == "__main__":
    unittest.main()
