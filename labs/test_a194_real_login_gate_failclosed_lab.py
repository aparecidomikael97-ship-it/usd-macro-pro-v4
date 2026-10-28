"""A194 LAB: regressions on REAL Streamlit login gate and cloud app fallback.

Executes the exact source AST of evaluate_access and of the import-failure
fallback in the real app. Avoids importing or launching the Streamlit app,
making network/provider/billing calls, or touching any live identity data.

This proves only branch behavior with synthetic user registries. It DOES
NOT prove that the registry/session itself is independently authenticated.
"""
import ast
import os
from pathlib import Path
from types import SimpleNamespace
import unittest

from atlasquant_access_control import (
    authenticate,
    has_permission,
    hash_password,
    load_users_config,
    session_is_current,
)

ROOT = Path(__file__).resolve().parents[1]
ACCESS_PATH = ROOT / "atlasquant_access_panel.py"
APP_PATH = ROOT / "usd_macro_pro_v4_cloud.py"
VALID_PASSWORD = "synthetic-for-auth-gate-2026#"
NEW_PASSWORD = "synthetic-revoked-password-2026#"


def _extract_access_function():
    tree = ast.parse(ACCESS_PATH.read_text(encoding="utf-8"))
    matches = [
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "evaluate_access"
    ]
    if len(matches) != 1:
        raise AssertionError("actual evaluate_access missing or ambiguous")
    namespace = {
        "Any": object,
        "has_permission": has_permission,
        "session_is_current": session_is_current,
    }
    exec(compile(ast.Module(body=matches, type_ignores=[]), str(ACCESS_PATH), "exec"), namespace)
    return namespace["evaluate_access"]


def _extract_app_gate_ast():
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    matches = [
        n for n in tree.body
        if isinstance(n, ast.If)
        and isinstance(n.test, ast.Compare)
        and isinstance(n.test.left, ast.Name)
        and n.test.left.id == "render_access_gate"
    ]
    if len(matches) != 1:
        raise AssertionError("live cloud app import-fallback gate missing or ambiguous")
    return compile(ast.Module(body=matches, type_ignores=[]), str(APP_PATH), "exec")


ACCESS = _extract_access_function()
CLOUD_GATE_CODE = _extract_app_gate_ast()


class StopWasCalled(Exception):
    pass


class FakeSecrets:
    def __init__(self, values=None, broken=False):
        self.values = dict(values or {})
        self.broken = broken

    def get(self, name, default=None):
        if self.broken:
            raise RuntimeError("synthetic inaccessible secrets")
        return self.values.get(name, default)


class FakeStreamlit:
    def __init__(self, values=None, broken=False):
        self.secrets = FakeSecrets(values, broken=broken)
        self.errors = []
        self.captions = []
        self.stops = 0

    def error(self, text):
        self.errors.append(str(text))

    def caption(self, text):
        self.captions.append(str(text))

    def stop(self):
        self.stops += 1
        raise StopWasCalled()


def simulate_app_fallback(secrets=None, env=None, *, broken_secrets=False):
    st = FakeStreamlit(secrets, broken=broken_secrets)
    values = dict(env or {})
    fake_os = SimpleNamespace(getenv=lambda key, default="": values.get(key, default))
    namespace = {
        "render_access_gate": None, "st": st, "os": fake_os,
        "_ATLASQUANT_ACCESS_IMPORT_ERROR": "synthetic import failure",
    }
    denied = False
    try:
        exec(CLOUD_GATE_CODE, namespace)
    except StopWasCalled:
        denied = True
    return denied, st, namespace.get("_ATLASQUANT_ACCESS")


