"""Synthetic NY17 sessions only. Never evidence of broker prices or accuracy."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import unittest

from atlasquant_trader_fx_bias_quality_lab import BiasTrial
from atlasquant_trader_fx_bias_ny17_calendar_join_lab import (
    inspect_fx_bias_ny17_calendar_join_lab as inspect,
)

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 20, 12, tzinfo=UTC)


def ny(year, month, day, hour=17, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=NY).astimezone(UTC)


def trial(start, end, *, i=1, horizon="D1", pair="EUR/USD",
          side="UP", exit_price="1.01000"):
    return BiasTrial(
        trial_id=f"NY17_TRIAL_{i:03d}",
        pair=pair, horizon=horizon, side=side,
        features_captured_at=start - timedelta(hours=3),
        entry_price_captured_at=start - timedelta(hours=2),
        prediction_issued_at=start - timedelta(hours=1),
        outcome_start_at=start, outcome_end_at=end,
        outcome_captured_at=end + timedelta(minutes=1),
        entry_close_price_claim="1.00000",
        exit_close_price_claim=exit_price,
    )


def call(rows, *, pair="EUR/USD", horizon="D1", as_of=NOW):
    return inspect(
        rows, pair=pair, horizon=horizon, evaluated_at_utc=as_of,
    )


class StrictNy17BiasJoinTests(unittest.TestCase):
    def safety(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertFalse(r["publishable"])
        self.assertFalse(r["can_feed_live_radar"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["broker_session_calendar_independently_verified"])
        self.assertFalse(r["broker_holidays_and_early_closes_verified"])
        self.assertFalse(r["prediction_precommit_independently_verified"])
        self.assertFalse(r["point_in_time_features_independently_verified"])
        self.assertFalse(r["price_originals_independently_verified"])
        self.assertFalse(r["outcomes_independently_verified"])
        self.assertFalse(r["statistical_independence_verified"])
        self.assertIsNone(r["validated_directional_accuracy"])
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assertEqual(
            (r["external_http_requests"], r["file_writes"], r["new_cost_brl"]),
            (0, 0, 0),
        )
        self.assertTrue(r["research_only"])

    def test_canonical_sunday_monday_and_monday_tuesday_d1(self):
        rows = [
            trial(ny(2026, 11, 8), ny(2026, 11, 9), i=1),
            trial(ny(2026, 11, 9), ny(2026, 11, 10), i=2),
        ]
        r = call(rows)
        self.assertEqual(r["state"], "LAB_FX_NY17_BIAS_QUALITY_CLAIM_ONLY_NO_GO")
        self.assertEqual(r["claimed_sessions_checked"], 2)
        self.assertEqual(r["claimed_quality_accounting"]["emitted_biases"], 2)
        self.assertTrue(r["new_york_iana_timezone_applied"])
        self.assertTrue(r["strict_ny17_claim_window_shape_checked"])
        self.safety(r)

    def test_canonical_sunday_to_friday_w1(self):
        weekly = trial(ny(2026, 11, 8), ny(2026, 11, 13),
                       i=1, horizon="W1")
        r = call([weekly], horizon="W1")
        self.assertEqual(r["state"], "LAB_FX_NY17_BIAS_QUALITY_CLAIM_ONLY_NO_GO")
        self.assertEqual(r["claimed_sessions_checked"], 1)
        self.assertEqual(r["claimed_quality_accounting"]["horizon"], "W1")
        self.safety(r)

    def test_utc_midnight_24h_rejected_even_when_duration_is_correct(self):
        start = datetime(2026, 11, 9, 0, tzinfo=UTC)
        r = call([trial(start, start + timedelta(days=1))])
        self.assertEqual(r["state"], "LAB_FX_BIAS_NY17_JOIN_BLOCKED")
        self.assertEqual(r["reason"],
                         "NONCANONICAL_NY17_NOT_NEW_YORK_1700_CLOSE_BOUNDARY")
        self.assertEqual(r["rejected_trial_index"], 0)
        self.assertIsNone(r["claimed_quality_accounting"])
        self.safety(r)

    def test_weekly_monday_to_saturday_is_wrong_despite_five_days(self):
        row = trial(ny(2026, 11, 9), ny(2026, 11, 14), horizon="W1")
        r = call([row], horizon="W1")
        self.assertEqual(r["reason"],
                         "NONCANONICAL_NY17_FOREX_WEEKEND_OR_NONCANONICAL_SESSION")
        self.safety(r)

    def test_weekly_sunday_to_friday_at_1600_is_not_ny_close(self):
        row = trial(ny(2026, 11, 8), ny(2026, 11, 13, 16),
                    horizon="W1")
        r = call([row], horizon="W1")
        self.assertEqual(r["reason"],
                         "NONCANONICAL_NY17_NOT_NEW_YORK_1700_CLOSE_BOUNDARY")
        self.safety(r)

    def test_fifteen_minute_or_four_hour_chart_cannot_be_d1(self):
        start = ny(2026, 11, 8)
        for minutes in (15, 60, 240):
            with self.subTest(minutes=minutes):
                r = call([trial(start, start + timedelta(minutes=minutes))])
                self.assertEqual(r["state"], "LAB_FX_BIAS_NY17_JOIN_BLOCKED")
                self.safety(r)

    def test_spring_and_fall_dst_use_new_york_iana_not_fixed_utc(self):
        cases = (
            (ny(2026, 3, 8), ny(2026, 3, 9)),
            (ny(2026, 11, 1), ny(2026, 11, 2)),
        )
        for start, end in cases:
            with self.subTest(start=start):
                r = call([trial(start, end)])
                self.assertEqual(r["state"],
                                 "LAB_FX_NY17_BIAS_QUALITY_CLAIM_ONLY_NO_GO")
                self.assertEqual((end - start).total_seconds(), 86400)
                self.safety(r)
        self.assertEqual(ny(2026, 3, 8).hour, 21)
        self.assertEqual(ny(2026, 11, 1).hour, 22)

    def test_any_invalid_session_blocks_entire_cohort_not_drop_one(self):
        first = trial(ny(2026, 11, 8), ny(2026, 11, 9), i=1)
        second = trial(ny(2026, 11, 9), ny(2026, 11, 10, 16), i=2)
        r = call([first, second])
        self.assertEqual(r["state"], "LAB_FX_BIAS_NY17_JOIN_BLOCKED")
        self.assertEqual(r["rejected_trial_index"], 1)
        self.assertEqual(r["claimed_sessions_checked"], 0)
        self.assertIsNone(r["claimed_quality_accounting"])
        self.safety(r)

    def test_duplicate_claimed_window_stays_blocked_by_accountant(self):
        first = trial(ny(2026, 11, 8), ny(2026, 11, 9), i=1)
        second = replace(first, trial_id="NY17_TRIAL_002")
        r = call([first, second])
        self.assertEqual(r["state"], "LAB_FX_BIAS_NY17_JOIN_BLOCKED")
        self.assertEqual(r["reason"],
                         "BIAS_QUALITY_OVERLAPPING_OUTCOME_WINDOWS_MULTICOUNTING")
        self.safety(r)

    def test_future_or_unresolved_outcome_remains_blocked(self):
        row = trial(ny(2026, 11, 8), ny(2026, 11, 9))
        r = call([row], as_of=ny(2026, 11, 9) - timedelta(hours=1))
        self.assertEqual(r["state"], "LAB_FX_BIAS_NY17_JOIN_BLOCKED")
        self.assertEqual(r["reason"],
                         "BIAS_QUALITY_FUTURE_LEAKAGE_OR_UNRESOLVED_OUTCOME")
        self.safety(r)

    def test_invalid_pair_horizon_and_mn1_unimplemented_no_fallback(self):
        row = trial(ny(2026, 11, 8), ny(2026, 11, 9))
        for params in (
            {"pair": "XAU/USD"},
            {"horizon": "MN1"},
            {"horizon": "M1"},
            {"horizon": "M15"},
            {"as_of": NOW.replace(tzinfo=None)},
        ):
            with self.subTest(params=params):
                r = call([row], **params)
                self.assertEqual(r["state"], "LAB_FX_BIAS_NY17_JOIN_BLOCKED")
                self.assertIsNone(r["claimed_quality_accounting"])
                self.safety(r)

    def test_mismatched_pair_claim_is_blocked(self):
        row = trial(ny(2026, 11, 8), ny(2026, 11, 9), pair="EUR/USD")
        r = call([row], pair="GBP/USD")
        self.assertEqual(r["reason"], "TRIAL_PAIR_HORIZON_OR_TYPE_CONFLICT")
        self.safety(r)

    def test_abstention_is_not_a_hit_and_no_probability_is_generated(self):
        row = trial(ny(2026, 11, 8), ny(2026, 11, 9), side="ABSTAIN")
        r = call([row])
        self.assertEqual(r["claimed_quality_accounting"]["abstentions"], 1)
        self.assertIsNone(
            r["claimed_quality_accounting"]["research_claim_only_hit_rate_pct"]
        )
        self.assertIsNone(r["calibrated_direction_probability"])
        self.safety(r)


if __name__ == "__main__":
    unittest.main()
