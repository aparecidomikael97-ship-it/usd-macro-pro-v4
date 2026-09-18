import json
import tempfile
import unittest
from pathlib import Path
import pandas as pd
from atlasquant_backtest_snapshot import SCHEMA,normalized_candles_fingerprint,settings_fingerprint,code_fingerprint,build_backtest_snapshot,snapshot_json,load_snapshot_json,compare_backtest_snapshots,validate_snapshot

def candles():
    return pd.DataFrame({"datetime":pd.date_range("2026-09-15T00:00:00Z",periods=3,freq="15min",tz="UTC"),"open":[1.,1.1,1.2],"high":[1.2,1.3,1.4],"low":[.9,1.,1.1],"close":[1.1,1.2,1.3]})
def evidence(expectancy=.2): return {"schema":"ATLASQUANT_BACKTEST_EVIDENCE_V1","evidence_summary":[{"strategy":"FVG","trades":20,"expectancy_r":expectancy,"net_r":4.,"max_drawdown_r":2.}]}
def snap(root,raw=b"A",settings=None,expectancy=.2):
    return build_backtest_snapshot(raw_csv=raw,candles=candles(),settings=settings or {},evidence_bundle=evidence(expectancy),code_root=root,code_paths=["logic.py"])

class BacktestSnapshotTests(unittest.TestCase):
    def test_normalized_data_hash_is_stable_for_same_data(self):
        self.assertEqual(normalized_candles_fingerprint(candles())["sha256"],normalized_candles_fingerprint(candles().copy())["sha256"])
    def test_settings_hash_is_order_independent(self): self.assertEqual(settings_fingerprint({"b":2,"a":1})["sha256"],settings_fingerprint({"a":1,"b":2})["sha256"])
    def test_code_fingerprint_tracks_file_content(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/"a.py").write_text("x=1\n"); one=code_fingerprint(root=root,paths=["a.py"]); (root/"a.py").write_text("x=2\n"); self.assertNotEqual(one["sha256"],code_fingerprint(root=root,paths=["a.py"])["sha256"])
    def test_snapshot_id_is_reproducible(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/"logic.py").write_text("x=1\n"); self.assertEqual(snap(root)["snapshot_id"],snap(root)["snapshot_id"])
    def test_compare_reports_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); p=root/"logic.py"; p.write_text("x=1\n"); a=snap(root,settings={"cost_r":.01}); p.write_text("x=2\n"); b=snap(root,settings={"cost_r":.03},expectancy=.1); d=compare_backtest_snapshots(a,b); self.assertTrue(d["settings_changed"]); self.assertTrue(d["code_changed"]); self.assertTrue(d["evidence_changed"])
    def test_json_roundtrip_validates_schema(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/"logic.py").write_text("x=1\n"); a=snap(root); self.assertEqual(load_snapshot_json(snapshot_json(a))["snapshot_id"],a["snapshot_id"])
    def test_fail_closed_when_snapshot_id_is_tampered(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/"logic.py").write_text("x=1\n"); a=snap(root); a["snapshot_id"]="0"*64
            with self.assertRaisesRegex(ValueError,"snapshot_id"): validate_snapshot(a)
    def test_fail_closed_when_settings_are_tampered(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/"logic.py").write_text("x=1\n"); a=snap(root,settings={"cost_r":.01}); a["settings"]["values"]["cost_r"]=.99
            with self.assertRaisesRegex(ValueError,"adulterado"): validate_snapshot(a)
    def test_fail_closed_when_code_manifest_is_tampered(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/"logic.py").write_text("x=1\n"); a=snap(root)
            a["code"]["files"][0]["sha256"]="0"*64
            with self.assertRaisesRegex(ValueError,"code sha256"):
                validate_snapshot(a)

    def test_fail_closed_when_evidence_is_tampered(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/"logic.py").write_text("x=1\n"); a=snap(root); a["evidence"]["bundle"]["evidence_summary"][0]["net_r"]=999
            with self.assertRaisesRegex(ValueError,"adulterado"): compare_backtest_snapshots(a,a)
    def test_fail_closed_on_incomplete_identity(self):
        with self.assertRaisesRegex(ValueError,"identity incompleta"): validate_snapshot({"schema":SCHEMA,"identity":{}})
    def test_invalid_json_is_controlled_error(self):
        with self.assertRaisesRegex(ValueError,"JSON inválido"): load_snapshot_json("{")


    def test_fail_closed_when_safety_flags_are_removed_or_false(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/"logic.py").write_text("x=1\n")
            for key,value in (("research_only",False),("no_live_gate_effect",False)):
                with self.subTest(flag=key):
                    a=snap(root); a[key]=value
                    with self.assertRaisesRegex(ValueError,"flags de segurança"):
                        validate_snapshot(a)

    def test_fail_closed_on_invalid_count_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/"logic.py").write_text("x=1\n")
            for section,key,bad in (("raw_csv","bytes",-1),("raw_csv","bytes",True),("normalized_data","rows",-1),("normalized_data","rows",1.5)):
                with self.subTest(section=section,key=key,bad=bad):
                    a=snap(root); a[section][key]=bad
                    with self.assertRaisesRegex(ValueError,"inválidos"):
                        validate_snapshot(a)


if __name__=="__main__": unittest.main()