class A194RealGateSourceLab(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        old = hash_password(VALID_PASSWORD, salt=b"synthetic-salt001", iterations=200_000)
        new = hash_password(NEW_PASSWORD, salt=b"synthetic-salt002", iterations=200_000)
        cls.users = load_users_config({
            "users": {
                "admin.01": {"role": "ADMIN", "password_hash": old, "active": True},
                "user.01": {"role": "USER", "password_hash": old, "active": True},
            },
        })
        cls.rotated = load_users_config({
            "users": {
                "admin.01": {"role": "ADMIN", "password_hash": new, "active": True},
                "user.01": {"role": "USER", "password_hash": old, "active": True},
            },
        })
        cls.admin = authenticate("admin.01", VALID_PASSWORD, cls.users)
        cls.user = authenticate("user.01", VALID_PASSWORD, cls.users)

    def test_role_only_admin_missing_registry_denied(self):
        out = ACCESS(required=True, users_count=2, session={"role": "ADMIN"})
        self.assertFalse(out["allowed"])
        self.assertNotEqual(out["mode"], "AUTHENTICATED")
        print("A194_ROLE_ONLY_ADMIN_NO_REGISTRY=DENIED", flush=True)

    def test_role_only_user_missing_registry_denied(self):
        out = ACCESS(required=True, users_count=2, session={"role": "USER"})
        self.assertFalse(out["allowed"])

    def test_valid_looking_session_missing_registry_denied(self):
        out = ACCESS(required=True, users_count=2, session=self.admin)
        self.assertFalse(out["allowed"])
        self.assertEqual(out["reason"], "SESSION_REVOKED")

    def test_verified_admin_and_registry_allow_authenticated_mode(self):
        out = ACCESS(required=True, users_count=2, session=self.admin, users=self.users)
        self.assertTrue(out["allowed"])
        self.assertEqual(out["mode"], "AUTHENTICATED")

    def test_verified_user_and_registry_allow_authenticated_mode(self):
        out = ACCESS(required=True, users_count=2, session=self.user, users=self.users)
        self.assertTrue(out["allowed"])

    def test_rotated_secret_revokes_prior_session(self):
        out = ACCESS(required=True, users_count=2, session=self.admin, users=self.rotated)
        self.assertFalse(out["allowed"])
        self.assertEqual(out["reason"], "SESSION_REVOKED")

    def test_registry_current_role_mismatch_denied(self):
        other = dict(self.users)
        other["admin.01"] = self.users["user.01"]
        out = ACCESS(required=True, users_count=2, session=self.admin, users=other)
        self.assertFalse(out["allowed"])

    def test_fake_fingerprint_denied(self):
        out = ACCESS(required=True, users_count=2, session={**self.admin, "credential_fingerprint": "forged"}, users=self.users)
        self.assertFalse(out["allowed"])

    def test_fake_admin_role_on_user_denied(self):
        out = ACCESS(required=True, users_count=2, session={**self.user, "role": "ADMIN"}, users=self.users)
        self.assertFalse(out["allowed"])

    def test_current_session_missing_from_registry_denied(self):
        out = ACCESS(required=True, users_count=2, session=self.admin, users={})
        self.assertFalse(out["allowed"])

    def test_unknown_role_denied(self):
        out = ACCESS(required=True, users_count=2, session={"role": "ROOT"}, users=self.users)
        self.assertFalse(out["allowed"])

    def test_no_session_demands_login(self):
        out = ACCESS(required=True, users_count=2, session=None, users=self.users)
        self.assertEqual(out["mode"], "LOGIN")
        self.assertFalse(out["allowed"])

    def test_no_configured_users_locked_even_with_forged_admin(self):
        out = ACCESS(required=True, users_count=0, session={"role": "ADMIN"}, users={})
        self.assertFalse(out["allowed"])

    def test_explicit_bootstrap_preview_never_authenticates(self):
        out = ACCESS(required=True, users_count=0, session=None, users={}, allow_unconfigured_preview=True)
        self.assertEqual(out["mode"], "PREVIEW")
        self.assertNotEqual(out["mode"], "AUTHENTICATED")

    def test_open_mode_is_open_not_authenticated(self):
        out = ACCESS(required=False, users_count=0, session={"role": "ADMIN"}, users=None)
        self.assertEqual(out["mode"], "OPEN")

    def test_production_env_os_fails_closed_without_gate_import(self):
        denied, st, access = simulate_app_fallback(env={"ATLASQUANT_ENV": "PRODUCTION", "ATLASQUANT_AUTH_REQUIRED": "false"})
        self.assertTrue(denied)
        self.assertEqual(st.stops, 1)
        self.assertIsNone(access)
        print("A194_LOGIN_MODULE_IMPORT_FAILURE_PRODUCTION=STOPPED", flush=True)

    def test_production_env_secrets_fails_closed_without_gate_import(self):
        denied, _, access = simulate_app_fallback(secrets={"ATLASQUANT_ENV": "PRODUCTION", "ATLASQUANT_AUTH_REQUIRED": "false"})
        self.assertTrue(denied)
        self.assertIsNone(access)

    def test_production_os_env_cannot_be_downgraded_by_secrets_dev(self):
        denied, _, access = simulate_app_fallback(secrets={"ATLASQUANT_ENV": "LOCAL"}, env={"ATLASQUANT_ENV": "PRODUCTION"})
        self.assertTrue(denied)
        self.assertIsNone(access)

    def test_secrets_exception_production_still_fails_closed(self):
        denied, _, access = simulate_app_fallback(env={"ATLASQUANT_ENV": "PRODUCTION"}, broken_secrets=True)
        self.assertTrue(denied)
        self.assertIsNone(access)

    def test_case_insensitive_production_blocks(self):
        denied, _, access = simulate_app_fallback(secrets={"ATLASQUANT_ENV": "production"})
        self.assertTrue(denied)
        self.assertIsNone(access)

    def test_auth_required_true_still_fails_closed(self):
        denied, _, access = simulate_app_fallback(env={"ATLASQUANT_ENV": "LOCAL", "ATLASQUANT_AUTH_REQUIRED": "true"})
        self.assertTrue(denied)
        self.assertIsNone(access)

    def test_non_production_no_auth_required_preserves_open_preview(self):
        denied, st, access = simulate_app_fallback(env={"ATLASQUANT_ENV": "LOCAL", "ATLASQUANT_AUTH_REQUIRED": "false"})
        self.assertFalse(denied)
        self.assertEqual(st.stops, 0)
        self.assertEqual(access, {"allowed": True, "mode": "OPEN", "role": "OPEN"})
        self.assertNotEqual(access["mode"], "AUTHENTICATED")

    def test_blank_env_no_auth_required_keeps_local_open(self):
        denied, _, access = simulate_app_fallback()
        self.assertFalse(denied)
        self.assertEqual(access["mode"], "OPEN")

    def test_app_source_login_precedes_chat_host_calls(self):
        src = APP_PATH.read_text(encoding="utf-8")
        self.assertLess(src.index("render_access_gate()"), src.index("build_streamlit_production_binding("))
        self.assertLess(src.index("render_access_gate()"), src.index("build_streamlit_staged_binding("))

    def test_host_requires_upstream_auth_not_independent_trust(self):
        # Do NOT claim that the existence of 'authenticated' in a dict
        # proves origin/authentication of the HTTP or Streamlit session.
        src = (ROOT / "atlasquant_aion_chat_product_bridge.py").read_text(encoding="utf-8")
        self.assertIn("already authenticated AtlasQuant access decision", src)
        self.assertIn('\"authenticated\": not blockers', src)
        print("A194_HOST_TRUST_ROOT=NOT_INDEPENDENTLY_VERIFIED_RED", flush=True)


if __name__ == "__main__":
    unittest.main()
