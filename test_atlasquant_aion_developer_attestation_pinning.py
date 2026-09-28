"""Content attestation, principal identity and executable pinning contracts.

These tests are data-only. They do not hash binaries, start a process, apply
a patch, or authorize execution.
"""
from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_developer_command_policy import build_command_policy_contract
from atlasquant_aion_developer_content_attestation import (
    SCHEMA as ATTESTATION_SCHEMA,
    attestation_for_documents,
    build_content_attestation,
)
from atlasquant_aion_developer_executable_pinning import (
    SANDBOX_EPHEMERAL_PYCACHE,
    build_environment_contract,
    build_executable_pinning_spec,
    build_os_sandbox_design_review,
)
from atlasquant_aion_developer_builder_sandbox import structural_builder_sandbox_request
from atlasquant_aion_developer_manifest import (
    REQUIRED_MANDATORY_GATES,
    bind_builder_request_lineage,
    structural_request_roles,
)
from atlasquant_aion_developer_patch_validation import canonical_patch_document
from atlasquant_aion_developer_principal_identity import (
    assert_independent_principals,
    classify_actor_pair,
    require_principal_id,
)
from atlasquant_aion_developer_runner_contract import (
    _bind_runner_contract_ids,
    build_runner_contract,
)
from atlasquant_aion_developer_sandbox_preflight import (
    ALLOWED_COMMAND_POLICY,
    build_sandbox_preflight,
)


def _builder():
    return structural_builder_sandbox_request()


def _preflight(builder):
    return build_sandbox_preflight(
        builder,
        environment_kind="ISOLATED_WORKTREE",
        environment_id="sandbox-001",
        isolated_worktree=True,
        repository_root_bound=True,
        network_disabled=True,
        secrets_mounted=False,
        command_policy=ALLOWED_COMMAND_POLICY,
    )


def _patch(builder, preflight, **overrides):
    document = canonical_patch_document(builder, preflight)
    document.update(overrides)
    return document


def _roles():
    return {
        "builder_principal_id": "prn_builder01",
        "reviewer_principal_id": "prn_reviewer1",
        "breaker_principal_id": "prn_breaker01",
        "approver_principal_id": "prn_approver1",
        "attestor_principal_id": "prn_attestor1",
    }


def _pin(name, path, digest):
    return {
        "logical_name": name,
        "absolute_path": path,
        "sha256": digest,
        "file_size_bytes": 128,
        "version_claim": "claim-only",
        "verification_evidence_refs": ["evidence:pin:" + name],
    }


def _pins():
    return [
        _pin("python", "/usr/bin/python3", "ab" * 32),
        _pin("git", "/usr/bin/git", "cd" * 32),
    ]


def _policy_runner():
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
                "pycache_prefix": SANDBOX_EPHEMERAL_PYCACHE,
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
            "mandatory_gates": list(REQUIRED_MANDATORY_GATES),
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


def _closed(test, document):
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
        "executable_pinning_verified",
        "os_sandbox_verified",
        "child_process_policy_verified",
        "symlink_physical_boundary_verified",
        "hardlink_physical_boundary_verified",
        "content_binding_independently_verified",
    ):
        if key in document:
            test.assertIs(document[key], False)
    test.assertNotEqual(document.get("state"), "READY_FOR_EXECUTION")


