"""AION B2B pre-dispatch attestation contract V1.

Design-only, fail-closed and non-executable.

This layer defines the immediate pre-effect revalidation boundary for a future
external dispatch. It consumes only the Execution Envelope design review and
defines what MUST be re-proven immediately before any future dispatch.

It does not build or consume an envelope, reserve idempotency/effect keys,
acquire a lease, resolve an endpoint, load credentials, construct a payload,
record a dispatch, call a provider, bill, contact a customer, write CRM,
provision, deploy or mutate production.

Maximum positive state:
READY_FOR_PRE_DISPATCH_ATTESTATION_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_execution_envelope_contract_v1 as envelope

SCHEMA = "ATLASQUANT_AION_B2B_PRE_DISPATCH_ATTESTATION_CONTRACT_V1"
READY = "READY_FOR_PRE_DISPATCH_ATTESTATION_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_DURABLE_DISPATCH_RECORD_CONTRACT_ONLY"

ATTESTATION_MODE = "IMMEDIATE_PRE_EFFECT_REVALIDATION"
MAX_ATTESTATION_AGE_SECONDS = 30
FINOPS_CAP_CENTS_REQUIRED = 20000

REQUIRED_REVALIDATIONS = (
    "EXECUTION_ENVELOPE_DIGEST_REBUILD_MATCH",
    "EXECUTION_ENVELOPE_NOT_EXPIRED",
    "FRESH_OWNER_AUTHORIZATION_STILL_VALID",
    "FRESH_OWNER_AUTHORIZATION_NOT_CONSUMED",
    "AUTHORIZATION_SINGLE_USE_PRESERVED",
    "ENVELOPE_NONCE_NOT_CONSUMED",
    "ENVELOPE_SINGLE_USE_PRESERVED",
    "EXACT_SCOPE_BINDING_UNCHANGED",
    "EXACT_ACTION_OPERATION_BINDING_UNCHANGED",
    "BEFORE_STATE_DIGEST_STILL_MATCHES",
    "EXPECTED_POSTCONDITION_STILL_BOUND",
    "IDEMPOTENCY_KEY_RESERVATION_REQUIRED_BEFORE_DISPATCH",
    "EFFECT_KEY_RESERVATION_REQUIRED_BEFORE_DISPATCH",
    "LEASE_OWNERSHIP_REQUIRED_BEFORE_DISPATCH",
    "LEASE_NOT_EXPIRED",
    "PROVIDER_ADAPTER_ATTESTATION_STILL_VALID",
    "PROVIDER_CAPABILITY_BINDING_STILL_VALID",
    "EFFECTIVE_CAPABILITY_INTERSECTION_UNCHANGED",
    "PROVIDER_IDENTITY_REFERENCE_UNCHANGED",
    "PROVIDER_HEALTH_EVIDENCE_FRESH",
    "FINOPS_ESTIMATE_WITHIN_20000_CENTS",
    "CAPACITY_RESERVATION_REQUIRED",
    "QUOTA_AVAILABLE",
    "SECURITY_INCIDENT_CLEAR",
    "PRIVACY_INCIDENT_CLEAR",
    "SCOPE_BREACH_CLEAR",
    "CIRCUIT_BREAKER_CLOSED",
    "KILL_SWITCH_AVAILABLE",
    "ROLLBACK_COMPENSATION_CLASS_STILL_VALID",
    "IRREVERSIBLE_BOUNDARY_RECHECKED",
    "OBSERVABILITY_TRACE_RESERVED",
    "AUDIT_CONTEXT_COMPLETE",
    "DISPATCH_RECORD_REQUIRED_BEFORE_EXTERNAL_EFFECT",
)

REQUIRED_ATTESTATION_BINDINGS = (
    "execution_envelope_digest",
    "fresh_owner_authorization_digest",
    "authenticated_receipt_digest",
    "provider_adapter_attestation_digest",
    "provider_capability_binding_digest",
    "effective_capabilities_digest",
    "idempotency_key_digest",
    "effect_key_digest",
    "lease_identity_digest",
    "provider_identity_ref",
    "before_state_digest",
    "expected_postcondition_digest",
    "rollback_plan_digest",
    "rollback_compensation_contract_digest",
    "runtime_execution_guards_digest",
    "finops_estimate_digest",
    "capacity_reservation_digest",
    "quota_snapshot_digest",
    "provider_health_digest",
    "security_state_digest",
    "observability_trace_id",
    "checked_at",
)

FORBIDDEN_PRE_DISPATCH_MATERIAL = (
    "credential",
    "secret",
    "password",
    "api_key",
    "access_token",
    "refresh_token",
    "private_key",
    "authorization_header",
    "cookie",
    "endpoint",
    "url",
    "webhook",
    "callback",
    "http_method",
    "headers",
    "payload",
    "body",
    "command",
    "shell",
    "subprocess",
    "powershell",
    "curl",
    "script",
)

FALSE_FIELDS = (
    "pre_dispatch_attestation_performed",
    "pre_dispatch_attested",
    "execution_envelope_rebuilt",
    "execution_envelope_consumed",
    "fresh_authorization_revalidated",
    "fresh_authorization_consumed",
    "envelope_nonce_claimed",
    "idempotency_reserved",
    "effect_key_reserved",
    "lease_acquired",
    "lease_renewed",
    "capacity_reserved",
    "quota_consumed",
    "provider_adapter_revalidated",
    "provider_capability_revalidated",
    "provider_health_checked",
    "provider_identity_verified",
    "provider_selected",
    "provider_bound",
    "credentials_loaded",
    "secrets_loaded",
    "endpoint_resolved",
    "payload_constructed",
    "dispatch_record_created",
    "dispatch_record_persisted",
    "dispatch_recorded",
    "observability_event_written",
    "audit_receipt_written",
    "network_called",
    "provider_called",
    "billing_authorized",
    "billing_executed",
    "customer_contact_authorized",
    "crm_write_authorized",
    "provisioning_authorized",
    "deploy_authorized",
    "production_mutation_authorized",
    "production_mutation_performed",
    "external_action_executed",
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


def build_pre_dispatch_attestation_contract(
    *,
    execution_envelope_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define immediate pre-dispatch revalidation; perform no attestation."""
    row = (
        dict(execution_envelope_review)
        if isinstance(execution_envelope_review, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != envelope.SCHEMA:
        blockers.append("EXECUTION_ENVELOPE_SCHEMA_REQUIRED")
    if row.get("state") != envelope.READY:
        blockers.append("EXECUTION_ENVELOPE_DESIGN_REVIEW_REQUIRED")
    if row.get("execution_envelope_design_only") is not True:
        blockers.append("EXECUTION_ENVELOPE_NOT_DESIGN_ONLY")
    if row.get("envelope_mode") != envelope.ENVELOPE_MODE:
        blockers.append("EXECUTION_ENVELOPE_MODE_INVALID")
    if row.get("digest_references_only") is not True:
        blockers.append("DIGEST_REFERENCES_ONLY_REQUIRED")
    if row.get("immutable_after_seal_required") is not True:
        blockers.append("IMMUTABLE_ENVELOPE_REQUIRED")
    if row.get("envelope_single_use_required") is not True:
        blockers.append("ENVELOPE_SINGLE_USE_REQUIRED")
    if row.get("authorization_reuse_allowed") is not False:
        blockers.append("AUTHORIZATION_REUSE_MUST_BE_FORBIDDEN")
    if row.get("no_implicit_execution_authority") is not True:
        blockers.append("NO_IMPLICIT_EXECUTION_AUTHORITY_REQUIRED")
    if row.get("finops_cap_cents") != FINOPS_CAP_CENTS_REQUIRED:
        blockers.append("FINOPS_CAP_MUST_REMAIN_20000_CENTS")
    if row.get("next_allowed_step") != envelope.NEXT_ALLOWED_STEP:
        blockers.append("EXECUTION_ENVELOPE_NEXT_STEP_INVALID")

    for key in envelope.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("EXECUTION_ENVELOPE_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            pre_dispatch_attestation_design_only=True,
            attestation_mode=ATTESTATION_MODE,
            fail_closed=True,
            provider_neutral=True,
            authorization_reuse_allowed=False,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        pre_dispatch_attestation_design_only=True,
        attestation_mode=ATTESTATION_MODE,
        fail_closed=True,
        provider_neutral=True,
        immediate_before_external_effect_required=True,
        max_attestation_age_seconds=MAX_ATTESTATION_AGE_SECONDS,
        stale_attestation_forbidden=True,
        envelope_rebuild_match_required=True,
        authorization_reuse_allowed=False,
        authorization_single_use_required=True,
        envelope_single_use_required=True,
        exact_scope_revalidation_required=True,
        exact_action_operation_revalidation_required=True,
        before_state_revalidation_required=True,
        provider_adapter_revalidation_required=True,
        provider_capability_revalidation_required=True,
        provider_health_freshness_required=True,
        provider_identity_reference_only=True,
        idempotency_reservation_required_before_dispatch=True,
        effect_key_reservation_required_before_dispatch=True,
        lease_ownership_required_before_dispatch=True,
        capacity_reservation_required_before_dispatch=True,
        quota_check_required_before_dispatch=True,
        finops_cap_cents=FINOPS_CAP_CENTS_REQUIRED,
        security_privacy_recheck_required=True,
        circuit_breaker_closed_required=True,
        kill_switch_available_required=True,
        rollback_compensation_recheck_required=True,
        irreversible_boundary_recheck_required=True,
        observability_trace_required=True,
        audit_context_required=True,
        durable_dispatch_record_required_before_external_effect=True,
        required_revalidations=REQUIRED_REVALIDATIONS,
        required_attestation_bindings=REQUIRED_ATTESTATION_BINDINGS,
        forbidden_pre_dispatch_material=FORBIDDEN_PRE_DISPATCH_MATERIAL,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "ATTESTATION_MODE",
    "MAX_ATTESTATION_AGE_SECONDS",
    "FINOPS_CAP_CENTS_REQUIRED",
    "REQUIRED_REVALIDATIONS",
    "REQUIRED_ATTESTATION_BINDINGS",
    "FORBIDDEN_PRE_DISPATCH_MATERIAL",
    "FALSE_FIELDS",
    "build_pre_dispatch_attestation_contract",
]
