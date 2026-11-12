"""Offline AM12 loader tests with disposable synthetic files, never real MT5."""
from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from atlasquant_instrument_registry import FX_28
from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_mt5_closedbar_outcome_lab import MT5_SCHEMA
from atlasquant_trader_mt5_forward_label_gate_lab import EXPECTED
from atlasquant_trader_mt5_28fx_archive_reader_lab import (
    inspect_local_am12_28fx_lab as inspect,
    main,
)
from test_atlasquant_trader_mt5_m15_ny17_archive_join_lab import (
    EVALUATED, archive, ny,
)


def make_record(symbol, frame, *, captured, sha="0" * 64):
    return {
        "symbol": symbol, "timeframe": frame,
        "snapshot_file": f"{symbol}_{frame}_closedbar.csv.gz",
        "requested": EXPECTED[frame], "returned": EXPECTED[frame],
        "bar_position_start": 1,
        "validation_errors": [], "sha256_uncompressed_csv": sha,
        "observed_at_utc": captured.isoformat(),
    }


def build(root: Path):
    """Synthetic 28 M15 compressed files and 84 metadata records in 7 batches."""
    records = []
    for pair in OFFICIAL_PAIRS:
        symbol = pair.replace("/", "")
        manifest, packed, captured = archive(pair=pair)
        (root / f"{symbol}_M15_closedbar.csv.gz").write_bytes(packed)
        m15 = {
            **make_record(symbol, "M15", captured=captured,
                          sha=manifest["sha256_uncompressed_csv"]),
            **manifest,
            # Real capture files may include fractional seconds. Do not
            # quietly round this away or reject a valid collector stamp.
            "observed_at_utc": (captured + timedelta(microseconds=123456)).isoformat(),
        }
        records.append(m15)
        for timeframe in ("D1", "W1"):
            # D1/W1 are inventory only; no original bytes present or audited.
            records.append(make_record(symbol, timeframe, captured=captured))
    assert len(records) == 84
    for i in range(7):
        document = {
            "schema": MT5_SCHEMA,
            "research_only": True, "trade_authorized": False,
            "prediction_available": False,
            "broker_identity_independently_verified": False,
            "historical_point_in_time_verified": False,
            "records": records[i * 12:(i + 1) * 12],
        }
        (root / f"batch_{i+1:02d}_manifest.json").write_text(
            json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return records


class Am12ReadonlyRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        build(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def audit(self, *, root=None, horizon="D1", end=None, as_of=EVALUATED):
        return inspect(
            root=self.root if root is None else root,
            horizon=horizon,
            start_at_utc=ny(8),
            end_at_utc=ny(9) if end is None else end,
            evaluated_at_utc=as_of,
        )

    def no_go(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["validated_directional_accuracy"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertIs(result["all_84_series_original_bytes_verified"], False)
        for flag in (
            "broker_provenance_authenticated", "broker_calendar_verified",
            "price_vintage_at_bias_decision_verified",
            "precommitted_forecast_proven", "trade_authorized",
            "publishable", "live_alert_allowed", "worker_enabled",
            "scheduler_enabled",
        ):
            self.assertIs(result[flag], False, flag)
        self.assertEqual(
            (result["output_files_written"], result["mt5_connections"],
             result["http_requests"], result["new_cost_brl"]), (0, 0, 0, 0))
        self.assertTrue(result["research_only"])

    def test_7_manifests_84_inventory_and_28_m15_window_local_only(self):
        before = {p.name for p in self.root.iterdir()}
        r = self.audit()
        self.assertEqual(r["state"], "LAB_AM12_LOCAL_M15_WINDOW_CHECKS_ONLY_NO_GO")
        self.assertEqual(r["manifest_files_seen"], 7)
        self.assertEqual(r["inventory_series_seen"], 84)
        self.assertEqual(r["m15_archive_files_read"], 28)
        self.assertTrue(r["all_28_m15_archive_bytes_self_consistent"])
        self.assertEqual(r["batch_result"]["coverage_claim_complete_pairs"], 28)
        self.assertEqual(set(r["batch_result"]["pair_results"]), set(OFFICIAL_PAIRS))
        self.assertEqual({p.name for p in self.root.iterdir()}, before)
        self.no_go(r)

    def test_weekly_window_is_only_local_not_broker_attestation(self):
        r = self.audit(horizon="W1", end=ny(13))
        self.assertEqual(r["state"], "LAB_AM12_LOCAL_M15_WINDOW_CHECKS_ONLY_NO_GO")
        self.assertEqual(r["batch_result"]["coverage_claim_complete_pairs"], 28)
        self.assertFalse(r["broker_provenance_authenticated"])
        self.no_go(r)

    def test_subsecond_capture_stamp_preserved_in_input(self):
        r = self.audit()
        self.assertTrue(r["all_28_m15_archive_bytes_self_consistent"])
        self.no_go(r)

    def test_missing_one_gzip_blocks_before_pass(self):
        pair = OFFICIAL_PAIRS[0].replace("/", "")
        file = self.root / f"{pair}_M15_closedbar.csv.gz"
        tmp = self.root / f"{pair}_M15_closedbar.csv.gz.bak"
        file.rename(tmp)
        try:
            r = self.audit()
            self.assertEqual(r["state"], "LAB_AM12_READONLY_28FX_RUNNER_BLOCKED")
            self.assertEqual(r["reason"],
                             "M15_ARCHIVE_MISSING_SYMLINK_OR_OVERSIZED")
            self.assertFalse(r["all_28_m15_archive_bytes_self_consistent"])
            self.no_go(r)
        finally:
            tmp.rename(file)

    def test_missing_manifest_blocks_instead_of_only_six(self):
        p = self.root / "batch_07_manifest.json"
        tmp = self.root / "batch_07_manifest.bak"
        p.rename(tmp)
        try:
            r = self.audit()
            self.assertEqual(r["manifest_files_seen"], 6)
            self.assertEqual(r["reason"], "SEVEN_BATCH_MANIFESTS_REQUIRED")
            self.no_go(r)
        finally:
            tmp.rename(p)

    def test_duplicate_series_across_manifests_is_not_new_data(self):
        p = self.root / "batch_07_manifest.json"
        raw = p.read_text()
        obj = json.loads(raw)
        first = json.loads((self.root / "batch_01_manifest.json").read_text())
        obj["records"][0] = first["records"][0]
        p.write_text(json.dumps(obj), encoding="utf-8")
        try:
            r = self.audit()
            self.assertEqual(r["reason"], "DUPLICATE_SERIES_ACROSS_MANIFESTS")
            self.no_go(r)
        finally:
            p.write_text(raw, encoding="utf-8")

    def test_duplicate_json_key_is_rejected(self):
        p = self.root / "batch_07_manifest.json"
        raw = p.read_text()
        p.write_text('{"schema":"x","schema":"y","records":[]}', encoding="utf-8")
        try:
            r = self.audit()
            self.assertEqual(r["reason"], "DUPLICATE_JSON_KEY")
            self.no_go(r)
        finally:
            p.write_text(raw, encoding="utf-8")

    def test_unexpected_provenance_flags_fail_closed(self):
        p = self.root / "batch_07_manifest.json"
        raw = p.read_text()
        obj = json.loads(raw)
        obj["trade_authorized"] = True
        p.write_text(json.dumps(obj), encoding="utf-8")
        try:
            r = self.audit()
            self.assertEqual(r["reason"], "MANIFEST_SCHEMA_OR_PROVENANCE_INVALID")
            self.no_go(r)
        finally:
            p.write_text(raw, encoding="utf-8")

    def test_tampered_m15_hash_not_counted_as_28_valid(self):
        p = self.root / "batch_07_manifest.json"
        raw = p.read_text()
        obj = json.loads(raw)
        rec = next(x for x in obj["records"] if x["timeframe"] == "M15")
        rec["sha256_uncompressed_csv"] = "f" * 64
        p.write_text(json.dumps(obj), encoding="utf-8")
        try:
            r = self.audit()
            self.assertEqual(r["state"],
                             "LAB_AM12_LOCAL_M15_INCOMPLETE_OR_GAPS_NO_GO")
            self.assertEqual(r["batch_result"]["coverage_claim_complete_pairs"], 27)
            self.assertFalse(r["all_28_m15_archive_bytes_self_consistent"])
            self.no_go(r)
        finally:
            p.write_text(raw, encoding="utf-8")

    def test_future_asof_or_bad_horizon_never_valid(self):
        for horizon, as_of in (
            ("MN1", EVALUATED),
            ("D1", ny(9)),
        ):
            with self.subTest(horizon=horizon, as_of=as_of):
                r = self.audit(horizon=horizon, as_of=as_of)
                self.assertEqual(r["state"], "LAB_AM12_READONLY_28FX_RUNNER_BLOCKED")
                self.no_go(r)

    def test_runner_main_return_codes_no_file_output(self):
        from unittest.mock import patch
        args = ["--root", str(self.root), "--horizon", "D1",
                "--start-utc", ny(8).isoformat(),
                "--end-utc", ny(9).isoformat(),
                "--as-of-utc", EVALUATED.isoformat()]
        with patch("builtins.print") as write:
            self.assertEqual(main(args), 0)
        self.assertEqual(write.call_count, 1)
        self.assertEqual(json.loads(write.call_args.args[0])["state"],
                         "LAB_AM12_LOCAL_M15_WINDOW_CHECKS_ONLY_NO_GO")
        with patch("builtins.print") as write:
            self.assertEqual(main(args[:-1] + [ny(9).isoformat()]), 2)
        self.assertEqual(json.loads(write.call_args.args[0])["operational_bias"],
                         "AGUARDAR")


if __name__ == "__main__":
    unittest.main()
