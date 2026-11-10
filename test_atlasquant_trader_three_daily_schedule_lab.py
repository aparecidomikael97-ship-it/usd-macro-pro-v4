"""Three daily BRT/Cuiabá/New York refresh schedule regression tests."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import unittest
from zoneinfo import ZoneInfo

from atlasquant_trader_three_daily_schedule_lab import (
    CalendarEventClaim, plan_three_daily_refreshes_lab as plan,
)


class TraderThreeDailyScheduleLabTests(unittest.TestCase):
    def plan(self, day=date(2026, 11, 10), events=()):
        return plan(reference_date_brt=day, calendar_events=events)

    def assert_no_bias_or_cost(self, r):
        self.assertFalse(r["refresh_jobs_actually_scheduled"])
        self.assertFalse(r["calendar_events_independently_authenticated"])
        self.assertFalse(r["new_bias_emitted"])
        self.assertFalse(r["can_feed_live_radar"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["news_fetched"])
        self.assertFalse(r["macro_data_fetched"])
        self.assertEqual(r["http_requests"], 0)
        self.assertEqual(r["file_writes"], 0)
        self.assertEqual(r["new_cost_brl"], 0)
        self.assertIsNone(r["calibrated_probability"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")

    def test_three_planned_windows_november(self):
        r = self.plan()
        self.assertEqual(r["state"], "LAB_THREE_DAILY_BRT_REFRESH_PLAN_ONLY_NO_GO")
        self.assertEqual(r["daily_master_refresh_count"], 3)
        self.assertEqual([v["refresh_window"] for v in r["planned_slots"]],
                         ["MORNING", "MIDDAY", "AFTERNOON"])
        self.assertEqual([v["scheduled_brt"][11:16] for v in r["planned_slots"]],
                         ["06:35", "10:45", "17:15"])
        self.assert_no_bias_or_cost(r)

    def test_brt_is_one_hour_ahead_of_cuiaba_in_november_2026(self):
        r = self.plan()
        self.assertEqual(r["planned_slots"][0]["scheduled_brt"],
                         "2026-11-10T06:35:00-03:00")
        self.assertEqual(r["planned_slots"][0]["scheduled_cuiaba_local"],
                         "2026-11-10T05:35:00-04:00")
        self.assertEqual(r["planned_slots"][0]["scheduled_utc"],
                         "2026-11-10T09:35:00+00:00")

    def test_ny_standard_time_in_november(self):
        r = self.plan()
        self.assertEqual(r["planned_slots"][0]["scheduled_new_york_local"],
                         "2026-11-10T04:35:00-05:00")

    def test_ny_daylight_time_in_july_without_manual_fixed_offset(self):
        r = self.plan(date(2026, 7, 10))
        self.assertEqual(r["planned_slots"][0]["scheduled_new_york_local"],
                         "2026-07-10T05:35:00-04:00")
        self.assertEqual(r["planned_slots"][0]["scheduled_brt"],
                         "2026-07-10T06:35:00-03:00")
        self.assertEqual(r["planned_slots"][0]["scheduled_cuiaba_local"],
                         "2026-07-10T05:35:00-04:00")

    def test_ny_dst_change_is_respected_march_2026(self):
        before = self.plan(date(2026, 3, 7))["planned_slots"][0]
        after = self.plan(date(2026, 3, 9))["planned_slots"][0]
        self.assertEqual(before["scheduled_new_york_local"][11:16], "04:35")
        self.assertEqual(after["scheduled_new_york_local"][11:16], "05:35")

    def test_0640_indicator_check_is_separate_from_three_refreshes(self):
        r = self.plan()
        self.assertEqual(r["indicator_age_check"]["scheduled_brt"],
                         "2026-11-10T06:40:00-03:00")
        self.assertFalse(r["indicator_age_check"]["executed"])
        self.assertIn("NOT_AN_EXTRA_BIAS_ALERT", r["indicator_age_check"]["purpose"])
        self.assertEqual(r["daily_master_refresh_count"], 3)

    def test_high_impact_claim_tags_near_window_without_canceling_data_refresh(self):
        brt = ZoneInfo("America/Sao_Paulo")
        event = CalendarEventClaim("US_CPI_SAMPLE", "USD", "HIGH",
                                   datetime(2026, 11, 10, 10, 30, tzinfo=brt))
        r = self.plan(events=(event,))
        self.assertEqual([x["risk_high_impact_event_ids_claimed"] for x in r["planned_slots"]],
                         [[], ["US_CPI_SAMPLE"], []])
        self.assertEqual(r["planned_slots"][1]["bias_review_status"],
                         "HIGH_IMPACT_BLACKOUT_CLAIM_REVIEW")
        self.assertTrue(r["planned_slots"][1]["data_refresh_planned_not_executed"])
        self.assertFalse(r["planned_slots"][1]["bias_publication_allowed"])
        self.assert_no_bias_or_cost(r)

    def test_calendar_claim_on_boundary_30_minutes_is_conservative(self):
        brt = ZoneInfo("America/Sao_Paulo")
        event = CalendarEventClaim("FOMC_BOUNDARY", "USD", "HIGH",
                                   datetime(2026, 11, 10, 11, 15, tzinfo=brt))
        r = self.plan(events=[event])
        self.assertEqual(r["planned_slots"][1]["risk_high_impact_event_ids_claimed"],
                         ["FOMC_BOUNDARY"])

    def test_31_minute_distance_does_not_claim_blackout(self):
        brt = ZoneInfo("America/Sao_Paulo")
        event = CalendarEventClaim("FOMC_OUTSIDE", "USD", "HIGH",
                                   datetime(2026, 11, 10, 11, 16, tzinfo=brt))
        r = self.plan(events=[event])
        self.assertEqual(r["planned_slots"][1]["risk_high_impact_event_ids_claimed"], [])
        self.assertEqual(r["planned_slots"][1]["bias_review_status"],
                         "CALENDAR_COMPLETENESS_UNVERIFIED")

    def test_low_impact_event_is_not_high_impact_veto(self):
        event = CalendarEventClaim("SMALL_DATA", "CAD", "LOW",
                                   datetime(2026, 11, 10, 13, 45, tzinfo=timezone.utc))
        r = self.plan(events=(event,))
        self.assertEqual(r["planned_slots"][1]["risk_high_impact_event_ids_claimed"], [])

    def test_missing_events_never_proves_calendar_complete(self):
        r = self.plan()
        self.assertEqual(r["source_event_claim_count"], 0)
        self.assertTrue(all(x["bias_review_status"] == "CALENDAR_COMPLETENESS_UNVERIFIED"
                            for x in r["planned_slots"]))

    def test_duplicate_event_id_blocks(self):
        claim = CalendarEventClaim("NFP_TEST", "USD", "HIGH",
                                   datetime(2026, 11, 10, 13, tzinfo=timezone.utc))
        r = self.plan(events=[claim, claim])
        self.assertEqual(r["state"], "LAB_THREE_DAILY_REFRESH_PLAN_BLOCKED")
        self.assertEqual(r["reason"], "UNSUPPORTED_OR_DUPLICATE_CALENDAR_EVENT_CLAIM")

    def test_naive_event_clock_blocks(self):
        claim = CalendarEventClaim("NFP_TEST", "USD", "HIGH",
                                   datetime(2026, 11, 10, 13))
        r = self.plan(events=[claim])
        self.assertEqual(r["reason"], "CALENDAR_EVENT_CLOCK_MISSING_OR_NAIVE")

    def test_invalid_date_or_future_malicious_volume_blocks(self):
        r = self.plan(day="2026-11-10")
        self.assertEqual(r["state"], "LAB_THREE_DAILY_REFRESH_PLAN_BLOCKED")
        many = [CalendarEventClaim(f"USD_EVENT_{i}", "USD", "HIGH",
                                   datetime(2026, 11, 10, 13, tzinfo=timezone.utc))
                for i in range(65)]
        self.assertEqual(self.plan(events=many)["state"],
                         "LAB_THREE_DAILY_REFRESH_PLAN_BLOCKED")

    def test_weekend_plans_are_still_not_jobs_or_signals(self):
        r = self.plan(date(2026, 11, 14))
        self.assertEqual(r["daily_master_refresh_count"], 3)
        self.assert_no_bias_or_cost(r)


if __name__ == "__main__":
    unittest.main()
