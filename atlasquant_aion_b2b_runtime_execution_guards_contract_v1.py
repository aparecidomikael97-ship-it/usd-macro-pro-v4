"""AION B2B runtime execution guards contract V1.

Design-only, provider-neutral and non-executable.

This layer defines the runtime guardrails that must be proven before any future
provider adapter or executor implementation can be reviewed. It does not select
a provider, open a network connection, create credentials, dispatch an action,
bill, contact a customer, write CRM, provision, deploy or mutate production.

Maximum positive state:
READY_FOR_RUNTIME_EXECUTION_GUARDS_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_fresh_owner_execution_authorization_contract_v1 as fresh

SCHEMA = "ATLASQUANT_AION_B2B_RUNTIME_EXECUTION_GUARDS_CONTRACT_V1"
READY = "READY_FOR_RUNTIME_EXECUTION_GUARDS_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_PROVIDER_ADAPTER_ATTESTATION_CONTRACT_ONLY"

FINOPS_CAP_CENTS_REQUIRED = 20000

REQUIRED_RUNTIME_GUARDS = (
    "FRESH_OWNER_AUTHORIZATION_VERIFIED_AT_DISPATCH",
    "AUTHORIZATION_SINGLE_USE_ENFORCED",
    "AUTHORIZATION_NOT_EXPIRED",
    "EXACT_OWNER_TENANT_WORKSPACE_BINDING",
    "EXACT_CUSTOMER_PILOT_PACKAGE_BINDING",
    "EXACT_ACTION_FAMILY_OPERATION_BINDING",
    "NO_PRODUCTION_SCOPE_EXPANSION",
    "CAPABILITY_ALLOWLIST_MINIMUM_REQUIRED",
    "TENANT_ISOLATION_ENFORCED",
    "PERSISTENT_IDEMPOTENCY_ENFORCED",
    "PERSISTENT_EFFECT_KEY_UNIQUENESS",
    "LEASE_OWNERSHIP_ENFORCED",
    "DISPATCH_RECORDED_BEFORE_EXTERNAL_EFFECT",
    "OUTCOME_UNKNOWN_FAIL_CLOSED",
    "ROLLBACK_COMPENSATION_CLASS_BOUND",
    "IRREVERSIBLE_BOUNDARY_FAIL_CLOSED",
    "FINOPS_RUNTIME_CAP_ENFORCED",
    "PER_ACTION_COST_EVIDENCE_REQUIRED",
    "CAPACITY_RESERVATION_REQUIRED",
    "CAPACITY_QUOTA_ENFORCED",
    "PROVIDER_ADAPTER_ATTESTATION_REQUIRED",
    "PROVIDER_IDENTITY_BINDING_REQUIRED",
    "WRITER_IDENTITY_BINDING_REQUIRED",
    "SECURITY_PRIVACY_INCIDENT_FAIL_CLOSED",
    "CIRCUIT_BREAKER_REQUIRED",
    "KILL_SWITCH_REQUIRED",
    "BEFORE_AFTER_STATE_EVIDENCE_REQUIRED",
    "OBSERVABILITY_TRACE_REQUIRED",
    "AUDIT_RECEIPT_REQUIRED",
)

REQUIRED_OBSERVABILITY_FIELDS = (
    "trace_id",
    "execution_id",
    "owner_id",
    "tenant_id",
    "workspace_id",
    "customer_id",
    "pilot_id",
    "action_family",
    "operation_kind",
    "authorization_digest",
    "authenticated_receipt_digest",
    "idempotency_key_digest",
    "effect_key_digest",
    "provider_identity_ref",
    "writer_identity_ref",
    "before_state_digest",
    "after_state_digest",
    "rollback_plan_digest",
    "finops_estimate_cents",
    "started_at",
    "completed_at",
    "outcome",
)

FALSE_FIELDS = (
    "runtime_guard_verified",
    "fresh_authorization_consumed",
    "capacity_reserved",
    "quota_consumed",
    "finops_charge_reserved",
    "provider_adapter_attested",
    "provider_identity_verified",
    "writer_identity_verified",
    "circuit_breaker_armed",
    "kill_switch_armed",
    "audit_receipt_written",
    "observability_event_written",
    "executor_created",
    "executor_selected",
    "executor_implementation_allowed",
    "provider_selected",
    "provider_bound",
    "provider_called",
    "network_called",
    "credential_material_included",
    "secret_material_included",
    "provider_endpoint_included",
    "http_method_included",
    "headers_included",
    "executable_payload_included",
    "execution_token_issued",
    "shell_command_generated",
    "execution_command_generated",
    "execution_command_executed",
    "business_action_authorized",
    "billing_authorized",
    "customer_contact_authorized",
    "crm_write_authorized",
    "provisioning_authorized",
    "deploy_authorized",
    "production_mutation_authorized",
    "production_mutation_performed",
    "external_action_executed",
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


def build_runtime_execution_guards_contract(
    *,
    fresh_owner_authorization_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build provider-neutral runtime guard requirements; execute nothing."""
    row = (
        dict(fresh_owner_authorization_review)
        if isinstance(fresh_owner_authorization_review, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != fresh.SCHEMA:
        blockers.append("FRESH_OWNER_AUTHORIZATION_SCHEMA_REQUIRED")
    if row.get("state") != fresh.READY:
        blockers.append("FRESH_OWNER_AUTHORIZATION_DESIGN_REVIEW_REQUIRED")
    if row.get("fresh_owner_authorization_design_only") is not True:
        blockers.append("FRESH_OWNER_AUTHORIZATION_NOT_DESIGN_ONLY")
    if row.get("reuses_existing_execution_ceremony") is not True:
        blockers.append("EXISTING_EXECUTION_CEREMONY_REUSE_REQUIRED")
    if row.get("fresh_owner_authorization_required") is not True:
        blockers.append("FRESH_OWNER_AUTHORIZATION_REQUIREMENT_MISSING")
    if row.get("authorization_reuse_allowed") is not False:
        blockers.append("AUTHORIZATION_REUSE_MUST_BE_FORBIDDEN")
    if row.get("single_use_authorization_required") is not True:
        blockers.append("SINGLE_USE_AUTHORIZATION_REQUIREMENT_MISSING")
    if row.get("generic_chat_is_authorization") is not False:
        blockers.append("GENERIC_CHAT_AUTHORIZATION_FORBIDDEN")
    if row.get("next_allowed_step") != fresh.NEXT_ALLOWED_STEP:
        blockers.append("FRESH_OWNER_AUTHORIZATION_NEXT_STEP_INVALID")

    for key in fresh.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("FRESH_OWNER_AUTHORIZATION_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            runtime_guards_design_only=True,
            provider_neutral=True,
            fresh_owner_authorization_required=True,
            authorization_reuse_allowed=False,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        runtime_guards_design_only=True,
        provider_neutral=True,
        fresh_owner_authorization_required=True,
        authorization_reuse_allowed=False,
        single_use_authorization_required=True,
        tenant_scope_binding_required=True,
        production_scope_expansion_allowed=False,
        capability_allowlist_required=True,
        persistent_idempotency_required=True,
        persistent_effect_key_uniqueness_required=True,
        lease_required=True,
        dispatch_record_before_effect_required=True,
        outcome_unknown_fail_closed=True,
        rollback_compensation_binding_required=True,
        irreversible_effect_default_allowed=False,
        finops_cap_cents=FINOPS_CAP_CENTS_REQUIRED,
        runtime_finops_guard_required=True,
        per_action_cost_evidence_required=True,
        capacity_reservation_required=True,
        quota_enforcement_required=True,
        provider_adapter_attestation_required=True,
        provider_identity_binding_required=True,
        writer_identity_binding_required=True,
        security_privacy_incident_fail_closed=True,
        circuit_breaker_required=True,
        kill_switch_required=True,
        before_after_state_evidence_required=True,
        observability_trace_required=True,
        audit_receipt_required=True,
        required_runtime_guards=REQUIRED_RUNTIME_GUARDS,
        required_observability_fields=REQUIRED_OBSERVABILITY_FIELDS,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "FINOPS_CAP_CENTS_REQUIRED",
    "REQUIRED_RUNTIME_GUARDS",
    "REQUIRED_OBSERVABILITY_FIELDS",
    "FALSE_FIELDS",
    "build_runtime_execution_guards_contract",
]
