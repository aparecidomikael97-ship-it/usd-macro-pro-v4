import unittest

from atlasquant_aion_windows_build_completion_package_attestation_handoff_v1 import (
    READY_CONTRACT_STATE, CLASSIFIED_STATE, READY_ARTIFACT_STATE,
    READY_HANDOFF_STATE, READY_RECONCILIATION_STATE, READY_REVIEW_STATE,
    BUILD_SUCCESS, BUILD_FAILURE, BUILD_UNKNOWN,
    build_completion_contract, classify_future_completion_observation,
    build_artifact_set_candidate, build_package_attestation_handoff,
    build_completion_reconciliation_contract, build_implementation_review,
    build_completion_policy,
)

D=lambda c:"sha256:"+(c*64)

class BuildCompletionPackageAttestationHandoffV1Tests(unittest.TestCase):
    def contract(self):
        out=build_completion_contract(
            start_receipt_digest=D("1"),
            launch_id="launch://first-prod-build-0001",
            build_id="build://first-prod-build-0001",
            expected_installation_manifest_digest=D("2"),
            expected_package_manifest_digest=D("3"),
            expected_dependency_lock_digest=D("4"),
            expected_build_recipe_digest=D("5"),
            expected_offline_input_promotion_digest=D("6"),
            build_observer_manifest_digest=D("7"),
            artifact_collector_manifest_digest=D("8"),
            completion_reconciliation_policy_digest=D("9"),
        )
        self.assertEqual(out["state"],READY_CONTRACT_STATE,out["blockers"])
        return out

    def success(self):
        c=self.contract()
        out=classify_future_completion_observation(
            c,requested_outcome=BUILD_SUCCESS,process_exit_observed=True,exit_code=0,
            process_identity_digest=D("a"),process_exit_observation_digest=D("b"),
            build_log_digest=D("c"),output_inventory_digest=D("d"),
            archive_digest=D("e"),sbom_digest=D("f"),provenance_digest=D("1"),
            dependency_lock_digest=c["expected_dependency_lock_digest"],
            installation_manifest_digest=c["expected_installation_manifest_digest"],
            package_manifest_digest=c["expected_package_manifest_digest"],
            network_deny_observation_digest=D("2"),
            sandbox_integrity_observation_digest=D("3"),
            unexpected_output_count=0,
        )
        self.assertEqual(out["state"],CLASSIFIED_STATE,out["blockers"])
        self.assertEqual(out["final_outcome"],BUILD_SUCCESS)
        return c,out

    def test_contract_is_design_only(self):
        c=self.contract()
        self.assertTrue(c["success_requires_exit_code_zero"])
        self.assertTrue(c["success_requires_complete_artifact_set"])
        self.assertTrue(c["terminal_failure_requires_authoritative_failure_evidence"])
        self.assertTrue(c["ambiguity_overrides_requested_success"])
        self.assertFalse(c["automatic_retry_after_ambiguous_completion_allowed"])
        for f in ("build_observer_implemented","artifact_collector_implemented",
                  "build_completion_observed","package_built","package_attested",
                  "package_installed","filesystem_modified","network_called","github_api_called"):
            self.assertFalse(c[f],f)

    def test_success_requires_complete_evidence(self):
        c=self.contract()
        out=classify_future_completion_observation(
            c,requested_outcome=BUILD_SUCCESS,process_exit_observed=True,exit_code=0,
            process_identity_digest=D("a"),process_exit_observation_digest=D("b"),
            build_log_digest=D("c"),output_inventory_digest=D("d"),
            archive_digest=D("e"),sbom_digest=D("f"),provenance_digest=D("1"),
            dependency_lock_digest=c["expected_dependency_lock_digest"],
            installation_manifest_digest=c["expected_installation_manifest_digest"],
            package_manifest_digest="",network_deny_observation_digest=D("2"),
            sandbox_integrity_observation_digest=D("3"),unexpected_output_count=0)
        self.assertEqual(out["final_outcome"],BUILD_UNKNOWN)
        self.assertFalse(out["artifact_promotion_allowed"])
        self.assertTrue(out["reconciliation_required"])

    def test_manifest_or_lock_drift_turns_requested_success_unknown(self):
        c=self.contract()
        for field in ("dependency_lock_digest","installation_manifest_digest","package_manifest_digest"):
            kwargs=dict(
                contract=c,requested_outcome=BUILD_SUCCESS,process_exit_observed=True,exit_code=0,
                process_identity_digest=D("a"),process_exit_observation_digest=D("b"),
                build_log_digest=D("c"),output_inventory_digest=D("d"),archive_digest=D("e"),
                sbom_digest=D("f"),provenance_digest=D("1"),
                dependency_lock_digest=c["expected_dependency_lock_digest"],
                installation_manifest_digest=c["expected_installation_manifest_digest"],
                package_manifest_digest=c["expected_package_manifest_digest"],
                network_deny_observation_digest=D("2"),sandbox_integrity_observation_digest=D("3"),
                unexpected_output_count=0)
            kwargs[field]=D("0")
            out=classify_future_completion_observation(**kwargs)
            self.assertEqual(out["final_outcome"],BUILD_UNKNOWN)

    def test_ambiguity_wins_over_complete_success(self):
        c=self.contract()
        out=classify_future_completion_observation(
            c,requested_outcome=BUILD_SUCCESS,process_exit_observed=True,exit_code=0,
            process_identity_digest=D("a"),process_exit_observation_digest=D("b"),
            build_log_digest=D("c"),output_inventory_digest=D("d"),archive_digest=D("e"),
            sbom_digest=D("f"),provenance_digest=D("1"),
            dependency_lock_digest=c["expected_dependency_lock_digest"],
            installation_manifest_digest=c["expected_installation_manifest_digest"],
            package_manifest_digest=c["expected_package_manifest_digest"],
            network_deny_observation_digest=D("2"),sandbox_integrity_observation_digest=D("3"),
            unexpected_output_count=0,ambiguity_evidence_digest=D("4"))
        self.assertEqual(out["final_outcome"],BUILD_UNKNOWN)
        self.assertFalse(out["artifact_promotion_allowed"])
        self.assertFalse(out["automatic_retry_allowed"])

    def test_terminal_failure_needs_authoritative_evidence(self):
        c=self.contract()
        good=classify_future_completion_observation(
            c,requested_outcome=BUILD_FAILURE,process_exit_observed=True,exit_code=2,
            terminal_failure_evidence_digest=D("5"))
        self.assertEqual(good["final_outcome"],BUILD_FAILURE)
        self.assertTrue(good["build_terminal_failure_confirmed"])
        bad=classify_future_completion_observation(
            c,requested_outcome=BUILD_FAILURE,process_exit_observed=True,exit_code=2)
        self.assertEqual(bad["final_outcome"],BUILD_UNKNOWN)

    def test_success_promotes_only_to_attestation_review(self):
        c,out=self.success()
        artifacts=build_artifact_set_candidate(c,out)
        self.assertEqual(artifacts["state"],READY_ARTIFACT_STATE,artifacts["blockers"])
        self.assertFalse(artifacts["artifact_set_trusted_as_physical_output"])
        self.assertFalse(artifacts["package_attestation_started"])
        self.assertFalse(artifacts["package_attested"])
        self.assertFalse(artifacts["package_installed"])
        handoff=build_package_attestation_handoff(artifacts)
        self.assertEqual(handoff["state"],READY_HANDOFF_STATE,handoff["blockers"])
        self.assertEqual(handoff["required_package_attestation_state"],"PACKAGE_ATTESTED_OFFLINE_NOT_INSTALLED")
        self.assertFalse(handoff["package_attestation_executed"])
        self.assertFalse(handoff["release_signature_verified_here"])
        self.assertFalse(handoff["authenticode_verified_here"])
        self.assertFalse(handoff["package_attested"])
        self.assertFalse(handoff["installation_authorized"])
        self.assertFalse(handoff["package_installed"])

    def test_unknown_cannot_promote_artifacts_and_requires_reconciliation(self):
        c=self.contract()
        unknown=classify_future_completion_observation(
            c,requested_outcome=BUILD_UNKNOWN,process_exit_observed=False,exit_code=None,
            ambiguity_evidence_digest=D("6"))
        artifacts=build_artifact_set_candidate(c,unknown)
        self.assertEqual(artifacts["state"],"BLOCKED")
        self.assertIn("CONFIRMED_BUILD_SUCCESS_REQUIRED",artifacts["blockers"])
        rec=build_completion_reconciliation_contract(
            unknown,process_readback_policy_digest=D("1"),
            output_store_readback_policy_digest=D("2"),
            artifact_directory_readback_policy_digest=D("3"))
        self.assertEqual(rec["state"],READY_RECONCILIATION_STATE,rec["blockers"])
        self.assertFalse(rec["automatic_retry_allowed"])
        self.assertFalse(rec["new_build_launch_authorized"])
        self.assertFalse(rec["artifact_promotion_allowed"])
        self.assertFalse(rec["reconciliation_completed"])

    def test_unexpected_output_blocks_success(self):
        c=self.contract()
        out=classify_future_completion_observation(
            c,requested_outcome=BUILD_SUCCESS,process_exit_observed=True,exit_code=0,
            process_identity_digest=D("a"),process_exit_observation_digest=D("b"),
            build_log_digest=D("c"),output_inventory_digest=D("d"),archive_digest=D("e"),
            sbom_digest=D("f"),provenance_digest=D("1"),
            dependency_lock_digest=c["expected_dependency_lock_digest"],
            installation_manifest_digest=c["expected_installation_manifest_digest"],
            package_manifest_digest=c["expected_package_manifest_digest"],
            network_deny_observation_digest=D("2"),sandbox_integrity_observation_digest=D("3"),
            unexpected_output_count=1)
        self.assertEqual(out["final_outcome"],BUILD_UNKNOWN)

    def test_implementation_review_stops_before_attestation_or_install(self):
        c=self.contract()
        review=build_implementation_review(
            c,build_observer_source_digest=D("1"),artifact_collector_source_digest=D("2"),
            completion_receipt_writer_design_digest=D("3"),package_handoff_verifier_design_digest=D("4"),
            reconciliation_source_digest=D("5"))
        self.assertEqual(review["state"],READY_REVIEW_STATE,review["blockers"])
        for f in ("build_observer_implemented","artifact_collector_implemented",
                  "completion_receipt_writer_implemented","package_handoff_verifier_implemented",
                  "reconciliation_implemented","build_completion_observed","completion_receipt_persisted",
                  "artifact_set_collected","package_attestation_executed","package_attested",
                  "installation_authorized","package_installed","network_called","github_api_called"):
            self.assertFalse(review[f],f)

    def test_policy_is_fail_closed(self):
        p=build_completion_policy()
        self.assertTrue(p["success_requires_exit_code_zero"])
        self.assertTrue(p["success_requires_complete_artifact_set"])
        self.assertTrue(p["terminal_failure_requires_authoritative_failure_evidence"])
        self.assertTrue(p["ambiguity_overrides_requested_success"])
        self.assertFalse(p["automatic_retry_after_ambiguous_completion_allowed"])
        self.assertTrue(p["unknown_requires_separate_reconciliation"])
        self.assertFalse(p["unknown_allows_artifact_promotion"])
        self.assertFalse(p["failure_allows_artifact_promotion"])
        self.assertTrue(p["successful_build_is_not_package_attestation"])
        self.assertTrue(p["package_attestation_is_not_install_authorization"])
        self.assertFalse(p["generic_chat_is_install_authority"])
        for f in ("build_observer_implemented","artifact_collector_implemented","build_completion_observed",
                  "completion_receipt_persisted","artifact_set_collected","package_attestation_executed",
                  "package_attested","installation_authorized","package_installed","filesystem_modified",
                  "network_called","github_api_called","live_repository_mutation_authorized",
                  "live_repository_mutation_performed","production_repository_mutation_performed",
                  "deploy_executed","worker_activated","provider_activated","production_persistence_activated"):
            self.assertFalse(p[f],f)

if __name__=="__main__":
    unittest.main()
