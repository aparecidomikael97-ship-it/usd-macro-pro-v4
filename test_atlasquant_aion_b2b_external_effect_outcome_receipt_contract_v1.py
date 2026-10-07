from __future__ import annotations

import unittest

import atlasquant_aion_b2b_external_effect_call_boundary_contract_v1 as boundary
import atlasquant_aion_b2b_external_effect_outcome_receipt_contract_v1 as receipt
from test_atlasquant_aion_b2b_external_effect_call_boundary_contract_v1 import (
    approved_dispatch_review,
)


def approved_call_boundary_review():
    return boundary.build_external_effect_call_boundary_contract(
        durable_dispatch_record_review=approved_dispatch_review(),
    )


class ExternalEffectOutcomeReceiptContractV1Tests(unittest.TestCase):
    def assert_no_authority(self, out):
        for key in receipt.FALSE_FIELDS:
            self.assertIs(out[key], False, key)

    def test_approved_call_boundary_unlocks_design_only(self):
        out = receipt.build_external_effect_outcome_receipt_contract(
            external_effect_call_boundary_review=approved_call_boundary_review(),
        )
        self.assertEqual(out["state"], receipt.READY)
        self.assertTrue(out["external_effect_outcome_receipt_design_only"])
        self.assertEqual(
            out["receipt_mode"],
            "IMMUTABLE_PROVIDER_OUTCOME_CLASSIFICATION",
        )
        self.assertTrue(out["immutable_receipt_required"])
        self.assertTrue(out["append_only_receipt_required"])
        self.assertEqual(out["finops_cap_cents"], 20000)
        self.assertEqual(out["next_allowed_step"], receipt.NEXT_ALLOWED_STEP)
        self.assert_no_authority(out)

    def test_boundary_must_be_exact_ready_state(self):
        row = approved_call_boundary_review()
        row["state"] = "BLOCKED"
        out = receipt.build_external_effect_outcome_receipt_contract(
            external_effect_call_boundary_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXTERNAL_EFFECT_CALL_BOUNDARY_DESIGN_REVIEW_REQUIRED",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_upstream_effect_flip_blocks(self):
        row = approved_call_boundary_review()
        row["provider_called"] = True
        out = receipt.build_external_effect_outcome_receipt_contract(
            external_effect_call_boundary_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXTERNAL_EFFECT_CALL_BOUNDARY_UNSAFE_FIELD:provider_called",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_missing_unknown_semantics_blocks(self):
        row = approved_call_boundary_review()
        row["post_record_ambiguity_requires_outcome_unknown"] = False
        out = receipt.build_external_effect_outcome_receipt_contract(
            external_effect_call_boundary_review=row,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "OUTCOME_UNKNOWN_CLASSIFICATION_REQUIRED",
            out["blockers"],
        )
        self.assert_no_authority(out)

    def test_outcome_state_model_is_closed_and_explicit(self):
        out = receipt.build_external_effect_outcome_receipt_contract(
            external_effect_call_boundary_review=approved_call_boundary_review(),
        )
        self.assertEqual(
            tuple(out["outcome_states"]),
            (
                "CONFIRMED_SUCCESS",
                "CONFIRMED_TERMINAL_FAILURE",
                "OUTCOME_UNKNOWN",
            ),
        )
        self.assert_no_authority(out)

    def test_ambiguity_never_infers_success_or_failure(self):
        out = receipt.build_external_effect_outcome_receipt_contract(
            external_effect_call_boundary_review=approved_call_boundary_review(),
        )
        triggers = set(out["ambiguity_triggers"])
        self.assertTrue({
            "TIMEOUT_AFTER_DISPATCH",
            "CONNECTION_RESET_AFTER_DISPATCH",
            "PROCESS_CRASH_AFTER_DISPATCH",
            "MISSING_PROVIDER_ACK",
            "MALFORMED_PROVIDER_ACK",
            "AMBIGUOUS_PROVIDER_ACK",
            "RESPONSE_CORRELATION_MISMATCH",
            "RESPONSE_AUTHENTICITY_UNVERIFIED",
            "DUPLICATE_PROVIDER_RESPONSE_CONFLICT",
            "EFFECT_CONFIRMATION_EVIDENCE_INCOMPLETE",
        }.issubset(triggers))
        self.assertTrue(out["ambiguity_maps_to_outcome_unknown"])
        self.assertTrue(out["absence_of_error_is_success_forbidden"])
        self.assertTrue(out["absence_of_response_is_failure_forbidden"])
        self.assert_no_authority(out)

    def test_success_requires_complete_positive_evidence(self):
        out = receipt.build_external_effect_outcome_receipt_contract(
            external_effect_call_boundary_review=approved_call_boundary_review(),
        )
        required = set(out["success_evidence_requirements"])
        self.assertTrue({
            "PROVIDER_IDENTITY_MATCH",
            "PROVIDER_ADAPTER_DIGEST_MATCH",
            "CAPABILITY_BINDING_MATCH",
            "EXECUTION_ID_MATCH",
            "TRACE_ID_MATCH",
            "PROVIDER_REQUEST_CORRELATION_MATCH",
            "IDEMPOTENCY_KEY_MATCH",
            "EFFECT_KEY_MATCH",
            "RESPONSE_SCHEMA_VALID",
            "RESPONSE_AUTHENTICITY_POLICY_SATISFIED",
            "PROVIDER_SUCCESS_SEMANTICS_ATTESTED",
            "EFFECT_CONFIRMATION_EVIDENCE_COMPLETE",
            "EXPECTED_POSTCONDITION_EVIDENCE_MATCH",
        }.issubset(required))
        self.assert_no_authority(out)

    def test_terminal_failure_requires_authoritative_no_effect_evidence(self):
        out = receipt.build_external_effect_outcome_receipt_contract(
            external_effect_call_boundary_review=approved_call_boundary_review(),
        )
        required = set(out["terminal_failure_evidence_requirements"])
        self.assertTrue({
            "PROVIDER_IDENTITY_MATCH",
            "PROVIDER_REQUEST_CORRELATION_MATCH",
            "RESPONSE_SCHEMA_VALID",
            "RESPONSE_AUTHENTICITY_POLICY_SATISFIED",
            "PROVIDER_TERMINAL_FAILURE_SEMANTICS_ATTESTED",
            "NO_EFFECT_OR_TERMINAL_REJECTION_EVIDENCE_COMPLETE",
        }.issubset(required))
        self.assert_no_authority(out)

    def test_unknown_is_immutable_and_never_auto_retried(self):
        out = receipt.build_external_effect_outcome_receipt_contract(
            external_effect_call_boundary_review=approved_call_boundary_review(),
        )
        rules = set(out["required_receipt_rules"])
        self.assertTrue({
            "OUTCOME_UNKNOWN_RECEIPT_IMMUTABLE",
            "OUTCOME_UNKNOWN_AUTOMATIC_RETRY_FORBIDDEN",
            "OUTCOME_UNKNOWN_REQUIRES_EXPLICIT_RECONCILIATION",
            "RECONCILIATION_PRODUCES_SEPARATE_RECORD",
            "RECONCILIATION_REQUIRES_EVIDENCE",
            "RECONCILIATION_REQUIRES_SEPARATE_AUTHORIZATION",
            "NEW_ATTEMPT_REQUIRES_FRESH_AUTHORIZATION_AND_NEW_DISPATCH",
        }.issubset(rules))
        self.assertTrue(out["automatic_retry_after_unknown_forbidden"])
        self.assertTrue(out["fresh_authorization_for_new_attempt_required"])
        self.assertTrue(out["new_dispatch_for_new_attempt_required"])
        self.assert_no_authority(out)

    def test_receipt_bindings_preserve_exact_effect_identity(self):
        out = receipt.build_external_effect_outcome_receipt_contract(
            external_effect_call_boundary_review=approved_call_boundary_review(),
        )
        fields = set(out["required_receipt_bindings"])
        self.assertTrue({
            "execution_id",
            "durable_dispatch_record_digest",
            "external_effect_call_boundary_digest",
            "fresh_owner_authorization_digest",
            "provider_adapter_attestation_digest",
            "provider_capability_binding_digest",
            "provider_identity_ref",
            "provider_adapter_digest",
            "endpoint_reference_digest",
            "credential_reference_digest",
            "payload_digest",
            "idempotency_key_digest",
            "effect_key_digest",
            "provider_request_correlation_digest",
            "provider_response_evidence_digest",
            "expected_postcondition_digest",
            "rollback_plan_digest",
            "finops_estimate_digest",
            "finops_observation_digest",
            "observability_trace_id",
        }.issubset(fields))
        self.assert_no_authority(out)

    def test_receipt_design_contains_no_live_secrets_or_payload(self):
        out = receipt.build_external_effect_outcome_receipt_contract(
            external_effect_call_boundary_review=approved_call_boundary_review(),
        )
        forbidden = set(out["forbidden_receipt_material"])
        self.assertTrue({
            "credential_value",
            "secret_value",
            "api_key_value",
            "access_token_value",
            "private_key_value",
            "authorization_header_value",
            "payload_body_value",
            "raw_provider_response_body",
            "shell_command_value",
        }.issubset(forbidden))
        self.assert_no_authority(out)

    def test_contract_does_not_observe_execute_persist_or_reconcile(self):
        out = receipt.build_external_effect_outcome_receipt_contract(
            external_effect_call_boundary_review=approved_call_boundary_review(),
        )
        for key in (
            "outcome_classified",
            "success_confirmed",
            "terminal_failure_confirmed",
            "outcome_unknown_recorded",
            "receipt_persisted",
            "network_called",
            "provider_called",
            "provider_request_sent",
            "provider_response_received",
            "external_effect_attempted",
            "external_action_executed",
            "retry_performed",
            "reconciliation_performed",
        ):
            self.assertFalse(out[key], key)
        self.assert_no_authority(out)

    def test_next_step_is_reconciliation_design_only(self):
        out = receipt.build_external_effect_outcome_receipt_contract(
            external_effect_call_boundary_review=approved_call_boundary_review(),
        )
        self.assertEqual(
            out["next_allowed_step"],
            "DESIGN_OUTCOME_RECONCILIATION_CONTRACT_ONLY",
        )
        self.assertFalse(out["execution_allowed"])
        self.assertFalse(out["external_action_executed"])
        self.assert_no_authority(out)


if __name__ == "__main__":
    unittest.main()
