import unittest
from pathlib import Path

from atlasquant_ui_v1 import BEGINNER_OPEN_AREAS, NAVIGATION_LABELS
from atlasquant_premium_shell import (
    PREMIUM_CSS,
    PREMIUM_MODULES,
    WORKSPACE_WELCOME,
    catalog_is_home,
    cockpit_header_html,
    alert_card_html,
    beginner_attention_html,
    consume_premium_navigation,
    empty_state_html,
    premium_catalog_html,
    request_premium_card,
    loading_state_html,
    master_command_html,
    master_surface_state_html,
    metric_card_html,
    premium_module_card_html,
    premium_panel_html,
    radar_live_html,
    section_hero_html,
    status_badge_html,
    workspace_welcome_html,
)


class PremiumShellTests(unittest.TestCase):
    def test_catalog_covers_the_requested_sectors_without_new_engines(self):
        titles = [item["title"] for item in PREMIUM_MODULES]
        for expected in (
            "Radar", "Painel Mestre", "Macroeconomia", "Microeconomia", "Geopolítica",
            "Fundamentalista", "Calendário Econômico", "Pré-Notícia", "Laboratório / Backtests",
            "Paper Trading", "Guardião de Risco", "Academia", "Diário", "Investimentos",
            "Negócios", "Vídeo / Conteúdo", "AION / Central Administrativa", "Perfil / Configurações",
        ):
            self.assertIn(expected, titles)
        self.assertEqual(len(titles), len(set(titles)))
        known = set(NAVIGATION_LABELS) | {"🧠 AION"}
        for item in PREMIUM_MODULES:
            self.assertIn(item["page"], known)
            self.assertNotIn("real_orders_enabled\": True", item["summary"])

    def test_fast_shell_targets_exist_in_the_fast_shell(self):
        import ast
        import re
        src = Path("atlasquant_fast_startup.py").read_text(encoding="utf-8")
        fast_pages = set(ast.literal_eval(re.search(r"_fast_pages=(\[[^\]]+\])", src).group(1)))
        for item in PREMIUM_MODULES:
            if item.get("fast_page"):
                self.assertIn(item["fast_page"], fast_pages, item["id"])

    def test_cards_escape_text_and_do_not_fake_click_affordance(self):
        sample = dict(PREMIUM_MODULES[0])
        sample["title"] = "<script>x</script>"
        locked = premium_module_card_html(sample, locked=True, available=True)
        self.assertNotIn("<script>", locked)
        self.assertIn("&lt;script&gt;", locked)
        self.assertIn("Navegação interna", locked)
        self.assertIn("Prévia no Iniciante", locked)
        self.assertIn("Disponível no modo Avançado", locked)
        self.assertIn("aq-premium-card", locked)

        available = premium_module_card_html(PREMIUM_MODULES[0], locked=False, available=True)
        self.assertIn("Acesso disponível", available)
        self.assertNotIn("Abrir Radar", available)
        self.assertNotIn("<a class=\"aq-premium-card\"", available)

        hero = section_hero_html("<b>", "Central", "texto")
        self.assertIn("&lt;b&gt;", hero)

    def test_navigation_only_selects_an_existing_page(self):
        state = {}
        state["atlasquant_premium_nav_target"] = "🧭 Painel mestre"
        chosen = consume_premium_navigation(
            state,
            mode="Iniciante",
            available_pages=list(NAVIGATION_LABELS),
        )
        self.assertEqual(chosen, "🧭 Painel mestre")
        self.assertEqual(state["atlasquant_beginner_area_full"], "🧭 Painel mestre")
        self.assertNotIn("atlasquant_experience_mode", state)
        blocked = {}
        blocked["atlasquant_premium_nav_target"] = "mesa secreta"
        self.assertEqual(
            consume_premium_navigation(blocked, mode="Avançado", available_pages=NAVIGATION_LABELS),
            "",
        )
        self.assertNotIn("atlasquant_advanced_area", blocked)

    def test_fast_beginner_navigation_stays_inside_the_quick_shell(self):
        state = {"atlasquant_premium_nav_target": "🎯 Radar"}
        pages = ["🎯 Radar", "🎙️ Macro", "🎓 Aprender"]
        self.assertEqual(
            consume_premium_navigation(state, mode="Iniciante", available_pages=pages, fast=True),
            "🎯 Radar",
        )
        self.assertEqual(state["aq_beginner_page"], "🎯 Radar")

    def test_beginner_layer_names_the_decision_without_color_alone(self):
        html = beginner_attention_html({
            "pair": "EUR/USD",
            "action": "NÃO OPERAR",
            "bias": "NEUTRO",
            "priority": 42,
            "news": "CPI",
            "state": "bloqueado",
            "next_action": "Aguardar.",
        })
        for label in ("Ativo em atenção", "Viés", "Confiança", "Operar ou não", "Risco / estado", "Notícia", "Próximo passo"):
            self.assertIn(label, html)
        self.assertIn("NÃO OPERAR", html)
        self.assertIn("EUR/USD", html)

    def test_master_surface_state_is_explicit_fail_closed_and_escaped(self):
        ready = master_surface_state_html("READY", "Matriz pronta", build_id="abc12345deadbeef")
        self.assertIn('data-master-state="READY"', ready)
        self.assertIn("PRONTO PARA LEITURA", ready)
        self.assertIn("Build abc12345dead", ready)
        self.assertNotIn("abc12345deadbeef", ready)

        waiting = master_surface_state_html("WAITING", "<script>aguarde</script>")
        self.assertIn("AGUARDANDO MATRIZ", waiting)
        self.assertNotIn("<script>", waiting)
        self.assertIn("&lt;script&gt;", waiting)

        snapshot = master_surface_state_html("SNAPSHOT", "continuidade")
        self.assertIn("CONTINUIDADE POR SNAPSHOT", snapshot)

        unavailable = master_surface_state_html("UNAVAILABLE", "sem módulo")
        self.assertIn("INDISPONÍVEL", unavailable)

        unknown = master_surface_state_html("qualquer", "x")
        self.assertIn("ESTADO NÃO COMPROVADO", unknown)
        self.assertIn('data-master-state="QUALQUER"', unknown)

    def test_master_panel_explains_the_separate_universe(self):
        html = master_command_html(operational_count=7)
        self.assertIn("28 pares", html)
        self.assertIn("7 pares", html)
        self.assertIn("não é erro nem regressão", html)
        for label in ("Visão geral", "Scanner", "Mapa", "Risco", "Bloqueios", "Status operacional"):
            self.assertIn(label, html)

    def test_design_system_keeps_contrast_motion_and_small_screens(self):
        self.assertIn("prefers-reduced-motion", PREMIUM_CSS)
        self.assertIn(".aq-cockpit-head", PREMIUM_CSS)
        self.assertIn('[data-testid="stMetric"]', PREMIUM_CSS)
        self.assertIn('[data-testid="stDataFrame"]', PREMIUM_CSS)
        self.assertIn("overflow-x:hidden", PREMIUM_CSS)
        self.assertIn("grid-template-columns:1fr", PREMIUM_CSS)
        self.assertIn("#f5f8fc", PREMIUM_CSS)
        self.assertIn("#d7e4f2", PREMIUM_CSS)
        self.assertIn(":focus-visible", PREMIUM_CSS)
        self.assertIn("button:disabled", PREMIUM_CSS)
        self.assertIn("aq-radar-dot", radar_live_html())
        self.assertIn("aq-ping", PREMIUM_CSS)
        self.assertIn("role=\"status\"", alert_card_html("ok", "good"))
        self.assertIn("aq-empty", empty_state_html("vazio"))
        self.assertIn("aq-loading", loading_state_html("carregando"))
        self.assertIn("aq-panel", premium_panel_html("t", "b"))
        self.assertIn("aq-metric", metric_card_html("k", "v"))
        self.assertIn("aq-badge warn", status_badge_html("atenção", "warn"))
        self.assertTrue(set(BEGINNER_OPEN_AREAS).issubset(set(NAVIGATION_LABELS)))
        self.assertTrue(catalog_is_home("🎯 Radar"))
        self.assertTrue(catalog_is_home(""))
        self.assertFalse(catalog_is_home("🧭 Painel mestre"))
        self.assertIn("flex-wrap:nowrap", PREMIUM_CSS)
        self.assertIn("overflow-x:auto", PREMIUM_CSS)
        self.assertIn("overflow-y:hidden", PREMIUM_CSS)
        self.assertIn("scroll-snap-type:x mandatory", PREMIUM_CSS)
        self.assertIn("scroll-snap-align:start", PREMIUM_CSS)
        self.assertIn("86vw", PREMIUM_CSS)
        self.assertIn("340px", PREMIUM_CSS)
        row = PREMIUM_CSS.split(".aq-premium-row{")[1].split("}")[0]
        self.assertNotIn("overflow-x:hidden", row)
        self.assertIn("-webkit-overflow-scrolling:touch", PREMIUM_CSS)
        self.assertIn("scrollbar-width:thin", PREMIUM_CSS)
        self.assertIn(".aq-premium-row::-webkit-scrollbar{height:8px}", PREMIUM_CSS)
        self.assertIn("aq-premium-scroll-hint", PREMIUM_CSS)
        self.assertIn("aq-radar-sweep", PREMIUM_CSS)

    def test_catalog_sectors_are_horizontal_strips_and_cards_carry_the_action(self):
        pages = list(NAVIGATION_LABELS) + ["🧠 AION"]
        html = premium_catalog_html(mode="Avançado", available_pages=pages, fast=False)
        for sector in ("Essencial", "Leitura", "Operação", "Ecossistema"):
            self.assertEqual(html.count(f'aria-label="{sector}"'), 1)
            self.assertIn("aq-premium-row", html)
        essencial = html.split('aria-label="Essencial"')[1].split('aria-label="Leitura"')[0]
        self.assertLess(essencial.index(">Radar<"), essencial.index(">Painel Mestre<"))
        self.assertLess(essencial.index(">Painel Mestre<"), essencial.index(">Macroeconomia<"))
        self.assertNotIn("?aq_card=", essencial)
        self.assertIn("Acesso disponível", essencial)
        self.assertNotIn("Abrir Radar", essencial)
        self.assertNotIn('<a class="aq-premium-card"', essencial)
        self.assertIn("deslize, role ou use as setas", html)
        fast_pages = ["🎯 Radar", "🎙️ Macro", "🎓 Aprender", "👤 Conta", "📱 Instalar", "💰 Investir", "🛟 Suporte"]
        fast_html = premium_catalog_html(mode="Iniciante", available_pages=fast_pages, fast=True)
        self.assertNotIn("?aq_card=", fast_html)
        self.assertIn("flex-basis:86vw", PREMIUM_CSS)
        self.assertIn("<article", fast_html)
        beginner = premium_catalog_html(mode="Iniciante", available_pages=pages, fast=False)
        self.assertNotIn("?aq_card=", beginner)
        self.assertIn("Prévia no Iniciante", beginner)
        state = {}
        self.assertEqual(
            request_premium_card(state, "master", mode="Avançado", available_pages=pages, fast=False),
            "🧭 Painel mestre",
        )
        self.assertEqual(
            consume_premium_navigation(state, mode="Avançado", available_pages=pages),
            "🧭 Painel mestre",
        )
        self.assertEqual(
            request_premium_card({}, "mesa secreta", mode="Avançado", available_pages=pages),
            "",
        )
        self.assertEqual(
            request_premium_card({}, "../radar", mode="Avançado", available_pages=pages),
            "",
        )
        blocked = {}
        self.assertEqual(
            request_premium_card(blocked, "lab", mode="Iniciante", available_pages=fast_pages, fast=True),
            "",
        )
        self.assertNotIn("atlasquant_premium_nav_target", blocked)
        aion_state = {}
        self.assertEqual(
            request_premium_card(aion_state, "aion", mode="Avançado", available_pages=pages, fast=False),
            "🧠 AION",
        )
        from atlasquant_navigation_bridge import consume_navigation_request
        consume_navigation_request(aion_state, available_pages=pages)
        self.assertEqual(aion_state["atlasquant_advanced_area"], "🧠 AION")

        business_state = {}
        self.assertEqual(
            request_premium_card(business_state, "business", mode="Avançado", available_pages=pages, fast=False),
            "🧠 AION",
        )
        self.assertEqual(business_state["aion_admin_workspace_jump"], "💼 Negócios")
        consume_navigation_request(business_state, available_pages=pages)
        self.assertEqual(business_state["atlasquant_advanced_area"], "🧠 AION")
        business_module=next(item for item in PREMIUM_MODULES if item["id"]=="business")
        self.assertEqual(business_module["page"], "🧠 AION")
        self.assertNotEqual(business_module["page"], "💼 Vendas")
        self.assertIn("Portal Comercial", business_module["summary"])
        shell = Path("atlasquant_premium_shell.py").read_text(encoding="utf-8")
        self.assertNotIn("real_orders_enabled = True", shell)
        self.assertNotIn("automatic_execution = True", shell)

    def test_workspace_welcome_covers_every_navigation_area_and_aion(self):
        expected = set(NAVIGATION_LABELS) | {"🧠 AION"}
        self.assertEqual(set(WORKSPACE_WELCOME), expected)
        for page in sorted(expected):
            with self.subTest(page=page):
                html = workspace_welcome_html(page, mode="Avançado")
                self.assertIn("Seja bem-vindo", html)
                self.assertIn("Poderoso por dentro. Simples por fora.", html)
                self.assertIn("modo Avançado", html)
                self.assertIn('aria-label="Boas-vindas da área"', html)
        self.assertEqual(workspace_welcome_html("mesa secreta"), "")

    def test_workspace_welcome_escapes_dynamic_mode_and_keeps_mobile_safe_css(self):
        html = workspace_welcome_html("🎯 Radar", mode="<script>x</script>")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("Seja bem-vindo ao Radar.", html)
        self.assertIn(".aq-workspace-welcome", PREMIUM_CSS)
        self.assertIn("overflow:hidden", PREMIUM_CSS)

    def test_catalog_renderer_uses_only_valid_native_stateful_launchers(self):
        shell = Path("atlasquant_premium_shell.py").read_text(encoding="utf-8")
        controls = shell[
            shell.index("def _render_premium_stateful_controls"):
            shell.index("def render_premium_catalog")
        ]
        self.assertIn("launchable = []", controls)
        self.assertIn("if target:", controls)
        self.assertIn("launchable.append((module, target))", controls)
        self.assertIn('st.caption(f"Acessos seguros · {sector}")', controls)
        self.assertIn('"Abrir · " + str(module["title"])', controls)
        self.assertIn("request_premium_card(", controls)
        self.assertIn("st.rerun()", controls)
        self.assertNotIn("disabled=not bool(target)", controls)
        self.assertNotIn('href=f"?aq_card=', shell)
        self.assertNotIn('href="?aq_card=', shell)

    def test_cockpit_header_escapes_copy_and_telemetry(self):
        html = cockpit_header_html("<Radar>", "x & y", telemetry={"ORDENS": "<BLOQUEADAS>"})
        self.assertIn("&lt;Radar&gt;", html)
        self.assertIn("x &amp; y", html)
        self.assertIn("&lt;BLOQUEADAS&gt;", html)
        self.assertIn("aq-cockpit-telemetry", html)

    def test_app_wires_catalog_without_removing_stable_navigation(self):
        cloud = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        catalog = cloud.index("render_premium_catalog(")
        consume = cloud.index("consume_premium_navigation(")
        home_state = cloud.index("_aq_catalog_home = bool(", consume)
        home_branch = cloud.index("if _aq_catalog_home:", home_state)
        groups_branch = cloud.index("elif navigation_groups_html is not None:", home_branch)
        select = cloud.index("render_stable_navigation(", groups_branch)
        self.assertLess(consume, home_state)
        self.assertLess(home_state, home_branch)
        self.assertLess(home_branch, groups_branch)
        self.assertLess(groups_branch, catalog)
        self.assertLess(catalog, select)
        self.assertIn("mobile_navigation_hint_html()", cloud[home_branch:groups_branch])
        self.assertNotIn("navigation_groups_html()", cloud[home_branch:groups_branch])
        groups_block = cloud[groups_branch:catalog]
        self.assertIn("navigation_groups_html()", groups_block)
        self.assertNotIn("mobile_navigation_hint_html()", groups_block)
        self.assertIn("workspace_welcome_html,", cloud)
        self.assertIn("workspace_welcome_html(", cloud)
        welcome_pos = cloud.index("workspace_welcome_html(")
        locked_pos = cloud.index("_aq_locked_preview = bool(", welcome_pos)
        self.assertLess(welcome_pos, locked_pos)
        fast = Path("atlasquant_fast_startup.py").read_text(encoding="utf-8")
        self.assertLess(fast.index("consume_premium_navigation("), fast.index('key="aq_beginner_page"'))
        home = Path("atlasquant_home_radar.py").read_text(encoding="utf-8")
        self.assertIn("beginner_attention_html", home)
        self.assertIn("Top 10 em observação", home)
        self.assertIn("prefers-reduced-motion", home)
        master = Path("master_panel_v102.py").read_text(encoding="utf-8")
        self.assertIn("master_command_html", master)
        self.assertIn("matrix.head(7)", master)


if __name__ == "__main__":
    unittest.main()
