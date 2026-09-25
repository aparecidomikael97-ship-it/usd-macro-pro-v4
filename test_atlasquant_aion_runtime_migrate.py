from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from atlasquant_aion_memory import default_checkpoint
from atlasquant_aion_runtime_migrate import migrate_checkpoint


class AtlasQuantAionRuntimeMigrationTests(unittest.TestCase):
    def test_v14_shape_migrates_to_current_v16_and_preserves_data(self):
        cp=default_checkpoint()
        cp["checkpoint_version"]=14
        cp.pop("memory_reliability",None)
        cp["pending"].append("PENDENCIA-PRESERVADA")
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/"before.json"
            target=Path(td)/"after.json"
            source.write_text(json.dumps(cp),encoding="utf-8")
            out=migrate_checkpoint(source,target)
            migrated=json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(out["status"],"CONFIRMED")
        self.assertGreaterEqual(out["after_version"],16)
        self.assertIn("memory_reliability",migrated)
        self.assertIn("PENDENCIA-PRESERVADA",migrated["pending"])
        self.assertFalse(migrated["aion"]["real_trading"])

    def test_v15_shape_without_data_decision_fabric_migrates_to_v16(self):
        cp=default_checkpoint()
        cp["checkpoint_version"]=15
        cp.pop("data_decision_fabric",None)
        cp["pending"].append("PENDENCIA-V15-PRESERVADA")
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/"before-v15.json"
            target=Path(td)/"after-v16.json"
            source.write_text(json.dumps(cp),encoding="utf-8")
            out=migrate_checkpoint(source,target)
            migrated=json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(out["status"],"CONFIRMED")
        self.assertGreaterEqual(out["after_version"],16)
        self.assertIn("data_decision_fabric",migrated)
        self.assertTrue(migrated["data_decision_fabric"]["digest"])
        self.assertFalse(migrated["data_decision_fabric"]["automatic_execution"])
        self.assertIn("PENDENCIA-V15-PRESERVADA",migrated["pending"])
        self.assertFalse(migrated["aion"]["real_trading"])

    def test_dirty_persisted_checkpoint_blocks_automatic_migration(self):
        cp=default_checkpoint()
        cp["operating"]["dirty"]=True
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/"before.json"
            target=Path(td)/"after.json"
            source.write_text(json.dumps(cp),encoding="utf-8")
            with self.assertRaises(ValueError):
                migrate_checkpoint(source,target)

    def test_integrity_mismatch_blocks_migration(self):
        cp=default_checkpoint()
        cp["studio"]["digest"]="wrong"
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/"before.json"
            target=Path(td)/"after.json"
            source.write_text(json.dumps(cp),encoding="utf-8")
            with self.assertRaises(ValueError):
                migrate_checkpoint(source,target)


if __name__=="__main__":
    unittest.main()
