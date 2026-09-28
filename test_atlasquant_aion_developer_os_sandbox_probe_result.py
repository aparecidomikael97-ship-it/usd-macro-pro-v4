"""The probe result contract describes a future measurement. It does not run one."""
from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_developer_command_policy import build_command_policy_contract
from atlasquant_aion_developer_content_attestation import attestation_for_documents
from atlasquant_aion_developer_executable_pinning import (
    build_environment_contract,
    build_executable_pinning_spec,
    build_os_sandbox_design_review,
)
from atlasquant_aion_developer_manifest import bind_builder_request_lineage
from atlasquant_aion_developer_os_sandbox_contract import (
    PHYSICAL_PROOF_BLOCKERS,
    READY_STATE as SANDBOX_READY_STATE,
    REQUIRED_BEFORE_FUTURE_EXECUTION,
    build_os_sandbox_contract,
)
from atlasquant_aion_developer_os_sandbox_probe_result import (
    NEXT_IMPLEMENTATION_STEP,
    READY_STATE,
    _bind_probe_result_ids,
    assert_probe_result,
    assert_probe_result_integrity,
    build_probe_result_contract,
    derived_probe_requirements,
    expected_probe_result_state_and_blockers,
    probe_result_manifest,
    reconstruct_physical_coverage,
)
from atlasquant_aion_developer_runner_contract import build_runner_contract
from test_atlasquant_aion_developer_attestation_pinning import (
    _builder,
    _patch,
    _pin,
    _preflight,
)


_PHYSICAL_FLAGS = (
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
    "filesystem_isolation_verified",
    "network_isolation_verified",
    "resource_limits_verified",
    "environment_isolation_verified",
    "output_limits_verified",
    "symlink_physical_boundary_verified",
    "hardlink_physical_boundary_verified",
    "platform_adapter_verified",
    "platform_verified",
    "physical_probe_executed",
    "physical_probe_passed",
    "physical_proof_verified",
    "independently_verified",
)


def _pins(python_digest="ab" * 32):
    return [
        _pin("python", "/usr/bin/python3", python_digest),
        _pin("git", "/usr/bin/git", "cd" * 32),
    ]


