from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_developer_manifest import (
    REQUIRED_MANDATORY_GATES,
    bind_builder_request_lineage,
    structural_request_roles,
)
from atlasquant_aion_developer_sandbox_preflight import (
    ALLOWED_COMMAND_POLICY,
    SCHEMA,
    build_sandbox_preflight,
)


def _request():
    return bind_builder_request_lineage({
        "schema": "ATLASQUANT_AION_DEVELOPER_BUILDER_SANDBOX_REQUEST_V1",
        "state": "READY_FOR_BUILDER_SANDBOX",
        "roles": structural_request_roles(),
        "lineage": {
            "snapshot_digest": "REPO-FIXTURE",
            "implementation_envelope_id": "DEVIMPL-FIXTURE",
            "implementation_authorization_id": "DEVAUTH-FIXTURE",
        },
        "branch_contract": {
            "branch": "cursor/sandbox",
            "baseline_ref": "main@a",
            "candidate_ref": "cursor/sandbox@b",
            "candidate_bound_to_branch": True,
            "main_branch_allowed": False,
            "force_push_allowed": False,
            "history_rewrite_allowed": False,
        },
        "scope": {
            "requested_files": ["module.py", "test_module.py"],
            "authorized_files": ["module.py", "test_module.py"],
            "scope_expansion_allowed": False,
            "new_file_allowed": False,
            "delete_file_allowed": False,
            "rename_file_allowed": False,
        },
        "test_contract": {
            "candidate_tests": ["test_module.py"],
            "mandatory_gates": list(REQUIRED_MANDATORY_GATES),
            "test_deletion_allowed": False,
            "test_weakening_allowed": False,
            "tests_executed": False,
        },
        "blockers": [],
        "execution_authorized": False,
        "executor_attached": False,
        "writes_files": False,
    })


def _preflight(request=None, **overrides):
    kwargs = {
        "environment_kind": "ISOLATED_WORKTREE",
        "environment_id": "sandbox-001",
        "isolated_worktree": True,
        "repository_root_bound": True,
        "network_disabled": True,
        "secrets_mounted": False,
        "command_policy": ALLOWED_COMMAND_POLICY,
    }
    kwargs.update(overrides)
    return build_sandbox_preflight(request or _request(), **kwargs)


class AionDeveloperSandboxPreflightTests(unittest.TestCase):
    def test_safe_contract_is_only_ready_for_executor_design_review(self):
        out = _preflight()
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "READY_FOR_EXECUTOR_DESIGN_REVIEW")
        self.assertTrue(out["preflight_passed"])
        self.assertTrue(out["executor_design_review_required"])
        self.assertFalse(out["execution_authorized"])
        self.assertFalse(out["executor_attached"])
        self.assertFalse(out["commands_executed"])
        self.assertFalse(out["writes_files"])
        self.assertFalse(out["network_called"])
        self.assertFalse(out["subprocess_called"])

    def test_network_or_secret_mount_blocks_preflight(self):
        out = _preflight(network_disabled=False, secrets_mounted=True)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("NETWORK_MUST_BE_DISABLED", out["blockers"])
        self.assertIn("SECRETS_MUST_NOT_BE_MOUNTED", out["blockers"])
        self.assertFalse(out["execution_authorized"])

    def test_isolation_and_repository_boundary_are_required(self):
        out = _preflight(isolated_worktree=False, repository_root_bound=False)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("ISOLATED_WORKTREE_REQUIRED", out["blockers"])
        self.assertIn("REPOSITORY_ROOT_BOUNDARY_REQUIRED", out["blockers"])

    def test_command_policy_must_be_allowlist_only(self):
        out = _preflight(command_policy="SHELL_ANY")
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("COMMAND_POLICY_MUST_BE_ALLOWLIST_ONLY", out["blockers"])

    def test_resource_budgets_fail_closed(self):
        out = _preflight(
            runtime_seconds=901,
            memory_mb=4096,
            output_bytes=3_000_000,
            max_commands=25,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("RUNTIME_BUDGET_OUT_OF_RANGE", out["blockers"])
        self.assertIn("MEMORY_BUDGET_OUT_OF_RANGE", out["blockers"])
        self.assertIn("OUTPUT_BUDGET_OUT_OF_RANGE", out["blockers"])
        self.assertIn("COMMAND_BUDGET_OUT_OF_RANGE", out["blockers"])

    def test_unsafe_path_fails_closed(self):
        request = _request()
        request["scope"] = deepcopy(request["scope"])
        request["scope"]["requested_files"] = ["../outside.py"]
        request["scope"]["authorized_files"] = ["../outside.py"]
        with self.assertRaises(ValueError):
            _preflight(request)

    def test_scope_expansion_fails_closed(self):
        request = _request()
        request["scope"] = deepcopy(request["scope"])
        request["scope"]["requested_files"] = ["module.py", "extra.py"]
        with self.assertRaises(ValueError):
            _preflight(request)

    def test_main_force_push_or_history_rewrite_authority_fails_closed(self):
        for field in ("main_branch_allowed", "force_push_allowed", "history_rewrite_allowed"):
            request = _request()
            request["branch_contract"] = deepcopy(request["branch_contract"])
            request["branch_contract"][field] = True
            with self.assertRaises(ValueError):
                _preflight(request)

    def test_no_tests_or_weakened_tests_fail_closed(self):
        request = _request()
        request["test_contract"] = deepcopy(request["test_contract"])
        request["test_contract"]["candidate_tests"] = []
        with self.assertRaises(ValueError):
            _preflight(request)

        request = _request()
        request["test_contract"] = deepcopy(request["test_contract"])
        request["test_contract"]["test_weakening_allowed"] = True
        with self.assertRaises(ValueError):
            _preflight(request)

    def test_non_ready_or_already_attached_request_fails_closed(self):
        request = _request()
        request["state"] = "BLOCKED"
        with self.assertRaises(ValueError):
            _preflight(request)

        request = _request()
        request["executor_attached"] = True
        with self.assertRaises(ValueError):
            _preflight(request)


if __name__ == "__main__":
    unittest.main()
