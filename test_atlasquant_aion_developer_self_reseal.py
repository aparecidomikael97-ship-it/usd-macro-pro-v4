"""A recomputed digest is not a trust boundary.

STALE_ID mutates a document and keeps the previous id. SELF_RESEAL mutates
the document and recomputes the id so the digest matches the new bytes.
Consumers reject the second attack unless the payload is the canonical
contract the constructor would emit. These tests do not execute commands.
"""
from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_developer_command_policy import (
    _bind_command_policy_ids,
    assert_command_policy_integrity,
    assert_runner_policy_boundary,
    build_command_policy_contract,
    expected_command_policy_id,
    expected_command_policy_payload,
)
from atlasquant_aion_developer_content_attestation import attestation_for_documents
from atlasquant_aion_developer_executable_pinning import FIXED_ENVIRONMENT
from atlasquant_aion_developer_runner_contract import (
    _bind_runner_contract_ids,
    assert_runner_contract_integrity,
    build_runner_contract,
)
from test_atlasquant_aion_developer_attestation_pinning import (
    _builder,
    _patch,
    _preflight,
)


def _reseal_policy(policy):
    _bind_command_policy_ids(policy)
    return policy


class SelfResealBoundaryTests(unittest.TestCase):
    def setUp(self):
        builder = _builder()
        preflight = _preflight(builder)
        patch = _patch(builder, preflight)
        attestation = attestation_for_documents(builder, preflight, patch)
        self.builder = builder
        self.preflight = preflight
        self.patch = patch
        self.attestation = attestation
        self.runner = build_runner_contract(
            builder,
            preflight,
            patch,
            content_attestation=attestation,
            human_patch_reviewed=True,
            human_patch_reviewer="reviewer-1",
            human_patch_review_refs=["review:patch:1"],
        )
        self.policy = build_command_policy_contract(self.runner, **self._upstream())
        self.assertEqual(self.runner["state"], "READY_FOR_RUNNER_DESIGN_REVIEW")
        self.assertEqual(self.policy["state"], "READY_FOR_EXECUTABLE_PINNING_REVIEW")
        self.assertFalse(self.policy["execution_authorized"])
        self.assertIs(self.policy["upstream_provenance_structurally_verified"], True)
        self.assertIs(self.policy["upstream_provenance_independently_verified"], False)

    def _upstream(self):
        return {
            "builder_request": self.builder,
            "preflight": self.preflight,
            "patch_validation": self.patch,
            "content_attestation": self.attestation,
        }

    def _reject_resealed_policy(self, mutate):
        mutated = deepcopy(self.policy)
        mutate(mutated)
        self.assertEqual(mutated["command_policy_id"], self.policy["command_policy_id"])
        _reseal_policy(mutated)
        self.assertNotEqual(mutated["command_policy_id"], self.policy["command_policy_id"])
        self.assertEqual(mutated["command_policy_id"], expected_command_policy_id(mutated))
        with self.assertRaises(ValueError):
            assert_command_policy_integrity(mutated)
        with self.assertRaises(ValueError):
            assert_runner_policy_boundary(self.runner, mutated)

    def test_arbitrary_argv_with_new_id_is_rejected(self):
        def mutate(policy):
            policy["validated_command_plan"][0]["argv"] = ["-c", "ARBITRARY"]
        self._reject_resealed_policy(mutate)

    def test_executable_change_with_new_id_is_rejected(self):
        def mutate(policy):
            policy["validated_command_plan"][0]["executable"] = "/tmp/python"
        self._reject_resealed_policy(mutate)

    def test_cwd_change_with_new_id_is_rejected(self):
        def mutate(policy):
            policy["validated_command_plan"][2]["cwd"] = "/tmp"
        self._reject_resealed_policy(mutate)

    def test_runtime_out_of_range_with_new_id_is_rejected(self):
        def mutate(policy):
            policy["resource_budget"]["runtime_seconds"] = 999999
        self._reject_resealed_policy(mutate)

    def test_runtime_string_with_new_id_is_rejected(self):
        def mutate(policy):
            policy["resource_budget"]["runtime_seconds"] = "900"
        self._reject_resealed_policy(mutate)

    def test_invalid_memory_with_new_id_is_rejected(self):
        def mutate(policy):
            policy["resource_budget"]["memory_mb"] = 999999
        self._reject_resealed_policy(mutate)

    def test_pythonpath_injection_with_new_id_is_rejected(self):
        def mutate(policy):
            policy["fixed_environment"] = dict(policy["fixed_environment"])
            policy["allowlist_policy"] = dict(policy["allowlist_policy"])
            policy["allowlist_policy"]["fixed_environment"] = dict(FIXED_ENVIRONMENT)
            policy["fixed_environment"]["PYTHONPATH"] = "/evil"
            policy["allowlist_policy"]["fixed_environment"]["PYTHONPATH"] = "/evil"
        self._reject_resealed_policy(mutate)

    def test_pythonhashseed_change_with_new_id_is_rejected(self):
        def mutate(policy):
            policy["fixed_environment"] = dict(policy["fixed_environment"])
            policy["allowlist_policy"] = dict(policy["allowlist_policy"])
            policy["allowlist_policy"]["fixed_environment"] = dict(FIXED_ENVIRONMENT)
            policy["fixed_environment"]["PYTHONHASHSEED"] = "123"
            policy["allowlist_policy"]["fixed_environment"]["PYTHONHASHSEED"] = "123"
        self._reject_resealed_policy(mutate)

    def test_divergent_environment_copies_with_new_id_are_rejected(self):
        def mutate(policy):
            policy["fixed_environment"] = dict(FIXED_ENVIRONMENT)
            policy["allowlist_policy"] = dict(policy["allowlist_policy"])
            policy["allowlist_policy"]["fixed_environment"] = dict(FIXED_ENVIRONMENT)
            policy["allowlist_policy"]["fixed_environment"]["PYTHONHASHSEED"] = "123"
        self._reject_resealed_policy(mutate)

    def test_shell_allowed_with_new_id_is_rejected(self):
        def mutate(policy):
            policy["allowlist_policy"] = dict(policy["allowlist_policy"])
            policy["allowlist_policy"]["shell_allowed"] = True
        self._reject_resealed_policy(mutate)

    def test_resealed_runner_argv_cannot_cross_policy_boundary(self):
        mutated_runner = deepcopy(self.runner)
        mutated_runner["command_plan"][0]["argv"] = ["-c", "ARBITRARY"]
        _bind_runner_contract_ids(mutated_runner)
        self.assertNotEqual(
            mutated_runner["runner_contract_id"],
            self.runner["runner_contract_id"],
        )
        with self.assertRaises(ValueError):
            assert_runner_contract_integrity(mutated_runner)
        with self.assertRaises(ValueError):
            assert_runner_policy_boundary(mutated_runner, self.policy)
        followed = deepcopy(self.policy)
        followed["runner_contract_id"] = mutated_runner["runner_contract_id"]
        followed["runner_contract_manifest_id"] = mutated_runner["runner_contract_manifest_id"]
        followed["resource_budget"] = dict(mutated_runner["resource_budget"])
        followed["validated_command_plan"] = deepcopy(mutated_runner["command_plan"])
        _reseal_policy(followed)
        with self.assertRaises(ValueError):
            assert_runner_policy_boundary(mutated_runner, followed)

    def test_resealed_runner_budget_rejects_the_old_policy(self):
        mutated_runner = deepcopy(self.runner)
        mutated_runner["resource_budget"]["runtime_seconds"] = 600
        _bind_runner_contract_ids(mutated_runner)
        rebuilt = build_command_policy_contract(mutated_runner)
        self.assertEqual(rebuilt["state"], "BLOCKED")
        self.assertIn("UPSTREAM_PROVENANCE_REQUIRED", rebuilt["blockers"])
        self.assertIs(rebuilt["upstream_provenance_structurally_verified"], False)
        with self.assertRaises(ValueError):
            build_command_policy_contract(mutated_runner, **self._upstream())
        with self.assertRaises(ValueError):
            assert_runner_policy_boundary(mutated_runner, self.policy, **self._upstream())

    def test_joint_reseal_of_runner_and_policy_is_rejected(self):
        mutated_runner = deepcopy(self.runner)
        mutated_runner["command_plan"][1]["argv"] = ["-c", "ARBITRARY"]
        mutated_runner["resource_budget"]["runtime_seconds"] = 600
        _bind_runner_contract_ids(mutated_runner)
        followed = deepcopy(self.policy)
        followed["runner_contract_id"] = mutated_runner["runner_contract_id"]
        followed["runner_contract_manifest_id"] = mutated_runner["runner_contract_manifest_id"]
        followed["resource_budget"] = dict(mutated_runner["resource_budget"])
        followed["validated_command_plan"] = deepcopy(mutated_runner["command_plan"])
        _reseal_policy(followed)
        self.assertNotEqual(followed["command_policy_id"], self.policy["command_policy_id"])
        self.assertNotEqual(
            mutated_runner["runner_contract_id"],
            self.runner["runner_contract_id"],
        )
        with self.assertRaises(ValueError):
            assert_runner_policy_boundary(mutated_runner, followed)

    def test_individually_valid_budgets_must_still_match(self):
        mutated = deepcopy(self.policy)
        mutated["resource_budget"]["runtime_seconds"] = 600
        _reseal_policy(mutated)
        assert_command_policy_integrity(mutated)
        with self.assertRaises(ValueError):
            assert_runner_policy_boundary(self.runner, mutated)

    def test_plan_must_match_the_runner_canonical_template(self):
        mutated = deepcopy(self.policy)
        mutated["validated_command_plan"][2]["argv"] = ["diff", "--check", "--exit-code"]
        _reseal_policy(mutated)
        expected = expected_command_policy_payload(self.runner)
        self.assertNotEqual(
            mutated["validated_command_plan"],
            expected["validated_command_plan"],
        )
        with self.assertRaises(ValueError):
            assert_command_policy_integrity(mutated)
        with self.assertRaises(ValueError):
            assert_runner_policy_boundary(self.runner, mutated)

    def test_deepcopy_nested_mutation_with_new_id_is_rejected(self):
        def mutate(policy):
            policy["validated_command_plan"] = deepcopy(policy["validated_command_plan"])
            policy["validated_command_plan"][0]["argv"] = list(
                policy["validated_command_plan"][0]["argv"]
            )
            policy["validated_command_plan"][0]["argv"][-1] = "<MUTATED_SCOPE>"
            policy["fixed_environment"] = dict(policy["fixed_environment"])
            policy["allowlist_policy"] = dict(policy["allowlist_policy"])
            policy["allowlist_policy"]["fixed_environment"] = dict(FIXED_ENVIRONMENT)
            policy["fixed_environment"]["PYTHONHASHSEED"] = "123"
            policy["allowlist_policy"]["fixed_environment"]["PYTHONHASHSEED"] = "123"
        self._reject_resealed_policy(mutate)

    def test_authority_flag_with_new_id_is_rejected(self):
        def mutate(policy):
            policy["execution_authorized"] = True
        self._reject_resealed_policy(mutate)

    def test_relaxed_security_flag_with_new_id_is_rejected(self):
        def mutate(policy):
            policy["path_lookup_allowed"] = True
            policy["os_sandbox_verified"] = True
        self._reject_resealed_policy(mutate)

    def test_extra_environment_key_with_new_id_is_rejected(self):
        def mutate(policy):
            policy["fixed_environment"] = dict(FIXED_ENVIRONMENT)
            policy["allowlist_policy"] = dict(policy["allowlist_policy"])
            policy["allowlist_policy"]["fixed_environment"] = dict(FIXED_ENVIRONMENT)
            policy["fixed_environment"]["LC_ALL"] = "C"
            policy["allowlist_policy"]["fixed_environment"]["LC_ALL"] = "C"
        self._reject_resealed_policy(mutate)

    def test_constructor_document_still_passes(self):
        expected = expected_command_policy_payload(self.runner, **self._upstream())
        assert_command_policy_integrity(self.policy)
        assert_runner_policy_boundary(self.runner, self.policy, **self._upstream())
        assert_runner_contract_integrity(self.runner)
        self.assertEqual(self.policy["resource_budget"], self.runner["resource_budget"])
        self.assertEqual(self.policy["validated_command_plan"], expected["validated_command_plan"])
        self.assertEqual(self.policy["fixed_environment"], dict(FIXED_ENVIRONMENT))
        self.assertEqual(
            self.policy["allowlist_policy"]["fixed_environment"],
            dict(FIXED_ENVIRONMENT),
        )
        self.assertEqual(self.policy["runner_contract_id"], self.runner["runner_contract_id"])
        self.assertFalse(self.policy["execution_authorized"])
        self.assertFalse(self.policy["subprocess_called"])
        self.assertFalse(self.policy["os_sandbox_verified"])
        self.assertEqual(self.policy["state"], "READY_FOR_EXECUTABLE_PINNING_REVIEW")


if __name__ == "__main__":
    unittest.main()
