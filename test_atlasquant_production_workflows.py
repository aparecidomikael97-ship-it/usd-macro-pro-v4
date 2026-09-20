import unittest
from pathlib import Path


class AtlasQuantProductionWorkflowContractTests(unittest.TestCase):
    def test_health_workflow_remains_read_only_and_checks_both_endpoints(self):
        text=Path(".github/workflows/production-health.yml").read_text(encoding="utf-8")
        self.assertIn("branches: [main]",text)
        self.assertIn("contents: read",text)
        self.assertNotIn("contents: write",text)
        self.assertIn('/_stcore/health',text)
        self.assertIn('$APP_URL/',text)
        self.assertIn('test "$code" = "200"',text)

    def test_browser_smoke_keeps_fast_home_and_safety_contract(self):
        text=Path(".github/workflows/production-browser-smoke.yml").read_text(encoding="utf-8")
        self.assertIn("branches: [main, atlasquant-integration]",text)
        self.assertIn("contents: read",text)
        self.assertNotIn("contents: write",text)
        self.assertIn("ATLASQUANT_HOME_SNAPSHOT_V1",text)
        self.assertIn('age <= 120',text)
        self.assertIn('get("real_orders") is False',text)
        self.assertIn('get("automatic_execution") is False',text)
        self.assertIn('"desktop"',text)
        self.assertIn('"mobile"',text)
        self.assertIn('"Pixel 7"',text)
        self.assertIn("MARKET INTELLIGENCE PLATFORM",text)
        self.assertIn("Safety Core monitorado",text)


if __name__=="__main__":
    unittest.main()
