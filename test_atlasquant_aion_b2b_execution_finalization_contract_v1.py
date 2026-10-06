from __future__ import annotations

import unittest

import atlasquant_aion_b2b_execution_finalization_contract_v1 as finalization
import atlasquant_aion_b2b_outcome_reconciliation_contract_v1 as reconciliation
from test_atlasquant_aion_b2b_outcome_reconciliation_contract_v1 import (
    approved_outcome_receipt_review,
)


def approved_reconciliation_review():
    return reconciliation.build_outcome_reconciliation_contract(
        outcome_receipt_review=approved_outcome_receipt_review(),
    )


class ExecutionFinalizationContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in finalization.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_reconciliation_unlocks_design_only(self):
        out = finalization.build_execution_finalization_contract(
            outcome_reconciliation_review=approved_reconciliation_review(),
        )
        self.assertEqual(out["state"], finalization.READY)
        self.assertTrue(out["execution_finalization_design_only"])
        self.assertEqual(
            out["finalization_mode"],
            "TERMINAL_EVIDENCE_ONLY_CLOSURE",
        )
        self.assertTrue(out["terminal_evidence_required"])
        self.assertTrue(out["append_only_finalization_record_required"])
        self.assertFalse(out["finalization_creates_execution_authority"])
        self.assertEqual(out["finops_cap_cents"], 20000)
        self.assert_no_authority(out)

    def test_reconciliation_must_be_exact_ready_state(self):
        row = approved_reconciliation_review()
        row["state"] = "BLOCKED"
        out = finalization.build_execution_finalization_contract(
            outcome_reconciliation_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "OUTCOME_RECONCILIATION_DESIGN_REVIEW_REQUIRED",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_upstream_retry_flip_blocks(self):
        row = approved_reconciliation_review()
        row["retry_performed"] = True
        out = finalization.build_execution_finalization_contract(
            outcome_reconciliation_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "OUTCOME_RECONCILIATION_UNSAFE_FIELD:retry_performed",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_only_terminal_outcomes_are_finalizable(self):
        out = finalization.build_execution_finalization_contract(
            outcome_reconciliation_review=approved_reconciliation_review(),
        )
        self.assertEqual(
            tuple(out["finalizable_outcome_states"]),
            (
                "CONFIRMED_SUCCESS",
                "CONFIRMED_TERMINAL_FAILURE",
                "RECONCILED_CONFIRMED_SUCCESS",
                "RECONCILED_CONFIRMED_TERMINAL_FAILURE",
            ),
        )
        self.assertEqual(
            tuple(out["non_finalizable_outcome_states"]),
            ("OUTCOME_UNKNOWN", "STILL_OUTCOME_UNKNOWN"),
        )
        self.assertTrue(out["unknown_outcome_finalization_forbidden"])
        self.assertTrue(out["still_unknown_outcome_finalization_forbidden"])
        self.assert_no_authority(out)

    def test_final_execution_states_are_closed_and_explicit(self):
        out = finalization.build_execution_finalization_contract(
            outcome_reconciliation_review=approved_reconciliation_review(),
        )
        self.assertEqual(
            tuple(out["final_execution_states"]),
            ("FINALIZED_SUCCESS", "FINALIZED_TERMINAL_FAILURE"),
        )
        self.assert_no_authority(out)

    def test_success_requires_positive_effect_and_postcondition_evidence(self):
        out = finalization.build_execution_finalization_contract(
            outcome_reconciliation_review=approved_reconciliation_review(),
        )
        required = set(out["required_success_finalization_evidence"])
        self.assertTrue({
            "AUTHORITATIVE_TERMINAL_OUTCOME",
            "SUCCESS_OUTCOME_STATE",
            "EXECUTION_ID_MATCH",
            "TRACE_ID_MATCH",
            "IDEMPOTENCY_KEY_MATCH",
            "EFFECT_KEY_MATCH",
            "PROVIDER_REQUEST_CORRELATION_MATCH",
            "PROVIDER_IDENTITY_MATCH",
            "EFFECT_CONFIRMATION_EVIDENCE_COMPLETE",
            "EXPECTED_POSTCONDITION_EVIDENCE_MATCH",
            "NO_UNRESOLVED_OUTCOME_CONFLICT",
            "NO_PENDING_RECONCILIATION",
            "NO_PENDING_ROLLBACK_OR_COMPENSATION",
            "FINOPS_OBSERVATION_WITHIN_POLICY",
        }.issubset(required))
        self.assertTrue(out["success_requires_positive_effect_evidence"])
        self.assertTrue(out["success_requires_postcondition_evidence"])
        self.assert_no_authority(out)

    def test_terminal_failure_requires_authoritative_no_effect_or_rejection(self):
        out = finalization.build_execution_finalization_contract(
            outcome_reconciliation_review=approved_reconciliation_review(),
        )
        required = set(out["required_failure_finalization_evidence"])
        self.assertTrue({
            "AUTHORITATIVE_TERMINAL_OUTCOME",
            "TERMINAL_FAILURE_OUTCOME_STATE",
            "EXECUTION_ID_MATCH",
            "TRACE_ID_MATCH",
            "IDEMPOTENCY_KEY_MATCH",
            "EFFECT_KEY_MATCH",
            "PROVIDER_REQUEST_CORRELATION_MATCH",
            "PROVIDER_IDENTITY_MATCH",
            "AUTHORITATIVE_NO_EFFECT_OR_TERMINAL_REJECTION_EVIDENCE",
            "NO_UNRESOLVED_OUTCOME_CONFLICT",
            "NO_PENDING_RECONCILIATION",
            "ROLLBACK_OR_COMPENSATION_NOT_REQUIRED_OR_SETTLED",
            "FINOPS_OBSERVATION_WITHIN_POLICY",
        }.issubset(required))
        self.assertTrue(
            out["terminal_failure_requires_authoritative_no_effect_or_rejection_evidence"]
        )
        self.assert_no_authority(out)

    def test_unsettled_safety_work_blocks_finalization(self):
        out = finalization.build_execution_finalization_contract(
            outcome_reconciliation_review=approved_reconciliation_review(),
        )
        blockers = set(out["finalization_blockers"])
        self.assertTrue({
            "OUTCOME_UNKNOWN",
            "STILL_OUTCOME_UNKNOWN",
            "MISSING_TERMINAL_EVIDENCE",
            "CONFLICTING_TERMINAL_EVIDENCE",
            "POSTCONDITION_NOT_CONFIRMED",
            "PENDING_RECONCILIATION",
            "PENDING_ROLLBACK",
            "PENDING_COMPENSATION",
            "ROLLBACK_OR_COMPENSATION_FAILED",
            "FINOPS_POLICY_UNSETTLED",
            "AUDIT_CHAIN_INCOMPLETE",
        }.issubset(blockers))
        self.assertTrue(out["pending_reconciliation_blocks_finalization"])
        self.assertTrue(out["pending_rollback_blocks_finalization"])
        self.assertTrue(out["pending_compensation_blocks_finalization"])
        self.assertTrue(out["failed_rollback_or_compensation_blocks_finalization"])
        self.assert_no_authority(out)

    def test_finalization_never_grants_retry_reconcile_or_compensation(self):
        out = finalization.build_execution_finalization_contract(
            outcome_reconciliation_review=approved_reconciliation_review(),
        )
        rules = set(out["required_finalization_rules"])
        self.assertTrue({
            "FINALIZATION_IS_NOT_RETRY",
            "FINALIZATION_IS_NOT_RECONCILIATION",
            "FINALIZATION_IS_NOT_ROLLBACK",
            "FINALIZATION_IS_NOT_COMPENSATION",
            "FINALIZATION_IS_NOT_EXTERNAL_EFFECT_REPLAY",
            "FINALIZATION_CANNOT_CREATE_NEW_EXECUTION_AUTHORITY",
        }.issubset(rules))
        self.assertFalse(out["retry_allowed_by_finalization"])
        self.assertFalse(out["reconciliation_allowed_by_finalization"])
        self.assertFalse(out["rollback_allowed_by_finalization"])
        self.assertFalse(out["compensation_allowed_by_finalization"])
        self.assert_no_authority(out)

    def test_bindings_preserve_terminal_chain_of_custody(self):
        out = finalization.build_execution_finalization_contract(
            outcome_reconciliation_review=approved_reconciliation_review(),
        )
        fields = set(out["required_finalization_bindings"])
        self.assertTrue({
            "execution_id",
            "durable_dispatch_record_digest",
            "external_effect_call_boundary_digest",
            "external_effect_outcome_receipt_digest",
            "outcome_reconciliation_record_digest",
            "execution_envelope_digest",
            "pre_dispatch_attestation_digest",
            "fresh_owner_authorization_digest",
            "reconciliation_authorization_digest",
            "provider_adapter_attestation_digest",
            "provider_capability_binding_digest",
            "provider_identity_ref",
            "provider_adapter_digest",
            "idempotency_key_digest",
            "effect_key_digest",
            "provider_request_correlation_digest",
            "terminal_evidence_set_digest",
            "expected_postcondition_digest",
            "rollback_plan_digest",
            "rollback_or_compensation_settlement_digest",
            "finops_estimate_digest",
            "finops_observation_digest",
            "observability_trace_id",
            "audit_chain_digest",
        }.issubset(fields))
        self.assert_no_authority(out)

    def test_contract_does_not_finalize_query_retry_or_execute(self):
        out = finalization.build_execution_finalization_contract(
            outcome_reconciliation_review=approved_reconciliation_review(),
        )
        for key in (
            "finalization_authorized",
            "finalization_performed",
            "finalization_record_persisted",
            "execution_finalized",
            "success_finalized",
            "terminal_failure_finalized",
            "provider_status_queried",
            "network_called",
            "provider_called",
            "retry_performed",
            "reconciliation_performed",
            "rollback_performed",
            "compensation_performed",
            "external_effect_attempted",
            "external_action_executed",
        ):
            self.assertFalse(out[key], key)
        self.assert_no_authority(out)

    def test_next_step_is_finalization_persistence_design_only(self):
        out = finalization.build_execution_finalization_contract(
            outcome_reconciliation_review=approved_reconciliation_review(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_EXECUTION_FINALIZATION_PERSISTENCE_CONTRACT_ONLY",
        )
        self.assertFalse(out["execution_allowed"])
        self.assertFalse(out["external_action_executed"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
