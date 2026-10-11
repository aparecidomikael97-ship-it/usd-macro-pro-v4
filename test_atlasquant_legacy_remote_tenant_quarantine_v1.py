"""Offline checks: shared GitHub private files cannot cross tenant boundaries.

Real entrypoint and store functions are extracted without booting the app.
They must deny BEFORE config/token lookup, HTTP GET, decode or cached return.
This suite never reads real secrets and never calls external services.
"""
from __future__ import annotations

import ast
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from atlasquant_legacy_private_resource_gate_v1 import (
    LEGACY_SHARED_PATHS, legacy_private_remote_resource_allowed,
    require_legacy_private_remote_resource,
)

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "usd_macro_pro_v4_cloud.py"


def extraction(path, name, globals_):
    source = (ROOT / path).read_text("utf-8")
    parsed = ast.parse(source, filename=path)
    found = [x for x in parsed.body if isinstance(x, ast.FunctionDef) and x.name == name]
    if len(found) != 1:
        raise AssertionError("Missing or ambiguous private reader " + path + ":" + name)
    node = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        found[0],
    ], type_ignores=[])
    scope = dict(globals_)
    exec(compile(ast.fix_missing_locations(node), path, "exec"), scope)
    return scope[name]


class LegacyRemoteTenantQuarantineTests(unittest.TestCase):
    def test_legacy_shared_paths_inventory_is_pinned(self):
        for expected in (
            "dados/sinais_v84.csv", "dados/atlasquant_shadow_samples.jsonl",
            "dados/atlasquant_operational_evidence_v1.jsonl",
            "dados/configuracoes_completas_v937.csv",
            "dados/scanner_tecnico_v934.json",
            "dados/autopilot_status_v107.json",
            "dados/paper_trading_summary_v112.json",
            "dados/paper_setup_summary_v114.json",
            "dados/atlasquant_quota_shadow_v1.json",
        ):
            self.assertIn(expected, LEGACY_SHARED_PATHS)

    def test_A_and_B_admin_membership_never_authorizes_same_remote_legacy_file(self):
        # Both synthetic accounts have valid admin membership in their own
        # workspaces. The shared legacy object lacks any trustworthy owner tag.
        for actor, workspace in (("admin.aaa", "tenant_one"),
                                  ("admin.bbb", "tenant_two")):
            for path in sorted(LEGACY_SHARED_PATHS):
                with self.subTest(actor=actor, workspace=workspace, path=path):
                    self.assertFalse(legacy_private_remote_resource_allowed(path))
                    with self.assertRaisesRegex(PermissionError, "TENANT_SOURCE_UNBOUND"):
                        require_legacy_private_remote_resource(path)

    def test_no_override_for_forged_tenant_prefixed_paths_or_malformed_values(self):
        for path in ("tenants/tenant_one/private.jsonl",
                     "tenants/tenant_two/private.jsonl",
                     "../tenant_one/private.jsonl", "%2fadmin", "", None,
                     {}, ["tenant_one"], object()):
            with self.subTest(path=repr(path)):
                self.assertFalse(legacy_private_remote_resource_allowed(path))

    def test_authorized_admin_cannot_fetch_any_entrypoint_legacy_resource(self):
        network = Mock(side_effect=AssertionError("NETWORK_DISPATCHED"))
        token = Mock(side_effect=AssertionError("PRIVATE_TOKEN_LOOKUP"))
        fake_df = lambda columns=None: {"columns": list(columns or [])}
        space = {
            "private_read_allowed": Mock(return_value=True),
            "legacy_private_remote_resource_allowed": legacy_private_remote_resource_allowed,
            "_github_cfg_v84": token, "_gh_cfg_v934": token,
            "pd": SimpleNamespace(DataFrame=fake_df),
            "_config_cols_v937": lambda: ["id_config"],
            "_CONFIG_GH_PATH_V937": "dados/configuracoes_completas_v937.csv",
            "_SCANNER_GH_PATH_V934": "dados/scanner_tecnico_v934.json",
            "requests": SimpleNamespace(get=network),
        }
        cases = (
            ("_github_get_json_v937", ("dados/autopilot_status_v107.json", {})),
            ("_github_ler_csv_v84", ()),
            ("_config_ler_v937", ()),
            ("_scanner_load_v934", ()),
        )
        for name, args in cases:
            with self.subTest(reader=name):
                reader = extraction(ENTRY.name, name, space)
                answer = reader(*args)
                if name == "_github_get_json_v937":
                    self.assertEqual(answer, ({}, "TENANT_SOURCE_UNBOUND"))
                elif name == "_github_ler_csv_v84":
                    self.assertIsNone(answer)
                elif name == "_config_ler_v937":
                    self.assertEqual(answer[1], "TENANT_SOURCE_UNBOUND")
                else:
                    self.assertEqual(answer["_erro"], "TENANT_SOURCE_UNBOUND")
        token.assert_not_called()
        network.assert_not_called()

    def test_stores_deny_even_if_private_session_gate_grants_admin(self):
        network = Mock(side_effect=AssertionError("NETWORK_DISPATCHED"))
        fake_auth = ModuleType("atlasquant_private_read_gate_v1")
        fake_auth.require_private_read = Mock(return_value=None)
        cases = (
            ("atlasquant_shadow_store.py", "_fetch", "dados/atlasquant_shadow_samples.jsonl"),
            ("atlasquant_research_evidence_store.py", "_fetch", "dados/atlasquant_operational_evidence_v1.jsonl"),
        )
        with patch.dict(sys.modules, {"atlasquant_private_read_gate_v1": fake_auth}):
            for path, fn, resource in cases:
                with self.subTest(path=path):
                    constants = {
                        "SHADOW_PATH": "dados/atlasquant_shadow_samples.jsonl",
                        "RESEARCH_EVIDENCE_PATH": "dados/atlasquant_operational_evidence_v1.jsonl",
                        "requests": SimpleNamespace(get=network),
                    }
                    reader = extraction(path, fn, constants)
                    with self.assertRaisesRegex(PermissionError, "TENANT_SOURCE_UNBOUND"):
                        reader("synthetic/repo", "atlasquant-runtime", "synthetic", 15)
        self.assertEqual(fake_auth.require_private_read.call_count, 2)
        network.assert_not_called()

    def test_paper_runtime_denies_before_token_branch_and_network(self):
        network = Mock(side_effect=AssertionError("NETWORK_DISPATCHED"))
        fake_auth = ModuleType("atlasquant_private_read_gate_v1")
        fake_auth.private_read_allowed = Mock(return_value=True)
        fake_pd = SimpleNamespace(DataFrame=lambda: [])
        with patch.dict(sys.modules, {"atlasquant_private_read_gate_v1": fake_auth}):
            reader = extraction("atlasquant_paper_setup_bridge.py", "_load_runtime_csv", {
                "pd": fake_pd, "requests": SimpleNamespace(get=network),
                "require_runtime_branch": Mock(side_effect=AssertionError("BRANCH_LOOKUP")),
                "DEFAULT_MAX_RUNTIME_ROWS": 10000,
            })
            rows, status = reader(
                path="dados/paper_audit_shared.csv",
                repo="synthetic/repo", branch="atlasquant-runtime", token="synthetic",
            )
        self.assertEqual(rows, [])
        self.assertEqual(status["reason"], "TENANT_SOURCE_UNBOUND")
        network.assert_not_called()

    def test_public_macro_provider_calls_are_not_blanket_quarantined(self):
        source = ENTRY.read_text("utf-8")
        self.assertIn('https://api.stlouisfed.org/fred/', source)
        self.assertIn('def _github_get_json_v937(path: str, default):', source)
        self.assertNotIn('legacy_private_remote_resource_allowed("FRED")', source)

    def test_guard_is_first_in_each_real_github_reader(self):
        spec = {
            "usd_macro_pro_v4_cloud.py": (
                "_github_get_json_v937", "_github_ler_csv_v84",
                "_config_ler_v937", "_scanner_load_v934",
            ),
            "atlasquant_shadow_store.py": ("_fetch",),
            "atlasquant_research_evidence_store.py": ("_fetch",),
            "atlasquant_paper_setup_bridge.py": ("_load_runtime_csv",),
        }
        for path, names in spec.items():
            src = (ROOT / path).read_text("utf-8")
            for name in names:
                found = [x for x in ast.parse(src).body
                         if isinstance(x, ast.FunctionDef) and x.name == name]
                self.assertEqual(len(found), 1)
                fn = found[0]
                calls = [x for x in ast.walk(fn) if isinstance(x, ast.Call)]
                target = [
                    x for x in calls
                    if isinstance(x.func, ast.Name)
                    and x.func.id in ("legacy_private_remote_resource_allowed",
                                      "require_legacy_private_remote_resource")
                ]
                self.assertEqual(len(target), 1, path + ":" + name)
                request = [x for x in calls
                           if isinstance(x.func, ast.Attribute)
                           and x.func.attr == "get"
                           and isinstance(x.func.value, ast.Name)
                           and x.func.value.id == "requests"]
                self.assertGreaterEqual(len(request), 1, path + ":" + name)
                self.assertLess(target[0].lineno, min(x.lineno for x in request))

    def test_quarantine_has_no_runtime_toggle_or_secret_token_dependency(self):
        path = ROOT / "atlasquant_legacy_private_resource_gate_v1.py"
        src = path.read_text("utf-8")
        tree = ast.parse(src)
        functions = {x.name:x for x in tree.body if isinstance(x, ast.FunctionDef)}
        target=functions["legacy_private_remote_resource_allowed"]
        self.assertEqual(len(target.body), 2)  # docstring and unconditional denial
        self.assertIsInstance(target.body[-1], ast.Return)
        self.assertIsInstance(target.body[-1].value, ast.Constant)
        self.assertIs(target.body[-1].value.value, False)
        for forbidden in ("os.environ", "st.secrets", "ATLASQUANT_PRIVATE", "GITHUB_TOKEN"):
            self.assertNotIn(forbidden, src)

if __name__ == "__main__":
    unittest.main()
