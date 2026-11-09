"""Synthetic-only, read-only regression tests of MT5 closed-bar label custody."""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO, StringIO
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from atlasquant_trader_mt5_closedbar_outcome_lab import (
    inspect_mt5_closedbar_outcome_lab as inspect, COLUMNS, MT5_SCHEMA,
)

UTC = timezone.utc
PRED_HASH = "a" * 64
OBSERVED = datetime(2026, 11, 7, 10, tzinfo=UTC)
AS_OF = datetime(2026, 11, 8, 12, tzinfo=UTC)


class ArchivedOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.symbol = "EURUSD"
        self.horizon = "W1"
        self.start = datetime(2023, 1, 1, tzinfo=UTC)
        self.step = timedelta(days=7)
        self.count = 200
        self.rows = self.generate()
        self.commit_fixture()

    def generate(self):
        result = []
        for i in range(self.count):
            opened = self.start + i * self.step
            price = 100 + i
            result.append({
                "time_utc_epoch": str(int(opened.timestamp())),
                "open": str(price), "high": str(price + 2),
                "low": str(price - 1), "close": str(price + 1),
                "tick_volume": "1", "spread": "2", "real_volume": "0",
            })
        return result

    def commit_fixture(self, *, omit_file=False):
        buf = StringIO(newline="")
        writer = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(self.rows)
        raw = buf.getvalue().encode("utf-8")
        self.raw = raw
        archive = self.root / f"{self.symbol}_{self.horizon}_closedbar.csv.gz"
        if not omit_file:
            with archive.open("wb") as f:
                with gzip.GzipFile(fileobj=f, mode="wb", mtime=0) as gz:
                    gz.write(raw)
        record = {
            "symbol": self.symbol, "timeframe": self.horizon,
            "requested": self.count, "returned": self.count,
            "bar_position_start": 1,
            "observed_at_utc": OBSERVED.isoformat(),
            "earliest_open_utc": datetime.fromtimestamp(int(self.rows[0]["time_utc_epoch"]),UTC).isoformat(),
            "latest_open_utc": datetime.fromtimestamp(int(self.rows[-1]["time_utc_epoch"]),UTC).isoformat(),
            "validation_errors": [],
            "sha256_uncompressed_csv": sha256(raw).hexdigest(),
            "snapshot_file": archive.name,
        }
        self.record = record
        for i in range(7):
            doc = {
                "schema": MT5_SCHEMA, "research_only": True, "trade_authorized": False,
                "prediction_available": False,
                "broker_identity_independently_verified": False,
                "historical_point_in_time_verified": False,
                "records": [record] if i == 0 else [],
            }
            (self.root/f"batch_{4*i:02d}_manifest.json").write_text(json.dumps(doc), encoding="utf-8")

    def args(self, idx=-1):
        opening = datetime.fromtimestamp(int(self.rows[idx]["time_utc_epoch"]), UTC)
        return {
            "archive_root": self.root, "symbol": self.symbol, "horizon": self.horizon,
            "target_open_epoch": int(self.rows[idx]["time_utc_epoch"]),
            "decided_at": opening - timedelta(hours=4),
            "prediction_locked_at": opening - timedelta(hours=5),
            "as_of_utc": AS_OF, "prediction_sha256_claim": PRED_HASH,
        }

    def blocked(self, data, reason=None):
        self.assertEqual(data["state"], "LAB_MT5_OUTCOME_BLOCKED")
        if reason:
            self.assertEqual(data["reason"], reason)
        self.assertIsNone(data["outcome_direction_documentary"])
        self.assertFalse(data["raw_csv_sha256_verified"])
        self.no_live(data)

    def no_live(self, data):
        self.assertEqual(data["operational_bias"], "AGUARDAR")
        self.assertFalse(data["publishable"])
        self.assertFalse(data["live_alert_allowed"])
        self.assertFalse(data["trade_authorized"])
        self.assertFalse(data["worker_enabled"])
        self.assertFalse(data["scheduler_enabled"])
        self.assertFalse(data["broker_calendar_verified"])
        self.assertFalse(data["market_price_vintage_at_decision_verified"])
        self.assertFalse(data["prediction_precommit_externally_attested"])
        self.assertFalse(data["historical_directional_accuracy_validated"])
        self.assertIsNone(data["calibrated_direction_probability"])
        self.assertFalse(data["full_archive_84_series_reaudited_here"])
        self.assertEqual((data["http_requests"],data["new_cost_brl"],data["file_writes"]),(0,0,0))

    def test_weekly_up_bar_documented_not_signal(self):
        data = inspect(**self.args())
        self.assertEqual(data["state"], "LAB_ARCHIVED_BAR_DOCUMENTARY_ONLY_NO_GO")
        self.assertEqual(data["asset"], "EUR/USD")
        self.assertEqual(data["horizon"], "W1")
        self.assertEqual(data["outcome_direction_documentary"], "ALTA")
        self.assertTrue(data["raw_csv_sha256_verified"])
        self.assertTrue(data["target_prior_edge_nominal"])
        self.assertEqual(data["start_price_documentary"], "299")
        self.assertEqual(data["end_price_documentary"], "300")
        self.no_live(data)

    def test_down_and_flat_are_documentary_not_trade(self):
        for close, expected in (("298", "BAIXA"), ("299", "SEM_VARIACAO")):
            with self.subTest(close=close):
                self.rows[-1]["close"] = close
                self.commit_fixture()
                data = inspect(**self.args())
                self.assertEqual(data["outcome_direction_documentary"], expected)
                self.no_live(data)

    def test_dual_clock_lookahead_and_naive(self):
        opts = self.args()
        for changes in (
            {"prediction_locked_at": opts["decided_at"] + timedelta(minutes=1)},
            {"decided_at": datetime.fromtimestamp(opts["target_open_epoch"],UTC)},
            {"prediction_locked_at": opts["prediction_locked_at"].replace(tzinfo=None)},
            {"as_of_utc": datetime(2026,10,31,tzinfo=UTC)},
            {"as_of_utc": AS_OF.replace(tzinfo=None)},
            {"prediction_sha256_claim": "invalid"},
            {"target_open_epoch": True},
        ):
            with self.subTest(change=changes):
                self.blocked(inspect(**(opts | changes)),"INVALID_INPUT_OR_CHRONOLOGY")

    def test_wrong_pair_timeframe_and_unsafe_parameters(self):
        opts=self.args()
        for change in ({"symbol":"USD/EUR"},{"symbol":"../EURUSD"},{"horizon":"M15"},
                       {"horizon":"MN1"},{"archive_root":None},{"target_open_epoch":-3}):
            with self.subTest(change=change):
                self.blocked(inspect(**(opts|change)))

    def test_missing_manifest_and_missing_snapshot(self):
        (self.root/"batch_24_manifest.json").unlink()
        self.blocked(inspect(**self.args()),"REQUIRES_SEVEN_BATCH_MANIFESTS")
        self.commit_fixture()
        (self.root/f"{self.symbol}_{self.horizon}_closedbar.csv.gz").unlink()
        self.blocked(inspect(**self.args()),"SNAPSHOT_FILE_MISSING_OR_UNSAFE")

    def test_gzip_tamper_detected(self):
        file=self.root/f"{self.symbol}_{self.horizon}_closedbar.csv.gz"
        with file.open("wb") as f:
            with gzip.GzipFile(fileobj=f,mode="wb",mtime=0) as gz:
                gz.write(self.raw.replace(b"299,301",b"299,302"))
        self.blocked(inspect(**self.args()),"SNAPSHOT_HASH_MISMATCH")

    def test_compressed_truncated_detected(self):
        path=self.root/f"{self.symbol}_{self.horizon}_closedbar.csv.gz"
        payload=path.read_bytes()
        path.write_bytes(payload[:-8])
        self.blocked(inspect(**self.args()),"SNAPSHOT_GZIP_CORRUPT")

    def test_claimed_manifest_hash_cannot_authorize_bad_ohlc(self):
        self.rows[-1]["high"]="1"
        self.commit_fixture()
        self.blocked(inspect(**self.args()),"CSV_BAD_OHLC")

    def test_wrong_field_schema(self):
        self.rows[-1]["spread"]="-1"
        self.commit_fixture()
        self.blocked(inspect(**self.args()),"CSV_INVALID_VOLUME_OR_SPREAD")

    def test_duplicate_timestamp_detected_even_with_fresh_hash(self):
        self.rows[-1]["time_utc_epoch"]=self.rows[-2]["time_utc_epoch"]
        self.commit_fixture()
        self.blocked(inspect(**self.args()),"CSV_TIME_NOT_MONOTONIC")

    def test_gap_adjacent_to_target_is_blocked(self):
        # A missing/unverified interval directly before the target is never filled.
        self.rows[-2]["time_utc_epoch"]=str(int(self.rows[-2]["time_utc_epoch"])-86400)
        self.commit_fixture()
        self.blocked(inspect(**self.args()),"UNVERIFIED_GAP_DIRECTLY_BEFORE_TARGET")

    def test_missing_target_bar_blocks(self):
        opts=self.args()
        opts["target_open_epoch"]-=2*86400
        opening=datetime.fromtimestamp(opts["target_open_epoch"],UTC)
        opts["decided_at"]=opening-timedelta(hours=4)
        opts["prediction_locked_at"]=opening-timedelta(hours=5)
        self.blocked(inspect(**opts),"TARGET_BAR_NOT_IN_ARCHIVE")

    def test_capture_future_or_before_close_not_valid(self):
        self.record["observed_at_utc"]="2026-10-26T10:00:00+00:00"
        # commit_fixture replaces record, so directly patch the manifest document.
        f=self.root/"batch_00_manifest.json"
        obj=json.loads(f.read_text())
        obj["records"][0]["observed_at_utc"]="2026-10-26T10:00:00+00:00"
        f.write_text(json.dumps(obj))
        self.blocked(inspect(**self.args()),"CAPTURE_BEFORE_TARGET_CLOSE_OR_FUTURE")

    def test_same_pair_duplicate_across_manifest_blocks(self):
        obj=json.loads((self.root/"batch_00_manifest.json").read_text())
        (self.root/"batch_04_manifest.json").write_text(json.dumps(obj))
        self.blocked(inspect(**self.args()),"DUPLICATE_MANIFEST_SERIES")

    def test_manifests_with_duplicate_json_keys_block(self):
        f=self.root/"batch_00_manifest.json"
        f.write_text('{"schema":"x","schema":"y"}',encoding="utf-8")
        self.blocked(inspect(**self.args()),"DUPLICATE_JSON_KEY")

    def test_symlink_to_archive_blocks(self):
        path=self.root/f"{self.symbol}_{self.horizon}_closedbar.csv.gz"
        other=self.root/"other.gz"
        path.rename(other)
        try:
            path.symlink_to(other)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable on this OS")
        self.blocked(inspect(**self.args()),"SNAPSHOT_FILE_MISSING_OR_UNSAFE")

    def test_d1_history_uses_500_bars_and_open_close(self):
        self.symbol="GBPNZD";self.horizon="D1";self.start=datetime(2025,6,10,tzinfo=UTC)
        self.step=timedelta(days=1);self.count=500;self.rows=self.generate();self.commit_fixture()
        # File's last date is 2026-10-22, before capture.
        data=inspect(**self.args())
        self.assertEqual(data["state"],"LAB_ARCHIVED_BAR_DOCUMENTARY_ONLY_NO_GO")
        self.assertEqual(data["asset"],"GBP/NZD")
        self.assertEqual(data["horizon"],"D1")
        self.no_live(data)

    def test_manifest_claiming_verified_broker_is_rejected(self):
        f=self.root/"batch_00_manifest.json"
        obj=json.loads(f.read_text())
        obj["broker_identity_independently_verified"]=True
        f.write_text(json.dumps(obj))
        self.blocked(inspect(**self.args()),"MANIFEST_SCHEMA_OR_PROVENANCE_INVALID")

    def test_unfinished_target_and_missing_decision(self):
        opts=self.args()
        self.blocked(inspect(**(opts|{"decided_at":None})))
        self.blocked(inspect(**(opts|{"as_of_utc":datetime(2026,10,30,tzinfo=UTC)})))


    def test_known_gbpnzd_september_gap_synthetic_case(self):
        # Replicates the missing 2025-09-30 daily timestamp pattern, NOT its prices.
        self.symbol="GBPNZD";self.horizon="D1"
        self.start=datetime(2024,7,1,tzinfo=UTC)
        self.step=timedelta(days=1);self.count=500;self.rows=self.generate()
        gap_epoch=int(datetime(2025,9,30,tzinfo=UTC).timestamp())
        self.rows=[r for r in self.rows if int(r["time_utc_epoch"]) != gap_epoch]
        last=dict(self.rows[-1]);last["time_utc_epoch"]=str(int(last["time_utc_epoch"])+86400)
        self.rows.append(last)
        self.commit_fixture()
        target=int(datetime(2025,10,1,tzinfo=UTC).timestamp())
        opts=self.args(idx=0)
        opts.update(target_open_epoch=target,
                    decided_at=datetime(2025,9,30,12,tzinfo=UTC),
                    prediction_locked_at=datetime(2025,9,30,10,tzinfo=UTC))
        self.blocked(inspect(**opts),"UNVERIFIED_GAP_DIRECTLY_BEFORE_TARGET")
        opts["target_open_epoch"]=gap_epoch
        opts["decided_at"]=datetime(2025,9,29,12,tzinfo=UTC)
        opts["prediction_locked_at"]=datetime(2025,9,29,10,tzinfo=UTC)
        self.blocked(inspect(**opts),"TARGET_BAR_NOT_IN_ARCHIVE")

    def test_archive_cannot_contain_future_bars_relative_to_capture(self):
        f=self.root/"batch_00_manifest.json"
        obj=json.loads(f.read_text())
        obj["records"][0]["observed_at_utc"]="2026-10-30T00:00:00+00:00"
        f.write_text(json.dumps(obj))
        self.blocked(inspect(**self.args(idx=-3)),"CAPTURE_BEFORE_LATEST_CLOSED_BAR")


    def test_weekly_ny17_dst_boundary_never_generates_false_label(self):
        for opened in (datetime(2026, 3, 1, 22, tzinfo=UTC),
                       datetime(2026, 10, 25, 21, tzinfo=UTC)):
            with self.subTest(opened=opened):
                opts = self.args()
                opts.update(target_open_epoch=int(opened.timestamp()),
                            decided_at=opened-timedelta(hours=2),
                            prediction_locked_at=opened-timedelta(hours=3),
                            as_of_utc=opened+timedelta(days=8))
                self.blocked(inspect(**opts),
                             "W1_NY17_DST_CLOSE_REQUIRES_BROKER_VERIFICATION")


if __name__ == "__main__":
    unittest.main()
