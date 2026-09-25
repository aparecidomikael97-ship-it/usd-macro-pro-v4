from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from atlasquant_aion_runtime_bootstrap import (
    canonical_bootstrap_checkpoint,
    verify_checkpoint,
    write_checkpoint,
)


class AtlasQuantAionRuntimeBootstrapTests(unittest.TestCase):
    def test_bootstrap_checkpoint_is_v14_clean_and_safe(self):
        cp=canonical_bootstrap_checkpoint()
        self.assertGreaterEqual(cp["checkpoint_version"],14)
        self.assertFalse(cp["operating"]["dirty"])
        self.assertFalse(cp["aion"]["real_trading"])
        self.assertIn("release_confidence",cp)

    def test_runtime_bootstrap_workflow_is_v14_and_runtime_branch_only(self):
        src=Path(".github/workflows/aion-runtime-checkpoint-bootstrap.yml").read_text(encoding="utf-8")
        self.assertIn("Generate canonical V14 checkpoint",src)
        self.assertIn("branch='atlasquant-runtime'",src)
        self.assertIn("contents: write",src)
        self.assertNotIn("branch='main'",src)

    def test_write_and_verify_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"checkpoint_master.json"
            written=write_checkpoint(path)
            verified=verify_checkpoint(path)
            self.assertEqual(written["status"],"CONFIRMED")
            self.assertEqual(verified["status"],"CONFIRMED")
            self.assertEqual(written["digest"],verified["digest"])

    def test_tampered_digest_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"checkpoint_master.json"
            write_checkpoint(path)
            cp=json.loads(path.read_text(encoding="utf-8"))
            cp["studio"]["digest"]="tampered"
            path.write_text(json.dumps(cp),encoding="utf-8")
            with self.assertRaises(ValueError):
                verify_checkpoint(path)


if __name__=="__main__":
    unittest.main()
