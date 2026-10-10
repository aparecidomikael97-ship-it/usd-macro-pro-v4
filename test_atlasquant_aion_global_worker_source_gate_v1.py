"""Actual Global Worker function: denied before first GET/CAS/exec, offline.

These tests run the unmodified body of run_global_worker_once via AST with
synthetic dependencies. No production flag, token, trusted key or network.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from atlasquant_aion_global_worker_source_gate_v1 import (
    independent_worker_source_preflight, SOURCE_GATE_SCHEMA,
)

ROOT = Path(__file__).resolve().parent
WORKER = ROOT / "atlasquant_aion_global_worker.py"
SOURCE_GATE = ROOT / "atlasquant_aion_global_worker_source_gate_v1.py"


def extract_runner(global_scope):
    source = WORKER.read_text("utf-8")
    tree = ast.parse(source)
    functions = [node for node in tree.body
                 if isinstance(node, ast.FunctionDef)
                 and node.name == "run_global_worker_once"]
    assert len(functions) == 1, "Real production runner missing or ambiguous"
    minimal = ast.Module(
        body=[
            ast.ImportFrom(module="__future__",
                           names=[ast.alias(name="annotations")], level=0),
            functions[0],
        ], type_ignores=[]
    )
    scope = dict(global_scope)
    exec(compile(ast.fix_missing_locations(minimal), str(WORKER), "exec"), scope)
    return scope["run_global_worker_once"]


class IndependentSourceWorkerBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.load = Mock(side_effect=AssertionError("UNAUTHORIZED_CHECKPOINT_GET"))
        self.cas = Mock(side_effect=AssertionError("UNAUTHORIZED_CAS"))
        self.execute = Mock(side_effect=AssertionError("UNAUTHORIZED_EXECUTOR"))
        self.config = SimpleNamespace(
            token="synthetic-only", repo="fake/repo", branch="atlasquant-runtime",
            path="dados/aion/checkpoint_master.json", write_ready=True,
        )
        self.scope = {
            "SCHEMA": "SYNTHETIC_WORKER_SCHEMA",
            "global_worker_feature_enabled": lambda: True,
            "config_from_mapping": lambda: self.config,
            "_runtime_id": lambda value: value if value else "",
            "independent_worker_source_preflight": independent_worker_source_preflight,
            "load_runtime_checkpoint": self.load,
            "_persist_runtime_checkpoint_cas": self.cas,
            "_execute_due_local_work_authorized": self.execute,
        }
        self.runner = extract_runner(self.scope)

    def assert_zero_io(self):
        self.load.assert_not_called()
        self.cas.assert_not_called()
        self.execute.assert_not_called()

    def test_real_runtime_denies_before_checkpoint_get_despite_enabled_valid_token(self):
        result = self.runner(config=self.config, runtime_id="gha-100-1",
                             feature_enabled=True)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "INDEPENDENT_CHECKPOINT_SOURCE_UNAVAILABLE")
        self.assertEqual(result["processed"], 0)
        self.assertFalse(result["network_called"])
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["automatic_runtime_checkpoint_persistence"])
        self.assertFalse(result["safe_to_retry"])
        self.assert_zero_io()

    def test_no_proof_when_repo_branch_path_claims_owner_b(self):
        for tenant in ("tenant_a", "tenant_b"):
            for path in (
                "dados/aion/checkpoint_master.json",
                f"dados/{tenant}/checkpoint_master.json",
                "../dados/aion/checkpoint_master.json",
            ):
                with self.subTest(tenant=tenant, path=path):
                    self.config.path = path
                    result = self.runner(config=self.config, runtime_id="gha-100-1",
                                         feature_enabled=True)
                    self.assertEqual(result["status"], "BLOCKED")
                    self.assert_zero_io()

    def test_admin_identity_and_runtime_flag_cannot_unlock_gate(self):
        for value in ("ENABLED", "ADMIN", "HUMAN_OWNER", True):
            with self.subTest(roles=value):
                self.config.role = value
                self.config.tenant_id = "tenant-one"
                self.config.owner_id = "owner-one"
                self.config.authorized = True
                decision = self.runner(config=self.config, runtime_id="gha-100-1",
                                       feature_enabled=True)
                self.assertEqual(decision["status"], "BLOCKED")
                self.assert_zero_io()

    def test_source_preflight_is_unconditionally_denied(self):
        self.assertEqual(
            independent_worker_source_preflight(self.config),
            {
                "schema": SOURCE_GATE_SCHEMA,
                "status": "BLOCKED",
                "reason": "INDEPENDENT_CHECKPOINT_SOURCE_UNAVAILABLE",
                "source_verified": False,
                "worker_authorized": False,
                "network_called": False,
                "reconciliation_required": True,
                "safe_to_retry": False,
            },
        )
        for config in (None, {}, object(), {"trusted":True,"approved":True}):
            with self.subTest(config=repr(config)):
                self.assertFalse(independent_worker_source_preflight(config)["source_verified"])

    def test_forged_positive_status_without_source_verified_does_not_unlock(self):
        scope = dict(self.scope)
        scope["independent_worker_source_preflight"] = Mock(
            return_value={"status": "VERIFIED", "source_verified":False})
        runner = extract_runner(scope)
        self.assertEqual(
            runner(config=self.config, runtime_id="gha-100-1", feature_enabled=True)["status"],
            "BLOCKED"
        )
        self.assert_zero_io()

    def test_feature_disabled_still_zero_io(self):
        result = self.runner(config=self.config, runtime_id="gha-100-1",
                             feature_enabled=False)
        self.assertEqual(result["status"], "FEATURE_DISABLED")
        self.assertFalse(result["network_called"])
        self.assert_zero_io()

    def test_missing_runtime_id_still_zero_io(self):
        result = self.runner(config=self.config, runtime_id="", feature_enabled=True)
        self.assertEqual(result["reason"], "GLOBAL_RUNTIME_ID_REQUIRED")
        self.assert_zero_io()

    def test_missing_write_credential_still_zero_io(self):
        self.config.write_ready = False
        result = self.runner(config=self.config, runtime_id="gha-100-1",
                             feature_enabled=True)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assert_zero_io()

    def test_static_source_origin_check_precedes_read_and_executor(self):
        src = WORKER.read_text(encoding="utf-8")
        tree = ast.parse(src)
        runner = next(x for x in tree.body
                      if isinstance(x, ast.FunctionDef)
                      and x.name == "run_global_worker_once")
        text = ast.get_source_segment(src, runner)
        self.assertLess(text.index("independent_worker_source_preflight(cfg)"),
                        text.index("load_runtime_checkpoint(cfg"))
        self.assertLess(text.index("independent_worker_source_preflight(cfg)"),
                        text.index("load_global_worker_state(checkpoint)"))
        self.assertIn("network_called\": False", text)
        gate = ast.parse(SOURCE_GATE.read_text(encoding="utf-8"))
        func = next(x for x in gate.body if isinstance(x, ast.FunctionDef)
                    and x.name == "independent_worker_source_preflight")
        self.assertEqual(len(func.body), 2)
        self.assertIsInstance(func.body[1], ast.Return)
        self.assertNotIn("os.environ", SOURCE_GATE.read_text("utf-8"))
        self.assertNotIn("st.session_state", SOURCE_GATE.read_text("utf-8"))
        self.assertNotIn("requests.", SOURCE_GATE.read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
