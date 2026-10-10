"""Source-only regression: auth-module import/gate errors may NEVER allow OPEN.

Tests execute ONLY the exact access-gate conditional extracted by AST,
not the Streamlit app, providers, network, storage or user configuration.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parent


class GateStopped(RuntimeError):
    pass


def gate_ast(source: str) -> ast.If:
    tree = ast.parse(source)
    matches = [
        node for node in tree.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "render_access_gate"
        and len(node.test.ops) == 1
        and isinstance(node.test.ops[0], ast.IsNot)
        and len(node.test.comparators) == 1
        and isinstance(node.test.comparators[0], ast.Constant)
        and node.test.comparators[0].value is None
    ]
    if len(matches) != 1:
        raise AssertionError("EXPECTED_EXACTLY_ONE_AUTH_GATE")
    return matches[0]


def execute_gate(source: str, gate_func):
    gate = gate_ast(source)
    module = ast.fix_missing_locations(ast.Module(body=[gate], type_ignores=[]))
    messages = Mock()
    calls = []

    def stop():
        calls.append("st.stop")
        raise GateStopped()

    namespace = {
        "render_access_gate": gate_func,
        "os": os,
        "st": SimpleNamespace(
            error=messages, caption=Mock(), secrets={}, stop=stop,
        ),
    }
    exec(compile(module, "offline_auth_gate_ast", "exec"), namespace)
    return namespace, messages


class AuthImportFailClosedTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "usd_macro_pro_v4_cloud.py").read_text("utf-8")

    def test_missing_auth_module_never_falls_back_to_open(self):
        with self.assertRaises(GateStopped):
            execute_gate(self.source, None)

    def test_production_without_auth_required_never_falls_back_to_open(self):
        with patch.dict(os.environ, {
            "ATLASQUANT_ENV": "PRODUCTION",
            "ATLASQUANT_AUTH_REQUIRED": "false",
        }):
            with self.assertRaises(GateStopped):
                execute_gate(self.source, None)

    def test_auth_gate_exception_fails_closed(self):
        def broken():
            raise OSError("sensitive synthetic fixture")
        with self.assertRaises(GateStopped):
            execute_gate(self.source, broken)

    def test_auth_gate_denial_fails_closed(self):
        with self.assertRaises(GateStopped):
            execute_gate(self.source, lambda: {"allowed": False, "mode": "LOGIN"})

    def test_explicit_open_from_working_module_stays_separate_from_private_reads(self):
        ns, messages = execute_gate(
            self.source, lambda: {"allowed": True, "mode": "OPEN", "role": "OPEN"}
        )
        self.assertEqual(ns["_ATLASQUANT_ACCESS"]["mode"], "OPEN")
        self.assertFalse(messages.called)

    def test_invalid_gate_returns_fail_closed(self):
        for invalid in (None, "OPEN", [], True, {}):
            with self.subTest(value=repr(invalid)):
                with self.assertRaises(GateStopped):
                    execute_gate(self.source, lambda value=invalid: value)

    def test_authenticated_result_only_allows_application_boot(self):
        ns, _ = execute_gate(
            self.source,
            lambda: {"allowed": True, "mode": "AUTHENTICATED", "role": "ADMIN"},
        )
        self.assertTrue(ns["_ATLASQUANT_ACCESS"]["allowed"])

    def test_import_fallback_contains_no_open_or_env_override(self):
        gate = gate_ast(self.source)
        fallback = ast.unparse(ast.Module(body=gate.orelse, type_ignores=[]))
        self.assertNotIn("_ATLASQUANT_ACCESS", fallback)
        self.assertNotIn("AUTH_REQUIRED", fallback)
        self.assertNotIn("os.getenv", fallback)
        self.assertIn("st.stop()", fallback)


if __name__ == "__main__":
    unittest.main()
