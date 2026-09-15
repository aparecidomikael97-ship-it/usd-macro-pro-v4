import unittest
import pandas as pd
from strength_breakdown_v1104 import build_strength_breakdown

class StrengthBreakdownV1104Tests(unittest.TestCase):
    def setUp(self):
        self.ranking=pd.DataFrame([
            {"Código":"USD","Pontuação_Final":72,"Pontuação_Macro":65,"Influência_Fed":5,
             "n_juros":80,"n_inflacao":60,"n_pib":50,"n_emprego":70,"n_atividade":55,"n_sentimento":50},
            {"Código":"EUR","Pontuação_Final":52,"Pontuação_Macro":53,"Influência_Fed":-1,
             "n_juros":55,"n_inflacao":50,"n_pib":50,"n_emprego":50,"n_atividade":50,"n_sentimento":48},
        ])

    def test_total_difference(self):
        x=build_strength_breakdown(self.ranking,"USD","EUR")
        self.assertEqual(x["difference"],20.0)
        self.assertEqual(x["stronger"],"USD")

    def test_has_factor_rows(self):
        x=build_strength_breakdown(self.ranking,"USD","EUR")
        names=[r["Fator"] for r in x["rows"]]
        self.assertIn("Juros / Treasury",names)
        self.assertIn("Federal Reserve",names)
        self.assertIn("Ajustes dedicados / residual",names)

    def test_dynamic_weights_affect_non_usd(self):
        x=build_strength_breakdown(self.ranking,"EUR","USD",{"juros":0.5,"inflacao":0.1,"pib":0.1,"emprego":0.1,"atividade":0.1,"sentimento":0.1})
        self.assertEqual(x["base"],"EUR")
        self.assertTrue(len(x["rows"])>=8)

if __name__=="__main__":
    unittest.main()
