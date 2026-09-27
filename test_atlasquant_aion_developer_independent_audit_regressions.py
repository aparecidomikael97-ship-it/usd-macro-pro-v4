"""Permanent regressions for the 17 independent-audit contract gaps."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest

from atlasquant_aion_developer_command_policy import build_command_policy_contract
from atlasquant_aion_developer_content_attestation import attestation_for_documents
from atlasquant_aion_developer_manifest import (
    REQUIRED_MANDATORY_GATES,
    bind_builder_request_lineage,
    structural_request_roles,
)
from atlasquant_aion_developer_patch_validation import validate_patch
from atlasquant_aion_developer_runner_contract import (
    MAX_MANDATORY_GATES,
    MAX_TEST_TARGETS,
    _bind_runner_contract_ids,
    build_runner_contract,
)
from atlasquant_aion_developer_sandbox_preflight import (
    build_sandbox_preflight,
    expected_preflight_id,
)


def _builder(tests, gates=None):
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
            "branch": "cursor/fix",
            "baseline_ref": "main@aaa",
            "candidate_ref": "cursor/fix@bbb",
            "candidate_bound_to_branch": True,
            "main_branch_allowed": False,
            "force_push_allowed": False,
            "history_rewrite_allowed": False,
        },
        "scope": {
            "requested_files": ["test_module.py"],
            "authorized_files": ["test_module.py"],
            "scope_expansion_allowed": False,
            "new_file_allowed": False,
            "delete_file_allowed": False,
            "rename_file_allowed": False,
        },
        "test_contract": {
            "candidate_tests": list(tests),
            "mandatory_gates": list(gates) if gates is not None else list(REQUIRED_MANDATORY_GATES),
            "test_deletion_allowed": False,
            "test_weakening_allowed": False,
        },
        "blockers": [],
        "execution_authorized": False,
        "executor_attached": False,
        "writes_files": False,
    })


def _preflight_doc(builder):
    preflight = {
        "schema": "ATLASQUANT_AION_DEVELOPER_SANDBOX_PREFLIGHT_V1",
        "state": "READY_FOR_EXECUTOR_DESIGN_REVIEW",
        "builder_request_id": builder["request_id"],
        "test_contract_manifest_id": builder["test_contract_manifest_id"],
        "preflight_passed": True,
        "environment_contract": {
            "environment_kind": "ISOLATED_WORKTREE",
            "environment_id": "sandbox-001",
            "isolated_worktree": True,
            "repository_root_bound": True,
            "network_disabled": True,
            "secrets_mounted": False,
            "command_policy": "ALLOWLIST_ONLY",
        },
        "resource_budget": {
            "runtime_seconds": 900,
            "memory_mb": 2048,
            "output_bytes": 2_000_000,
            "max_commands": 24,
        },
        "scope": {"requested_files": ["test_module.py"]},
        "execution_authorized": False,
        "executor_attached": False,
    }
    preflight["preflight_id"] = expected_preflight_id(preflight)
    return preflight


def _patch_doc(builder, preflight):
    return {
        "schema": "ATLASQUANT_AION_DEVELOPER_PATCH_VALIDATION_V1",
        "validation_id": "DEVPATCHVAL-1",
        "state": "READY_FOR_PATCH_REVIEW",
        "builder_request_id": builder["request_id"],
        "preflight_id": preflight["preflight_id"],
        "patch_digest": "DEVPATCH-ABC",
        "revision_binding": {
            "baseline_ref": "main@aaa",
            "candidate_ref": "cursor/fix@bbb",
            "refs_match_approved_request": True,
            "revision_content_verified": True,
        },
        "blockers": [],
        "patch_applied": False,
        "execution_authorized": False,
        "executor_attached": False,
    }


def _runner(tests, gates=None):
    builder = _builder(tests, gates)
    preflight = _preflight_doc(builder)
    patch = _patch_doc(builder, preflight)
    return build_runner_contract(
        builder,
        preflight,
        patch,
        content_attestation=attestation_for_documents(builder, preflight, patch),
        human_patch_reviewed=True,
        human_patch_reviewer="reviewer-1",
        human_patch_review_refs=["review:patch:1"],
    )


def _preflight_request(path):
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
            "requested_files": [path],
            "authorized_files": [path],
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
        },
        "blockers": [],
        "execution_authorized": False,
        "executor_attached": False,
        "writes_files": False,
    })


def _call_preflight(path):
    return build_sandbox_preflight(
        _preflight_request(path),
        environment_kind="ISOLATED_WORKTREE",
        environment_id="sandbox-001",
        isolated_worktree=True,
        repository_root_bound=True,
        network_disabled=True,
        secrets_mounted=False,
        command_policy="ALLOWLIST_ONLY",
    )


def _patch_request():
    return {
        "schema": "ATLASQUANT_AION_DEVELOPER_BUILDER_SANDBOX_REQUEST_V1",
        "request_id": "DEVBUILD-1",
        "state": "READY_FOR_BUILDER_SANDBOX",
        "branch_contract": {
            "branch": "cursor/safe",
            "baseline_ref": "main@a",
            "candidate_ref": "cursor/safe@b",
        },
        "scope": {
            "requested_files": ["module.py", "test_module.py"],
            "authorized_files": ["module.py", "test_module.py"],
        },
        "blockers": [],
        "execution_authorized": False,
        "executor_attached": False,
    }


def _patch_preflight():
    return {
        "schema": "ATLASQUANT_AION_DEVELOPER_SANDBOX_PREFLIGHT_V1",
        "preflight_id": "DEVPREF-1",
        "builder_request_id": "DEVBUILD-1",
        "state": "READY_FOR_EXECUTOR_DESIGN_REVIEW",
        "preflight_passed": True,
        "execution_authorized": False,
        "executor_attached": False,
    }


def _validate(patch):
    return validate_patch(
        _patch_request(),
        _patch_preflight(),
        patch,
        baseline_ref="main@a",
        candidate_ref="cursor/safe@b",
    )


def _command_runner():
    runner = {
        "schema": "ATLASQUANT_AION_DEVELOPER_RUNNER_CONTRACT_V1",
        "runner_contract_id": "DEVRUN-1",
        "state": "READY_FOR_RUNNER_DESIGN_REVIEW",
        "resource_budget": {
            "runtime_seconds": 900,
            "memory_mb": 2048,
            "output_bytes": 2_000_000,
            "max_commands": 24,
        },
        "command_plan": [
            {
                "step": "COMPILE_CHANGED_SCOPE",
                "executable": "python",
                "argv": ["-m", "compileall", "-q", "<AUTHORIZED_CHANGED_SCOPE>"],
                "shell": False,
                "cwd": "<ISOLATED_WORKTREE>",
                "network": False,
                "writes_repo": False,
                "writes_repository": False,
                "may_write_ephemeral_cache": True,
                "pycache_prefix": "<SANDBOX_EPHEMERAL_PYCACHE>",
            },
            {
                "step": "RUN_TARGETED_TESTS",
                "executable": "python",
                "argv": ["-m", "unittest", "-q", "<APPROVED_TEST_TARGETS>"],
                "shell": False,
                "cwd": "<ISOLATED_WORKTREE>",
                "network": False,
                "writes_repo": False,
            },
            {
                "step": "VERIFY_DIFF_CHECK",
                "executable": "git",
                "argv": ["diff", "--check"],
                "shell": False,
                "cwd": "<ISOLATED_WORKTREE>",
                "network": False,
                "writes_repo": False,
            },
        ],
        "lineage": {
            "builder_request_id": "DEVBUILD-FIXTURE",
            "preflight_id": "DEVPREF-FIXTURE",
            "patch_validation_id": "DEVPATCHVAL-1",
            "patch_digest": "DEVPATCH-ABC",
            "content_attestation_id": "DEVATT-FIXTURE000000",
            "content_binding_structurally_bound": True,
            "content_binding_independently_verified": False,
        },
        "review": {
            "human_patch_reviewed": True,
            "human_patch_reviewer": "reviewer-1",
            "human_patch_review_refs": ["review:patch:1"],
        },
        "tests": {
            "targets": ["test_module.py"],
            "mandatory_gates": ["TARGETED_TESTS"],
            "tests_executed": False,
        },
        "command_plan_is_data_only": True,
        "shell_allowed": False,
        "network_allowed": False,
        "secrets_allowed": False,
        "repo_write_allowed": False,
        "path_lookup_allowed": False,
        "parent_environment_inheritance": False,
        "caller_environment_overrides_allowed": False,
        "content_binding_structurally_bound": True,
        "content_binding_independently_verified": False,
        "executable_pinning_verified": False,
        "os_sandbox_verified": False,
        "child_process_policy_verified": False,
        "symlink_physical_boundary_verified": False,
        "hardlink_physical_boundary_verified": False,
        "blockers": [],
        "execution_authorized": False,
        "executor_attached": False,
        "commands_executed": False,
        "writes_files": False,
        "runs_tests": False,
        "network_called": False,
        "subprocess_called": False,
        "automatic_commit": False,
        "automatic_merge": False,
        "automatic_deploy": False,
        "production_change_allowed": False,
        "real_trading_enabled": False,
        "tool_output_is_authority": False,
    }
    return _bind_runner_contract_ids(runner)


def _closed(out):
    for key in (
        "execution_authorized",
        "executor_attached",
        "commands_executed",
        "writes_files",
        "runs_tests",
    ):
        if key in out:
            if out[key] is not False:
                raise AssertionError(key)


class IndependentAuditContractGapTests(unittest.TestCase):
    def test_runner_rejects_external_test_paths(self):
        for target in ("../outside.py", "/outside.py"):
            with self.subTest(target=target):
                out = _runner([target])
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn("UNSAFE_TEST_TARGET", out["blockers"])
                self.assertNotIn(target, out["tests"]["targets"])
                _closed(out)

    def test_runner_rejects_windows_absolute_test_paths(self):
        for target in (
            "C:/outside.py",
            "C:\\outside.py",
            "\\\\server\\share\\test.py",
            "//server/share/test.py",
        ):
            with self.subTest(target=target):
                out = _runner([target])
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn("UNSAFE_TEST_TARGET", out["blockers"])
                self.assertNotIn(target, out["tests"]["targets"])
                _closed(out)

    def test_runner_rejects_unauthorized_or_missing_tests(self):
        for target in ("missing_test.py", "other_authorized_looking.py"):
            with self.subTest(target=target):
                out = _runner([target])
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn("TEST_TARGET_NOT_IN_AUTHORIZED_FILES", out["blockers"])
                self.assertNotIn(target, out["tests"]["targets"])
                _closed(out)

    def test_preflight_rejects_windows_drive_path_on_any_host(self):
        for path in (
            "C:/outside.py",
            "C:\\outside.py",
            "C:",
            "C:/",
            "/",
            "~",
            "\\\\server\\share\\test.py",
            "//server/share/test.py",
            "..\\outside.py",
            "../outside.py",
            "mod\x00ule.py",
        ):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    _call_preflight(path)

    def test_patch_rejects_divergent_diff_headers(self):
        patch = (
            "diff --git a/module.py b/module.py\n"
            "--- a/other.py\n"
            "+++ b/other.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        )
        out = _validate(patch)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("DIFF_HEADER_PATH_MISMATCH", out["blockers"])
        _closed(out)

    def test_patch_detects_secret_past_four_thousand_characters(self):
        sentinel = "password=SYNTHETICSECRETVALUE"
        patch = (
            "diff --git a/module.py b/module.py\n"
            "--- a/module.py\n"
            "+++ b/module.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+" + ("A" * 4000) + " " + sentinel + "\n"
        )
        out = _validate(patch)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("SECRET_LIKE_ADDITION_NOT_ALLOWED", out["blockers"])
        self.assertNotIn(sentinel, json.dumps(out))
        self.assertFalse(out["patch_text_included"])
        _closed(out)

    def test_patch_blocks_additive_test_neutralization(self):
        patch = (
            "diff --git a/test_module.py b/test_module.py\n"
            "--- a/test_module.py\n"
            "+++ b/test_module.py\n"
            "@@ -1,2 +1,4 @@\n"
            " def test_guard():\n"
            "     assert guard()\n"
            "+def test_guard():\n"
            "+    pass\n"
        )
        out = _validate(patch)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("TEST_ADDITIVE_NEUTRALIZATION_REQUIRES_SEPARATE_REVIEW", out["blockers"])
        self.assertEqual(out["files"][0]["deleted_lines"], 0)
        _closed(out)

    def _blocked_executable(self, executable):
        runner = _command_runner()
        runner["command_plan"] = deepcopy(runner["command_plan"])
        runner["command_plan"][0]["executable"] = executable
        _bind_runner_contract_ids(runner)
        out = build_command_policy_contract(runner)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("EXECUTABLE_MISMATCH:COMPILE_CHANGED_SCOPE", out["blockers"])
        rendered = json.dumps(out["validated_command_plan"])
        self.assertNotIn(executable, rendered)
        _closed(out)

    def test_command_policy_rejects_executable_nul(self):
        self._blocked_executable("python\x00")

    def test_command_policy_rejects_executable_newline(self):
        self._blocked_executable("python\n")

    def test_command_policy_rejects_executable_whitespace(self):
        self._blocked_executable("python ")
        self._blocked_executable(" python")

    def test_command_policy_rejects_non_mapping_plan_entries(self):
        for bad in (None, "python", [], 123, True):
            with self.subTest(bad=bad):
                runner = _command_runner()
                runner["command_plan"] = list(runner["command_plan"]) + [bad]
                _bind_runner_contract_ids(runner)
                out = build_command_policy_contract(runner)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn("COMMAND_PLAN_ENTRY_NOT_OBJECT", out["blockers"])
                self.assertEqual(out["validated_command_plan"], [])
                _closed(out)

    def test_command_policy_revalidates_runtime_budget(self):
        for value in (0, -1, 901):
            with self.subTest(value=value):
                runner = _command_runner()
                runner["resource_budget"] = dict(runner["resource_budget"])
                runner["resource_budget"]["runtime_seconds"] = value
                _bind_runner_contract_ids(runner)
                out = build_command_policy_contract(runner)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn("RUNTIME_BUDGET_OUT_OF_RANGE", out["blockers"])
                _closed(out)

    def test_command_policy_revalidates_memory_budget(self):
        for value in (0, 64, 4096):
            with self.subTest(value=value):
                runner = _command_runner()
                runner["resource_budget"] = dict(runner["resource_budget"])
                runner["resource_budget"]["memory_mb"] = value
                _bind_runner_contract_ids(runner)
                out = build_command_policy_contract(runner)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn("MEMORY_BUDGET_OUT_OF_RANGE", out["blockers"])
                _closed(out)

    def test_command_policy_revalidates_output_budget(self):
        for value in (0, 100, 3_000_000):
            with self.subTest(value=value):
                runner = _command_runner()
                runner["resource_budget"] = dict(runner["resource_budget"])
                runner["resource_budget"]["output_bytes"] = value
                _bind_runner_contract_ids(runner)
                out = build_command_policy_contract(runner)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn("OUTPUT_BUDGET_OUT_OF_RANGE", out["blockers"])
                _closed(out)

    def test_command_policy_revalidates_command_budget(self):
        for value in (0, 25, 100):
            with self.subTest(value=value):
                runner = _command_runner()
                runner["resource_budget"] = dict(runner["resource_budget"])
                runner["resource_budget"]["max_commands"] = value
                _bind_runner_contract_ids(runner)
                out = build_command_policy_contract(runner)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn("COMMAND_BUDGET_OUT_OF_RANGE", out["blockers"])
                _closed(out)

    def test_patch_without_hunk_is_not_ready(self):
        patch = (
            "diff --git a/module.py b/module.py\n"
            "--- a/module.py\n"
            "+++ b/module.py\n"
        )
        out = _validate(patch)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("DIFF_HUNK_REQUIRED", out["blockers"])
        self.assertEqual(out["files"][0]["hunk_count"], 0)
        _closed(out)

    def test_runner_does_not_truncate_excess_test_targets(self):
        out = _runner(["test_module.py"] * (MAX_TEST_TARGETS + 1))
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("TEST_TARGET_LIMIT_EXCEEDED", out["blockers"])
        self.assertEqual(out["tests"]["targets"], [])
        gates = _runner(
            ["test_module.py"],
            gates=[f"GATE_{index}" for index in range(MAX_MANDATORY_GATES + 1)],
        )
        self.assertEqual(gates["state"], "BLOCKED")
        self.assertIn("MANDATORY_GATE_LIMIT_EXCEEDED", gates["blockers"])
        self.assertEqual(gates["tests"]["mandatory_gates"], [])
        _closed(out)
        _closed(gates)


if __name__ == "__main__":
    unittest.main()
