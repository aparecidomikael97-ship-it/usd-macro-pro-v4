"""Three full daily updates plus faster event watch are only targets, no jobs."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_monitoring_cadence_lab import (
    DAILY_FULL_REFRESH, SCHEMA, build_monitoring_cadence_lab,
)

AT = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


class MonitoringCadenceLabTests(unittest.TestCase):
    def test_three_full_slots_per_day_and_no_scheduler(self):
        report = build_monitoring_cadence_lab(at=AT)
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["state"], "LAB_POLICY_ONLY_NOT_RUNNING")
        self.assertEqual(len(report["daily_full_refresh_slots_next_two_days"]), 6)
        self.assertEqual(report["daily_full_refresh_target"], 3)
        self.assertEqual([x.strftime("%H:%M") for x in DAILY_FULL_REFRESH],
                         ["06:35", "10:45", "17:15"])
        self.assertEqual(report["daily_full_refresh_slots_next_two_days"][0]
                         ["at_mato_grosso"], "2026-11-04T05:35:00-04:00")
        for key in ("source_rate_limits_reviewed",
                    "source_terms_and_commercial_license_checked",
                    "full_g8_calendar_coverage", "news_feed_latency_measured",
                    "realtime_delivery_verified", "three_daily_runs_actually_verified",
                    "durable_change_history_available", "alert_delivery_verified",
                    "calendar_changes_automatically_ingested", "news_live",
                    "scheduler_enabled", "worker_enabled", "aion_worker_enabled",
                    "paid_api_enabled", "paid_provider_charged", "trade_authorized",
                    "can_feed_live_radar"):
            self.assertFalse(report[key], key)
        self.assertEqual(report["new_external_requests"], 0)
        self.assertEqual(report["target_poll_minutes_now"], 15)

    def test_around_official_event_target_can_be_faster_not_live_claim(self):
        at = datetime(2026, 11, 5, 11, 30, tzinfo=timezone.utc)
        report = build_monitoring_cadence_lab(at=at)
        self.assertTrue(report["in_curated_critical_window"])
        self.assertIn("BOE_MPC_20261105", report["curated_critical_event_ids"])
        self.assertEqual(report["target_poll_minutes_now"], 5)
        self.assertFalse(report["realtime_delivery_verified"])

    def test_before_v2_review_no_anachronistic_event_promoted(self):
        report = build_monitoring_cadence_lab(
            at=AT - timedelta(days=1))
        self.assertFalse(report["in_curated_critical_window"])
        self.assertEqual(report["curated_critical_event_ids"], [])

    def test_naive_clock_refused(self):
        with self.assertRaises(ValueError):
            build_monitoring_cadence_lab(at=AT.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
