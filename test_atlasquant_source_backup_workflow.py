import unittest
from pathlib import Path

class AtlasQuantSourceBackupWorkflowTests(unittest.TestCase):
    def test_backup_workflow_is_safe_and_reproducible(self):
        path=Path(".github/workflows/atlasquant-source-backup.yml")
        self.assertTrue(path.is_file())
        text=path.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:",text)
        self.assertIn("branches: [main]",text)
        self.assertIn('ATLASQUANT_REAL_EXECUTION: "0"',text)
        self.assertIn("BACKUP_MANIFEST.txt",text)
        self.assertIn("sha256sum",text)
        self.assertIn("actions/upload-artifact@v7",text)
        self.assertIn("retention-days: 30",text)
        self.assertNotIn('ATLASQUANT_REAL_EXECUTION: "1"',text)
        self.assertNotIn("atlasquant-runtime",text)

if __name__=="__main__":
    unittest.main()