class OsSandboxProbeResultContractTests(unittest.TestCase):
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
        self.sandbox = build_os_sandbox_contract(
            self.policy,
            self.runner,
            self.builder,
            self.preflight,
            self.patch,
            self.attestation,
            self.pinning,
            self.environment,
        )
        self.result = self._build()

    def _build(self, **overrides):
        payload = {
            "os_sandbox_contract": self.sandbox,
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
        return build_probe_result_contract(**payload)

    def _assert_chain(self, result, **overrides):
        payload = {
            "result": result,
            "os_sandbox_contract": self.sandbox,
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
        result = payload.pop("result")
        assert_probe_result(result, **payload)

    def _flags_false(self, document):
        for field in _PHYSICAL_FLAGS:
            self.assertIs(document[field], False, field)
        for measurement in document["measurements"]:
            self.assertIs(measurement["verified"], False)
            self.assertIs(measurement["evidence"]["evidence_is_physical"], False)
            self.assertIs(measurement["evidence"]["independently_verified"], False)

    def test_legitimate_result_design_has_no_verified_measurement(self):
        again = self._build()
        self.assertEqual(again["probe_result_id"], self.result["probe_result_id"])
        self.assertEqual(self.result["state"], READY_STATE)
        self.assertEqual(self.result["blockers"], [])
        derived = reconstruct_physical_coverage(self.result["measurements"])
        self.assertEqual(self.result["coverage"]["required_verified"], 0)
        self.assertEqual(derived["required_verified"], 0)
        self.assertEqual(self.result["coverage"]["missing"], list(derived_probe_requirements()))
        self.assertEqual(self.result["missing_requirements"], derived["missing"])
        self.assertEqual(self.result["physical_proof_satisfied"], [])
        self.assertEqual(derived["physical_proof_satisfied"], [])
        self.assertEqual(self.result["platform"], "UNRESOLVED")
        self.assertIs(self.result["platform_verified"], False)
        self.assertIs(self.result["recheck_required_before_use"], True)
        self.assertEqual(self.result["measurements"][0]["failure_reason"], "PROBE_NOT_IMPLEMENTED")
        self.assertIs(self.result["measurements"][0]["verified"], False)
        self.assertEqual(self.result["measurements"][0]["window_validity"], "NO_MEASUREMENT_WINDOW")
        self.assertIs(self.result["measurements"][0]["recheck_required_before_use"], True)
        self.assertEqual(self.result["measurements"][0]["evidence"]["evidence_digest"], "")
        self.assertTrue(self.result["measurements"][0]["evidence"]["measurement_identity"].startswith("DEVPROBEV-"))
        self.assertEqual(
            list(derived_probe_requirements()),
            list(dict.fromkeys(tuple(PHYSICAL_PROOF_BLOCKERS) + tuple(REQUIRED_BEFORE_FUTURE_EXECUTION))),
        )
        self.assertIs(self.result["upstream_contract_structurally_verified"], True)
        self.assertIs(self.result["upstream_contract_independently_verified"], False)
        self.assertEqual(self.result["os_sandbox_contract_id"], self.sandbox["os_sandbox_contract_id"])
        self.assertEqual(self.result["next_implementation_step"], NEXT_IMPLEMENTATION_STEP)
        self.assertEqual(self.result["execution_context"], "NOT_EXECUTED")
        self.assertNotIn("timestamp", self.result)
        self._flags_false(self.result)
        assert_probe_result_integrity(self.result)
        self._assert_chain(self.result)
        review = build_os_sandbox_design_review(
            self.policy,
            self.pinning,
            self.attestation,
            self.environment,
            runner_contract=self.runner,
            builder_request=self.builder,
            preflight=self.preflight,
            patch_validation=self.patch,
        )
        self.assertEqual(review["canonical_os_sandbox_state"], SANDBOX_READY_STATE)
        self.assertEqual(self.sandbox["state"], SANDBOX_READY_STATE)

    def test_verified_true_is_rejected(self):
        with self.assertRaises(ValueError):
            self._build(verified=True)
        mutated = deepcopy(self.result)
        mutated["measurements"][0]["verified"] = True
        _bind_probe_result_ids(mutated)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(mutated)

    def test_physical_probe_passed_is_rejected(self):
        with self.assertRaises(ValueError):
            self._build(physical_probe_passed=True)
        mutated = deepcopy(self.result)
        mutated["physical_probe_passed"] = True
        _bind_probe_result_ids(mutated)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(mutated)

    def test_execution_authorized_is_rejected(self):
        with self.assertRaises(ValueError):
            self._build(execution_authorized=True)
        mutated = deepcopy(self.result)
        mutated["execution_authorized"] = True
        _bind_probe_result_ids(mutated)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(mutated)

    def test_ready_for_execution_is_rejected(self):
        mutated = deepcopy(self.result)
        mutated["state"] = "READY_FOR_EXECUTION"
        _bind_probe_result_ids(mutated)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(mutated)

    def test_platform_verified_is_rejected(self):
        with self.assertRaises(ValueError):
            self._build(platform_verified=True)
        mutated = deepcopy(self.result)
        mutated["platform_verified"] = True
        _bind_probe_result_ids(mutated)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(mutated)

    def test_independently_verified_is_rejected(self):
        with self.assertRaises(ValueError):
            self._build(independently_verified=True)
        mutated = deepcopy(self.result)
        mutated["independently_verified"] = True
        _bind_probe_result_ids(mutated)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(mutated)

    def test_unknown_top_level_authority_field_is_rejected(self):
        for field in (
            "safe",
            "trusted",
            "execution_ready",
            "probe_passed",
            "allow_execute",
            "allow_network",
            "allow_write",
            "allow_spawn",
        ):
            mutated = deepcopy(self.result)
            mutated[field] = True
            with self.assertRaises(ValueError):
                assert_probe_result_integrity(mutated)

    def test_unknown_measurement_field_is_rejected(self):
        mutated = deepcopy(self.result)
        mutated["measurements"][0]["safe"] = True
        _bind_probe_result_ids(mutated)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(mutated)

    def test_unknown_evidence_field_is_rejected(self):
        mutated = deepcopy(self.result)
        mutated["measurements"][0]["evidence"]["trusted"] = True
        _bind_probe_result_ids(mutated)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(mutated)

    def test_stale_sandbox_contract_id_is_rejected(self):
        mutated = deepcopy(self.result)
        mutated["os_sandbox_contract_id"] = "DEVOS-STALECONTRACT01"
        self.assertEqual(mutated["probe_result_id"], self.result["probe_result_id"])
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(mutated)

    def test_swapped_sandbox_chain_is_rejected(self):
        other = deepcopy(self.builder)
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
        sandbox = build_os_sandbox_contract(
            policy, runner, other, preflight, patch, attestation, self.pinning, self.environment,
        )
        self.assertNotEqual(sandbox["os_sandbox_contract_id"], self.sandbox["os_sandbox_contract_id"])
        with self.assertRaises(ValueError):
            self._assert_chain(
                self.result,
                os_sandbox_contract=sandbox,
                command_policy=policy,
                runner_contract=runner,
                builder_request=other,
                preflight=preflight,
                patch_validation=patch,
                content_attestation=attestation,
            )

    def test_manual_state_promotion_keeps_old_id_and_is_rejected(self):
        environment = build_environment_contract(path_lookup_allowed=True)
        sandbox = build_os_sandbox_contract(
            self.policy, self.runner, self.builder, self.preflight, self.patch,
            self.attestation, self.pinning, environment,
        )
        blocked = self._build(os_sandbox_contract=sandbox, environment_contract=environment)
        self.assertEqual(blocked["state"], "BLOCKED")
        promoted = deepcopy(blocked)
        promoted["state"] = READY_STATE
        promoted["blockers"] = []
        self.assertEqual(promoted["probe_result_id"], blocked["probe_result_id"])
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(promoted)

    def test_resealed_promotion_is_rejected_by_reconstruction(self):
        environment = build_environment_contract(path_lookup_allowed=True)
        sandbox = build_os_sandbox_contract(
            self.policy, self.runner, self.builder, self.preflight, self.patch,
            self.attestation, self.pinning, environment,
        )
        blocked = self._build(os_sandbox_contract=sandbox, environment_contract=environment)
        promoted = deepcopy(blocked)
        promoted["state"] = READY_STATE
        promoted["blockers"] = []
        _bind_probe_result_ids(promoted)
        self.assertNotEqual(promoted["probe_result_id"], blocked["probe_result_id"])
        assert_probe_result_integrity(promoted)
        with self.assertRaises(ValueError):
            assert_probe_result(
                promoted, sandbox, self.policy, self.runner, self.builder, self.preflight,
                self.patch, self.attestation, self.pinning, environment,
            )
        state, blockers = expected_probe_result_state_and_blockers(
            sandbox, self.policy, self.runner, self.builder, self.preflight,
            self.patch, self.attestation, self.pinning, environment,
        )
        self.assertEqual(state, "BLOCKED")
        self.assertEqual(blockers, ["OS_SANDBOX_PROBE_DESIGN_REQUIRED"])

    def test_missing_requirements_are_reflected_in_coverage(self):
        requirements = list(derived_probe_requirements())
        self.assertEqual(self.result["coverage"]["required_total"], len(requirements))
        self.assertEqual(self.result["coverage"]["required_verified"], 0)
        self.assertEqual(self.result["coverage"]["missing"], requirements)
        self.assertEqual(self.result["missing_requirements"], requirements)
        self.assertEqual(self.result["state"], READY_STATE)

    def test_forged_required_verified_is_rejected(self):
        mutated = deepcopy(self.result)
        mutated["coverage"]["required_verified"] = 1
        _bind_probe_result_ids(mutated)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(mutated)

    def test_forged_physical_proof_satisfied_is_rejected(self):
        mutated = deepcopy(self.result)
        mutated["physical_proof_satisfied"] = ["EXECUTABLE_PINNING_PROOF_REQUIRED"]
        _bind_probe_result_ids(mutated)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(mutated)

    def test_cleared_missing_list_is_rejected(self):
        mutated = deepcopy(self.result)
        mutated["coverage"]["missing"] = []
        mutated["missing_requirements"] = []
        _bind_probe_result_ids(mutated)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(mutated)

    def test_ambiguous_measurement_cannot_pass(self):
        mutated = deepcopy(self.result)
        mutated["measurements"][0]["observed_value"] = "AMBIGUOUS"
        _bind_probe_result_ids(mutated)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(mutated)
        passed = deepcopy(self.result)
        passed["measurements"][0]["observed_value"] = "PASS"
        passed["measurements"][0]["verified"] = True
        _bind_probe_result_ids(passed)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(passed)

    def test_unsupported_platform_cannot_become_verified(self):
        for platform in ("UNKNOWN", "OTHER", "UNSUPPORTED"):
            with self.assertRaises(ValueError):
                self._build(platform=platform)
        mutated = deepcopy(self.result)
        mutated["platform"] = "UNSUPPORTED"
        mutated["platform_verified"] = True
        _bind_probe_result_ids(mutated)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(mutated)
        declared = self._build(platform="LINUX")
        self.assertEqual(declared["platform"], "LINUX")
        self.assertIs(declared["platform_verified"], False)
        self.assertEqual(declared["state"], READY_STATE)

    def test_hazards_do_not_change_the_authority_id(self):
        mutated = deepcopy(self.result)
        mutated["hazards"] = ["informational commentary only"]
        assert_probe_result_integrity(mutated)
        self.assertEqual(mutated["probe_result_id"], self.result["probe_result_id"])
        self.assertNotIn("hazards", probe_result_manifest(mutated))

    def test_partial_inventory_cannot_be_promoted_to_the_ready_format(self):
        requirements = list(derived_probe_requirements())
        mutated = deepcopy(self.result)
        mutated["measurements"] = mutated["measurements"][:-1]
        mutated["sequence"] = [item["requirement"] for item in mutated["measurements"]]
        missing = list(requirements)
        mutated["coverage"]["missing"] = missing
        mutated["missing_requirements"] = missing
        mutated["state"] = "PARTIAL"
        mutated["blockers"] = ["MEASUREMENT_COVERAGE_INCOMPLETE"]
        _bind_probe_result_ids(mutated)
        assert_probe_result_integrity(mutated)
        self._flags_false(mutated)
        with self.assertRaises(ValueError):
            self._assert_chain(mutated)
        mutated["state"] = READY_STATE
        mutated["blockers"] = []
        _bind_probe_result_ids(mutated)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(mutated)

    def test_reseal_keeps_local_integrity_distinct_from_chain_reconstruction(self):
        environment = build_environment_contract(path_lookup_allowed=True)
        sandbox = build_os_sandbox_contract(
            self.policy, self.runner, self.builder, self.preflight, self.patch,
            self.attestation, self.pinning, environment,
        )
        blocked = self._build(os_sandbox_contract=sandbox, environment_contract=environment)

        promoted = deepcopy(blocked)
        promoted["state"] = READY_STATE
        promoted["blockers"] = []
        _bind_probe_result_ids(promoted)
        assert_probe_result_integrity(promoted)
        with self.assertRaises(ValueError):
            assert_probe_result(
                promoted, sandbox, self.policy, self.runner, self.builder, self.preflight,
                self.patch, self.attestation, self.pinning, environment,
            )

        coverage = deepcopy(self.result)
        coverage["coverage"]["required_verified"] = coverage["coverage"]["required_total"]
        _bind_probe_result_ids(coverage)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(coverage)

        cleared = deepcopy(self.result)
        cleared["coverage"]["missing"] = []
        cleared["missing_requirements"] = []
        _bind_probe_result_ids(cleared)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(cleared)

        satisfied = deepcopy(self.result)
        satisfied["physical_proof_satisfied"] = [derived_probe_requirements()[0]]
        _bind_probe_result_ids(satisfied)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(satisfied)

        counted = deepcopy(self.result)
        counted["coverage"]["required_verified"] = 1
        _bind_probe_result_ids(counted)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(counted)

        verified = deepcopy(self.result)
        verified["measurements"][0]["verified"] = True
        _bind_probe_result_ids(verified)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(verified)

    def test_forged_evidence_and_document_digest_are_not_physical_proof(self):
        measurement = deepcopy(self.result["measurements"][0])
        measurement["verified"] = True
        measurement["evidence"]["evidence_is_physical"] = True
        measurement["evidence"]["independently_verified"] = True
        measurement["evidence"]["evidence_digest"] = measurement["evidence"]["measurement_identity"]
        forged = deepcopy(self.result["measurements"])
        forged[0] = measurement
        derived = reconstruct_physical_coverage(forged)
        self.assertEqual(derived["required_verified"], 0)
        self.assertEqual(derived["physical_proof_satisfied"], [])
        self.assertEqual(derived["missing"], list(derived_probe_requirements()))
        mutated = deepcopy(self.result)
        mutated["measurements"] = forged
        mutated["physical_proof_satisfied"] = [measurement["requirement"]]
        _bind_probe_result_ids(mutated)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(mutated)

    def test_closed_schema_rejects_missing_fields_at_three_levels(self):
        top = deepcopy(self.result)
        del top["platform"]
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(top)
        measurement = deepcopy(self.result)
        del measurement["measurements"][0]["failure_reason"]
        _bind_probe_result_ids(measurement)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(measurement)
        evidence = deepcopy(self.result)
        del evidence["measurements"][0]["evidence"]["method"]
        _bind_probe_result_ids(evidence)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(evidence)

    def test_recheck_required_before_use_cannot_be_cleared(self):
        mutated = deepcopy(self.result)
        mutated["recheck_required_before_use"] = False
        _bind_probe_result_ids(mutated)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(mutated)
        nested = deepcopy(self.result)
        nested["measurements"][0]["recheck_required_before_use"] = False
        _bind_probe_result_ids(nested)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(nested)
        eternal = deepcopy(self.result)
        eternal["measurements"][0]["window_validity"] = "ETERNAL"
        _bind_probe_result_ids(eternal)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(eternal)

    def test_unresolved_and_windows_labels_are_not_physical_proof(self):
        self.assertEqual(self.result["platform"], "UNRESOLVED")
        self.assertIs(self.result["platform_verified"], False)
        self.assertEqual(self.result["physical_proof_satisfied"], [])
        windows = self._build(platform="WINDOWS")
        self.assertEqual(windows["platform"], "WINDOWS")
        self.assertIs(windows["platform_verified"], False)
        self.assertEqual(windows["coverage"]["required_verified"], 0)
        self.assertEqual(windows["physical_proof_satisfied"], [])
        self.assertTrue(all(item["verified"] is False for item in windows["measurements"]))
        ambiguous = deepcopy(self.result)
        ambiguous["measurements"][0]["observed_value"] = "PASS"
        _bind_probe_result_ids(ambiguous)
        with self.assertRaises(ValueError):
            assert_probe_result_integrity(ambiguous)
