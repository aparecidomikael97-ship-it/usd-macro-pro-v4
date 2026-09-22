import unittest
from pathlib import Path


class AtlasQuantCentralPairMatrixIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.src=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")

    def test_central_matrix_is_resolved_before_pair_workspace(self):
        central=self.src.index("# MATRIZ CENTRAL DOS 7 PARES — V11.2")
        pair_page=self.src.index("# ABA 3 — PARES",central)
        decision=self.src.index("# V9.1 — CENTRAL DE DECISÃO AUTOMÁTICA",pair_page)
        master=self.src.index("# ABA 10 — V10.2 PAINEL MESTRE",decision)
        self.assertLess(central,pair_page)
        self.assertLess(central,decision)
        self.assertLess(central,master)

    def test_only_one_matrix_builder_contract_is_used(self):
        self.assertIn("_aq_pair_matrix_result = build_pair_matrix(",self.src)
        self.assertNotIn("_build_pair_matrix_for_surfaces_v111",self.src)
        self.assertIn("matriz_v61 = pd.DataFrame()",self.src)
        self.assertIn("matriz_v61 = _aq_pair_matrix_result["matrix"].copy()",self.src)

    def test_pair_workspace_reuses_shared_usd_context(self):
        pair=self.src.index("# ABA 3 — PARES")
        body=self.src[pair:self.src.index("# ABA 4 — FED E NOTÍCIAS",pair)]
        self.assertIn('usd_ajustado = float(_aq_pair_context["usd_for_pairs"])',body)
        self.assertIn('peso_fomc_v77 = float(_aq_pair_context["fomc_weight"])',body)
        self.assertNotIn("peso_fomc_v77 = 0.0",body)
        self.assertNotIn("linhas_matriz.append({",body)

    def test_matrix_failure_is_explicit_and_fail_closed(self):
        self.assertIn("Matriz indisponível, aguardando dados completos",self.src)
        self.assertIn("Nenhuma oportunidade será criada",self.src)
        self.assertIn("atlasquant_pair_matrix_status",self.src)
        self.assertIn('"trading_side_effects": False',self.src)

    def test_all_known_matrix_consumers_are_declared(self):
        self.assertIn("_AQ_MATRIX_CONSUMER_INDICES = {0, 1, 4, 8, 9, 14}",self.src)
        for expected in (
            'if _aq_active_index == 0:',
            'if _aq_active_index == 1:',
            'if _aq_active_index == 4:',
            'if _aq_active_index == 8:',
            'if _aq_active_index == 9:',
            'if _aq_active_index == 14:',
        ):
            self.assertIn(expected,self.src)


if __name__=="__main__":
    unittest.main()
