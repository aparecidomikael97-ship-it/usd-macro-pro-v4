import unittest
import pandas as pd

try:
    import streamlit  # noqa
except Exception:
    import sys, types
    st = types.ModuleType("streamlit")
    st.session_state = {}
    sys.modules["streamlit"] = st

from evolution_v105 import (
    HISTORY_V105, EXECUTION_PLAN, _normalize_series, _evaluate_alert,
    _limit_for_period, _load_preferences
)

class EvolutionV105Tests(unittest.TestCase):
    def test_trade_balance_added(self):
        self.assertIn("Saldo comercial", HISTORY_V105)

    def test_normalization_base_100(self):
        df = pd.DataFrame({
            "date": pd.to_datetime(["2026-01-01", "2026-02-01"]),
            "value": [10.0, 12.0]
        })
        out = _normalize_series(df, "X")
        self.assertAlmostEqual(float(out.iloc[0]["normalized"]), 100.0)
        self.assertAlmostEqual(float(out.iloc[1]["normalized"]), 120.0)

    def test_alert_logic(self):
        self.assertTrue(_evaluate_alert(5.1, "Acima de", 5.0))
        self.assertTrue(_evaluate_alert(4.9, "Abaixo de", 5.0))
        self.assertFalse(_evaluate_alert(4.9, "Acima de", 5.0))

    def test_one_month_limit(self):
        self.assertEqual(_limit_for_period("1 mês", "daily"), 35)
        self.assertEqual(_limit_for_period("1 mês", "monthly"), 2)

    def test_plan_has_requested_phases(self):
        text = " ".join(EXECUTION_PLAN["Fase"].astype(str).tolist())
        for phase in ("Diagnóstico", "Interatividade", "Contextualização", "Personalização",
                      "Design", "Atualização", "Feedback"):
            self.assertIn(phase, text)

    def test_preferences_json(self):
        ok, obj = _load_preferences(b'{"layout":"Compacto"}')
        self.assertTrue(ok)
        self.assertEqual(obj["layout"], "Compacto")

if __name__ == "__main__":
    unittest.main()
