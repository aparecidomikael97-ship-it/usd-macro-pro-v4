"""Synthetic AM12-style CSV.gz tests; no actual Pepperstone bars are loaded."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import gzip
from hashlib import sha256
from io import StringIO
import csv
import unittest

from atlasquant_trader_mt5_forward_label_gate_lab import (
    EXPECTED, FIELDS, MAX_GZIP_BYTES, MAX_RAW_BYTES, SECONDS,
    inspect_mt5_forward_label_lab as inspect,
)


def fixture(*, pair="EUR/USD", frame="D1", overrides=None, indexes=None,
            shift_from=None, shift_intervals=0):
    symbol = pair.replace("/", "")
    start_epoch = 1735689600
    n = EXPECTED[frame]
    times = [start_epoch + i * SECONDS[frame] for i in range(n)]
    if shift_from is not None:
        for idx in range(shift_from, n):
            times[idx] += shift_intervals * SECONDS[frame]
    if indexes:
        for idx, value in indexes.items():
            times[idx] = value
    rows = []
    for i, epoch in enumerate(times):
        closing = Decimal("1.00000") + Decimal(i) / Decimal(10000)
        rows.append({
            "time_utc_epoch": str(epoch), "open": str(closing),
            "high": str(closing + Decimal("0.00100")),
            "low": str(closing - Decimal("0.00100")), "close": str(closing),
            "tick_volume": "10", "spread": "2", "real_volume": "0",
        })
    if overrides:
        for index, changes in overrides.items():
            rows[index].update(changes)
    s = StringIO(newline="")
    writer = csv.DictWriter(s, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    raw = s.getvalue().encode("utf-8")
    manifest = {
        "symbol": symbol, "timeframe": frame,
        "snapshot_file": f"{symbol}_{frame}_closedbar.csv.gz",
        "bar_position_start": 1, "returned": n, "validation_errors": [],
        "sha256_uncompressed_csv": sha256(raw).hexdigest(),
        "earliest_open_utc": datetime.fromtimestamp(times[0], timezone.utc).isoformat(),
        "latest_open_utc": datetime.fromtimestamp(times[-1], timezone.utc).isoformat(),
    }
    return manifest, gzip.compress(raw, mtime=0), times


def run(*, pair="EUR/USD", frame="D1", manifest=None, packed=None,
        epoch_start=None, epoch_end=None):
    if manifest is None or packed is None:
        manifest0, packed0, epochs = fixture(pair=pair, frame=frame)
        manifest = manifest0 if manifest is None else manifest
        packed = packed0 if packed is None else packed
    else:
        epochs = None
    if epoch_start is None:
        epoch_start = epochs[250 if frame != "W1" else 100] if epochs else 1735689600
    if epoch_end is None:
        epoch_end = epoch_start + SECONDS.get(frame, 86400)
    return inspect(pair=pair, timeframe=frame, manifest_record=manifest,
                   compressed_csv_gz=packed,
                   entry_bar_open_epoch=epoch_start,
                   exit_bar_open_epoch=epoch_end)


class Mt5ForwardLabelGateLabTests(unittest.TestCase):
    def always_no_go(self, result):
        for key in ("broker_price_source_authenticated",
                    "mt5_candle_utc_time_independently_verified",
                    "historical_point_in_time_verified",
                    "decision_features_point_in_time_verified",
                    "precommitted_prediction_present",
                    "can_feed_validated_backtest", "publishable", "trade_authorized"):
            self.assertIs(result[key], False, key)
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["validated_accuracy"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertEqual((result["file_writes"], result["http_requests"],
                          result["new_cost_brl"]), (0, 0, 0))

    def blocked(self, result, reason):
        self.assertEqual(result["state"], "LAB_MT5_FORWARD_PRICE_LABEL_BLOCKED")
        self.assertEqual(result["reason"], reason)
        self.assertIsNone(result["forward_price_change_bps_documentary"])
        self.always_no_go(result)

    def test_synthetic_documentary_d1_m15_w1_moves_not_predictions(self):
        for frame in EXPECTED:
            with self.subTest(frame=frame):
                m, b, epochs = fixture(frame=frame)
                i = 100
                result = run(frame=frame, manifest=m, packed=b,
                             epoch_start=epochs[i], epoch_end=epochs[i + 1])
                self.assertEqual(result["state"],
                                 "LAB_MT5_FORWARD_PRICE_LABEL_DOCUMENTARY_UNATTESTED")
                self.assertEqual(result["observed_price_direction_only"], "UP")
                self.assertTrue(result["source_manifest_hash_self_consistent"])
                self.assertTrue(result["closed_bar_position_claim_only"])
                self.assertEqual(result["entry_close_price_documentary"], "1.01000")
                self.assertEqual(result["exit_close_price_documentary"], "1.01010")
                self.assertEqual(result["forward_price_change_bps_documentary"], "0.9901")
                self.always_no_go(result)

    def test_down_and_flat_are_historical_price_directions_only(self):
        for closes, expected in [(("1.2", "1.1"), "DOWN"),
                                (("1.2", "1.2"), "FLAT")]:
            m, b, epochs = fixture(overrides={100: {"close": closes[0], "high": "1.3", "low": "0.9"},
                                                    101: {"close": closes[1], "high": "1.3", "low": "0.9"}})
            result = run(manifest=m, packed=b,
                         epoch_start=epochs[100], epoch_end=epochs[101])
            self.assertEqual(result["observed_price_direction_only"], expected)
            self.always_no_go(result)

    def test_next_bar_body_can_disagree_with_close_to_close_gap(self):
        m, b, epochs = fixture(overrides={
            100: {"open": "1.02", "close": "1.02", "high": "1.03", "low": "1.00"},
            101: {"open": "1.00", "close": "1.01", "high": "1.02", "low": "0.99"},
        })
        result = run(manifest=m, packed=b,
                     epoch_start=epochs[100], epoch_end=epochs[101])
        self.assertEqual(result["state"],
                         "LAB_MT5_FORWARD_PRICE_LABEL_DOCUMENTARY_UNATTESTED")
        self.assertEqual(result["observed_price_direction_only"], "DOWN")
        self.assertEqual(result["observed_exit_bar_body_direction_only"], "UP")
        self.assertEqual(result["exit_bar_open_to_close_bps_documentary"], "100.0000")
        self.always_no_go(result)

    def test_manifests_cannot_change_pair_or_approved_timeframe(self):
        m, b, epochs = fixture()
        for field, bad in (("symbol", "USDJPY"), ("timeframe", "W1"),
                           ("snapshot_file", "../EURUSD.csv.gz"),
                           ("bar_position_start", 0), ("returned", 499),
                           ("validation_errors", ["untrusted"]),
                           ("sha256_uncompressed_csv", "fake")):
            with self.subTest(field=field):
                self.blocked(run(manifest={**m, field: bad}, packed=b),
                             "MANIFEST_SERIES_OR_CLOSED_BARS_CLAIM_INVALID")
        self.blocked(run(pair="USD/EUR", manifest=m, packed=b),
                     "UNSUPPORTED_PAIR_OR_TIMEFRAME")
        self.blocked(run(frame="M1", manifest=m, packed=b),
                     "UNSUPPORTED_PAIR_OR_TIMEFRAME")

    def test_zip_mutation_or_wrong_hash_rejected(self):
        m, b, epochs = fixture()
        self.blocked(run(manifest={**m, "sha256_uncompressed_csv": "a" * 64}, packed=b),
                     "ARCHIVE_MANIFEST_HASH_MISMATCH")
        self.blocked(run(manifest=m, packed=b[:-6]), "GZIP_DECOMPRESSION_FAILED")

    def test_non_monotonic_or_duplicate_epochs_rejected(self):
        for epoch in (1735689600 + 99 * 86400, 1735689600 + 98 * 86400):
            m, b, times = fixture(indexes={100: epoch})
            self.blocked(run(manifest=m, packed=b,
                             epoch_start=times[99], epoch_end=times[100]),
                         "NON_MONOTONIC_OR_DUPLICATE_BAR_TIMES")

    def test_gap_on_adjacent_rows_cannot_be_patched_or_silently_ignored(self):
        # Exact special-case type: GBP/NZD D1 remains a separate known coverage risk.
        m, b, epochs = fixture(pair="GBP/NZD", shift_from=101, shift_intervals=1)
        result = run(pair="GBP/NZD", manifest=m, packed=b,
                     epoch_start=epochs[100], epoch_end=epochs[101])
        self.blocked(result, "NON_NOMINAL_TIME_GAP_NO_IMPUTATION")

    def test_weekend_closure_and_weekly_non_nominal_gap_abstain(self):
        for frame in ("D1", "W1"):
            m, b, epochs = fixture(frame=frame, shift_from=101, shift_intervals=2)
            result = run(frame=frame, manifest=m, packed=b,
                         epoch_start=epochs[100], epoch_end=epochs[101])
            self.blocked(result, "NON_NOMINAL_TIME_GAP_NO_IMPUTATION")

    def test_non_adjacent_stored_bars_rejected_even_when_prices_exist(self):
        m, b, epochs = fixture()
        self.blocked(run(manifest=m, packed=b,
                         epoch_start=epochs[100], epoch_end=epochs[102]),
                     "BAR_NOT_FOUND_OR_NOT_ADJACENT")

    def test_bad_ohlc_or_negative_spread_or_nonfinite_price_rejected(self):
        cases = [({"high": "0.5"}, "OHLC_INCONSISTENT"),
                 ({"spread": "-2"}, "VOLUME_OR_SPREAD_INVALID"),
                 ({"close": "NaN"}, "INVALID_CSV_BAR_VALUES_OR_TIMESTAMPS")]
        for changes, reason in cases:
            with self.subTest(changes=changes):
                m, b, epochs = fixture(overrides={100: changes})
                self.blocked(run(manifest=m, packed=b,
                                 epoch_start=epochs[100], epoch_end=epochs[101]), reason)

    def test_manifest_time_tampering_rejected(self):
        m, b, epochs = fixture()
        self.blocked(run(manifest={**m, "latest_open_utc": "2026-01-01T00:00:00+00:00"},
                         packed=b), "MANIFEST_BAR_TIME_RANGE_MISMATCH")

    def test_csv_header_and_row_count_rejected_even_if_hash_matches(self):
        m, b, epochs = fixture()
        raw = gzip.decompress(b)
        for raw_bad, expected in ((raw.replace(b"tick_volume", b"tick_qty", 1),
                                   "CSV_HEADER_MISMATCH"),
                                  (raw[:raw.rfind(b"\n", 0, len(raw)-1)+1],
                                   "CSV_BAR_COUNT_MISMATCH")):
            changed_manifest = {**m, "sha256_uncompressed_csv": sha256(raw_bad).hexdigest()}
            self.blocked(run(manifest=changed_manifest,
                             packed=gzip.compress(raw_bad, mtime=0)), expected)

    def test_invalid_epoch_type_and_absent_archive_rejected(self):
        m, b, epochs = fixture()
        self.blocked(run(manifest=m, packed=b, epoch_start=True),
                     "INVALID_SELECTED_BAR_TIMESTAMPS")
        self.blocked(run(manifest=m, packed=b, epoch_start=100),
                     "BAR_NOT_FOUND_OR_NOT_ADJACENT")
        self.blocked(run(manifest=m, packed=b""),
                     "COMPRESSED_ARCHIVE_INVALID_OR_TOO_LARGE")
        self.blocked(run(manifest=m, packed=b"z" * (MAX_GZIP_BYTES + 1)),
                     "COMPRESSED_ARCHIVE_INVALID_OR_TOO_LARGE")

    def test_decompression_bomb_limit_stops_before_hash_claim(self):
        m, b, epochs = fixture()
        oversized = b"A" * (MAX_RAW_BYTES + 1)
        self.blocked(run(manifest={**m, "sha256_uncompressed_csv": sha256(oversized).hexdigest()},
                         packed=gzip.compress(oversized, mtime=0)),
                     "UNCOMPRESSED_ARCHIVE_TOO_LARGE")


if __name__ == "__main__":
    unittest.main()
