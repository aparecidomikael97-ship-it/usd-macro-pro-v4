import copy
import hashlib
import json
import unittest

from atlasquant_aion_repository_mutation_executor_boundary_v1 import (
    EXECUTOR_BOUNDARY_SCHEMA,
)
from atlasquant_aion_signed_github_mutation_adapter_outcome_v1 import (
    ADAPTER_SCHEMA,
    ATTEMPT_SCHEMA,
    FORBIDDEN_ADAPTER_CAPABILITIES,
    OUTCOME_SCHEMA,
    build_external_mutation_attempt_observation,
    build_immutable_mutation_outcome_receipt,
    build_signed_github_mutation_adapter_attestation,
    github_mutation_outcome_policy,
    verify_mutation_outcome_receipt,
)


D = lambda c: "sha256:" + (c * 64)


def digest(value):
    return "sha256:" + hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


class AionSignedGithubMutationAdapterOutcomeV1Tests(unittest.TestCase):
    def boundary(self):
        material = {
            "execution_attempt_id": "repo-attempt-1",
            "authorization_receipt_digest": D("1"),
            "consumption_attestation_digest": D("2"),
            "authorization_consumed_at": "2026-10-08T10:00:52+00:00",
            "repository_ref_digest": D("3"),
            "pr_number": 1015,
            "requested_mutation": "PR_DRAFT_TO_READY",
            "logical_operation": "SET_PR_READY_FOR_REVIEW",
            "main_sha": "a" * 40,
            "main_tree_sha": "b" * 40,
            "head_branch": "impl/aion-owner-experience-v1-20261008",
            "head_sha": "c" * 40,
            "base_branch": "main",
            "file_delta_digest": D("4"),
            "workflow_snapshot_digest": D("5"),
            "idempotency_key_digest": D("6"),
            "effect_key_digest": D("7"),
            "lease_identity_digest": D("8"),
            "adapter_manifest_digest": D("9"),
            "adapter_build_digest": D("a"),
            "signed_adapter_verified": True,
            "repository_identity_match": True,
            "least_privilege_scope_verified": True,
            "target_pr_match": True,
            "requested_mutation_match": True,
            "main_sha_match": True,
            "head_sha_match": True,
            "base_branch_match": True,
            "file_delta_match": True,
            "workflow_snapshot_match": True,
            "checked_at": "2026-10-08T10:00:55+00:00",
        }
        return {
            "schema": EXECUTOR_BOUNDARY_SCHEMA,
            "state": "READY_FOR_SINGLE_REPOSITORY_MUTATION_ATTEMPT",
            "blockers": [],
            **material,
            "executor_boundary_digest": digest(material),
            "exactly_one_mutation_attempt_allowed": True,
            "authorization_consumed_before_attempt": True,
            "provider_switch_allowed": False,
            "repository_switch_allowed": False,
            "pr_switch_allowed": False,
            "mutation_switch_allowed": False,
            "main_sha_switch_allowed": False,
            "head_sha_switch_allowed": False,
            "base_switch_allowed": False,
            "scope_expansion_allowed": False,
            "api_request_generated": False,
            "api_method_selected": False,
            "api_endpoint_included": False,
            "credential_material_included": False,
            "github_api_called": False,
            "network_called": False,
            "repository_mutation_performed": False,
            "merge_executed": False,
            "retarget_executed": False,
            "draft_transition_executed": False,
            "branch_deleted": False,
            "deploy_executed": False,
            "worker_activated": False,
            "provider_activated": False,
            "production_persistence_activated": False,
            "executes_action": False,
        }

    def adapter(self, boundary=None, **changes):
        boundary = boundary or self.boundary()
        kwargs = {
            "executor_boundary": boundary,
            "adapter_id": "github-mutation-adapter-v1",
            "adapter_version": "1.0.0",
            "adapter_manifest_digest": D("9"),
            "adapter_build_digest": D("a"),
            "supply_chain_evidence_digest": D("b"),
            "repository_identity_digest": D("c"),
            "capability_scope_digest": D("d"),
            "response_schema_digest": D("e"),
            "error_taxonomy_digest": D("f"),
            "postcondition_policy_digest": D("1"),
            "signed_adapter_verified": True,
            "trusted_signing_root_verified": True,
            "repository_identity_match": True,
            "least_privilege_scope_verified": True,
            "logical_operation_allowlist": ["SET_PR_READY_FOR_REVIEW"],
            "forbidden_capabilities_declared": list(
                FORBIDDEN_ADAPTER_CAPABILITIES
            ),
            "checked_at": "2026-10-08T10:01:00+00:00",
        }
        kwargs.update(changes)
        return build_signed_github_mutation_adapter_attestation(**kwargs)

    def attempt(self, boundary=None, adapter=None, **changes):
        boundary = boundary or self.boundary()
        adapter = adapter or self.adapter(boundary)
        kwargs = {
            "executor_boundary": boundary,
            "adapter_attestation": adapter,
            "observation_id": "attempt-observation-1",
            "request_correlation_digest": D("2"),
            "transport_observation_digest": D("3"),
            "provider_request_identity_digest": D("4"),
            "attempted_at": "2026-10-08T10:01:02+00:00",
            "observed_at": "2026-10-08T10:01:05+00:00",
            "trusted_adapter_observation_verified": True,
            "request_dispatch_observed": True,
            "network_transport_observed": True,
        }
        kwargs.update(changes)
        return build_external_mutation_attempt_observation(**kwargs)

    def success_receipt(self, attempt=None, **changes):
        attempt = attempt or self.attempt()
        kwargs = {
            "attempt_observation": attempt,
            "receipt_id": "outcome-receipt-success-1",
            "declared_outcome": "CONFIRMED_SUCCESS",
            "provider_response_evidence_digest": D("5"),
            "postcondition_evidence_digest": D("6"),
            "terminal_failure_evidence_digest": "",
            "ambiguity_evidence_digest": "",
            "ambiguity_triggers": [],
            "provider_response_received": True,
            "response_correlation_verified": True,
            "response_authenticity_verified": True,
            "response_schema_verified": True,
            "provider_success_semantics_verified": True,
            "provider_terminal_failure_semantics_verified": False,
            "repository_postcondition_readback_verified": True,
            "expected_postcondition_match": True,
            "authoritative_no_effect_or_terminal_rejection_verified": False,
            "evidence_complete": True,
            "observed_at": "2026-10-08T10:01:07+00:00",
        }
        kwargs.update(changes)
        return build_immutable_mutation_outcome_receipt(**kwargs)

    def test_signed_adapter_attestation_is_nonexecuting(self):
        adapter = self.adapter()
        self.assertEqual(
            adapter["state"],
            "SIGNED_GITHUB_MUTATION_ADAPTER_ATTESTED",
            adapter["blockers"],
        )
        self.assertEqual(adapter["schema"], ADAPTER_SCHEMA)
        self.assertFalse(adapter["endpoint_included"])
        self.assertFalse(adapter["credential_material_included"])
        self.assertFalse(adapter["token_material_included"])
        self.assertFalse(adapter["raw_request_payload_included"])
        self.assertFalse(adapter["adapter_loaded_by_this_module"])
        self.assertFalse(adapter["api_request_generated"])
        self.assertFalse(adapter["github_api_called"])
        self.assertFalse(adapter["network_called"])
        self.assertFalse(adapter["repository_mutation_performed"])
        self.assertFalse(adapter["executes_action"])

    def test_unsigned_or_scope_incomplete_adapter_blocks(self):
        blocked = self.adapter(
            signed_adapter_verified=False,
            forbidden_capabilities_declared=[],
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn(
            "SIGNED_ADAPTER_VERIFICATION_REQUIRED",
            blocked["blockers"],
        )
        self.assertIn(
            "FORBIDDEN_CAPABILITY_DECLARATION_INCOMPLETE",
            blocked["blockers"],
        )

    def test_attempt_observation_is_external_evidence_only(self):
        attempt = self.attempt()
        self.assertEqual(
            attempt["state"],
            "MUTATION_ATTEMPT_EXTERNALLY_ATTESTED",
            attempt["blockers"],
        )
        self.assertEqual(attempt["schema"], ATTEMPT_SCHEMA)
        self.assertTrue(attempt["request_dispatch_observed"])
        self.assertTrue(attempt["network_transport_observed"])
        self.assertFalse(attempt["attempt_performed_by_this_module"])
        self.assertFalse(attempt["api_request_generated_by_this_module"])
        self.assertFalse(attempt["github_api_called_by_this_module"])
        self.assertFalse(attempt["network_called_by_this_module"])
        self.assertFalse(
            attempt["repository_mutation_performed_by_this_module"]
        )
        self.assertFalse(attempt["automatic_retry_allowed"])
        self.assertFalse(attempt["retry_scheduled"])
        self.assertFalse(attempt["retry_performed"])

    def test_confirmed_success_requires_postcondition_readback(self):
        receipt = self.success_receipt()
        self.assertEqual(
            receipt["state"],
            "IMMUTABLE_MUTATION_OUTCOME_RECORDED",
            receipt["blockers"],
        )
        self.assertEqual(receipt["outcome"], "CONFIRMED_SUCCESS")
        self.assertTrue(receipt["success_confirmed"])
        self.assertFalse(receipt["terminal_failure_confirmed"])
        self.assertFalse(receipt["outcome_unknown_recorded"])
        self.assertEqual(
            receipt["expected_postcondition"],
            "PR_IS_READY_FOR_REVIEW",
        )
        self.assertFalse(receipt["automatic_retry_allowed"])
        self.assertFalse(receipt["new_attempt_authorized"])
        self.assertTrue(
            verify_mutation_outcome_receipt(receipt)["valid"]
        )

    def test_claimed_success_without_postcondition_downgrades_to_unknown(self):
        receipt = self.success_receipt(
            repository_postcondition_readback_verified=False,
            expected_postcondition_match=False,
            postcondition_evidence_digest="",
            ambiguity_evidence_digest=D("7"),
        )
        self.assertEqual(receipt["outcome"], "OUTCOME_UNKNOWN")
        self.assertFalse(receipt["success_confirmed"])
        self.assertTrue(receipt["outcome_unknown_recorded"])
        self.assertTrue(receipt["reconciliation_required"])
        self.assertIn("EVIDENCE_INCOMPLETE", receipt["ambiguity_triggers"])
        self.assertFalse(receipt["automatic_retry_allowed"])

    def test_terminal_failure_requires_authoritative_no_effect_or_rejection(self):
        attempt = self.attempt()
        receipt = build_immutable_mutation_outcome_receipt(
            attempt,
            receipt_id="outcome-receipt-failure-1",
            declared_outcome="CONFIRMED_TERMINAL_FAILURE",
            provider_response_evidence_digest=D("5"),
            postcondition_evidence_digest="",
            terminal_failure_evidence_digest=D("6"),
            ambiguity_evidence_digest="",
            ambiguity_triggers=[],
            provider_response_received=True,
            response_correlation_verified=True,
            response_authenticity_verified=True,
            response_schema_verified=True,
            provider_success_semantics_verified=False,
            provider_terminal_failure_semantics_verified=True,
            repository_postcondition_readback_verified=False,
            expected_postcondition_match=False,
            authoritative_no_effect_or_terminal_rejection_verified=True,
            evidence_complete=True,
            observed_at="2026-10-08T10:01:07+00:00",
        )
        self.assertEqual(
            receipt["outcome"],
            "CONFIRMED_TERMINAL_FAILURE",
        )
        self.assertTrue(receipt["terminal_failure_confirmed"])
        self.assertFalse(receipt["automatic_retry_allowed"])
        self.assertTrue(verify_mutation_outcome_receipt(receipt)["valid"])

    def test_missing_terminal_evidence_downgrades_to_unknown(self):
        attempt = self.attempt()
        receipt = build_immutable_mutation_outcome_receipt(
            attempt,
            receipt_id="outcome-receipt-failure-weak-1",
            declared_outcome="CONFIRMED_TERMINAL_FAILURE",
            provider_response_evidence_digest=D("5"),
            postcondition_evidence_digest="",
            terminal_failure_evidence_digest="",
            ambiguity_evidence_digest=D("7"),
            ambiguity_triggers=[],
            provider_response_received=True,
            response_correlation_verified=True,
            response_authenticity_verified=True,
            response_schema_verified=True,
            provider_success_semantics_verified=False,
            provider_terminal_failure_semantics_verified=True,
            repository_postcondition_readback_verified=False,
            expected_postcondition_match=False,
            authoritative_no_effect_or_terminal_rejection_verified=False,
            evidence_complete=True,
            observed_at="2026-10-08T10:01:07+00:00",
        )
        self.assertEqual(receipt["outcome"], "OUTCOME_UNKNOWN")
        self.assertTrue(receipt["outcome_unknown_recorded"])
        self.assertFalse(receipt["automatic_retry_allowed"])

    def test_timeout_is_unknown_and_never_retryable(self):
        attempt = self.attempt()
        receipt = build_immutable_mutation_outcome_receipt(
            attempt,
            receipt_id="outcome-receipt-timeout-1",
            declared_outcome="OUTCOME_UNKNOWN",
            provider_response_evidence_digest=D("5"),
            postcondition_evidence_digest="",
            terminal_failure_evidence_digest="",
            ambiguity_evidence_digest=D("6"),
            ambiguity_triggers=["TIMEOUT_AFTER_DISPATCH"],
            provider_response_received=False,
            response_correlation_verified=False,
            response_authenticity_verified=False,
            response_schema_verified=False,
            provider_success_semantics_verified=False,
            provider_terminal_failure_semantics_verified=False,
            repository_postcondition_readback_verified=False,
            expected_postcondition_match=False,
            authoritative_no_effect_or_terminal_rejection_verified=False,
            evidence_complete=True,
            observed_at="2026-10-08T10:01:07+00:00",
        )
        self.assertEqual(receipt["outcome"], "OUTCOME_UNKNOWN")
        self.assertTrue(receipt["outcome_unknown_recorded"])
        self.assertTrue(receipt["reconciliation_required"])
        self.assertTrue(
            receipt["separate_reconciliation_authorization_required"]
        )
        self.assertFalse(receipt["automatic_retry_allowed"])
        self.assertFalse(receipt["retry_scheduled"])
        self.assertFalse(receipt["retry_performed"])
        self.assertFalse(receipt["new_attempt_authorized"])
        self.assertTrue(
            receipt["fresh_authorization_required_for_new_attempt"]
        )
        self.assertTrue(receipt["new_effect_key_required_for_new_attempt"])
        self.assertTrue(
            receipt["new_execution_attempt_id_required"]
        )

    def test_unknown_requires_ambiguity_evidence_digest(self):
        attempt = self.attempt()
        receipt = build_immutable_mutation_outcome_receipt(
            attempt,
            receipt_id="outcome-receipt-unknown-no-proof-1",
            declared_outcome="OUTCOME_UNKNOWN",
            provider_response_evidence_digest=D("5"),
            postcondition_evidence_digest="",
            terminal_failure_evidence_digest="",
            ambiguity_evidence_digest="",
            ambiguity_triggers=["CONNECTION_RESET_AFTER_DISPATCH"],
            provider_response_received=False,
            response_correlation_verified=False,
            response_authenticity_verified=False,
            response_schema_verified=False,
            provider_success_semantics_verified=False,
            provider_terminal_failure_semantics_verified=False,
            repository_postcondition_readback_verified=False,
            expected_postcondition_match=False,
            authoritative_no_effect_or_terminal_rejection_verified=False,
            evidence_complete=True,
            observed_at="2026-10-08T10:01:07+00:00",
        )
        self.assertEqual(receipt["state"], "BLOCKED")
        self.assertIn(
            "AMBIGUITY_EVIDENCE_DIGEST_REQUIRED",
            receipt["blockers"],
        )

    def test_conflicting_success_and_failure_signals_force_unknown(self):
        receipt = self.success_receipt(
            provider_terminal_failure_semantics_verified=True,
            ambiguity_evidence_digest=D("7"),
        )
        self.assertEqual(receipt["outcome"], "OUTCOME_UNKNOWN")
        self.assertIn(
            "SUCCESS_AND_FAILURE_SIGNAL_CONFLICT",
            receipt["ambiguity_triggers"],
        )
        self.assertFalse(receipt["automatic_retry_allowed"])

    def test_outcome_receipt_is_tamper_evident_and_immutable(self):
        receipt = self.success_receipt()
        tampered = copy.deepcopy(receipt)
        tampered["outcome"] = "CONFIRMED_TERMINAL_FAILURE"
        result = verify_mutation_outcome_receipt(tampered)
        self.assertFalse(result["valid"])
        self.assertIn(
            "OUTCOME_RECEIPT_DIGEST_MISMATCH",
            result["blockers"],
        )

    def test_policy_forbids_implicit_success_failure_and_retry(self):
        policy = github_mutation_outcome_policy()
        self.assertTrue(policy["signed_adapter_required"])
        self.assertTrue(policy["trusted_signing_root_required"])
        self.assertTrue(policy["least_privilege_scope_required"])
        self.assertTrue(policy["repository_identity_binding_required"])
        self.assertFalse(policy["raw_endpoint_material_allowed"])
        self.assertFalse(policy["credential_material_allowed"])
        self.assertFalse(policy["raw_request_payload_allowed"])
        self.assertTrue(
            policy["attempt_observation_must_be_external_attestation"]
        )
        self.assertFalse(policy["attempt_performed_by_this_module"])
        self.assertFalse(policy["absence_of_error_is_success"])
        self.assertFalse(
            policy["absence_of_response_is_terminal_failure"]
        )
        self.assertTrue(
            policy["success_requires_authoritative_postcondition_readback"]
        )
        self.assertTrue(
            policy["terminal_failure_requires_authoritative_no_effect_or_rejection"]
        )
        self.assertTrue(
            policy["ambiguity_always_maps_to_outcome_unknown"]
        )
        self.assertTrue(policy["outcome_unknown_receipt_immutable"])
        self.assertFalse(
            policy["automatic_retry_after_outcome_unknown_allowed"]
        )
        self.assertTrue(
            policy["reconciliation_required_after_outcome_unknown"]
        )
        self.assertTrue(
            policy["separate_reconciliation_authorization_required"]
        )
        self.assertTrue(
            policy["fresh_authorization_required_for_new_attempt"]
        )
        self.assertFalse(policy["github_api_called"])
        self.assertFalse(policy["network_called"])
        self.assertFalse(policy["repository_mutation_performed"])
        self.assertFalse(policy["merge_executed"])
        self.assertFalse(policy["retarget_executed"])
        self.assertFalse(policy["draft_transition_executed"])
        self.assertFalse(policy["branch_deleted"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["worker_activation_allowed"])
        self.assertFalse(policy["provider_activation_allowed"])
        self.assertFalse(policy["production_persistence_activation_allowed"])
        self.assertFalse(policy["external_action_executed"])
        self.assertFalse(policy["executes_action"])


if __name__ == "__main__":
    unittest.main()
