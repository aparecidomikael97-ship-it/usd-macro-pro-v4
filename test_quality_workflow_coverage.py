import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent
WORKFLOW=ROOT/".github"/"workflows"/"quality-tests.yml"

class QualityWorkflowCoverageTests(unittest.TestCase):
    def test_every_root_test_file_is_executed_by_quality_workflow(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        listed=set(re.findall(r"(?m)^\s+(test_[A-Za-z0-9_]+\.py)\s*\\?$",text))
        discovered={p.name for p in ROOT.glob("test_*.py")}
        missing=sorted(discovered-listed)
        self.assertEqual(missing,[],f"Quality workflow omits test files: {missing}")

if __name__=="__main__":
    unittest.main()
