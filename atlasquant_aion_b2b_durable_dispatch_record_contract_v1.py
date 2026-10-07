"""AION B2B durable dispatch record contract V1.

Design-only, fail-closed and non-executable.

This layer defines the durable write-ahead record that MUST exist before any
future EXTERNAL_EFFECT dispatch. It reuses the safety semantics of
atlasquant_aion_durable_execution_kernel.DurableExecutionStore and its
DISPATCH_RECORDED state, but does not instantiate or write to that store.

Critical invariant:
after DISPATCH_RECORDED, any crash/ambiguity becomes OUTCOME_UNKNOWN and
automatic retry is forbidden until explicit reconciliation.

Maximum positive state:
READY_FOR_DURABLE_DISPATCH_RECORD_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_pre_dispatch_attestation_contract_v1 as predispatch

SCHEMA = "ATLASQUANT_AION_B2B_DURABLE_DISPATCH_RECORD_CONTRACT_V1"
READY = "READY_FOR_DURABLE_DISPATCH_RECORD_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_EXTERNAL_EFFECT_CALL_BOUNDARY_CONTRACT_ONLY"

CORE_EXECUTION_STORE = "atlasquant_aion_durable_execution_kernel.DurableExecutionStore"
CORE_DISPATCH_METHOD = "DurableExecutionStore.record_dispatch_started"
CORE_DISPATCH_STATE = "DISPATCH_RECORDED"
CORE_UNKNOWN_STATE = "OUTCOME_UNKNOWN"
CORE_MODE = "EXTERNAL_EFFECT"

REQUIRED_STATE_TRANSITION = (
    "PREPARED",
    "LEASED",
    "DISPATCH_RECORDED",
)

REQUIRED_RECORD_BINDINGS = (
    "execution_id",
    "task_id",
    "step_id",
    "owner_id",
    "tenant_id",
    "workspace_id",
    "customer_id",
    "pilot_id",
    "action_family",
    "operation_kind",
    "execution_envelope_digest",
    "pre_dispatch_attestation_digest",
    "fresh_owner_authorization_digest",
    "authenticated_receipt_digest",
    "provider_adapter_attestation_digest",
    "provider_capability_binding_digest",
    "effective_capabilities_digest",
    "provider_identity_ref",
    "idempotency_key_digest",
    "effect_key_digest",
    "payload_digest",
    "lease_identity_digest",
    "before_state_digest",
    "expected_postcondition_digest",
    "rollback_plan_digest",
    "rollback_compensation_contract_digest",
    "finops_estimate_digest",
    "capacity_reservation_digest",
    "quota_snapshot_digest",
    "observability_trace_id",
    "dispatch_recorded_at",
)

REQUIRED_DISPATCH_INVARIANTS = (
    "MODE_MUST_BE_EXTERNAL_EFFECT",
    "STATE_MUST_BE_LEASED_BEFORE_RECORD",
    "LEASE_TOKEN_MATCH_REQUIRED",
    "LEASE_NOT_EXPIRED",
    "DEADLINE_NOT_EXPIRED",
    "PRE_DISPATCH_ATTESTATION_FRESH",
    "PRE_DISPATCH_ATTESTATION_DIGEST_MATCH",
    "EXECUTION_ENVELOPE_DIGEST_MATCH",
    "IDEMPOTENCY_KEY_ALREADY_RESERVED",
    "EFFECT_KEY_ALREADY_RESERVED",
    "EFFECT_KEY_UNIQUE",
    "DISPATCH_RECORD_DURABLE_BEFORE_EXTERNAL_EFFECT",
    "DISPATCH_RECORD_ATOMIC",
    "DISPATCH_RECORD_REPLAY_CONFLICT_FAIL_CLOSED",
    "NO_PROVIDER_CALL_BEFORE_DURABLE_RECORD",
    "POST_RECORD_CRASH_BECOMES_OUTCOME_UNKNOWN",
    "POST_RECORD_AMBIGUITY_BECOMES_OUTCOME_UNKNOWN",
    "OUTCOME_UNKNOWN_AUTOMATIC_RETRY_FORBIDDEN",
    "OUTCOME_UNKNOWN_REQUIRES_EXPLICIT_RECONCILIATION",
    "RECONCILIATION_REQUIRES_EVIDENCE",
    "RECONCILIATION_REQUIRES_SEPARATE_AUTHORIZATION",
    "AUDIT_TRACE_BINDING_REQUIRED",
)

FORBIDDEN_RECORD_MATERIAL = (
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
    "payload_body",
    "command",
    "shell",
    "subprocess",
    "powershell",
    "curl",
    "script",
)

FALSE_FIELDS = (
    "durable_dispatch_record_design_executed",
    "execution_store_opened",
    "execution_record_created",
    "execution_record_loaded",
    "idempotency_reserved",
    "effect_key_reserved",
    "lease_acquired",
    "lease_token_verified",
    "pre_dispatch_attestation_performed",
    "dispatch_record_created",
    "dispatch_record_persisted",
    "dispatch_recorded",
    "outcome_unknown_marked",
    "reconciliation_performed",
    "provider_selected",
    "provider_bound",
    "provider_identity_verified",
    "credentials_loaded",
    "secrets_loaded",
    "endpoint_resolved",
    "payload_constructed",
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


def build_durable_dispatch_record_contract(
    *,
    pre_dispatch_attestation_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define the durable dispatch write-ahead boundary; write nothing."""
    row = (
        dict(pre_dispatch_attestation_review)
        if isinstance(pre_dispatch_attestation_review, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != predispatch.SCHEMA:
        blockers.append("PRE_DISPATCH_ATTESTATION_SCHEMA_REQUIRED")
    if row.get("state") != predispatch.READY:
        blockers.append("PRE_DISPATCH_ATTESTATION_DESIGN_REVIEW_REQUIRED")
    if row.get("pre_dispatch_attestation_design_only") is not True:
        blockers.append("PRE_DISPATCH_ATTESTATION_NOT_DESIGN_ONLY")
    if row.get("attestation_mode") != predispatch.ATTESTATION_MODE:
        blockers.append("PRE_DISPATCH_ATTESTATION_MODE_INVALID")
    if row.get("fail_closed") is not True:
        blockers.append("PRE_DISPATCH_FAIL_CLOSED_REQUIRED")
    if row.get("stale_attestation_forbidden") is not True:
        blockers.append("STALE_PRE_DISPATCH_ATTESTATION_MUST_BE_FORBIDDEN")
    if row.get("idempotency_reservation_required_before_dispatch") is not True:
        blockers.append("IDEMPOTENCY_RESERVATION_REQUIREMENT_MISSING")
    if row.get("effect_key_reservation_required_before_dispatch") is not True:
        blockers.append("EFFECT_KEY_RESERVATION_REQUIREMENT_MISSING")
    if row.get("lease_ownership_required_before_dispatch") is not True:
        blockers.append("LEASE_OWNERSHIP_REQUIREMENT_MISSING")
    if row.get("durable_dispatch_record_required_before_external_effect") is not True:
        blockers.append("DURABLE_DISPATCH_RECORD_REQUIREMENT_MISSING")
    if row.get("authorization_reuse_allowed") is not False:
        blockers.append("AUTHORIZATION_REUSE_MUST_BE_FORBIDDEN")
    if row.get("finops_cap_cents") != 20000:
        blockers.append("FINOPS_CAP_MUST_REMAIN_20000_CENTS")
    if row.get("next_allowed_step") != predispatch.NEXT_ALLOWED_STEP:
        blockers.append("PRE_DISPATCH_NEXT_STEP_INVALID")

    for key in predispatch.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("PRE_DISPATCH_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            durable_dispatch_record_design_only=True,
            reuses_core_durable_execution_kernel=True,
            no_provider_call_before_record=True,
            post_record_unknown_fail_closed=True,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        durable_dispatch_record_design_only=True,
        reuses_core_durable_execution_kernel=True,
        core_execution_store=CORE_EXECUTION_STORE,
        core_dispatch_method=CORE_DISPATCH_METHOD,
        required_core_mode=CORE_MODE,
        required_dispatch_state=CORE_DISPATCH_STATE,
        post_dispatch_unknown_state=CORE_UNKNOWN_STATE,
        required_state_transition=REQUIRED_STATE_TRANSITION,
        no_provider_call_before_record=True,
        write_ahead_record_required=True,
        atomic_dispatch_record_required=True,
        exact_lease_token_required=True,
        deadline_recheck_required=True,
        pre_dispatch_attestation_freshness_required=True,
        idempotency_already_reserved_required=True,
        effect_key_already_reserved_required=True,
        effect_key_unique_required=True,
        post_record_crash_requires_outcome_unknown=True,
        post_record_ambiguity_requires_outcome_unknown=True,
        automatic_retry_after_dispatch_forbidden=True,
        explicit_reconciliation_required=True,
        reconciliation_evidence_required=True,
        separate_reconciliation_authorization_required=True,
        audit_trace_binding_required=True,
        provider_identity_reference_only=True,
        required_record_bindings=REQUIRED_RECORD_BINDINGS,
        required_dispatch_invariants=REQUIRED_DISPATCH_INVARIANTS,
        forbidden_record_material=FORBIDDEN_RECORD_MATERIAL,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "CORE_EXECUTION_STORE",
    "CORE_DISPATCH_METHOD",
    "CORE_DISPATCH_STATE",
    "CORE_UNKNOWN_STATE",
    "CORE_MODE",
    "REQUIRED_STATE_TRANSITION",
    "REQUIRED_RECORD_BINDINGS",
    "REQUIRED_DISPATCH_INVARIANTS",
    "FORBIDDEN_RECORD_MATERIAL",
    "FALSE_FIELDS",
    "build_durable_dispatch_record_contract",
]
