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


if __name__=="__main__":
    unittest.main()
