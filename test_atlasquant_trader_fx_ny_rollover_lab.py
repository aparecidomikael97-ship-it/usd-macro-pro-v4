"""NY rollover forex convention tests; not verified broker sessions."""
from datetime import datetime, timezone, timedelta
import unittest
from atlasquant_trader_fx_ny_rollover_lab import inspect_fx_ny_close_window_lab as inspect

def stamp(s):
    try:
        return datetime.fromisoformat(s.replace("Z","+00:00"))
    except ValueError:
        # Invalid strings must reach the lab validator and be blocked there.
        return s

def run(horizon,start,end):
    return inspect(horizon=horizon,start_at_utc=stamp(start) if isinstance(start,str) else start,
                   end_at_utc=stamp(end) if isinstance(end,str) else end)

class ForexNyRolloverTests(unittest.TestCase):
    def assert_safe(self,r):
        self.assertFalse(r["broker_session_schedule_verified"])
        self.assertFalse(r["weekend_holiday_early_close_verified"])
        self.assertFalse(r["broker_m15_execution_price_verified"])
        self.assertFalse(r["point_in_time_evidence_verified"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["new_cost_brl"],0)

    def test_standard_est_daily_session(self):
        r=run("D1","2026-11-02T22:00:00Z","2026-11-03T22:00:00Z")
        self.assertEqual(r["state"],"LAB_FX_NY_ROLLOVER_WINDOW_STRUCTURALLY_VALID")
        self.assertEqual(r["session_days"],1)
        self.assertTrue(r["start_new_york"].startswith("2026-11-02T17:00:00-05:00"))
        self.assert_safe(r)

    def test_edt_daily_session_has_different_utc_rollover(self):
        r=run("D1","2026-10-26T21:00:00Z","2026-10-27T21:00:00Z")
        self.assertEqual(r["state"],"LAB_FX_NY_ROLLOVER_WINDOW_STRUCTURALLY_VALID")
        self.assertIn("-04:00",r["start_new_york"])
        self.assert_safe(r)

    def test_sunday_open_daily_session_after_fall_dst(self):
        r=run("D1","2026-11-01T22:00:00Z","2026-11-02T22:00:00Z")
        self.assertEqual(r["state"],"LAB_FX_NY_ROLLOVER_WINDOW_STRUCTURALLY_VALID")
        self.assert_safe(r)

    def test_sunday_open_daily_session_before_fall_dst(self):
        r=run("D1","2026-10-25T21:00:00Z","2026-10-26T21:00:00Z")
        self.assertEqual(r["state"],"LAB_FX_NY_ROLLOVER_WINDOW_STRUCTURALLY_VALID")

    def test_daily_friday_close_cannot_stretch_to_sunday(self):
        r=run("D1","2026-10-30T21:00:00Z","2026-11-01T22:00:00Z")
        self.assertEqual(r["state"],"LAB_BLOCKED")
        self.assert_safe(r)

    def test_midnight_utc_is_not_trading_day_close(self):
        r=run("D1","2026-11-03T00:00:00Z","2026-11-04T00:00:00Z")
        self.assertEqual(r["reason"],"NOT_NEW_YORK_1700_CLOSE_BOUNDARY")

    def test_est_week_sunday_through_friday(self):
        r=run("W1","2026-11-01T22:00:00Z","2026-11-06T22:00:00Z")
        self.assertEqual(r["state"],"LAB_FX_NY_ROLLOVER_WINDOW_STRUCTURALLY_VALID")
        self.assertEqual(r["session_days"],5)
        self.assert_safe(r)

    def test_edt_week_sunday_through_friday(self):
        r=run("W1","2026-10-25T21:00:00Z","2026-10-30T21:00:00Z")
        self.assertEqual(r["state"],"LAB_FX_NY_ROLLOVER_WINDOW_STRUCTURALLY_VALID")
        self.assertEqual(r["session_days"],5)
        self.assert_safe(r)

    def test_weekly_seven_calendar_days_wrong(self):
        r=run("W1","2026-11-01T22:00:00Z","2026-11-08T22:00:00Z")
        self.assertEqual(r["state"],"LAB_BLOCKED")

    def test_weekday_to_weekday_not_a_weekly_forex_bar(self):
        r=run("W1","2026-11-02T22:00:00Z","2026-11-06T22:00:00Z")
        self.assertEqual(r["state"],"LAB_BLOCKED")

    def test_weekend_saturday_open_invalid(self):
        r=run("D1","2026-10-31T21:00:00Z","2026-11-01T22:00:00Z")
        self.assertEqual(r["state"],"LAB_BLOCKED")

    def test_fixed_est_offset_during_edt_is_wrong(self):
        r=run("D1","2026-10-26T22:00:00Z","2026-10-27T22:00:00Z")
        self.assertEqual(r["state"],"LAB_BLOCKED")

    def test_naive_or_string_timestamps_denied(self):
        for start in (None,42,"",datetime(2026,11,2,22)):
            r=run("D1",start,"2026-11-03T22:00:00Z")
            self.assertEqual(r["state"],"LAB_BLOCKED")

    def test_timezone_aware_utc_offset_normalized(self):
        offset=timezone(timedelta(hours=-4))
        start=datetime(2026,11,2,18,0,tzinfo=offset)
        r=run("D1",start,"2026-11-03T22:00:00Z")
        self.assertEqual(r["state"],"LAB_FX_NY_ROLLOVER_WINDOW_STRUCTURALLY_VALID")
        self.assertEqual(r["start_utc"],"2026-11-02T22:00:00+00:00")

    def test_wrong_horizon_denied(self):
        self.assertEqual(run("MN1","2026-11-02T22:00:00Z",
                             "2026-11-03T22:00:00Z")["state"],"LAB_BLOCKED")

    def test_reverse_time_denied(self):
        self.assertEqual(run("D1","2026-11-03T22:00:00Z",
                             "2026-11-02T22:00:00Z")["state"],"LAB_BLOCKED")
