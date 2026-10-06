"""AION B2B execution finalization contract V1.

Design-only, fail-closed and non-executable.

This layer defines when a future B2B execution may be considered terminally
closed after external-effect outcome classification and, when necessary,
OUTCOME_UNKNOWN reconciliation.

Only authoritative terminal evidence may permit finalization. Unknown,
conflicting, stale, incomplete or unauthenticated evidence must keep the
execution non-finalized. Finalization never retries, replays, reconciles,
compensates or performs an external effect.

Permitted future terminal closures:
- FINALIZED_SUCCESS;
- FINALIZED_TERMINAL_FAILURE.

OUTCOME_UNKNOWN and STILL_OUTCOME_UNKNOWN are never finalizable.

A success closure requires positive effect/postcondition evidence. A terminal
failure closure requires authoritative no-effect/terminal-rejection evidence,
or an already-settled rollback/compensation chain when policy requires it.

This module does NOT persist final state, query a provider, open network
transport, load secrets, retry, reconcile, compensate, bill, contact customers,
write CRM, provision, deploy or mutate production.

Maximum positive state:
READY_FOR_EXECUTION_FINALIZATION_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_outcome_reconciliation_contract_v1 as reconciliation

SCHEMA = "ATLASQUANT_AION_B2B_EXECUTION_FINALIZATION_CONTRACT_V1"
READY = "READY_FOR_EXECUTION_FINALIZATION_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_EXECUTION_FINALIZATION_PERSISTENCE_CONTRACT_ONLY"

FINALIZATION_MODE = "TERMINAL_EVIDENCE_ONLY_CLOSURE"
FINOPS_CAP_CENTS_REQUIRED = 20000

FINALIZABLE_OUTCOME_STATES = (
    "CONFIRMED_SUCCESS",
    "CONFIRMED_TERMINAL_FAILURE",
    "RECONCILED_CONFIRMED_SUCCESS",
    "RECONCILED_CONFIRMED_TERMINAL_FAILURE",
)

NON_FINALIZABLE_OUTCOME_STATES = (
    "OUTCOME_UNKNOWN",
    "STILL_OUTCOME_UNKNOWN",
)

FINAL_EXECUTION_STATES = (
    "FINALIZED_SUCCESS",
    "FINALIZED_TERMINAL_FAILURE",
)

REQUIRED_SUCCESS_FINALIZATION_EVIDENCE = (
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
)

REQUIRED_FAILURE_FINALIZATION_EVIDENCE = (
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
)

FINALIZATION_BLOCKERS = (
    "OUTCOME_UNKNOWN",
    "STILL_OUTCOME_UNKNOWN",
    "MISSING_TERMINAL_EVIDENCE",
    "INCOMPLETE_TERMINAL_EVIDENCE",
    "UNAUTHENTICATED_TERMINAL_EVIDENCE",
    "STALE_TERMINAL_EVIDENCE",
    "CONFLICTING_TERMINAL_EVIDENCE",
    "EXECUTION_ID_MISMATCH",
    "TRACE_ID_MISMATCH",
    "IDEMPOTENCY_KEY_MISMATCH",
    "EFFECT_KEY_MISMATCH",
    "PROVIDER_CORRELATION_MISMATCH",
    "POSTCONDITION_NOT_CONFIRMED",
    "PENDING_RECONCILIATION",
    "PENDING_ROLLBACK",
    "PENDING_COMPENSATION",
    "ROLLBACK_OR_COMPENSATION_FAILED",
    "FINOPS_POLICY_UNSETTLED",
    "AUDIT_CHAIN_INCOMPLETE",
)

REQUIRED_FINALIZATION_RULES = (
    "FINALIZATION_REQUIRES_TERMINAL_EVIDENCE",
    "UNKNOWN_OUTCOME_CANNOT_BE_FINALIZED",
    "STILL_UNKNOWN_OUTCOME_CANNOT_BE_FINALIZED",
    "FINALIZATION_IS_NOT_RETRY",
    "FINALIZATION_IS_NOT_RECONCILIATION",
    "FINALIZATION_IS_NOT_ROLLBACK",
    "FINALIZATION_IS_NOT_COMPENSATION",
    "FINALIZATION_IS_NOT_EXTERNAL_EFFECT_REPLAY",
    "ORIGINAL_OUTCOME_RECEIPT_IMMUTABLE",
    "RECONCILIATION_RECORD_IMMUTABLE",
    "FINALIZATION_RECORD_APPEND_ONLY",
    "SUCCESS_REQUIRES_POSITIVE_EFFECT_EVIDENCE",
    "SUCCESS_REQUIRES_POSTCONDITION_EVIDENCE",
    "TERMINAL_FAILURE_REQUIRES_AUTHORITATIVE_NO_EFFECT_OR_REJECTION_EVIDENCE",
    "PENDING_RECONCILIATION_BLOCKS_FINALIZATION",
    "PENDING_ROLLBACK_BLOCKS_FINALIZATION",
    "PENDING_COMPENSATION_BLOCKS_FINALIZATION",
    "FAILED_ROLLBACK_OR_COMPENSATION_BLOCKS_FINALIZATION",
    "CAPABILITY_SCOPE_CANNOT_EXPAND_DURING_FINALIZATION",
    "FINOPS_CEILING_CANNOT_EXPAND_DURING_FINALIZATION",
    "FINALIZATION_CANNOT_CREATE_NEW_EXECUTION_AUTHORITY",
)

REQUIRED_FINALIZATION_BINDINGS = (
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
    "before_state_digest",
    "expected_postcondition_digest",
    "rollback_plan_digest",
    "rollback_or_compensation_settlement_digest",
    "finops_estimate_digest",
    "finops_observation_digest",
    "observability_trace_id",
    "audit_chain_digest",
)

FORBIDDEN_FINALIZATION_MATERIAL = (
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
    "rollback_command_value",
    "compensation_command_value",
)

FALSE_FIELDS = (
    "finalization_verified",
    "finalization_authorized",
    "finalization_performed",
    "finalization_record_persisted",
    "execution_finalized",
    "success_finalized",
    "terminal_failure_finalized",
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
    "outcome_receipt_mutated",
    "reconciliation_record_mutated",
    "retry_authorized",
    "retry_scheduled",
    "retry_performed",
    "reconciliation_authorized",
    "reconciliation_performed",
    "rollback_authorized",
    "rollback_performed",
    "compensation_authorized",
    "compensation_performed",
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


def build_execution_finalization_contract(
    *,
    outcome_reconciliation_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define terminal execution closure semantics; finalize nothing."""
    row = (
        dict(outcome_reconciliation_review)
        if isinstance(outcome_reconciliation_review, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != reconciliation.SCHEMA:
        blockers.append("OUTCOME_RECONCILIATION_SCHEMA_REQUIRED")
    if row.get("state") != reconciliation.READY:
        blockers.append("OUTCOME_RECONCILIATION_DESIGN_REVIEW_REQUIRED")
    if row.get("outcome_reconciliation_design_only") is not True:
        blockers.append("OUTCOME_RECONCILIATION_NOT_DESIGN_ONLY")
    if row.get("fail_closed") is not True:
        blockers.append("FAIL_CLOSED_RECONCILIATION_REQUIRED")
    if row.get("original_receipt_immutable") is not True:
        blockers.append("ORIGINAL_RECEIPT_IMMUTABILITY_REQUIRED")
    if row.get("separate_reconciliation_record_required") is not True:
        blockers.append("SEPARATE_RECONCILIATION_RECORD_REQUIRED")
    if row.get("append_only_reconciliation_record_required") is not True:
        blockers.append("APPEND_ONLY_RECONCILIATION_RECORD_REQUIRED")
    if row.get("reconciliation_is_retry") is not False:
        blockers.append("RECONCILIATION_MUST_NOT_BE_RETRY")
    if row.get("reconciliation_replays_external_effect") is not False:
        blockers.append("RECONCILIATION_MUST_NOT_REPLAY_EFFECT")
    if row.get("automatic_retry_after_still_unknown_forbidden") is not True:
        blockers.append("STILL_UNKNOWN_AUTOMATIC_RETRY_MUST_BE_FORBIDDEN")
    if row.get("confirmed_no_effect_required_for_new_attempt") is not True:
        blockers.append("CONFIRMED_NO_EFFECT_FOR_NEW_ATTEMPT_REQUIRED")
    if row.get("fresh_owner_authorization_for_new_attempt_required") is not True:
        blockers.append("FRESH_OWNER_AUTHORIZATION_FOR_NEW_ATTEMPT_REQUIRED")
    if row.get("new_durable_dispatch_for_new_attempt_required") is not True:
        blockers.append("NEW_DURABLE_DISPATCH_FOR_NEW_ATTEMPT_REQUIRED")
    if row.get("finops_cap_cents") != FINOPS_CAP_CENTS_REQUIRED:
        blockers.append("FINOPS_CAP_MUST_REMAIN_20000_CENTS")
    if row.get("next_allowed_step") != reconciliation.NEXT_ALLOWED_STEP:
        blockers.append("OUTCOME_RECONCILIATION_NEXT_STEP_INVALID")

    for key in reconciliation.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("OUTCOME_RECONCILIATION_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            execution_finalization_design_only=True,
            finalization_mode=FINALIZATION_MODE,
            fail_closed=True,
            terminal_evidence_required=True,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        execution_finalization_design_only=True,
        finalization_mode=FINALIZATION_MODE,
        fail_closed=True,
        provider_neutral=True,
        terminal_evidence_required=True,
        unknown_outcome_finalization_forbidden=True,
        still_unknown_outcome_finalization_forbidden=True,
        append_only_finalization_record_required=True,
        original_outcome_receipt_immutable=True,
        reconciliation_record_immutable=True,
        success_requires_positive_effect_evidence=True,
        success_requires_postcondition_evidence=True,
        terminal_failure_requires_authoritative_no_effect_or_rejection_evidence=True,
        pending_reconciliation_blocks_finalization=True,
        pending_rollback_blocks_finalization=True,
        pending_compensation_blocks_finalization=True,
        failed_rollback_or_compensation_blocks_finalization=True,
        finalization_creates_execution_authority=False,
        retry_allowed_by_finalization=False,
        reconciliation_allowed_by_finalization=False,
        rollback_allowed_by_finalization=False,
        compensation_allowed_by_finalization=False,
        finops_cap_cents=FINOPS_CAP_CENTS_REQUIRED,
        finalizable_outcome_states=FINALIZABLE_OUTCOME_STATES,
        non_finalizable_outcome_states=NON_FINALIZABLE_OUTCOME_STATES,
        final_execution_states=FINAL_EXECUTION_STATES,
        required_success_finalization_evidence=REQUIRED_SUCCESS_FINALIZATION_EVIDENCE,
        required_failure_finalization_evidence=REQUIRED_FAILURE_FINALIZATION_EVIDENCE,
        finalization_blockers=FINALIZATION_BLOCKERS,
        required_finalization_rules=REQUIRED_FINALIZATION_RULES,
        required_finalization_bindings=REQUIRED_FINALIZATION_BINDINGS,
        forbidden_finalization_material=FORBIDDEN_FINALIZATION_MATERIAL,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "FINALIZATION_MODE",
    "FINOPS_CAP_CENTS_REQUIRED",
    "FINALIZABLE_OUTCOME_STATES",
    "NON_FINALIZABLE_OUTCOME_STATES",
    "FINAL_EXECUTION_STATES",
    "REQUIRED_SUCCESS_FINALIZATION_EVIDENCE",
    "REQUIRED_FAILURE_FINALIZATION_EVIDENCE",
    "FINALIZATION_BLOCKERS",
    "REQUIRED_FINALIZATION_RULES",
    "REQUIRED_FINALIZATION_BINDINGS",
    "FORBIDDEN_FINALIZATION_MATERIAL",
    "FALSE_FIELDS",
    "build_execution_finalization_contract",
]
