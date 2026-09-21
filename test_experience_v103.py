import inspect
import unittest
import pandas as pd

try:
    import streamlit  # noqa: F401
except Exception:
    import sys, types
    st = types.ModuleType("streamlit")
    st.session_state = {}
    sys.modules["streamlit"] = st

from experience_v103 import inflation_projection, select_alert_hits, INDICATOR_GUIDE, experience_theme_summary


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
        for key in ("Taxa de juros", "CPI / IPC", "Core CPI", "PCE", "Payroll / NFP", "Desemprego", "PIB", "ISM / PMI", "Treasury 2Y", "Fed", "ADR14", "W1 / D1", "BSL / SSL", "Killzones", "Quarterly Theory"):
            self.assertIn(key, INDICATOR_GUIDE)


    def test_indicator_guide_keeps_quarterly_as_context_not_direction(self):
        item=INDICATOR_GUIDE["Quarterly Theory"]
        text=" ".join(str(v) for v in item.values()).casefold()
        self.assertIn("timing",text)
        self.assertIn("nunca",text)
        self.assertIn("gestão de risco",text)

    def test_experience_hub_accepts_mode_and_wires_guided_advanced_learning(self):
        import experience_v103 as ux
        source=inspect.getsource(ux.render_experience_hub)
        self.assertIn("experience_mode",source)
        self.assertIn("render_guided_advanced_learning",source)
        self.assertIn("advanced_mode",source)
        self.assertIn("Comece por aqui",source)

    def test_theme_preferences_fail_safe_to_known_values(self):
        out=experience_theme_summary("INVALID","gigante",1)
        self.assertEqual(out["theme"],"Claro")
        self.assertEqual(out["font_scale"],"Normal")
        self.assertTrue(out["reduced_motion"])
        self.assertTrue(out["responsive"])



if __name__ == "__main__":
    unittest.main()