class AttestationPinningContractTests(unittest.TestCase):
    def setUp(self):
        self.builder = _builder()
        self.preflight = _preflight(self.builder)
        self.patch = _patch(self.builder, self.preflight)
        self.attestation = attestation_for_documents(self.builder, self.preflight, self.patch)

    def _run(self, attestation, patch=None):
        return build_runner_contract(
            self.builder,
            self.preflight,
            patch or self.patch,
            content_attestation=attestation,
            human_patch_reviewed=True,
            human_patch_reviewer="reviewer-1",
            human_patch_review_refs=["review:patch:1"],
        )

    def test_structural_attestation_does_not_independently_verify(self):
        self.assertEqual(self.attestation["schema"], ATTESTATION_SCHEMA)
        self.assertTrue(self.attestation["content_attestation_id"].startswith("DEVATT-"))
        self.assertEqual(len(self.attestation["content_attestation_id"]), len("DEVATT-") + 18)
        self.assertTrue(self.attestation["content_binding_structurally_bound"])
        self.assertFalse(self.attestation["content_binding_independently_verified"])
        again = build_content_attestation(self.attestation)
        self.assertEqual(again["content_attestation_id"], self.attestation["content_attestation_id"])
        runner = self._run(self.attestation)
        self.assertEqual(runner["state"], "READY_FOR_RUNNER_DESIGN_REVIEW")
        self.assertTrue(runner["content_binding_structurally_bound"])
        _closed(self, runner)

    def test_forged_content_attestation_is_rejected(self):
        forged = dict(self.attestation)
        forged["content_attestation_id"] = "DEVATT-" + ("F" * 18)
        forged["content_binding_verified"] = True
        with self.assertRaises(ValueError):
            self._run(forged)

    def test_stolen_attestation_id_is_rejected(self):
        other = attestation_for_documents(
            self.builder,
            self.preflight,
            self.patch,
            verification_evidence_refs=["evidence:other:1"],
        )
        stolen = dict(self.attestation)
        stolen["content_attestation_id"] = other["content_attestation_id"]
        self.assertNotEqual(stolen["content_attestation_id"], self.attestation["content_attestation_id"])
        with self.assertRaises(ValueError):
            self._run(stolen)

    def test_mutated_patch_digest_is_rejected(self):
        mutated = dict(self.attestation)
        mutated["patch_digest"] = "DEVPATCH-MUTATED"
        with self.assertRaises(ValueError):
            self._run(mutated)

    def test_mutated_candidate_sha_is_rejected(self):
        mutated = dict(self.attestation)
        mutated["candidate_commit_sha"] = "e" * 40
        with self.assertRaises(ValueError):
            self._run(mutated)

    def test_mutated_baseline_sha_is_rejected(self):
        mutated = dict(self.attestation)
        mutated["baseline_commit_sha"] = "f" * 40
        with self.assertRaises(ValueError):
            self._run(mutated)

    def test_mutated_tree_sha_is_rejected(self):
        mutated = dict(self.attestation)
        mutated["candidate_tree_sha"] = "9" * 40
        with self.assertRaises(ValueError):
            self._run(mutated)

    def test_different_request_id_is_rejected(self):
        foreign = attestation_for_documents(
            self.builder,
            self.preflight,
            self.patch,
            builder_request_id="DEVBUILD-OTHERREQUEST1",
        )
        with self.assertRaises(ValueError):
            self._run(foreign)

    def test_different_preflight_id_is_rejected(self):
        foreign = attestation_for_documents(
            self.builder,
            self.preflight,
            self.patch,
            preflight_id="DEVPREF-OTHERREQUEST01",
        )
        with self.assertRaises(ValueError):
            self._run(foreign)

    def test_different_validation_id_is_rejected(self):
        foreign = attestation_for_documents(
            self.builder,
            self.preflight,
            self.patch,
            patch_validation_id="DEVPATCHVAL-OTHER",
        )
        with self.assertRaises(ValueError):
            self._run(foreign)

    def test_attestation_replay_on_another_patch_is_rejected(self):
        other = _patch(self.builder, self.preflight)
        other["patch_digest"] = "DEVPATCH-OTHER"
        other["validation_id"] = "DEVPATCHVAL-2"
        with self.assertRaises(ValueError):
            self._run(self.attestation, other)

    def test_duplicate_principal_ids_are_rejected(self):
        roles = _roles()
        roles["attestor_principal_id"] = roles["builder_principal_id"]
        with self.assertRaises(ValueError):
            assert_independent_principals(roles)

    def test_same_principal_with_cyrillic_display_is_the_same_actor(self):
        shared = "prn_attestor1"
        left = {"display_actor": "Alice", "principal_id": shared}
        right = {"display_actor": "\u0410lice", "principal_id": shared}
        self.assertEqual(classify_actor_pair(left, right), "SAME_PRINCIPAL")
        roles = _roles()
        roles["builder_principal_id"] = shared
        roles["attestor_principal_id"] = shared
        with self.assertRaises(ValueError):
            assert_independent_principals(roles)
        distinct = classify_actor_pair(
            {"display_actor": "Alice", "principal_id": "prn_builder01"},
            {"display_actor": "Alice", "principal_id": "prn_reviewer1"},
        )
        self.assertEqual(distinct, "DISTINCT_PRINCIPALS")

    def test_empty_principal_is_rejected(self):
        with self.assertRaises(ValueError):
            require_principal_id("")
        with self.assertRaises(ValueError):
            require_principal_id(" prn_builder01")

    def test_principal_with_control_or_invisible_is_rejected(self):
        with self.assertRaises(ValueError):
            require_principal_id("prn_builder01" + "\u200b")
        with self.assertRaises(ValueError):
            require_principal_id("prn_builder01" + "\u0001")

    def test_relative_executable_path_is_rejected(self):
        pins = _pins()
        pins[0]["absolute_path"] = "usr/bin/python3"
        with self.assertRaises(ValueError):
            build_executable_pinning_spec(pins)

    def test_malformed_sha256_is_rejected(self):
        pins = _pins()
        pins[0]["sha256"] = "AB" * 32
        with self.assertRaises(ValueError):
            build_executable_pinning_spec(pins)
        pins[0]["sha256"] = "abc"
        with self.assertRaises(ValueError):
            build_executable_pinning_spec(pins)

    def test_extra_executable_is_rejected(self):
        with self.assertRaises(ValueError):
            build_executable_pinning_spec(_pins() + [
                _pin("bash", "/usr/bin/bash", "ef" * 32),
            ])

    def test_python_without_git_is_rejected(self):
        with self.assertRaises(ValueError):
            build_executable_pinning_spec([_pins()[0]])

    def test_path_lookup_enabled_is_blocked(self):
        out = build_command_policy_contract(_policy_runner(), path_lookup_allowed=True)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PATH_LOOKUP_NOT_ALLOWED", out["blockers"])
        self.assertFalse(out["allowlist_policy"]["PATH_LOOKUP_ALLOWED"])
        _closed(self, out)

    def test_caller_environment_override_is_blocked(self):
        out = build_environment_contract(caller_environment={"CUSTOM": "1"})
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("CALLER_ENVIRONMENT_NOT_ALLOWED", out["blockers"])
        self.assertFalse(out["caller_environment_overrides_allowed"])
        policy = build_command_policy_contract(
            _policy_runner(),
            requested_environment={"CUSTOM": "1"},
        )
        self.assertIn("CALLER_ENVIRONMENT_OVERRIDES_NOT_ALLOWED", policy["blockers"])

    def test_pythonpath_injection_is_blocked(self):
        out = build_environment_contract(caller_environment={"PYTHONPATH": "/tmp/injected"})
        self.assertIn("INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED", out["blockers"])
        self.assertNotIn("PYTHONPATH", out["fixed_environment"])

    def test_pythonstartup_injection_is_blocked(self):
        out = build_environment_contract(caller_environment={"PYTHONSTARTUP": "/tmp/startup.py"})
        self.assertIn("INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED", out["blockers"])

    def test_home_injection_is_blocked(self):
        out = build_environment_contract(caller_environment={"HOME": "/tmp/home"})
        self.assertIn("INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED", out["blockers"])

    def test_git_config_injection_is_blocked(self):
        out = build_environment_contract(caller_environment={"GIT_CONFIG": "/tmp/gitconfig"})
        self.assertIn("INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED", out["blockers"])
        policy = build_command_policy_contract(
            _policy_runner(),
            requested_environment={"GIT_CONFIG": "/tmp/gitconfig"},
        )
        self.assertIn("INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED", policy["blockers"])
        self.assertEqual(policy["state"], "BLOCKED")

    def test_pycache_inside_worktree_is_blocked(self):
        runner = _policy_runner()
        runner["command_plan"] = deepcopy(runner["command_plan"])
        runner["command_plan"][0]["pycache_prefix"] = "<ISOLATED_WORKTREE>/__pycache__"
        _bind_runner_contract_ids(runner)
        out = build_command_policy_contract(runner)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PYCACHE_INSIDE_WORKTREE", out["blockers"])
        self.assertEqual(out["validated_command_plan"], [])

    def test_pycache_inside_repository_is_blocked(self):
        runner = _policy_runner()
        runner["command_plan"] = deepcopy(runner["command_plan"])
        runner["command_plan"][0]["pycache_prefix"] = "<REPOSITORY_ROOT>/__pycache__"
        _bind_runner_contract_ids(runner)
        out = build_command_policy_contract(runner)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PYCACHE_INSIDE_REPOSITORY", out["blockers"])

    def test_fake_executable_pinning_verified_is_rejected(self):
        with self.assertRaises(ValueError):
            build_executable_pinning_spec(_pins(), executable_pinning_verified=True)
        spec = build_executable_pinning_spec([
            _pin("python", "/tmp/python", "ab" * 32),
            _pin("git", "/tmp/git", "cd" * 32),
        ])
        self.assertEqual(spec["state"], "READY_FOR_EXECUTABLE_PINNING_PROBE")
        self.assertTrue(spec["pinning_spec_complete"])
        self.assertFalse(spec["executable_pinning_verified"])
        self.assertFalse(spec["caller_supplied_digest_is_proof"])
        _closed(self, spec)

    def test_boolean_content_binding_without_attestation_does_not_promote(self):
        blocked = self._run(None)
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn("CONTENT_ATTESTATION_REQUIRED", blocked["blockers"])
        self.assertFalse(blocked["content_binding_structurally_bound"])
        _closed(self, blocked)
        with self.assertRaises(TypeError):
            build_runner_contract(
                self.builder,
                self.preflight,
                self.patch,
                content_binding_verified=True,
                content_binding_ref="tree:123",
                human_patch_reviewed=True,
                human_patch_reviewer="reviewer-1",
                human_patch_review_refs=["review:patch:1"],
            )

    def test_compileall_without_cache_policy_is_blocked(self):
        runner = _policy_runner()
        runner["command_plan"] = deepcopy(runner["command_plan"])
        runner["command_plan"][0].pop("writes_repository")
        runner["command_plan"][0].pop("may_write_ephemeral_cache")
        runner["command_plan"][0].pop("pycache_prefix")
        self.assertFalse(runner["command_plan"][0]["writes_repo"])
        _bind_runner_contract_ids(runner)
        out = build_command_policy_contract(runner)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("COMPILEALL_CACHE_POLICY_REQUIRED", out["blockers"])
        self.assertFalse(out["compile_step_executable"])

    def test_mutation_after_attestation_is_rejected(self):
        mutated = dict(self.attestation)
        mutated["verification_evidence_refs"] = ["evidence:mutated:1"]
        with self.assertRaises(ValueError):
            self._run(mutated)
        mutated_sha = dict(self.attestation)
        mutated_sha["baseline_tree_sha"] = "1" * 40
        with self.assertRaises(ValueError):
            self._run(mutated_sha)

    def test_equal_refs_commits_or_trees_are_rejected(self):
        with self.assertRaises(ValueError):
            attestation_for_documents(
                self.builder,
                self.preflight,
                self.patch,
                baseline_ref="cursor/fix@bbb",
                candidate_ref="cursor/fix@bbb",
            )
        with self.assertRaises(ValueError):
            attestation_for_documents(
                self.builder,
                self.preflight,
                self.patch,
                candidate_commit_sha="a" * 40,
            )
        with self.assertRaises(ValueError):
            attestation_for_documents(
                self.builder,
                self.preflight,
                self.patch,
                candidate_tree_sha="c" * 40,
            )

    def test_design_review_bundle_never_authorizes_execution(self):
        runner = self._run(self.attestation)
        policy = build_command_policy_contract(
            runner,
            builder_request=self.builder,
            preflight=self.preflight,
            patch_validation=self.patch,
            content_attestation=self.attestation,
        )
        pinning = build_executable_pinning_spec(_pins())
        environment = build_environment_contract()
        review = build_os_sandbox_design_review(
            policy,
            pinning,
            self.attestation,
            environment,
            runner_contract=runner,
            builder_request=self.builder,
            preflight=self.preflight,
            patch_validation=self.patch,
        )
        self.assertEqual(review["state"], "READY_FOR_OS_SANDBOX_DESIGN_REVIEW")
        self.assertTrue(review["content_binding_structurally_bound"])
        self.assertFalse(review["compile_step_executable"])
        _closed(self, review)
        claimed = dict(pinning)
        claimed["executable_pinning_verified"] = True
        with self.assertRaises(ValueError):
            build_os_sandbox_design_review(
                policy,
                claimed,
                self.attestation,
                environment,
                runner_contract=runner,
                builder_request=self.builder,
                preflight=self.preflight,
                patch_validation=self.patch,
            )


if __name__ == "__main__":
    unittest.main()
