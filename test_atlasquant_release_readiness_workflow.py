import unittest
from pathlib import Path

class AtlasQuantReleaseReadinessWorkflowTests(unittest.TestCase):
    def test_release_readiness_workflow_is_safe_and_automated(self):
        path=Path(".github/workflows/atlasquant-release-readiness.yml")
        self.assertTrue(path.is_file())
        text=path.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:",text)
        self.assertIn("schedule:",text)
        self.assertIn("atlasquant_finalization_audit",text)
        self.assertIn('ATLASQUANT_REAL_EXECUTION: "0"',text)
        self.assertIn("internal_release_preparation_complete",text)
        self.assertNotIn('ATLASQUANT_REAL_EXECUTION: "1"',text)
        self.assertNotIn("automatic_merge",text)

if __name__=="__main__":
    unittest.main()
