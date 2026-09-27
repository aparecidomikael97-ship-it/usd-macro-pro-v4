"""Upstream provenance and blocked-to-ready promotion.

A runner id matches the bytes it was computed from. It does not prove that
those bytes were derived from the builder request, preflight, patch
validation or content attestation. Review display is a label. These tests
do not execute commands.
"""
from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_developer_command_policy import (
    _bind_command_policy_ids,
    assert_command_policy_integrity,
    assert_runner_policy_boundary,
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
    assert_runner_contract_integrity,
    assert_runner_provenance,
    build_runner_contract,
    expected_runner_contract_id,
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


class UpstreamProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.builder = _builder()
        self.preflight = _preflight(self.builder)
        self.patch = _patch(self.builder, self.preflight)
        self.attestation = attestation_for_documents(self.builder, self.preflight, self.patch)
        self.runner = self._runner()
        self.policy = build_command_policy_contract(self.runner)
        self.assertEqual(self.runner["state"], "READY_FOR_RUNNER_DESIGN_REVIEW")
        self.assertEqual(self.runner["blockers"], [])
        self.assertEqual(self.policy["state"], "READY_FOR_EXECUTABLE_PINNING_REVIEW")
        self.assertEqual(self.policy["blockers"], [])
        self.assertEqual(
            self.runner["review"]["human_patch_reviewer_principal_id"],
            "prn_reviewer1",
        )

    def _runner(self, **overrides):
        args = {
            "content_attestation": self.attestation,
            "human_patch_reviewed": True,
            "human_patch_reviewer": "reviewer-1",
            "human_patch_review_refs": ["review:patch:1"],
        }
        args.update(overrides)
        return build_runner_contract(self.builder, self.preflight, self.patch, **args)

    def _provenance(self, runner, patch=None, attestation=None):
        assert_runner_provenance(
            runner,
            self.builder,
            self.preflight,
            self.patch if patch is None else patch,
            self.attestation if attestation is None else attestation,
        )

    def _promote(self, runner):
        promoted = deepcopy(runner)
        promoted["state"] = "READY_FOR_RUNNER_DESIGN_REVIEW"
        promoted["blockers"] = []
        return promoted

    def test_blocked_review_keeps_old_id_and_is_rejected(self):
        blocked = self._runner(human_patch_reviewed=False)
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn("HUMAN_PATCH_REVIEW_REQUIRED", blocked["blockers"])
        promoted = self._promote(blocked)
        self.assertEqual(promoted["runner_contract_id"], blocked["runner_contract_id"])
        with self.assertRaises(ValueError):
            assert_runner_contract_integrity(promoted)
        with self.assertRaises(ValueError):
            self._provenance(promoted)

    def test_blocked_review_reseal_is_rejected(self):
        blocked = self._runner(human_patch_reviewed=False)
        promoted = self._promote(blocked)
        _bind_runner_contract_ids(promoted)
        self.assertNotEqual(promoted["runner_contract_id"], blocked["runner_contract_id"])
        self.assertEqual(promoted["runner_contract_id"], expected_runner_contract_id(promoted))
        with self.assertRaises(ValueError):
            assert_runner_contract_integrity(promoted)
        with self.assertRaises(ValueError):
            self._provenance(promoted)

    def test_missing_review_refs_cannot_become_ready(self):
        promoted = deepcopy(self.runner)
        promoted["review"]["human_patch_review_refs"] = []
        promoted["state"] = "READY_FOR_RUNNER_DESIGN_REVIEW"
        promoted["blockers"] = []
        _bind_runner_contract_ids(promoted)
        with self.assertRaises(ValueError):
            assert_runner_contract_integrity(promoted)
        with self.assertRaises(ValueError):
            self._provenance(promoted)

    def test_unverified_revision_cannot_become_ready(self):
        patch = deepcopy(self.patch)
        patch["revision_binding"] = dict(patch["revision_binding"])
        patch["revision_binding"]["revision_content_verified"] = False
        attestation = attestation_for_documents(self.builder, self.preflight, patch)
        blocked = build_runner_contract(
            self.builder,
            self.preflight,
            patch,
            content_attestation=attestation,
            human_patch_reviewed=True,
            human_patch_reviewer="reviewer-1",
            human_patch_review_refs=["review:patch:1"],
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn("PATCH_VALIDATOR_CONTENT_BINDING_NOT_VERIFIED", blocked["blockers"])
        stale = self._promote(blocked)
        with self.assertRaises(ValueError):
            assert_runner_contract_integrity(stale)
        promoted = self._promote(blocked)
        _bind_runner_contract_ids(promoted)
        with self.assertRaises(ValueError):
            assert_runner_provenance(
                promoted, self.builder, self.preflight, patch, attestation,
            )

    def test_missing_targets_cannot_become_ready(self):
        promoted = deepcopy(self.runner)
        promoted["tests"]["targets"] = []
        promoted["state"] = "READY_FOR_RUNNER_DESIGN_REVIEW"
        promoted["blockers"] = []
        _bind_runner_contract_ids(promoted)
        with self.assertRaises(ValueError):
            assert_runner_contract_integrity(promoted)
        with self.assertRaises(ValueError):
            self._provenance(promoted)

    def _reject_lineage(self, field, value):
        mutated = deepcopy(self.runner)
        mutated["lineage"][field] = value
        _bind_runner_contract_ids(mutated)
        self.assertNotEqual(mutated["runner_contract_id"], self.runner["runner_contract_id"])
        with self.assertRaises(ValueError):
            self._provenance(mutated)

    def test_builder_request_id_reseal_is_rejected(self):
        self._reject_lineage("builder_request_id", "DEVBUILD-OTHERREQUEST1")

    def test_preflight_id_reseal_is_rejected(self):
        self._reject_lineage("preflight_id", "DEVPREF-OTHERREQUEST01")

    def test_patch_validation_id_reseal_is_rejected(self):
        self._reject_lineage("patch_validation_id", "DEVPATCHVAL-OTHER")

    def test_patch_digest_reseal_is_rejected(self):
        self._reject_lineage("patch_digest", "DEVPATCH-OTHER")

    def test_attestation_id_reseal_is_rejected(self):
        self._reject_lineage("content_attestation_id", "DEVATT-" + ("A" * 18))

    def test_different_valid_targets_are_rejected(self):
        mutated = deepcopy(self.runner)
        mutated["tests"]["targets"] = ["test_module.py::extra"]
        _bind_runner_contract_ids(mutated)
        with self.assertRaises(ValueError):
            self._provenance(mutated)

    def test_removed_target_is_rejected(self):
        mutated = deepcopy(self.runner)
        mutated["tests"]["targets"] = []
        mutated["blockers"] = []
        mutated["state"] = "READY_FOR_RUNNER_DESIGN_REVIEW"
        _bind_runner_contract_ids(mutated)
        with self.assertRaises(ValueError):
            self._provenance(mutated)

    def test_unapproved_target_is_rejected(self):
        mutated = deepcopy(self.runner)
        mutated["tests"]["targets"] = list(self.runner["tests"]["targets"]) + ["test_other.py"]
        _bind_runner_contract_ids(mutated)
        with self.assertRaises(ValueError):
            self._provenance(mutated)

    def test_different_gates_are_rejected(self):
        mutated = deepcopy(self.runner)
        mutated["tests"]["mandatory_gates"] = list(REQUIRED_MANDATORY_GATES) + ["EXTRA_GATE"]
        _bind_runner_contract_ids(mutated)
        with self.assertRaises(ValueError):
            self._provenance(mutated)

    def test_reviewer_display_does_not_change_identity(self):
        mutated = deepcopy(self.runner)
        mutated["review"]["human_patch_reviewer"] = "other-reviewer"
        self.assertEqual(expected_runner_contract_id(mutated), self.runner["runner_contract_id"])
        self.assertEqual(
            mutated["review"]["human_patch_reviewer_principal_id"],
            "prn_reviewer1",
        )
        assert_runner_contract_integrity(mutated)
        self._provenance(mutated)

    def test_other_reviewer_principal_is_rejected(self):
        mutated = deepcopy(self.runner)
        mutated["review"]["human_patch_reviewer_principal_id"] = "prn_otherrev1"
        _bind_runner_contract_ids(mutated)
        assert_runner_contract_integrity(mutated)
        with self.assertRaises(ValueError):
            self._provenance(mutated)

    def test_reviewed_false_reseal_is_rejected(self):
        mutated = deepcopy(self.runner)
        mutated["review"]["human_patch_reviewed"] = False
        mutated["state"] = "READY_FOR_RUNNER_DESIGN_REVIEW"
        mutated["blockers"] = []
        _bind_runner_contract_ids(mutated)
        with self.assertRaises(ValueError):
            assert_runner_contract_integrity(mutated)
        with self.assertRaises(ValueError):
            self._provenance(mutated)

    def test_review_refs_removed_or_stale_are_rejected(self):
        removed = deepcopy(self.runner)
        removed["review"]["human_patch_review_refs"] = []
        removed["state"] = "READY_FOR_RUNNER_DESIGN_REVIEW"
        removed["blockers"] = []
        _bind_runner_contract_ids(removed)
        with self.assertRaises(ValueError):
            self._provenance(removed)
        swapped = deepcopy(self.runner)
        swapped["review"]["human_patch_review_refs"] = ["review:other"]
        self.assertEqual(swapped["runner_contract_id"], self.runner["runner_contract_id"])
        with self.assertRaises(ValueError):
            assert_runner_contract_integrity(swapped)

    def test_promoted_blocked_policy_is_rejected(self):
        bad = deepcopy(self.runner)
        bad["command_plan"][0]["argv"] = ["-c", "ARBITRARY"]
        _bind_runner_contract_ids(bad)
        blocked = build_command_policy_contract(bad)
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertTrue(blocked["blockers"])
        promoted = deepcopy(blocked)
        promoted["state"] = "READY_FOR_EXECUTABLE_PINNING_REVIEW"
        promoted["blockers"] = []
        promoted["validated_command_plan"] = deepcopy(self.policy["validated_command_plan"])
        _bind_command_policy_ids(promoted)
        self.assertNotEqual(promoted["command_policy_id"], blocked["command_policy_id"])
        with self.assertRaises(ValueError):
            assert_runner_policy_boundary(bad, promoted)
        with self.assertRaises(ValueError):
            self._provenance(bad)

    def test_ready_policy_with_blockers_is_rejected(self):
        mutated = deepcopy(self.policy)
        mutated["blockers"] = ["PATH_LOOKUP_NOT_ALLOWED"]
        _bind_command_policy_ids(mutated)
        self.assertEqual(mutated["state"], "READY_FOR_EXECUTABLE_PINNING_REVIEW")
        with self.assertRaises(ValueError):
            assert_command_policy_integrity(mutated)
        with self.assertRaises(ValueError):
            assert_runner_policy_boundary(self.runner, mutated)

    def test_joint_reseal_with_original_upstream_is_rejected(self):
        mutated = deepcopy(self.runner)
        mutated["tests"]["targets"] = ["test_other.py"]
        _bind_runner_contract_ids(mutated)
        followed = deepcopy(self.policy)
        followed["runner_contract_id"] = mutated["runner_contract_id"]
        followed["runner_contract_manifest_id"] = mutated["runner_contract_manifest_id"]
        _bind_command_policy_ids(followed)
        self.assertNotEqual(mutated["runner_contract_id"], self.runner["runner_contract_id"])
        self.assertNotEqual(followed["command_policy_id"], self.policy["command_policy_id"])
        with self.assertRaises(ValueError):
            self._provenance(mutated)
        with self.assertRaises(ValueError):
            build_os_sandbox_design_review(
                followed,
                build_executable_pinning_spec(_pins()),
                self.attestation,
                build_environment_contract(),
                runner_contract=mutated,
                builder_request=self.builder,
                preflight=self.preflight,
                patch_validation=self.patch,
            )

    def test_legitimate_upstream_chain_passes(self):
        assert_runner_contract_integrity(self.runner)
        self._provenance(self.runner)
        assert_runner_policy_boundary(self.runner, self.policy)
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
        self.assertEqual(self.runner["tests"]["targets"], ["test_module.py"])
        self.assertEqual(self.runner["tests"]["mandatory_gates"], list(REQUIRED_MANDATORY_GATES))
        self.assertEqual(self.runner["resource_budget"], self.preflight["resource_budget"])
        self.assertEqual(self.policy["blockers"], [])
        self.assertEqual(self.runner["blockers"], [])


if __name__ == "__main__":
    unittest.main()
