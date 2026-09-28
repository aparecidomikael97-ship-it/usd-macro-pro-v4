"""Weekly profile research stays descriptive, point-in-time, and fail-closed."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

import pandas as pd

from atlasquant_weekly_profile import STATE_INSUFFICIENT_SAMPLE, STATE_RESEARCH_READY, analyze_weekly_extremes


def _days(start: str, highs: list[float], lows: list[float], *, tz=None) -> list[dict[str, object]]:
    origin = pd.Timestamp(start)
    rows = []
    for offset, (high, low) in enumerate(zip(highs, lows)):
        stamp = origin + pd.Timedelta(days=offset)
        if tz is not None:
            stamp = stamp.tz_localize(tz)
        rows.append({"datetime": stamp, "high": high, "low": low})
    return rows


class WeeklyProfileTests(unittest.TestCase):
    def test_missing_or_invalid_frame_is_insufficient(self):
        for daily in (None, {"datetime": [], "high": [], "low": []}, pd.DataFrame({"close": [1]})):
            with self.subTest(daily=type(daily).__name__):
                out = analyze_weekly_extremes(daily)
                self.assertEqual(out["state"], STATE_INSUFFICIENT_SAMPLE)
                self.assertEqual(out["data_quality"], "INPUT_INVALID")
                self.assertEqual(out["weeks"], 0)
                self.assertEqual(out["rows"], [])
                self.assertIsNone(out["tuesday_wednesday_high_pct"])
                self.assertEqual(out["observations"], 0)

    def test_empty_frame_is_insufficient(self):
        out = analyze_weekly_extremes(pd.DataFrame(columns=["datetime", "high", "low"]))
        self.assertEqual(out["state"], STATE_INSUFFICIENT_SAMPLE)
        self.assertEqual(out["data_quality"], "EMPTY_SAMPLE")
        self.assertEqual(out["high_day_frequency_pct"], {})
        self.assertIsNone(out["sample_start"])

    def test_invalid_datetime_is_discarded(self):
        rows = _days("2026-08-03", [10, 12, 11, 10], [5, 4, 3, 4])
        rows.append({"datetime": "not-a-date", "high": 99, "low": 1})
        out = analyze_weekly_extremes(pd.DataFrame(rows))
        self.assertEqual(out["invalid_rows"], 1)
        self.assertEqual(out["observations"], 4)
        self.assertEqual(out["weeks"], 1)
        self.assertNotEqual(out["rows"][0]["high"], 99)

    def test_invalid_ohlc_and_high_below_low_are_discarded(self):
        rows = _days("2026-08-03", [10, 12, 11, 10], [5, 4, 3, 4])
        rows.extend([
            {"datetime": "2026-08-07", "high": float("inf"), "low": 1},
            {"datetime": "2026-08-07", "high": float("nan"), "low": 1},
            {"datetime": "2026-08-07", "high": 1, "low": 5},
            {"datetime": "2026-08-07", "high": True, "low": 1},
        ])
        out = analyze_weekly_extremes(pd.DataFrame(rows))
        self.assertEqual(out["invalid_rows"], 4)
        self.assertEqual(out["observations"], 4)
        self.assertEqual(out["rows"][0]["high"], 12.0)
        self.assertEqual(out["rows"][0]["low"], 3.0)

    def test_short_week_is_not_a_frequency_conclusion(self):
        out = analyze_weekly_extremes(pd.DataFrame(_days("2026-08-03", [10, 12, 11], [5, 4, 3])))
        self.assertEqual(out["state"], STATE_INSUFFICIENT_SAMPLE)
        self.assertEqual(out["data_quality"], "INSUFFICIENT_WEEKS")
        self.assertEqual(out["weeks"], 0)
        self.assertEqual(out["observations"], 3)
        self.assertEqual(out["high_day_frequency_pct"], {})
        self.assertIsNone(out["tuesday_wednesday_high_pct"])
        self.assertIsNone(out["tuesday_wednesday_low_pct"])
        self.assertIsNotNone(out["sample_start"])

    def test_valid_week_reports_research_sample(self):
        out = analyze_weekly_extremes(pd.DataFrame(_days("2026-08-03", [10, 15, 12, 11], [6, 5, 2, 4])))
        self.assertEqual(out["state"], STATE_RESEARCH_READY)
        self.assertEqual(out["data_quality"], "RESEARCH_SAMPLE")
        self.assertEqual(out["weeks"], 1)
        self.assertEqual(out["observations"], 4)
        self.assertEqual(out["min_days_per_week"], 4)
        self.assertEqual(out["rows"][0]["high_day"], "Tuesday")
        self.assertEqual(out["rows"][0]["low_day"], "Wednesday")
        self.assertEqual(out["sample_start"], "2026-08-03T00:00:00+00:00")
        self.assertEqual(out["sample_end"], "2026-08-06T00:00:00+00:00")
        self.assertNotIn("VALIDATED_STRATEGY", out.values())

    def test_high_and_low_can_fall_on_distinct_days(self):
        out = analyze_weekly_extremes(pd.DataFrame(_days("2026-08-03", [9, 10, 14, 11], [4, 1, 3, 2])))
        self.assertEqual(out["rows"][0]["high_day"], "Wednesday")
        self.assertEqual(out["rows"][0]["low_day"], "Tuesday")
        self.assertNotEqual(out["rows"][0]["high_day"], out["rows"][0]["low_day"])

    def test_tie_uses_first_occurrence(self):
        out = analyze_weekly_extremes(pd.DataFrame(_days("2026-08-03", [20, 11, 20, 10], [2, 3, 1, 1])))
        self.assertEqual(out["extreme_tie_rule"], "FIRST_OCCURRENCE")
        self.assertEqual(out["rows"][0]["high_day"], "Monday")
        self.assertEqual(out["rows"][0]["low_day"], "Wednesday")

    def test_tuesday_wednesday_share_is_calculated_not_assumed(self):
        out = analyze_weekly_extremes(pd.DataFrame(_days("2026-08-03", [20, 11, 12, 13], [1, 4, 3, 2])))
        self.assertEqual(out["tuesday_wednesday_high_pct"], 0.0)
        self.assertEqual(out["tuesday_wednesday_low_pct"], 0.0)
        self.assertFalse(out["fixed_day_rule_assumed"])

    def test_several_weeks_do_not_look_ahead(self):
        rows = []
        rows.extend(_days("2026-08-03", [10, 11, 14, 12, 11], [5, 4, 3, 4, 5]))
        rows.extend(_days("2026-08-10", [10, 11, 12, 11, 50], [5, 4, 3, 2, 4]))
        out = analyze_weekly_extremes(pd.DataFrame(rows))
        self.assertEqual(out["weeks"], 2)
        self.assertEqual(out["observations"], 10)
        self.assertEqual(out["rows"][0]["high_day"], "Wednesday")
        self.assertEqual(out["rows"][0]["high"], 14.0)
        self.assertEqual(out["rows"][1]["high_day"], "Friday")
        self.assertEqual(out["rows"][1]["high"], 50.0)
        self.assertEqual(out["tuesday_wednesday_high_pct"], 50.0)

    def test_timezone_weekday_follows_utc(self):
        rows = [
            {"datetime": pd.Timestamp("2026-08-03 22:00:00", tz="America/New_York"), "high": 30, "low": 10},
            {"datetime": pd.Timestamp("2026-08-05 12:00:00", tz="UTC"), "high": 11, "low": 4},
            {"datetime": pd.Timestamp("2026-08-06 12:00:00", tz="UTC"), "high": 12, "low": 5},
            {"datetime": pd.Timestamp("2026-08-07 12:00:00", tz="UTC"), "high": 13, "low": 6},
        ]
        out = analyze_weekly_extremes(pd.DataFrame(rows))
        self.assertEqual(out["rows"][0]["high_day"], "Tuesday")
        self.assertTrue(str(out["sample_start"]).endswith("+00:00"))

    def test_min_days_rejects_bool_zero_negative_absurd_and_numeric_string(self):
        frame = pd.DataFrame(_days("2026-08-03", [10, 12, 11, 10], [5, 4, 3, 4]))
        for value in (True, False, 0, -1, 8, "4", 4.0, 4.5):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    analyze_weekly_extremes(frame, min_days_per_week=value)

    def test_custom_min_days_is_echoed(self):
        out = analyze_weekly_extremes(
            pd.DataFrame(_days("2026-08-03", [10, 12], [4, 3])),
            min_days_per_week=2,
        )
        self.assertEqual(out["state"], STATE_RESEARCH_READY)
        self.assertEqual(out["min_days_per_week"], 2)
        self.assertEqual(out["weeks"], 1)

    def test_research_flags_never_infer_intent_or_promotion(self):
        ready = analyze_weekly_extremes(pd.DataFrame(_days("2026-08-03", [10, 12, 11, 10], [5, 4, 3, 4])))
        empty = analyze_weekly_extremes(pd.DataFrame(columns=["datetime", "high", "low"]))
        for out in (ready, empty):
            self.assertFalse(out["fixed_day_rule_assumed"])
            self.assertFalse(out["institutional_intent_inferred"])
            self.assertFalse(out["automatic_strategy_change"])
            self.assertFalse(out["automatic_promotion"])
            self.assertNotIn("probabilidade de ganho", out["interpretation"].casefold())

    def test_module_does_not_fetch_external_context(self):
        source = Path("atlasquant_weekly_profile.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(imported.isdisjoint({"requests", "urllib", "socket", "subprocess", "http"}))
        self.assertNotIn("COT", source)
        self.assertNotIn("VALIDATED_STRATEGY", source)


if __name__ == "__main__":
    unittest.main()
