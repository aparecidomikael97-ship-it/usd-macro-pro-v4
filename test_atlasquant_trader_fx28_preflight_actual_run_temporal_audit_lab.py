"""Synthetic and observed-schedule-shape tests. No broker/API/network IO."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_fx28_preflight_actual_run_temporal_audit_lab import (
    SCHEMA, WINDOW_START, FIRST_NOMINAL_OPEN,
    audit_fx28_preflight_actual_run_times_lab as audit,
)

UTC = timezone.utc
P0 = datetime(2026, 11, 15, 9, 57, 50, 949240, tzinfo=UTC)
P1 = datetime(2026, 11, 15, 9, 58, 11, 169321, tzinfo=UTC)
H0 = datetime(2026, 11, 15, 10, 5, 51, 825067, tzinfo=UTC)
H1 = datetime(2026, 11, 15, 10, 6, 16, 116272, tzinfo=UTC)
NOW = datetime(2026, 11, 15, 10, 23, 22, tzinfo=UTC)


class PreflightTemporalRunTests(unittest.TestCase):
    def run_audit(self, **overrides):
        arguments = {
            "preflight_started": P0,
            "preflight_completed": P1,
            "hourly_started": H0,
            "hourly_completed": H1,
            "inspected_at": NOW,
            "github_comments_checked": 100,
            "canonical_header_count": 0,
            "local_source_audit_completed": False,
        }
        arguments.update(overrides)
        return audit(**arguments)

    def safe(self, report):
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["frozen_total_pair_horizon_slots"], 672)
        self.assertEqual(report["frozen_first_d1w1_pair_horizon_slots"], 56)
        self.assertEqual(report["authenticated_immutable_forecast_count"], 0)
        self.assertFalse(report["market_data_observed"])
        self.assertFalse(report["m15_data_collection_performed"])
        self.assertFalse(report["trade_authorized"])
        self.assertFalse(report["publishable"])
        self.assertEqual(report["operational_bias"], "AGUARDAR")
        self.assertIsNone(report["validated_accuracy"])
        self.assertIsNone(report["calibrated_directional_probability"])
        self.assertFalse(report["github_comments_absence_independently_attested"])
        self.assertFalse(report["hourly_comment_review_substitutes_local_source_audit"])
        self.assertEqual((report["http_requests"], report["mt5_calls"],
                          report["file_writes"]), (0, 0, 0))

    def test_01_actual_early_run_and_later_hourly_are_separate(self):
        r = self.run_audit()
        self.safe(r)
        self.assertEqual(r["state"],
            "LAB_FX28_PREFLIGHT_EARLY_LATER_COMMENT_REVIEW_ONLY_NO_GO")
        self.assertTrue(r["preflight_early_completed_outside_window"])
        self.assertFalse(r["preflight_execution_fully_inside_12h"])
        self.assertTrue(r["hourly_comment_review_inside_12h"])
        self.assertFalse(r["first_56_slots_due"])
        self.assertEqual(r["observed_comment_count"], 100)
        self.assertEqual(r["canonical_comment_header_count"], 0)
        self.assertEqual(r["local_source_state"], "UNKNOWN")

    def test_02_scheduled_at_10_00_does_not_overwrite_actual_clock(self):
        # Explicit schedule field is absent by design; only actual timestamps.
        r = self.run_audit()
        self.assertFalse(r["preflight_execution_fully_inside_12h"])

    def test_03_exact_10_00_start_meets_time_gate_only(self):
        r = self.run_audit(
            preflight_started=WINDOW_START,
            preflight_completed=WINDOW_START + timedelta(seconds=11))
        self.safe(r)
        self.assertTrue(r["preflight_execution_fully_inside_12h"])
        self.assertFalse(r["preflight_early_completed_outside_window"])
        self.assertEqual(r["state"],
            "LAB_FX28_PREFLIGHT_TEMPORALLY_IN_WINDOW_STILL_UNATTESTED_NO_GO")

    def test_04_cross_boundary_preflight_not_fully_inside(self):
        r = self.run_audit(
            preflight_started=WINDOW_START-timedelta(seconds=10),
            preflight_completed=WINDOW_START+timedelta(seconds=10))
        self.safe(r)
        self.assertFalse(r["preflight_execution_fully_inside_12h"])
        self.assertFalse(r["preflight_early_completed_outside_window"])

    def test_05_hourly_before_window_is_not_in_window_review(self):
        r = self.run_audit(
            hourly_started=P0, hourly_completed=P1)
        self.safe(r)
        self.assertFalse(r["hourly_comment_review_inside_12h"])

    def test_06_hourly_within_window_cannot_substitute_local_offline(self):
        r = self.run_audit(local_source_audit_completed=False)
        self.safe(r)
        self.assertTrue(r["hourly_comment_review_inside_12h"])
        self.assertEqual(r["local_source_state"], "UNKNOWN")

    def test_07_even_local_source_audit_claim_is_not_pit_forecast(self):
        r = self.run_audit(local_source_audit_completed=True)
        self.safe(r)
        self.assertEqual(r["local_source_state"], "LOCALLY_AUDITED_CLAIM_ONLY")
        self.assertEqual(r["authenticated_immutable_forecast_count"], 0)

    def test_08_comment_count_one_hundred_does_not_mean_one_hundred_forecasts(self):
        r = self.run_audit(canonical_header_count=99)
        self.safe(r)
        self.assertEqual(r["canonical_comment_header_count"], 99)
        self.assertEqual(r["authenticated_immutable_forecast_count"], 0)

    def test_09_comment_count_cannot_exceed_total(self):
        r = self.run_audit(github_comments_checked=10,
                           canonical_header_count=11)
        self.safe(r)
        self.assertEqual(r["state"], "LAB_FX28_PREFLIGHT_TEMPORAL_INPUT_INVALID_NO_GO")

    def test_10_bool_comment_count_rejected(self):
        r = self.run_audit(github_comments_checked=True)
        self.safe(r)
        self.assertEqual(r["state"], "LAB_FX28_PREFLIGHT_TEMPORAL_INPUT_INVALID_NO_GO")

    def test_11_naive_time_rejected(self):
        r = self.run_audit(
            hourly_started=datetime(2026, 11, 15, 10, 5))
        self.safe(r)
        self.assertEqual(r["state"], "LAB_FX28_PREFLIGHT_TEMPORAL_INPUT_INVALID_NO_GO")

    def test_12_run_end_before_start_rejected(self):
        r = self.run_audit(preflight_started=P1, preflight_completed=P0)
        self.safe(r)
        self.assertEqual(r["state"], "LAB_FX28_PREFLIGHT_TEMPORAL_INPUT_INVALID_NO_GO")

    def test_13_inspection_before_completed_hourly_rejected(self):
        r = self.run_audit(inspected_at=H0)
        self.safe(r)
        self.assertEqual(r["state"], "LAB_FX28_PREFLIGHT_TEMPORAL_INPUT_INVALID_NO_GO")

    def test_14_first_56_slots_due_at_exact_nominal_open_not_at_m15_close(self):
        r = self.run_audit(inspected_at=FIRST_NOMINAL_OPEN)
        self.safe(r)
        self.assertTrue(r["first_56_slots_due"])
        self.assertFalse(r["m15_data_collection_performed"])

    def test_15_before_22_00_nothing_due(self):
        r = self.run_audit(inspected_at=FIRST_NOMINAL_OPEN-timedelta(microseconds=1))
        self.safe(r)
        self.assertFalse(r["first_56_slots_due"])

    def test_16_local_source_bool_validation(self):
        r = self.run_audit(local_source_audit_completed="true")
        self.safe(r)
        self.assertEqual(r["state"], "LAB_FX28_PREFLIGHT_TEMPORAL_INPUT_INVALID_NO_GO")

    def test_17_timezone_offsets_normalized(self):
        cuiaba = timezone(timedelta(hours=-4))
        r = self.run_audit(
            preflight_started=P0.astimezone(cuiaba),
            preflight_completed=P1.astimezone(cuiaba),
            hourly_started=H0.astimezone(cuiaba),
            hourly_completed=H1.astimezone(cuiaba),
            inspected_at=NOW.astimezone(cuiaba))
        self.safe(r)
        self.assertTrue(r["preflight_early_completed_outside_window"])
        self.assertTrue(r["hourly_comment_review_inside_12h"])

    def test_18_look_forward_not_precommit_hindsight(self):
        r = self.run_audit(inspected_at=FIRST_NOMINAL_OPEN+timedelta(hours=3))
        self.safe(r)
        self.assertTrue(r["first_56_slots_due"])
        self.assertFalse(r["preflight_execution_fully_inside_12h"])
        self.assertEqual(r["authenticated_immutable_forecast_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
