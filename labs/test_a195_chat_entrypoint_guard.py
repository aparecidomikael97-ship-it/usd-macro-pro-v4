"""A195: REAL session registry guard and exact Streamlit wrapper AST test.

No real streamlit invocation, production DB, network, credentials or effects.
Synthetic AccessUser registry is used; imports the real login/auth primitives.
"""
import ast
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from atlasquant_access_control import (
    AccessUser, authenticate, hash_password, load_users_config,
)
from atlasquant_aion_chat_entrypoint_guard import (
    REGISTRY_KEY, SESSION_KEY, MAX_AGE_SECONDS, MAX_IDLE_SECONDS,
    require_chat_host_session,
)

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "synthetic-admin-password-2026#"
OTHER_PASSWORD = "synthetic-other-password-2026#"


class FakeST:
    def __init__(self, *, registry=None, session=None, config=None, secret_broken=False):
        self.secrets = FakeSecrets({REGISTRY_KEY: registry} if registry is not None else {}, secret_broken)
        self.session_state = {SESSION_KEY: session} if session is not None else {}
        self.config = dict(config or {})


class FakeSecrets:
    def __init__(self, vals, broken=False):
        self.vals = vals
        self.broken = broken

    def get(self, name, default=None):
        if self.broken:
            raise RuntimeError("LAB simulated unavailable secrets")
        return self.vals.get(name, default)


