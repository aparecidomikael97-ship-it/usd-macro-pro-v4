"""AION B2B outcome reconciliation contract V1.

Design-only, fail-closed and non-executable.

This layer defines how a future AION runtime may reconcile an already-recorded
OUTCOME_UNKNOWN external-effect receipt without rewriting history and without
replaying the external effect.

Reconciliation is a separate, evidence-bound ceremony. It may only classify the
unknown outcome as:
- RECONCILED_CONFIRMED_SUCCESS;
- RECONCILED_CONFIRMED_TERMINAL_FAILURE;
- STILL_OUTCOME_UNKNOWN.

Conflicting, stale, unauthenticated, weakly correlated or incomplete evidence
must remain STILL_OUTCOME_UNKNOWN. Reconciliation never authorizes retry. A new
attempt, when policy permits it, requires evidence that no effect occurred,
fresh owner authorization and a new durable dispatch record.

This module does NOT query a provider, open a socket, load credentials, inspect
live production, mutate the original receipt, retry, execute an external effect,
bill, contact a customer, write CRM, provision, deploy or mutate production.

Maximum positive state:
READY_FOR_OUTCOME_RECONCILIATION_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_external_effect_outcome_receipt_contract_v1 as outcome

SCHEMA = "ATLASQUANT_AION_B2B_OUTCOME_RECONCILIATION_CONTRACT_V1"
READY = "READY_FOR_OUTCOME_RECONCILIATION_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_EXECUTION_FINALIZATION_CONTRACT_ONLY"

RECONCILIATION_MODE = "SEPARATE_EVIDENCE_BOUND_UNKNOWN_RESOLUTION"
FINOPS_CAP_CENTS_REQUIRED = 20000

RECONCILIATION_STATES = (
    "RECONCILED_CONFIRMED_SUCCESS",
    "RECONCILED_CONFIRMED_TERMINAL_FAILURE",
    "STILL_OUTCOME_UNKNOWN",
)

REQUIRED_RECONCILIATION_EVIDENCE = (
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
    "EXPECTED_POSTCONDITION_CONTEXT_BOUND",
    "ROLLBACK_PLAN_CONTEXT_BOUND",
    "FINOPS_CONTEXT_BOUND",
)

AUTHORITATIVE_EVIDENCE_CLASSES = (
    "PROVIDER_AUTHORITATIVE_OPERATION_STATUS",
    "PROVIDER_AUTHORITATIVE_REQUEST_LOOKUP",
    "PROVIDER_SIGNED_EVENT_OR_RECEIPT",
    "EFFECT_SIDE_AUTHORITATIVE_READBACK",
    "IMMUTABLE_DOWNSTREAM_AUDIT_RECORD",
)

UNKNOWN_PRESERVING_CONDITIONS = (
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
)

REQUIRED_RECONCILIATION_RULES = (
    "ORIGINAL_OUTCOME_RECEIPT_IMMUTABLE",
    "RECONCILIATION_RECORD_APPEND_ONLY",
    "RECONCILIATION_IS_NOT_RETRY",
    "RECONCILIATION_IS_NOT_EXTERNAL_EFFECT_REPLAY",
    "SEPARATE_RECONCILIATION_AUTHORIZATION_REQUIRED",
    "AUTHORIZATION_REUSE_FORBIDDEN",
    "AUTHORITATIVE_EVIDENCE_REQUIRED",
    "MULTIPLE_EVIDENCE_SOURCES_MAY_BE_REQUIRED_BY_POLICY",
    "CONFLICTING_EVIDENCE_PRESERVES_UNKNOWN",
    "INCOMPLETE_EVIDENCE_PRESERVES_UNKNOWN",
    "STALE_EVIDENCE_PRESERVES_UNKNOWN",
    "UNAUTHENTICATED_EVIDENCE_PRESERVES_UNKNOWN",
    "UNKNOWN_CANNOT_BE_COERCED_TO_SUCCESS",
    "UNKNOWN_CANNOT_BE_COERCED_TO_FAILURE",
    "RECONCILED_SUCCESS_REQUIRES_COMPLETE_POSITIVE_EVIDENCE",
    "RECONCILED_TERMINAL_FAILURE_REQUIRES_AUTHORITATIVE_NO_EFFECT_OR_TERMINAL_REJECTION_EVIDENCE",
    "STILL_UNKNOWN_AUTOMATIC_RETRY_FORBIDDEN",
    "NEW_ATTEMPT_REQUIRES_CONFIRMED_NO_EFFECT",
    "NEW_ATTEMPT_REQUIRES_FRESH_OWNER_AUTHORIZATION",
    "NEW_ATTEMPT_REQUIRES_NEW_DURABLE_DISPATCH",
    "NEW_ATTEMPT_REQUIRES_NEW_CALL_BOUNDARY",
    "FINOPS_CEILING_CANNOT_EXPAND_DURING_RECONCILIATION",
    "CAPABILITY_SCOPE_CANNOT_EXPAND_DURING_RECONCILIATION",
)

REQUIRED_RECONCILIATION_BINDINGS = (
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
)

FORBIDDEN_RECONCILIATION_MATERIAL = (
    "credential_value",
    "secret_value",
    "password_value",
    "api_key_value",
    "access_token_value",
    "refresh_token_value",
    "private_key_value",
    "authorization_header_value",
    "cookie_value",
    "payload_body_value",
    "raw_provider_response_body",
    "shell_command_value",
    "retry_command_value",
)

FALSE_FIELDS = (
    "reconciliation_verified",
    "reconciliation_authorized",
    "reconciliation_performed",
    "reconciliation_record_persisted",
    "evidence_loaded",
    "evidence_queried",
    "provider_status_queried",
    "provider_selected",
    "provider_bound",
    "adapter_loaded",
    "endpoint_resolved",
    "credentials_loaded",
    "secrets_loaded",
    "transport_opened",
    "socket_opened",
    "network_called",
    "provider_called",
    "provider_request_sent",
    "provider_response_received",
    "original_receipt_mutated",
    "success_reconciled",
    "terminal_failure_reconciled",
    "still_unknown_recorded",
    "retry_authorized",
    "retry_scheduled",
    "retry_performed",
    "new_attempt_authorized",
    "external_effect_attempted",
    "external_action_executed",
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


def build_outcome_reconciliation_contract(
    *,
    outcome_receipt_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define reconciliation semantics; query or mutate nothing."""
    row = (
        dict(outcome_receipt_review)
        if isinstance(outcome_receipt_review, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != outcome.SCHEMA:
        blockers.append("OUTCOME_RECEIPT_SCHEMA_REQUIRED")
    if row.get("state") != outcome.READY:
        blockers.append("OUTCOME_RECEIPT_DESIGN_REVIEW_REQUIRED")
    if row.get("external_effect_outcome_receipt_design_only") is not True:
        blockers.append("OUTCOME_RECEIPT_NOT_DESIGN_ONLY")
    if row.get("fail_closed") is not True:
        blockers.append("FAIL_CLOSED_OUTCOME_RECEIPT_REQUIRED")
    if row.get("immutable_receipt_required") is not True:
        blockers.append("IMMUTABLE_OUTCOME_RECEIPT_REQUIRED")
    if row.get("append_only_receipt_required") is not True:
        blockers.append("APPEND_ONLY_OUTCOME_RECEIPT_REQUIRED")
    if row.get("ambiguity_maps_to_outcome_unknown") is not True:
        blockers.append("OUTCOME_UNKNOWN_MAPPING_REQUIRED")
    if row.get("automatic_retry_after_unknown_forbidden") is not True:
        blockers.append("UNKNOWN_AUTOMATIC_RETRY_MUST_BE_FORBIDDEN")
    if row.get("explicit_reconciliation_required") is not True:
        blockers.append("EXPLICIT_RECONCILIATION_REQUIRED")
    if row.get("reconciliation_produces_separate_record") is not True:
        blockers.append("SEPARATE_RECONCILIATION_RECORD_REQUIRED")
    if row.get("reconciliation_evidence_required") is not True:
        blockers.append("RECONCILIATION_EVIDENCE_REQUIRED")
    if row.get("separate_reconciliation_authorization_required") is not True:
        blockers.append("SEPARATE_RECONCILIATION_AUTHORIZATION_REQUIRED")
    if row.get("fresh_authorization_for_new_attempt_required") is not True:
        blockers.append("FRESH_AUTHORIZATION_FOR_NEW_ATTEMPT_REQUIRED")
    if row.get("new_dispatch_for_new_attempt_required") is not True:
        blockers.append("NEW_DISPATCH_FOR_NEW_ATTEMPT_REQUIRED")
    if row.get("finops_cap_cents") != FINOPS_CAP_CENTS_REQUIRED:
        blockers.append("FINOPS_CAP_MUST_REMAIN_20000_CENTS")
    if row.get("next_allowed_step") != outcome.NEXT_ALLOWED_STEP:
        blockers.append("OUTCOME_RECEIPT_NEXT_STEP_INVALID")

    for key in outcome.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("OUTCOME_RECEIPT_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            outcome_reconciliation_design_only=True,
            reconciliation_mode=RECONCILIATION_MODE,
            fail_closed=True,
            original_receipt_immutable=True,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        outcome_reconciliation_design_only=True,
        reconciliation_mode=RECONCILIATION_MODE,
        fail_closed=True,
        provider_neutral=True,
        original_receipt_immutable=True,
        separate_reconciliation_record_required=True,
        append_only_reconciliation_record_required=True,
        reconciliation_is_retry=False,
        reconciliation_replays_external_effect=False,
        separate_reconciliation_authorization_required=True,
        authorization_reuse_allowed=False,
        authoritative_evidence_required=True,
        conflicting_evidence_preserves_unknown=True,
        incomplete_evidence_preserves_unknown=True,
        stale_evidence_preserves_unknown=True,
        unauthenticated_evidence_preserves_unknown=True,
        automatic_retry_after_still_unknown_forbidden=True,
        confirmed_no_effect_required_for_new_attempt=True,
        fresh_owner_authorization_for_new_attempt_required=True,
        new_durable_dispatch_for_new_attempt_required=True,
        new_call_boundary_for_new_attempt_required=True,
        finops_cap_cents=FINOPS_CAP_CENTS_REQUIRED,
        reconciliation_states=RECONCILIATION_STATES,
        required_reconciliation_evidence=REQUIRED_RECONCILIATION_EVIDENCE,
        authoritative_evidence_classes=AUTHORITATIVE_EVIDENCE_CLASSES,
        unknown_preserving_conditions=UNKNOWN_PRESERVING_CONDITIONS,
        required_reconciliation_rules=REQUIRED_RECONCILIATION_RULES,
        required_reconciliation_bindings=REQUIRED_RECONCILIATION_BINDINGS,
        forbidden_reconciliation_material=FORBIDDEN_RECONCILIATION_MATERIAL,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "RECONCILIATION_MODE",
    "FINOPS_CAP_CENTS_REQUIRED",
    "RECONCILIATION_STATES",
    "REQUIRED_RECONCILIATION_EVIDENCE",
    "AUTHORITATIVE_EVIDENCE_CLASSES",
    "UNKNOWN_PRESERVING_CONDITIONS",
    "REQUIRED_RECONCILIATION_RULES",
    "REQUIRED_RECONCILIATION_BINDINGS",
    "FORBIDDEN_RECONCILIATION_MATERIAL",
    "FALSE_FIELDS",
    "build_outcome_reconciliation_contract",
]
