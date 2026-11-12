"""Offline fail-closed tests; optional regression reads original AM12 archive."""
import unittest
import csv
from datetime import datetime, timedelta, timezone
import gzip
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from atlasquant_mt5_calendar_gap_audit_lab import DEFAULT_ROOT
from atlasquant_mt5_backtest_gap_guard_lab import (
    GapGuardError, audit_archive, partition_series, require_contiguous_window,
    window_decision,
)


def epoch(date_time):
    return int(datetime.fromisoformat(date_time).replace(tzinfo=timezone.utc).timestamp())


class GapGuardTests(unittest.TestCase):
    def test_nominal_m15_window_only_passes_calendar_gate(self):
        times = [epoch("2026-11-04T12:00:00"), epoch("2026-11-04T12:15:00"),
                 epoch("2026-11-04T12:30:00")]
        report = partition_series("EURUSD", "M15", times)
        self.assertEqual(len(report["segments"]), 1)
        self.assertEqual(report["segments"][0]["bars"], 3)
        decision = require_contiguous_window("EURUSD", "M15", times, 0, 2)
        self.assertEqual(decision["status"], "CALENDAR_CONTIGUOUS_UNATTESTED")
        self.assertTrue(decision["calendar_contiguous"])
        self.assertFalse(decision["backtest_approved"])

    def test_gbpnzd_isolated_missing_day_is_barrier(self):
        times = [epoch("2025-09-29T00:00:00"), epoch("2025-10-01T00:00:00")]
        report = partition_series("GBPNZD", "D1", times)
        self.assertEqual([part["bars"] for part in report["segments"]], [1, 1])
        self.assertEqual(report["blocked_intervals"][0]["classification"],
                         "REVIEW_UNEXPLAINED")
        self.assertEqual(window_decision("GBPNZD", "D1", times, 0, 1)["status"],
                         "BLOCKED_UNVERIFIED_GAP")
        with self.assertRaisesRegex(GapGuardError, "UNVERIFIED_GAP_CROSSED"):
            require_contiguous_window("GBPNZD", "D1", times, 0, 1)

    def test_holiday_unverified_blocks_even_common_event(self):
        times = [epoch("2025-12-24T00:00:00"), epoch("2025-12-26T00:00:00")]
        self.assertFalse(window_decision("EURUSD", "D1", times, 0, 1)["calendar_contiguous"])

    def test_weekend_candidate_is_not_calendar_attestation(self):
        times = [epoch("2026-11-06T00:00:00"), epoch("2026-11-09T00:00:00")]
        p = partition_series("EURUSD", "D1", times)
        self.assertEqual(p["blocked_intervals"][0]["classification"], "WEEKEND_CANDIDATE")
        self.assertFalse(window_decision("EURUSD", "D1", times, 0, 1)["backtest_approved"])
        with self.assertRaises(GapGuardError):
            require_contiguous_window("EURUSD", "D1", times, 0, 1)

    def test_intraday_weekend_candidate_blocks(self):
        times = [epoch("2026-11-06T22:45:00"), epoch("2026-11-08T23:00:00")]
        self.assertEqual(partition_series("EURUSD", "M15", times)["blocked_intervals"][0]["classification"],
                         "WEEKEND_CANDIDATE")

    def test_missing_week_blocks(self):
        times = [epoch("2026-10-11T00:00:00"), epoch("2026-10-25T00:00:00")]
        self.assertFalse(window_decision("USDJPY", "W1", times, 0, 1)["calendar_contiguous"])

    def test_nominal_week_approval_is_still_false(self):
        times = [epoch("2026-10-18T00:00:00"), epoch("2026-10-25T00:00:00")]
        self.assertTrue(window_decision("USDJPY", "W1", times, 0, 1)["calendar_contiguous"])
        self.assertFalse(window_decision("USDJPY", "W1", times, 0, 1)["backtest_approved"])

    def test_partition_indices_around_gap(self):
        times = [epoch("2026-11-04T12:00:00"), epoch("2026-11-04T12:15:00"),
                 epoch("2026-11-04T12:45:00"), epoch("2026-11-04T13:00:00")]
        p = partition_series("EURUSD", "M15", times)
        self.assertEqual([(s["first_index"], s["last_index"]) for s in p["segments"]],
                         [(0, 1), (2, 3)])
        self.assertTrue(window_decision("EURUSD", "M15", times, 0, 1)["calendar_contiguous"])
        self.assertTrue(window_decision("EURUSD", "M15", times, 2, 3)["calendar_contiguous"])
        self.assertFalse(window_decision("EURUSD", "M15", times, 1, 2)["calendar_contiguous"])
        self.assertFalse(window_decision("EURUSD", "M15", times, 0, 3)["calendar_contiguous"])

    def test_off_grid_rejected(self):
        times = [epoch("2026-11-04T12:00:00"), epoch("2026-11-04T12:16:00")]
        with self.assertRaisesRegex(GapGuardError, "OFF_UTC_GRID"):
            partition_series("EURUSD", "M15", times)

    def test_duplicate_or_backward_rejected(self):
        t = epoch("2026-11-04T12:00:00")
        for times in ([t, t], [t + 900, t]):
            with self.subTest(times=times), self.assertRaises(GapGuardError):
                partition_series("EURUSD", "M15", times)

    def test_invalid_symbol_and_tf_rejected(self):
        t = epoch("2026-11-04T12:00:00")
        for symbol, tf in (("eurusd", "M15"), ("EURUSD", "H1"), ("123456", "M15")):
            with self.subTest(symbol=symbol, tf=tf), self.assertRaises(GapGuardError):
                partition_series(symbol, tf, [t, t + 900])

    def test_invalid_window_indices_rejected(self):
        t = epoch("2026-11-04T12:00:00")
        times = [t, t + 900]
        for a, b in ((0, 0), (-1, 1), (1, 2), (True, 1)):
            with self.subTest(a=a, b=b), self.assertRaises(GapGuardError):
                window_decision("EURUSD", "M15", times, a, b)

    def test_bad_timestamp_type_rejected(self):
        with self.assertRaises(GapGuardError):
            partition_series("EURUSD", "M15", [True, 1793794500])

    def test_missing_archive_fails_closed(self):
        report = audit_archive(Path("_no_mt5_archive_present_here"))
        self.assertEqual(report["status"], "BLOCKED_INVALID_ARCHIVE")
        self.assertFalse(report["backtest_approved"])
        self.assertEqual(report["series_partitions"], [])
        self.assertIn("FULL_ARCHIVE_INTEGRITY_REQUIRED", report["errors"])

    def test_synthetic_full_archive_integration_preserves_gbpnzd_barrier(self):
        """Recreate 28/84/103600 in a TEMP folder; never touch the AM12 files."""
        symbols = (
            "EURUSD GBPUSD AUDUSD NZDUSD USDJPY USDCHF USDCAD "
            "EURGBP EURJPY EURCHF EURCAD EURAUD EURNZD "
            "GBPJPY GBPCHF GBPCAD GBPAUD GBPNZD "
            "AUDJPY AUDCHF AUDCAD AUDNZD "
            "NZDJPY NZDCHF NZDCAD CADJPY CADCHF CHFJPY"
        ).split()
        frames = (("M15", 3000, datetime(2026, 9, 1, tzinfo=timezone.utc), 900),
                  ("D1", 500, datetime(2025, 1, 1, tzinfo=timezone.utc), 86400),
                  ("W1", 200, datetime(2023, 1, 1, tzinfo=timezone.utc), 604800))
        with TemporaryDirectory(prefix="atlasquant_guard_synthetic_") as directory:
            root = Path(directory)
            for batch in range(7):
                records = []
                for symbol in symbols[batch * 4: batch * 4 + 4]:
                    for tf, count, start, seconds in frames:
                        times = [int((start + timedelta(seconds=seconds * i)).timestamp())
                                 for i in range(count)]
                        if symbol == "GBPNZD" and tf == "D1":
                            cutoff = epoch("2025-09-30T00:00:00")
                            times = [t + (86400 if t >= cutoff else 0) for t in times]
                        buf = StringIO(newline="")
                        writer = csv.writer(buf, lineterminator="\n")
                        writer.writerow(("time_utc_epoch", "open", "high", "low", "close",
                                         "tick_volume", "spread", "real_volume"))
                        for t in times:
                            writer.writerow((t, "1", "2", "0.5", "1.5", "10", "1", "0"))
                        raw = buf.getvalue().encode("utf-8")
                        name = f"{symbol}_{tf}_closedbar.csv.gz"
                        (root / name).write_bytes(gzip.compress(raw, mtime=0))
                        records.append({
                            "symbol": symbol, "timeframe": tf, "requested": count,
                            "returned": count, "bar_position_start": 1,
                            "validation_errors": [], "snapshot_file": name,
                            "sha256_uncompressed_csv": sha256(raw).hexdigest(),
                            "earliest_open_utc": datetime.fromtimestamp(times[0], timezone.utc).isoformat(),
                            "latest_open_utc": datetime.fromtimestamp(times[-1], timezone.utc).isoformat(),
                        })
                (root / f"batch_{batch * 4:02d}_manifest.json").write_text(
                    json.dumps({"schema": "ATLASQUANT_MT5_CLOSED_BARS_LOCAL_LAB_V1",
                                "records": records}), encoding="utf-8")
            report = audit_archive(root)
            self.assertEqual(report["errors"], [])
            self.assertEqual((report["pairs"], report["files"], report["bars"]), (28, 84, 103600))
            self.assertEqual(report["blocked_interval_counts"], {"REVIEW_UNEXPLAINED": 1})
            self.assertEqual(report["segments_total"], 85)
            self.assertTrue(report["gbpnzd_2025_09_30_blocked"])
            self.assertEqual(report["status"], "BLOCKED_UNVERIFIED_GAPS")
            self.assertFalse(report["backtest_approved"])
            corrupted = root / "EURUSD_M15_closedbar.csv.gz"
            bytes_to_tamper = bytearray(corrupted.read_bytes())
            bytes_to_tamper[-12] ^= 1
            corrupted.write_bytes(bytes_to_tamper)
            rejected = audit_archive(root)
            self.assertEqual(rejected["status"], "BLOCKED_INVALID_ARCHIVE")
            self.assertFalse(rejected["backtest_approved"])
            self.assertEqual(rejected["series_partitions"], [])


@unittest.skipUnless(DEFAULT_ROOT.is_dir() and len(list(DEFAULT_ROOT.glob("batch_??_manifest.json"))) == 7,
                     "Original MT5 AM12 archive not available in this environment")
class ArchivedMT5Regression(unittest.TestCase):
    def test_real_archive_is_blocked_and_gbpnzd_remains_isolated(self):
        report = audit_archive(DEFAULT_ROOT)
        self.assertEqual(report["status"], "BLOCKED_UNVERIFIED_GAPS")
        self.assertEqual((report["pairs"], report["files"], report["bars"]), (28, 84, 103600))
        self.assertEqual(report["blocked_interval_counts"].get("WEEKEND_CANDIDATE"), 168 + 2800)
        self.assertEqual(report["blocked_interval_counts"].get("REVIEW_UNEXPLAINED"), 87)
        self.assertTrue(report["gbpnzd_2025_09_30_blocked"])
        self.assertEqual(report["segments_total"], 84 + 168 + 2800 + 87)
        self.assertFalse(report["backtest_approved"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
