"""Command-policy readiness requires structural upstream provenance.

A locally canonical runner can still be sealed. That seal does not make a
command policy ready. Structural provenance means the supplied documents
agree. It does not establish an independent root of trust. These tests do
not execute commands.
"""
from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_developer_command_policy import (
    _bind_command_policy_ids,
    assert_command_policy_integrity,
    assert_command_policy_provenance,
    build_command_policy_contract,
)
from atlasquant_aion_developer_content_attestation import attestation_for_documents
from atlasquant_aion_developer_executable_pinning import (
    build_environment_contract,
    build_executable_pinning_spec,
    build_os_sandbox_design_review,
)
from atlasquant_aion_developer_manifest import bind_builder_request_lineage
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


def _pins():
    return [
        _pin("python", "/usr/bin/python3", "ab" * 32),
        _pin("git", "/usr/bin/git", "cd" * 32),
    ]


def _alternate_builder():
    document = deepcopy(_builder())
    document["lineage"] = dict(document["lineage"])
    document["lineage"]["snapshot_digest"] = "REPO-OTHER"
    return bind_builder_request_lineage(document)


class PolicyProvenanceBoundaryTests(unittest.TestCase):
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
        self.policy = build_command_policy_contract(self.runner, **self._upstream())

    def _upstream(self, builder=None, preflight=None, patch=None, attestation=None):
        return {
            "builder_request": self.builder if builder is None else builder,
            "preflight": self.preflight if preflight is None else preflight,
            "patch_validation": self.patch if patch is None else patch,
            "content_attestation": self.attestation if attestation is None else attestation,
        }

    def _other_bundle(self):
        builder = _alternate_builder()
        preflight = _preflight(builder)
        patch = _patch(builder, preflight)
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
            **self._upstream(builder, preflight, patch, attestation),
        )
        return builder, preflight, patch, attestation, runner, policy

    def test_policy_without_upstream_is_not_ready(self):
        withheld = build_command_policy_contract(self.runner)
        self.assertEqual(withheld["state"], "BLOCKED")
        self.assertIn("UPSTREAM_PROVENANCE_REQUIRED", withheld["blockers"])
        self.assertIs(withheld["upstream_provenance_structurally_verified"], False)
        self.assertIs(withheld["upstream_provenance_independently_verified"], False)
        self.assertEqual(withheld["upstream_provenance_binding_id"], "")
        self.assertNotEqual(withheld["state"], "READY_FOR_EXECUTABLE_PINNING_REVIEW")

    def test_policy_with_legitimate_upstream_is_ready(self):
        self.assertEqual(self.policy["state"], "READY_FOR_EXECUTABLE_PINNING_REVIEW")
        self.assertEqual(self.policy["blockers"], [])
        self.assertIs(self.policy["upstream_provenance_structurally_verified"], True)
        self.assertIs(self.policy["upstream_provenance_independently_verified"], False)
        self.assertTrue(self.policy["upstream_provenance_binding_id"].startswith("DEVPROV-"))
        self.assertEqual(
            self.policy["validated_command_plan"][0]["pycache_prefix"],
            "<SANDBOX_EPHEMERAL_PYCACHE>",
        )
        self.assertFalse(self.policy["execution_authorized"])

    def test_caller_structural_flag_without_upstream_is_rejected(self):
        with self.assertRaises(ValueError):
            build_command_policy_contract(
                self.runner,
                upstream_provenance_structurally_verified=True,
            )

    def test_independent_verification_true_is_rejected(self):
        mutated = deepcopy(self.policy)
        mutated["upstream_provenance_independently_verified"] = True
        _bind_command_policy_ids(mutated)
        with self.assertRaises(ValueError):
            assert_command_policy_integrity(mutated)
        with self.assertRaises(ValueError):
            build_command_policy_contract(
                self.runner,
                **self._upstream(),
                upstream_provenance_independently_verified=True,
            )

    def test_false_lineage_with_original_upstream_is_rejected(self):
        mutated = deepcopy(self.runner)
        mutated["lineage"]["builder_request_id"] = "DEVBUILD-OTHERREQUEST1"
        _bind_runner_contract_ids(mutated)
        self.assertNotEqual(mutated["runner_contract_id"], self.runner["runner_contract_id"])
        with self.assertRaises(ValueError):
            build_command_policy_contract(mutated, **self._upstream())

    def test_legitimate_runner_with_different_upstream_is_rejected(self):
        builder, preflight, patch, attestation, _runner, _policy = self._other_bundle()
        with self.assertRaises(ValueError):
            build_command_policy_contract(
                self.runner,
                **self._upstream(builder, preflight, patch, attestation),
            )

    def test_policy_from_bundle_a_rejects_bundle_b(self):
        builder, preflight, patch, attestation, runner, _policy = self._other_bundle()
        with self.assertRaises(ValueError):
            assert_command_policy_provenance(
                self.policy,
                runner,
                builder,
                preflight,
                patch,
                attestation,
            )

    def test_resealed_structural_claim_without_reconstruction_is_rejected(self):
        mutated = deepcopy(self.policy)
        mutated["upstream_provenance_binding_id"] = "DEVPROV-" + ("A" * 18)
        _bind_command_policy_ids(mutated)
        self.assertNotEqual(mutated["command_policy_id"], self.policy["command_policy_id"])
        with self.assertRaises(ValueError):
            assert_command_policy_provenance(
                mutated,
                self.runner,
                self.builder,
                self.preflight,
                self.patch,
                self.attestation,
            )

    def test_ready_state_with_provenance_blocker_is_rejected(self):
        withheld = build_command_policy_contract(self.runner)
        mutated = deepcopy(withheld)
        mutated["state"] = "READY_FOR_EXECUTABLE_PINNING_REVIEW"
        mutated["validated_command_plan"] = deepcopy(self.policy["validated_command_plan"])
        _bind_command_policy_ids(mutated)
        with self.assertRaises(ValueError):
            assert_command_policy_integrity(mutated)

    def test_removed_provenance_blocker_reseal_is_rejected(self):
        withheld = build_command_policy_contract(self.runner)
        mutated = deepcopy(withheld)
        mutated["state"] = "READY_FOR_EXECUTABLE_PINNING_REVIEW"
        mutated["blockers"] = []
        mutated["upstream_provenance_structurally_verified"] = True
        mutated["upstream_provenance_binding_id"] = "DEVPROV-" + ("B" * 18)
        mutated["validated_command_plan"] = deepcopy(self.policy["validated_command_plan"])
        _bind_command_policy_ids(mutated)
        with self.assertRaises(ValueError):
            assert_command_policy_provenance(
                mutated,
                self.runner,
                self.builder,
                self.preflight,
                self.patch,
                self.attestation,
            )

    def test_legitimate_upstream_runner_policy_chain_passes(self):
        assert_command_policy_provenance(
            self.policy,
            self.runner,
            self.builder,
            self.preflight,
            self.patch,
            self.attestation,
        )
        self.assertEqual(self.policy["state"], "READY_FOR_EXECUTABLE_PINNING_REVIEW")
        self.assertEqual(self.runner["state"], "READY_FOR_RUNNER_DESIGN_REVIEW")
        self.assertEqual(self.policy["blockers"], [])
        self.assertEqual(self.runner["blockers"], [])

    def test_os_sandbox_design_bundle_still_passes(self):
        review = build_os_sandbox_design_review(
            self.policy,
            build_executable_pinning_spec(_pins()),
            self.attestation,
            build_environment_contract(),
            runner_contract=self.runner,
            builder_request=self.builder,
            preflight=self.preflight,
            patch_validation=self.patch,
        )
        self.assertEqual(review["state"], "READY_FOR_OS_SANDBOX_DESIGN_REVIEW")
        self.assertFalse(review["execution_authorized"])
        self.assertFalse(review["os_sandbox_verified"])
        self.assertIs(self.policy["upstream_provenance_structurally_verified"], True)
        self.assertIs(self.policy["upstream_provenance_independently_verified"], False)

    def test_structural_true_and_independent_false_is_the_ready_claim(self):
        self.assertIs(self.policy["upstream_provenance_structurally_verified"], True)
        self.assertIs(self.policy["upstream_provenance_independently_verified"], False)
        self.assertEqual(self.policy["state"], "READY_FOR_EXECUTABLE_PINNING_REVIEW")

    def test_structural_false_is_never_ready(self):
        withheld = build_command_policy_contract(self.runner)
        self.assertIs(withheld["upstream_provenance_structurally_verified"], False)
        self.assertNotEqual(withheld["state"], "READY_FOR_EXECUTABLE_PINNING_REVIEW")
        mutated = deepcopy(self.policy)
        mutated["upstream_provenance_structurally_verified"] = False
        mutated["upstream_provenance_binding_id"] = ""
        _bind_command_policy_ids(mutated)
        with self.assertRaises(ValueError):
            assert_command_policy_integrity(mutated)

    def test_consistent_bundle_is_structural_and_not_independent(self):
        _builder_b, _preflight_b, _patch_b, _attestation_b, runner, policy = self._other_bundle()
        self.assertEqual(policy["state"], "READY_FOR_EXECUTABLE_PINNING_REVIEW")
        self.assertIs(policy["upstream_provenance_structurally_verified"], True)
        self.assertIs(policy["upstream_provenance_independently_verified"], False)
        self.assertEqual(runner["state"], "READY_FOR_RUNNER_DESIGN_REVIEW")
        self.assertFalse(policy["execution_authorized"])
        self.assertFalse(policy["real_trading_enabled"])
        self.assertFalse(policy["subprocess_called"])


if __name__ == "__main__":
    unittest.main()
