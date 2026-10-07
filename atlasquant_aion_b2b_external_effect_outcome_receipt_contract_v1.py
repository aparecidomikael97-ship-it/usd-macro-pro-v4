"""AION B2B external-effect outcome receipt contract V1.

Design-only, fail-closed and non-executable.

This layer defines how a future executor must classify and bind the observable
outcome of exactly one sealed external-effect call after a durable dispatch
record. It never performs the call and never infers success from silence,
timeouts, connection resets, crashes, malformed acknowledgements or incomplete
provider evidence.

A future call outcome may be classified only as:
- CONFIRMED_SUCCESS;
- CONFIRMED_TERMINAL_FAILURE;
- OUTCOME_UNKNOWN.

OUTCOME_UNKNOWN is immutable in this receipt. Any later reconciliation must
produce a separate evidence-bound record and requires separate authorization.
Automatic retry from OUTCOME_UNKNOWN is forbidden.

This module does NOT open network transport, call a provider, read secrets,
persist a receipt, reconcile an unknown outcome, retry, bill, contact a
customer, write CRM, provision, deploy or mutate production.

Maximum positive state:
READY_FOR_EXTERNAL_EFFECT_OUTCOME_RECEIPT_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_external_effect_call_boundary_contract_v1 as boundary

SCHEMA = "ATLASQUANT_AION_B2B_EXTERNAL_EFFECT_OUTCOME_RECEIPT_CONTRACT_V1"
READY = "READY_FOR_EXTERNAL_EFFECT_OUTCOME_RECEIPT_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_OUTCOME_RECONCILIATION_CONTRACT_ONLY"

RECEIPT_MODE = "IMMUTABLE_PROVIDER_OUTCOME_CLASSIFICATION"
FINOPS_CAP_CENTS_REQUIRED = 20000

OUTCOME_STATES = (
    "CONFIRMED_SUCCESS",
    "CONFIRMED_TERMINAL_FAILURE",
    "OUTCOME_UNKNOWN",
)

AMBIGUITY_TRIGGERS = (
    "TIMEOUT_AFTER_DISPATCH",
    "CONNECTION_RESET_AFTER_DISPATCH",
    "PROCESS_CRASH_AFTER_DISPATCH",
    "MISSING_PROVIDER_ACK",
    "MALFORMED_PROVIDER_ACK",
    "AMBIGUOUS_PROVIDER_ACK",
    "RESPONSE_CORRELATION_MISMATCH",
    "RESPONSE_IDENTITY_MISMATCH",
    "RESPONSE_SCHEMA_MISMATCH",
    "RESPONSE_AUTHENTICITY_UNVERIFIED",
    "DUPLICATE_PROVIDER_RESPONSE_CONFLICT",
    "LATE_RESPONSE_WITHOUT_RECONCILIATION_CONTEXT",
    "EFFECT_CONFIRMATION_EVIDENCE_INCOMPLETE",
)

SUCCESS_EVIDENCE_REQUIREMENTS = (
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
)

TERMINAL_FAILURE_EVIDENCE_REQUIREMENTS = (
    "PROVIDER_IDENTITY_MATCH",
    "PROVIDER_REQUEST_CORRELATION_MATCH",
    "RESPONSE_SCHEMA_VALID",
    "RESPONSE_AUTHENTICITY_POLICY_SATISFIED",
    "PROVIDER_TERMINAL_FAILURE_SEMANTICS_ATTESTED",
    "NO_EFFECT_OR_TERMINAL_REJECTION_EVIDENCE_COMPLETE",
)

REQUIRED_RECEIPT_RULES = (
    "ONE_CALL_ATTEMPT_PRODUCES_AT_MOST_ONE_PRIMARY_OUTCOME_RECEIPT",
    "RECEIPT_IS_APPEND_ONLY_AND_IMMUTABLE",
    "SUCCESS_REQUIRES_COMPLETE_POSITIVE_EVIDENCE",
    "FAILURE_REQUIRES_AUTHORITATIVE_TERMINAL_EVIDENCE",
    "ABSENCE_OF_ERROR_IS_NOT_SUCCESS",
    "ABSENCE_OF_RESPONSE_IS_NOT_FAILURE",
    "AMBIGUITY_ALWAYS_CLASSIFIES_OUTCOME_UNKNOWN",
    "OUTCOME_UNKNOWN_RECEIPT_IMMUTABLE",
    "OUTCOME_UNKNOWN_AUTOMATIC_RETRY_FORBIDDEN",
    "OUTCOME_UNKNOWN_REQUIRES_EXPLICIT_RECONCILIATION",
    "RECONCILIATION_PRODUCES_SEPARATE_RECORD",
    "RECONCILIATION_REQUIRES_EVIDENCE",
    "RECONCILIATION_REQUIRES_SEPARATE_AUTHORIZATION",
    "NEW_ATTEMPT_REQUIRES_FRESH_AUTHORIZATION_AND_NEW_DISPATCH",
    "RECEIPT_CANNOT_EXPAND_CAPABILITY_SCOPE_OR_FINOPS",
    "SECRET_OR_CREDENTIAL_VALUES_FORBIDDEN",
    "RAW_PAYLOAD_BODY_FORBIDDEN",
)

REQUIRED_RECEIPT_BINDINGS = (
    "execution_id",
    "durable_dispatch_record_digest",
    "external_effect_call_boundary_digest",
    "execution_envelope_digest",
    "pre_dispatch_attestation_digest",
    "fresh_owner_authorization_digest",
    "provider_adapter_attestation_digest",
    "provider_capability_binding_digest",
    "effective_capabilities_digest",
    "provider_identity_ref",
    "provider_adapter_digest",
    "endpoint_reference_digest",
    "credential_reference_digest",
    "payload_digest",
    "idempotency_key_digest",
    "effect_key_digest",
    "provider_request_correlation_digest",
    "provider_response_evidence_digest",
    "before_state_digest",
    "expected_postcondition_digest",
    "rollback_plan_digest",
    "finops_estimate_digest",
    "finops_observation_digest",
    "observability_trace_id",
)

FORBIDDEN_RECEIPT_MATERIAL = (
    "credential_value",
    "secret_value",
    "password_value",
    "api_key_value",
    "access_token_value",
    "refresh_token_value",
    "private_key_value",
    "authorization_header_value",
    "cookie_value",
    "endpoint_value",
    "request_headers_value",
    "payload_body_value",
    "raw_provider_response_body",
    "shell_command_value",
)

FALSE_FIELDS = (
    "outcome_receipt_verified",
    "outcome_classified",
    "success_confirmed",
    "terminal_failure_confirmed",
    "outcome_unknown_recorded",
    "receipt_persisted",
    "receipt_replayed",
    "provider_selected",
    "provider_bound",
    "adapter_loaded",
    "endpoint_resolved",
    "credentials_loaded",
    "secrets_loaded",
    "payload_constructed",
    "transport_opened",
    "socket_opened",
    "network_called",
    "provider_called",
    "provider_request_sent",
    "provider_response_received",
    "provider_ack_verified",
    "external_effect_attempted",
    "external_action_executed",
    "retry_scheduled",
    "retry_performed",
    "reconciliation_performed",
    "reconciliation_authorized",
    "billing_authorized",
    "billing_executed",
    "customer_contact_authorized",
    "crm_write_authorized",
    "provisioning_authorized",
    "deploy_authorized",
    "production_mutation_authorized",
    "production_mutation_performed",
    "execution_allowed",
    "executor_created",
    "executor_selected",
    "executor_implementation_allowed",
    "execution_command_generated",
    "execution_command_executed",
    "executes_action",
)


def _result(state: str, blockers=(), **fields) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "blockers": sorted(set(blockers)),
        **fields,
        **{key: False for key in FALSE_FIELDS},
    }


def build_external_effect_outcome_receipt_contract(
    *,
    external_effect_call_boundary_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define outcome receipt semantics; observe or execute nothing."""
    row = (
        dict(external_effect_call_boundary_review)
        if isinstance(external_effect_call_boundary_review, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != boundary.SCHEMA:
        blockers.append("EXTERNAL_EFFECT_CALL_BOUNDARY_SCHEMA_REQUIRED")
    if row.get("state") != boundary.READY:
        blockers.append("EXTERNAL_EFFECT_CALL_BOUNDARY_DESIGN_REVIEW_REQUIRED")
    if row.get("external_effect_call_boundary_design_only") is not True:
        blockers.append("EXTERNAL_EFFECT_CALL_BOUNDARY_NOT_DESIGN_ONLY")
    if row.get("fail_closed") is not True:
        blockers.append("FAIL_CLOSED_BOUNDARY_REQUIRED")
    if row.get("single_sealed_call_required") is not True:
        blockers.append("SINGLE_SEALED_CALL_REQUIRED")
    if row.get("no_material_mutation_after_dispatch_record") is not True:
        blockers.append("POST_DISPATCH_IMMUTABILITY_REQUIRED")
    if row.get("provider_response_or_ambiguity_receipt_required") is not True:
        blockers.append("RESPONSE_OR_AMBIGUITY_RECEIPT_REQUIRED")
    if row.get("post_record_ambiguity_requires_outcome_unknown") is not True:
        blockers.append("OUTCOME_UNKNOWN_CLASSIFICATION_REQUIRED")
    if row.get("automatic_retry_after_dispatch_forbidden") is not True:
        blockers.append("POST_DISPATCH_AUTOMATIC_RETRY_MUST_BE_FORBIDDEN")
    if row.get("explicit_reconciliation_required") is not True:
        blockers.append("EXPLICIT_RECONCILIATION_REQUIRED")
    if row.get("reconciliation_evidence_required") is not True:
        blockers.append("RECONCILIATION_EVIDENCE_REQUIRED")
    if row.get("separate_reconciliation_authorization_required") is not True:
        blockers.append("SEPARATE_RECONCILIATION_AUTHORIZATION_REQUIRED")
    if row.get("finops_cap_cents") != FINOPS_CAP_CENTS_REQUIRED:
        blockers.append("FINOPS_CAP_MUST_REMAIN_20000_CENTS")
    if row.get("next_allowed_step") != boundary.NEXT_ALLOWED_STEP:
        blockers.append("EXTERNAL_EFFECT_CALL_BOUNDARY_NEXT_STEP_INVALID")

    for key in boundary.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("EXTERNAL_EFFECT_CALL_BOUNDARY_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            external_effect_outcome_receipt_design_only=True,
            receipt_mode=RECEIPT_MODE,
            fail_closed=True,
            immutable_receipt_required=True,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        external_effect_outcome_receipt_design_only=True,
        receipt_mode=RECEIPT_MODE,
        fail_closed=True,
        provider_neutral=True,
        immutable_receipt_required=True,
        append_only_receipt_required=True,
        positive_success_evidence_required=True,
        authoritative_terminal_failure_evidence_required=True,
        ambiguity_maps_to_outcome_unknown=True,
        absence_of_error_is_success_forbidden=True,
        absence_of_response_is_failure_forbidden=True,
        automatic_retry_after_unknown_forbidden=True,
        explicit_reconciliation_required=True,
        reconciliation_produces_separate_record=True,
        reconciliation_evidence_required=True,
        separate_reconciliation_authorization_required=True,
        fresh_authorization_for_new_attempt_required=True,
        new_dispatch_for_new_attempt_required=True,
        finops_cap_cents=FINOPS_CAP_CENTS_REQUIRED,
        outcome_states=OUTCOME_STATES,
        ambiguity_triggers=AMBIGUITY_TRIGGERS,
        success_evidence_requirements=SUCCESS_EVIDENCE_REQUIREMENTS,
        terminal_failure_evidence_requirements=TERMINAL_FAILURE_EVIDENCE_REQUIREMENTS,
        required_receipt_rules=REQUIRED_RECEIPT_RULES,
        required_receipt_bindings=REQUIRED_RECEIPT_BINDINGS,
        forbidden_receipt_material=FORBIDDEN_RECEIPT_MATERIAL,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "RECEIPT_MODE",
    "FINOPS_CAP_CENTS_REQUIRED",
    "OUTCOME_STATES",
    "AMBIGUITY_TRIGGERS",
    "SUCCESS_EVIDENCE_REQUIREMENTS",
    "TERMINAL_FAILURE_EVIDENCE_REQUIREMENTS",
    "REQUIRED_RECEIPT_RULES",
    "REQUIRED_RECEIPT_BINDINGS",
    "FORBIDDEN_RECEIPT_MATERIAL",
    "FALSE_FIELDS",
    "build_external_effect_outcome_receipt_contract",
]
