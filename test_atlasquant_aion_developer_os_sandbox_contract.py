"""OS sandbox security design is a contract, not a running sandbox.

The ready state means the physical-probe checklist is complete. It does not
mean a process, filesystem, or network boundary was created. These tests do
not execute commands.
"""
from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_developer_command_policy import (
    _bind_command_policy_ids,
    build_command_policy_contract,
)
from atlasquant_aion_developer_content_attestation import attestation_for_documents
from atlasquant_aion_developer_executable_pinning import (
    assert_environment_contract_integrity,
    assert_executable_pinning_spec_integrity,
    build_environment_contract,
    build_executable_pinning_spec,
    build_os_sandbox_design_review,
    expected_pinning_spec_id,
    require_absolute_path,
)
from atlasquant_aion_developer_manifest import bind_builder_request_lineage
from atlasquant_aion_developer_os_sandbox_contract import (
    FUTURE_RESOURCE_PROBE_FIELDS,
    PHYSICAL_PROOF_BLOCKERS,
    READY_STATE,
    REQUIRED_BEFORE_FUTURE_EXECUTION,
    _bind_os_sandbox_ids,
    assert_os_sandbox_contract,
    assert_os_sandbox_contract_integrity,
    build_os_sandbox_contract,
    expected_os_sandbox_state_and_blockers,
    os_sandbox_manifest,
)
from atlasquant_aion_developer_runner_contract import build_runner_contract
from test_atlasquant_aion_developer_attestation_pinning import (
    _builder,
    _patch,
    _pin,
    _preflight,
)


_PHYSICAL_FLAGS = (
    "executable_pinning_verified",
    "os_sandbox_verified",
    "child_process_policy_verified",
    "filesystem_isolation_verified",
    "network_isolation_verified",
    "resource_limits_verified",
    "environment_isolation_verified",
    "output_limits_verified",
    "symlink_physical_boundary_verified",
    "hardlink_physical_boundary_verified",
    "platform_adapter_verified",
    "content_binding_independently_verified",
    "upstream_provenance_independently_verified",
    "execution_authorized",
    "subprocess_called",
    "network_called",
    "writes_files",
    "runs_tests",
)


def _pins(python_digest="ab" * 32):
    return [
        _pin("python", "/usr/bin/python3", python_digest),
        _pin("git", "/usr/bin/git", "cd" * 32),
    ]


