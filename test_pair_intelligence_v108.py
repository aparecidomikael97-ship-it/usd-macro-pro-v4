import unittest
from pathlib import Path
import pair_intelligence_v108 as pair_panel

class PairIntelligenceV108SourceTests(unittest.TestCase):
    def test_unified_tab_does_not_call_twelve(self):
        src=Path("pair_intelligence_v108.py").read_text(encoding="utf-8")
        self.assertNotIn("api.twelvedata.com",src)
        self.assertIn("Central Inteligente dos 7 Pares",src)
        self.assertIn("O que favorece ALTA",src)
        self.assertIn("O que favorece QUEDA",src)
        self.assertIn("ICT Execution Engine",src)

    def test_first_tab_is_unified_central(self):
        src=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn("_nav_items = list(navigation_labels())",src)
        self.assertIn('"🎯 Central"',src)
        self.assertIn("abas = st.tabs(_nav_items)",src)


    def test_pair_intelligence_uses_runtime_branch_resolver(self):
        src=Path("pair_intelligence_v108.py").read_text(encoding="utf-8")
        self.assertIn("resolve_runtime_branch(",src)
        self.assertIn("GITHUB_DATA_BRANCH",src)
        self.assertNotIn('branch="main"',src)



    def test_pair_intelligence_visual_state_is_conservative(self):
        self.assertEqual(pair_panel.pair_intelligence_status({},None)["label"],"ATENÇÃO")
        self.assertEqual(pair_panel.pair_intelligence_status({},{"forex_market_open":False})["label"],"EM ESPERA")
        self.assertEqual(pair_panel.pair_intelligence_status({"state":"🔴 BLOQUEADO / CONTRA"},{"forex_market_open":True,"healthy":True})["label"],"BLOQUEADO")
        self.assertEqual(pair_panel.pair_intelligence_status({"state":"🟢 EXECUÇÃO CONFIRMADA"},{"forex_market_open":True,"healthy":True})["label"],"CONTEXTO CONFIRMADO")
        self.assertNotIn("probabilidade",pair_panel.pair_intelligence_status({"state":"🟢 EXECUÇÃO CONFIRMADA"},{"forex_market_open":True,"healthy":True})["label"].lower())


if __name__=="__main__": unittest.main()
