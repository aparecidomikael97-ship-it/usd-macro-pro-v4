import unittest
import pandas as pd
from strength_breakdown_v1104 import make_score_attribution, build_strength_breakdown, attribution_sides
from pair_intelligence_v110 import _reason_pack

class AttributionIntegrityTests(unittest.TestCase):
    def ranking(self):
        c={'Inflação':61,'Emprego':54,'Atividade':55,'Juros / Treasury 2Y':64,'Federal Reserve':76.5,'Índice amplo USD':43}
        w={'Inflação':.18,'Emprego':.18,'Atividade':.12,'Juros / Treasury 2Y':.24,'Federal Reserve':.20,'Índice amplo USD':.08}
        usd={'Código':'USD','Pontuação_Final':sum(c[k]*w[k] for k in c),'Pontuação_Macro':59.2,'Influência_Fed':26.5}
        cad={'Código':'CAD','Pontuação_Final':38.333,'Pontuação_Macro':41.233,'Influência_Fed':-2.9,
             **{f'n_{k}':41.233 for k in ('juros','inflacao','pib','emprego','atividade','sentimento')}}
        usd['strength_attribution']=make_score_attribution(usd,{}, {'componentes':c,'pesos':w})
        cad['strength_attribution']=make_score_attribution(cad,{},None)
        for r in (usd,cad): r['Pontuação_Final']=round(r['Pontuação_Final'],1)
        return pd.DataFrame([usd,cad])

    def test_real_fed_weight_and_index(self):
        x=build_strength_breakdown(self.ranking(),'USD','CAD')
        self.assertTrue(x['attribution_exact'])
        rows={r['Fator']:r for r in x['rows']}
        self.assertAlmostEqual(rows['Federal Reserve']['USD'],15.3)
        self.assertAlmostEqual(rows['Índice amplo USD']['USD'],3.44)
        self.assertNotIn('Ajustes dedicados / residual',rows)

    def test_displayed_rows_and_pair_orders_reconcile(self):
        for base,quote in [('USD','CAD'),('CAD','USD')]:
            x=build_strength_breakdown(self.ranking(),base,quote); a=attribution_sides(x)
            self.assertAlmostEqual(sum(r[base] for r in x['rows']),x['base_score'],places=2)
            self.assertAlmostEqual(sum(r[quote] for r in x['rows']),x['quote_score'],places=2)
            self.assertAlmostEqual(a['base_advantages']-a['quote_advantages'],a['net'],places=2)

    def test_reason_ranking_and_matrix_separated_without_unlock(self):
        x=_reason_pack('USD/CAD',{'Direção':'COMPRA USD/CAD','Dif. macro':22.1},self.ranking(),{},{},{})
        self.assertEqual(x['matrix_diff'],22.1)
        self.assertAlmostEqual(x['macro_diff'],x['strength']['difference'],places=2)
        self.assertIn(f"{x['strength']['difference']:.1f}",x['reason'])
        self.assertFalse(x['executable'])

    def test_clipping_explicit(self):
        r={'Código':'CAD','Pontuação_Final':100,'Influência_Fed':20,
           **{f'n_{k}':100 for k in ('juros','inflacao','pib','emprego','atividade','sentimento')}}
        a=make_score_attribution(r,{},None)
        self.assertEqual(a['other']['Limite da escala 0–100'],-20)

if __name__=='__main__': unittest.main()
