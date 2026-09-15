import unittest
import pandas as pd
from strength_breakdown_v1104 import build_strength_breakdown

class StrengthSyncV1105Tests(unittest.TestCase):
    def setUp(self):
        self.r = pd.DataFrame([
            {"Código":"USD","Pontuação_Final":61.4,"Pontuação_Macro":59.0,"Influência_Fed":5.0,
             "n_juros":80,"n_inflacao":65,"n_pib":50,"n_emprego":70,"n_atividade":55,"n_sentimento":50},
            {"Código":"CHF","Pontuação_Final":39.4,"Pontuação_Macro":40.0,"Influência_Fed":-0.6,
             "n_juros":40,"n_inflacao":45,"n_pib":50,"n_emprego":50,"n_atividade":42,"n_sentimento":48},
            {"Código":"EUR","Pontuação_Final":40.1,"Pontuação_Macro":41.1,"Influência_Fed":-1.0,
             "n_juros":45,"n_inflacao":48,"n_pib":49,"n_emprego":50,"n_atividade":44,"n_sentimento":47},
        ])

    def test_usd_chf_labels_never_become_eur_usd(self):
        x=build_strength_breakdown(self.r,"USD","CHF")
        self.assertEqual(x["base"],"USD")
        self.assertEqual(x["quote"],"CHF")
        self.assertAlmostEqual(x["difference"],22.0,places=1)
        self.assertNotEqual(x["base"],"EUR")

    def test_reconciliation_matches_final_scores(self):
        x=build_strength_breakdown(self.r,"USD","CHF")
        self.assertAlmostEqual(x["explained_base"],x["base_score"],places=2)
        self.assertAlmostEqual(x["explained_quote"],x["quote_score"],places=2)

    def test_factor_rows_have_winner(self):
        x=build_strength_breakdown(self.r,"USD","CHF")
        self.assertTrue(all("Favorece" in row for row in x["rows"]))
        self.assertTrue(all("Diferença base−cotada" in row for row in x["rows"]))

if __name__=="__main__":
    unittest.main()
