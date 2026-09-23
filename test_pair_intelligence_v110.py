import unittest
from pathlib import Path


class PairIntelligenceSourceTests(unittest.TestCase):
    def test_central_has_all_required_layers(self):
        src=Path("pair_intelligence_v110.py").read_text(encoding="utf-8")
        for term in ("SMT","Displacement","MSS","Premium/Discount","Judas/Sessão","Breaker/Mitigation","CRT","OTE","AMD / PO3","FVG"):
            self.assertIn(term,src)

    def test_g8_excludes_brl_from_header_extremes(self):
        src=Path("pair_intelligence_v110.py").read_text(encoding="utf-8")
        self.assertIn('MAJORS=("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")',src)

    def test_pair_pack_exposes_session_context_without_changing_direction(self):
        src=Path("pair_intelligence_v110.py").read_text(encoding="utf-8")
        self.assertIn('"active_session_bucket"',src)
        self.assertIn('"active_session"',src)
        self.assertIn("session_bucket_from_timestamp",src)

    def test_pair_pack_carries_auditable_technical_timestamp_and_lifecycle(self):
        src=Path("pair_intelligence_v110.py").read_text(encoding="utf-8")
        self.assertIn('"technical_timestamp"',src)
        self.assertIn('"technical_timestamp_source"',src)
        self.assertIn("SIGNAL_LIFECYCLE_PATH",src)
        self.assertIn("annotate_packs_with_lifecycle",src)
        self.assertIn('"Status temporal"',src)
        self.assertIn('"Hora leitura"',src)

    def test_operational_blocks_are_not_streamlit_system_errors(self):
        src=Path("pair_intelligence_v110.py").read_text(encoding="utf-8")
        self.assertNotIn('st.error("🚫 NENHUM SETUP EXECUTÁVEL AGORA',src)
        self.assertNotIn('st.error(f"❌ NÃO —',src)
        self.assertNotIn('st.error("**Bloqueios duros:**',src)
        self.assertIn("não erro do sistema",src)
        self.assertIn("BLOQUEIO OPERACIONAL",src)

    def test_no_profit_probability_claim(self):
        src=Path("pair_intelligence_v110.py").read_text(encoding="utf-8")
        self.assertIn("não é probabilidade de lucro",src.lower())




class AtlasQuantPackBuilderContractTests(unittest.TestCase):
    def test_builder_is_exposed_for_background_runtime(self):
        import pair_intelligence_v110 as m
        self.assertTrue(callable(m.build_pair_intelligence_packs))
        self.assertTrue(callable(m.load_current_pair_intelligence))

    def test_builder_keeps_matrix_pair_identity_and_never_enables_orders(self):
        import pandas as pd
        import pair_intelligence_v110 as m
        pairs=["EUR/USD","GBP/USD","AUD/USD","NZD/USD","USD/JPY","USD/CHF","USD/CAD"]
        matrix=pd.DataFrame([{
            "Par":pair,"Direção":"⚪ AGUARDAR CONFIRMAÇÃO","Dif. macro":0.0,
            "Score final":50.0,"Qualidade":50.0,"Confluência":"BAIXA",
            "Índice ranking":50.0,"Ranking":i+1,
        } for i,pair in enumerate(pairs)])
        ranking=pd.DataFrame([{"Código":ccy,"Pontuação_Final":50.0} for ccy in ("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")])
        packs=m.build_pair_intelligence_packs(matrix,ranking,scanner_state={},map_state={},news_state={},fed_tone="Neutro")
        self.assertEqual({p["pair"] for p in packs},set(pairs))
        self.assertEqual(len(packs),7)
        self.assertTrue(all(not bool(p.get("real_orders_enabled",False)) for p in packs))


if __name__ == "__main__":
    unittest.main()
