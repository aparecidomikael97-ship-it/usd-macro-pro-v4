import unittest
from pathlib import Path
import autopilot_v107 as a

class AutopilotRecoveryV1075Tests(unittest.TestCase):
    def test_daily_budget_is_conservative(self):
        self.assertLessEqual(a.AUTOPILOT_DAILY_CALL_BUDGET, 500)

    def test_nonpriority_frequencies_reduce_daily_usage(self):
        self.assertGreaterEqual(a.M15_EVERY_MIN, 50)
        self.assertGreaterEqual(a.H1_EVERY_MIN, 110)
        self.assertGreaterEqual(a.H4_EVERY_MIN, 230)

    def test_priority_still_checks_m15_faster(self):
        self.assertLess(a.PRIORITY_M15_EVERY_MIN, a.M15_EVERY_MIN)

    def test_workflow_creates_streamlit_secrets(self):
        wf = Path(".github/workflows/autopilot-v107.yml").read_text(encoding="utf-8")
        self.assertIn("Create Streamlit secrets for headless app", wf)
        self.assertIn(".streamlit/secrets.toml", wf)
        self.assertIn("GITHUB_TOKEN_HISTORICO", wf)

    def test_runner_reports_429_message(self):
        src = Path("autopilot_v107.py").read_text(encoding="utf-8")
        self.assertIn("HTTP 429:", src)

if __name__ == "__main__":
    unittest.main()
