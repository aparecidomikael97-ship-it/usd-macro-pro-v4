import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import pandas as pd

from atlasquant_backtest_snapshot import build_backtest_snapshot
from atlasquant_backtest_snapshot_history import (
    DEFAULT_HISTORY_DIR,
    consecutive_history_diffs,
    history_archive_zip,
    history_timeline_frame,
    load_snapshot_history,
    save_snapshot_local,
)


def candles():
    return pd.DataFrame({
        "datetime":pd.date_range("2026-09-15T00:00:00Z",periods=3,freq="15min",tz="UTC"),
        "open":[1.0,1.1,1.2],
        "high":[1.2,1.3,1.4],
        "low":[0.9,1.0,1.1],
        "close":[1.1,1.2,1.3],
    })


def evidence(pair="EUR/USD", expectancy=0.2):
    return {
        "schema":"ATLASQUANT_BACKTEST_EVIDENCE_V1",
        "pair":pair,
        "evidence_summary":[{
            "strategy":"FVG",
            "trades":20,
            "expectancy_r":expectancy,
            "net_r":4.0,
            "max_drawdown_r":2.0,
        }],
    }


def snapshot(code_root, *, raw=b"A", cost=0.01, expectancy=0.2):
    return build_backtest_snapshot(
        raw_csv=raw,
        candles=candles(),
        settings={"pair":"EUR/USD","cost_r":cost,"slippage_r":0.0},
        evidence_bundle=evidence(expectancy=expectancy),
        code_root=code_root,
        code_paths=["logic.py"],
    )


class BacktestSnapshotHistoryTests(unittest.TestCase):
    def test_default_store_is_outside_operational_dados(self):
        self.assertEqual(DEFAULT_HISTORY_DIR.parts[0],".atlasquant_research")
        self.assertNotIn("dados",DEFAULT_HISTORY_DIR.parts)

    def test_save_load_and_deduplicate_snapshot(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as code_td:
            code=Path(code_td)
            (code/"logic.py").write_text("x=1\n",encoding="utf-8")
            snap=snapshot(code)
            first=save_snapshot_local(snap,root=td)
            second=save_snapshot_local(snap,root=td)
            self.assertEqual(first["reason"],"SAVED")
            self.assertEqual(second["reason"],"ALREADY_PRESENT")
            loaded=load_snapshot_history(root=td)
            self.assertEqual(len(loaded["snapshots"]),1)
            self.assertEqual(loaded["invalid_files"],[])
            self.assertEqual(loaded["snapshots"][0]["snapshot_id"],snap["snapshot_id"])

    def test_tampered_file_is_reported_not_trusted(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as code_td:
            code=Path(code_td)
            (code/"logic.py").write_text("x=1\n",encoding="utf-8")
            snap=snapshot(code)
            save_snapshot_local(snap,root=td)
            bad=dict(snap)
            bad["snapshot_id"]="0"*64
            Path(td,"tampered.json").write_text(json.dumps(bad),encoding="utf-8")
            loaded=load_snapshot_history(root=td)
            self.assertEqual(len(loaded["snapshots"]),1)
            self.assertEqual(len(loaded["invalid_files"]),1)
            self.assertEqual(loaded["invalid_files"][0]["file"],"tampered.json")

    def test_timeline_and_consecutive_diff_are_chronological(self):
        with tempfile.TemporaryDirectory() as code_td:
            code=Path(code_td)
            path=code/"logic.py"
            path.write_text("x=1\n",encoding="utf-8")
            a=snapshot(code,cost=0.01,expectancy=0.2)
            b=snapshot(code,cost=0.03,expectancy=0.1)
            a["created_at"]="2026-09-16T10:00:00+00:00"
            b["created_at"]="2026-09-16T11:00:00+00:00"

            timeline=history_timeline_frame([b,a])
            self.assertEqual(timeline.iloc[0]["snapshot_id"],a["snapshot_id"])
            self.assertEqual(timeline.iloc[1]["snapshot_id"],b["snapshot_id"])

            diffs=consecutive_history_diffs([b,a])
            self.assertEqual(len(diffs),1)
            self.assertTrue(bool(diffs.iloc[0]["settings_changed"]))
            self.assertTrue(bool(diffs.iloc[0]["evidence_changed"]))
            self.assertEqual(int(diffs.iloc[0]["settings_changes"]),1)

    def test_archive_contains_manifest_timeline_changes_and_snapshots(self):
        with tempfile.TemporaryDirectory() as code_td:
            code=Path(code_td)
            (code/"logic.py").write_text("x=1\n",encoding="utf-8")
            a=snapshot(code,cost=0.01)
            b=snapshot(code,cost=0.02)
            a["created_at"]="2026-09-16T10:00:00+00:00"
            b["created_at"]="2026-09-16T11:00:00+00:00"
            raw=history_archive_zip([a,b])
            with zipfile.ZipFile(io.BytesIO(raw),"r") as zf:
                names=set(zf.namelist())
                self.assertIn("manifest.json",names)
                self.assertIn("timeline.csv",names)
                self.assertIn("changes.csv",names)
                snapshot_names=[x for x in names if x.startswith("snapshots/")]
                self.assertEqual(len(snapshot_names),2)
                manifest=json.loads(zf.read("manifest.json").decode("utf-8"))
                self.assertEqual(manifest["snapshot_count"],2)
                self.assertTrue(manifest["research_only"])
                self.assertTrue(manifest["no_live_gate_effect"])


if __name__=="__main__":
    unittest.main()
