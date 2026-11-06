"""All eight G8 currencies can have next CPI dates without an FX signal."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_g8_eight_next_cpi_schedules_lab import (
    PINNED_NEW_THREE_SHA256,
    inspect_g8_eight_next_cpi_schedules_lab as inspect,
)

DOCS = Path(__file__).resolve().parent / "docs" / "continuidade"
FIVE = (DOCS / "TRADER_G8_OCT2026_FIVE_OFFICIAL_NEXT_CPI_CALENDAR_LAB_20261106.json").read_bytes()
THREE = (DOCS / "TRADER_G8_JPY_CHF_NZD_NEXT_CPI_SCHEDULES_LAB_20261106.json").read_bytes()


def at(y, m, d, h=0, minute=0):
    return datetime(y, m, d, h, minute, tzinfo=timezone.utc)


class FullG8NextCpiCalendarTests(unittest.TestCase):
    def case(self, when=at(2026, 11, 7), five=FIVE, three=THREE):
        return inspect(five_calendar_casebook_raw=five,
                       three_calendar_casebook_raw=three, as_of_utc=when)

    def assert_non_operational(self, report):
        self.assertEqual(report["observed_cpi_actual_by_currency"], {})
        self.assertEqual(report["surprise_to_consensus_by_currency"], {})
        self.assertEqual(report["relative_inflation_spreads"], {})
        self.assertEqual(report["ranked_currencies"], [])
        self.assertIsNone(report["best_pair_of_day"])
        self.assertIsNone(report["fx_bias"])
        self.assertEqual(report["operational_bias"], "AGUARDAR")
        self.assertEqual(report["validated_forward_prediction_count"], 0)
        self.assertIsNone(report["validated_accuracy"])
        self.assertTrue(report["calendar_may_change"])
        self.assertEqual((report["http_requests"], report["new_cost_brl"]), (0, 0))
        for field in ("can_feed_live_radar", "trade_authorized", "publishable",
                      "worker_enabled", "scheduler_enabled", "source_original_bytes_archived",
                      "exact_source_consultation_instant_attested"):
            self.assertFalse(report[field], field)
        for e in report["visible_official_calendar_events"]:
            self.assertIsNone(e["official_actual"])
            self.assertIsNone(e["surprise"])
        for row in report["pair_rows"]:
            self.assertEqual((row["D1"], row["W1"]), ("AGUARDAR", "AGUARDAR"))
            self.assertIsNone(row["currency_strength_score"])
            self.assertIsNone(row["relative_macro_score"])
            self.assertFalse(row["comparable_cpi_reference_periods_verified"])
            self.assertFalse(row["trade_authorized"])

    def test_pinned_new_sources_and_all_eight_currencies(self):
        self.assertEqual(sha256(THREE).hexdigest(), PINNED_NEW_THREE_SHA256)
        report = self.case()
        self.assertEqual(report["state"],
                         "LAB_8_CURRENCIES_28_PAIRS_TWO_CALENDAR_DATES_EACH_NO_FX_BIAS")
        self.assertEqual(report["visible_scheduled_currencies"], sorted(CURRENCIES))
        self.assertEqual((report["source_calendar_count"],
                          report["five_monthly_2026_oct_calendar_events"],
                          report["three_other_period_calendar_events"]), (8, 5, 3))
        self.assertEqual(len(report["visible_official_calendar_events"]), 8)
        self.assert_non_operational(report)

    def test_japan_oct_national_cpi_nov20_and_not_tokyo(self):
        ev = next(e for e in self.case()["visible_official_calendar_events"]
                  if e["currency"] == "JPY")
        self.assertEqual((ev["reference_period"], ev["scheduled_calendar_date"],
                          ev["statistical_frequency"]), ("2026-10", "2026-11-20", "MONTHLY"))
        self.assertEqual(ev["statistical_scope"], "NATIONAL_JAPAN_NOT_PRELIMINARY_TOKYO_CPI")

    def test_swiss_next_release_is_november_not_already_released_october(self):
        ev = next(e for e in self.case()["visible_official_calendar_events"]
                  if e["currency"] == "CHF")
        self.assertEqual((ev["reference_period"], ev["scheduled_calendar_date"]),
                         ("2026-11", "2026-12-02"))
        self.assertEqual(ev["statistical_scope"], "SWISS_NATIONAL_CPI_NOT_HICP")
        self.assertIsNone(ev["official_actual"])

    def test_nzd_december_quarter_not_mislabeled_as_october_monthly(self):
        ev = next(e for e in self.case()["visible_official_calendar_events"]
                  if e["currency"] == "NZD")
        self.assertEqual((ev["reference_period"], ev["reference_period_type"],
                          ev["statistical_frequency"], ev["scheduled_calendar_date"]),
                         ("2026-Q4", "QUARTER", "QUARTERLY", "2027-01-27"))
        self.assertEqual(ev["statistical_scope"],
                         "NEW_ZEALAND_FULL_QUARTERLY_CPI_NOT_MONTHLY_SELECTED_PRICE_INDEX")

    def test_all_28_pairs_have_exactly_2_currency_schedules_and_correct_roles(self):
        report = self.case()
        self.assertEqual((report["pair_count"],
                          report["pairs_with_two_currencies_in_schedule"],
                          report["pairs_with_upcoming_schedule"],
                          report["pairs_without_schedule"]), (28, 28, 28, 0))
        self.assertEqual({r["pair"] for r in report["pair_rows"]}, set(OFFICIAL_PAIRS))
        for row in report["pair_rows"]:
            self.assertEqual(row["calendar_currency_count"], 2)
            self.assertEqual({e["currency"] for e in row["calendar_events"]},
                             {row["base"], row["quote"]})
            for event in row["calendar_events"]:
                self.assertEqual(event["pair_currency_role"],
                                 "BASE" if event["currency"] == row["base"] else "QUOTE")
        self.assert_non_operational(report)

    def test_first_and_next_event_never_mixes_reference_periods(self):
        rows = {r["pair"]: r for r in self.case()["pair_rows"]}
        self.assertEqual(rows["USD/JPY"]["next_calendar_date"], "2026-11-10")
        self.assertEqual(rows["CHF/JPY"]["next_calendar_date"], "2026-11-20")
        self.assertEqual(rows["NZD/CHF"]["next_calendar_date"], "2026-12-02")
        self.assertEqual(rows["NZD/JPY"]["next_calendar_date"], "2026-11-20")
        self.assertEqual({e["reference_period"] for e in rows["NZD/CHF"]["calendar_events"]},
                         {"2026-11", "2026-Q4"})
        self.assert_non_operational(self.case())

    def test_eurgbp_same_day_keeps_both_official_events(self):
        row = {r["pair"]: r for r in self.case()["pair_rows"]}["EUR/GBP"]
        self.assertEqual(row["next_calendar_date"], "2026-11-18")
        self.assertEqual([e["currency"] for e in row["next_calendar_events"]],
                         ["EUR", "GBP"])

    def test_future_date_no_longer_next_but_not_claimed_released(self):
        rows = {r["pair"]: r for r in self.case(at(2026, 11, 21))["pair_rows"]}
        self.assertEqual(rows["CHF/JPY"]["next_calendar_date"], "2026-12-02")
        self.assertEqual(rows["NZD/JPY"]["next_calendar_date"], "2027-01-27")
        rows = {r["pair"]: r for r in self.case(at(2026, 12, 3))["pair_rows"]}
        self.assertIsNone(rows["CHF/JPY"]["next_calendar_date"])
        self.assertEqual(rows["NZD/CHF"]["next_calendar_date"], "2027-01-27")
        self.assert_non_operational(self.case(at(2026, 12, 3)))

    def test_far_future_all_dates_passed_does_not_manufacture_results(self):
        report = self.case(at(2027, 1, 28))
        self.assertEqual(report["pairs_with_two_currencies_in_schedule"], 28)
        self.assertEqual(report["pairs_with_upcoming_schedule"], 0)
        self.assertTrue(all(e["calendar_status"] ==
                            "SCHEDULE_DATE_PASSED_ACTUAL_UNVERIFIED"
                            for e in report["visible_official_calendar_events"]))
        self.assert_non_operational(report)

    def test_before_conservative_research_gate_no_retrospective_leakage(self):
        for when in (at(2026, 11, 6, 23, 59), at(2026, 11, 1), at(2025, 12, 1)):
            report = self.case(when)
            self.assertEqual(report["state"], "LAB_RESEARCH_NOT_VISIBLE_AT_ASOF")
            self.assertEqual(report["visible_official_calendar_events"], [])
            self.assertEqual((report["pairs_with_two_currencies_in_schedule"],
                              report["pairs_without_schedule"]), (0, 28))
            self.assert_non_operational(report)

    def test_timezone_equivalent_and_invalid_clock_fail_closed(self):
        local = datetime(2026, 11, 6, 20, tzinfo=timezone(timedelta(hours=-4)))
        self.assertEqual(self.case(local), self.case(at(2026, 11, 7)))
        for when in (None, "2026-11-07", datetime(2026, 11, 7)):
            report = self.case(when)
            self.assertEqual(report["state"], "LAB_BLOCKED")
            self.assertEqual(report["pair_rows"], [])
            self.assert_non_operational(report)

    def test_tamper_each_source_fails_closed(self):
        for kwargs in ({"five": FIVE + b" "}, {"five": None},
                       {"three": THREE + b" "}, {"three": None},
                       {"three": "not bytes"},
                       {"three": THREE.replace(b"2027-01-27", b"2026-11-27")},
                       {"three": THREE.replace(b'"actual_headline_yoy_percent": null',
                                               b'"actual_headline_yoy_percent": 3.0')}):
            report = self.case(**kwargs)
            self.assertEqual(report["state"], "LAB_BLOCKED")
            self.assertEqual(report["visible_official_calendar_events"], [])
            self.assertEqual(report["pair_rows"], [])
            self.assert_non_operational(report)


if __name__ == "__main__":
    unittest.main()
