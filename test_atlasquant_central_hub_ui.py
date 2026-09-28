"""Central hub visibility, AION home truth, and presentation contracts."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

from atlasquant_central_hub_ui import (
    CENTRAL_CHOICE_KEY,
    CENTRAL_ROOT,
    aion_home_html,
    assert_area_access,
    central_surface_html,
    central_visibility_model,
    ecosystem_rail_html,
    request_central_destination,
    resolve_central_area,
    sync_central_choice,
)
from atlasquant_navigation_bridge import consume_navigation_request
from atlasquant_ui_v1 import navigation_labels
from atlasquant_ui_v1 import ATLASQUANT_CSS


_PRIVATE_LABELS = ("AION IA", "Negócios", "Renda Fixa")
_AION_TITLES = (
    "Administração",
    "Memória / Checkpoint Mestre",
    "Desenvolvedor",
    "Pesquisa",
    "Voz",
    "Conteúdo",
    "Automação",
    "Segurança",
    "Observabilidade",
)


def _access(role, **extra):
    payload = {"allowed": True, "mode": "AUTHENTICATED", "role": role}
    payload.update(extra)
    return payload


class CentralHubUiTests(unittest.TestCase):
    def test_admin_sees_four_areas_with_aion_first(self):
        model = central_visibility_model(_access("ADMIN"))
        self.assertEqual(
            [area["label"] for area in model["areas"]],
            ["AION IA", "Negócios", "Trader", "Renda Fixa / Investimentos"],
        )
        self.assertEqual(model["area_ids"], ("aion", "negocios", "trader", "investimentos"))
        self.assertEqual(model["priority_area"], "aion")
        self.assertEqual(model["default_area"], CENTRAL_ROOT)
        self.assertEqual(model["entry"], CENTRAL_ROOT)
        self.assertTrue(model["admin"])

    def test_non_admin_sees_only_trader(self):
        for role in ("USER", "SALES", "OPEN", "PREVIEW", "ALUNO", "ASSINANTE", ""):
            model = central_visibility_model(_access(role))
            self.assertEqual(model["area_ids"], ("trader",), role)
            self.assertEqual(model["areas"][0]["label"], "Trader")
            self.assertFalse(model["admin"])
        self.assertEqual(central_visibility_model(None)["area_ids"], ("trader",))
        self.assertEqual(central_visibility_model({"role": "ADMIN", "allowed": False})["area_ids"], ("trader",))

    def test_student_html_omits_private_areas(self):
        access = _access("USER")
        html = "\n".join([
            ecosystem_rail_html(access),
            central_surface_html(access),
            central_surface_html(access, "aion"),
            central_surface_html(access, "negocios"),
            central_surface_html(access, "Renda Fixa"),
        ])
        for label in _PRIVATE_LABELS:
            self.assertNotIn(label, html)
        self.assertIn("Trader", html)
        self.assertIn("Área privada indisponível para esta sessão.", html)
        self.assertNotIn("central=aion", html)
        self.assertNotIn("central=negocios", html)
        self.assertNotIn("central=investimentos", html)

    def test_direct_private_access_is_denied(self):
        access = _access("USER")
        for area in ("aion", "AION IA", "negocios", "Negócios", "investimentos", "Renda Fixa"):
            with self.assertRaisesRegex(ValueError, "central area access denied"):
                assert_area_access(access, area)
        self.assertEqual(assert_area_access(access, "trader"), "trader")
        self.assertEqual(assert_area_access(_access("ADMIN"), "aion"), "aion")

    def test_unknown_status_does_not_become_available(self):
        html = aion_home_html(statuses={"Administração": "DISPONÍVEL", "Voz": "PRONTO"})
        self.assertNotIn("DISPONÍVEL", html)
        self.assertNotIn("DISPONIVEL", html)
        self.assertNotIn("PRONTO", html)
        self.assertIn("UNKNOWN", html)
        self.assertIn("EM CONSTRUÇÃO", html)
        self.assertGreaterEqual(html.count('data-truth="UNKNOWN"'), 9)

    def test_aion_home_lists_nine_modules(self):
        html = aion_home_html()
        for title in _AION_TITLES:
            self.assertIn(title, html)
        self.assertEqual(html.count('class="aq-aion-module"'), 9)
        self.assertIn("Depende de Memória / Checkpoint Mestre.", html)
        self.assertIn("aq-hero", html)
        self.assertIn("aq-section-title", html)
        self.assertIn("aq-state", html)
        self.assertIn("PRIORIDADE ATUAL", html)
        self.assertIn('data-truth="UNKNOWN"', html)
        surface = central_surface_html(_access("ADMIN"), "aion")
        self.assertIn("PRIORIDADE ATUAL", surface)
        self.assertIn("border:1px solid var(--aq-aion,#b48cff)", surface)
        self.assertIn("rgba(180,140,255,.18)", surface)
        self.assertIn("@media (prefers-reduced-motion: reduce)", surface)
        self.assertNotIn("DISPONÍVEL", surface)
        self.assertNotIn("PRONTO", surface)

    def test_rail_is_vertical_and_collapses_at_760(self):
        html = ecosystem_rail_html(_access("ADMIN"), "aion")
        self.assertIn("aq-central-rail", html)
        self.assertIn("flex-direction:column", html)
        self.assertIn("@media (max-width:760px)", html)
        self.assertIn("<details", html)
        self.assertNotIn("flex-direction:row", html)
        self.assertLess(html.index("AION IA"), html.index("Negócios"))
        self.assertLess(html.index("Negócios"), html.index("Trader"))
        self.assertLess(html.index(">Trader<"), html.index("Renda Fixa"))
        self.assertEqual(html.count('<svg class="aq-central-art"'), 4)
        self.assertIn(".aq-central-rail .aq-central-art{width:44px;height:30px}", html)
        student = ecosystem_rail_html(_access("USER"))
        self.assertEqual(student.count('<svg class="aq-central-art"'), 1)
        self.assertNotIn("AION IA", student)

    def test_existing_tokens_remain_and_aion_token_is_additive(self):
        self.assertIn("--aq-bg: #07111f;", ATLASQUANT_CSS)
        self.assertIn("--aq-accent: #4fa3ff;", ATLASQUANT_CSS)
        self.assertIn("--aq-warn: #f2c14e;", ATLASQUANT_CSS)
        self.assertIn("--aq-aion: #b48cff;", ATLASQUANT_CSS)
        self.assertIn("var(--aq-aion,#b48cff)", ecosystem_rail_html(_access("ADMIN")))

    def test_no_new_admin_authority(self):
        forged = _access("USER", is_admin=True, admin=True, grant_admin=True)
        self.assertEqual(central_visibility_model(forged)["area_ids"], ("trader",))
        self.assertTrue(central_visibility_model(_access("admin"))["admin"])
        self.assertFalse(central_visibility_model({"allowed": True, "role": "USER", "admin": True})["admin"])
        source = Path("atlasquant_central_hub_ui.py").read_text(encoding="utf-8")
        for banned in ("pbkdf2", "ADMIN_USERS", "grant_admin", "subprocess", "socket"):
            self.assertNotIn(banned, source)
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                self.assertNotEqual(node.module, "streamlit")
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
                self.assertNotIn("streamlit", names)

    def test_module_has_no_sensitive_io_and_runs_without_a_server(self):
        source = Path("atlasquant_central_hub_ui.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                called.add(node.func.id)
        for banned in ("subprocess", "socket", "urllib", "requests", "http", "pathlib"):
            self.assertNotIn(banned, imported)
        for banned in ("Popen", "system", "open", "urlopen"):
            self.assertNotIn(banned, called)
        model = central_visibility_model(_access("SALES"))
        self.assertEqual(model["default_area"], "trader")
        surface = central_surface_html(_access("ADMIN"), "aion")
        self.assertIn("AION IA", surface)
        self.assertEqual(surface.count('class="aq-aion-module"'), 9)

    def test_trader_central_leaves_aion_and_shells_stay_shells(self):
        pages = list(navigation_labels())
        pages.append("🧠 AION")
        self.assertEqual(pages[0], "🎯 Radar")
        self.assertEqual(pages.index("🧠 AION"), 21)
        admin = _access("ADMIN")
        state = {
            "atlasquant_experience_mode": "Avançado",
            "atlasquant_advanced_area": "🧠 AION",
            "atlasquant_stable_nav_fallback": "🧠 AION",
        }
        request_central_destination(state, admin, "trader")
        self.assertIsNotNone(consume_navigation_request(state, available_pages=pages))
        self.assertEqual(state["atlasquant_advanced_area"], "🎯 Radar")
        self.assertEqual(state["atlasquant_stable_nav_fallback"], "🎯 Radar")
        self.assertNotEqual(pages.index(state["atlasquant_advanced_area"]), 21)

        again = {"atlasquant_experience_mode": "Avançado"}
        request_central_destination(again, admin, "aion")
        consume_navigation_request(again, available_pages=pages)
        self.assertEqual(again["atlasquant_advanced_area"], "🧠 AION")
        self.assertEqual(pages.index(again["atlasquant_advanced_area"]), 21)

        student = {
            "atlasquant_experience_mode": "Avançado",
            "atlasquant_advanced_area": "🎯 Radar",
        }
        for area in ("aion", "negocios", "investimentos"):
            with self.assertRaisesRegex(ValueError, "central area access denied"):
                request_central_destination(student, _access("USER"), area)
        self.assertEqual(student["atlasquant_advanced_area"], "🎯 Radar")

        parked = {
            "atlasquant_experience_mode": "Avançado",
            "atlasquant_advanced_area": "🧠 AION",
        }
        self.assertIsNone(request_central_destination(parked, admin, "negocios"))
        self.assertIsNone(request_central_destination(parked, admin, "Renda Fixa"))
        self.assertEqual(parked["atlasquant_advanced_area"], "🧠 AION")
        self.assertTrue(resolve_central_area(admin, "negocios")["shell"])
        self.assertTrue(resolve_central_area(admin, "investimentos")["shell"])
        self.assertFalse(resolve_central_area(admin, "trader")["shell"])

        src = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        early = src.index("_apply_central_trader_navigation()\n_aq_early_pages")
        self.assertLess(early, src.index("consume_navigation_request(", early))
        late = src.index("_apply_central_trader_navigation()\n# Guided AION")
        self.assertLess(late, src.index("consume_navigation_request(", late))
        self.assertIn('if _aq_active_index == 21:', src)
        self.assertIn('resolved.get("shell")', src)
        hold = src.index("\n_hold_admin_before_trader_shell()\n")
        self.assertLess(hold, src.index("load_home_snapshot(", hold))
        self.assertLess(early, hold)

    def test_entry_point_keeps_the_existing_aion_console(self):
        src = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn("from atlasquant_central_hub_ui import (", src)
        self.assertIn("render_central_hub,", src)
        self.assertIn("render_central_hub(_ATLASQUANT_ACCESS, requested)", src)
        self.assertIn("render_aion_admin_console(", src)
        self.assertIn('if _aq_active_index == 21:', src)

    def test_admin_without_a_choice_stays_on_the_central_root(self):
        admin = _access("ADMIN")
        resolved = resolve_central_area(admin, None)
        self.assertTrue(resolved["root"])
        self.assertEqual(resolved["area"], CENTRAL_ROOT)
        self.assertFalse(resolved["shell"])
        html = central_surface_html(admin)
        self.assertIn("CENTRAL PRINCIPAL", html)
        self.assertIn("Escolha um setor", html)
        for label in ("AION IA", "Negócios", "Trader", "Renda Fixa / Investimentos"):
            self.assertIn(label, html)
        self.assertIn("?central=aion", html)
        self.assertIn("?central=trader", html)
        self.assertIn("?central=negocios", html)
        self.assertIn("?central=investimentos", html)
        self.assertNotIn('aria-current="page">', html)
        self.assertEqual(html.count('<svg class="aq-central-art"'), 8)
        state = {}
        self.assertIsNone(request_central_destination(state, admin, "central"))
        self.assertEqual(state[CENTRAL_CHOICE_KEY], CENTRAL_ROOT)
        self.assertNotIn("atlasquant_advanced_area", state)
        synced = sync_central_choice({}, admin, None)
        self.assertTrue(synced["root"])

    def test_admin_choice_opens_trader_or_aion_and_can_return(self):
        admin = _access("ADMIN")
        trader = resolve_central_area(admin, "trader")
        self.assertFalse(trader["root"])
        self.assertFalse(trader["shell"])
        self.assertEqual(trader["area"], "trader")
        surface = central_surface_html(admin, "trader")
        self.assertIn("Voltar à Central Principal", surface)
        self.assertIn("?central=central", surface)
        self.assertNotIn("Escolha um setor", surface)
        aion = central_surface_html(admin, "aion")
        self.assertIn("PRIORIDADE ATUAL", aion)
        self.assertIn("Voltar à Central Principal", aion)
        self.assertTrue(resolve_central_area(admin, "central")["root"])
        self.assertTrue(resolve_central_area(admin, "central_root")["root"])

    def test_student_still_enters_trader_and_cannot_open_the_selector(self):
        user = _access("ALUNO")
        resolved = resolve_central_area(user, None)
        self.assertFalse(resolved["root"])
        self.assertEqual(resolved["area"], "trader")
        html = "\n".join([
            central_surface_html(user),
            central_surface_html(user, "central"),
            central_surface_html(user, "central_root"),
            ecosystem_rail_html(user),
        ])
        for label in _PRIVATE_LABELS:
            self.assertNotIn(label, html)
        self.assertNotIn("CENTRAL PRINCIPAL", html)
        self.assertNotIn("Escolha um setor", html)
        self.assertIn("Trader", html)
        forged = {CENTRAL_CHOICE_KEY: "aion"}
        synced = sync_central_choice(forged, _access("USER", grant_admin=True), None)
        self.assertEqual(synced["area"], "trader")
        self.assertTrue(synced["denied"])
        self.assertEqual(forged[CENTRAL_CHOICE_KEY], "trader")
        with self.assertRaisesRegex(ValueError, "central area access denied"):
            request_central_destination({}, user, "central")


if __name__ == "__main__":
    unittest.main()
