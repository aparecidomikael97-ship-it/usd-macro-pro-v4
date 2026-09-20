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
        self.assertIn("external_evidence_complete",text)
        self.assertIn("production_admin_secret_configured",text)
        self.assertIn("neural_tts_provider_ready",text)
        self.assertIn("academy_videos_published",text)
        self.assertIn("commercial_data_licenses_verified",text)
        self.assertIn("native_store_publication_verified",text)
        self.assertIn("pull_request:",text)
        self.assertIn("branches: [main]",text)
        self.assertNotIn('ATLASQUANT_REAL_EXECUTION: "1"',text)
        self.assertNotIn("automatic_merge",text)

if __name__=="__main__":
    unittest.main()
