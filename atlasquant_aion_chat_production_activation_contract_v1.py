"""AION Chat production activation contract V1.

Design/CI-only, provider-neutral and non-executable.

This layer composes evidence that a future production chat host MUST require
before any real model response path can be implemented. It does not read
credentials, create storage, call a provider, execute billing, write the Core,
deploy, arm a Worker or perform any external action.

Maximum positive state:
READY_FOR_PRODUCTION_CHAT_ACTIVATION_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_CHAT_PRODUCTION_ACTIVATION_CONTRACT_V1"
READY = "READY_FOR_PRODUCTION_CHAT_ACTIVATION_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "IMPLEMENT_PRODUCTION_CHAT_HOST_ADAPTER_IN_SEPARATE_PR"
OWNER_ID = "HUMAN_OWNER"
PER_TURN_APPROVAL = "PER_TURN_EXPLICIT"

FALSE_FIELDS = (
    "credentials_loaded",
    "secrets_loaded",
    "store_created",
    "production_store_opened",
    "provider_selected",
    "provider_bound",
    "endpoint_resolved",
    "prompt_constructed",
    "network_called",
    "provider_called",
    "billing_authorized",
    "billing_executed",
    "model_output_persisted",
    "core_checkpoint_write",
    "memory_promoted",
    "deploy_authorized",
    "deploy_executed",
    "execution_allowed",
    "worker_armed",
    "worker_activated",
    "external_action_executed",
    "trading_enabled",
    "executes_action",
)

REQUIRED_PRODUCTION_STORE_EVIDENCE = (
    "ATTESTED_PRODUCTION_STORE",
    "OWNER_TENANT_WORKSPACE_SCOPE_BOUND",
    "ENCRYPTION_AT_REST_ATTESTED",
    "BACKUP_RESTORE_ATTESTED",
    "SCHEMA_MIGRATION_ATTESTED",
    "HEALTH_CHECK_ATTESTED",
)

REQUIRED_MODEL_BOUNDARY_EVIDENCE = (
    "PROVIDER_NEUTRAL_GATEWAY",
    "HEALTHY_LOCAL_FALLBACK",
    "EXTERNAL_PROVIDER_CONFIGURATION_READY",
    "EXTERNAL_FEATURE_EXPLICITLY_ENABLED",
    "PRICING_CONFIGURED",
    "VALID_BUDGET_POLICY",
    "POSITIVE_REMAINING_BUDGET",
    "PER_TURN_EXPLICIT_APPROVAL_REQUIRED",
    "MODEL_OUTPUT_REMAINS_UNVERIFIED_UNTIL_EVIDENCE",
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

def evaluate_production_chat_activation_contract(
    *,
    owner_context: Mapping[str, Any] | None,
    production_store_attestation: Mapping[str, Any] | None,
    model_gateway_review: Mapping[str, Any] | None,
    provider_review: Mapping[str, Any] | None,
    budget_review: Mapping[str, Any] | None,
    external_feature_enabled: bool = False,
    external_actions_blocked: bool = True,
) -> dict[str, Any]:
    """Evaluate design readiness only; perform no activation."""
    owner = _mapping(owner_context)
    store = _mapping(production_store_attestation)
    gateway = _mapping(model_gateway_review)
    provider = _mapping(provider_review)
    budget = _mapping(budget_review)
    blockers: list[str] = []

    if owner.get("is_human_owner") is not True:
        blockers.append("HUMAN_OWNER_SESSION_REQUIRED")
    if str(owner.get("owner_id") or "") != OWNER_ID:
        blockers.append("HUMAN_OWNER_ID_REQUIRED")
    if owner.get("session_bound") is not True:
        blockers.append("HUMAN_OWNER_SESSION_BINDING_REQUIRED")

    if str(store.get("state") or "") != "ATTESTED_READY":
        blockers.append("PRODUCTION_STORE_ATTESTATION_REQUIRED")
    if store.get("production") is not True:
        blockers.append("PRODUCTION_STORE_FLAG_REQUIRED")
    if store.get("durable") is not True:
        blockers.append("DURABLE_STORE_REQUIRED")
    if store.get("scope_bound") is not True:
        blockers.append("OWNER_TENANT_WORKSPACE_SCOPE_BINDING_REQUIRED")
    if store.get("encryption_at_rest_attested") is not True:
        blockers.append("ENCRYPTION_AT_REST_ATTESTATION_REQUIRED")
    if store.get("backup_restore_attested") is not True:
        blockers.append("BACKUP_RESTORE_ATTESTATION_REQUIRED")
    if store.get("schema_migration_attested") is not True:
        blockers.append("SCHEMA_MIGRATION_ATTESTATION_REQUIRED")
    if store.get("health_check_attested") is not True:
        blockers.append("STORE_HEALTH_ATTESTATION_REQUIRED")

    if gateway.get("provider_neutral") is not True:
        blockers.append("PROVIDER_NEUTRAL_GATEWAY_REQUIRED")
    if gateway.get("healthy_local_fallback") is not True:
        blockers.append("HEALTHY_LOCAL_FALLBACK_REQUIRED")
    if gateway.get("routing_executes_provider_call") is not False:
        blockers.append("ROUTING_MUST_NOT_CALL_PROVIDER")

    if provider.get("ready") is not True:
        blockers.append("EXTERNAL_PROVIDER_READY_REQUIRED")
    if str(provider.get("state") or "") != "EXTERNAL_READY":
        blockers.append("EXTERNAL_PROVIDER_STATE_REQUIRED")
    if provider.get("api_key_present") is not True:
        blockers.append("PROVIDER_SECRET_PRESENCE_ATTESTATION_REQUIRED")
    if provider.get("pricing_configured") is not True:
        blockers.append("PROVIDER_PRICING_REQUIRED")

    if external_feature_enabled is not True:
        blockers.append("EXTERNAL_MODEL_FEATURE_FLAG_REQUIRED")
    if budget.get("budget_amounts_valid") is not True:
        blockers.append("VALID_MODEL_BUDGET_REQUIRED")
    if budget.get("allow_paid") is not True:
        blockers.append("PAID_MODEL_USE_NOT_EXPLICITLY_ENABLED")
    try:
        monthly_limit = float(budget.get("monthly_limit_usd"))
        remaining = float(budget.get("remaining_usd"))
    except (TypeError, ValueError):
        monthly_limit = -1.0
        remaining = -1.0
    if monthly_limit <= 0:
        blockers.append("POSITIVE_MONTHLY_MODEL_BUDGET_REQUIRED")
    if remaining <= 0:
        blockers.append("POSITIVE_REMAINING_MODEL_BUDGET_REQUIRED")
    if str(budget.get("request_approval_mode") or "") != PER_TURN_APPROVAL:
        blockers.append("PER_TURN_EXPLICIT_APPROVAL_REQUIRED")

    if external_actions_blocked is not True:
        blockers.append("EXTERNAL_ACTIONS_MUST_REMAIN_BLOCKED")

    common = dict(
        activation_design_only=True,
        provider_neutral=True,
        human_owner_required=True,
        production_store_attestation_required=True,
        local_fallback_required=True,
        external_provider_optional_at_runtime=False,
        external_feature_flag_required=True,
        budget_policy_required=True,
        per_turn_explicit_approval_required=True,
        model_output_truth_state="MODEL_OUTPUT_UNVERIFIED",
        external_actions_must_remain_blocked=True,
        required_production_store_evidence=REQUIRED_PRODUCTION_STORE_EVIDENCE,
        required_model_boundary_evidence=REQUIRED_MODEL_BOUNDARY_EVIDENCE,
        next_allowed_step=NEXT_ALLOWED_STEP,
    )
    if blockers:
        return _result("BLOCKED", blockers, **common)
    return _result(READY, [], **common)

__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "OWNER_ID",
    "PER_TURN_APPROVAL",
    "FALSE_FIELDS",
    "REQUIRED_PRODUCTION_STORE_EVIDENCE",
    "REQUIRED_MODEL_BOUNDARY_EVIDENCE",
    "evaluate_production_chat_activation_contract",
]
