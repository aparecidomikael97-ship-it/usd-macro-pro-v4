from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_developer_builder_sandbox import structural_builder_sandbox_request
from atlasquant_aion_developer_content_attestation import attestation_for_documents
from atlasquant_aion_developer_manifest import (
    REQUIRED_MANDATORY_GATES,
    bind_builder_request_lineage,
    structural_request_roles,
)
from atlasquant_aion_developer_runner_contract import (
    SCHEMA,
    build_runner_contract,
)
from atlasquant_aion_developer_patch_validation import canonical_patch_document
from atlasquant_aion_developer_sandbox_preflight import (
    ALLOWED_COMMAND_POLICY,
    build_sandbox_preflight,
    expected_preflight_id,
)


def _builder(**contract_overrides):
    tests = contract_overrides.get("candidate_tests", ["test_module.py"])
    gates = contract_overrides.get("mandatory_gates", list(REQUIRED_MANDATORY_GATES))
    return structural_builder_sandbox_request(
        candidate_tests=list(tests),
        mandatory_gates=list(gates),
    )


def _preflight(builder=None):
    return build_sandbox_preflight(
        builder or _builder(),
        environment_kind="ISOLATED_WORKTREE",
        environment_id="sandbox-001",
        isolated_worktree=True,
        repository_root_bound=True,
        network_disabled=True,
        secrets_mounted=False,
        command_policy=ALLOWED_COMMAND_POLICY,
    )


def _patch(builder, preflight, *, content_verified=False):
    document = canonical_patch_document(builder, preflight)
    if content_verified:
        document["revision_binding"]["revision_content_verified"] = True
    return document


def _run(builder=None, preflight=None, patch=None, **overrides):
    builder = builder or _builder()
    preflight = preflight or _preflight(builder)
    patch = patch or _patch(builder, preflight)
    args = {
        "content_attestation": attestation_for_documents(builder, preflight, patch),
        "human_patch_reviewed": True,
        "human_patch_reviewer": "reviewer-1",
        "human_patch_review_refs": ["review:patch:1"],
    }
    args.update(overrides)
    return build_runner_contract(
        builder,
        preflight,
        patch,
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
        self.assertTrue(out["content_binding_structurally_bound"])
        self.assertFalse(out["content_binding_independently_verified"])
        self.assertTrue(out["runner_contract_id"].startswith("DEVRUN-"))

    def test_revision_content_verified_true_is_rejected(self):
        builder = _builder()
        preflight = _preflight(builder)
        with self.assertRaises(ValueError):
            _run(
                builder=builder,
                preflight=preflight,
                patch=_patch(builder, preflight, content_verified=True),
            )

    def test_missing_external_content_binding_blocks(self):
        out = _run(content_attestation=None)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("CONTENT_ATTESTATION_REQUIRED", out["blockers"])
        self.assertFalse(out["content_binding_structurally_bound"])
        self.assertFalse(out["content_binding_independently_verified"])
        self.assertFalse(out["execution_authorized"])
        with self.assertRaises(TypeError):
            _run(content_binding_verified=True, content_binding_ref="tree:123")

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
        builder = _builder()
        preflight = _preflight(builder)
        patch = _patch(builder, preflight)
        bad_preflight = deepcopy(preflight)
        bad_preflight["builder_request_id"] = "OTHER"
        with self.assertRaises(ValueError):
            _run(builder=builder, preflight=bad_preflight, patch=patch)
        bad_patch = deepcopy(patch)
        bad_patch["preflight_id"] = "OTHER"
        with self.assertRaises(ValueError):
            _run(builder=builder, preflight=preflight, patch=bad_patch)

    def test_revision_ref_drift_fails_closed(self):
        builder = _builder()
        preflight = _preflight(builder)
        patch = _patch(builder, preflight)
        patch["revision_binding"] = deepcopy(patch["revision_binding"])
        patch["revision_binding"]["candidate_ref"] = "cursor/other@bbb"
        with self.assertRaises(ValueError):
            _run(builder=builder, preflight=preflight, patch=patch)

    def test_shell_network_and_write_are_absent_from_plan(self):
        out = _run()
        for step in out["command_plan"]:
            self.assertFalse(step["shell"])
            self.assertFalse(step["network"])
            self.assertFalse(step["writes_repo"])
            self.assertEqual(step["cwd"], "<ISOLATED_WORKTREE>")
            self.assertIsInstance(step["argv"], list)
        compile_step = out["command_plan"][0]
        self.assertFalse(compile_step["writes_repository"])
        self.assertTrue(compile_step["may_write_ephemeral_cache"])
        self.assertEqual(compile_step["pycache_prefix"], "<SANDBOX_EPHEMERAL_PYCACHE>")

    def test_unsafe_test_target_blocks_contract(self):
        builder = _builder(candidate_tests=["../outside_test.py"])
        out = _run(builder=builder)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("UNSAFE_TEST_TARGET", out["blockers"])

    def test_invalid_resource_budget_blocks(self):
        builder = _builder()
        preflight = _preflight(builder)
        preflight["resource_budget"] = dict(preflight["resource_budget"])
        preflight["resource_budget"]["runtime_seconds"] = 0
        preflight["preflight_id"] = expected_preflight_id(preflight)
        with self.assertRaises(ValueError):
            _run(builder=builder, preflight=preflight)

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