class OsSandboxSecurityContractTests(unittest.TestCase):
    def setUp(self):
        self.builder = _builder()
        self.preflight = _preflight(self.builder)
        self.patch = _patch(self.builder, self.preflight)
        self.attestation = attestation_for_documents(
            self.builder, self.preflight, self.patch,
        )
        self.runner = build_runner_contract(
            self.builder,
            self.preflight,
            self.patch,
            content_attestation=self.attestation,
            human_patch_reviewed=True,
            human_patch_reviewer="reviewer-1",
            human_patch_review_refs=["review:patch:1"],
        )
        self.policy = build_command_policy_contract(
            self.runner,
            builder_request=self.builder,
            preflight=self.preflight,
            patch_validation=self.patch,
            content_attestation=self.attestation,
        )
        self.pinning = build_executable_pinning_spec(_pins())
        self.environment = build_environment_contract()
        self.contract = self._build()

    def _build(self, **overrides):
        payload = {
            "command_policy": self.policy,
            "runner_contract": self.runner,
            "builder_request": self.builder,
            "preflight": self.preflight,
            "patch_validation": self.patch,
            "content_attestation": self.attestation,
            "pinning_spec": self.pinning,
            "environment_contract": self.environment,
        }
        payload.update(overrides)
        return build_os_sandbox_contract(**payload)

    def _assert_physical_flags_false(self, document):
        for field in _PHYSICAL_FLAGS:
            self.assertIs(document[field], False, field)
        self.assertNotEqual(document["state"], "READY_FOR_EXECUTION")
        self.assertEqual(list(document["physical_proof_blockers"]), list(PHYSICAL_PROOF_BLOCKERS))

    def test_policy_without_provenance_is_rejected(self):
        withheld = build_command_policy_contract(self.runner)
        self.assertIs(withheld["upstream_provenance_structurally_verified"], False)
        with self.assertRaises(ValueError):
            self._build(command_policy=withheld)

    def test_structural_false_is_rejected(self):
        mutated = deepcopy(self.policy)
        mutated["upstream_provenance_structurally_verified"] = False
        mutated["upstream_provenance_binding_id"] = ""
        mutated["state"] = "BLOCKED"
        mutated["blockers"] = ["UPSTREAM_PROVENANCE_REQUIRED"]
        _bind_command_policy_ids(mutated)
        with self.assertRaises(ValueError):
            self._build(command_policy=mutated)

    def test_independent_provenance_true_is_rejected(self):
        mutated = deepcopy(self.policy)
        mutated["upstream_provenance_independently_verified"] = True
        _bind_command_policy_ids(mutated)
        with self.assertRaises(ValueError):
            self._build(command_policy=mutated)

    def test_fake_executable_pinning_verified_is_rejected(self):
        with self.assertRaises(ValueError):
            self._build(executable_pinning_verified=True)
        mutated = deepcopy(self.contract)
        mutated["executable_pinning_verified"] = True
        _bind_os_sandbox_ids(mutated)
        with self.assertRaises(ValueError):
            assert_os_sandbox_contract_integrity(mutated)

    def test_path_lookup_enabled_is_blocked(self):
        environment = build_environment_contract(path_lookup_allowed=True)
        out = self._build(environment_contract=environment)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PATH_LOOKUP_NOT_ALLOWED", out["blockers"])
        self.assertIs(out["path_lookup_allowed"], False)
        self._assert_physical_flags_false(out)

    def test_parent_environment_inheritance_is_blocked(self):
        environment = build_environment_contract(inherit_parent_environment=True)
        out = self._build(environment_contract=environment)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PARENT_ENVIRONMENT_INHERITANCE_NOT_ALLOWED", out["blockers"])
        self.assertIs(out["parent_environment_inheritance"], False)

    def test_caller_environment_override_is_blocked(self):
        environment = build_environment_contract(caller_environment={"CUSTOM": "1"})
        out = self._build(environment_contract=environment)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("CALLER_ENVIRONMENT_OVERRIDES_NOT_ALLOWED", out["blockers"])
        self.assertIs(out["caller_environment_overrides_allowed"], False)

    def test_secrets_mounted_is_rejected(self):
        preflight = deepcopy(self.preflight)
        preflight["environment_contract"] = dict(preflight["environment_contract"])
        preflight["environment_contract"]["secrets_mounted"] = True
        with self.assertRaises(ValueError):
            self._build(preflight=preflight)

    def test_network_allowed_is_rejected(self):
        with self.assertRaises(ValueError):
            self._build(network_allowed=True)
        mutated = deepcopy(self.contract)
        mutated["network_allowed"] = True
        _bind_os_sandbox_ids(mutated)
        with self.assertRaises(ValueError):
            assert_os_sandbox_contract_integrity(mutated)

    def test_shell_allowed_is_rejected(self):
        with self.assertRaises(ValueError):
            self._build(shell_allowed=True)
        mutated = deepcopy(self.contract)
        mutated["shell_allowed"] = True
        _bind_os_sandbox_ids(mutated)
        with self.assertRaises(ValueError):
            assert_os_sandbox_contract_integrity(mutated)

    def test_repo_write_allowed_is_rejected(self):
        with self.assertRaises(ValueError):
            self._build(repo_write_allowed=True)
        mutated = deepcopy(self.contract)
        mutated["repo_write_allowed"] = True
        _bind_os_sandbox_ids(mutated)
        with self.assertRaises(ValueError):
            assert_os_sandbox_contract_integrity(mutated)

    def test_child_process_allowed_is_rejected(self):
        with self.assertRaises(ValueError):
            self._build(arbitrary_process_spawn_allowed=True)
        mutated = deepcopy(self.contract)
        mutated["child_process_policy"] = "ALLOW"
        _bind_os_sandbox_ids(mutated)
        with self.assertRaises(ValueError):
            assert_os_sandbox_contract_integrity(mutated)

    def test_fake_symlink_verification_is_rejected(self):
        with self.assertRaises(ValueError):
            self._build(symlink_physical_boundary_verified=True)
        mutated = deepcopy(self.contract)
        mutated["symlink_physical_boundary_verified"] = True
        _bind_os_sandbox_ids(mutated)
        with self.assertRaises(ValueError):
            assert_os_sandbox_contract_integrity(mutated)

    def test_fake_hardlink_verification_is_rejected(self):
        with self.assertRaises(ValueError):
            self._build(hardlink_physical_boundary_verified=True)

    def test_fake_os_sandbox_verified_is_rejected(self):
        with self.assertRaises(ValueError):
            self._build(os_sandbox_verified=True)

    def test_fake_resource_limits_verified_is_rejected(self):
        with self.assertRaises(ValueError):
            self._build(resource_limits_verified=True)

    def test_fake_filesystem_isolation_is_rejected(self):
        with self.assertRaises(ValueError):
            self._build(filesystem_isolation_verified=True)

    def test_fake_network_isolation_is_rejected(self):
        with self.assertRaises(ValueError):
            self._build(network_isolation_verified=True)

    def test_fake_platform_adapter_verified_is_rejected(self):
        with self.assertRaises(ValueError):
            self._build(platform_adapter_verified=True)
        mutated = deepcopy(self.contract)
        mutated["platform_adapter"] = "LINUX"
        mutated["platform_adapter_verified"] = True
        _bind_os_sandbox_ids(mutated)
        with self.assertRaises(ValueError):
            assert_os_sandbox_contract_integrity(mutated)

    def test_blocked_to_ready_with_stale_id_is_rejected(self):
        environment = build_environment_contract(path_lookup_allowed=True)
        blocked = self._build(environment_contract=environment)
        self.assertEqual(blocked["state"], "BLOCKED")
        promoted = deepcopy(blocked)
        promoted["state"] = READY_STATE
        promoted["blockers"] = []
        self.assertEqual(promoted["os_sandbox_contract_id"], blocked["os_sandbox_contract_id"])
        with self.assertRaises(ValueError):
            assert_os_sandbox_contract_integrity(promoted)

    def test_blocked_to_ready_reseal_is_rejected_by_reconstruction(self):
        environment = build_environment_contract(path_lookup_allowed=True)
        blocked = self._build(environment_contract=environment)
        promoted = deepcopy(blocked)
        promoted["state"] = READY_STATE
        promoted["blockers"] = []
        _bind_os_sandbox_ids(promoted)
        self.assertNotEqual(promoted["os_sandbox_contract_id"], blocked["os_sandbox_contract_id"])
        with self.assertRaises(ValueError):
            assert_os_sandbox_contract(
                promoted,
                self.policy,
                self.runner,
                self.builder,
                self.preflight,
                self.patch,
                self.attestation,
                self.pinning,
                environment,
            )
        state, blockers = expected_os_sandbox_state_and_blockers(
            self.policy,
            self.runner,
            self.builder,
            self.preflight,
            self.patch,
            self.attestation,
            self.pinning,
            environment,
        )
        self.assertEqual(state, "BLOCKED")
        self.assertIn("PATH_LOOKUP_NOT_ALLOWED", blockers)

    def test_swapped_environment_is_rejected(self):
        other = build_environment_contract(path_lookup_allowed=True)
        with self.assertRaises(ValueError):
            assert_os_sandbox_contract(
                self.contract,
                self.policy,
                self.runner,
                self.builder,
                self.preflight,
                self.patch,
                self.attestation,
                self.pinning,
                other,
            )

    def test_swapped_pinning_spec_is_rejected(self):
        other = build_executable_pinning_spec(_pins("ef" * 32))
        self.assertNotEqual(other["pinning_spec_id"], self.pinning["pinning_spec_id"])
        with self.assertRaises(ValueError):
            assert_os_sandbox_contract(
                self.contract,
                self.policy,
                self.runner,
                self.builder,
                self.preflight,
                self.patch,
                self.attestation,
                other,
                self.environment,
            )

    def test_runner_policy_bundle_swap_is_rejected(self):
        other = deepcopy(_builder())
        other["lineage"] = dict(other["lineage"])
        other["lineage"]["snapshot_digest"] = "REPO-OTHER"
        other = bind_builder_request_lineage(other)
        preflight = _preflight(other)
        patch = _patch(other, preflight)
        attestation = attestation_for_documents(other, preflight, patch)
        runner = build_runner_contract(
            other,
            preflight,
            patch,
            content_attestation=attestation,
            human_patch_reviewed=True,
            human_patch_reviewer="reviewer-1",
            human_patch_review_refs=["review:patch:1"],
        )
        policy = build_command_policy_contract(
            runner,
            builder_request=other,
            preflight=preflight,
            patch_validation=patch,
            content_attestation=attestation,
        )
        with self.assertRaises(ValueError):
            assert_os_sandbox_contract(
                self.contract,
                policy,
                runner,
                other,
                preflight,
                patch,
                attestation,
                self.pinning,
                self.environment,
            )

    def test_extra_authority_field_is_rejected(self):
        mutated = deepcopy(self.contract)
        mutated["sandbox_escape_allowed"] = True
        with self.assertRaises(ValueError):
            assert_os_sandbox_contract_integrity(mutated)
        mutated["execution_authorized"] = True
        _bind_os_sandbox_ids(mutated)
        with self.assertRaises(ValueError):
            assert_os_sandbox_contract_integrity(mutated)

    def test_legitimate_design_chain_passes_with_physical_flags_false(self):
        again = self._build()
        self.assertEqual(again["os_sandbox_contract_id"], self.contract["os_sandbox_contract_id"])
        self.assertEqual(self.contract["state"], READY_STATE)
        self.assertEqual(self.contract["blockers"], [])
        self.assertEqual(self.contract["child_process_policy"], "DENY_BY_DEFAULT")
        self.assertEqual(self.contract["network_default"], "DENY")
        self.assertEqual(self.contract["source_tree_mode"], "READ_ONLY")
        self.assertIs(self.contract["repository_root_bound"], True)
        self.assertEqual(self.contract["platform_adapter"], "UNRESOLVED")
        self.assertEqual(self.contract["supported_future_adapters"], ["LINUX", "WINDOWS"])
        self.assertEqual(self.contract["resource_budget"], self.policy["resource_budget"])
        self.assertEqual(self.contract["output_bound_field"], "output_bytes")
        self.assertIs(self.contract["stdout_captured"], True)
        self.assertIs(self.contract["stderr_captured"], True)
        self.assertIs(self.contract["truncation_hides_security_status"], False)
        self.assertEqual(
            list(self.contract["required_before_future_execution"]),
            list(REQUIRED_BEFORE_FUTURE_EXECUTION),
        )
        self.assertEqual(
            list(self.contract["future_resource_probe_fields"]),
            list(FUTURE_RESOURCE_PROBE_FIELDS),
        )
        self.assertIs(self.contract["separate_stdout_stderr_budgets_defined"], False)
        self.assertIs(self.contract["disk_write_budget_defined"], False)
        for name in FUTURE_RESOURCE_PROBE_FIELDS:
            self.assertNotIn(name, self.contract["resource_budget"])
        self.assertEqual(self.contract["executable_path_model"], "POSIX_PINNING_CONTRACT")
        self.assertEqual(self.contract["windows_physical_path_support"], "FUTURE_WORK")
        self.assertIn("MITIGATE_TOCTOU_BETWEEN_CHECK_AND_USE", self.contract["toctou_requirements"])
        self.assertIn("REJECT_WINDOWS_REPARSE_POINT_ESCAPE", self.contract["toctou_requirements"])
        self.assertIn("NO_HARDLINK_CREATION", self.contract["filesystem_requirements"])
        self._assert_physical_flags_false(self.contract)
        assert_os_sandbox_contract_integrity(self.contract)
        assert_os_sandbox_contract(
            self.contract,
            self.policy,
            self.runner,
            self.builder,
            self.preflight,
            self.patch,
            self.attestation,
            self.pinning,
            self.environment,
        )
        self.assertIs(self.contract["sandbox_contract_is_data_only"], True)
        hazards = " ".join(self.contract["hazards"]).lower()
        self.assertNotIn("subprocess", hazards)
        self.assertIn("sandbox", hazards)

    def _review(self, **overrides):
        payload = {
            "command_policy": self.policy,
            "pinning_spec": self.pinning,
            "attestation": self.attestation,
            "environment_contract": self.environment,
            "runner_contract": self.runner,
            "builder_request": self.builder,
            "preflight": self.preflight,
            "patch_validation": self.patch,
        }
        payload.update(overrides)
        return build_os_sandbox_design_review(**payload)

    def test_design_review_follows_the_canonical_contract(self):
        review = self._review()
        self.assertEqual(review["state"], "READY_FOR_OS_SANDBOX_DESIGN_REVIEW")
        self.assertEqual(review["canonical_os_sandbox_state"], self.contract["state"])
        self.assertEqual(review["canonical_os_sandbox_contract_id"], self.contract["os_sandbox_contract_id"])
        self.assertEqual(review["canonical_schema"], self.contract["schema"])
        self.assertIs(review["os_sandbox_verified"], False)
        self.assertIs(review["platform_adapter_verified"], False)
        environment = build_environment_contract(path_lookup_allowed=True)
        blocked = self._build(environment_contract=environment)
        review_blocked = self._review(environment_contract=environment)
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertEqual(review_blocked["state"], "BLOCKED")
        self.assertEqual(review_blocked["canonical_os_sandbox_state"], blocked["state"])
        self.assertNotEqual(review["state"], review["canonical_os_sandbox_state"])

    def test_pinning_absolute_path_stale_id_is_rejected(self):
        mutated = deepcopy(self.pinning)
        mutated["pins"] = deepcopy(mutated["pins"])
        mutated["pins"][0]["absolute_path"] = "/usr/local/bin/python3"
        self.assertEqual(mutated["pinning_spec_id"], self.pinning["pinning_spec_id"])
        with self.assertRaises(ValueError):
            assert_executable_pinning_spec_integrity(mutated)
        with self.assertRaises(ValueError):
            self._build(pinning_spec=mutated)

    def test_pinning_sha256_stale_id_is_rejected(self):
        mutated = deepcopy(self.pinning)
        mutated["pins"] = deepcopy(mutated["pins"])
        mutated["pins"][1]["sha256"] = "ef" * 32
        self.assertEqual(mutated["pinning_spec_id"], self.pinning["pinning_spec_id"])
        with self.assertRaises(ValueError):
            assert_executable_pinning_spec_integrity(mutated)

    def test_pinning_state_change_is_rejected(self):
        mutated = deepcopy(self.pinning)
        mutated["state"] = "BLOCKED"
        with self.assertRaises(ValueError):
            assert_executable_pinning_spec_integrity(mutated)
        mutated["pinning_spec_id"] = expected_pinning_spec_id(mutated)
        with self.assertRaises(ValueError):
            assert_executable_pinning_spec_integrity(mutated)

    def test_pinning_complete_change_is_rejected(self):
        mutated = deepcopy(self.pinning)
        mutated["pinning_spec_complete"] = False
        with self.assertRaises(ValueError):
            assert_executable_pinning_spec_integrity(mutated)
        mutated["pinning_spec_id"] = expected_pinning_spec_id(mutated)
        with self.assertRaises(ValueError):
            assert_executable_pinning_spec_integrity(mutated)

    def test_git_config_count_injection_is_rejected(self):
        environment = build_environment_contract(caller_environment={"GIT_CONFIG_COUNT": "1"})
        self.assertEqual(environment["state"], "BLOCKED")
        self.assertIn("INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED", environment["blockers"])
        self.assertIn("git_config_count", environment["rejected_environment_keys"])
        out = self._build(environment_contract=environment)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED", out["blockers"])
        forged = deepcopy(environment)
        forged["state"] = "ENVIRONMENT_DECLARED"
        forged["blockers"] = []
        still = self._build(environment_contract=forged)
        self.assertEqual(still["state"], "BLOCKED")
        self.assertIn("INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED", still["blockers"])
        policy = build_command_policy_contract(
            self.runner,
            requested_environment={"GIT_CONFIG_COUNT": "1"},
        )
        self.assertIn("INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED", policy["blockers"])

    def test_git_config_key_and_value_injection_is_rejected(self):
        for key in (
            "GIT_CONFIG_KEY_0",
            "GIT_CONFIG_VALUE_0",
            "GIT_CONFIG_GLOBAL",
            "GIT_CONFIG_SYSTEM",
        ):
            environment = build_environment_contract(caller_environment={key: "x"})
            self.assertIn("INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED", environment["blockers"], key)
            self.assertIn(key.casefold(), environment["rejected_environment_keys"], key)

    def test_unknown_authority_fields_are_rejected(self):
        for field in (
            "safe",
            "trusted",
            "sandbox_verified",
            "execution_ready",
            "allow_spawn",
            "allow_network",
            "allow_write",
        ):
            mutated = deepcopy(self.contract)
            mutated[field] = True
            with self.assertRaises(ValueError):
                assert_os_sandbox_contract_integrity(mutated)

    def test_windows_support_is_not_claimed_as_verified(self):
        self.assertEqual(self.contract["platform_adapter"], "UNRESOLVED")
        self.assertIs(self.contract["platform_adapter_verified"], False)
        self.assertEqual(self.contract["windows_physical_path_support"], "FUTURE_WORK")
        mutated = deepcopy(self.contract)
        mutated["platform_adapter"] = "WINDOWS"
        mutated["platform_adapter_verified"] = True
        _bind_os_sandbox_ids(mutated)
        with self.assertRaises(ValueError):
            assert_os_sandbox_contract_integrity(mutated)
        with self.assertRaises(ValueError):
            require_absolute_path(r"C:\Python\python.exe")
        with self.assertRaises(ValueError):
            require_absolute_path("//server/share/python.exe")

    def test_pinning_unknown_authority_fields_are_rejected(self):
        for field in (
            "safe",
            "trusted",
            "execution_ready",
            "allow_spawn",
            "allow_network",
            "allow_write",
            "sandbox_verified",
            "ready_for_execution",
        ):
            mutated = deepcopy(self.pinning)
            mutated[field] = True
            self.assertEqual(mutated["pinning_spec_id"], self.pinning["pinning_spec_id"])
            with self.assertRaises(ValueError):
                assert_executable_pinning_spec_integrity(mutated)
            with self.assertRaises(ValueError):
                self._build(pinning_spec=mutated)

    def test_environment_unknown_authority_fields_are_rejected(self):
        for field in (
            "safe",
            "trusted",
            "execution_ready",
            "allow_spawn",
            "allow_network",
            "allow_write",
        ):
            mutated = deepcopy(self.environment)
            mutated[field] = True
            with self.assertRaises(ValueError):
                assert_environment_contract_integrity(mutated)
            with self.assertRaises(ValueError):
                self._build(environment_contract=mutated)

    def test_canonical_pinning_and_environment_pass_closed_schema(self):
        self.assertEqual(
            assert_executable_pinning_spec_integrity(self.pinning),
            self.pinning["pinning_spec_id"],
        )
        self.assertEqual(assert_environment_contract_integrity(self.environment), [])
        self.assertEqual(self.pinning["state"], "READY_FOR_EXECUTABLE_PINNING_PROBE")
        self.assertIs(self.pinning["pinning_spec_complete"], True)
        self.assertEqual(self.environment["state"], "ENVIRONMENT_DECLARED")
        self.assertEqual(self.environment["blockers"], [])

    def test_git_config_prefix_variants_stay_blocked(self):
        for key in (
            "GIT_CONFIG_COUNT",
            "Git_Config_Count",
            "GIT_CONFIG_KEY_0",
            "GIT_CONFIG_VALUE_0",
            "git_config_evil",
            "GIT_CONFIG_GLOBAL",
            "GIT_CONFIG_SYSTEM",
        ):
            environment = build_environment_contract(caller_environment={key: "1"})
            self.assertEqual(environment["state"], "BLOCKED", key)
            self.assertIn("INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED", environment["blockers"], key)
            self.assertIn(key.casefold(), environment["rejected_environment_keys"], key)
            derived = assert_environment_contract_integrity(environment)
            self.assertIn("INHERITED_ENVIRONMENT_KEY_NOT_ALLOWED", derived, key)
            out = self._build(environment_contract=environment)
            self.assertEqual(out["state"], "BLOCKED", key)

    def test_hazards_stay_outside_the_authority_digest(self):
        mutated = deepcopy(self.contract)
        mutated["hazards"] = ["informational commentary only"]
        assert_os_sandbox_contract_integrity(mutated)
        self.assertEqual(mutated["os_sandbox_contract_id"], self.contract["os_sandbox_contract_id"])
        self.assertNotIn("hazards", os_sandbox_manifest(mutated))

    def test_closed_schemas_keep_probe_design_ready_and_flags_false(self):
        assert_executable_pinning_spec_integrity(self.pinning)
        self.assertEqual(assert_environment_contract_integrity(self.environment), [])
        self.assertEqual(self.contract["state"], READY_STATE)
        self._assert_physical_flags_false(self.contract)
        review = self._review()
        self.assertEqual(review["state"], "READY_FOR_OS_SANDBOX_DESIGN_REVIEW")
        self.assertEqual(review["canonical_os_sandbox_state"], READY_STATE)
        self.assertNotEqual(review["state"], "READY_FOR_EXECUTION")