def compile_host_wrapper(path, name, *, production):
    """Compile only the real function's AST, inject mocked storage builder."""
    parsed = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    funcs = [n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(funcs) != 1:
        raise AssertionError("missing or duplicated production source wrapper " + name)
    # bind the actual guard; only the DB constructor below is substituted.
    def construction(*args, **kwargs):
        return {
            "state": "SYNTHETIC_CONSTRUCTOR_CALLED",
            "access_passed": args[0] if args else None,
            "environment": kwargs.get("environment"),
        }

    ns = {
        "Any": object,
        "Mapping": dict,
        "require_chat_host_session": require_chat_host_session,
        "production_feature_enabled": lambda c: c.get("enabled") is True,
        "staged_feature_enabled": lambda c: c.get("enabled") is True,
        "streamlit_production_config": lambda st: st.config,
        "streamlit_staged_config": lambda st: st.config,
        "build_production_host_binding": construction,
        "build_staged_host_binding": construction,
    }
    exec(compile(ast.Module(body=funcs, type_ignores=[]), path, "exec"), ns)
    return ns[name]


class A195ChatHostEntrypointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.owner_hash = hash_password(PASSWORD, salt=b"a195-owner-salt00", iterations=200_000)
        cls.other_hash = hash_password(OTHER_PASSWORD, salt=b"a195-other-salt00", iterations=200_000)
        cls.registry = {"users": {
            "owner.01": {"role": "ADMIN", "password_hash": cls.owner_hash, "active": True},
            "user.01": {"role": "USER", "password_hash": cls.other_hash, "active": True},
        }}
        cls.users = load_users_config(cls.registry)
        cls.production_wrapper = compile_host_wrapper(
            "atlasquant_aion_chat_render_production_host_v1.py",
            "build_streamlit_production_binding",
            production=True,
        )
        cls.staging_wrapper = compile_host_wrapper(
            "atlasquant_aion_chat_host_staging.py",
            "build_streamlit_staged_binding",
            production=False,
        )

    def setUp(self):
        self.now = time.time()
        self.session = authenticate("owner.01", PASSWORD, self.users)
        self.session["authenticated_at"] = self.now - 100
        self.session["last_seen"] = self.now - 5
        self.st = FakeST(registry=self.registry, session=self.session, config={"enabled": True})
        self.access = {
            "allowed": True, "mode": "AUTHENTICATED", "role": "ADMIN",
            "session": dict(self.session),
        }

    def deny(self, expected, *, access=None, st=None, now=None):
        with self.assertRaisesRegex(PermissionError, expected):
            require_chat_host_session(
                st if st is not None else self.st,
                self.access if access is None else access,
                now=self.now if now is None else now,
            )

    def test_valid_admin_server_session_passes_recheck(self):
        self.assertTrue(require_chat_host_session(self.st, self.access, now=self.now))

    def test_missing_access_rejected(self):
        with self.assertRaisesRegex(PermissionError, "ACCESS_MAPPING_REQUIRED"):
            require_chat_host_session(self.st, None, now=self.now)

    def test_claimed_admin_but_open_mode_denied(self):
        self.deny("AUTHENTICATED_ACCESS_REQUIRED", access={**self.access, "mode": "OPEN"})

    def test_preview_mode_denied(self):
        self.deny("AUTHENTICATED_ACCESS_REQUIRED", access={**self.access, "mode": "PREVIEW"})

    def test_flagged_access_not_allowed_denied(self):
        self.deny("AUTHENTICATED_ACCESS_REQUIRED", access={**self.access, "allowed": False})

    def test_missing_server_session_denied(self):
        self.st.session_state.pop(SESSION_KEY)
        self.deny("SERVER_SESSION_REQUIRED")

    def test_missing_user_registry_denied(self):
        self.st.secrets.vals.clear()
        with patch.dict("os.environ", {REGISTRY_KEY: ""}):
            self.deny("CURRENT_USER_REGISTRY_MISMATCH")

    def test_unavailable_registry_denied(self):
        self.st.secrets.broken = True
        with patch.dict("os.environ", {REGISTRY_KEY: ""}):
            self.deny("CURRENT_USER_REGISTRY_MISMATCH")

    def test_stale_password_rejected_after_change(self):
        newer = {"users": dict(self.registry["users"])}
        newer["users"]["owner.01"] = {
            "role": "ADMIN", "password_hash": self.other_hash, "active": True,
        }
        self.st.secrets.vals[REGISTRY_KEY] = newer
        self.deny("CURRENT_USER_REGISTRY_MISMATCH")

    def test_disabled_user_denied(self):
        newer = {"users": dict(self.registry["users"])}
        newer["users"]["owner.01"] = {
            "role": "ADMIN", "password_hash": self.owner_hash, "active": False,
        }
        self.st.secrets.vals[REGISTRY_KEY] = newer
        self.deny("CURRENT_USER_REGISTRY_MISMATCH")

    def test_user_role_downgrade_denied(self):
        newer = {"users": dict(self.registry["users"])}
        newer["users"]["owner.01"] = {
            "role": "USER", "password_hash": self.owner_hash, "active": True,
        }
        self.st.secrets.vals[REGISTRY_KEY] = newer
        self.deny("CURRENT_USER_REGISTRY_MISMATCH")

    def test_other_user_in_access_mapping_denied(self):
        impersonated = dict(self.access)
        impersonated["session"] = {
            **self.session, "username": "user.01",
        }
        self.deny("SESSION_BINDING_MISMATCH", access=impersonated)

    def test_altered_credential_fingerprint_denied(self):
        altered = dict(self.access)
        altered["session"] = {**self.session, "credential_fingerprint": "fake"}
        self.deny("SESSION_BINDING_MISMATCH", access=altered)

    def test_access_session_missing_denied(self):
        self.deny("BOUND_ACCESS_SESSION_REQUIRED", access={**self.access, "session": None})

    def test_admin_role_only_untrusted_denied(self):
        self.deny("CURRENT_USER_REGISTRY_MISMATCH",
                  access=self.access,
                  st=FakeST(registry=self.registry, session={"role": "ADMIN", "username": "owner.01"}))

    def test_non_admin_access_claim_denied(self):
        self.deny("OWNER_ADMIN_REQUIRED", access={**self.access, "role": "USER"})

    def test_role_only_helper_does_not_authorize_chat(self):
        self.deny("SESSION_BINDING_MISMATCH",
                  access={**self.access, "session": {**self.session, "role": "USER"}})

    def test_permissions_changed_in_server_session_denied(self):
        bad = dict(self.session)
        bad["permissions"] = ["app:read"]
        self.st.session_state[SESSION_KEY] = bad
        self.access["session"] = dict(bad)
        self.deny("ROLE_PERMISSIONS_NOT_SERVER_CANONICAL")

    def test_permissions_injection_denied_without_type_error(self):
        bad = dict(self.session)
        bad["permissions"] = [{"role": "ADMIN"}]
        self.st.session_state[SESSION_KEY] = bad
        self.access["session"] = dict(bad)
        self.deny("SESSION_PERMISSIONS_REQUIRED")

    def test_missing_permissions_denied(self):
        bad = dict(self.session)
        bad.pop("permissions")
        self.st.session_state[SESSION_KEY] = bad
        self.access["session"] = dict(bad)
        self.deny("SESSION_PERMISSIONS_REQUIRED")

    def test_expired_max_age_denied(self):
        self.session["authenticated_at"] = self.now - MAX_AGE_SECONDS - 10
        self.access["session"] = dict(self.session)
        self.deny("SESSION_MAX_AGE")

    def test_expired_idle_denied(self):
        self.session["authenticated_at"] = self.now - MAX_IDLE_SECONDS - 1000
        self.session["last_seen"] = self.now - MAX_IDLE_SECONDS - 10
        self.access["session"] = dict(self.session)
        self.deny("SESSION_IDLE_TIMEOUT")

    def test_invalid_timestamp_nan_denied(self):
        self.session["last_seen"] = float("nan")
        self.access["session"] = dict(self.session)
        # nan != nan; identity mismatch also rejects. No trust expansion.
        with self.assertRaises(PermissionError):
            require_chat_host_session(self.st, self.access, now=self.now)

    def test_invalid_future_timestamp_denied(self):
        self.session["last_seen"] = self.now + 100
        self.access["session"] = dict(self.session)
        self.deny("INVALID_SESSION_TIME")

    def test_invalid_timestamp_type_denied(self):
        self.session["authenticated_at"] = "invalid"
        self.access["session"] = dict(self.session)
        self.deny("INVALID_SESSION_TIME")

    def test_explicit_feature_disabled_staging_has_no_store(self):
        self.st.config["enabled"] = False
        self.assertIsNone(self.staging_wrapper(self.st, self.access, environment="STAGING"))

    def test_explicit_feature_disabled_production_has_no_store(self):
        self.st.config["enabled"] = False
        self.assertIsNone(self.production_wrapper(self.st, self.access, environment="PRODUCTION"))

    def test_staging_wrapper_denies_forged_access_before_store(self):
        with self.assertRaises(PermissionError):
            self.staging_wrapper(self.st, {**self.access, "session": {"role": "ADMIN"}}, environment="STAGING")

    def test_production_wrapper_denies_forged_access_before_store(self):
        with self.assertRaises(PermissionError):
            self.production_wrapper(self.st, {**self.access, "session": {"role": "ADMIN"}}, environment="PRODUCTION")

    def test_staging_wrapper_guard_then_mock_store(self):
        out = self.staging_wrapper(self.st, self.access, environment="STAGING")
        self.assertEqual(out["state"], "SYNTHETIC_CONSTRUCTOR_CALLED")
        self.assertEqual(out["environment"], "STAGING")

    def test_production_wrapper_guard_then_mock_store(self):
        out = self.production_wrapper(self.st, self.access, environment="PRODUCTION")
        self.assertEqual(out["state"], "SYNTHETIC_CONSTRUCTOR_CALLED")
        self.assertEqual(out["environment"], "PRODUCTION")

    def test_host_settings_self_managed_red_remains(self):
        # A user able to rewrite both the server's configured users and
        # st.session_state could impersonate others; no external root here.
        forged = authenticate("owner.01", PASSWORD, self.users)
        self.assertIsNotNone(forged)
        print("A195_SERVER_REGISTRY_AND_SESSION_HOST_TRUST=NOT_EXTERNAL_ROOT_RED", flush=True)

    def test_host_source_does_not_make_guard_an_independent_signature(self):
        for path in (
            "atlasquant_aion_chat_render_production_host_v1.py",
            "atlasquant_aion_chat_host_staging.py",
        ):
            source = (ROOT / path).read_text(encoding="utf-8")
            self.assertIn("require_chat_host_session(st, access)", source)
        print("A195_ENTRYPOINT_GUARD=NOT_P0_AUTHENTICATION_HOMOLOGATION_RED", flush=True)


if __name__ == "__main__":
    unittest.main()
