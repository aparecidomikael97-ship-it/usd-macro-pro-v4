"""AION Chat production Postgres store-adapter implementation contract V1.

Design/CI-only. This module does not import a Postgres client, connect to a
database, execute SQL, load secrets, call a model/provider, bill, deploy, or
write runtime/Core state.

It defines the interface and invariants a future Postgres implementation must
satisfy while preserving compatibility with the existing AionChatStore
protocol.

Maximum state:
READY_FOR_POSTGRES_STORE_ADAPTER_IMPLEMENTATION
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

SCHEMA = "ATLASQUANT_AION_CHAT_POSTGRES_STORE_ADAPTER_CONTRACT_V1"
READY = "READY_FOR_POSTGRES_STORE_ADAPTER_IMPLEMENTATION"
NEXT_ALLOWED_STEP = "IMPLEMENT_NON_NETWORK_POSTGRES_ADAPTER_SKELETON_WITH_FAKE_BACKEND"

REQUIRED_METHODS = (
    "create_conversation",
    "get_conversation",
    "list_conversations",
    "search_conversations",
    "archive_conversation",
    "append_message",
    "list_messages",
    "get_message",
    "add_attachment_metadata",
    "get_attachment",
    "save_checkpoint",
    "get_latest_checkpoint",
    "save_context_summary",
    "get_latest_summary",
    "retrieve_messages",
)

FALSE_FIELDS = (
    "postgres_client_imported",
    "connection_opened",
    "sql_executed",
    "transaction_opened",
    "database_created",
    "migration_executed",
    "credentials_loaded",
    "secrets_loaded",
    "network_called",
    "provider_called",
    "billing_executed",
    "deploy_executed",
    "worker_armed",
    "external_action_executed",
    "core_checkpoint_write",
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

def evaluate_postgres_store_adapter_contract(
    *,
    interface: Mapping[str, Any] | None,
    scope_policy: Mapping[str, Any] | None,
    transaction_policy: Mapping[str, Any] | None,
    health_policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    i = _mapping(interface)
    s = _mapping(scope_policy)
    t = _mapping(transaction_policy)
    h = _mapping(health_policy)
    blockers: list[str] = []

    methods = set(str(x) for x in (i.get("methods") or ()))
    for method in REQUIRED_METHODS:
        if method not in methods:
            blockers.append(f"STORE_METHOD_MISSING:{method}")

    interface_checks = {
        "AION_CHAT_STORE_COMPAT_REQUIRED": i.get("aion_chat_store_compatible") is True,
        "MODEL_TYPES_REUSED_REQUIRED": i.get("reuse_existing_models") is True,
        "STORAGE_UNAVAILABLE_ERROR_REQUIRED": i.get("storage_unavailable_error_contract") is True,
        "NO_PROVIDER_DEPENDENCY_REQUIRED": i.get("provider_dependency_absent") is True,
    }
    for blocker, ok in interface_checks.items():
        if not ok:
            blockers.append(blocker)

    scope_checks = {
        "TRUSTED_SCOPE_REQUIRED": s.get("trusted_scope_required") is True,
        "SCOPE_ON_EVERY_QUERY_REQUIRED": s.get("scope_on_every_query") is True,
        "CROSS_SCOPE_DEFAULT_DENY_REQUIRED": s.get("cross_scope_default_deny") is True,
        "RLS_DEFENSE_IN_DEPTH_REQUIRED": s.get("rls_defense_in_depth") is True,
        "APP_SCOPE_CHECKS_REQUIRED": s.get("application_scope_checks") is True,
        "NO_UNSCOPED_ADMIN_BYPASS_REQUIRED": s.get("no_unscoped_admin_bypass") is True,
    }
    for blocker, ok in scope_checks.items():
        if not ok:
            blockers.append(blocker)

    tx_checks = {
        "APPEND_MESSAGE_ATOMIC_REQUIRED": t.get("append_message_atomic") is True,
        "MESSAGE_SEQUENCE_LOCK_REQUIRED": t.get("sequence_lock_required") is True,
        "IDEMPOTENCY_REQUIRED": t.get("idempotency_required") is True,
        "DUPLICATE_APPEND_SAFE_REQUIRED": t.get("duplicate_append_safe") is True,
        "CONVERSATION_COUNT_UPDATE_ATOMIC_REQUIRED": t.get("conversation_count_atomic") is True,
        "CHECKPOINT_ADVANCE_MONOTONIC_REQUIRED": t.get("checkpoint_monotonic") is True,
        "NO_AUTO_RETRY_UNKNOWN_COMMIT_REQUIRED": t.get("no_auto_retry_unknown_commit") is True,
    }
    for blocker, ok in tx_checks.items():
        if not ok:
            blockers.append(blocker)

    health_checks = {
        "PRE_OPERATION_HEALTH_REQUIRED": h.get("pre_operation_health_required") is True,
        "SCHEMA_VERSION_HEALTH_REQUIRED": h.get("schema_version_health") is True,
        "SCOPE_POLICY_HEALTH_REQUIRED": h.get("scope_policy_health") is True,
        "FAIL_CLOSED_REQUIRED": h.get("fail_closed") is True,
        "UNKNOWN_COMMIT_EXPLICIT_REQUIRED": h.get("unknown_commit_explicit") is True,
    }
    for blocker, ok in health_checks.items():
        if not ok:
            blockers.append(blocker)

    if t.get("blind_retry_after_unknown_commit") is True:
        blockers.append("BLIND_RETRY_AFTER_UNKNOWN_COMMIT_FORBIDDEN")
    if s.get("global_lookup_without_scope") is True:
        blockers.append("GLOBAL_LOOKUP_WITHOUT_SCOPE_FORBIDDEN")
    if i.get("store_calls_provider") is True:
        blockers.append("STORE_PROVIDER_CALL_FORBIDDEN")

    common = dict(
        design_only=True,
        preserves_existing_store_protocol=True,
        required_methods=REQUIRED_METHODS,
        scope_required_on_every_operation=True,
        row_level_security_is_defense_in_depth=True,
        no_provider_dependency=True,
        unknown_commit_state="COMMIT_OUTCOME_UNKNOWN",
        next_allowed_step=NEXT_ALLOWED_STEP,
    )
    if blockers:
        return _result("BLOCKED", blockers, **common)
    return _result(READY, [], **common)

__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "REQUIRED_METHODS",
    "FALSE_FIELDS",
    "evaluate_postgres_store_adapter_contract",
]
