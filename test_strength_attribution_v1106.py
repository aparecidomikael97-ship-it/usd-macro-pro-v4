import unittest
import pandas as pd
from strength_breakdown_v1104 import build_strength_breakdown, attribution_sides

class StrengthAttributionV1106(unittest.TestCase):
    def test_net_reconciles_and_sides(self):
        r=pd.DataFrame([
            {'Código':'USD','Pontuação_Final':61.4,'Pontuação_Macro':59.0,'Influência_Fed':5.0,'n_juros':80,'n_inflacao':65,'n_pib':50,'n_emprego':70,'n_atividade':55,'n_sentimento':50},
            {'Código':'EUR','Pontuação_Final':40.1,'Pontuação_Macro':41.1,'Influência_Fed':-1.0,'n_juros':45,'n_inflacao':48,'n_pib':49,'n_emprego':50,'n_atividade':44,'n_sentimento':47},
        ])
        x=build_strength_breakdown(r,'EUR','USD'); a=attribution_sides(x)
        self.assertAlmostEqual(x['difference'],-21.3,places=1)
        self.assertAlmostEqual(a['base_advantages']-a['quote_advantages'],x['difference'],places=2)
        self.assertAlmostEqual(x['explained_base'],x['base_score'],places=2)
        self.assertAlmostEqual(x['explained_quote'],x['quote_score'],places=2)

if __name__=='__main__': unittest.main()
