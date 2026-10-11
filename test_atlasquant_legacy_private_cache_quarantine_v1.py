"""Private Shadow/Research session caches are not remote tenant proof.

Uses actual function source and real clear_private_ui_state, synthetic dict
state, zero dependencies/services. No GitHub token/network or real client rows.
"""
from __future__ import annotations
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from atlasquant_private_read_gate_v1 import (
    clear_private_ui_state, PENDING_KEYS, QUARANTINE_KEY, SCOPE_KEY,
    DISPLAY_KEYS,
)
from atlasquant_legacy_private_resource_gate_v1 import legacy_private_remote_resource_allowed

ROOT = Path(__file__).resolve().parent


def real_function(path, name, scope):
    program = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    methods = [x for x in program.body if isinstance(x, ast.FunctionDef) and x.name == name]
    if len(methods) != 1:
        raise AssertionError("Missing / ambiguous production function " + path + ":" + name)
    node = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
                            methods[0]], type_ignores=[])
    ctx = dict(scope)
    exec(compile(ast.fix_missing_locations(node), path, "exec"), ctx)
    return ctx[name]


class PrivateLegacySessionCacheTests(unittest.TestCase):
    @staticmethod
    def scope(state):
        trap = Mock(side_effect=AssertionError("UNSAFE_OP_EXECUTED"))
        ctx = {
            "st": SimpleNamespace(session_state=state),
            "private_read_allowed": lambda: True,
            "legacy_private_remote_resource_allowed": legacy_private_remote_resource_allowed,
            "clear_private_ui_state": clear_private_ui_state,
            "SHADOW_PATH": "dados/atlasquant_shadow_samples.jsonl",
            "RESEARCH_EVIDENCE_PATH": "dados/atlasquant_operational_evidence_v1.jsonl",
            "load_shadow_samples": trap,
            "load_research_evidence": trap,
            "shadow_persistence_config": trap,
            "research_evidence_config": trap,
            "evidence_record": trap,
            "build_shadow_batch": trap,
            "persist_shadow_samples": trap,
            "persist_research_evidence": trap,
        }
        return ctx, trap

    def test_hydrated_shadow_cache_from_A_is_not_returned_to_any_authorized_actor(self):
        for actor in ("admin.aaa", "admin.bbb"):
            with self.subTest(actor=actor):
                state = {SCOPE_KEY: "synthetic-scope-" + actor,
                         "atlasquant_shadow_samples": [{"private": "FROM_A"}],
                         "atlasquant_shadow_hydrated": True,
                         "atlasquant_shadow_persistence_status": {"reason": "LOADED"}}
                ctx, trap = self.scope(state)
                run = real_function("atlasquant_shadow_capture.py", "ensure_shadow_hydrated", ctx)
                rows, status = run()
                self.assertEqual(rows, [])
                self.assertEqual(status["reason"], "TENANT_SOURCE_UNBOUND")
                self.assertNotIn("atlasquant_shadow_samples", state)
                self.assertNotIn("atlasquant_shadow_hydrated", state)
                self.assertNotIn(SCOPE_KEY, state)
                trap.assert_not_called()

    def test_hydrated_research_cache_never_returns_even_with_VALID_admin(self):
        state = {SCOPE_KEY: "synthetic-scope-A",
                 "atlasquant_research_evidence_records": [{"private": "FROM_A"}],
                 "atlasquant_research_evidence_hydrated": True,
                 "atlasquant_research_evidence_status": {"reason": "LOADED"}}
        ctx, trap = self.scope(state)
        run = real_function("atlasquant_research_evidence_capture.py", "ensure_research_evidence_hydrated", ctx)
        rows, status = run()
        self.assertEqual(rows, [])
        self.assertEqual(status["reason"], "TENANT_SOURCE_UNBOUND")
        self.assertNotIn("atlasquant_research_evidence_records", state)
        self.assertNotIn("atlasquant_research_evidence_hydrated", state)
        trap.assert_not_called()

    def test_research_session_only_capture_cannot_reseed_unbound_private_cache(self):
        for persist in (False, True):
            with self.subTest(persist=persist):
                state = {"atlasquant_research_evidence_records": [{"secret": "A"}]}
                ctx, trap = self.scope(state)
                capture = real_function("atlasquant_research_evidence_capture.py", "capture_research_evidence", ctx)
                result = capture(strategy="synthetic", source="unit", passport={},
                                 evidence={}, persist=persist)
                self.assertEqual(result["reason"], "TENANT_SOURCE_UNBOUND")
                self.assertFalse(result["safe_to_retry"])
                self.assertNotIn("atlasquant_research_evidence_records", state)
                trap.assert_not_called()

    def test_shadow_capture_cannot_reseed_unbound_private_cache(self):
        state = {"atlasquant_shadow_samples": [{"secret": "A"}]}
        ctx, trap = self.scope(state)
        capture = real_function("atlasquant_shadow_capture.py", "capture_shadow_batch", ctx)
        result = capture([], champion_version="synthetic")
        self.assertEqual(result["reason"], "TENANT_SOURCE_UNBOUND")
        self.assertNotIn("atlasquant_shadow_samples", state)
        trap.assert_not_called()

    def test_persist_existing_session_records_cannot_read_unbound_legacy_state(self):
        state = {"atlasquant_research_evidence_records": [{"private": "A"}]}
        ctx, trap = self.scope(state)
        persist = real_function("atlasquant_research_evidence_capture.py",
                                "persist_session_research_evidence", ctx)
        result = persist()
        self.assertEqual(result["reason"], "TENANT_SOURCE_UNBOUND")
        self.assertNotIn("atlasquant_research_evidence_records", state)
        trap.assert_not_called()

    def test_pending_unknown_write_kept_only_as_quarantined_status(self):
        state = {
            SCOPE_KEY: "old-scope",
            "atlasquant_shadow_hydrated": True,
            "atlasquant_shadow_samples": [{"private": "A"}],
            "atlasquant_shadow_persistence_status": {
                "reason": "UNKNOWN_OUTCOME",
                "write_attempted": True, "reconciliation_required": True
            },
        }
        ctx, trap = self.scope(state)
        rows, status = real_function("atlasquant_shadow_capture.py", "ensure_shadow_hydrated", ctx)()
        self.assertEqual(rows, [])
        self.assertEqual(status["reason"], "TENANT_SOURCE_UNBOUND")
        self.assertTrue(state[QUARANTINE_KEY])
        self.assertIn(PENDING_KEYS[0], state)
        self.assertEqual(state[PENDING_KEYS[0]]["reason"], "UNKNOWN_OUTCOME")
        self.assertTrue(state[PENDING_KEYS[0]]["write_attempted"])
        for k in (*DISPLAY_KEYS, SCOPE_KEY):
            self.assertNotIn(k, state)
        trap.assert_not_called()

    def test_all_cache_paths_require_tenant_source_proof_before_read(self):
        specs = (
            ("atlasquant_shadow_capture.py", "ensure_shadow_hydrated"),
            ("atlasquant_shadow_capture.py", "capture_shadow_batch"),
            ("atlasquant_research_evidence_capture.py", "ensure_research_evidence_hydrated"),
            ("atlasquant_research_evidence_capture.py", "capture_research_evidence"),
            ("atlasquant_research_evidence_capture.py", "persist_session_research_evidence"),
        )
        for path, name in specs:
            src = (ROOT / path).read_text("utf-8")
            funcs = [x for x in ast.parse(src).body if isinstance(x, ast.FunctionDef) and x.name == name]
            self.assertEqual(len(funcs), 1)
            calls = [x for x in ast.walk(funcs[0]) if isinstance(x, ast.Call)]
            gate = [x for x in calls if isinstance(x.func, ast.Name)
                    and x.func.id == "legacy_private_remote_resource_allowed"]
            self.assertEqual(len(gate), 1, path + " " + name)
            # Guard must run before a private collection can be copied
            # from st.session_state or used for dedup.
            getters = [x for x in calls if isinstance(x.func, ast.Attribute)
                       and x.func.attr == "get" and isinstance(x.func.value, ast.Attribute)
                       and x.func.value.attr == "session_state"]
            if getters:
                self.assertLess(gate[0].lineno, min(x.lineno for x in getters))

if __name__ == "__main__":
    unittest.main()
