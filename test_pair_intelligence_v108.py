import unittest
from pathlib import Path

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

if __name__=="__main__": unittest.main()
