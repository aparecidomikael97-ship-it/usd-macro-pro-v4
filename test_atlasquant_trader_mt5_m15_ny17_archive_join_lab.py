"""Synthetic compressed AM12-style bars. No real Pepperstone archive."""
import csv
from datetime import datetime, timedelta, timezone
import gzip
from hashlib import sha256
from io import StringIO
import unittest
from zoneinfo import ZoneInfo

from atlasquant_trader_mt5_forward_label_gate_lab import FIELDS, EXPECTED
from atlasquant_trader_mt5_m15_ny17_archive_join_lab import (
    inspect_mt5_m15_archive_ny17_join_lab as inspect,
)

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
EVALUATED = datetime(2026, 12, 11, 0, 0, tzinfo=UTC)
N = EXPECTED["M15"]


def ny(day, *, hour=17):
    return datetime(2026, 11, day, hour, tzinfo=NY).astimezone(UTC)


def archive(*, pair="EUR/USD", missing_at=None, duplicate_at=None,
            malformed_at=None, off_grid_at=None):
    """Construct 3000 synthetic M15 bars, not a broker calendar."""
    start_epoch = int(ny(8).timestamp())
    times = []
    for i in range(N):
        stamp = start_epoch + i * 900
        if missing_at is not None and i >= missing_at:
            stamp += 900
        if duplicate_at is not None and i == duplicate_at:
            stamp = start_epoch + (i - 1) * 900
        if off_grid_at is not None and i == off_grid_at:
            stamp += 60  # still ordered; not a valid 15-minute opening
        times.append(stamp)
    s = StringIO(newline="")
    w = csv.DictWriter(s, fieldnames=FIELDS, lineterminator="\n")
    w.writeheader()
    for i, t in enumerate(times):
        row = {
            "time_utc_epoch": str(t), "open": "1.0000", "high": "1.0200",
            "low": "0.9900", "close": "1.0010", "tick_volume": "1",
            "spread": "2", "real_volume": "0",
        }
        if i == malformed_at:
            row["high"] = "0.1"
        w.writerow(row)
    raw = s.getvalue().encode("utf-8")
    symbol = pair.replace("/", "")
    manifest = {
        "symbol": symbol, "timeframe": "M15",
        "snapshot_file": f"{symbol}_M15_closedbar.csv.gz",
        "bar_position_start": 1,
        "returned": N, "validation_errors": [],
        "sha256_uncompressed_csv": sha256(raw).hexdigest(),
        "earliest_open_utc": datetime.fromtimestamp(times[0], UTC).isoformat(),
        "latest_open_utc": datetime.fromtimestamp(times[-1], UTC).isoformat(),
    }
    packed = gzip.compress(raw, mtime=0)
    captured = datetime.fromtimestamp(times[-1] + 901, UTC)
    return manifest, packed, captured


def inspect_case(*, manifest=None, packed=None, captured=None,
                 start=None, end=None, horizon="D1", pair="EUR/USD",
                 evaluated=EVALUATED):
    if manifest is None or packed is None or captured is None:
        default = archive(pair=pair)
        manifest = default[0] if manifest is None else manifest
        packed = default[1] if packed is None else packed
        captured = default[2] if captured is None else captured
    return inspect(
        pair=pair, horizon=horizon,
        start_at_utc=ny(8) if start is None else start,
        end_at_utc=ny(9) if end is None else end,
        manifest_record=manifest, compressed_csv_gz=packed,
        archive_captured_at_utc=captured, evaluated_at_utc=evaluated,
    )


