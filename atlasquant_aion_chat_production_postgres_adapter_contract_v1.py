"""AION Chat production Postgres adapter contract V1.

Design/CI-only. No database, SQL, provider, network, billing, deploy or runtime
action is executed here.

The contract defines the composition/order a future production chat host must
follow when combining:
- authenticated product binding + Scope,
- attested Postgres storage,
- provider-neutral model routing,
- optional external provider execution,
- truthful durable persistence.

Maximum state:
READY_FOR_PRODUCTION_POSTGRES_ADAPTER_IMPLEMENTATION_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_CHAT_PRODUCTION_POSTGRES_ADAPTER_CONTRACT_V1"
READY = "READY_FOR_PRODUCTION_POSTGRES_ADAPTER_IMPLEMENTATION_REVIEW"
NEXT_ALLOWED_STEP = "IMPLEMENT_PRODUCTION_POSTGRES_STORE_ADAPTER_IN_SEPARATE_PR"

FALSE_FIELDS = (
    "sql_executed",
    "connection_opened",
    "database_created",
    "migration_executed",
    "credentials_loaded",
    "secrets_loaded",
    "network_called",
    "provider_called",
    "billing_executed",
    "message_written",
    "deploy_executed",
    "worker_armed",
    "worker_activated",
    "external_action_executed",
    "core_checkpoint_write",
    "memory_promoted",
)

REQUIRED_SEQUENCE = (
    "VALIDATE_AUTHENTICATED_SCOPE_BINDING",
    "CHECK_DATABASE_HEALTH_AND_SCHEMA",
    "RESUME_SCOPED_DURABLE_CONTEXT",
    "PERSIST_USER_TURN_CONFIRMED",
    "ROUTE_MODEL_WITHOUT_CALLING_PROVIDER",
    "ENFORCE_PRIVACY_APPROVAL_AND_BUDGET",
    "OPTIONALLY_CALL_PROVIDER_ONCE",
    "PERSIST_ASSISTANT_OUTPUT_CONFIRMED",
    "RETURN_TRUTHFUL_DURABILITY_STATE",
)

def _mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}

def _result(state: str, blockers=(), **fields) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "blockers": sorted(set(str(x) for x in blockers if str(x))),
        **fields,
        **{key: False for key in FALSE_FIELDS},
    }

def evaluate_production_postgres_adapter_contract(
    *,
    binding: Mapping[str, Any] | None,
    storage: Mapping[str, Any] | None,
    routing: Mapping[str, Any] | None,
    provider_boundary: Mapping[str, Any] | None,
    persistence_policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    b = _mapping(binding)
    s = _mapping(storage)
    r = _mapping(routing)
    p = _mapping(provider_boundary)
    d = _mapping(persistence_policy)
    blockers: list[str] = []

    binding_checks = {
        "AUTHENTICATED_BINDING_REQUIRED": b.get("bound") is True,
        "OWNER_SCOPE_REQUIRED": bool(str(b.get("owner_id") or "")),
        "TENANT_SCOPE_REQUIRED": bool(str(b.get("tenant_id") or "")),
        "WORKSPACE_SCOPE_REQUIRED": bool(str(b.get("workspace_id") or "")),
        "CREDENTIAL_FINGERPRINT_REQUIRED": b.get("credential_fingerprint_present") is True,
        "PERMISSIONS_VERIFIED_REQUIRED": b.get("permissions_verified") is True,
    }
    for blocker, ok in binding_checks.items():
        if not ok:
            blockers.append(blocker)

    storage_checks = {
        "ATTESTED_PRODUCTION_STORE_REQUIRED": s.get("attested_ready") is True,
        "DATABASE_HEALTH_REQUIRED": s.get("healthy") is True,
        "SCHEMA_COMPATIBILITY_REQUIRED": s.get("schema_compatible") is True,
        "SCOPE_POLICY_HEALTH_REQUIRED": s.get("scope_policy_healthy") is True,
        "FAIL_CLOSED_DB_REQUIRED": s.get("fail_closed_on_unavailable") is True,
        "IDEMPOTENT_APPEND_REQUIRED": s.get("idempotent_append") is True,
    }
    for blocker, ok in storage_checks.items():
        if not ok:
            blockers.append(blocker)

    routing_checks = {
        "PROVIDER_NEUTRAL_ROUTER_REQUIRED": r.get("provider_neutral") is True,
        "ROUTER_MUST_NOT_CALL_PROVIDER": r.get("executes_provider_call") is False,
        "ROUTER_MUST_NOT_BILL": r.get("executes_billing") is False,
        "HEALTHY_LOCAL_FALLBACK_REQUIRED": r.get("healthy_local_fallback") is True,
    }
    for blocker, ok in routing_checks.items():
        if not ok:
            blockers.append(blocker)

    provider_checks = {
        "EXTERNAL_PROVIDER_OPTIONAL_REQUIRED": p.get("external_provider_optional") is True,
        "PER_TURN_EXPLICIT_APPROVAL_REQUIRED": p.get("per_turn_explicit_approval") is True,
        "BUDGET_GATE_REQUIRED": p.get("budget_gate_required") is True,
        "PRIVACY_GATE_REQUIRED": p.get("privacy_gate_required") is True,
        "MODEL_OUTPUT_UNVERIFIED_REQUIRED": p.get("model_output_unverified") is True,
        "EXTERNAL_ACTIONS_BLOCKED_REQUIRED": p.get("external_actions_blocked") is True,
    }
    for blocker, ok in provider_checks.items():
        if not ok:
            blockers.append(blocker)

    durability_checks = {
        "USER_PERSIST_BEFORE_PROVIDER_REQUIRED": d.get("persist_user_before_provider") is True,
        "USER_PERSISTENCE_CONFIRMATION_REQUIRED": d.get("user_persistence_confirmed") is True,
        "ASSISTANT_PERSISTENCE_CONFIRMATION_REQUIRED": d.get("assistant_persistence_must_confirm") is True,
        "UNKNOWN_ASSISTANT_PERSISTENCE_NOT_SUCCESS": d.get("unknown_assistant_persistence_not_success") is True,
        "NO_SESSION_ONLY_DURABLE_FALLBACK": d.get("session_only_fallback_forbidden") is True,
        "NO_STAGING_SQLITE_PROD_FALLBACK": d.get("staging_sqlite_fallback_forbidden") is True,
        "PROVIDER_RESULT_IDEMPOTENCY_REQUIRED": d.get("provider_result_idempotency") is True,
        "NO_AUTO_PROVIDER_RECALL_AFTER_UNKNOWN_PERSISTENCE": d.get("no_provider_recall_after_unknown_persistence") is True,
        "RECONCILE_PERSISTENCE_SEPARATELY_REQUIRED": d.get("separate_persistence_reconciliation") is True,
    }
    for blocker, ok in durability_checks.items():
        if not ok:
            blockers.append(blocker)

    if d.get("claims_saved_when_unknown") is True:
        blockers.append("FALSE_SAVED_CLAIM_FORBIDDEN")
    if d.get("provider_before_user_persist") is True:
        blockers.append("PROVIDER_BEFORE_USER_PERSIST_FORBIDDEN")
    if d.get("automatic_second_provider_call_after_unknown") is True:
        blockers.append("AUTOMATIC_DUPLICATE_PROVIDER_CALL_FORBIDDEN")
    if p.get("provider_approval_implies_external_action_authority") is True:
        blockers.append("MODEL_APPROVAL_MUST_NOT_GRANT_EXTERNAL_ACTION_AUTHORITY")

    common = dict(
        design_only=True,
        required_sequence=REQUIRED_SEQUENCE,
        provider_call_may_happen_only_after_confirmed_user_persistence=True,
        assistant_persistence_unknown_state="PERSISTENCE_OUTCOME_UNKNOWN",
        provider_retry_after_unknown_persistence="FORBIDDEN_AUTOMATICALLY",
        persistence_reconciliation="SEPARATE_IDEMPOTENT_PATH",
        model_output_truth_state="MODEL_OUTPUT_UNVERIFIED",
        external_actions_must_remain_blocked=True,
        next_allowed_step=NEXT_ALLOWED_STEP,
    )
    if blockers:
        return _result("BLOCKED", blockers, **common)
    return _result(READY, [], **common)

__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "FALSE_FIELDS",
    "REQUIRED_SEQUENCE",
    "evaluate_production_postgres_adapter_contract",
]
