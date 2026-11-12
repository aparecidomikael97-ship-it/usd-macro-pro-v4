"""Only synthetic M15 timestamps: NOT AM12 archive or broker proof."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import unittest

from atlasquant_trader_mt5_m15_ny17_coverage_lab import (
    inspect_m15_ny17_coverage_lab as inspect,
)

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
HASH = "a" * 64
EVALUATED = datetime(2026, 11, 20, tzinfo=UTC)


def ny(year, month, day, *, hour=17):
    return datetime(year, month, day, hour, tzinfo=NY).astimezone(UTC)


def full_epochs(start, end):
    total = int((end - start).total_seconds()) // 900
    return [int(start.timestamp()) + i * 900 for i in range(total)]


def audit(*, start=None, end=None, horizon="D1", pair="EUR/USD",
          epochs=None, captured=None, evaluated=EVALUATED, sha=HASH):
    start = ny(2026, 11, 8) if start is None else start
    end = ny(2026, 11, 9) if end is None else end
    epochs = full_epochs(start, end) if epochs is None else epochs
    captured = end + timedelta(minutes=2) if captured is None else captured
    return inspect(
        pair=pair, horizon=horizon, start_at_utc=start, end_at_utc=end,
        m15_candle_open_epochs=epochs, archive_captured_at_utc=captured,
        evaluated_at_utc=evaluated, source_sha256_claim=sha)


class Ny17M15CoverageTests(unittest.TestCase):
    def safe(self, r):
        for key in (
            "native_d1_utc_grid_is_ny17_equivalent",
            "native_w1_seven_day_bar_is_ny17_equivalent",
            "archive_original_bytes_supplied",
            "source_hash_independently_checked",
            "broker_m15_clock_independently_verified",
            "broker_session_calendar_independently_verified",
            "holiday_rollover_pauses_verified",
            "source_ohlc_independently_verified",
            "prediction_precommit_independently_verified",
            "historical_point_in_time_verified",
            "publishable", "can_feed_live_radar", "trade_authorized",
            "live_alert_allowed", "scheduler_enabled", "worker_enabled",
        ):
            self.assertFalse(r[key], key)
        self.assertIsNone(r["validated_directional_accuracy"])
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assertIsNone(r["observed_direction"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertEqual((r["http_requests"], r["file_writes"],
                          r["new_cost_brl"]), (0, 0, 0))
        self.assertTrue(r["research_only"])

    def test_sunday_monday_d1_96_bars_is_caller_claim_only(self):
        r = audit()
        self.assertEqual(r["state"], "LAB_M15_NY17_TIMESTAMP_COVERAGE_CLAIM_ONLY_NO_GO")
        self.assertEqual((r["m15_expected_candle_count"],
                          r["m15_received_candle_count"]), (96, 96))
        self.assertTrue(r["contiguous_ny17_m15_timestamps_claim_only"])
        self.assertEqual(r["archive_capture_utc_claim"],
                         ny(2026, 11, 9).replace(minute=2).isoformat())
        self.safe(r)

    def test_full_sunday_friday_week_is_480_m15_slots(self):
        start, end = ny(2026, 11, 8), ny(2026, 11, 13)
        r = audit(start=start, end=end, horizon="W1")
        self.assertEqual(r["state"], "LAB_M15_NY17_TIMESTAMP_COVERAGE_CLAIM_ONLY_NO_GO")
        self.assertEqual(r["m15_expected_candle_count"], 480)
        self.assertFalse(r["broker_session_calendar_independently_verified"])
        self.safe(r)

    def test_m15_gap_blocks_instead_of_fake_imputation(self):
        start, end = ny(2026, 11, 8), ny(2026, 11, 9)
        candles = full_epochs(start, end)
        candles.pop(43)
        r = audit(epochs=candles)
        self.assertEqual(r["state"], "LAB_M15_NY17_COVERAGE_BLOCKED")
        self.assertEqual(r["first_mismatch_index"], 43)
        self.assertEqual(r["reason"], "M15_MISSING_DUPLICATE_OR_WRONG_EPOCH")
        self.safe(r)

    def test_duplicate_m15_epoch_is_blocked(self):
        start, end = ny(2026, 11, 8), ny(2026, 11, 9)
        candles = full_epochs(start, end)
        candles[30] = candles[29]
        r = audit(epochs=candles)
        self.assertEqual(r["first_mismatch_index"], 30)
        self.safe(r)

    def test_wrong_open_epoch_shift_cannot_be_claimed_as_coverage(self):
        start, end = ny(2026, 11, 8), ny(2026, 11, 9)
        candles = [i + 900 for i in full_epochs(start, end)]
        r = audit(epochs=candles)
        self.assertEqual(r["first_mismatch_index"], 0)
        self.safe(r)

    def test_excess_bar_outside_end_rejected(self):
        start, end = ny(2026, 11, 8), ny(2026, 11, 9)
        candles = full_epochs(start, end)
        candles.append(int(end.timestamp()))
        r = audit(epochs=candles)
        self.assertEqual(r["reason"], "M15_EXCESS_EPOCHS_OUTSIDE_NY17_WINDOW")
        self.assertEqual(r["first_mismatch_index"], 96)
        self.safe(r)

    def test_invalid_boolean_epoch_not_accepted_as_int(self):
        start, end = ny(2026, 11, 8), ny(2026, 11, 9)
        candles = full_epochs(start, end)
        candles[12] = True
        r = audit(epochs=candles)
        self.assertEqual(r["first_mismatch_index"], 12)
        self.safe(r)

    def test_24h_utc_midnight_grid_is_not_ny17(self):
        start = datetime(2026, 11, 9, tzinfo=UTC)
        end = start + timedelta(days=1)
        r = audit(start=start, end=end)
        self.assertEqual(r["reason"],
                         "NONCANONICAL_FX_NY17_NOT_NEW_YORK_1700_CLOSE_BOUNDARY")
        self.safe(r)

    def test_seven_day_nominal_w1_is_not_fx_five_day_week(self):
        start = ny(2026, 11, 8)
        end = start + timedelta(days=7)
        r = audit(start=start, end=end, horizon="W1")
        self.assertIn("NONCANONICAL_FX_NY17_", r["reason"])
        self.safe(r)

    def test_spring_and_fall_dst_windows_follow_iana_new_york(self):
        for y, m, d, utc_hour in ((2026, 3, 8, 21), (2026, 11, 1, 22)):
            with self.subTest(month=m):
                start = ny(y, m, d)
                end = start + timedelta(days=1)
                r = audit(start=start, end=end)
                self.assertEqual(start.hour, utc_hour)
                self.assertEqual(r["m15_expected_candle_count"], 96)
                self.assertEqual(r["state"],
                                 "LAB_M15_NY17_TIMESTAMP_COVERAGE_CLAIM_ONLY_NO_GO")
                self.safe(r)

    def test_missing_snapshot_or_future_capture_must_not_look_historical(self):
        end = ny(2026, 11, 9)
        for captured, evaluated in (
            (end - timedelta(seconds=1), EVALUATED),
            (end + timedelta(minutes=1), end),
            (end + timedelta(minutes=1), end + timedelta(seconds=30)),
        ):
            with self.subTest(captured=captured):
                r = audit(captured=captured, evaluated=evaluated)
                self.assertEqual(r["state"], "LAB_M15_NY17_COVERAGE_BLOCKED")
                self.assertIsNone(r["archive_capture_utc_claim"])
                self.safe(r)

    def test_missing_or_fabricated_source_hash_is_never_proof(self):
        for sha in (None, "wrong", "B" * 64):
            r = audit(sha=sha)
            self.assertEqual(r["reason"], "INVALID_UNATTESTED_SOURCE_HASH_CLAIM")
            self.safe(r)
        r = audit(sha="f" * 64)
        self.assertEqual(r["state"], "LAB_M15_NY17_TIMESTAMP_COVERAGE_CLAIM_ONLY_NO_GO")
        self.assertFalse(r["source_hash_independently_checked"])
        self.safe(r)

    def test_wrong_pair_and_mn1_cannot_reuse_unverified_d1_w1_calendar(self):
        for kw in (
            {"pair": "XAU/USD"}, {"horizon": "MN1"},
            {"horizon": "M1"}, {"horizon": "M15"},
        ):
            with self.subTest(kw=kw):
                r = audit(**kw)
                self.assertEqual(r["state"], "LAB_M15_NY17_COVERAGE_BLOCKED")
                self.safe(r)

    def test_malformed_timestamps_are_blocked_before_coverage(self):
        for kw in (
            {"start": ny(2026, 11, 8).replace(tzinfo=None)},
            {"start": ny(2026, 11, 8).replace(microsecond=1)},
            {"end": ny(2026, 11, 8)},
        ):
            with self.subTest(kw=kw):
                # Invalid clocks must reach the fail-closed gate without
                # the synthetic fixture trying naive-aware subtraction.
                r = audit(epochs=[], **kw)
                self.assertEqual(r["state"], "LAB_M15_NY17_COVERAGE_BLOCKED")
                self.safe(r)


if __name__ == "__main__":
    unittest.main()
