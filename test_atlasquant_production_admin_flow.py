"""Run the Render entrypoint as PRODUCTION with an authenticated session.

Network is offline, the home snapshot is a fresh fixture served as if read from
atlasquant-runtime, and the background refresh is recorded instead of started.
"""
import json
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import requests
import streamlit as st
from streamlit.testing.v1 import AppTest

from atlasquant_access_control import authenticate, hash_password, load_users_config
from test_atlasquant_fast_startup import snapshot

_SALT_ADMIN = bytes(range(16))
_SALT_USER = bytes(range(16, 32))
_ADMIN_PASSWORD = "local-test-only-admin-pass"
_USER_PASSWORD = "local-test-only-user-pass"
_USERS_JSON = json.dumps({"users": {
    "aparecidomikael": {"role": "ADMIN", "password_hash": hash_password(_ADMIN_PASSWORD, salt=_SALT_ADMIN, iterations=200_000)},
    "cliente.teste": {"role": "USER", "password_hash": hash_password(_USER_PASSWORD, salt=_SALT_USER, iterations=200_000)},
}})


class _Offline:
    status_code = 503
    ok = False
    content = b""
    text = "offline"
    headers = {}

    def json(self):
        return {}

    def raise_for_status(self):
        raise requests.HTTPError("offline")


def _session(username, password):
    session = authenticate(username, password, load_users_config(_USERS_JSON))
    now = time.time()
    session["authenticated_at"] = now
    session["last_seen"] = now
    return session


def _aion_stub(access, **_kwargs):
    st.markdown("AION_CONSOLE_RENDERED")
    return {"allowed": True}


