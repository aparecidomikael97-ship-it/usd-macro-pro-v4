"""AION Chat Postgres migration + health fail-closed contract V1.

Design/CI-only. It performs no SQL, migration, database connection, provider
call, billing, deploy or runtime write.

Maximum state:
READY_FOR_POSTGRES_MIGRATION_HEALTH_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_CHAT_POSTGRES_MIGRATION_HEALTH_CONTRACT_V1"
READY = "READY_FOR_POSTGRES_MIGRATION_HEALTH_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_PRODUCTION_CHAT_POSTGRES_ADAPTER_CONTRACT"

FALSE_FIELDS = (
    "sql_executed",
    "connection_opened",
    "migration_executed",
    "schema_changed",
    "database_created",
    "credentials_loaded",
    "secrets_loaded",
    "network_called",
    "provider_called",
    "billing_executed",
    "deploy_executed",
    "worker_armed",
    "external_action_executed",
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

def evaluate_migration_health_contract(
    migration: Mapping[str, Any] | None,
    health: Mapping[str, Any] | None,
) -> dict[str, Any]:
    m = _mapping(migration)
    h = _mapping(health)
    blockers: list[str] = []

    migration_checks = {
        "VERSIONED_MIGRATIONS_REQUIRED": m.get("versioned") is True,
        "MIGRATION_CHECKSUM_REQUIRED": m.get("checksum_required") is True,
        "SINGLE_MIGRATION_WRITER_REQUIRED": m.get("single_writer_lock") is True,
        "NO_AUTO_PROD_MIGRATION_ON_STARTUP": m.get("auto_migrate_on_startup") is False,
        "ISOLATED_COPY_VALIDATION_REQUIRED": m.get("isolated_copy_test_required") is True,
        "PRE_MIGRATION_RECOVERY_POINT_REQUIRED": m.get("recovery_point_required") is True,
        "ADDITIVE_FIRST_REQUIRED": m.get("additive_first") is True,
        "DESTRUCTIVE_V1_FORBIDDEN": m.get("destructive_changes_v1_forbidden") is True,
        "SCHEMA_VERSION_COMPATIBILITY_REQUIRED": m.get("schema_version_compatibility") is True,
        "ROLL_FORWARD_PLAN_REQUIRED": m.get("roll_forward_plan") is True,
        "OWNER_AUTH_REQUIRED_FOR_REAL_MIGRATION": m.get("real_migration_requires_owner_authorization") is True,
    }
    for blocker, ok in migration_checks.items():
        if not ok:
            blockers.append(blocker)

    health_checks = {
        "DB_HEALTH_REQUIRED": h.get("database_health_required") is True,
        "SCHEMA_COMPATIBILITY_HEALTH_REQUIRED": h.get("schema_compatibility_required") is True,
        "SCOPE_POLICY_HEALTH_REQUIRED": h.get("scope_policy_health_required") is True,
        "FAIL_CLOSED_ON_DB_UNAVAILABLE_REQUIRED": h.get("fail_closed_on_db_unavailable") is True,
        "NO_SESSION_ONLY_DURABLE_FALLBACK": h.get("session_only_fallback_forbidden") is True,
        "NO_STAGING_SQLITE_PROD_FALLBACK": h.get("staging_sqlite_fallback_forbidden") is True,
        "USER_TURN_DURABLE_BEFORE_PROVIDER_REQUIRED": h.get("persist_user_turn_before_provider") is True,
        "ASSISTANT_DURABILITY_EXPLICIT_REQUIRED": h.get("assistant_persistence_must_be_confirmed") is True,
        "UNKNOWN_PERSISTENCE_NEVER_SUCCESS": h.get("unknown_persistence_never_success") is True,
        "IDEMPOTENT_RETRY_REQUIRED": h.get("idempotent_retry_required") is True,
        "HEALTH_DEGRADATION_VISIBLE_REQUIRED": h.get("degraded_state_visible") is True,
    }
    for blocker, ok in health_checks.items():
        if not ok:
            blockers.append(blocker)

    if h.get("claims_saved_when_unconfirmed") is True:
        blockers.append("FALSE_DURABILITY_CLAIM_FORBIDDEN")
    if h.get("provider_call_before_user_persist") is True:
        blockers.append("PROVIDER_CALL_BEFORE_USER_PERSIST_FORBIDDEN")
    if m.get("production_migration_implicit_authority") is True:
        blockers.append("IMPLICIT_PRODUCTION_MIGRATION_AUTHORITY_FORBIDDEN")

    common = dict(
        design_only=True,
        migrations_separate_from_app_startup=True,
        production_migration_is_protected_action=True,
        durability_truthful=True,
        provider_call_order_guarded=True,
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
    "evaluate_migration_health_contract",
]
