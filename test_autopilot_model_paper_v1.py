import unittest
from pathlib import Path

import atlasquant_model_paper as model


class AutopilotModelPaperContractTests(unittest.TestCase):
    def test_model_paper_profiles_enable_only_exact_m15_and_h1_for_now(self):
        self.assertEqual(set(model.MODEL_PAPER_EXECUTION_PROFILES),{"M15","H1"})
        self.assertEqual(model.MODEL_PAPER_EXECUTION_PROFILES["M15"]["cache_key"],"m15")
        self.assertEqual(model.MODEL_PAPER_EXECUTION_PROFILES["H1"]["cache_key"],"h1")
        self.assertEqual(model.MODEL_PAPER_EXECUTION_PROFILES["H1"]["bar_minutes"],60)

    def test_autopilot_wrapper_declares_no_lower_timeframe_substitution(self):
        src=Path("autopilot_model_paper_v1.py").read_text(encoding="utf-8")
        self.assertIn('"exact_execution_frame_required":True',src)
        self.assertIn('"lower_timeframe_substitution":False',src)
        self.assertIn('"additional_market_data_calls":False',src)
        self.assertIn('"real_orders":False',src)

    def test_model_paper_runtime_declares_two_gain_lock_in_safety(self):
        src=Path("autopilot_model_paper_v1.py").read_text(encoding="utf-8")
        self.assertIn('"daily_gain_lock":"2 wins UTC no dia bloqueiam novas entradas"',src)
        self.assertIn('"daily_gain_lock_max_wins":2',src)

    def test_model_paper_does_not_enable_h4_d1_or_w1_before_exact_executor_exists(self):
        for tf in ("H4","D1","W1"):
            self.assertIsNone(model._execution_profile(tf))
            self.assertTrue(model._execution_frame({},tf).empty)


if __name__=="__main__":
    unittest.main()
