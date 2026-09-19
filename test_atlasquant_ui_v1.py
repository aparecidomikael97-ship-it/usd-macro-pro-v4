import unittest

from atlasquant_ui_v1 import ATLASQUANT_CSS, NAVIGATION_LABELS, NAVIGATION_GROUPS, hero_html, navigation_labels, navigation_groups, navigation_groups_html, operation_focus_html, score_semantics, section_title_html, state_badge_html, decision_strip_html, context_strip_html


class AtlasQuantUiTests(unittest.TestCase):
    def test_navigation_includes_macro_briefing_without_losing_endpoints(self):
        self.assertEqual(len(NAVIGATION_LABELS), 19)
        self.assertIn("🎙️ Macro Briefing", NAVIGATION_LABELS)
        self.assertEqual(navigation_labels()[0], "🎯 Central")
        self.assertEqual(navigation_labels()[-1], "💼 Vendas")
        self.assertIn("📱 Instalar", navigation_labels())
        self.assertIn("👤 Conta", navigation_labels())
        self.assertIn("🤖 Autopilot", navigation_labels())

    def test_navigation_groups_cover_every_endpoint_once(self):
        grouped=[item for _, items in navigation_groups() for item in items]
        self.assertEqual(len(NAVIGATION_GROUPS),5)
        self.assertEqual(len(grouped),len(NAVIGATION_LABELS))
        self.assertEqual(set(grouped),set(NAVIGATION_LABELS))
        self.assertEqual(len(grouped),len(set(grouped)))
        html=navigation_groups_html()
        self.assertIn("Operação",html)
        self.assertIn("Mercado",html)
        self.assertIn("Pesquisa",html)
        self.assertIn("Sistema",html)
        self.assertIn("Conta",html)


    def test_operation_focus_is_safe_and_responsive(self):
        html=operation_focus_html(
            decision="<NÃO OPERAR>",
            market="EUR/USD",
            data="98%",
            safety="BLOQUEADO",
        )
        self.assertIn("&lt;NÃO OPERAR&gt;",html)
        self.assertIn("EUR/USD",html)
        self.assertIn("98%",html)
        self.assertIn("BLOQUEADO",html)
        self.assertIn("aq-focus-main",html)
        self.assertIn("aq-focus-card",html)
        self.assertIn("aq-focus",ATLASQUANT_CSS)
        self.assertIn("grid-template-columns:1fr 1fr",ATLASQUANT_CSS)

    def test_score_semantics_is_not_probability(self):
        self.assertEqual(score_semantics(80)["label"], "FORTE")
        self.assertEqual(score_semantics(50)["label"], "NEUTRO")
        self.assertEqual(score_semantics(None)["label"], "SEM DADO")

    def test_score_is_clamped_for_presentation(self):
        self.assertEqual(score_semantics(999)["label"], "FORTE")
        self.assertEqual(score_semantics(-10)["label"], "MUITO FRACO")

    def test_header_escapes_external_text(self):
        html = hero_html('<script>alert(1)</script>', 'dev')
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('ATLASQUANT', html)


    def test_theme_has_responsive_mobile_and_consistent_controls(self):
        from atlasquant_ui_v1 import ATLASQUANT_CSS
        self.assertIn("@media (max-width: 760px)", ATLASQUANT_CSS)
        self.assertIn('data-testid="stButton"', ATLASQUANT_CSS)
        self.assertIn("stMainBlockContainer", ATLASQUANT_CSS)
        self.assertIn('data-testid="stMetric"', ATLASQUANT_CSS)



    def test_reusable_ui_primitives_escape_text_and_restrict_tones(self):
        section=section_title_html("<script>x</script>","⚡")
        badge=state_badge_html("<b>READY</b>","evil")
        self.assertNotIn("<script>",section)
        self.assertIn("&lt;script&gt;",section)
        self.assertNotIn("<b>READY</b>",badge)
        self.assertIn("aq-state-info",badge)



    def test_main_sidebar_groups_advanced_controls(self):
        from pathlib import Path
        src=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn('st.sidebar.expander("⚙️ Modelo macro"',src)
        self.assertIn('st.sidebar.expander("🏦 Sensibilidade ao Fed"',src)
        self.assertIn('st.sidebar.expander("📡 Fontes & status"',src)



    def test_main_tabs_reuse_navigation_labels_without_changing_count(self):
        from pathlib import Path
        src=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn("_nav_items = list(navigation_labels())",src)
        self.assertIn("abas = st.tabs(_nav_items)",src)
        self.assertIn("navigation_groups_html()",src)
        self.assertEqual(len(NAVIGATION_LABELS),19)



    def test_decision_strip_escapes_content_and_is_not_probability(self):
        html=decision_strip_html("<b>EUR/USD</b>","BUY","AGUARDAR","NORMAL",88)
        self.assertNotIn("<b>EUR/USD</b>",html)
        self.assertIn("&lt;b&gt;EUR/USD&lt;/b&gt;",html)
        self.assertIn("QUALIDADE",html)
        self.assertNotIn("probabilidade",html.lower())



    def test_tab_navigation_is_mobile_scrollable_and_sticky(self):
        from atlasquant_ui_v1 import ATLASQUANT_CSS, UI_VERSION
        self.assertEqual(UI_VERSION,"0.8")
        self.assertIn("overflow-x: auto",ATLASQUANT_CSS)
        self.assertIn("flex-wrap: nowrap",ATLASQUANT_CSS)
        self.assertIn("position: sticky",ATLASQUANT_CSS)
        self.assertIn("white-space: nowrap",ATLASQUANT_CSS)
        self.assertIn("aq-nav-groups",ATLASQUANT_CSS)



    def test_context_strip_escapes_values_and_keeps_brand_state_compact(self):
        html=context_strip_html("<b>Neutro</b>",0.25,"ALTA","local")
        self.assertNotIn("<b>Neutro</b>",html)
        self.assertIn("&lt;b&gt;Neutro&lt;/b&gt;",html)
        self.assertIn("+0.25",html)
        self.assertIn("QUALIDADE USD",html)
        self.assertIn("LOCAL",html)

    def test_primary_app_header_is_at_execution_start_not_duplicated_before_tabs(self):
        from pathlib import Path
        src=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertEqual(src.count("render_atlasquant_header(APP_VERSION, environment=ATLASQUANT_ENVIRONMENT)"),1)
        self.assertNotIn('st.title("USD Macro Pro")',src)
        exec_pos=src.index("# EXECUÇÃO PRINCIPAL")
        hero_pos=src.index("render_atlasquant_header(APP_VERSION, environment=ATLASQUANT_ENVIRONMENT)")
        tabs_pos=src.index("abas = st.tabs(_nav_items)")
        self.assertLess(exec_pos,hero_pos)
        self.assertLess(hero_pos,tabs_pos)



if __name__ == "__main__":
    unittest.main()