class ProductionAdminFlowTests(unittest.TestCase):
    def setUp(self):
        from atlasquant_advanced_boot import reset_live_refresh_for_tests
        reset_live_refresh_for_tests()
        self.snapshot_calls = []
        self.refresh_calls = []
        fresh = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        self.fixture = snapshot(generated_at=fresh)

        def fake_snapshot(repo, branch="atlasquant-runtime", token="", timeout=4.0):
            self.snapshot_calls.append(branch)
            return json.loads(json.dumps(self.fixture))

        def fake_refresh(loaders, **kwargs):
            self.refresh_calls.append((sorted(loaders), dict(kwargs)))
            return "running"

        def forbidden(url, *args, **kwargs):
            raise AssertionError(f"remote write during UI test: {url}")

        self.patches = [
            patch("atlasquant_fast_startup.load_home_snapshot", side_effect=fake_snapshot),
            patch("atlasquant_advanced_boot.start_live_refresh", side_effect=fake_refresh),
            patch("atlasquant_aion_admin.render_aion_admin_console", side_effect=_aion_stub),
            patch("requests.get", side_effect=lambda *a, **k: _Offline()),
            patch("requests.post", side_effect=forbidden),
            patch("requests.put", side_effect=forbidden),
            patch("requests.patch", side_effect=forbidden),
            patch("requests.delete", side_effect=forbidden),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        from atlasquant_advanced_boot import reset_live_refresh_for_tests
        reset_live_refresh_for_tests()

    def _app(self, username, password):
        at = AppTest.from_file("usd_macro_pro_v4_cloud.py", default_timeout=180)
        for key in ("CHAVE_FRED", "CHAVE_TWELVE_DATA", "CHAVE_NEWSAPI", "CHAVE_EODHD", "GITHUB_TOKEN_HISTORICO"):
            at.secrets[key] = ""
        at.secrets["ATLASQUANT_ENV"] = "PRODUCTION"
        at.secrets["ATLASQUANT_USERS_JSON"] = _USERS_JSON
        at.secrets["GITHUB_REPO_HISTORICO"] = "aparecidomikael97-ship-it/usd-macro-pro-v4"
        at.secrets["GITHUB_DATA_BRANCH"] = "main"
        at.secrets["GITHUB_BRANCH_HISTORICO"] = "main"
        at.session_state["atlasquant_access_session"] = _session(username, password)
        return at

    @staticmethod
    def _html(at):
        return " ".join(str(item.value) for item in at.markdown)

    def _assert_clean(self, at):
        errors = [str(getattr(exc, "value", exc)) for exc in at.exception]
        self.assertEqual(errors, [])

    def test_admin_sees_identity_premium_home_and_opens_aion_from_the_top(self):
        at = self._app("aparecidomikael", _ADMIN_PASSWORD)
        at.run(timeout=180)
        self._assert_clean(at)
        html = self._html(at)
        self.assertIn('id="aq-account-identity"', html)
        self.assertIn('data-role="ADMIN"', html)
        self.assertIn("aparecidomikael · ADMIN", html)
        self.assertIn("aq-premium-hero", html)
        self.assertIn("Central do ecossistema", html)
        self.assertEqual(self.snapshot_calls[0], "atlasquant-runtime")
        self.assertEqual(at.session_state["atlasquant_fast_boot_observability"]["mode"], "Iniciante")
        dock = at.button(key="aq_voice_dock_aion")
        self.assertEqual(dock.label, "Abrir central AION")

        dock.click().run(timeout=180)
        self._assert_clean(at)
        self.assertEqual(at.session_state["atlasquant_experience_mode"], "Avançado")
        self.assertEqual(at.session_state["atlasquant_advanced_area"], "🧠 AION")
        self.assertIn("AION_CONSOLE_RENDERED", self._html(at))
        self.assertIn("aparecidomikael · ADMIN", self._html(at))
        nav = at.selectbox(key="atlasquant_advanced_area")
        self.assertIn("🧠 AION", nav.options)
        self.assertEqual(nav.value, "🧠 AION")

    def test_admin_advanced_click_paints_from_the_runtime_snapshot(self):
        at = self._app("aparecidomikael", _ADMIN_PASSWORD)
        at.run(timeout=180)
        self._assert_clean(at)
        radio = at.radio(key="atlasquant_experience_mode")
        started = time.perf_counter()
        radio.set_value("Avançado").run(timeout=180)
        elapsed = time.perf_counter() - started
        self._assert_clean(at)
        boot = at.session_state["atlasquant_advanced_boot"]
        self.assertEqual(boot["state"], "CACHED_SNAPSHOT")
        self.assertFalse(boot["real_orders_enabled"])
        self.assertFalse(boot["automatic_execution"])
        self.assertEqual(self.refresh_calls[0][0], ["dados_moedas", "fed", "macro_eua"])
        self.assertEqual(self.refresh_calls[0][1]["timeouts"]["dados_moedas"], 50.0)
        self.assertTrue(all(branch == "atlasquant-runtime" for branch in self.snapshot_calls))
        html = self._html(at)
        self.assertIn("Leitura em cache", html)
        self.assertIn("não trata o cache como coleta ao vivo", html)
        self.assertIn("aparecidomikael · ADMIN", html)
        self.assertIn("🧠 AION", at.selectbox(key="atlasquant_advanced_area").options)
        self.assertEqual(at.button(key="aq_voice_dock_aion").label, "Abrir central AION")
        # The whole Advanced script, including the Radar workspace, runs offline here.
        self.assertLess(elapsed, 60)
        print(f"\n[advanced-click] AppTest full rerun {elapsed:.2f}s, cache state {boot['state']}")

    def test_stale_runtime_snapshot_keeps_the_live_path(self):
        self.fixture = snapshot(generated_at=(datetime.now(timezone.utc) - timedelta(minutes=120)).isoformat())
        at = self._app("aparecidomikael", _ADMIN_PASSWORD)
        at.session_state["atlasquant_experience_mode"] = "Avançado"
        at.run(timeout=180)
        self._assert_clean(at)
        boot = at.session_state["atlasquant_advanced_boot"]
        self.assertNotEqual(boot["state"], "CACHED_SNAPSHOT")
        self.assertEqual(self.refresh_calls, [])
        self.assertNotIn("Leitura em cache", self._html(at))

    def test_regular_user_gets_no_admin_identity_or_aion(self):
        at = self._app("cliente.teste", _USER_PASSWORD)
        at.session_state["atlasquant_experience_mode"] = "Avançado"
        at.run(timeout=180)
        self._assert_clean(at)
        html = self._html(at)
        self.assertIn("cliente.teste · USER", html)
        self.assertIn('data-role="USER"', html)
        self.assertNotIn("· ADMIN", html)
        self.assertNotIn("AION liberado", html)
        self.assertNotIn("AION_CONSOLE_RENDERED", html)
        self.assertNotIn("🧠 AION", at.selectbox(key="atlasquant_advanced_area").options)
        self.assertEqual([b for b in at.button if b.key == "aq_voice_dock_aion"], [])

    def test_render_entrypoint_is_the_app_that_carries_the_premium_flow(self):
        blueprint = Path("render.yaml").read_text(encoding="utf-8")
        self.assertIn("streamlit run usd_macro_pro_v4_cloud.py", blueprint)
        app = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn("from atlasquant_premium_shell import", app)
        self.assertIn("render_premium_catalog(", app)
        self.assertIn("render_account_identity(_ATLASQUANT_ACCESS)", app)
        self.assertIn("render_top_voice_access(st.session_state, pages=_nav_items", app)


class AccountIdentityRulesTests(unittest.TestCase):
    def _access(self, role, *, session_role=None, mode="AUTHENTICATED", username="aparecidomikael"):
        return {
            "mode": mode,
            "role": role,
            "session": {"username": username, "role": session_role or role},
        }

    def test_admin_label_comes_only_from_a_matching_authenticated_session(self):
        from atlasquant_ui_v1 import account_identity, account_identity_html
        ident = account_identity(self._access("ADMIN"))
        self.assertTrue(ident["is_admin"])
        self.assertEqual(ident["label"], "aparecidomikael · ADMIN")
        html = account_identity_html(self._access("ADMIN"))
        self.assertIn('data-role="ADMIN"', html)
        self.assertIn("#1a1408", html)
        self.assertNotIn("Iniciante", html)
        self.assertNotIn("Avançado", html)

    def test_common_profiles_never_inherit_admin(self):
        from atlasquant_ui_v1 import account_identity, account_identity_html
        for role in ("USER", "SALES"):
            with self.subTest(role=role):
                html = account_identity_html(self._access(role, username="cliente.teste"))
                self.assertIn(f"cliente.teste · {role}", html)
                self.assertNotIn("ADMIN", html)
                self.assertNotIn("AION", html)
                self.assertFalse(account_identity(self._access(role))["is_admin"])
        self.assertFalse(account_identity(self._access("ADMIN", session_role="USER"))["visible"])
        self.assertFalse(account_identity(self._access("USER", session_role="ADMIN"))["visible"])
        for mode in ("OPEN", "PREVIEW", "LOGIN"):
            self.assertEqual(account_identity_html(self._access("ADMIN", mode=mode)), "")
        self.assertEqual(account_identity_html({"mode": "AUTHENTICATED", "role": "ADMIN"}), "")
        self.assertEqual(account_identity_html(None), "")

    def test_escaped_username_cannot_inject_markup(self):
        from atlasquant_ui_v1 import account_identity_html
        html = account_identity_html(self._access("USER", username="<b>x</b>"))
        self.assertNotIn("<b>x</b>", html)

    def test_aion_shortcuts_use_the_admin_bridge_and_fast_shell_adds_them_only_for_admin(self):
        voice = Path("atlasquant_voice_assistant.py").read_text(encoding="utf-8")
        dock = voice[voice.index("def render_top_voice_access"):]
        self.assertIn("request_return_to_aion(session_state)", dock)
        premium = Path("atlasquant_premium_shell.py").read_text(encoding="utf-8")
        self.assertIn('if target == "🧠 AION":', premium)
        self.assertIn("request_return_to_aion(st.session_state)", premium)
        fast = Path("atlasquant_fast_startup.py").read_text(encoding="utf-8")
        self.assertIn('if str(dict(access or {}).get("role") or "").upper()=="ADMIN":', fast)
        self.assertIn('_dock_pages.append("🧠 AION")', fast)
        self.assertIn("render_top_voice_access(st.session_state, pages=_dock_pages, fast=True)", fast)
        self.assertIn("render_account_identity(", fast)
        from atlasquant_navigation_bridge import consume_navigation_request, request_return_to_aion
        state = {}
        request_return_to_aion(state)
        self.assertIsNone(consume_navigation_request(state, available_pages=["🎯 Radar"]))
        self.assertNotIn("atlasquant_advanced_area", state)

    def test_dark_canvas_is_the_only_theme_so_light_text_stays_readable(self):
        from atlasquant_ui_v1 import ATLASQUANT_CSS
        from experience_v103 import THEME_CHOICES, experience_theme_summary
        self.assertEqual(THEME_CHOICES, ("Escuro", "Alto contraste"))
        self.assertEqual(experience_theme_summary("Claro", "Normal", False)["theme"], "Escuro")
        self.assertIn('.stApp [data-testid="stExpander"] details > summary {\n  background: #102338 !important;', ATLASQUANT_CSS)
        self.assertIn("background: #1d4e89 !important;", ATLASQUANT_CSS)


if __name__ == "__main__":
    unittest.main()
