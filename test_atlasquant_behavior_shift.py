"""Behavior shift research compares observed windows and does not authorize action."""
from __future__ import annotations

import json
import math
import unittest

from atlasquant_behavior_shift import BehaviorStats, detect_behavior_shift


def _stats(sample_size=80, **overrides) -> BehaviorStats:
    values = {
        "sample_size": sample_size,
        "london_expansion_pct": 50,
        "new_york_expansion_pct": 45,
        "sweep_followthrough_pct": 60,
        "reversal_after_sweep_pct": 30,
        "level_reaction_pct": 55,
        "average_range": 100,
    }
    values.update(overrides)
    return BehaviorStats(**values)


class BehaviorShiftTests(unittest.TestCase):
    def test_valid_windows_expose_thresholds_and_closed_flags(self):
        out = detect_behavior_shift(_stats(120), _stats(40, london_expansion_pct=70, average_range=140))
        self.assertEqual(out["baseline_sample_size"], 120)
        self.assertEqual(out["recent_sample_size"], 40)
        self.assertTrue(out["sample_sufficient"])
        self.assertEqual(out["thresholds"], {
            "min_baseline_samples": 50,
            "min_recent_samples": 20,
            "pct_shift_threshold": 15.0,
            "range_relative_threshold": 0.25,
        })
        self.assertGreaterEqual(out["change_count"], 2)
        self.assertEqual(out["state"], "MEANINGFUL_SHIFT_REVIEW")

    def test_insufficient_sample_emits_no_changes(self):
        out = detect_behavior_shift(_stats(100), _stats(8, london_expansion_pct=10, average_range=200))
        self.assertEqual(out["state"], "INSUFFICIENT_SAMPLE")
        self.assertFalse(out["sample_sufficient"])
        self.assertEqual(out["change_count"], 0)
        self.assertEqual(out["changes"], [])

    def test_stable_windows_stay_inside_thresholds(self):
        out = detect_behavior_shift(_stats(), _stats(sample_size=30, london_expansion_pct=55))
        self.assertEqual(out["state"], "STABLE_WITHIN_THRESHOLDS")
        self.assertEqual(out["change_count"], 0)
        self.assertEqual(out["range_relative_change_pct"], 0.0)

    def test_single_metric_shift(self):
        out = detect_behavior_shift(_stats(), _stats(sample_size=30, new_york_expansion_pct=70))
        self.assertEqual(out["state"], "SINGLE_METRIC_SHIFT")
        self.assertEqual(out["change_count"], 1)
        self.assertEqual(out["changes"][0]["metric"], "new_york_expansion_pct")
        self.assertEqual(out["changes"][0]["direction"], "UP")

    def test_meaningful_shift_needs_two_metrics(self):
        out = detect_behavior_shift(
            _stats(),
            _stats(sample_size=30, london_expansion_pct=20, reversal_after_sweep_pct=60),
        )
        self.assertEqual(out["state"], "MEANINGFUL_SHIFT_REVIEW")
        self.assertEqual(out["change_count"], 2)
        self.assertEqual({row["direction"] for row in out["changes"]}, {"DOWN", "UP"})

    def test_range_shift_reports_relative_change(self):
        out = detect_behavior_shift(_stats(), _stats(sample_size=30, average_range=140))
        self.assertEqual(out["state"], "SINGLE_METRIC_SHIFT")
        self.assertTrue(out["range_relative_calculable"])
        self.assertEqual(out["range_relative_change_pct"], 40.0)
        self.assertEqual(out["changes"][0]["metric"], "average_range")
        self.assertEqual(out["changes"][0]["relative_change_pct"], 40.0)

    def test_zero_baseline_range_is_not_calculable(self):
        out = detect_behavior_shift(_stats(average_range=0), _stats(sample_size=30, average_range=80))
        self.assertFalse(out["range_relative_calculable"])
        self.assertIsNone(out["range_relative_change_pct"])
        self.assertEqual(out["changes"], [])
        self.assertEqual(out["state"], "STABLE_WITHIN_THRESHOLDS")

    def test_percent_outside_unit_interval_is_rejected(self):
        for name, value in (
            ("london_expansion_pct", -0.1),
            ("new_york_expansion_pct", 100.1),
            ("level_reaction_pct", 101),
        ):
            with self.subTest(name=name, value=value):
                with self.assertRaises(ValueError):
                    _stats(**{name: value})

    def test_nan_and_infinity_are_rejected(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _stats(london_expansion_pct=value)
                with self.assertRaises(ValueError):
                    _stats(average_range=value)

    def test_sample_size_must_be_exact_non_negative_int(self):
        for value in (-1, 20.5, 20.0, "20", True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _stats(sample_size=value)
        self.assertEqual(_stats(sample_size=0).sample_size, 0)

    def test_thresholds_reject_bool_negative_and_nan(self):
        baseline = _stats()
        recent = _stats(sample_size=30)
        rejected = (
            {"min_baseline_samples": True},
            {"min_recent_samples": False},
            {"min_baseline_samples": 0},
            {"min_recent_samples": -5},
            {"min_baseline_samples": 50.0},
            {"pct_shift_threshold": -1},
            {"pct_shift_threshold": math.nan},
            {"pct_shift_threshold": math.inf},
            {"pct_shift_threshold": True},
            {"range_relative_threshold": -0.1},
            {"range_relative_threshold": math.nan},
            {"range_relative_threshold": True},
            {"pct_shift_threshold": "15"},
        )
        for override in rejected:
            with self.subTest(override=override):
                with self.assertRaises(ValueError):
                    detect_behavior_shift(baseline, recent, **override)

    def test_closed_research_flags_and_no_order(self):
        out = detect_behavior_shift(_stats(120, london_expansion_pct=80), _stats(40, london_expansion_pct=20))
        self.assertFalse(out["institutional_intent_inferred"])
        self.assertFalse(out["automatic_strategy_change"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["execution_authorized"])
        self.assertFalse(out["real_trading_enabled"])
        blob = json.dumps(out)
        self.assertNotIn("BUY", blob)
        self.assertNotIn("SELL", blob)
        text = out["interpretation"].casefold()
        self.assertNotIn("smart money", text)
        self.assertNotIn("vai entrar", text)
        self.assertNotIn("comprando", text)


if __name__ == "__main__":
    unittest.main()
