import unittest
from pathlib import Path

from atlasquant_ui_v1 import NAVIGATION_LABELS


APP = Path("usd_macro_pro_v4_cloud.py")


class AtlasQuantAionAppIntegrationTests(unittest.TestCase):
    def test_public_navigation_contract_stays_unchanged(self):
        self.assertEqual(len(NAVIGATION_LABELS), 21)
        self.assertEqual(NAVIGATION_LABELS[0], "🎯 Radar")
        self.assertEqual(NAVIGATION_LABELS[-1], "🛟 Suporte")
        self.assertNotIn("🧠 AION", NAVIGATION_LABELS)

    def test_aion_is_appended_only_for_admin_without_shifting_legacy_indices(self):
        src = APP.read_text(encoding="utf-8")
        labels = src.index("_nav_items = list(navigation_labels())")
        role_check = src.index('if str(_ATLASQUANT_ACCESS.get("role") or "").upper() == "ADMIN":', labels)
        append = src.index('_nav_items.append("🧠 AION")', role_check)
        active_index = src.index("_aq_active_index =", append)
        self.assertLess(labels, role_check)
        self.assertLess(role_check, append)
        self.assertLess(append, active_index)

    def test_aion_workspace_has_dedicated_index_and_admin_guard(self):
        src = APP.read_text(encoding="utf-8")
        start = src.index("if _aq_active_index == 21:")
        end = src.index("# No modo GitHub Actions/AppTest", start)
        block = src[start:end]
        self.assertIn('!= "ADMIN"', block)
        self.assertIn("_build_aion_source_runtime_context()", block)
        self.assertIn("render_aion_admin_console(", block)
        self.assertIn('"market_status": _aion_market_context["summary"]', block)
        self.assertIn("except Exception as _aion_render_exc:", block)
        self.assertIn("nenhuma permissão externa foi ampliada", block)

    def test_aion_import_is_fault_isolated(self):
        src = APP.read_text(encoding="utf-8")
        self.assertIn("from atlasquant_aion_admin import render_aion_admin_console", src)
        self.assertIn("render_aion_admin_console = None", src)
        self.assertIn("_ATLASQUANT_AION_IMPORT_ERROR", src)

    def test_aion_system_identity_is_truth_labeled_but_market_is_not_invented(self):
        src = APP.read_text(encoding="utf-8")
        helper_start = src.index("def _build_aion_source_runtime_context():")
        block_start = src.index("if _aq_active_index == 21:", helper_start)
        helper = src[helper_start:block_start]
        end = src.index("# No modo GitHub Actions/AppTest", block_start)
        block = src[block_start:end]
        self.assertIn('"truth_state": "CONFIRMED"', block)
        self.assertIn('"source_build": _ATLASQUANT_SOURCE_BUILD', block)
        self.assertIn('"fresh_confirmed": market_live', helper)
        self.assertIn('market_live = bool(mesh.get("market_live_confirmed", False))', helper)
        self.assertIn("Leitura ao vivo não confirmada pelo Source Mesh", helper)
        self.assertIn('"source_mesh": _aion_source_mesh', block)

    def test_aion_does_not_replace_existing_public_support_handler(self):
        src = APP.read_text(encoding="utf-8")
        support = src.index("if _aq_active_index == 20:")
        aion = src.index("if _aq_active_index == 21:")
        self.assertLess(support, aion)
        self.assertIn("render_support_center()", src[support:aion])


if __name__ == "__main__":
    unittest.main()
