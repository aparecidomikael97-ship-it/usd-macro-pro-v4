"""Central hub visibility, AION home truth, and presentation contracts."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from atlasquant_central_hub_ui import (
    AION_MODULE_JUMP_KEY,
    CENTRAL_CHOICE_KEY,
    CENTRAL_ROOT,
    DEFAULT_TIMEZONE,
    LOGIN_GREETING_KEY,
    acknowledge_login_greeting,
    aion_home_claims,
    aion_home_viewer_html,
    application_timezone,
    consume_aion_module_jump,
    aion_home_html,
    aion_login_presence_html,
    assert_area_access,
    central_surface_html,
    central_visibility_model,
    clear_login_greeting,
    ecosystem_rail_html,
    greeting_period,
    login_greeting,
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
        business_request=request_central_destination(parked, admin, "negocios")
        self.assertEqual(business_request["workspace"], "💼 Negócios")
        self.assertEqual(business_request["state"], "BUSINESS_WORKSPACE_REQUESTED")
        self.assertEqual(parked["aion_admin_workspace_jump"], "💼 Negócios")
        self.assertIsNone(request_central_destination(parked, admin, "Renda Fixa"))
        self.assertEqual(parked["atlasquant_advanced_area"], "🧠 AION")
        self.assertFalse(resolve_central_area(admin, "negocios")["shell"])
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
        self.assertIn(
            "render_central_hub(_ATLASQUANT_ACCESS, requested, defer_aion_home=(active_index == 21))",
            src,
        )
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
        self.assertNotIn("?central=", html)
        for area_id in ("aion", "trader", "negocios", "investimentos"):
            self.assertIn(f'data-central-area="{area_id}"', html)
        self.assertNotIn('aria-current="page">', html)
        self.assertEqual(html.count('<svg class="aq-central-art"'), 8)
        state = {}
        self.assertIsNone(request_central_destination(state, admin, "central"))
        self.assertEqual(state[CENTRAL_CHOICE_KEY], CENTRAL_ROOT)
        self.assertNotIn("atlasquant_advanced_area", state)
        synced = sync_central_choice({}, admin, None)
        self.assertTrue(synced["root"])

    def test_admin_business_surface_uses_new_demo_without_changing_navigation(self):
        admin = _access("ADMIN")
        html = central_surface_html(admin, "negocios")
        self.assertIn("AION BUSINESS // DEMO SEGURA", html)
        self.assertIn("Poderoso por dentro. Simples por fora.", html)
        self.assertIn("BUSINESS CERTIFIED", html)
        self.assertIn("RUNTIME OFF", html)
        self.assertIn("dados fictícios", html)
        self.assertIn("Voltar à Central Principal", html)
        self.assertNotIn("EM CONSTRUÇÃO", html)
        user_html = central_surface_html(_access("USER"), "negocios")
        self.assertNotIn("AION BUSINESS // DEMO SEGURA", user_html)
        self.assertIn("Área privada indisponível para esta sessão.", user_html)

        state = {"atlasquant_experience_mode": "Avançado"}
        request = request_central_destination(state, admin, "negocios")
        self.assertEqual(request["workspace"], "💼 Negócios")
        self.assertEqual(state["aion_admin_workspace_jump"], "💼 Negócios")

    def test_admin_choice_opens_trader_or_aion_and_can_return(self):
        admin = _access("ADMIN")
        trader = resolve_central_area(admin, "trader")
        self.assertFalse(trader["root"])
        self.assertFalse(trader["shell"])
        self.assertEqual(trader["area"], "trader")
        surface = central_surface_html(admin, "trader")
        self.assertIn("Voltar à Central Principal", surface)
        self.assertNotIn("?central=", surface)
        self.assertNotIn("Escolha um setor", surface)
        aion = central_surface_html(admin, "aion")
        self.assertIn("PRIORIDADE ATUAL", aion)
        self.assertIn("Voltar à Central Principal", aion)
        self.assertTrue(resolve_central_area(admin, "central")["root"])
        self.assertTrue(resolve_central_area(admin, "central_root")["root"])

    def test_streamlit_edge_uses_stateful_controls_not_query_anchors(self):
        source = Path("atlasquant_central_hub_ui.py").read_text(encoding="utf-8")
        self.assertIn("def _render_central_navigation_controls", source)
        self.assertIn("request_central_destination(st.session_state, access, area_id)", source)
        self.assertIn("st.rerun()", source)
        self.assertNotIn('href="?central=', source)

        cloud = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn('del st.query_params["central"]', cloud)
        self.assertIn("Consume a deep-link once", cloud)
        self.assertNotIn('requested = st.query_params.get("central", "")\n        if isinstance(requested', cloud[cloud.index("def _apply_central_trader_navigation"):])

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
        self.assertNotIn('<section class="aq-aion-presence"', html)
        self.assertNotIn("AION ativo", html)


class LoginGreetingTests(unittest.TestCase):
    def _admin(self, **session):
        payload = {"username": "mikael", "role": "ADMIN", "authenticated_at": 10}
        payload.update(session)
        return _access("ADMIN", session=payload)

    def test_authenticated_admin_is_greeted_on_the_central_door(self):
        now = datetime(2026, 9, 27, 23, 30, tzinfo=timezone.utc)
        admin = self._admin()
        html = central_surface_html(admin, now=now)
        self.assertLess(html.index('<section class="aq-aion-presence"'), html.index('<div class="aq-central-choices">'))
        self.assertEqual(html.count('<section class="aq-aion-presence"'), 1)
        self.assertIn("AION", html)
        self.assertIn("ATIVO", html)
        self.assertIn("Mikael, boa noite. AION ativo.", html)
        self.assertIn("Bem-vindo ao AtlasQuant. O que você gostaria de saber ou fazer?", html)
        self.assertIn("Abrir AION", html)
        for label in ("AION IA", "Negócios", "Trader", "Renda Fixa / Investimentos"):
            self.assertIn(label, html)
        self.assertIn('data-root="central_root"', html)
        state = {}
        before = dict(admin)
        spoken = acknowledge_login_greeting(state, admin, now=now)
        self.assertTrue(spoken["announced"])
        self.assertFalse(spoken["spoken"])
        self.assertEqual(admin, before)
        self.assertNotIn("atlasquant_advanced_area", state)
        self.assertNotIn(CENTRAL_CHOICE_KEY, state)
        self.assertTrue(resolve_central_area(admin, None)["root"])
        self.assertIn("@media (prefers-reduced-motion: reduce)", html)
        self.assertIn(".aq-aion-presence", html)

    def test_period_follows_the_application_clock(self):
        admin = self._admin()
        morning = login_greeting(admin, now=datetime(2026, 9, 27, 11, 0, tzinfo=timezone.utc))
        afternoon = login_greeting(admin, now=datetime(2026, 9, 27, 17, 0, tzinfo=timezone.utc))
        night = login_greeting(admin, now=datetime(2026, 9, 27, 23, 30, tzinfo=timezone.utc))
        self.assertIn("bom dia", morning["text"])
        self.assertIn("boa tarde", afternoon["text"])
        self.assertIn("boa noite", night["text"])
        self.assertIn("Mikael, bom dia. AION ativo.", aion_login_presence_html(admin, now=datetime(2026, 9, 27, 11, 0, tzinfo=timezone.utc)))

    def test_greeting_clock_is_cuiaba_and_an_invalid_zone_falls_back(self):
        cuiaba = ZoneInfo("America/Cuiaba")

        def wall(hour, minute):
            return datetime(2026, 9, 27, hour, minute, tzinfo=cuiaba)

        self.assertEqual(greeting_period(wall(11, 59), timezone_name="America/Cuiaba"), "Bom dia")
        self.assertEqual(greeting_period(wall(12, 0), timezone_name="America/Cuiaba"), "Boa tarde")
        self.assertEqual(greeting_period(wall(17, 59), timezone_name="America/Cuiaba"), "Boa tarde")
        self.assertEqual(greeting_period(wall(18, 0), timezone_name="America/Cuiaba"), "Boa noite")
        self.assertEqual(greeting_period(wall(4, 59), timezone_name="America/Cuiaba"), "Boa noite")
        self.assertEqual(greeting_period(wall(5, 0), timezone_name="America/Cuiaba"), "Bom dia")
        self.assertEqual(greeting_period(datetime(2026, 9, 27, 18, 0), timezone_name="America/Cuiaba"), "Boa noite")
        utc = datetime(2026, 6, 15, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(greeting_period(utc, timezone_name="America/Cuiaba"), "Bom dia")
        self.assertEqual(greeting_period(utc, timezone_name="America/Sao_Paulo"), "Boa tarde")
        self.assertEqual(greeting_period(utc, timezone_name="Not/AZone"), "Bom dia")
        self.assertEqual(application_timezone("Not/AZone").key, "America/Cuiaba")
        self.assertEqual(application_timezone("").key, DEFAULT_TIMEZONE)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ATLASQUANT_TIMEZONE", None)
            self.assertEqual(application_timezone(None).key, "America/Cuiaba")
            self.assertEqual(greeting_period(utc), "Bom dia")
        with patch.dict(os.environ, {"ATLASQUANT_TIMEZONE": "Invalid/Zone"}):
            self.assertEqual(greeting_period(utc), "Bom dia")
        with patch.dict(os.environ, {"ATLASQUANT_TIMEZONE": "America/Sao_Paulo"}):
            self.assertEqual(greeting_period(utc), "Boa tarde")
        user = _access("USER", session={"username": "cliente", "role": "USER", "authenticated_at": 3})
        self.assertFalse(login_greeting(user, now=wall(11, 59), timezone_name="America/Cuiaba")["show"])
        self.assertEqual(aion_login_presence_html(user, now=wall(11, 59), timezone_name="America/Cuiaba"), "")
        admin = self._admin()
        self.assertIn("Mikael, bom dia. AION ativo.", aion_login_presence_html(admin, now=wall(11, 59), timezone_name="America/Cuiaba"))
        hub = Path("atlasquant_central_hub_ui.py").read_text(encoding="utf-8")
        self.assertIn("from atlasquant_aion_clock import (", hub)
        self.assertNotIn("if 5 <= moment.hour", hub)
        clock = Path("atlasquant_aion_clock.py").read_text(encoding="utf-8")
        period = clock[clock.index("def greeting_period"):]
        self.assertNotIn("greeting_for", period)
        self.assertIsNone(re.search(r"datetime\.now\(\s*\)", period))
        self.assertIn("datetime.now(timezone.utc)", period)

    def test_user_and_unauthenticated_admin_get_no_greeting(self):
        now = datetime(2026, 9, 27, 11, 0, tzinfo=timezone.utc)
        for access in (
            _access("USER", session={"username": "cliente", "role": "USER", "authenticated_at": 3}),
            _access("ALUNO", session={"username": "aluno", "role": "ALUNO"}),
            {"allowed": False, "role": "ADMIN", "session": {"username": "mikael", "authenticated_at": 3}},
            {"role": "ADMIN"},
        ):
            with self.subTest(role=access.get("role"), allowed=access.get("allowed")):
                self.assertFalse(login_greeting(access, now=now)["show"])
                self.assertEqual(aion_login_presence_html(access, now=now), "")
                state = {}
                result = acknowledge_login_greeting(state, access, now=now)
                self.assertFalse(result["announced"])
                self.assertNotIn(LOGIN_GREETING_KEY, state)

    def test_rerun_does_not_announce_twice_and_a_new_login_can(self):
        now = datetime(2026, 9, 27, 17, 0, tzinfo=timezone.utc)
        admin = self._admin()
        calls = []
        state = {}
        first = acknowledge_login_greeting(state, admin, now=now, speak=calls.append)
        second = acknowledge_login_greeting(state, admin, now=now, speak=calls.append)
        self.assertTrue(first["announced"])
        self.assertFalse(second["announced"])
        self.assertEqual(calls, [])
        self.assertEqual(state[LOGIN_GREETING_KEY]["mark"], "mikael|10")
        fresh = self._admin(authenticated_at=99)
        again = acknowledge_login_greeting(state, fresh, now=now, speak=calls.append)
        self.assertTrue(again["announced"])
        clear_login_greeting(state)
        self.assertNotIn(LOGIN_GREETING_KEY, state)
        after_logout = acknowledge_login_greeting(state, admin, now=now)
        self.assertTrue(after_logout["announced"])

    def test_unavailable_voice_does_not_block_the_greeting(self):
        now = datetime(2026, 9, 27, 11, 0, tzinfo=timezone.utc)
        admin = self._admin()

        def boom(_text):
            raise RuntimeError("tts indisponível")

        quiet = acknowledge_login_greeting({}, admin, now=now, provider_configured=False, speak=boom)
        self.assertTrue(quiet["announced"])
        self.assertIn("AION ativo", quiet["text"])
        self.assertFalse(quiet["spoken"])
        self.assertFalse(quiet["voice_failed"])
        failed = acknowledge_login_greeting({}, admin, now=now, provider_configured=True, speak=boom)
        self.assertTrue(failed["announced"])
        self.assertIn("Bem-vindo ao AtlasQuant", failed["text"])
        self.assertTrue(failed["voice_ready"])
        self.assertTrue(failed["voice_failed"])
        self.assertFalse(failed["spoken"])

    def test_unconfirmed_status_is_omitted(self):
        now = datetime(2026, 9, 27, 23, 30, tzinfo=timezone.utc)
        admin = self._admin()
        html = aion_login_presence_html(
            admin,
            now=now,
            confirmed_status={"health": "ótimo", "pending": 4, "summary": "Novidade inventada", "truth_state": "UNKNOWN"},
        )
        self.assertNotIn("ótimo", html)
        self.assertNotIn("Novidade inventada", html)
        self.assertNotIn("incidente", html.casefold())
        self.assertNotIn("data-confirmed", html)
        confirmed = aion_login_presence_html(
            admin,
            now=now,
            confirmed_status={"truth_state": "CONFIRMED", "source": "sessao", "summary": "Sessão autenticada."},
        )
        self.assertIn("Sessão autenticada.", confirmed)
        self.assertIn('data-confirmed="sessao"', confirmed)
        self.assertIn("O que você gostaria de saber ou fazer?", confirmed)

    def test_greeting_does_not_open_aion_or_write_memory(self):
        source = Path("atlasquant_central_hub_ui.py").read_text(encoding="utf-8")
        render = source[source.index("def render_central_hub"):]
        self.assertNotIn("provider_configured=True", render)
        self.assertNotIn("request_return_to_aion", render)
        self.assertNotIn("save_checkpoint", source)
        self.assertNotIn("openai", source)
        panel = Path("atlasquant_access_panel.py").read_text(encoding="utf-8")
        self.assertIn("clear_login_greeting", panel)


class AionHomeViewerTests(unittest.TestCase):
    def _article(self, html, module_id):
        marker = f'data-module="{module_id}"'
        start = html.index(marker)
        end = html.find('data-module="', start + len(marker))
        return html[start:] if end < 0 else html[start:end]

    def test_zero_claims_keep_every_module_unknown(self):
        html = aion_home_html()
        self.assertEqual(html.count('class="aq-aion-module"'), 9)
        self.assertEqual(html.count('data-truth="CONFIRMED"'), 0)
        self.assertGreaterEqual(html.count('data-truth="UNKNOWN"'), 9)
        self.assertNotIn("CONFIRMADO", html)
        wrapped = aion_home_claims({"truth_state": "CONFIRMED", "source_build": "abc"})
        self.assertTrue(all(item["truth_state"] == "UNKNOWN" for item in wrapped.values()))

    def test_only_a_complete_claim_is_confirmed(self):
        html = aion_home_html(claims={
            "observabilidade": {
                "truth_state": "CONFIRMED",
                "source": "source_mesh",
                "summary": "Uma observação já confirmada nesta execução.",
            }
        })
        self.assertEqual(html.count('data-truth="CONFIRMED"'), 1)
        card = self._article(html, "observabilidade")
        self.assertIn("CONFIRMADO", card)
        self.assertIn("Uma observação já confirmada nesta execução.", card)
        self.assertIn("Fonte: source_mesh", card)
        admin = self._article(html, "administracao")
        self.assertIn('data-truth="UNKNOWN"', admin)
        self.assertIn("EM CONSTRUÇÃO", admin)
        self.assertNotIn("CONFIRMADO", admin)

    def test_incomplete_claims_stay_unknown(self):
        cases = (
            {"truth_state": "READY", "source": "mesh", "summary": "texto"},
            {"truth_state": "CONFIRMED", "summary": "texto"},
            {"truth_state": "CONFIRMED", "source": "mesh"},
            {"truth_state": "CONFIRMED", "source": " ", "summary": " "},
            "disponível",
        )
        for raw in cases:
            with self.subTest(raw=raw):
                html = aion_home_html(claims={"memoria": raw})
                card = self._article(html, "memoria")
                self.assertIn('data-truth="UNKNOWN"', card)
                self.assertNotIn("CONFIRMADO", card)
                self.assertNotIn("Fonte:", card)

    def test_non_admin_gets_no_private_home_or_jump(self):
        user = _access("USER", session={"username": "cliente", "role": "USER"})
        self.assertEqual(aion_home_viewer_html(user, {"truth_state": "CONFIRMED"}), "")
        surface = central_surface_html(user, "aion")
        self.assertNotIn("AION IA", surface)
        self.assertNotIn("module=", surface)
        state = {}
        self.assertEqual(consume_aion_module_jump(state, user, "administracao"), "")
        self.assertEqual(state, {})

    def test_unknown_module_does_not_jump_and_research_and_voice_have_no_link(self):
        admin = _access("ADMIN")
        state = {}
        self.assertEqual(consume_aion_module_jump(state, admin, "mesa secreta"), "")
        self.assertEqual(consume_aion_module_jump(state, admin, "pesquisa"), "")
        self.assertEqual(consume_aion_module_jump(state, admin, "voz"), "")
        self.assertNotIn(AION_MODULE_JUMP_KEY, state)
        self.assertNotIn("aion_admin_workspace", state)
        html = aion_home_html()
        for module_id in ("pesquisa", "voz"):
            article = self._article(html, module_id)
            self.assertNotIn("href=", article)
            self.assertNotIn("Abrir", article)

    def test_linked_modules_jump_only_through_the_existing_key(self):
        admin = _access("ADMIN")
        expected = {
            "administracao": "🧠 Central",
            "memoria": "🧠 Central",
            "desenvolvedor": "🛠️ Desenvolvimento",
            "conteudo": "🎬 Studio",
            "automacao": "🧠 Central",
            "seguranca": "🧠 Central",
            "observabilidade": "🧠 Central",
        }
        html = aion_home_html()
        for module_id, workspace in expected.items():
            with self.subTest(module_id=module_id):
                state = {}
                self.assertEqual(consume_aion_module_jump(state, admin, module_id), workspace)
                self.assertEqual(state[AION_MODULE_JUMP_KEY], workspace)
                self.assertNotIn("aion_admin_workspace", state)
                article = self._article(html, module_id)
                self.assertNotIn("href=", article)
                self.assertNotIn(f"module={module_id}", article)
                self.assertIn("Abrir pelo controle de módulo abaixo.", article)

        source = Path("atlasquant_central_hub_ui.py").read_text(encoding="utf-8")
        self.assertIn("aq_aion_module_stateful_", source)
        self.assertIn("consume_aion_module_jump(st.session_state, access, spec[\"id\"])", source)

    def test_same_execution_context_feeds_the_home_without_a_second_fetch(self):
        observation = {
            "truth_state": "CONFIRMED",
            "source": "FRED",
            "detail": "Última observação já presente no mesh.",
            "claim": "macro:juros",
        }
        context = {
            "truth_state": "CONFIRMED",
            "source_build": "bundle",
            "source_observations": [observation],
            "publication_truth": {"truth_state": "CONFIRMED", "schema": "PUB", "next_action": "Revisar."},
        }
        claims = aion_home_claims(context)
        self.assertEqual(claims["observabilidade"]["truth_state"], "CONFIRMED")
        self.assertEqual(claims["observabilidade"]["source"], "FRED")
        self.assertEqual(claims["administracao"]["truth_state"], "UNKNOWN")
        self.assertEqual(claims["memoria"]["truth_state"], "UNKNOWN")
        html = aion_home_viewer_html(_access("ADMIN"), context)
        self.assertEqual(html.count('data-truth="CONFIRMED"'), 1)
        cloud = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertEqual(cloud.count("= _build_aion_source_runtime_context()"), 1)
        built = cloud.index("= _build_aion_source_runtime_context()")
        assigned = cloud.index("_aion_system_context = {")
        home = cloud.index("render_aion_home_viewer(_ATLASQUANT_ACCESS, _aion_system_context)")
        console = cloud.index("system_context=_aion_system_context,")
        self.assertLess(built, assigned)
        self.assertLess(assigned, home)
        self.assertLess(home, console)
        self.assertIn("defer_aion_home=(active_index == 21)", cloud)
        viewer = Path("atlasquant_central_hub_ui.py").read_text(encoding="utf-8")
        body = viewer[viewer.index("def render_aion_home_viewer"):viewer.index("def render_central_hub")]
        for banned in ("requests", "_github_get", "save_checkpoint", "openai", "subprocess", "urlopen"):
            self.assertNotIn(banned, body)
        self.assertNotIn("aion_admin_workspace\"]", viewer[viewer.index("def consume_aion_module_jump"):viewer.index("def central_selector_html")])


    def test_central_controls_are_explicit_and_master_panel_stays_visible(self):
        hub = Path("atlasquant_central_hub_ui.py").read_text(encoding="utf-8")
        self.assertIn("#### Acessos da Central", hub)
        self.assertIn('"Abrir " + label', hub)
        self.assertIn('key=f"aq_central_stateful_{area_id}"', hub)

        admin = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("def _render_master_status_summary", admin)
        self.assertIn("Painel Mestre · resumo essencial", admin)
        self.assertIn("_render_master_status_summary(status_board)", admin)
        self.assertIn("aion_workspace_overview_open_", admin)
        self.assertIn('st.session_state[_AION_WORKSPACE_JUMP_KEY] = workspace', admin)
        self.assertIn('"Abrir " + workspace', admin)

        cloud = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn("_CENTRAL_RENDER_ERROR_KEY", cloud)
        self.assertIn("A Central Principal encontrou um erro isolado de interface", cloud)
        self.assertIn("Abrir Trader seguro", cloud)
        self.assertIn("Abrir AION seguro", cloud)
        self.assertIn("st.session_state[_CENTRAL_RENDER_ERROR_KEY]", cloud)


if __name__ == "__main__":
    unittest.main()
