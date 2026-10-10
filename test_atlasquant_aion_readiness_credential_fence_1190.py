"""Real CLI + real config resolver AST, synthetic getenv only. No Worker tick."""
from contextlib import redirect_stdout
from io import StringIO
import ast
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from atlasquant_runtime_store import resolve_runtime_branch
import test_atlasquant_aion_global_worker_readiness_no_get_v1 as no_get
extract_real = no_get.extract_real
SOURCE = no_get.SOURCE

ROOT = Path(__file__).resolve().parent
MEMORY = ROOT / "atlasquant_aion_memory.py"


def memory_resolver(scope):
    program = ast.parse(MEMORY.read_text(encoding="utf-8"))
    node = next(n for n in program.body if isinstance(n, ast.FunctionDef) and n.name == "config_from_mapping")
    out = dict(scope)
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), node], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(MEMORY), "exec"), out)
    return out["config_from_mapping"]


class ReadinessCredentialFenceTests(unittest.TestCase):
    def setUp(self):
        self.base = no_get.ReadinessNoUnboundNetworkTests()
        self.base.setUp()
        self.lookups = []
        self.flag = "1"
        self.public = {"GITHUB_REPO_HISTORICO":"tenant-source/repository",
                       "GITHUB_DATA_BRANCH":"atlasquant-runtime", "GITHUB_BRANCH_HISTORICO":""}
        def getenv(key, default=""):
            self.lookups.append(key)
            if "TOKEN" in key or "SECRET" in key or "PASSWORD" in key:
                raise AssertionError("SECRET_RESOLVED_BEFORE_DENIAL")
            return self.flag if key == "GLOBAL_WORKER_FLAG_STATE" else self.public.get(key, default)
        self.scope = dict(self.base.scope)
        self.scope.update(os=SimpleNamespace(getenv=getenv), RuntimeConfig=SimpleNamespace,
                          DEFAULT_RUNTIME_REPO="aparecidomikael97-ship-it/usd-macro-pro-v4",
                          resolve_runtime_branch=resolve_runtime_branch)
        self.resolver = Mock(wraps=memory_resolver(self.scope))
        self.scope["config_from_mapping"] = self.resolver
        self.configs = []
        snapshot = self.scope["activation_readiness_snapshot"]
        def observe_snapshot(**kwargs):
            self.configs.append(kwargs["config"])
            return snapshot(**kwargs)
        self.scope["activation_readiness_snapshot"] = observe_snapshot
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        if any(isinstance(n, ast.FunctionDef) and n.name == "_readiness_source_config" for n in tree.body):
            self.scope["_readiness_source_config"] = extract_real("_readiness_source_config", self.scope)
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection", "requests.sessions.Session.request"):
            guard = patch(target, side_effect=AssertionError("NETWORK_FORBIDDEN"));guard.start();self.addCleanup(guard.stop)

    def run_cli(self):
        cli = extract_real("_cli", self.scope)
        output = StringIO()
        with patch.object(sys, "argv", ["readiness", "--check-runtime"]), redirect_stdout(output):
            code = cli()
        result = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["activation_stage"], "BLOCKED")
        self.assertIn("INDEPENDENT_CHECKPOINT_SOURCE_UNAVAILABLE", result["blockers"])
        self.assertFalse(result["private_checkpoint_fetch_performed"])
        self.assertFalse(result["pulse_fetch_performed"])
        self.base.runtime_get.assert_not_called();self.base.pulse_get.assert_not_called()
        self.assertFalse(any("TOKEN" in key for key in self.lookups))
        self.resolver.assert_not_called()
        self.assertEqual(self.configs[-1].token, "")
        return result

    def test_real_config_resolver_not_called_on_denied_source(self):
        self.run_cli()

    def test_flag_truthy_false_invalid_do_not_resolve_credentials(self):
        for flag in ("1", "0", "true", "false", "ADMIN", ""):
            with self.subTest(flag=flag):
                self.flag = flag
                self.run_cli()

    def test_default_public_destination_has_empty_token(self):
        self.public = {}
        self.run_cli()
        self.assertEqual(self.configs[-1].repo, "aparecidomikael97-ship-it/usd-macro-pro-v4")
        self.assertEqual(self.configs[-1].branch, "atlasquant-runtime")

    def test_supplied_repo_branch_only_describes_unverified_source(self):
        self.public["GITHUB_REPO_HISTORICO"] = "different-tenant/repository"
        self.public["GITHUB_DATA_BRANCH"] = "other-runtime"
        self.run_cli()
        self.assertEqual(self.configs[-1].repo, "different-tenant/repository")
        self.assertEqual(self.configs[-1].branch, "other-runtime")

    def test_production_source_gate_remains_unconditionally_denied(self):
        from atlasquant_aion_global_worker_source_gate_v1 import independent_worker_source_preflight
        for cfg in (None, self.public, {"source_verified": True, "approved": True}):
            result = independent_worker_source_preflight(cfg)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertFalse(result["worker_authorized"])

    def test_operational_workflow_preserves_failed_exit_not_continue_on_error(self):
        workflow = (ROOT / ".github/workflows/aion-global-worker-readiness.yml").read_text(encoding="utf-8")
        self.assertIn("set -o pipefail", workflow)
        self.assertIn("--check-runtime", workflow)
        self.assertNotIn("continue-on-error", workflow)
        self.assertNotIn("|| true", workflow)

    def test_frozen_resolver_negative_control_does_access_secret(self):
        with self.assertRaisesRegex(AssertionError, "SECRET_RESOLVED_BEFORE_DENIAL"):
            memory_resolver(self.scope)()
        self.assertIn("GITHUB_TOKEN_HISTORICO", self.lookups)


if __name__ == "__main__":
    unittest.main()
