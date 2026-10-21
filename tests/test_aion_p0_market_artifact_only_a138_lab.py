"""A138 LAB tests: artifact-only market snapshots with ZERO runtime write authority.

No external network or provider APIs. Use synthetic files and strict manifests.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/"tools"/"aion_p0_market_artifact_only_a138.py"
SPEC=importlib.util.spec_from_file_location("aion_market_bundle_a138",MODULE)
assert SPEC and SPEC.loader
M=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
SHA="a"*40
CHECKPOINT="dados/aion/checkpoint_master.json"


class MarketArtifactOnlyA138LAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
        self.root=self.dir/"source"
        self.root.mkdir()
        for path in M.ALLOWLIST:
            file=self.root/path
            file.parent.mkdir(parents=True,exist_ok=True)
            file.write_text(json.dumps({"version":"SYNTHETIC_ONLY","pair":"EUR/USD",
                                        "data":[{"value":1.25}]}),encoding="utf-8")
        self.out=self.dir/"output"/"market.zip"

    def build(self,**overrides):
        kw={"source_root":self.root,"output_path":self.out,"source_sha":SHA}
        kw.update(overrides)
        return M.build_market_bundle(**kw)

    def rejects(self,**overrides):
        with self.assertRaises((ValueError,TypeError,FileNotFoundError)):
            self.build(**overrides)
        self.assertFalse(self.out.exists())

    def test_01_default_allowed_public_market_json_only(self):
        report=self.build()
        self.assertEqual(report["status"],"OFFLINE_ARTIFACT_ONLY")
        self.assertEqual([x["path"] for x in report["files"]],list(M.ALLOWLIST))
        self.assertTrue(self.out.is_file())

    def test_02_checkpoint_explicit_request_is_refused(self):
        self.rejects(requested_paths=[CHECKPOINT])

    def test_03_checkpoint_added_to_allowed_inputs_is_refused(self):
        self.rejects(requested_paths=list(M.ALLOWLIST)+[CHECKPOINT])

    def test_04_traversal_is_refused(self):
        self.rejects(requested_paths=["dados/x/../aion/checkpoint_master.json"])

    def test_05_encoded_checkpoint_is_refused(self):
        self.rejects(requested_paths=["dados%2Faion%2Fcheckpoint_master.json"])

    def test_06_absolute_path_is_refused(self):
        self.rejects(requested_paths=["/tmp/secret"])

    def test_07_duplicate_path_is_refused(self):
        self.rejects(requested_paths=[M.ALLOWLIST[0],M.ALLOWLIST[0]])

    def test_08_nonstring_path_is_refused(self):
        self.rejects(requested_paths=[True])

    def test_09_symlink_escape_is_refused(self):
        src=self.root/M.ALLOWLIST[0]
        secret=self.dir/"secret.json"
        secret.write_text('{"key":"private"}',encoding="utf-8")
        src.unlink()
        try:
            src.symlink_to(secret)
        except (OSError,NotImplementedError):
            self.skipTest("symlink unavailable on host")
        self.rejects()

    def test_10_missing_allowed_input_fails_closed(self):
        (self.root/M.ALLOWLIST[0]).unlink()
        self.rejects()

    def test_11_invalid_json_fails_closed(self):
        (self.root/M.ALLOWLIST[0]).write_text('{"bad":',encoding="utf-8")
        self.rejects()

    def test_12_duplicate_json_keys_fail_closed(self):
        (self.root/M.ALLOWLIST[0]).write_text('{"x":1,"x":2}',encoding="utf-8")
        self.rejects()

    def test_13_nonstandard_nan_json_fails_closed(self):
        (self.root/M.ALLOWLIST[0]).write_text('{"x":NaN}',encoding="utf-8")
        self.rejects()

    def test_14_sensitive_field_name_not_packaged(self):
        (self.root/M.ALLOWLIST[0]).write_text(
            '{"GITHUB_TOKEN_HISTORICO":"do-not-publish"}',encoding="utf-8")
        self.rejects()

    def test_15_oversize_file_not_packaged(self):
        (self.root/M.ALLOWLIST[0]).write_text(
            json.dumps({"data":"x"*(M.MAX_FILE_BYTES+1)}),encoding="utf-8")
        self.rejects()

    def test_16_invalid_commit_sha_not_accepted_as_provenance(self):
        self.rejects(source_sha="abc")

    def test_17_cannot_write_output_inside_checkout(self):
        self.rejects(output_path=self.root/"dados"/"bundle.zip")

    def test_18_cannot_overwrite_existing_artifact(self):
        self.out.parent.mkdir(parents=True,exist_ok=True)
        self.out.write_bytes(b"prior")
        with self.assertRaises((ValueError,FileExistsError)):
            self.build()
        self.assertEqual(self.out.read_bytes(),b"prior")

    def test_19_manifest_hashes_match_exact_source_bytes(self):
        self.build()
        with zipfile.ZipFile(self.out) as archive:
            manifest=json.loads(archive.read("manifest.json"))
            self.assertFalse(manifest["provider_fetch_performed"])
            self.assertFalse(manifest["runtime_write_authorized"])
            self.assertFalse(manifest["independent_witness_enrolled"])
            self.assertEqual(manifest["source_commit"],SHA)
            self.assertEqual(manifest["freshness_status"],"NOT_VERIFIED_STORED_REPOSITORY_COPY")
            for item in manifest["files"]:
                data=archive.read(item["path"])
                self.assertEqual(item["sha256"],hashlib.sha256(data).hexdigest())
                self.assertEqual(item["size_bytes"],len(data))
                self.assertNotIn("aion/checkpoint_master.json",item["path"])

    def test_20_bundle_reproducible_for_same_bytes(self):
        self.build()
        first=self.out.read_bytes()
        self.out.unlink()
        self.build()
        self.assertEqual(first,self.out.read_bytes())

    def test_21_source_files_are_not_changed(self):
        original={p:(self.root/p).read_bytes() for p in M.ALLOWLIST}
        self.build()
        self.assertEqual(original,{p:(self.root/p).read_bytes() for p in M.ALLOWLIST})

    def test_22_non_mapping_top_level_refused(self):
        (self.root/M.ALLOWLIST[0]).write_text('["not a market snapshot"]',encoding="utf-8")
        self.rejects()


if __name__=="__main__":
    unittest.main()
