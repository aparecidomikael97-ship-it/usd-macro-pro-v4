"""Synthetic-only tests for P0 staged FX28 Motor A migration checksum gate.

No originals, no network, no MT5, no scheduler, no production edits.
Uses TemporaryDirectory; fake contents are NOT the AM12 source bytes.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from atlasquant_trader_fx28_staged_bundle_integrity_lab import (
    _evaluate,STAGE_PINS,LEGACY_PINS,_WIRING,SCHEMA,
)

class Fx28MigrationBundleIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(prefix="ATLASQUANT_FX28_BUNDLE_SYNTHETIC_")
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.stage=self.base/"STAGED"
        self.legacy=self.base/"LEGACY"
        self.run=self.base/"SCHEDULED"
        for root in (self.stage,self.legacy,self.run):
            root.mkdir()
        self.stage_pins={}
        self.legacy_pins={}
        for filename in STAGE_PINS:
            marker=next((mark for name,mark in _WIRING if name==filename),"")
            data=("stage "+filename+"\n"+marker+"\n").encode()
            (self.stage/filename).write_bytes(data)
            self.stage_pins[filename]=sha256(data).hexdigest()
        for filename in LEGACY_PINS:
            data=("legacy "+filename+"\n").encode()
            (self.legacy/filename).write_bytes(data)
            self.legacy_pins[filename]=sha256(data).hexdigest()
        self.wrapper=self.run/"run_fx28_readiness_with_tzdata_lab.py"
        self.collector=self.run/"atlasquant_trader_fx28_ny17_m15_writeonce_capture_lab.py"
        self.wrapper.write_bytes(b'program points to FX28_Single_Readiness_20261114')
        self.collector.write_bytes(b'first m15 collector is FROZEN mock')
        self.wp=sha256(self.wrapper.read_bytes()).hexdigest()
        self.cp=sha256(self.collector.read_bytes()).hexdigest()

    def run_gate(self,**updates):
        params={
            "stage_dir":self.stage,"legacy_dir":self.legacy,
            "scheduled_wrapper_path":self.wrapper,
            "scheduled_collector_path":self.collector,
            "stage_pins":self.stage_pins,
            "legacy_pins":self.legacy_pins,
            "wrapper_sha":self.wp,"collector_sha":self.cp,
        }
        params.update(updates)
        return _evaluate(**params)

    def safe(self,result):
        self.assertEqual(result["schema"],SCHEMA)
        self.assertEqual(result["operational_bias"],"AGUARDAR")
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["safe_to_change_automations"])
        self.assertFalse(result["explicit_rollout_or_merge_approved"])
        self.assertFalse(result["production_or_scheduled_files_modified_by_this_gate"])
        self.assertFalse(result["deployed_to_main"])
        self.assertIsNone(result["calibrated_fx_probability"])
        self.assertEqual(result["frozen_campaign_slots"],672)
        self.assertEqual((result["http_requests"],result["mt5_calls"],
                          result["file_writes"]),(0,0,0))

    def blocked(self,**kw):
        out=self.run_gate(**kw)
        self.safe(out)
        self.assertEqual(out["state"],
            "LAB_FX28_STAGED_MIGRATION_INTEGRITY_BLOCKED_NO_GO")
        return out

    def test_01_matching_twelve_files_is_stage_only_not_deployment(self):
        out=self.run_gate()
        self.safe(out)
        self.assertEqual(out["state"],
            "LAB_FX28_STAGED_MIGRATION_BUNDLE_BYTES_VERIFIED_NOT_DEPLOYED_NO_GO")
        self.assertEqual(out["total_files_matched"],12)
        self.assertEqual(len(out["staged_modules_checked"]),4)
        self.assertEqual(len(out["legacy_dependencies_checked"]),6)
        self.assertTrue(out["four_module_import_wiring_matches"])
        self.assertTrue(out["scheduled_wrapper_byte_hash_unchanged"])
        self.assertTrue(out["scheduled_m15_collector_byte_hash_unchanged"])
        self.assertFalse(out["file_mismatches"])

    def test_02_missing_stage_panel_fails_closed(self):
        (self.stage/"atlasquant_trader_fx28_single_readiness_panel_lab.py").unlink()
        r=self.blocked()
        self.assertTrue(r["file_mismatches"])

    def test_03_stage_parser_changed_one_byte_fails_closed(self):
        p=self.stage/"atlasquant_trader_nzd_rbnz_policy_source_variant_lab.py"
        p.write_bytes(p.read_bytes()+b"x")
        r=self.blocked()
        self.assertFalse(r["all_stage_files_match_pinned_versions"])

    def test_04_old_factor_dependency_changed_fails_closed(self):
        p=self.legacy/"atlasquant_trader_fx28_32_factor_source_admission_lab.py"
        p.write_bytes(p.read_bytes()+b"tampered")
        r=self.blocked()
        self.assertFalse(r["all_legacy_dependencies_match_pinned_versions"])

    def test_05_frozen_wrapper_modified_fails_closed(self):
        self.wrapper.write_bytes(self.wrapper.read_bytes()+b"new runner")
        r=self.blocked()
        self.assertFalse(r["scheduled_wrapper_byte_hash_unchanged"])

    def test_06_first_m15_collector_modified_fails_closed(self):
        self.collector.write_bytes(self.collector.read_bytes()+b"new order")
        r=self.blocked()
        self.assertFalse(r["scheduled_m15_collector_byte_hash_unchanged"])

    def test_07_wrong_import_wiring_fails_even_with_new_valid_hash(self):
        name="atlasquant_trader_fx28_eight_policy_raw_source_join_lab.py"
        p=self.stage/name
        p.write_bytes(b"# no reference to NZD policy variant\n")
        pins=dict(self.stage_pins)
        pins[name]=sha256(p.read_bytes()).hexdigest()
        r=self.blocked(stage_pins=pins)
        self.assertFalse(r["four_module_import_wiring_matches"])

    def test_08_wrapper_points_into_stage_fails_even_with_updated_pin(self):
        self.wrapper.write_bytes(b'program points to NZD_Policy_Variant_Staged_20261115')
        digest=sha256(self.wrapper.read_bytes()).hexdigest()
        r=self.blocked(wrapper_sha=digest)
        self.assertEqual(r["reason"],"STAGE_IMPORT_GRAPH_OR_FROZEN_WRAPPER_CHANGED")
        self.assertFalse(r["safe_to_change_automations"])

    def test_09_invalid_manifest_key_set_rejected(self):
        pins=dict(self.stage_pins)
        pins.pop("atlasquant_trader_nzd_rbnz_policy_source_variant_lab.py")
        r=self.blocked(stage_pins=pins)
        self.assertEqual(r["reason"],
            "FOUR_MODULE_OR_SIX_LEGACY_MODULE_MANIFEST_DRIFT")

    def test_10_empty_document_is_not_valid(self):
        p=self.stage/"atlasquant_trader_fx28_policy_local_archive_replay_lab.py"
        p.write_bytes(b"")
        self.blocked()

    def test_11_missing_collector_is_blocked(self):
        self.collector.unlink()
        self.blocked()

    def test_12_relative_staging_path_is_rejected(self):
        self.blocked(stage_dir=Path("STAGED"))

    def test_13_same_stage_and_legacy_dir_is_rejected(self):
        self.blocked(legacy_dir=self.stage)

    def test_14_no_stage_directory(self):
        self.blocked(stage_dir=self.base/"NOT_PRESENT")

    def test_15_swapping_stage_files_is_not_accepted(self):
        a=self.stage/"atlasquant_trader_fx28_single_readiness_panel_lab.py"
        b=self.stage/"atlasquant_trader_fx28_policy_local_archive_replay_lab.py"
        av=a.read_bytes();bv=b.read_bytes()
        a.write_bytes(bv);b.write_bytes(av)
        self.blocked()

    def test_16_same_second_run_never_mutates_inputs(self):
        r1=self.run_gate()
        before={str(p):p.read_bytes() for p in
                (*self.stage.iterdir(),*self.legacy.iterdir(),
                 self.wrapper,self.collector)}
        r2=self.run_gate()
        self.safe(r1);self.safe(r2)
        self.assertEqual(r1["state"],r2["state"])
        for name,raw in before.items():
            self.assertEqual(Path(name).read_bytes(),raw)

    def test_17_symlink_source_is_blocked_if_supported(self):
        original=self.stage/"atlasquant_trader_nzd_rbnz_policy_source_variant_lab.py"
        payload=original.read_bytes()
        outside=self.base/"original_elsewhere.py"
        outside.write_bytes(payload)
        original.unlink()
        try:
            original.symlink_to(outside)
        except (NotImplementedError,OSError) as error:
            self.skipTest("Symlinks not available on this system: "+str(error))
        r=self.blocked()
        self.assertTrue(r["file_mismatches"])

    def test_18_missing_source_does_not_create_it(self):
        path=self.stage/"atlasquant_trader_nzd_rbnz_policy_source_variant_lab.py"
        path.unlink()
        self.blocked()
        self.assertFalse(path.exists())

if __name__=="__main__":
    unittest.main(verbosity=2)
