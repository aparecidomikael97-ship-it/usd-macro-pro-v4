"""A199: contradictory ENV vs Streamlit secrets MUST NOT downgrade auth.

Runs AST-extracted ACTUAL access_required/_setting/_bool_setting functions and
the actual main-app login-import fallback, with fully synthetic Streamlit and
environment values. No live app, users, provider, network, Worker or deploy.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "atlasquant_access_panel.py"
APP = ROOT / "usd_macro_pro_v4_cloud.py"
TRUTHY = ("1", "true", "yes", "on", "sim")


class SimulatedStop(Exception):
    pass


class Secrets:
    def __init__(self, values=None, broken=False):
        self.values = dict(values or {})
        self.broken = broken

    def get(self, key, default=None):
        if self.broken:
            raise RuntimeError("synthetic inaccessible Streamlit secrets")
        return self.values.get(key, default)


class StreamlitStub:
    def __init__(self, secrets=None, broken=False):
        self.secrets = Secrets(secrets, broken)
        self.errors = []
        self.captions = []
        self.stops = 0

    def error(self, value):
        self.errors.append(str(value))

    def caption(self, value):
        self.captions.append(str(value))

    def stop(self):
        self.stops += 1
        raise SimulatedStop()


def env_object(env):
    return SimpleNamespace(getenv=lambda key, default="": env.get(key, default))


def extract_panel_functions():
    source = ast.parse(PANEL.read_text(encoding="utf-8"))
    names = ("_setting", "_bool_setting", "access_required")
    found = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in names]
    if len(found) != len(names):
        raise AssertionError("login source functions missing/duplicated")
    return compile(ast.Module(body=found, type_ignores=[]), str(PANEL), "exec")


def extract_cloud_fallback():
    source = ast.parse(APP.read_text(encoding="utf-8"))
    matches = [
        node for node in source.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "render_access_gate"
    ]
    if len(matches) != 1:
        raise AssertionError("actual app fallback missing/ambiguous")
    return compile(ast.Module(body=matches, type_ignores=[]), str(APP), "exec")


PANEL_CODE = extract_panel_functions()
FALLBACK_CODE = extract_cloud_fallback()


def simulated_primary(secrets=None, env=None, broken=False):
    st = StreamlitStub(secrets, broken)
    ns = {"st": st, "os": env_object(env or {}), "Any": object}
    exec(PANEL_CODE, ns)
    return ns["access_required"]()


def simulated_fallback(secrets=None, env=None, broken=False):
    st = StreamlitStub(secrets, broken)
    ns = {
        "render_access_gate": None,
        "st": st,
        "os": env_object(env or {}),
        "_ATLASQUANT_ACCESS_IMPORT_ERROR": "LAB missing import",
    }
    stopped = False
    try:
        exec(FALLBACK_CODE, ns)
    except SimulatedStop:
        stopped = True
    return stopped, st, ns.get("_ATLASQUANT_ACCESS")


class A199CrossSourceAuthenticationTests(unittest.TestCase):
    def check(self, secret=None, env=None, expected=True, broken=False):
        truth = simulated_primary(secret, env, broken)
        stopped, st, access = simulated_fallback(secret, env, broken)
        self.assertIs(truth, expected)
        self.assertIs(stopped, expected)
        if expected:
            self.assertEqual(st.stops, 1)
            self.assertIsNone(access)
        else:
            self.assertEqual(access["mode"], "OPEN")
            self.assertTrue(access["allowed"])
            self.assertEqual(st.stops, 0)

    def test_01_production_only_in_process_env_overrides_secrets_local(self):
        self.check(
            {"ATLASQUANT_ENV": "LOCAL", "ATLASQUANT_AUTH_REQUIRED": "false"},
            {"ATLASQUANT_ENV": "PRODUCTION"}, True,
        )

    def test_02_production_only_in_secrets_overrides_process_env_local(self):
        self.check(
            {"ATLASQUANT_ENV": "PRODUCTION", "ATLASQUANT_AUTH_REQUIRED": "false"},
            {"ATLASQUANT_ENV": "LOCAL"}, True,
        )

    def test_03_both_production_required(self):
        self.check({"ATLASQUANT_ENV": "PRODUCTION"}, {"ATLASQUANT_ENV": "PRODUCTION"})

    def test_04_lowercase_trim_process_production(self):
        self.check({"ATLASQUANT_ENV": "preview"}, {"ATLASQUANT_ENV": " production "})

    def test_05_lowercase_trim_secret_production(self):
        self.check({"ATLASQUANT_ENV": "  production "}, {"ATLASQUANT_ENV": "preview"})

    def test_06_secret_false_cannot_disable_env_auth_required_true(self):
        self.check(
            {"ATLASQUANT_ENV": "LOCAL", "ATLASQUANT_AUTH_REQUIRED": "false"},
            {"ATLASQUANT_AUTH_REQUIRED": "true"},
        )

    def test_07_env_auth_false_cannot_disable_secret_auth_true(self):
        self.check(
            {"ATLASQUANT_ENV": "LOCAL", "ATLASQUANT_AUTH_REQUIRED": "true"},
            {"ATLASQUANT_AUTH_REQUIRED": "false"},
        )

    def test_08_truthy_setting_aliases_in_both_sources(self):
        for value in TRUTHY:
            with self.subTest(source="secret", value=value):
                self.check({"ATLASQUANT_AUTH_REQUIRED": value}, {"ATLASQUANT_AUTH_REQUIRED": "false"})
            with self.subTest(source="process", value=value):
                self.check({"ATLASQUANT_AUTH_REQUIRED": "false"}, {"ATLASQUANT_AUTH_REQUIRED": value})

    def test_09_explicit_staging_all_false_can_remain_open(self):
        self.check(
            {"ATLASQUANT_ENV": "STAGING", "ATLASQUANT_AUTH_REQUIRED": "false"},
            {"ATLASQUANT_ENV": "STAGING", "ATLASQUANT_AUTH_REQUIRED": "false"},
            False,
        )

    def test_10_blank_missing_config_defaults_open_only_in_nonprod(self):
        self.check({}, {}, False)

    def test_11_unavailable_secrets_cannot_downgrade_env_production(self):
        self.check(
            {"ATLASQUANT_ENV": "LOCAL"},
            {"ATLASQUANT_ENV": "PRODUCTION"},
            broken=True,
        )

    def test_12_unavailable_secrets_cannot_downgrade_required_flag(self):
        self.check({}, {"ATLASQUANT_AUTH_REQUIRED": "yes"}, broken=True)

    def test_13_every_cross_source_combination_matches_fail_closed_or_rule(self):
        # The most important invariant: primary login and import-failure
        # fallback MUST implement identical monotonic OR semantics.
        env_values = ("", "LOCAL", "PRODUCTION", "production")
        flags = ("false", "true", "on")
        for secret_env in env_values:
            for process_env in env_values:
                for secret_auth in flags:
                    for process_auth in flags:
                        secrets = {
                            "ATLASQUANT_ENV": secret_env,
                            "ATLASQUANT_AUTH_REQUIRED": secret_auth,
                        }
                        env = {
                            "ATLASQUANT_ENV": process_env,
                            "ATLASQUANT_AUTH_REQUIRED": process_auth,
                        }
                        expected = (
                            secret_env.strip().upper() == "PRODUCTION"
                            or process_env.strip().upper() == "PRODUCTION"
                            or secret_auth in TRUTHY
                            or process_auth in TRUTHY
                        )
                        with self.subTest(secrets=secrets, env=env):
                            self.check(secrets, env, expected)

    def test_14_primary_gate_is_called_before_chat_host_in_live_app(self):
        source = APP.read_text(encoding="utf-8")
        self.assertLess(source.index("render_access_gate()"), source.index("build_streamlit_staged_binding("))
        self.assertLess(source.index("render_access_gate()"), source.index("build_streamlit_production_binding("))

    def test_15_debugger_cannot_treat_login_requirement_as_login_success(self):
        self.assertTrue(simulated_primary({"ATLASQUANT_ENV": "PRODUCTION"}, {}))
        # This unit only returns "authentication MUST be required". It does
        # not authenticate actual user, authorize external effects or close P0.
        print("A199_AUTH_REQUIRED_NOT_AUTHENTICATED_AND_NOT_P0_RED", flush=True)


if __name__ == "__main__":
    unittest.main()
