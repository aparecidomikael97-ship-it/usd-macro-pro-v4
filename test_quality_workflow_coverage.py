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


    def test_core_workflows_use_current_node24_action_generation(self):
        workflow_dir=ROOT/".github"/"workflows"
        names=("quality-tests.yml","autopilot-v107.yml","atlasquant-checkpoint.yml")
        joined="\n".join((workflow_dir/name).read_text(encoding="utf-8") for name in names)
        self.assertNotIn("actions/checkout@v4",joined)
        self.assertNotIn("actions/setup-python@v5",joined)
        self.assertNotIn("actions/upload-artifact@v4",joined)
        self.assertIn("actions/checkout@v7",joined)
        self.assertIn("actions/setup-python@v7",joined)
        self.assertIn("actions/upload-artifact@v7",joined)


if __name__=="__main__":
    unittest.main()
