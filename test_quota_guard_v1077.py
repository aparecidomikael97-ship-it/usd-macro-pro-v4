import unittest
from pathlib import Path
import autopilot_v107 as a

class QuotaGuardV1077Tests(unittest.TestCase):
    def test_daily_classifier_is_broad(self):
        self.assertTrue(a._td_is_daily_quota("You have run out of API credits for the day"))
        self.assertTrue(a._td_is_daily_quota("Daily limit reached"))
        self.assertTrue(a._td_is_daily_quota("API credits exhausted"))

    def test_minute_classifier_is_separate(self):
        self.assertTrue(a._td_is_minute_limit("8 API credits per minute"))
        self.assertFalse(a._td_is_minute_limit("daily limit reached"))

    def test_source_stops_after_block(self):
        src = Path("autopilot_v107.py").read_text(encoding="utf-8")
        self.assertIn("if _TD_DAILY_BLOCKED:", src)
        self.assertIn("HTTP 429 QUOTA:", src)
        self.assertIn("twelve_block_type", src)
        self.assertIn('"twelve_daily_blocked"', src)
        self.assertIn('"twelve_daily_block_reason"', src)
        self.assertIn("twelve_calls_this_run", src)
        self.assertIn("_TD_HTTP_CALLS", src)

if __name__ == "__main__":
    unittest.main()
