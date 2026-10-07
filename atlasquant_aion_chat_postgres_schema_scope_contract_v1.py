"""AION Chat Postgres schema + scope contract V1.

Design/CI-only. No SQL is executed and no database is contacted.

The contract defines the minimum relational and authorization invariants that a
future production Postgres adapter must satisfy before migrations or runtime
connections are allowed.

Maximum state:
READY_FOR_POSTGRES_SCHEMA_SCOPE_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

SCHEMA = "ATLASQUANT_AION_CHAT_POSTGRES_SCHEMA_SCOPE_CONTRACT_V1"
READY = "READY_FOR_POSTGRES_SCHEMA_SCOPE_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_POSTGRES_MIGRATION_AND_HEALTH_FAIL_CLOSED_CONTRACT"

FALSE_FIELDS = (
    "sql_executed",
    "connection_opened",
    "database_created",
    "migration_executed",
    "schema_applied",
    "credentials_loaded",
    "secrets_loaded",
    "network_called",
    "billing_executed",
    "deploy_executed",
    "worker_armed",
    "worker_activated",
    "external_action_executed",
)

REQUIRED_TABLES = (
    "chat_conversations",
    "chat_messages",
    "chat_attachment_metadata",
    "chat_access_audit",
)

REQUIRED_SCOPE_COLUMNS = (
    "owner_id",
    "tenant_id",
    "workspace_id",
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

def evaluate_postgres_schema_scope_contract(
    design: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Evaluate a proposed relational design without executing SQL."""
    row = _mapping(design)
    blockers: list[str] = []

    tables = set(str(x) for x in (row.get("tables") or ()))
    for table in REQUIRED_TABLES:
        if table not in tables:
            blockers.append(f"REQUIRED_TABLE_MISSING:{table}")

    scope_columns = set(str(x) for x in (row.get("scope_columns") or ()))
    for column in REQUIRED_SCOPE_COLUMNS:
        if column not in scope_columns:
            blockers.append(f"REQUIRED_SCOPE_COLUMN_MISSING:{column}")

    checks = {
        "SCOPE_COLUMNS_NOT_NULL_REQUIRED": row.get("scope_columns_not_null") is True,
        "COMPOSITE_SCOPE_INDEX_REQUIRED": row.get("composite_scope_index") is True,
        "CONVERSATION_SCOPE_UNIQUE_REQUIRED": row.get("conversation_scope_unique") is True,
        "MESSAGE_SCOPE_BOUND_REQUIRED": row.get("message_scope_bound") is True,
        "ATTACHMENT_SCOPE_BOUND_REQUIRED": row.get("attachment_scope_bound") is True,
        "AUDIT_SCOPE_BOUND_REQUIRED": row.get("audit_scope_bound") is True,
        "CROSS_SCOPE_FOREIGN_KEYS_FORBIDDEN": row.get("cross_scope_foreign_keys_forbidden") is True,
        "CROSS_TENANT_QUERY_DEFAULT_DENY_REQUIRED": row.get("cross_tenant_query_default_deny") is True,
        "PARAMETERIZED_QUERY_ONLY_REQUIRED": row.get("parameterized_queries_only") is True,
        "ROW_LEVEL_SECURITY_PLANNED_REQUIRED": row.get("row_level_security_planned") is True,
        "FORCE_RLS_PLANNED_REQUIRED": row.get("force_row_level_security_planned") is True,
        "LEAST_PRIVILEGE_APP_ROLE_REQUIRED": row.get("least_privilege_app_role") is True,
        "NO_DB_SUPERUSER_FOR_APP_REQUIRED": row.get("app_role_is_not_superuser") is True,
        "MESSAGE_CONTENT_EXCLUDED_FROM_AUDIT_REQUIRED": row.get("audit_excludes_message_content") is True,
        "ATTACHMENT_METADATA_ONLY_REQUIRED": row.get("attachments_metadata_only") is True,
        "SECRETS_FORBIDDEN_IN_CHAT_TABLES": row.get("secrets_forbidden_in_chat_tables") is True,
        "IMMUTABLE_MESSAGE_ID_REQUIRED": row.get("immutable_message_id") is True,
        "ORDERED_SEQUENCE_REQUIRED": row.get("ordered_message_sequence") is True,
        "IDEMPOTENCY_KEY_REQUIRED": row.get("idempotency_key_required") is True,
        "SOFT_OR_POLICY_DELETE_ONLY_REQUIRED": row.get("retention_controlled_delete") is True,
    }
    for blocker, ok in checks.items():
        if not ok:
            blockers.append(blocker)

    if row.get("global_unscoped_conversation_lookup") is True:
        blockers.append("GLOBAL_UNSCOPED_CONVERSATION_LOOKUP_FORBIDDEN")
    if row.get("global_unscoped_message_lookup") is True:
        blockers.append("GLOBAL_UNSCOPED_MESSAGE_LOOKUP_FORBIDDEN")
    if row.get("stores_provider_secret") is True:
        blockers.append("PROVIDER_SECRET_STORAGE_FORBIDDEN")
    if row.get("stores_db_credentials") is True:
        blockers.append("DB_CREDENTIAL_STORAGE_FORBIDDEN")

    common = dict(
        design_only=True,
        provider_vendor_neutral=True,
        required_tables=REQUIRED_TABLES,
        required_scope_columns=REQUIRED_SCOPE_COLUMNS,
        rls_is_defense_in_depth=True,
        application_scope_checks_still_required=True,
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
    "REQUIRED_TABLES",
    "REQUIRED_SCOPE_COLUMNS",
    "evaluate_postgres_schema_scope_contract",
]
