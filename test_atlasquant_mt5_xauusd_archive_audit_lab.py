"""Isolated XAUUSD archive audit tests; no real MT5, network or orders."""
from __future__ import annotations

import csv
import gzip
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from atlasquant_mt5_xauusd_archive_audit_lab import (
    audit_xauusd_closedbar_archive_lab as audit,
)
from atlasquant_mt5_xauusd_closedbar_capture_lab import (
    collect_xauusd_closedbar_snapshot_lab as collect,
)
from test_atlasquant_mt5_xauusd_closedbar_capture_lab import (
    AT, FakeMT5, WIN_TERMINAL,
)


class XauUsdArchiveAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="xauusd_audit_synthetic_")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "AtlasQuant" / "LAB" / "MT5_Snapshots"
        self.api = FakeMT5()
        created = collect(
            self.api, terminal_path=WIN_TERMINAL, output_root=self.root,
            clock=lambda: AT)
        self.assertEqual(created["verified_local_bars"], 3700)
        self.capture = Path(created["directory"])
        self.manifest_path = self.capture / "xauusd_manifest.json"

    def manifest(self):
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def replace_manifest(self, change):
        data = self.manifest()
        change(data)
        self.manifest_path.write_text(json.dumps(data), encoding="utf-8")

    def rewrite_csv(self, label, change, *, update_hash=True):
        name = f"XAUUSD_{label}_closedbar.csv.gz"
        path = self.capture / name
        content = gzip.decompress(path.read_bytes()).decode("utf-8")
        reader = csv.DictReader(StringIO(content))
        rows = list(reader)
        change(rows)
        buffer = StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=reader.fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        raw = buffer.getvalue().encode("utf-8")
        path.write_bytes(gzip.compress(raw, mtime=0))
        if update_hash:
            self.replace_manifest(
                lambda d: next(r for r in d["records"] if r["timeframe"] == label)
                .update(sha256_uncompressed_csv=sha256(raw).hexdigest()))

    def assert_blocked(self, *expected_substrings):
        result = audit(self.capture)
        self.assertEqual(result["status"], "LOCAL_XAUUSD_ARCHIVE_FAIL")
        self.assertTrue(result["errors"])
        self.assertTrue(any(any(word in error for word in expected_substrings)
                            for error in result["errors"]), result["errors"])
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["can_feed_live_radar"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")

    def test_success_confirms_3700_closed_bar_rows_without_attesting_broker(self):
        result = audit(self.capture)
        self.assertEqual(result["status"], "LOCAL_XAUUSD_ARCHIVE_INTEGRITY_PASS_UNATTESTED")
        self.assertEqual(result["verified_series"], 3)
        self.assertEqual(result["verified_bars"], 3700)
        self.assertEqual(set(result["timeframes"]), {"M15", "D1", "W1"})
        self.assertTrue(result["archive_read_only"])
        for key in ("archive_is_independently_authenticated",
                    "broker_identity_independently_authenticated",
                    "historical_point_in_time_verified", "can_feed_live_radar",
                    "trade_authorized", "publishable"):
            self.assertIs(result[key], False)
        self.assertIsNone(result["gold_bias"])

    def test_auditor_never_changes_any_capture_file(self):
        before = {p.name: sha256(p.read_bytes()).hexdigest()
                  for p in self.capture.iterdir()}
        self.assertFalse(audit(self.capture)["errors"])
        self.assertEqual(before, {p.name: sha256(p.read_bytes()).hexdigest()
                                  for p in self.capture.iterdir()})

    def test_refuses_missing_file(self):
        (self.capture / "XAUUSD_W1_closedbar.csv.gz").unlink()
        self.assert_blocked("ARCHIVE_FILE_SET_INCOMPLETE")

    def test_refuses_unexpected_file_in_incomplete_run(self):
        (self.capture / "unexpected.txt").write_text("no", encoding="utf-8")
        self.assert_blocked("ARCHIVE_FILE_SET_INCOMPLETE")

    def test_hash_mismatch_detects_single_csv_change(self):
        self.rewrite_csv("M15", lambda rows: rows[7].update(close="3500"),
                         update_hash=False)
        self.assert_blocked("ARCHIVE_SHA256_MISMATCH")

    def test_rehashed_invalid_ohlc_still_blocked(self):
        self.rewrite_csv("D1", lambda rows: rows[7].update(high="1"))
        self.assert_blocked("CSV_OHLC_INVALID")

    def test_rehashed_reordered_timestamps_still_blocked(self):
        self.rewrite_csv("W1", lambda rows: rows[10].update(
            time_utc_epoch=rows[9]["time_utc_epoch"]))
        self.assert_blocked("CSV_EPOCH_ORDER_OR_FUTURE")

    def test_rehashed_invalid_volume_still_blocked(self):
        self.rewrite_csv("M15", lambda rows: rows[12].update(tick_volume="-2"))
        self.assert_blocked("CSV_VOLUME_OR_SPREAD_INVALID")

    def test_rehashed_future_timestamp_still_blocked(self):
        self.rewrite_csv("M15", lambda rows: rows[-1].update(
            time_utc_epoch=str(int(AT.timestamp()) + 300)))
        self.assert_blocked("CSV_EPOCH_ORDER_OR_FUTURE")

    def test_manifest_wrong_instrument_blocked(self):
        self.replace_manifest(lambda d: d.update(canonical_id="FX:XAUUSD"))
        self.assert_blocked("MANIFEST_SAFETY_OR_INSTRUMENT_SCHEMA_INVALID")

    def test_manifest_claims_trading_authorized_blocked(self):
        self.replace_manifest(lambda d: d.update(trade_authorized=True))
        self.assert_blocked("MANIFEST_SAFETY_OR_INSTRUMENT_SCHEMA_INVALID")

    def test_manifest_wrong_count_blocked(self):
        self.replace_manifest(lambda d: d["records"][0].update(returned=2999))
        self.assert_blocked("RECORD_SCHEMA_OR_CLOSED_BAR_COUNT")

    def test_duplicate_timeframe_blocked(self):
        self.replace_manifest(lambda d: d["records"][1].update(timeframe="M15"))
        self.assert_blocked("MANIFEST_DUPLICATE_OR_UNEXPECTED_TIMEFRAME")

    def test_unhashable_malformed_timeframe_blocked_without_crash(self):
        self.replace_manifest(lambda d: d["records"][1].update(timeframe=["D1"]))
        self.assert_blocked("MANIFEST_DUPLICATE_OR_UNEXPECTED_TIMEFRAME")

    def test_manifest_capture_clock_must_match_directory(self):
        self.replace_manifest(lambda d: d.update(
            captured_at_utc_local_clock_claim="2026-11-10T13:00:00+00:00"))
        self.assert_blocked("MANIFEST_CAPTURE_CLOCK_INVALID")

    def test_manifest_gaps_cannot_be_silently_rewritten(self):
        self.replace_manifest(lambda d: d["records"][0].update(
            larger_than_nominal_gaps_needing_calendar_review=9999))
        self.assert_blocked("MANIFEST_TIME_OR_GAP_METADATA_MISMATCH")

    def test_symlink_csv_is_refused(self):
        source = self.capture / "XAUUSD_D1_closedbar.csv.gz"
        copy = Path(self.tmp.name) / "outside.csv.gz"
        copy.write_bytes(source.read_bytes())
        source.unlink()
        source.symlink_to(copy)
        self.assert_blocked("ARCHIVE_FILE_MISSING_OR_SYMLINK")

    def test_wrong_non_gold_snapshot_directory_is_rejected(self):
        result = audit(self.root)
        self.assertEqual(result["status"], "LOCAL_XAUUSD_ARCHIVE_FAIL")
        self.assertIn("CAPTURE_DIRECTORY_NOT_ISOLATED_XAUUSD_LAB", result["errors"])

    def test_broken_gzip_blocks(self):
        (self.capture / "XAUUSD_M15_closedbar.csv.gz").write_bytes(b"broken")
        self.assert_blocked("GZIP_UNREADABLE")

    def test_bomb_guard_blocks_excess_decompressed_data(self):
        (self.capture / "XAUUSD_M15_closedbar.csv.gz").write_bytes(
            gzip.compress(b"0" * 3_000_001))
        self.assert_blocked("DECOMPRESSED_CSV_OVERSIZED")


if __name__ == "__main__":
    unittest.main()
