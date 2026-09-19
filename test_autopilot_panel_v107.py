import unittest
from pathlib import Path
import pandas as pd
import autopilot_panel_v107 as panel

class AutopilotPanelV107Tests(unittest.TestCase):
    def test_age_future_timestamp_fails_closed(self):
        future=(pd.Timestamp.now(tz="UTC")+pd.Timedelta(minutes=5)).isoformat()
        self.assertIsNone(panel._age_min(future))

    def test_age_past_timestamp_is_nonnegative(self):
        past=(pd.Timestamp.now(tz="UTC")-pd.Timedelta(minutes=5)).isoformat()
        age=panel._age_min(past)
        self.assertIsNotNone(age)
        self.assertGreaterEqual(age,0)

    def test_panel_exposes_market_closed_and_readiness_states(self):
        src=Path("autopilot_panel_v107.py").read_text(encoding="utf-8")
        self.assertIn("MARKET_CLOSED",src)
        self.assertIn("operational_readiness",src)
        self.assertIn("Scanner pronto",src)
        self.assertIn("Market Map pronto",src)

if __name__=="__main__":
    unittest.main()
