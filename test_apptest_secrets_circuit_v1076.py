import unittest
from pathlib import Path
import autopilot_v107 as a

class AppTestSecretsCircuitV1076Tests(unittest.TestCase):
    def test_runner_injects_apptest_secrets(self):
        src = Path("autopilot_v107.py").read_text(encoding="utf-8")
        self.assertIn('at.secrets[key] = value', src)
        self.assertIn('App headless executado;', src)

    def test_daily_circuit_breaker_exists(self):
        src = Path("autopilot_v107.py").read_text(encoding="utf-8")
        self.assertIn("_TD_DAILY_BLOCKED", src)
        self.assertIn("HTTP 429 DAILY:", src)
        self.assertIn("API_COTA_DIARIA_BLOQUEADA", src)

    def test_budget_remains_conservative(self):
        self.assertLessEqual(a.AUTOPILOT_DAILY_CALL_BUDGET, 500)

if __name__ == "__main__":
    unittest.main()
