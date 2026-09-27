"""Builder, preflight and patch semantic integrity.

A recomputed id is not a substitute for the constructor decision. These tests
do not run a probe, start a process, or authorize execution.
"""
from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_developer_builder_sandbox import (
    READY_STATE as BUILDER_READY,
    assert_builder_sandbox_request_integrity,
    structural_builder_sandbox_request,
)
from atlasquant_aion_developer_command_policy import build_command_policy_contract
from atlasquant_aion_developer_content_attestation import attestation_for_documents
from atlasquant_aion_developer_executable_pinning import (
    build_environment_contract,
    build_executable_pinning_spec,
)
from atlasquant_aion_developer_manifest import bind_builder_request_lineage
from atlasquant_aion_developer_os_sandbox_contract import (
    READY_STATE as OS_READY,
    build_os_sandbox_contract,
)
from atlasquant_aion_developer_os_sandbox_probe_result import (
    READY_STATE as PROBE_READY,
    build_probe_result_contract,
)
from atlasquant_aion_developer_patch_validation import (
    READY_STATE as PATCH_READY,
    assert_patch_validation_integrity,
    canonical_patch_document,
    validate_patch,
)
from atlasquant_aion_developer_runner_contract import (
    build_runner_contract,
)
from atlasquant_aion_developer_sandbox_preflight import (
    READY_STATE as PREFLIGHT_READY,
    assert_sandbox_preflight_integrity,
    build_sandbox_preflight,
    expected_preflight_id,
)
from test_atlasquant_aion_developer_attestation_pinning import _pin


_FORBIDDEN_BRANCHES = (
    "main",
    "master",
    "production",
    "prod",
    "live",
    "refs/heads/main",
    "refs/heads/master",
)
_AUTHORITY_FIELDS = (
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
    "ready_for_execution",
    "physical_probe_passed",
    "root_of_trust_verified",
    "executable_pinning_verified",
    "os_sandbox_verified",
    "filesystem_isolation_verified",
    "network_isolation_verified",
    "resource_limits_verified",
    "environment_isolation_verified",
    "output_limits_verified",
    "platform_adapter_verified",
)


def _builder():
    return structural_builder_sandbox_request(
        branch="cursor/safe",
        baseline_ref="main@a",
        candidate_ref="cursor/safe@b",
        requested_files=("module.py", "test_module.py"),
        candidate_tests=("test_module.py",),
    )


def _preflight(builder):
    return build_sandbox_preflight(
        builder,
        environment_kind="ISOLATED_WORKTREE",
        environment_id="sandbox-001",
        isolated_worktree=True,
        repository_root_bound=True,
        network_disabled=True,
        secrets_mounted=False,
        command_policy="ALLOWLIST_ONLY",
    )


def _secret_patch(secret):
    return (
        "diff --git a/module.py b/module.py\n"
        "--- a/module.py\n+++ b/module.py\n"
        "@@ -1 +1 @@\n-x=1\n+api_key=" + secret + "\n"
    )


def _pins():
    return [
        _pin("python", "/usr/bin/python3", "ab" * 32),
        _pin("git", "/usr/bin/git", "cd" * 32),
    ]


class UpstreamSemanticIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.builder = _builder()
        self.preflight = _preflight(self.builder)

    def _chain(self, builder=None, preflight=None, patch=None):
        builder = self.builder if builder is None else builder
        preflight = self.preflight if preflight is None else preflight
        if patch is None:
            patch = canonical_patch_document(builder, preflight)
        attestation = attestation_for_documents(builder, preflight, patch)
        runner = build_runner_contract(
            builder,
            preflight,
            patch,
            content_attestation=attestation,
            human_patch_reviewed=True,
            human_patch_reviewer="reviewer-1",
            human_patch_review_refs=["review:patch:1"],
        )
        policy = build_command_policy_contract(
            runner,
            builder_request=builder,
            preflight=preflight,
            patch_validation=patch,
            content_attestation=attestation,
        )
        pinning = build_executable_pinning_spec(_pins())
        environment = build_environment_contract()
        sandbox = build_os_sandbox_contract(
            policy, runner, builder, preflight, patch, attestation, pinning, environment,
        )
        result = build_probe_result_contract(
            sandbox, policy, runner, builder, preflight, patch, attestation, pinning, environment,
        )
        return runner, policy, sandbox, result, patch

    def test_secret_promotion_cannot_clear_file_summary(self):
        secret = "super-secret-value"
        blocked = validate_patch(
            self.builder,
            self.preflight,
            _secret_patch(secret),
            baseline_ref="main@a",
            candidate_ref="cursor/safe@b",
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn("SECRET_LIKE_ADDITION_NOT_ALLOWED", blocked["blockers"])
        self.assertGreater(blocked["files"][0]["secret_additions"], 0)
        self.assertIs(blocked["revision_binding"]["revision_content_verified"], False)
        self.assertNotIn(secret, str(blocked))

        promoted = deepcopy(blocked)
        promoted["state"] = "READY_FOR_PATCH_REVIEW"
        promoted["blockers"] = []
        promoted["revision_binding"] = dict(promoted["revision_binding"])
        promoted["revision_binding"]["revision_content_verified"] = True
        with self.assertRaises(ValueError):
            assert_patch_validation_integrity(promoted, self.builder, self.preflight)

        resealed = deepcopy(promoted)
        resealed["validation_id"] = "DEVPATCH-RESEALEDSECRET"
        with self.assertRaises(ValueError):
            assert_patch_validation_integrity(resealed, self.builder, self.preflight)
        with self.assertRaises(ValueError):
            build_runner_contract(
                self.builder,
                self.preflight,
                resealed,
                content_attestation=attestation_for_documents(self.builder, self.preflight, blocked),
                human_patch_reviewed=True,
                human_patch_reviewer="reviewer-1",
                human_patch_review_refs=["review:patch:1"],
            )

    def test_forbidden_branch_reseal_is_rejected_by_preflight(self):
        for name in _FORBIDDEN_BRANCHES:
            with self.subTest(branch=name):
                forged = deepcopy(self.builder)
                forged["branch_contract"] = dict(forged["branch_contract"])
                forged["branch_contract"]["branch"] = name
                logical = name
                while logical.startswith("refs/heads/"):
                    logical = logical[len("refs/heads/"):]
                forged["branch_contract"]["candidate_ref"] = logical + "@bbb"
                forged = bind_builder_request_lineage(forged)
                self.assertNotEqual(forged["request_id"], self.builder["request_id"])
                with self.assertRaises(ValueError):
                    assert_builder_sandbox_request_integrity(forged)
                with self.assertRaises(ValueError):
                    _preflight(forged)

    def test_preflight_blocker_and_scope_swap_survive_reseal(self):
        kept = deepcopy(self.preflight)
        kept["blockers"] = ["NETWORK_MUST_BE_DISABLED"]
        kept["state"] = "BLOCKED"
        kept["preflight_passed"] = False
        with self.assertRaises(ValueError):
            assert_sandbox_preflight_integrity(kept, self.builder)

        resealed = deepcopy(kept)
        resealed["preflight_id"] = expected_preflight_id(resealed)
        self.assertNotEqual(resealed["preflight_id"], self.preflight["preflight_id"])
        with self.assertRaises(ValueError):
            assert_sandbox_preflight_integrity(resealed, self.builder)

        swapped = deepcopy(self.preflight)
        swapped["scope"] = dict(swapped["scope"])
        swapped["scope"]["requested_files"] = ["outside.py"]
        swapped["preflight_id"] = expected_preflight_id(swapped)
        with self.assertRaises(ValueError):
            assert_sandbox_preflight_integrity(swapped, self.builder)
        clean = canonical_patch_document(self.builder, self.preflight)
        with self.assertRaises(ValueError):
            build_runner_contract(
                self.builder,
                swapped,
                clean,
                content_attestation=attestation_for_documents(self.builder, self.preflight, clean),
                human_patch_reviewed=True,
                human_patch_reviewer="reviewer-1",
                human_patch_review_refs=["review:patch:1"],
            )

    def test_authority_claims_cannot_reach_design_ready(self):
        documents = (
            (self.builder, lambda forged: assert_builder_sandbox_request_integrity(forged)),
            (self.preflight, lambda forged: assert_sandbox_preflight_integrity(forged, self.builder)),
        )
        patch = validate_patch(
            self.builder,
            self.preflight,
            (
                "diff --git a/module.py b/module.py\n"
                "--- a/module.py\n+++ b/module.py\n"
                "@@ -1 +1 @@\n-x=1\n+x=2\n"
            ),
            baseline_ref="main@a",
            candidate_ref="cursor/safe@b",
        )
        documents = documents + (
            (patch, lambda forged: assert_patch_validation_integrity(forged, self.builder, self.preflight)),
        )
        for document, checker in documents:
            for field in _AUTHORITY_FIELDS:
                with self.subTest(schema=document["schema"], field=field):
                    forged = deepcopy(document)
                    forged[field] = True
                    with self.assertRaises(ValueError):
                        checker(forged)

        forged_builder = deepcopy(self.builder)
        forged_builder["execution_authorized"] = True
        forged_builder = bind_builder_request_lineage(forged_builder)
        with self.assertRaises(ValueError):
            self._chain(builder=forged_builder, patch=patch)

    def test_forged_upstream_fails_probe_result(self):
        patch = validate_patch(
            self.builder,
            self.preflight,
            (
                "diff --git a/module.py b/module.py\n"
                "--- a/module.py\n+++ b/module.py\n"
                "@@ -1 +1 @@\n-x=1\n+x=2\n"
            ),
            baseline_ref="main@a",
            candidate_ref="cursor/safe@b",
        )
        forged = deepcopy(self.preflight)
        forged["scope"] = dict(forged["scope"])
        forged["scope"]["requested_files"] = ["outside.py"]
        forged["preflight_id"] = expected_preflight_id(forged)
        with self.assertRaises(ValueError):
            self._chain(preflight=forged, patch=patch)

    def test_legitimate_chain_stays_design_only(self):
        runner, policy, sandbox, result, patch = self._chain()
        self.assertEqual(self.builder["state"], BUILDER_READY)
        self.assertEqual(self.preflight["state"], PREFLIGHT_READY)
        self.assertEqual(patch["state"], PATCH_READY)
        self.assertIs(patch["revision_binding"]["revision_content_verified"], False)
        self.assertEqual(runner["state"], "READY_FOR_RUNNER_DESIGN_REVIEW")
        self.assertEqual(policy["state"], "READY_FOR_EXECUTABLE_PINNING_REVIEW")
        self.assertEqual(sandbox["state"], OS_READY)
        self.assertEqual(result["state"], PROBE_READY)
        for document in (self.builder, self.preflight, patch, runner, policy, sandbox, result):
            for field in _AUTHORITY_FIELDS:
                if field in document:
                    self.assertIs(document[field], False, field)

    def test_closed_schema_rejects_missing_builder_field(self):
        forged = deepcopy(self.builder)
        del forged["request_prepared"]
        with self.assertRaises(ValueError):
            assert_builder_sandbox_request_integrity(forged)
        forged = deepcopy(self.preflight)
        del forged["preflight_passed"]
        with self.assertRaises(ValueError):
            assert_sandbox_preflight_integrity(forged, self.builder)
