"""Runner and command-policy ids must match the sealed document.

A later edit that keeps the old id fails closed at the command-policy boundary
and again at the next design-review boundary. These tests do not execute
commands or read binaries.
"""
from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_developer_command_policy import (
    assert_command_policy_integrity,
    build_command_policy_contract,
)
from atlasquant_aion_developer_content_attestation import attestation_for_documents
from atlasquant_aion_developer_executable_pinning import (
    build_environment_contract,
    build_executable_pinning_spec,
    build_os_sandbox_design_review,
)
from atlasquant_aion_developer_manifest import REQUIRED_MANDATORY_GATES
from atlasquant_aion_developer_runner_contract import (
    _bind_runner_contract_ids,
    build_runner_contract,
)
from test_atlasquant_aion_developer_attestation_pinning import (
    _builder,
    _patch,
    _pin,
    _preflight,
)


_AUTHORITY_FLAGS = (
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
)


def _pins():
    return [
        _pin("python", "/usr/bin/python3", "ab" * 32),
        _pin("git", "/usr/bin/git", "cd" * 32),
    ]


class RunnerPolicyIntegrityTests(unittest.TestCase):
    def setUp(self):
        builder = _builder()
        preflight = _preflight(builder)
        patch = _patch(builder, preflight)
        attestation = attestation_for_documents(builder, preflight, patch)
        self.builder = builder
        self.preflight = preflight
        self.patch = patch
        self.runner = build_runner_contract(
            builder,
            preflight,
            patch,
            content_attestation=attestation,
            human_patch_reviewed=True,
            human_patch_reviewer="reviewer-1",
            human_patch_review_refs=["review:patch:1"],
        )
        self.attestation = attestation
        self.policy = build_command_policy_contract(
            self.runner,
            builder_request=builder,
            preflight=preflight,
            patch_validation=patch,
            content_attestation=attestation,
        )
        self.assertEqual(self.runner["state"], "READY_FOR_RUNNER_DESIGN_REVIEW")
        self.assertEqual(self.policy["state"], "READY_FOR_EXECUTABLE_PINNING_REVIEW")
        self.assertEqual(self.runner["resource_budget"]["runtime_seconds"], 900)

    def _stale(self, mutate):
        cloned = deepcopy(self.runner)
        mutate(cloned)
        self.assertEqual(cloned["runner_contract_id"], self.runner["runner_contract_id"])
        self.assertEqual(cloned["runner_contract_manifest_id"], self.runner["runner_contract_manifest_id"])
        with self.assertRaises(ValueError):
            build_command_policy_contract(cloned)

    def test_runtime_change_keeps_old_id_and_is_rejected(self):
        def mutate(runner):
            runner["resource_budget"]["runtime_seconds"] = 600
        self._stale(mutate)
        resealed = deepcopy(self.runner)
        resealed["resource_budget"]["runtime_seconds"] = 600
        _bind_runner_contract_ids(resealed)
        withheld = build_command_policy_contract(resealed)
        self.assertEqual(withheld["state"], "BLOCKED")
        self.assertIn("UPSTREAM_PROVENANCE_REQUIRED", withheld["blockers"])
        self.assertIs(withheld["upstream_provenance_structurally_verified"], False)
        self.assertIs(withheld["upstream_provenance_independently_verified"], False)
        self.assertFalse(withheld["execution_authorized"])
        with self.assertRaises(ValueError):
            build_command_policy_contract(
                resealed,
                builder_request=self.builder,
                preflight=self.preflight,
                patch_validation=self.patch,
                content_attestation=self.attestation,
            )

    def test_memory_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner["resource_budget"].__setitem__("memory_mb", 256))

    def test_output_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner["resource_budget"].__setitem__("output_bytes", 4096))

    def test_max_commands_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner["resource_budget"].__setitem__("max_commands", 8))

    def test_targets_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner["tests"]["targets"].append("test_module.py::extra"))

    def test_each_mandatory_gate_change_keeps_old_id_and_is_rejected(self):
        for gate in REQUIRED_MANDATORY_GATES:
            with self.subTest(gate=gate):
                def mutate(runner, gate=gate):
                    runner["tests"]["mandatory_gates"] = [
                        item for item in runner["tests"]["mandatory_gates"] if item != gate
                    ]
                self._stale(mutate)

    def test_reviewer_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner["review"].__setitem__(
            "human_patch_reviewer_principal_id", "prn_otherrev1",
        ))

    def test_review_ref_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner["review"]["human_patch_review_refs"].append("review:other"))

    def test_builder_request_id_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner["lineage"].__setitem__("builder_request_id", "DEVBUILD-OTHERREQUEST1"))

    def test_preflight_id_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner["lineage"].__setitem__("preflight_id", "DEVPREF-OTHERREQUEST01"))

    def test_patch_validation_id_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner["lineage"].__setitem__("patch_validation_id", "DEVPATCHVAL-OTHER"))

    def test_patch_digest_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner["lineage"].__setitem__("patch_digest", "DEVPATCH-OTHER"))

    def test_attestation_id_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner["lineage"].__setitem__("content_attestation_id", "DEVATT-" + ("A" * 18)))

    def test_structurally_bound_change_keeps_old_id_and_is_rejected(self):
        def mutate(runner):
            runner["content_binding_structurally_bound"] = False
            runner["lineage"]["content_binding_structurally_bound"] = False
        self._stale(mutate)
        resealed = deepcopy(self.runner)
        mutate(resealed)
        _bind_runner_contract_ids(resealed)
        with self.assertRaises(ValueError):
            build_command_policy_contract(resealed)

    def test_argv_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner["command_plan"][1]["argv"].append("--verbose"))

    def test_executable_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner["command_plan"][0].__setitem__("executable", "/tmp/python"))

    def test_cwd_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner["command_plan"][2].__setitem__("cwd", "/tmp"))

    def test_shell_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner["command_plan"][2].__setitem__("shell", True))

    def test_network_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner["command_plan"][2].__setitem__("network", True))

    def test_writes_repo_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner["command_plan"][2].__setitem__("writes_repo", True))

    def test_pycache_prefix_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner["command_plan"][0].__setitem__(
            "pycache_prefix", "<ISOLATED_WORKTREE>/__pycache__",
        ))

    def test_ephemeral_cache_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner["command_plan"][0].__setitem__("may_write_ephemeral_cache", False))

    def test_path_lookup_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner.__setitem__("path_lookup_allowed", True))
        resealed = deepcopy(self.runner)
        resealed["path_lookup_allowed"] = True
        _bind_runner_contract_ids(resealed)
        with self.assertRaises(ValueError):
            build_command_policy_contract(resealed)

    def test_parent_environment_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner.__setitem__("parent_environment_inheritance", True))
        resealed = deepcopy(self.runner)
        resealed["parent_environment_inheritance"] = True
        _bind_runner_contract_ids(resealed)
        with self.assertRaises(ValueError):
            build_command_policy_contract(resealed)

    def test_caller_environment_flag_change_keeps_old_id_and_is_rejected(self):
        self._stale(lambda runner: runner.__setitem__("caller_environment_overrides_allowed", True))
        resealed = deepcopy(self.runner)
        resealed["caller_environment_overrides_allowed"] = True
        _bind_runner_contract_ids(resealed)
        with self.assertRaises(ValueError):
            build_command_policy_contract(resealed)

    def test_authority_flag_change_keeps_old_id_and_is_rejected(self):
        for flag in _AUTHORITY_FLAGS:
            with self.subTest(flag=flag):
                self._stale(lambda runner, flag=flag: runner.__setitem__(flag, True))
                resealed = deepcopy(self.runner)
                resealed[flag] = True
                _bind_runner_contract_ids(resealed)
                with self.assertRaises(ValueError):
                    build_command_policy_contract(resealed)

    def test_deepcopy_nested_mutation_keeps_old_id_and_is_rejected(self):
        def mutate(runner):
            runner["tests"]["targets"] = list(runner["tests"]["targets"]) + ["test_other.py"]
            runner["review"]["human_patch_review_refs"] = list(runner["review"]["human_patch_review_refs"])
            runner["review"]["human_patch_review_refs"][0] = "review:copied"
            runner["command_plan"][0]["argv"] = list(runner["command_plan"][0]["argv"])
            runner["command_plan"][0]["argv"][-1] = "<MUTATED_SCOPE>"
        self._stale(mutate)

    def test_command_policy_mutation_keeps_old_id_and_is_rejected(self):
        mutated = deepcopy(self.policy)
        mutated["resource_budget"]["runtime_seconds"] = 600
        self.assertEqual(mutated["command_policy_id"], self.policy["command_policy_id"])
        with self.assertRaises(ValueError):
            assert_command_policy_integrity(mutated)

    def test_fixed_environment_mutation_keeps_old_id_and_is_rejected(self):
        mutated = deepcopy(self.policy)
        mutated["fixed_environment"]["PYTHONHASHSEED"] = "1"
        self.assertEqual(mutated["command_policy_id"], self.policy["command_policy_id"])
        with self.assertRaises(ValueError):
            assert_command_policy_integrity(mutated)

    def test_validated_command_plan_mutation_keeps_old_id_and_is_rejected(self):
        mutated = deepcopy(self.policy)
        mutated["validated_command_plan"][0]["argv"] = ["-m", "compileall", "-q", "<MUTATED>"]
        self.assertEqual(mutated["command_policy_id"], self.policy["command_policy_id"])
        with self.assertRaises(ValueError):
            assert_command_policy_integrity(mutated)

    def test_chained_boundary_rejects_stale_runner_and_policy(self):
        environment = build_environment_contract()
        pinning = build_executable_pinning_spec(_pins())
        fresh = build_os_sandbox_design_review(
            self.policy,
            pinning,
            self.attestation,
            environment,
            runner_contract=self.runner,
            builder_request=self.builder,
            preflight=self.preflight,
            patch_validation=self.patch,
        )
        self.assertEqual(fresh["state"], "READY_FOR_OS_SANDBOX_DESIGN_REVIEW")
        self.assertFalse(fresh["execution_authorized"])
        stale_runner = deepcopy(self.runner)
        stale_runner["resource_budget"]["runtime_seconds"] = 600
        stale_policy = deepcopy(self.policy)
        stale_policy["fixed_environment"]["PYTHONHASHSEED"] = "1"
        with self.assertRaises(ValueError):
            build_os_sandbox_design_review(
                stale_policy,
                pinning,
                self.attestation,
                environment,
                runner_contract=stale_runner,
                builder_request=self.builder,
                preflight=self.preflight,
                patch_validation=self.patch,
            )
        with self.assertRaises(ValueError):
            build_os_sandbox_design_review(
                self.policy,
                pinning,
                self.attestation,
                environment,
                runner_contract=stale_runner,
                builder_request=self.builder,
                preflight=self.preflight,
                patch_validation=self.patch,
            )
        with self.assertRaises(ValueError):
            build_os_sandbox_design_review(
                stale_policy,
                pinning,
                self.attestation,
                environment,
                runner_contract=self.runner,
                builder_request=self.builder,
                preflight=self.preflight,
                patch_validation=self.patch,
            )


if __name__ == "__main__":
    unittest.main()
