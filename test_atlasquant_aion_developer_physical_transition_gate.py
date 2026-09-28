"""Physical transition gate. Design READY does not release physical operation.

The gate replays the transient patch and still returns PHYSICAL_TRANSITION_BLOCKED.
It does not execute, apply, merge, deploy or trade.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from atlasquant_aion_developer_builder_sandbox import structural_builder_sandbox_request
from atlasquant_aion_developer_command_policy import build_command_policy_contract
from atlasquant_aion_developer_content_attestation import attestation_for_documents
from atlasquant_aion_developer_executable_pinning import (
    build_environment_contract,
    build_executable_pinning_spec,
)
from atlasquant_aion_developer_os_sandbox_contract import build_os_sandbox_contract
from atlasquant_aion_developer_os_sandbox_probe_result import build_probe_result_contract
from atlasquant_aion_developer_patch_validation import (
    expected_patch_validation_id,
    validate_patch,
)
from atlasquant_aion_developer_physical_transition_gate import (
    EXTERNAL_PROVENANCE_MISSING,
    PHYSICAL_TRANSITION_BLOCKED,
    SOURCE_BOUND_READY,
    STRUCTURAL_READY,
    assert_physical_transition_record,
    evaluate_physical_transition_gate,
    expected_physical_transition_id,
)
from atlasquant_aion_developer_runner_contract import build_runner_contract
from atlasquant_aion_developer_sandbox_preflight import build_sandbox_preflight
from atlasquant_aion_developer_source_bound_consumption_gate import (
    assert_source_bound_consumption_gate,
)
from atlasquant_aion_developer_source_bound_patch_proof import verify_source_bound_patch
from test_atlasquant_aion_developer_attestation_pinning import _pin


def _builder(branch="cursor/safe", baseline="main@a", candidate="cursor/safe@b"):
    return structural_builder_sandbox_request(
        branch=branch,
        baseline_ref=baseline,
        candidate_ref=candidate,
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


def _safe_patch():
    return (
        "diff --git a/module.py b/module.py\n"
        "--- a/module.py\n+++ b/module.py\n"
        "@@ -1 +1 @@\n-x=1\n+x=2 # PHYSICAL_GATE_MARKER\n"
    )


def _other_ready_patch():
    return (
        "diff --git a/module.py b/module.py\n"
        "--- a/module.py\n+++ b/module.py\n"
        "@@ -1 +1 @@\n-x=1\n+x=3\n"
    )


def _chain(branch="cursor/safe", baseline="main@a", candidate="cursor/safe@b", raw=None):
    builder = _builder(branch, baseline, candidate)
    preflight = _preflight(builder)
    patch_text = _safe_patch() if raw is None else raw
    sealed = validate_patch(
        builder,
        preflight,
        patch_text,
        baseline_ref=baseline,
        candidate_ref=candidate,
    )
    attestation = attestation_for_documents(builder, preflight, sealed)
    review = dict(
        human_patch_reviewed=True,
        human_patch_reviewer="reviewer-1",
        human_patch_review_refs=["review:patch:1"],
    )
    runner = build_runner_contract(
        builder, preflight, sealed, content_attestation=attestation, **review,
    )
    policy = build_command_policy_contract(
        runner,
        builder_request=builder,
        preflight=preflight,
        patch_validation=sealed,
        content_attestation=attestation,
    )
    pinning = build_executable_pinning_spec([
        _pin("python", "/usr/bin/python3", "ab" * 32),
        _pin("git", "/usr/bin/git", "cd" * 32),
    ])
    environment = build_environment_contract()
    sandbox = build_os_sandbox_contract(
        policy, runner, builder, preflight, sealed,
        attestation, pinning, environment,
    )
    probe = build_probe_result_contract(
        sandbox, policy, runner, builder, preflight, sealed,
        attestation, pinning, environment,
    )
    return {
        "builder_request": builder,
        "preflight": preflight,
        "patch_validation": sealed,
        "runner_contract": runner,
        "command_policy": policy,
        "pinning_spec": pinning,
        "environment_contract": environment,
        "os_sandbox_contract": sandbox,
        "probe_result": probe,
        "patch_text": patch_text,
        "baseline_ref": baseline,
        "candidate_ref": candidate,
        "content_attestation": attestation,
    }


class PhysicalTransitionGateTests(unittest.TestCase):
    def setUp(self):
        self.chain = _chain()

    def _eval(self, **overrides):
        payload = dict(self.chain)
        payload.update(overrides)
        return evaluate_physical_transition_gate(**payload)

    def test_design_ready_without_receipt_stays_blocked(self):
        with self.assertRaisesRegex(ValueError, "design READY does not release physical transition"):
            self._eval(patch_text=None)
        with self.assertRaisesRegex(ValueError, "design READY does not release physical transition"):
            self._eval(patch_text=None, consumption_receipt=None)

    def test_stored_proof_is_not_a_receipt(self):
        proof = verify_source_bound_patch(
            self.chain["builder_request"],
            self.chain["preflight"],
            self.chain["patch_validation"],
            self.chain["patch_text"],
            baseline_ref=self.chain["baseline_ref"],
            candidate_ref=self.chain["candidate_ref"],
        )
        with self.assertRaisesRegex(ValueError, "stored source-bound proof is not a consumption receipt"):
            self._eval(consumption_receipt=proof)
        with self.assertRaisesRegex(ValueError, "stored source-bound proof is not a consumption receipt"):
            self._eval(patch_text=None, consumption_receipt=proof)

    def test_stale_receipt_is_blocked(self):
        receipt = assert_source_bound_consumption_gate(
            self.chain["builder_request"],
            self.chain["preflight"],
            self.chain["patch_validation"],
            self.chain["patch_text"],
            baseline_ref=self.chain["baseline_ref"],
            candidate_ref=self.chain["candidate_ref"],
        )
        stale = deepcopy(receipt)
        stale["consumption_id"] = "DEVSRCGATE-STALE"
        with self.assertRaisesRegex(ValueError, "stale consumption receipt"):
            self._eval(consumption_receipt=stale)

    def test_receipt_of_another_patch_is_blocked(self):
        raw = _other_ready_patch()
        sealed = validate_patch(
            self.chain["builder_request"],
            self.chain["preflight"],
            raw,
            baseline_ref=self.chain["baseline_ref"],
            candidate_ref=self.chain["candidate_ref"],
        )
        other_receipt = assert_source_bound_consumption_gate(
            self.chain["builder_request"],
            self.chain["preflight"],
            sealed,
            raw,
            baseline_ref=self.chain["baseline_ref"],
            candidate_ref=self.chain["candidate_ref"],
        )
        with self.assertRaisesRegex(ValueError, "does not match the transient patch"):
            self._eval(consumption_receipt=other_receipt)

    def test_swapped_lineage_is_blocked(self):
        forged = deepcopy(self.chain["patch_validation"])
        forged["builder_request_id"] = "DEVBUILD-OTHERLINEAGE"
        forged["validation_id"] = expected_patch_validation_id(forged)
        with self.assertRaisesRegex(ValueError, "lineage mismatch"):
            self._eval(patch_validation=forged)

    def test_swapped_refs_are_blocked(self):
        with self.assertRaisesRegex(ValueError, "revision refs differ"):
            self._eval(candidate_ref="cursor/other@b")

    def test_swapped_patch_digest_is_blocked(self):
        forged = deepcopy(self.chain["patch_validation"])
        forged["patch_digest"] = "DEVPATCH-SWAPPEDDIGEST"
        forged["validation_id"] = expected_patch_validation_id(forged)
        with self.assertRaisesRegex(ValueError, "mismatch"):
            self._eval(patch_validation=forged)

    def test_other_chain_runner_policy_os_is_blocked(self):
        other = _chain(branch="cursor/other", baseline="main@c", candidate="cursor/other@d")
        with self.assertRaises(ValueError):
            self._eval(
                runner_contract=other["runner_contract"],
                command_policy=other["command_policy"],
                os_sandbox_contract=other["os_sandbox_contract"],
            )

    def test_caller_cannot_claim_independent_verification(self):
        with self.assertRaisesRegex(ValueError, "independent external verification cannot be claimed"):
            self._eval(independent_external_verification=True)

    def test_caller_cannot_authorize_physical_execution(self):
        with self.assertRaisesRegex(ValueError, "physical execution cannot be authorized"):
            self._eval(physical_execution_authorized=True)

    def test_recomputed_id_cannot_promote_the_record(self):
        decision = self._eval()
        forged = deepcopy(decision)
        forged["state"] = "PHYSICAL_TRANSITION_READY"
        forged["transition_id"] = expected_physical_transition_id(forged)
        with self.assertRaisesRegex(ValueError, "physical transition remains blocked"):
            assert_physical_transition_record(forged)
        claimed = deepcopy(decision)
        claimed["independent_external_verification"] = True
        claimed["transition_id"] = expected_physical_transition_id(claimed)
        with self.assertRaisesRegex(ValueError, "independent external verification cannot be claimed"):
            assert_physical_transition_record(claimed)
        authorized = deepcopy(decision)
        authorized["physical_execution_authorized"] = True
        authorized["transition_id"] = expected_physical_transition_id(authorized)
        with self.assertRaisesRegex(ValueError, "physical execution cannot be authorized"):
            assert_physical_transition_record(authorized)

    def test_unknown_authority_field_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "not authority"):
            self._eval(git_object_verified=True)

    def test_missing_dependency_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "physical transition dependency is missing: runner_contract"):
            self._eval(runner_contract=None)
        with self.assertRaisesRegex(ValueError, "physical transition dependency is missing: content_attestation"):
            self._eval(content_attestation=None)

    def test_caller_cannot_promote_blocked_to_ready(self):
        with self.assertRaisesRegex(ValueError, "physical transition remains blocked"):
            self._eval(state="PHYSICAL_TRANSITION_READY")
        with self.assertRaisesRegex(ValueError, "physical transition remains blocked"):
            self._eval(state="READY")

    def test_matching_chain_stays_blocked_and_distinguishes_readiness(self):
        receipt = assert_source_bound_consumption_gate(
            self.chain["builder_request"],
            self.chain["preflight"],
            self.chain["patch_validation"],
            self.chain["patch_text"],
            baseline_ref=self.chain["baseline_ref"],
            candidate_ref=self.chain["candidate_ref"],
        )
        decision = self._eval(consumption_receipt=receipt)
        bare = self._eval()
        self.assertEqual(decision, bare)
        self.assertEqual(decision["state"], PHYSICAL_TRANSITION_BLOCKED)
        self.assertEqual(decision["structural_readiness"], STRUCTURAL_READY)
        self.assertEqual(decision["source_bound_readiness"], SOURCE_BOUND_READY)
        self.assertEqual(decision["external_provenance"], EXTERNAL_PROVENANCE_MISSING)
        self.assertEqual(decision["transition_id"], expected_physical_transition_id(decision))
        self.assertEqual(assert_physical_transition_record(decision), decision["transition_id"])
        self.assertIs(decision["independent_external_verification"], False)
        self.assertIs(decision["physical_execution_authorized"], False)
        self.assertIs(decision["physical_transition_remains_blocked"], True)
        self.assertIs(decision["design_ready_releases_physical_transition"], False)
        self.assertIs(decision["stored_proof_releases_physical_transition"], False)
        self.assertIs(decision["stored_receipt_releases_physical_transition"], False)
        self.assertIs(decision["caller_can_promote_state"], False)
        self.assertIs(decision["consumption_replay_performed"], True)
        self.assertIs(decision["patch_text_included"], False)
        self.assertIs(decision["execution_authorized"], False)
        self.assertIs(decision["patch_applied"], False)
        self.assertIs(decision["subprocess_called"], False)
        self.assertIs(decision["shell_authorized"], False)
        self.assertIs(decision["filesystem_write_authorized"], False)
        self.assertIs(decision["network_called"], False)
        self.assertIs(decision["git_mutation_authorized"], False)
        self.assertIs(decision["automatic_merge"], False)
        self.assertIs(decision["automatic_deploy"], False)
        self.assertIs(decision["real_trading_enabled"], False)
        self.assertEqual(decision["validation_id"], self.chain["patch_validation"]["validation_id"])
        self.assertEqual(decision["patch_digest"], self.chain["patch_validation"]["patch_digest"])
        self.assertEqual(decision["runner_contract_id"], self.chain["runner_contract"]["runner_contract_id"])
        self.assertEqual(decision["command_policy_id"], self.chain["command_policy"]["command_policy_id"])
        self.assertEqual(decision["os_sandbox_contract_id"], self.chain["os_sandbox_contract"]["os_sandbox_contract_id"])
        self.assertEqual(decision["probe_result_id"], self.chain["probe_result"]["probe_result_id"])
        self.assertEqual(decision["consumption_id"], receipt["consumption_id"])
        rendered = json.dumps(decision)
        self.assertNotIn(self.chain["patch_text"], rendered)
        self.assertNotIn("PHYSICAL_GATE_MARKER", rendered)
        self.assertNotIn("diff --git", rendered)
        self.assertEqual(self.chain["runner_contract"]["state"], "READY_FOR_RUNNER_DESIGN_REVIEW")
        self.assertEqual(self.chain["probe_result"]["state"], "READY_FOR_PHYSICAL_PROBE_IMPLEMENTATION_REVIEW")
        for document in (
            self.chain["patch_validation"],
            self.chain["runner_contract"],
            self.chain["command_policy"],
            self.chain["os_sandbox_contract"],
            self.chain["probe_result"],
        ):
            for field in (
                "execution_authorized",
                "subprocess_called",
                "automatic_merge",
                "automatic_deploy",
                "real_trading_enabled",
            ):
                if field in document:
                    self.assertIs(document[field], False, field)

    def test_gate_module_imports_no_execution_primitives(self):
        text = Path("atlasquant_aion_developer_physical_transition_gate.py").read_text(encoding="utf-8")
        self.assertNotIn("import subprocess", text)
        self.assertNotIn("import os", text)
        self.assertNotIn("import socket", text)
        self.assertNotIn("Popen", text)
        self.assertNotIn("os.system", text)
        self.assertNotIn("shell=True", text)
        for name in (
            "atlasquant_aion_developer_runner_contract.py",
            "atlasquant_aion_developer_command_policy.py",
            "atlasquant_aion_developer_os_sandbox_contract.py",
            "atlasquant_aion_developer_os_sandbox_probe_result.py",
        ):
            source = Path(name).read_text(encoding="utf-8")
            self.assertNotIn("physical_transition_gate", source)


if __name__ == "__main__":
    unittest.main()
