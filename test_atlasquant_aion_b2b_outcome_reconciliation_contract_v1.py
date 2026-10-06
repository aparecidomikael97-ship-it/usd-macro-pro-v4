from __future__ import annotations

import unittest

import atlasquant_aion_b2b_external_effect_outcome_receipt_contract_v1 as outcome
import atlasquant_aion_b2b_outcome_reconciliation_contract_v1 as reconciliation
from test_atlasquant_aion_b2b_external_effect_outcome_receipt_contract_v1 import (
    approved_call_boundary_review,
)


def approved_outcome_receipt_review():
    return outcome.build_external_effect_outcome_receipt_contract(
        external_effect_call_boundary_review=approved_call_boundary_review(),
    )


class OutcomeReconciliationContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in reconciliation.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_outcome_receipt_unlocks_design_only(self):
        out = reconciliation.build_outcome_reconciliation_contract(
            outcome_receipt_review=approved_outcome_receipt_review(),
        )
        self.assertEqual(out["state"], reconciliation.READY)
        self.assertTrue(out["outcome_reconciliation_design_only"])
        self.assertEqual(
            out["reconciliation_mode"],
            "SEPARATE_EVIDENCE_BOUND_UNKNOWN_RESOLUTION",
        )
        self.assertTrue(out["original_receipt_immutable"])
        self.assertTrue(out["separate_reconciliation_record_required"])
        self.assertFalse(out["reconciliation_is_retry"])
        self.assertFalse(out["reconciliation_replays_external_effect"])
        self.assertEqual(out["finops_cap_cents"], 20000)
        self.assert_no_authority(out)

    def test_outcome_receipt_must_be_exact_ready_state(self):
        row = approved_outcome_receipt_review()
        row["state"] = "BLOCKED"
        out = reconciliation.build_outcome_reconciliation_contract(
            outcome_receipt_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("OUTCOME_RECEIPT_DESIGN_REVIEW_REQUIRED", out["blockers"])
        self.assert_no_authority(out)

    def test_upstream_execution_flip_blocks(self):
        row = approved_outcome_receipt_review()
        row["provider_called"] = True
        out = reconciliation.build_outcome_reconciliation_contract(
            outcome_receipt_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "OUTCOME_RECEIPT_UNSAFE_FIELD:provider_called",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_reconciliation_states_are_closed_and_explicit(self):
        out = reconciliation.build_outcome_reconciliation_contract(
            outcome_receipt_review=approved_outcome_receipt_review(),
        )
        self.assertEqual(
            tuple(out["reconciliation_states"]),
            (
                "RECONCILED_CONFIRMED_SUCCESS",
                "RECONCILED_CONFIRMED_TERMINAL_FAILURE",
                "STILL_OUTCOME_UNKNOWN",
            ),
        )
        self.assert_no_authority(out)

    def test_conflict_or_weak_evidence_preserves_unknown(self):
        out = reconciliation.build_outcome_reconciliation_contract(
            outcome_receipt_review=approved_outcome_receipt_review(),
        )
        conditions = set(out["unknown_preserving_conditions"])
        self.assertTrue({
            "EVIDENCE_MISSING",
            "EVIDENCE_INCOMPLETE",
            "EVIDENCE_STALE",
            "EVIDENCE_UNAUTHENTICATED",
            "EVIDENCE_SOURCE_NOT_ATTESTED",
            "CORRELATION_MISMATCH",
            "IDENTITY_MISMATCH",
            "IDEMPOTENCY_MISMATCH",
            "EFFECT_KEY_MISMATCH",
            "EVIDENCE_CONFLICT",
            "DUPLICATE_EVIDENCE_CONFLICT",
            "SEQUENCE_REGRESSION",
            "POSTCONDITION_CONFLICT",
            "SUCCESS_AND_FAILURE_SIGNAL_CONFLICT",
        }.issubset(conditions))
        self.assertTrue(out["conflicting_evidence_preserves_unknown"])
        self.assertTrue(out["incomplete_evidence_preserves_unknown"])
        self.assertTrue(out["stale_evidence_preserves_unknown"])
        self.assertTrue(out["unauthenticated_evidence_preserves_unknown"])
        self.assert_no_authority(out)

    def test_authoritative_evidence_classes_are_explicit(self):
        out = reconciliation.build_outcome_reconciliation_contract(
            outcome_receipt_review=approved_outcome_receipt_review(),
        )
        classes = set(out["authoritative_evidence_classes"])
        self.assertTrue({
            "PROVIDER_AUTHORITATIVE_OPERATION_STATUS",
            "PROVIDER_AUTHORITATIVE_REQUEST_LOOKUP",
            "PROVIDER_SIGNED_EVENT_OR_RECEIPT",
            "EFFECT_SIDE_AUTHORITATIVE_READBACK",
            "IMMUTABLE_DOWNSTREAM_AUDIT_RECORD",
        }.issubset(classes))
        self.assert_no_authority(out)

    def test_reconciliation_evidence_binds_original_unknown_identity(self):
        out = reconciliation.build_outcome_reconciliation_contract(
            outcome_receipt_review=approved_outcome_receipt_review(),
        )
        evidence = set(out["required_reconciliation_evidence"])
        self.assertTrue({
            "ORIGINAL_OUTCOME_RECEIPT_DIGEST",
            "ORIGINAL_OUTCOME_STATE_IS_OUTCOME_UNKNOWN",
            "RECONCILIATION_AUTHORIZATION_DIGEST",
            "PROVIDER_IDENTITY_MATCH",
            "PROVIDER_ADAPTER_DIGEST_MATCH",
            "CAPABILITY_BINDING_MATCH",
            "EXECUTION_ID_MATCH",
            "TRACE_ID_MATCH",
            "PROVIDER_REQUEST_CORRELATION_MATCH",
            "IDEMPOTENCY_KEY_MATCH",
            "EFFECT_KEY_MATCH",
            "EVIDENCE_SOURCE_ATTESTED",
            "EVIDENCE_SCHEMA_VALID",
            "EVIDENCE_AUTHENTICITY_POLICY_SATISFIED",
            "EVIDENCE_FRESHNESS_POLICY_SATISFIED",
            "EVIDENCE_SEQUENCE_OR_VERSION_MONOTONIC",
            "EVIDENCE_DIGEST_BOUND",
        }.issubset(evidence))
        self.assert_no_authority(out)

    def test_reconciliation_never_retries_or_rewrites_history(self):
        out = reconciliation.build_outcome_reconciliation_contract(
            outcome_receipt_review=approved_outcome_receipt_review(),
        )
        rules = set(out["required_reconciliation_rules"])
        self.assertTrue({
            "ORIGINAL_OUTCOME_RECEIPT_IMMUTABLE",
            "RECONCILIATION_RECORD_APPEND_ONLY",
            "RECONCILIATION_IS_NOT_RETRY",
            "RECONCILIATION_IS_NOT_EXTERNAL_EFFECT_REPLAY",
            "SEPARATE_RECONCILIATION_AUTHORIZATION_REQUIRED",
            "AUTHORIZATION_REUSE_FORBIDDEN",
            "CONFLICTING_EVIDENCE_PRESERVES_UNKNOWN",
            "UNKNOWN_CANNOT_BE_COERCED_TO_SUCCESS",
            "UNKNOWN_CANNOT_BE_COERCED_TO_FAILURE",
            "STILL_UNKNOWN_AUTOMATIC_RETRY_FORBIDDEN",
        }.issubset(rules))
        self.assertFalse(out["reconciliation_is_retry"])
        self.assertFalse(out["reconciliation_replays_external_effect"])
        self.assertFalse(out["authorization_reuse_allowed"])
        self.assert_no_authority(out)

    def test_new_attempt_requires_no_effect_fresh_auth_and_new_dispatch(self):
        out = reconciliation.build_outcome_reconciliation_contract(
            outcome_receipt_review=approved_outcome_receipt_review(),
        )
        self.assertTrue(out["confirmed_no_effect_required_for_new_attempt"])
        self.assertTrue(out["fresh_owner_authorization_for_new_attempt_required"])
        self.assertTrue(out["new_durable_dispatch_for_new_attempt_required"])
        self.assertTrue(out["new_call_boundary_for_new_attempt_required"])
        self.assertFalse(out["new_attempt_authorized"])
        self.assertFalse(out["retry_authorized"])
        self.assert_no_authority(out)

    def test_bindings_preserve_full_chain_of_custody(self):
        out = reconciliation.build_outcome_reconciliation_contract(
            outcome_receipt_review=approved_outcome_receipt_review(),
        )
        fields = set(out["required_reconciliation_bindings"])
        self.assertTrue({
            "original_outcome_receipt_digest",
            "execution_id",
            "durable_dispatch_record_digest",
            "external_effect_call_boundary_digest",
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
            "reconciliation_evidence_set_digest",
            "expected_postcondition_digest",
            "rollback_plan_digest",
            "finops_estimate_digest",
            "finops_observation_digest",
            "observability_trace_id",
        }.issubset(fields))
        self.assert_no_authority(out)

    def test_contract_does_not_query_persist_retry_or_execute(self):
        out = reconciliation.build_outcome_reconciliation_contract(
            outcome_receipt_review=approved_outcome_receipt_review(),
        )
        for key in (
            "reconciliation_authorized",
            "reconciliation_performed",
            "reconciliation_record_persisted",
            "evidence_loaded",
            "evidence_queried",
            "provider_status_queried",
            "network_called",
            "provider_called",
            "original_receipt_mutated",
            "success_reconciled",
            "terminal_failure_reconciled",
            "still_unknown_recorded",
            "retry_authorized",
            "retry_performed",
            "new_attempt_authorized",
            "external_effect_attempted",
            "external_action_executed",
        ):
            self.assertFalse(out[key], key)
        self.assert_no_authority(out)

    def test_next_step_is_execution_finalization_design_only(self):
        out = reconciliation.build_outcome_reconciliation_contract(
            outcome_receipt_review=approved_outcome_receipt_review(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_EXECUTION_FINALIZATION_CONTRACT_ONLY",
        )
        self.assertFalse(out["execution_allowed"])
        self.assertFalse(out["external_action_executed"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
