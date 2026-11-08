"""Synthetic gap policy tests plus optional real-archive regression."""
import unittest
from datetime import datetime, timezone
from pathlib import Path

from atlasquant_mt5_calendar_gap_audit_lab import classify_gap, audit, DEFAULT_ROOT

def epoch(s):
    return int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp())

class GapClassifierTests(unittest.TestCase):
    def test_m15_normal_next_bar(self):
        self.assertEqual(classify_gap("M15", epoch("2026-11-04T12:00:00"),
                                      epoch("2026-11-04T12:15:00")), "NOMINAL")
    def test_weekend_m15_friday_sunday(self):
        self.assertEqual(classify_gap("M15", epoch("2026-11-06T22:45:00"),
                                      epoch("2026-11-08T23:00:00")), "WEEKEND_CANDIDATE")
    def test_midweek_m15_missing_bar_requires_review(self):
        self.assertEqual(classify_gap("M15", epoch("2026-11-04T12:00:00"),
                                      epoch("2026-11-04T12:30:00")), "REVIEW_UNEXPLAINED")
    def test_offgrid_m15_interval_requires_review(self):
        self.assertEqual(classify_gap("M15", epoch("2026-11-04T12:00:00"),
                                      epoch("2026-11-04T12:16:00")), "REVIEW_NON_GRID_DELTA")
    def test_friday_monday_daily_is_weekend_candidate(self):
        self.assertEqual(classify_gap("D1", epoch("2026-11-06T00:00:00"),
                                      epoch("2026-11-09T00:00:00")), "WEEKEND_CANDIDATE")
    def test_christmas_daily_kept_unverified(self):
        self.assertEqual(classify_gap("D1", epoch("2025-12-24T00:00:00"),
                                      epoch("2025-12-26T00:00:00")), "REVIEW_UNEXPLAINED")
    def test_gbpnzd_tuesday_missing_kept_unverified(self):
        self.assertEqual(classify_gap("D1", epoch("2025-09-29T00:00:00"),
                                      epoch("2025-10-01T00:00:00")), "REVIEW_UNEXPLAINED")
    def test_weekly_no_gap(self):
        self.assertEqual(classify_gap("W1", epoch("2026-10-18T00:00:00"),
                                      epoch("2026-10-25T00:00:00")), "NOMINAL")
    def test_weekly_missing_week_requires_review(self):
        self.assertEqual(classify_gap("W1", epoch("2026-10-11T00:00:00"),
                                      epoch("2026-10-25T00:00:00")), "REVIEW_UNEXPLAINED")
    def test_duplicate_clock_requires_review(self):
        t=epoch("2026-11-04T12:00:00")
        self.assertEqual(classify_gap("M15", t, t), "REVIEW_INVALID_TIME_OR_TF")
    def test_no_hidden_market_permission(self):
        report=audit(Path("_missing_mt5_archive_for_synthetic"))
        self.assertEqual(report["operational_bias"], "AGUARDAR")
        self.assertFalse(report["trade_authorized"])
        self.assertFalse(report["broker_trading_schedule_verified"])
        self.assertFalse(report["historical_point_in_time_verified"])
        self.assertEqual(report["status"], "LOCAL_CALENDAR_REVIEW_REQUIRED")

@unittest.skipUnless(DEFAULT_ROOT.is_dir() and len(list(DEFAULT_ROOT.glob("batch_??_manifest.json")))==7,
                     "Original AM12 archived snapshots are not in this environment")
class ArchivedMT5Regression(unittest.TestCase):
    def test_all_archives_and_unresolved_2025_september_event(self):
        r=audit(DEFAULT_ROOT)
        self.assertEqual((r["pairs"],r["files_verified"],r["bar_count"]), (28,84,103600))
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["gap_counts_by_tf"]["M15"].get("WEEKEND_CANDIDATE"), 168)
        self.assertEqual(r["gap_counts_by_tf"]["D1"].get("WEEKEND_CANDIDATE"), 2800)
        self.assertEqual(r["review_gap_count"], 87)
        self.assertEqual(r["missing_weekday_date_pairs"]["2025-09-30"],["GBPNZD"])
        self.assertFalse(r["trade_authorized"])
        self.assertEqual(r["status"],"LOCAL_CALENDAR_REVIEW_REQUIRED")

if __name__=="__main__":
    unittest.main(verbosity=2)
