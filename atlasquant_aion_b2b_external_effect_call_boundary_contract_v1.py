"""AION B2B external-effect call boundary contract V1.

Design-only, fail-closed and non-executable.

This layer defines the final trust boundary immediately around a future provider
network call. It is intentionally stricter than dispatch planning.

The contract requires that all mutable/preparable material be resolved and
validated BEFORE the durable DISPATCH_RECORDED write. After that durable marker,
a future executor may only perform the exact sealed external call and record its
outcome. Any crash, timeout or ambiguity after DISPATCH_RECORDED is treated as
OUTCOME_UNKNOWN and cannot be automatically retried.

This module does NOT select a provider, resolve an endpoint, load credentials,
construct a payload, open a socket, call a provider, bill, contact a customer,
write CRM, provision, deploy or mutate production.

Maximum positive state:
READY_FOR_EXTERNAL_EFFECT_CALL_BOUNDARY_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_durable_dispatch_record_contract_v1 as dispatch

SCHEMA = "ATLASQUANT_AION_B2B_EXTERNAL_EFFECT_CALL_BOUNDARY_CONTRACT_V1"
READY = "READY_FOR_EXTERNAL_EFFECT_CALL_BOUNDARY_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_EXTERNAL_EFFECT_OUTCOME_RECEIPT_CONTRACT_ONLY"

BOUNDARY_MODE = "SEALED_SINGLE_CALL_AFTER_DURABLE_DISPATCH"
FINOPS_CAP_CENTS_REQUIRED = 20000

REQUIRED_PRE_RECORD_PREPARATION = (
    "PROVIDER_IDENTITY_RESOLVED_FROM_ATTESTED_REFERENCE",
    "PROVIDER_ADAPTER_VERSION_PINNED",
    "PROVIDER_ADAPTER_DIGEST_MATCH",
    "CAPABILITY_BINDING_MATCH",
    "ENDPOINT_RESOLVED_FROM_TRUSTED_PROVIDER_CONFIGURATION",
    "ENDPOINT_ALLOWLIST_MATCH",
    "CREDENTIAL_REFERENCE_RESOLVED_FROM_APPROVED_SECRET_SOURCE",
    "CREDENTIAL_SCOPE_MINIMUM_REQUIRED",
    "CREDENTIAL_NOT_EXPIRED",
    "PAYLOAD_SCHEMA_VALIDATED",
    "PAYLOAD_DIGEST_MATCH",
    "REQUEST_HEADERS_POLICY_VALIDATED",
    "TRANSPORT_POLICY_VALIDATED",
    "TIMEOUT_POLICY_VALIDATED",
    "NO_REDIRECT_OR_UNBOUNDED_REDIRECT_POLICY",
    "FINOPS_ESTIMATE_WITHIN_20000_CENTS",
    "OBSERVABILITY_CORRELATION_READY",
    "ALL_MATERIAL_IMMUTABLE_AFTER_DISPATCH_RECORD",
)

REQUIRED_POST_RECORD_RULES = (
    "EXACTLY_ONE_SEALED_CALL_ATTEMPT",
    "NO_PROVIDER_OR_ENDPOINT_SWITCH_AFTER_RECORD",
    "NO_CREDENTIAL_SWITCH_AFTER_RECORD",
    "NO_PAYLOAD_MUTATION_AFTER_RECORD",
    "NO_CAPABILITY_EXPANSION_AFTER_RECORD",
    "NO_SCOPE_EXPANSION_AFTER_RECORD",
    "NO_FINOPS_CEILING_EXPANSION_AFTER_RECORD",
    "TRACE_ID_PRESERVED",
    "EXECUTION_ID_PRESERVED",
    "IDEMPOTENCY_KEY_PRESERVED",
    "EFFECT_KEY_PRESERVED",
    "PROVIDER_REQUEST_CORRELATION_REQUIRED",
    "RESPONSE_OR_AMBIGUITY_RECEIPT_REQUIRED",
    "TIMEOUT_AFTER_RECORD_BECOMES_OUTCOME_UNKNOWN",
    "CONNECTION_RESET_AFTER_RECORD_BECOMES_OUTCOME_UNKNOWN",
    "PROCESS_CRASH_AFTER_RECORD_BECOMES_OUTCOME_UNKNOWN",
    "AMBIGUOUS_PROVIDER_ACK_BECOMES_OUTCOME_UNKNOWN",
    "OUTCOME_UNKNOWN_AUTOMATIC_RETRY_FORBIDDEN",
    "OUTCOME_UNKNOWN_REQUIRES_EXPLICIT_RECONCILIATION",
    "RECONCILIATION_REQUIRES_EVIDENCE",
    "RECONCILIATION_REQUIRES_SEPARATE_AUTHORIZATION",
)

REQUIRED_CALL_BINDINGS = (
    "execution_id",
    "durable_dispatch_record_digest",
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
    "request_headers_policy_digest",
    "transport_policy_digest",
    "timeout_policy_digest",
    "idempotency_key_digest",
    "effect_key_digest",
    "before_state_digest",
    "expected_postcondition_digest",
    "rollback_plan_digest",
    "finops_estimate_digest",
    "observability_trace_id",
)

FORBIDDEN_DESIGN_MATERIAL = (
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
    "url_value",
    "webhook_value",
    "callback_value",
    "request_headers_value",
    "payload_body_value",
    "shell_command_value",
)

FALSE_FIELDS = (
    "call_boundary_verified",
    "provider_selected",
    "provider_bound",
    "provider_identity_verified",
    "adapter_loaded",
    "adapter_instantiated",
    "endpoint_resolved",
    "credential_reference_resolved",
    "credentials_loaded",
    "secrets_loaded",
    "payload_constructed",
    "payload_validated",
    "headers_constructed",
    "transport_opened",
    "socket_opened",
    "network_called",
    "provider_called",
    "provider_request_sent",
    "provider_response_received",
    "provider_ack_verified",
    "external_effect_attempted",
    "external_action_executed",
    "outcome_unknown_marked",
    "reconciliation_performed",
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


def build_external_effect_call_boundary_contract(
    *,
    durable_dispatch_record_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define the external-call boundary; perform no external call."""
    row = (
        dict(durable_dispatch_record_review)
        if isinstance(durable_dispatch_record_review, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != dispatch.SCHEMA:
        blockers.append("DURABLE_DISPATCH_RECORD_SCHEMA_REQUIRED")
    if row.get("state") != dispatch.READY:
        blockers.append("DURABLE_DISPATCH_RECORD_DESIGN_REVIEW_REQUIRED")
    if row.get("durable_dispatch_record_design_only") is not True:
        blockers.append("DURABLE_DISPATCH_RECORD_NOT_DESIGN_ONLY")
    if row.get("reuses_core_durable_execution_kernel") is not True:
        blockers.append("CORE_DURABLE_EXECUTION_REUSE_REQUIRED")
    if row.get("required_core_mode") != "EXTERNAL_EFFECT":
        blockers.append("EXTERNAL_EFFECT_MODE_REQUIRED")
    if row.get("required_dispatch_state") != "DISPATCH_RECORDED":
        blockers.append("DISPATCH_RECORDED_STATE_REQUIRED")
    if row.get("post_dispatch_unknown_state") != "OUTCOME_UNKNOWN":
        blockers.append("OUTCOME_UNKNOWN_STATE_REQUIRED")
    if row.get("no_provider_call_before_record") is not True:
        blockers.append("NO_PROVIDER_CALL_BEFORE_RECORD_REQUIRED")
    if row.get("write_ahead_record_required") is not True:
        blockers.append("WRITE_AHEAD_DISPATCH_RECORD_REQUIRED")
    if row.get("automatic_retry_after_dispatch_forbidden") is not True:
        blockers.append("POST_DISPATCH_AUTOMATIC_RETRY_MUST_BE_FORBIDDEN")
    if row.get("explicit_reconciliation_required") is not True:
        blockers.append("EXPLICIT_RECONCILIATION_REQUIRED")
    if row.get("separate_reconciliation_authorization_required") is not True:
        blockers.append("SEPARATE_RECONCILIATION_AUTHORIZATION_REQUIRED")
    if row.get("next_allowed_step") != dispatch.NEXT_ALLOWED_STEP:
        blockers.append("DURABLE_DISPATCH_RECORD_NEXT_STEP_INVALID")

    for key in dispatch.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("DURABLE_DISPATCH_RECORD_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            external_effect_call_boundary_design_only=True,
            boundary_mode=BOUNDARY_MODE,
            fail_closed=True,
            single_sealed_call_required=True,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        external_effect_call_boundary_design_only=True,
        boundary_mode=BOUNDARY_MODE,
        fail_closed=True,
        provider_neutral=True,
        single_sealed_call_required=True,
        all_mutable_material_prepared_before_dispatch_record_required=True,
        no_material_mutation_after_dispatch_record=True,
        provider_switch_after_dispatch_record_forbidden=True,
        endpoint_switch_after_dispatch_record_forbidden=True,
        credential_switch_after_dispatch_record_forbidden=True,
        payload_mutation_after_dispatch_record_forbidden=True,
        capability_expansion_after_dispatch_record_forbidden=True,
        scope_expansion_after_dispatch_record_forbidden=True,
        finops_ceiling_expansion_after_dispatch_record_forbidden=True,
        provider_response_or_ambiguity_receipt_required=True,
        post_record_ambiguity_requires_outcome_unknown=True,
        automatic_retry_after_dispatch_forbidden=True,
        explicit_reconciliation_required=True,
        reconciliation_evidence_required=True,
        separate_reconciliation_authorization_required=True,
        finops_cap_cents=FINOPS_CAP_CENTS_REQUIRED,
        required_pre_record_preparation=REQUIRED_PRE_RECORD_PREPARATION,
        required_post_record_rules=REQUIRED_POST_RECORD_RULES,
        required_call_bindings=REQUIRED_CALL_BINDINGS,
        forbidden_design_material=FORBIDDEN_DESIGN_MATERIAL,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "BOUNDARY_MODE",
    "FINOPS_CAP_CENTS_REQUIRED",
    "REQUIRED_PRE_RECORD_PREPARATION",
    "REQUIRED_POST_RECORD_RULES",
    "REQUIRED_CALL_BINDINGS",
    "FORBIDDEN_DESIGN_MATERIAL",
    "FALSE_FIELDS",
    "build_external_effect_call_boundary_contract",
]
