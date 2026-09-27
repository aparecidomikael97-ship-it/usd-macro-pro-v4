from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_developer_runner_contract import (
    SCHEMA,
    build_runner_contract,
)


def _builder():
    return {
        "schema": "ATLASQUANT_AION_DEVELOPER_BUILDER_SANDBOX_REQUEST_V1",
        "request_id": "DEVBUILD-1",
        "state": "READY_FOR_BUILDER_SANDBOX",
        "branch_contract": {
            "baseline_ref": "main@aaa",
            "candidate_ref": "cursor/fix@bbb",
        },
        "test_contract": {
            "candidate_tests": ["test_module.py"],
            "mandatory_gates": ["QUALITY_TESTS", "RELEASE_READINESS"],
        },
        "blockers": [],
        "execution_authorized": False,
        "executor_attached": False,
    }


def _preflight():
    return {
        "schema": "ATLASQUANT_AION_DEVELOPER_SANDBOX_PREFLIGHT_V1",
        "preflight_id": "DEVPREF-1",
        "state": "READY_FOR_EXECUTOR_DESIGN_REVIEW",
        "builder_request_id": "DEVBUILD-1",
        "preflight_passed": True,
        "environment_contract": {
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
        "execution_authorized": False,
        "executor_attached": False,
    }


def _patch(*, content_verified=False):
    return {
        "schema": "ATLASQUANT_AION_DEVELOPER_PATCH_VALIDATION_V1",
        "validation_id": "DEVPATCHVAL-1",
        "state": "READY_FOR_PATCH_REVIEW",
        "builder_request_id": "DEVBUILD-1",
        "preflight_id": "DEVPREF-1",
        "patch_digest": "DEVPATCH-ABC",
        "revision_binding": {
            "baseline_ref": "main@aaa",
            "candidate_ref": "cursor/fix@bbb",
            "refs_match_approved_request": True,
            "revision_content_verified": content_verified,
        },
        "blockers": [],
        "patch_applied": False,
        "execution_authorized": False,
        "executor_attached": False,
    }


def _run(builder=None, preflight=None, patch=None, **overrides):
    args = {
        "content_binding_verified": True,
        "content_binding_ref": "tree:123",
        "human_patch_reviewed": True,
        "human_patch_reviewer": "reviewer-1",
        "human_patch_review_refs": ["review:patch:1"],
    }
    args.update(overrides)
    return build_runner_contract(
        builder or _builder(),
        preflight or _preflight(),
        patch or _patch(content_verified=True),
        **args,
    )


class AionDeveloperRunnerContractTests(unittest.TestCase):
    def test_ready_contract_is_design_review_only(self):
        out = _run()
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "READY_FOR_RUNNER_DESIGN_REVIEW")
        self.assertTrue(out["command_plan_is_data_only"])
        self.assertFalse(out["shell_allowed"])
        self.assertFalse(out["network_allowed"])
        self.assertFalse(out["secrets_allowed"])
        self.assertFalse(out["repo_write_allowed"])
        self.assertFalse(out["execution_authorized"])
        self.assertFalse(out["executor_attached"])
        self.assertFalse(out["commands_executed"])
        self.assertFalse(out["runs_tests"])

    def test_unverified_patch_content_blocks(self):
        out = _run(patch=_patch(content_verified=False))
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PATCH_VALIDATOR_CONTENT_BINDING_NOT_VERIFIED", out["blockers"])
        self.assertFalse(out["execution_authorized"])

    def test_missing_external_content_binding_blocks(self):
        out = _run(content_binding_verified=False, content_binding_ref="")
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("REVISION_CONTENT_BINDING_REQUIRED", out["blockers"])
        self.assertIn("CONTENT_BINDING_REF_REQUIRED", out["blockers"])

    def test_human_patch_review_is_required(self):
        out = _run(
            human_patch_reviewed=False,
            human_patch_reviewer="",
            human_patch_review_refs=[],
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("HUMAN_PATCH_REVIEW_REQUIRED", out["blockers"])
        self.assertIn("HUMAN_PATCH_REVIEWER_REQUIRED", out["blockers"])
        self.assertIn("HUMAN_PATCH_REVIEW_EVIDENCE_REQUIRED", out["blockers"])

    def test_lineage_mismatch_fails_closed(self):
        preflight = _preflight()
        preflight["builder_request_id"] = "OTHER"
        with self.assertRaises(ValueError):
            _run(preflight=preflight)

        patch = _patch(content_verified=True)
        patch["preflight_id"] = "OTHER"
        with self.assertRaises(ValueError):
            _run(patch=patch)

    def test_revision_ref_drift_fails_closed(self):
        patch = _patch(content_verified=True)
        patch["revision_binding"] = deepcopy(patch["revision_binding"])
        patch["revision_binding"]["candidate_ref"] = "cursor/other@bbb"
        with self.assertRaises(ValueError):
            _run(patch=patch)

    def test_shell_network_and_write_are_absent_from_plan(self):
        out = _run()
        for step in out["command_plan"]:
            self.assertFalse(step["shell"])
            self.assertFalse(step["network"])
            self.assertFalse(step["writes_repo"])
            self.assertEqual(step["cwd"], "<ISOLATED_WORKTREE>")
            self.assertIsInstance(step["argv"], list)

    def test_unsafe_test_target_blocks_contract(self):
        builder = _builder()
        builder["test_contract"] = deepcopy(builder["test_contract"])
        builder["test_contract"]["candidate_tests"] = ["../outside_test.py"]
        out = _run(builder=builder)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("UNSAFE_TEST_TARGET", out["blockers"])

    def test_invalid_resource_budget_blocks(self):
        preflight = _preflight()
        preflight["resource_budget"] = dict(preflight["resource_budget"])
        preflight["resource_budget"]["runtime_seconds"] = 0
        out = _run(preflight=preflight)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("INVALID_RESOURCE_BUDGET", out["blockers"])

    def test_never_executes_or_mutates(self):
        out = _run()
        for key in (
            "execution_authorized",
            "executor_attached",
            "commands_executed",
            "writes_files",
            "runs_tests",
            "network_called",
            "subprocess_called",
            "automatic_commit",
            "automatic_merge",
            "automatic_deploy",
            "production_change_allowed",
            "real_trading_enabled",
            "tool_output_is_authority",
        ):
            self.assertFalse(out[key])


if __name__ == "__main__":
    unittest.main()
