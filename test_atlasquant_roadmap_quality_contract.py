import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
QUALITY_WORKFLOW = ROOT / ".github" / "workflows" / "quality-tests.yml"


class AtlasQuantRoadmapQualityContractTests(unittest.TestCase):
    def test_finalization_roadmap_remains_in_quality_gate(self):
        workflow = QUALITY_WORKFLOW.read_text(encoding="utf-8")
        required_tests = (
            "test_atlasquant_data_quality_center.py",
            "test_paper_trading_v112.py",
            "test_paper_friction_v116.py",
            "test_atlasquant_backtest_paper_comparison.py",
            "test_atlasquant_setup_journal.py",
            "test_atlasquant_performance_lab.py",
            "test_atlasquant_finalization_audit.py",
            "test_atlasquant_access_control.py",
            "test_atlasquant_sales_center.py",
            "test_atlasquant_native_packaging.py",
        )
        for test_name in required_tests:
            with self.subTest(test_name=test_name):
                self.assertIn(test_name, workflow)

    def test_safety_contracts_remain_in_quality_gate(self):
        workflow = QUALITY_WORKFLOW.read_text(encoding="utf-8")
        for test_name in (
            "test_decision_integrity_v110.py",
            "test_atlasquant_adaptive_execution_gate.py",
            "test_atlasquant_commercial_safety_contract.py",
            "test_atlasquant_repository_secret_hygiene.py",
        ):
            with self.subTest(test_name=test_name):
                self.assertIn(test_name, workflow)


if __name__ == "__main__":
    unittest.main()
