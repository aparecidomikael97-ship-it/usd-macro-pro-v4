import unittest
import pandas as pd

try:
    import streamlit  # noqa: F401
except Exception:
    import sys, types
    st = types.ModuleType("streamlit")
    st.session_state = {}
    sys.modules["streamlit"] = st

from experience_v103 import inflation_projection, select_alert_hits, INDICATOR_GUIDE


class ExperienceV103Tests(unittest.TestCase):
    def test_inflation_projection(self):
        out = inflation_projection(1000, 10, 1)
        self.assertAlmostEqual(out["future_cost"], 1100, places=2)
        self.assertLess(out["purchasing_power"], 1000)
        self.assertGreater(out["loss_pct"], 0)

    def test_alert_hits_filter(self):
        matrix = pd.DataFrame([
            {"Par":"USD/CHF","Direção":"COMPRA USD/CHF","Score final":93,"Qualidade":84},
            {"Par":"EUR/USD","Direção":"VENDA EUR/USD","Score final":82,"Qualidade":90},
            {"Par":"AUD/USD","Direção":"AGUARDAR CONFIRMAÇÃO","Score final":95,"Qualidade":95},
        ])
        hits = select_alert_hits(matrix, 85, 80)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["Par"], "USD/CHF")

    def test_glossary_has_core_macro(self):
        for key in ("CPI / IPC", "PCE", "Payroll / NFP", "Fed", "ADR14", "Killzones"):
            self.assertIn(key, INDICATOR_GUIDE)


if __name__ == "__main__":
    unittest.main()
