"""AION B2B idempotency + replay contract V1.

Design-only, fail-closed and non-executable.

This module defines the durable invariants that a future B2B executor must
satisfy before any external-effect implementation can be reviewed. It reuses
the safety semantics already established by AtlasQuant/AION core contracts,
including PersistentNonceRegistry and DurableExecutionStore concepts.

It does NOT instantiate a store, claim a nonce, reserve an idempotency key,
acquire a lease, record dispatch, retry, reconcile, call a provider, perform
network I/O, mutate production, bill, contact customers, write CRM, provision
resources or deploy.

Maximum positive state:
READY_FOR_IDEMPOTENCY_REPLAY_DESIGN_REVIEW

A positive result permits architecture review only.
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_real_receipt_authenticator_contract_v1 as auth

SCHEMA = "ATLASQUANT_AION_B2B_IDEMPOTENCY_REPLAY_CONTRACT_V1"
READY = "READY_FOR_IDEMPOTENCY_REPLAY_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_ROLLBACK_COMPENSATION_CONTRACT_ONLY"

CORE_NONCE_REGISTRY = "atlasquant_aion_nonce_registry.PersistentNonceRegistry"
CORE_EXECUTION_STORE = (
    "atlasquant_aion_durable_execution_kernel.DurableExecutionStore"
)
CORE_EXECUTION_ID = (
    "atlasquant_aion_durable_execution_kernel.canonical_execution_id"
)

REQUIRED_STATE_MODEL = (
    "PREPARED",
    "LEASED",
    "DISPATCH_RECORDED",
    "RETRY_WAIT",
    "OUTCOME_UNKNOWN",
    "COMPLETED",
    "CANCELED",
    "DLQ",
)

REQUIRED_INVARIANTS = (
    "AUTHENTICATION_PRECEDES_IDEMPOTENCY_RESERVATION",
    "PERSISTENT_NONCE_REPLAY_REJECTION",
    "PERSISTENT_IDEMPOTENCY_KEY_UNIQUENESS",
    "PERSISTENT_EFFECT_KEY_UNIQUENESS",
    "CANONICAL_EXECUTION_ID_BINDING",
    "SAME_IDEMPOTENCY_SAME_PAYLOAD_IS_REPLAY",
    "SAME_IDEMPOTENCY_DIFFERENT_PAYLOAD_IS_CONFLICT",
    "CONCURRENT_DUPLICATE_SINGLE_WINNER",
    "DURABLE_STATE_SURVIVES_REOPEN",
    "LEASE_OWNERSHIP_REQUIRED",
    "LEASE_TOKEN_REQUIRED",
    "LEASE_EXPIRY_RECOVERY_REQUIRED",
    "DEADLINE_ENFORCED",
    "ATTEMPT_LIMIT_ENFORCED",
    "DETERMINISTIC_BACKOFF_REQUIRED",
    "EXTERNAL_DISPATCH_RECORDED_BEFORE_EFFECT",
    "POST_DISPATCH_AMBIGUITY_BECOMES_OUTCOME_UNKNOWN",
    "OUTCOME_UNKNOWN_AUTOMATIC_RETRY_FORBIDDEN",
    "PRE_DISPATCH_FAILURE_MAY_RETRY_WITHIN_POLICY",
    "RESULT_REPLAY_CONFLICT_REJECTED",
    "OUTCOME_UNKNOWN_REQUIRES_EXPLICIT_RECONCILIATION",
    "RECONCILIATION_REQUIRES_EVIDENCE",
    "RECONCILIATION_REQUIRES_SEPARATE_AUTHORIZATION",
)

REQUIRED_BINDINGS = (
    "owner_id",
    "tenant_id",
    "workspace_id",
    "customer_id",
    "pilot_id",
    "action_family",
    "operation_kind",
    "execution_request_digest",
    "command_plan_digest",
    "adapter_plan_digest",
    "dry_run_digest",
    "rollback_plan_digest",
    "authenticated_receipt_digest",
    "idempotency_key_digest",
    "effect_key_digest",
    "payload_digest",
)

FORBIDDEN_IMPLEMENTATION_MATERIAL = (
    "sqlite_path",
    "database_connection",
    "lease_token_value",
    "idempotency_key_value",
    "effect_key_value",
    "provider_endpoint",
    "credential",
    "secret",
    "token",
    "http_method",
    "headers",
    "payload_body",
    "shell_command",
    "executable_command",
    "production_target",
)

FALSE_FIELDS = (
    "nonce_claimed",
    "nonce_registry_written",
    "idempotency_reserved",
    "effect_key_reserved",
    "execution_record_created",
    "execution_store_opened",
    "lease_acquired",
    "lease_heartbeat_sent",
    "dispatch_recorded",
    "retry_scheduled",
    "reconciliation_performed",
    "reconciliation_authorized",
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


def build_idempotency_replay_contract(
    *,
    authenticator_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build a design-only durable idempotency/replay contract."""
    row = dict(authenticator_review) if isinstance(authenticator_review, Mapping) else {}
    blockers: list[str] = []

    if row.get("schema") != auth.SCHEMA:
        blockers.append("AUTHENTICATOR_CONTRACT_SCHEMA_REQUIRED")
    if row.get("state") != auth.READY:
        blockers.append("AUTHENTICATOR_DESIGN_REVIEW_REQUIRED")
    if row.get("authenticator_design_only") is not True:
        blockers.append("AUTHENTICATOR_NOT_DESIGN_ONLY")
    if row.get("provider_neutral") is not True:
        blockers.append("AUTHENTICATOR_NOT_PROVIDER_NEUTRAL")
    if row.get("persistent_nonce_registry_required") is not True:
        blockers.append("PERSISTENT_NONCE_REGISTRY_REQUIREMENT_MISSING")
    if row.get("replay_rejection_required") is not True:
        blockers.append("REPLAY_REJECTION_REQUIREMENT_MISSING")
    if row.get("authorization_reuse_allowed") is not False:
        blockers.append("AUTHORIZATION_REUSE_MUST_BE_FORBIDDEN")
    if row.get("fresh_owner_authorization_required") is not True:
        blockers.append("FRESH_OWNER_AUTHORIZATION_REQUIREMENT_MISSING")
    if row.get("next_allowed_step") != auth.NEXT_ALLOWED_STEP:
        blockers.append("AUTHENTICATOR_NEXT_STEP_INVALID")

    for key in auth.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("AUTHENTICATOR_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            idempotency_replay_design_only=True,
            reuses_existing_core_safety=True,
            fresh_owner_authorization_required=True,
            authorization_reuse_allowed=False,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        idempotency_replay_design_only=True,
        reuses_existing_core_safety=True,
        provider_neutral=True,
        persistent_registry_required=True,
        persistent_execution_store_required=True,
        canonical_execution_identity_required=True,
        nonce_claim_after_authentication_only=True,
        idempotency_prepare_before_dispatch_required=True,
        effect_key_uniqueness_required=True,
        single_winner_concurrency_required=True,
        durable_reopen_recovery_required=True,
        lease_ownership_required=True,
        deadline_required=True,
        bounded_attempts_required=True,
        deterministic_backoff_required=True,
        dispatch_record_before_external_effect_required=True,
        post_dispatch_ambiguity_requires_outcome_unknown=True,
        automatic_retry_after_unknown_forbidden=True,
        explicit_reconciliation_required=True,
        reconciliation_evidence_required=True,
        separate_reconciliation_authorization_required=True,
        fresh_owner_authorization_required=True,
        authorization_reuse_allowed=False,
        core_nonce_registry=CORE_NONCE_REGISTRY,
        core_execution_store=CORE_EXECUTION_STORE,
        core_execution_id=CORE_EXECUTION_ID,
        required_state_model=REQUIRED_STATE_MODEL,
        required_invariants=REQUIRED_INVARIANTS,
        required_bindings=REQUIRED_BINDINGS,
        forbidden_implementation_material=FORBIDDEN_IMPLEMENTATION_MATERIAL,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "CORE_NONCE_REGISTRY",
    "CORE_EXECUTION_STORE",
    "CORE_EXECUTION_ID",
    "REQUIRED_STATE_MODEL",
    "REQUIRED_INVARIANTS",
    "REQUIRED_BINDINGS",
    "FORBIDDEN_IMPLEMENTATION_MATERIAL",
    "FALSE_FIELDS",
    "build_idempotency_replay_contract",
]
