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
        self.assertIn('"🎯 Radar"',src)
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



    def test_pair_focus_card_escapes_external_text_and_keeps_index_nonprobabilistic(self):
        html=pair_panel.pair_focus_card_html({
            "pair":"<b>EUR/USD</b>","side":"BUY","state":"<script>x</script>",
            "reason":"<img src=x>","gate":"A","m15":"OK","unified":88,
        })
        self.assertNotIn("<b>EUR/USD</b>",html)
        self.assertNotIn("<script>",html)
        self.assertNotIn("<img src=x>",html)
        self.assertIn("&lt;b&gt;EUR/USD&lt;/b&gt;",html)
        self.assertIn("não é probabilidade",html)


if __name__=="__main__": unittest.main()
