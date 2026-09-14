import unittest
import time
from unittest.mock import patch
import master_panel_v102 as m

class ScannerFreshnessV1074Tests(unittest.TestCase):
    def test_prefers_m15_fetched_at_over_old_processado_em(self):
        now = time.time()
        state = {
            "resultados": {
                "EUR/USD": {
                    "processado_em": now - 7200,  # 2h velho
                    "m15_fetched_at": now - 1200, # 20 min fresco
                    "tecnico": {
                        "disponivel": True,
                        "h4": {"status":"🟢 CONFIRMA"},
                        "h1": {"status":"🟢 PULLBACK OK"},
                        "m15": {"status":"🟡 AGUARDAR GATILHO"},
                    },
                }
            }
        }
        with patch("master_panel_v102._time.time", return_value=now):
            info = m._scanner_for_pair(state, "EUR/USD")
        self.assertTrue(info["available"])
        self.assertTrue(info["fresh"])
        self.assertEqual(info["freshness_source"], "m15_fetched_at")
        self.assertLessEqual(info["age_minutes"], 60)

    def test_old_m15_is_not_fresh(self):
        now = time.time()
        state = {
            "resultados": {
                "USD/CHF": {
                    "m15_fetched_at": now - 3900, # 65 min
                    "tecnico": {"disponivel": True},
                }
            }
        }
        with patch("master_panel_v102._time.time", return_value=now):
            info = m._scanner_for_pair(state, "USD/CHF")
        self.assertFalse(info["fresh"])

    def test_fallback_to_legacy_processado_em(self):
        now = time.time()
        state = {
            "resultados": {
                "USD/CAD": {
                    "processado_em": now - 1800,
                    "tecnico": {"disponivel": True},
                }
            }
        }
        with patch("master_panel_v102._time.time", return_value=now):
            info = m._scanner_for_pair(state, "USD/CAD")
        self.assertTrue(info["fresh"])
        self.assertEqual(info["freshness_source"], "processado_em")

if __name__ == "__main__":
    unittest.main()