class ArchiveJoinTests(unittest.TestCase):
    def safety(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["validated_accuracy"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertIsNone(r["market_direction_from_archive"])
        for flag in (
            "source_independently_authenticated",
            "source_broker_identity_verified",
            "broker_m15_epoch_timezone_independently_verified",
            "broker_session_calendar_verified",
            "holiday_gap_classification_verified",
            "source_ohlc_independently_verified",
            "history_point_in_time_verified",
            "model_prediction_externally_precommitted",
            "publishable", "can_feed_live_radar", "live_alert_allowed",
            "trade_authorized", "worker_enabled", "scheduler_enabled",
        ):
            self.assertFalse(r[flag], flag)
        self.assertEqual((r["external_http_requests"], r["file_writes"],
                          r["new_cost_brl"]), (0, 0, 0))
        self.assertTrue(r["research_only"])

    def test_synthetic_archive_links_96_ny17_daily_slots(self):
        m, gz, captured = archive()
        r = inspect_case(manifest=m, packed=gz, captured=captured)
        self.assertEqual(r["state"], "LAB_MT5_M15_ARCHIVE_NY17_LOCAL_JOIN_NO_GO")
        self.assertEqual(r["m15_rows_examined"], 3000)
        self.assertEqual(r["window_m15_rows_found"], 96)
        self.assertEqual(r["window_expected_m15_rows"], 96)
        self.assertTrue(r["manifest_local_hash_consistent"])
        self.assertTrue(r["csv_full_row_count_and_order_verified_locally"])
        self.assertTrue(r["window_coverage"][
            "contiguous_ny17_m15_timestamps_claim_only"])
        self.safety(r)

    def test_synthetic_archive_can_cover_480_weekly_slots(self):
        m, gz, captured = archive()
        r = inspect_case(
            manifest=m, packed=gz, captured=captured,
            horizon="W1", start=ny(8), end=ny(13))
        self.assertEqual(r["state"], "LAB_MT5_M15_ARCHIVE_NY17_LOCAL_JOIN_NO_GO")
        self.assertEqual(r["window_m15_rows_found"], 480)
        self.assertEqual(r["window_expected_m15_rows"], 480)
        self.safety(r)

    def test_gap_inside_daily_and_weekly_cannot_be_imputed(self):
        m, gz, captured = archive(missing_at=50)
        for horizon, end in (("D1", ny(9)), ("W1", ny(13))):
            with self.subTest(horizon=horizon):
                r = inspect_case(
                    manifest=m, packed=gz, captured=captured,
                    horizon=horizon, end=end)
                self.assertEqual(r["state"], "LAB_MT5_M15_ARCHIVE_NY17_JOIN_BLOCKED")
                self.assertIn("M15_NY17_COVERAGE_", r["reason"])
                self.assertEqual(r["first_mismatch_index"], 50)
                self.assertTrue(r["manifest_local_hash_consistent"])
                self.safety(r)

    def test_gap_outside_requested_window_does_not_imply_market_proof(self):
        m, gz, captured = archive(missing_at=110)
        r = inspect_case(manifest=m, packed=gz, captured=captured)
        self.assertEqual(r["state"], "LAB_MT5_M15_ARCHIVE_NY17_LOCAL_JOIN_NO_GO")
        self.assertFalse(r["broker_session_calendar_verified"])
        self.safety(r)

    def test_duplicate_archive_epoch_fails_even_with_matching_hash(self):
        m, gz, captured = archive(duplicate_at=100)
        r = inspect_case(manifest=m, packed=gz, captured=captured)
        self.assertEqual(r["reason"], "CSV_EPOCH_DUPLICATE_OR_NON_MONOTONIC")
        self.assertTrue(r["manifest_local_hash_consistent"])
        self.safety(r)

    def test_off_grid_m15_epoch_fails_even_outside_ny17_window(self):
        for index in (25, 120):
            with self.subTest(index=index):
                m, gz, captured = archive(off_grid_at=index)
                r = inspect_case(manifest=m, packed=gz, captured=captured)
                self.assertEqual(
                    r["reason"], "CSV_M15_EPOCH_NOT_ON_UTC_QUARTER_HOUR"
                )
                self.assertTrue(r["manifest_local_hash_consistent"])
                self.assertFalse(r["csv_full_row_count_and_order_verified_locally"])
                self.safety(r)

    def test_bad_ohlc_fails_even_when_manifest_hash_matches(self):
        m, gz, captured = archive(malformed_at=25)
        r = inspect_case(manifest=m, packed=gz, captured=captured)
        self.assertEqual(r["reason"], "CSV_OHLC_INCONSISTENT")
        self.safety(r)

    def test_hash_mismatch_blocks_with_no_tradable_result(self):
        m, gz, captured = archive()
        bad = {**m, "sha256_uncompressed_csv": "f" * 64}
        r = inspect_case(manifest=bad, packed=gz, captured=captured)
        self.assertEqual(r["reason"], "ARCHIVE_MANIFEST_LOCAL_HASH_MISMATCH")
        self.safety(r)

    def test_manifest_identity_and_claimed_closebars_must_match(self):
        m, gz, captured = archive()
        for changed in (
            {"symbol": "GBPUSD"}, {"timeframe": "D1"},
            {"returned": 2999}, {"bar_position_start": 0},
            {"validation_errors": ["gap"]},
        ):
            with self.subTest(changed=changed):
                r = inspect_case(
                    manifest={**m, **changed}, packed=gz, captured=captured)
                self.assertEqual(r["reason"],
                                 "MANIFEST_IDENTITY_OR_CLOSED_BAR_CLAIM_INVALID")
                self.safety(r)

    def test_wrong_manifest_range_is_rejected(self):
        m, gz, captured = archive()
        r = inspect_case(manifest={**m, "latest_open_utc": "2026-11-09T22:00:00+00:00"},
                         packed=gz, captured=captured)
        self.assertEqual(r["reason"], "MANIFEST_CSV_TIME_RANGE_MISMATCH")
        self.safety(r)

    def test_capture_before_latest_bar_close_rejected(self):
        m, gz, captured = archive()
        r = inspect_case(
            manifest=m, packed=gz, captured=captured - timedelta(minutes=20))
        self.assertEqual(r["reason"], "ARCHIVE_CAPTURE_BEFORE_LATEST_M15_CLOSE")
        self.safety(r)

    def test_no_future_data_or_unresolved_snapshot_claims(self):
        m, gz, captured = archive()
        for at in (captured - timedelta(seconds=1), ny(9)):
            with self.subTest(at=at):
                r = inspect_case(
                    manifest=m, packed=gz, captured=captured, evaluated=at)
                self.assertEqual(r["state"], "LAB_MT5_M15_ARCHIVE_NY17_JOIN_BLOCKED")
                self.safety(r)

    def test_wrong_calendar_rollover_utc_midnight_or_monthly_is_blocked(self):
        m, gz, captured = archive()
        start = datetime(2026, 11, 9, tzinfo=UTC)
        r = inspect_case(manifest=m, packed=gz, captured=captured,
                         start=start, end=start + timedelta(days=1))
        self.assertIn("NONCANONICAL_FX_NY17_", r["reason"])
        self.safety(r)
        r2 = inspect_case(manifest=m, packed=gz, captured=captured,
                          horizon="MN1")
        self.assertEqual(r2["state"], "LAB_MT5_M15_ARCHIVE_NY17_JOIN_BLOCKED")
        self.safety(r2)

    def test_corrupt_compressed_archive_is_blocked(self):
        m, gz, captured = archive()
        r = inspect_case(manifest=m, packed=b"bad gzip", captured=captured)
        self.assertEqual(r["reason"], "GZIP_CONTENTS_CORRUPT_OR_TOO_LARGE")
        self.safety(r)


if __name__ == "__main__":
    unittest.main()
