"""Synthetic 28-FX D1 archive-byte custody -> seven-stage precision veto tests.

Synthetic dates/prices are NOT actual FX markets, broker provenance or backtests.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import gzip
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from atlasquant_trader_fx_d1_archive_precision_join_lab import (
    ROWS_D1, inspect_d1_archive_precision_join_lab as inspect,
)
from atlasquant_trader_precision_gate_orchestrator_lab import FX28_CANONICAL_SYMBOLS
from test_atlasquant_trader_precision_gate_orchestrator_lab import (
    DECISION, NOW, fixture,
)

COVERAGE_DAY = date(2026, 11, 10)
CAPTURE = DECISION - timedelta(minutes=20)
FIELDS = "time_utc_epoch,open,high,low,close,tick_volume,spread,real_volume\n"


def synthetic_archive(root: Path, *, gbpnzd_missing: bool = False):
    """Create only test fixtures; 7 snapshot manifests, 28 gzip D1 CSVs."""
    records: dict[str, dict] = {}
    for symbol in FX28_CANONICAL_SYMBOLS:
        first = COVERAGE_DAY - timedelta(days=ROWS_D1-1)
        days = [first + timedelta(days=i) for i in range(ROWS_D1)]
        if gbpnzd_missing and symbol == "GBPNZD":
            days = [first - timedelta(days=1)] + days[:-1]
        rows = [FIELDS]
        for day in days:
            epoch = int(datetime.combine(day, datetime.min.time(),
                                         timezone.utc).timestamp())
            rows.append(f"{epoch},1.1,1.2,1.0,1.11,80,12,0\n")
        raw = "".join(rows).encode("utf-8")
        name = f"{symbol}_D1_closedbar.csv.gz"
        (root / name).write_bytes(gzip.compress(raw))
        records[symbol] = {
            "symbol": symbol, "timeframe": "D1",
            "snapshot_file": name, "requested": ROWS_D1, "returned": ROWS_D1,
            "bar_position_start": 1, "validation_errors": [],
            "sha256_uncompressed_csv": sha256(raw).hexdigest(),
            "observed_at_utc": CAPTURE.isoformat(),
            "earliest_open_utc": datetime.combine(days[0], datetime.min.time(),
                                                  timezone.utc).isoformat(),
            "latest_open_utc": datetime.combine(days[-1], datetime.min.time(),
                                                timezone.utc).isoformat(),
        }
    for offset in range(0, 28, 4):
        slots = []
        for symbol in FX28_CANONICAL_SYMBOLS[offset:offset+4]:
            for tf in ("M15", "D1", "W1"):
                slots.append(records[symbol] if tf == "D1" else
                             {"symbol": symbol, "timeframe": tf})
        doc = {
            "schema": "ATLASQUANT_MT5_CLOSED_BARS_LOCAL_LAB_V1",
            "research_only": True, "trade_authorized": False,
            "broker_identity_independently_verified": False,
            "historical_point_in_time_verified": False,
            "batch_start": offset, "batch_count": 4,
            "record_count": len(slots), "records": slots,
        }
        (root / f"batch_{offset:02d}_manifest.json").write_text(
            json.dumps(doc), encoding="utf-8")


def change_manifest(root: Path, offset: int, transform):
    path = root / f"batch_{offset:02d}_manifest.json"
    doc = json.loads(path.read_text("utf-8"))
    transform(doc)
    path.write_text(json.dumps(doc), encoding="utf-8")


class D1ArchivePrecisionJoinTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        synthetic_archive(self.root)

    def check(self, packet=None, as_of=NOW):
        out = inspect(
            archive_root=self.root,
            packet=fixture() if packet is None else packet,
            inspected_at_utc=as_of,
        )
        self.assertEqual(out["operational_bias"], "AGUARDAR")
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["publishable"])
        self.assertFalse(out["live_alert_allowed"])
        self.assertFalse(out["source_and_historical_capture_independently_attested"])
        self.assertFalse(out["market_data_pit_independently_verified"])
        self.assertFalse(out["calendar_and_ny_close_broker_verified"])
        self.assertIsNone(out["validated_directional_accuracy"])
        self.assertIsNone(out["calibrated_direction_probability"])
        self.assertEqual((out["http_requests"], out["file_writes"], out["new_cost_brl"]),
                         (0, 0, 0))
        return out

    def test_all_28_sha_bound_reaches_research_only_never_trade(self):
        out = self.check()
        self.assertEqual(out["state"], "LAB_D1_ARCHIVE_PRECISION_DOCUMENTARY_CANDIDATE_NO_GO")
        self.assertEqual(out["manifest_records_reconciled"], 84)
        self.assertEqual(out["d1_archive_series_bytes_matched"], 28)
        self.assertEqual(out["d1_archive_bars_checked"], 14000)
        self.assertEqual(out["d1_date_coverage_from_archive"]["present"], 28)
        self.assertEqual(len(out["precision_stage_reports"]), 7)
        self.assertEqual(out["research_candidate_direction"], "BAIXA")
        self.assertEqual(out["latest_archive_capture_at_utc_claim"], CAPTURE.isoformat())
        self.assertFalse(out["market_data_pit_independently_verified"])

    def test_gbpnzd_missing_from_actual_csv_cannot_claim_full_cohort(self):
        synthetic_archive(self.root, gbpnzd_missing=True)
        out = self.check(replace(fixture(), d1_coverage_present_symbols=None))
        self.assertEqual(out["state"], "LAB_D1_ARCHIVE_PRECISION_ABSTAIN")
        self.assertEqual(out["d1_date_coverage_from_archive"]["present"], 27)
        self.assertEqual(out["d1_date_coverage_from_archive"]["missing"], ["GBPNZD"])
        self.assertEqual(out["precision_stage_reports"]["D1_28FX_DATE_COVERAGE"]["state"],
                         "LAB_SINGLE_PAIR_D1_MISSING_DATE_QUARANTINE")
        self.assertIsNone(out["research_candidate_direction"])

    def test_claimed_28_but_archive_only_27_rejected_as_disagreement(self):
        synthetic_archive(self.root, gbpnzd_missing=True)
        out = self.check()
        self.assertEqual(out["state"], "LAB_D1_ARCHIVE_PRECISION_JOIN_BLOCKED")
        self.assertEqual(out["reason"], "CALLER_COVERAGE_DISAGREES_WITH_ARCHIVED_CSV_DATES")

    def test_rewritten_manifest_digest_blocks_consistent_price_history(self):
        def mutate(doc):
            for entry in doc["records"]:
                if entry["symbol"] == "EURUSD" and entry["timeframe"] == "D1":
                    entry["sha256_uncompressed_csv"] = "f" * 64
        change_manifest(self.root, 0, mutate)
        out = self.check()
        self.assertIn("D1_CSV_SHA256_DOES_NOT_MATCH_MANIFEST", out["reason"])
        self.assertIsNone(out["precision_stage_reports"])

    def test_archive_captured_after_decision_is_not_historical_proof(self):
        def mutate(doc):
            for entry in doc["records"]:
                if entry["symbol"] == "EURUSD" and entry["timeframe"] == "D1":
                    entry["observed_at_utc"] = (DECISION + timedelta(minutes=10)).isoformat()
        change_manifest(self.root, 0, mutate)
        out = self.check()
        self.assertIn("INVALID_OR_LATE_D1_MANIFEST_OR_ARCHIVE", out["reason"])
        self.assertIsNone(out["research_candidate_direction"])

    def test_archive_capture_before_last_candle_close_is_invalid(self):
        def mutate(doc):
            for entry in doc["records"]:
                if entry["symbol"] == "EURUSD" and entry["timeframe"] == "D1":
                    entry["observed_at_utc"] = (
                        datetime(2026, 11, 10, 8, tzinfo=timezone.utc).isoformat())
        change_manifest(self.root, 0, mutate)
        out = self.check()
        self.assertIn("D1_ARCHIVE_CAPTURE_PREDATES_BAR_CLOSE", out["reason"])

    def test_replacing_gzip_file_rejected(self):
        path = self.root / "EURUSD_D1_closedbar.csv.gz"
        path.write_bytes(gzip.compress(FIELDS.encode("utf-8")))
        out = self.check()
        self.assertIn("D1_CSV_SHA256_DOES_NOT_MATCH_MANIFEST", out["reason"])

    def test_missing_d1_file_blocks_whole_census(self):
        (self.root / "GBPUSD_D1_closedbar.csv.gz").unlink()
        out = self.check()
        self.assertIn("INVALID_OR_LATE_D1_MANIFEST_OR_ARCHIVE", out["reason"])

    def test_missing_manifest_blocks_before_six_macro_stages(self):
        (self.root / "batch_08_manifest.json").unlink()
        out = self.check()
        self.assertIn("MISSING_OR_UNSAFE_MANIFEST", out["reason"])
        self.assertIsNone(out["precision_stage_reports"])

    def test_duplicate_manifest_record_rejected(self):
        def mutate(doc):
            doc["records"][1] = dict(doc["records"][0])
        change_manifest(self.root, 0, mutate)
        out = self.check()
        self.assertIn("DUPLICATED_OR_UNKNOWN_COHORT_SLOT", out["reason"])

    def test_caller_timestamp_override_cannot_relabel_archive(self):
        out = self.check(replace(
            fixture(), d1_coverage_observed_at_utc=CAPTURE-timedelta(minutes=5)))
        self.assertEqual(out["reason"], "CALLER_CAPTURE_TIME_DISAGREES_WITH_MANIFESTS")

    def test_missing_caller_attendance_is_derived_from_actual_csv(self):
        packet = replace(fixture(), d1_coverage_present_symbols=None,
                         d1_coverage_observed_at_utc=None)
        out = self.check(packet)
        self.assertEqual(out["d1_date_coverage_from_archive"]["present"], 28)
        self.assertEqual(out["state"], "LAB_D1_ARCHIVE_PRECISION_DOCUMENTARY_CANDIDATE_NO_GO")

    def test_naive_asof_clock_never_passes(self):
        out = self.check(as_of=NOW.replace(tzinfo=None))
        self.assertEqual(out["reason"], "INVALID_ARCHIVE_PACKET_OR_CLOCK")

    def test_cannot_substitute_different_trading_date(self):
        p = replace(fixture(), d1_coverage_trading_date=date(2026, 11, 9),
                    d1_coverage_present_symbols=None)
        out = self.check(p)
        self.assertEqual(out["d1_date_coverage_from_archive"]["present"], 28)
        self.assertEqual(out["state"], "LAB_D1_ARCHIVE_PRECISION_DOCUMENTARY_CANDIDATE_NO_GO")
        self.assertFalse(out["market_data_pit_independently_verified"])

    def test_all_csv_files_are_never_modified(self):
        file = self.root / "EURUSD_D1_closedbar.csv.gz"
        before = sha256(file.read_bytes()).hexdigest()
        self.check()
        self.assertEqual(sha256(file.read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()
