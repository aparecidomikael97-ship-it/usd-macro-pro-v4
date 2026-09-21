import ast
import unittest
from pathlib import Path

from atlasquant_ui_v1 import NAVIGATION_LABELS


APP=Path("usd_macro_pro_v4_cloud.py")


class AtlasQuantNavigationStabilityTests(unittest.TestCase):
    def test_primary_navigation_does_not_mount_twenty_streamlit_tabs(self):
        src=APP.read_text(encoding="utf-8")
        self.assertNotIn("st.tabs(_nav_items)",src)
        self.assertNotIn("with abas[",src)
        self.assertIn("render_stable_navigation(",src)
        self.assertIn("_aq_active_index",src)

    def test_every_primary_workspace_is_guarded_by_active_index(self):
        src=APP.read_text(encoding="utf-8")
        for idx in range(len(NAVIGATION_LABELS)):
            self.assertIn(f"if _aq_active_index == {idx}:",src)
        self.assertGreaterEqual(src.count("if _aq_active_index =="),len(NAVIGATION_LABELS))

    def test_only_selected_workspace_executes_at_top_level(self):
        tree=ast.parse(APP.read_text(encoding="utf-8"))
        guarded=[]
        for node in tree.body:
            if not isinstance(node,ast.If):
                continue
            test=ast.unparse(node.test)
            if "_aq_active_index ==" in test:
                guarded.append(test)
        self.assertGreaterEqual(len(guarded),len(NAVIGATION_LABELS))

    def test_stable_navigation_preserves_all_twenty_endpoints(self):
        self.assertEqual(len(NAVIGATION_LABELS),21)
        self.assertEqual(NAVIGATION_LABELS[0],"🎯 Radar")
        self.assertEqual(NAVIGATION_LABELS[-1],"🛟 Suporte")
        self.assertIn("⚡ Decisão",NAVIGATION_LABELS)
        self.assertIn("🤖 Autopilot",NAVIGATION_LABELS)
        self.assertIn("💰 Investir",NAVIGATION_LABELS)

    def test_no_javascript_dom_mutation_workaround_was_added(self):
        src=APP.read_text(encoding="utf-8")
        ui=Path("atlasquant_ui_v1.py").read_text(encoding="utf-8")
        combined=src+"\n"+ui
        self.assertNotIn("removeChild(",combined)
        self.assertNotIn("MutationObserver(",combined)
        self.assertNotIn("document.querySelector(",combined)
        self.assertNotIn("window.parent.document",combined)

    def test_navigation_change_is_presentation_only(self):
        ui=Path("atlasquant_ui_v1.py").read_text(encoding="utf-8")
        self.assertIn("reduzindo carga e instabilidade de DOM no celular",ui)
        for forbidden in ("Score Mestre =","real_orders_enabled=True","automatic_execution=True"):
            self.assertNotIn(forbidden,ui)

    def test_radar_and_master_matrix_do_not_depend_on_opening_pair_tab_first(self):
        src=APP.read_text(encoding="utf-8")
        builder=src.index("def _build_pair_matrix_for_surfaces_v111")
        init=src.index("matriz_v61=_build_pair_matrix_for_surfaces_v111()",builder)
        market=src.index("# ABA 9 — V10.2 PROFESSIONAL MACRO MARKET MAP")
        master=src.index("# ABA 1 — V10.2.2 PAINEL MESTRE")
        pair_tab=src.index("if _aq_active_index == 4:")
        self.assertGreaterEqual(builder,0)
        self.assertLess(builder,market)
        self.assertLess(init,market)
        self.assertLess(builder,master)
        self.assertGreater(pair_tab,-1)
        self.assertIn('matriz_v61=_build_pair_matrix_for_surfaces_v111()',src)
        self.assertIn('_matrix_master_v102 = globals().get("matriz_v61")',src)

    def test_central_matrix_contract_is_seven_unique_fx_pairs(self):
        src=APP.read_text(encoding="utf-8")
        self.assertIn('["EUR/USD","GBP/USD","AUD/USD","NZD/USD","USD/JPY","USD/CHF","USD/CAD"]',src)
        self.assertIn('_df.insert(0,"Ranking",range(1,len(_df)+1))',src)
        compact="".join(src.split())
        self.assertIn('sort_values(["Índiceranking","Qualidade","Scorefinal"]',compact)
        self.assertIn('"⚪ AGUARDAR CONFIRMAÇÃO"',src)

    def test_shared_matrix_uses_official_confluence_engine_not_approximation(self):
        src=APP.read_text(encoding="utf-8")
        start=src.index("def _build_pair_matrix_for_surfaces_v111")
        end=src.index('if "matriz_v61" not in globals()',start)
        helper=src[start:end]
        self.assertIn("calcular_confluencia_v60(",helper)
        self.assertIn('_conf["score_confluencia"]',helper)
        self.assertIn('_conf["qualidade_confluencia"]',helper)
        self.assertNotIn("50.0+abs(_dif)*1.25",helper)

    def test_market_map_matrix_exists_before_first_consumer(self):
        src=APP.read_text(encoding="utf-8")
        init=src.index("matriz_v61=_build_pair_matrix_for_surfaces_v111()")
        market=src.index("if _aq_active_index == 9:")
        render=src.index("render_market_map(matriz_v61",market)
        self.assertLess(init,market)
        self.assertLess(init,render)


if __name__=="__main__":
    unittest.main()
