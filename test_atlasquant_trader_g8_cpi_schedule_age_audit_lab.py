"""Offline schedule-window tests. No release actual, historical vintage or FX bias."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_g8_cpi_schedule_age_audit_lab import (
    inspect_g8_cpi_schedule_age_audit_lab as inspect,
)
from atlasquant_trader_g8_macro_asof_lab import OBSERVATION_AGE_LIMIT_DAYS

DOCS = Path(__file__).resolve().parent / "docs" / "continuidade"
FIVE = (DOCS / "TRADER_G8_OCT2026_FIVE_OFFICIAL_NEXT_CPI_CALENDAR_LAB_20261106.json").read_bytes()
THREE = (DOCS / "TRADER_G8_JPY_CHF_NZD_NEXT_CPI_SCHEDULES_LAB_20261106.json").read_bytes()
AS_OF = datetime(2026, 11, 8, tzinfo=timezone.utc)


class ScheduleAgeAuditTests(unittest.TestCase):
    def run_audit(self, *, five=FIVE, three=THREE, as_of=AS_OF):
        return inspect(five_calendar_casebook_raw=five,
                       three_calendar_casebook_raw=three, as_of_utc=as_of)

    def assert_no_operational_status(self, report):
        self.assertEqual(report["operational_bias"], "AGUARDAR")
        self.assertIsNone(report["fx_bias"])
        self.assertIsNone(report["directional_accuracy"])
        self.assertEqual((report["http_requests"], report["new_cost_brl"]), (0, 0))
        for key in ("source_calendar_consultation_time_attested",
                    "historical_preceding_cpi_release_attested",
                    "future_release_occurrence_attested", "policy_rate_calendar_validated",
                    "original_point_in_time_vintages_verified", "trade_authorized",
                    "can_feed_live_radar", "publishable", "worker_enabled", "scheduler_enabled"):
            self.assertIs(report[key], False, key)

    def test_eight_calendars_cover_limits_until_day_before_scheduled_release(self):
        report = self.run_audit()
        self.assertEqual(report["state"], "LAB_CPI_SCHEDULE_AGE_CEILINGS_COVER_ALL_EIGHT_UNATTESTED")
        self.assertEqual((report["currencies_checked"], report["pairs_checked"]), (8, 28))
        self.assertEqual(report["currencies_with_insufficient_ceiling"], [])
        self.assertEqual(report["smallest_margin_days"], 7)
        self.assertEqual({r["pair"] for r in report["pair_rows"]}, set(OFFICIAL_PAIRS))
        self.assertTrue(all(r["ceiling_covers_day_before_scheduled_release"]
                            for r in report["currency_rows"]))
        self.assertTrue(all(r["both_ceilings_cover_next_scheduled_cpi"]
                            for r in report["pair_rows"]))
        self.assert_no_operational_status(report)

    def test_new_zealand_quarterly_has_only_seven_day_buffer(self):
        by_currency = {r["currency"]: r for r in self.run_audit()["currency_rows"]}
        nzd = by_currency["NZD"]
        self.assertEqual((nzd["next_scheduled_calendar_date"],
                          nzd["previous_expected_period_end_date"],
                          nzd["statistical_frequency"]),
                         ("2027-01-27", "2026-09-30", "QUARTERLY"))
        self.assertEqual((nzd["previous_period_age_day_before_scheduled_release"],
                          nzd["observation_age_ceiling_days"],
                          nzd["remaining_margin_days"]), (118, 125, 7))

    def test_monthly_periods_do_not_inherit_quarterly_ceiling(self):
        rows = {r["currency"]: r for r in self.run_audit()["currency_rows"]}
        self.assertEqual({r["currency"] for r in rows.values()
                          if r["statistical_frequency"] == "MONTHLY"},
                         {"USD", "CAD", "EUR", "GBP", "AUD", "JPY", "CHF"})
        self.assertTrue(all(r["observation_age_ceiling_days"] == 95
                            for c, r in rows.items() if c != "NZD"))

    def test_smaller_quarterly_ceiling_exposes_schedule_gap_and_stays_no_go(self):
        with patch.dict(OBSERVATION_AGE_LIMIT_DAYS, {("CPI_YOY", "QUARTERLY"): 115}):
            report = self.run_audit()
        self.assertEqual(report["state"], "LAB_CPI_SCHEDULE_AGE_CEILING_REVIEW_REQUIRED")
        self.assertEqual(report["currencies_with_insufficient_ceiling"], ["NZD"])
        self.assertEqual(report["smallest_margin_days"], -3)
        self.assertTrue(any(not row["both_ceilings_cover_next_scheduled_cpi"]
                            for row in report["pair_rows"]))
        self.assert_no_operational_status(report)

    def test_tampered_calendar_or_invalid_asof_refused(self):
        cases = [dict(five=FIVE + b" "), dict(three=THREE + b" "),
                 dict(as_of=datetime(2026, 11, 8)), dict(as_of=None),
                 dict(as_of=datetime(2026, 11, 6, tzinfo=timezone.utc))]
        for kwargs in cases:
            report = self.run_audit(**kwargs)
            self.assertEqual(report["state"], "LAB_BLOCKED")
            self.assertEqual((report["currency_rows"], report["pair_rows"]), ([], []))
            self.assert_no_operational_status(report)

    def test_later_clock_does_not_transform_schedule_into_actual(self):
        report = self.run_audit(as_of=datetime(2027, 2, 1, tzinfo=timezone.utc))
        self.assertEqual(report["state"], "LAB_CPI_SCHEDULE_AGE_CEILINGS_COVER_ALL_EIGHT_UNATTESTED")
        self.assertTrue(all(not row["previous_observation_has_authenticated_actual"]
                            and row["next_event_is_only_calendar_metadata"]
                            for row in report["currency_rows"]))
        self.assert_no_operational_status(report)


if __name__ == "__main__":
    unittest.main()
