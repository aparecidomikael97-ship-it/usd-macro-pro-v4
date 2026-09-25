from __future__ import annotations

import unittest
from pathlib import Path


WORKFLOW=Path(".github/workflows/aion-runtime-checkpoint-migrate.yml")


class AtlasQuantAionRuntimeMigrationWorkflowTests(unittest.TestCase):
    def test_legacy_source_is_verified_by_migrator_before_strict_current_verify(self):
        src=WORKFLOW.read_text(encoding="utf-8")
        step=src.split("- name: Verify and migrate current runtime checkpoint",1)[1].split("- name: Conditionally persist migration",1)[0]
        migrate=step.index("python atlasquant_aion_runtime_migrate.py")
        strict=step.index("python atlasquant_aion_runtime_bootstrap.py --verify /tmp/runtime_after.json")
        self.assertLess(migrate,strict)
        self.assertNotIn("bootstrap.py --verify /tmp/runtime_before.json",step)
        self.assertIn("MISMATCH/UNKNOWN/dirty fail closed",step)

    def test_runtime_write_remains_conditional_on_current_sha(self):
        src=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('CURRENT_SHA="$(cat /tmp/runtime_sha.txt)"',src)
        self.assertIn("-f sha=\"$CURRENT_SHA\"",src)
        self.assertIn("Read back and verify migration",src)


if __name__=="__main__":
    unittest.main()
