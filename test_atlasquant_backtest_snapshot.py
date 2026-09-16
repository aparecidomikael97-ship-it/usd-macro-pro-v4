import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from atlasquant_backtest_snapshot import (
    SCHEMA,
    normalized_candles_fingerprint,
    settings_fingerprint,
    code_fingerprint,
    build_backtest_snapshot,
    snapshot_json,
    load_snapshot_json,
    compare_backtest_snapshots,
)


def candles():
    return pd.DataFrame({
        "datetime":pd.date_range("2026-09-15T00:00:00Z",periods=3,freq="15min",tz="UTC"),
        "open":[1.0,1.1,1.2],
        "high":[1.2,1.3,1.4],
        "low":[0.9,1.0,1.1],
        "close":[1.1,1.2,1.3],
    })


def evidence(expectancy=0.2):
    return {
        "schema":"ATLASQUANT_BACKTEST_EVIDENCE_V1",
        "evidence_summary":[
            {
                "strategy":"FVG",
                "trades":20,
                "expectancy_r":expectancy,
                "net_r":4.0,
                "max_drawdown_r":2.0,
            }
        ],
    }


class BacktestSnapshotTests(unittest.TestCase):
    def test_normalized_data_hash_is_stable_for_same_data(self):
        a=normalized_candles_fingerprint(candles())
        b=normalized_candles_fingerprint(candles().copy())
        self.assertEqual(a["sha256"],b["sha256"])
        self.assertEqual(a["rows"],3)

    def test_settings_hash_is_order_independent(self):
        a=settings_fingerprint({"b":2,"a":1})
        b=settings_fingerprint({"a":1,"b":2})
        self.assertEqual(a["sha256"],b["sha256"])

    def test_code_fingerprint_tracks_file_content(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"a.py").write_text("x=1\n",encoding="utf-8")
            one=code_fingerprint(root=root,paths=["a.py"])
            (root/"a.py").write_text("x=2\n",encoding="utf-8")
            two=code_fingerprint(root=root,paths=["a.py"])
            self.assertNotEqual(one["sha256"],two["sha256"])

    def test_snapshot_id_is_reproducible_even_created_at_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"logic.py").write_text("x=1\n",encoding="utf-8")
            kwargs=dict(
                raw_csv=b"time,open,high,low,close\n",
                candles=candles(),
                settings={"cost_r":0.02},
                evidence_bundle=evidence(),
                code_root=root,
                code_paths=["logic.py"],
            )
            a=build_backtest_snapshot(**kwargs)
            b=build_backtest_snapshot(**kwargs)
            self.assertEqual(a["schema"],SCHEMA)
            self.assertEqual(a["snapshot_id"],b["snapshot_id"])

    def test_raw_file_can_change_while_normalized_data_stays_same(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"logic.py").write_text("x=1\n",encoding="utf-8")
            common=dict(
                candles=candles(),
                settings={"cost_r":0.02},
                evidence_bundle=evidence(),
                code_root=root,
                code_paths=["logic.py"],
            )
            a=build_backtest_snapshot(raw_csv=b"A",**common)
            b=build_backtest_snapshot(raw_csv=b"B",**common)
            diff=compare_backtest_snapshots(a,b)
            self.assertTrue(diff["raw_csv_changed"])
            self.assertFalse(diff["normalized_data_changed"])
            self.assertIn("raw_csv",diff["change_causes"])

    def test_compare_reports_settings_code_and_metric_deltas(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            path=root/"logic.py"
            path.write_text("x=1\n",encoding="utf-8")
            a=build_backtest_snapshot(
                raw_csv=b"A",
                candles=candles(),
                settings={"cost_r":0.01,"max_wait":8},
                evidence_bundle=evidence(0.2),
                code_root=root,
                code_paths=["logic.py"],
            )
            path.write_text("x=2\n",encoding="utf-8")
            b=build_backtest_snapshot(
                raw_csv=b"A",
                candles=candles(),
                settings={"cost_r":0.03,"max_wait":8},
                evidence_bundle=evidence(0.1),
                code_root=root,
                code_paths=["logic.py"],
            )
            diff=compare_backtest_snapshots(a,b)
            self.assertTrue(diff["settings_changed"])
            self.assertTrue(diff["code_changed"])
            self.assertTrue(diff["evidence_changed"])
            self.assertEqual(diff["settings_changes"][0]["setting"],"cost_r")
            delta=diff["evidence_metric_deltas"][0]
            self.assertAlmostEqual(delta["expectancy_r_delta"],-0.1)
            self.assertIn("não indicam melhora",diff["note"])

    def test_json_roundtrip_validates_schema(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"logic.py").write_text("x=1\n",encoding="utf-8")
            snap=build_backtest_snapshot(
                raw_csv=b"A",
                candles=candles(),
                settings={},
                evidence_bundle=evidence(),
                code_root=root,
                code_paths=["logic.py"],
            )
            loaded=load_snapshot_json(snapshot_json(snap))
            self.assertEqual(loaded["snapshot_id"],snap["snapshot_id"])
            with self.assertRaises(ValueError):
                load_snapshot_json(json.dumps({"schema":"BAD"}))


if __name__=="__main__":
    unittest.main()
