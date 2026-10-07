"""AION B2B terminal-certificate durable store extension V1.

Design-only, fail-closed and non-executable.

Defines the additive same-database schema/API extension required before the
terminal-certificate runtime reader may bind to DurableExecutionStore.

The current store safely persists execution lifecycle state but has no durable
tenant/workspace binding, no terminal revision API and no physical records for
the finalization -> audit-seal -> terminal-certificate chain. This contract
makes those gaps explicit and defines an additive path that preserves one
physical source of truth.

No migration is executed here. No SQLite connection is opened, no table is
created and no production state is changed.

Maximum positive state:
READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_DURABLE_STORE_EXTENSION_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_execution_terminal_certificate_runtime_reader_store_adapter_v1 as adapter

SCHEMA = "ATLASQUANT_AION_B2B_EXECUTION_TERMINAL_CERTIFICATE_DURABLE_STORE_EXTENSION_V1"
READY = "READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_DURABLE_STORE_EXTENSION_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = (
    "IMPLEMENT_EXECUTION_TERMINAL_CERTIFICATE_DURABLE_STORE_EXTENSION_OFFLINE_ONLY"
)

EXTENSION_MODE = "ADDITIVE_SAME_DB_TERMINAL_EVIDENCE_EXTENSION"
CORE_EXECUTION_STORE = "atlasquant_aion_durable_execution_kernel.DurableExecutionStore"
CORE_EXECUTION_TABLE = "executions"
DIGEST_ALGORITHM = "SHA256"
CANONICAL_ENCODING = "UTF8_CANONICAL_JSON"
FINOPS_CAP_CENTS_REQUIRED = 20000

REQUIRED_ADDITIVE_TABLES = (
    "execution_scope_bindings",
    "execution_terminal_finalizations",
    "execution_audit_seals",
    "execution_terminal_certificates",
)

EXECUTION_SCOPE_BINDING_FIELDS = (
    "execution_id",
    "owner_id",
    "tenant_id",
    "workspace_id",
    "scope_digest",
    "scope_binding_source_digest",
    "bound_at",
)

TERMINAL_FINALIZATION_FIELDS = (
    "execution_id",
    "terminal_revision",
    "core_execution_state",
    "final_execution_state",
    "execution_finalization_contract_digest",
    "finalization_record_digest",
    "external_effect_outcome_receipt_digest",
    "outcome_reconciliation_record_digest",
    "rollback_or_compensation_settlement_digest",
    "finops_estimate_digest",
    "finops_observation_digest",
    "observability_trace_id",
    "pre_terminal_audit_chain_digest",
    "persisted_at",
)

AUDIT_SEAL_FIELDS = (
    "execution_id",
    "terminal_revision",
    "finalization_record_digest",
    "audit_seal_manifest_digest",
    "audit_seal_record_digest",
    "audit_chain_digest",
    "finops_observation_digest",
    "observability_trace_id",
    "persisted_at",
)

TERMINAL_CERTIFICATE_FIELDS = (
    "execution_id",
    "terminal_revision",
    "final_execution_state",
    "scope_digest",
    "finalization_record_digest",
    "audit_seal_manifest_digest",
    "audit_seal_record_digest",
    "certificate_manifest_digest",
    "certificate_digest",
    "certificate_persistence_record_digest",
    "terminal_evidence_set_digest",
    "finops_observation_digest",
    "observability_trace_id",
    "pre_terminal_audit_chain_digest",
    "digest_algorithm",
    "canonical_encoding",
    "persisted_at",
)

REQUIRED_EXTENSION_INVARIANTS = (
    "SAME_DATABASE_AS_CORE_EXECUTION_STORE",
    "CORE_EXECUTIONS_TABLE_REMAINS_SOURCE_OF_EXECUTION_IDENTITY",
    "ADDITIVE_MIGRATION_ONLY",
    "NO_DESTRUCTIVE_EXECUTIONS_TABLE_REBUILD",
    "NO_SIDECAR_DATABASE",
    "NO_SECOND_TERMINAL_TRUTH",
    "FOREIGN_KEY_TO_EXECUTIONS_REQUIRED",
    "EXECUTION_SCOPE_BINDING_ONE_TO_ONE",
    "EXECUTION_SCOPE_BINDING_IMMUTABLE",
    "SCOPE_BACKFILL_BY_GUESS_FORBIDDEN",
    "LEGACY_UNSCOPED_EXECUTION_MUST_FAIL_CLOSED",
    "DURABLE_TERMINAL_REVISION_REQUIRED",
    "TIMESTAMP_AS_TERMINAL_REVISION_FORBIDDEN",
    "FINALIZATION_RECORD_APPEND_ONLY",
    "FINALIZATION_RECORD_IMMUTABLE",
    "AUDIT_SEAL_RECORD_APPEND_ONLY",
    "AUDIT_SEAL_RECORD_IMMUTABLE",
    "TERMINAL_CERTIFICATE_RECORD_APPEND_ONLY",
    "TERMINAL_CERTIFICATE_RECORD_IMMUTABLE",
    "ONE_TERMINAL_FINALIZATION_PER_EXECUTION",
    "ONE_AUDIT_SEAL_PER_FINALIZATION",
    "ONE_TERMINAL_CERTIFICATE_PER_FINALIZATION",
    "FINALIZATION_MUST_PRECEDE_AUDIT_SEAL",
    "AUDIT_SEAL_MUST_PRECEDE_CERTIFICATE",
    "CERTIFICATE_MUST_BIND_SCOPE_DIGEST",
    "CERTIFICATE_MUST_BIND_FINALIZATION_DIGEST",
    "CERTIFICATE_MUST_BIND_AUDIT_SEAL_DIGEST",
    "CERTIFICATE_MUST_BIND_FINOPS_OBSERVATION_DIGEST",
    "CERTIFICATE_MUST_BIND_OBSERVABILITY_TRACE",
    "CAS_OR_EQUIVALENT_SINGLE_WINNER_REQUIRED",
    "SAME_DIGEST_REPLAY_IDEMPOTENT",
    "DIVERGENT_DIGEST_CONFLICT_FAIL_CLOSED",
    "CRASH_BEFORE_COMMIT_MUST_NOT_INFER_RECORD",
    "CRASH_AFTER_COMMIT_MUST_REPLAY_RECORD",
    "READ_PATH_MUST_USE_CONSISTENT_SNAPSHOT",
    "NO_EXTENSION_RECORD_GRANTS_EXECUTION_AUTHORITY",
)

REQUIRED_FUTURE_STORE_APIS = (
    "bind_execution_scope_once",
    "get_execution_scope",
    "persist_terminal_finalization_once",
    "get_terminal_finalization",
    "persist_audit_seal_once",
    "get_audit_seal",
    "persist_terminal_certificate_once",
    "get_terminal_certificate",
    "read_terminal_certificate_snapshot",
)

MIGRATION_GATES = (
    "SCHEMA_VERSION_BUMP_REQUIRED",
    "EXISTING_EXECUTION_ROWS_PRESERVED",
    "FOREIGN_KEYS_ENABLED",
    "WAL_AND_SYNCHRONOUS_FULL_PRESERVED",
    "MIGRATION_TRANSACTION_REQUIRED",
    "MIGRATION_REOPEN_TEST_REQUIRED",
    "MIGRATION_CRASH_BEFORE_COMMIT_TEST_REQUIRED",
    "MIGRATION_CRASH_AFTER_COMMIT_TEST_REQUIRED",
    "LEGACY_UNSCOPED_READ_RETURNS_FAIL_CLOSED",
    "NO_AUTOMATIC_LEGACY_SCOPE_GUESS",
    "NO_PROVIDER_OR_NETWORK_DURING_MIGRATION",
    "BACKUP_ROLLBACK_PLAN_REQUIRED_BEFORE_NON_TEST_MIGRATION",
)

FORBIDDEN_EXTENSION_BEHAVIORS = (
    "create_sidecar_database",
    "replace_core_execution_store",
    "drop_executions_table",
    "truncate_executions_table",
    "rewrite_execution_identity",
    "guess_legacy_tenant",
    "guess_legacy_workspace",
    "delete_terminal_finalization",
    "replace_terminal_finalization",
    "delete_audit_seal",
    "replace_audit_seal",
    "delete_terminal_certificate",
    "replace_terminal_certificate",
    "reopen_execution",
    "authorize_retry",
    "call_provider",
    "open_network",
    "bill_customer",
    "write_crm",
    "deploy_service",
    "mutate_production",
)

FALSE_FIELDS = (
    "migration_executed",
    "schema_changed",
    "store_opened",
    "database_opened",
    "transaction_started",
    "table_created",
    "column_added",
    "row_written",
    "scope_bound",
    "finalization_persisted",
    "audit_seal_persisted",
    "terminal_certificate_persisted",
    "runtime_reader_connected",
    "live_binding_available",
    "execution_reopened",
    "execution_authority_created",
    "retry_authorized",
    "retry_performed",
    "reconciliation_authorized",
    "reconciliation_performed",
    "rollback_authorized",
    "rollback_performed",
    "compensation_authorized",
    "compensation_performed",
    "network_called",
    "provider_called",
    "external_effect_attempted",
    "external_action_executed",
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


def build_execution_terminal_certificate_durable_store_extension_contract(
    *,
    store_adapter_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define the additive durable-store extension; migrate nothing."""
    row = dict(store_adapter_review) if isinstance(store_adapter_review, Mapping) else {}
    blockers: list[str] = []

    if row.get("schema") != adapter.SCHEMA:
        blockers.append("RUNTIME_READER_STORE_ADAPTER_SCHEMA_REQUIRED")
    if row.get("state") != adapter.READY:
        blockers.append("RUNTIME_READER_STORE_ADAPTER_DESIGN_REVIEW_REQUIRED")
    if row.get(
        "execution_terminal_certificate_runtime_reader_store_adapter_design_only"
    ) is not True:
        blockers.append("RUNTIME_READER_STORE_ADAPTER_NOT_DESIGN_ONLY")
    if row.get("fail_closed") is not True:
        blockers.append("FAIL_CLOSED_STORE_ADAPTER_REQUIRED")
    if row.get("read_only") is not True:
        blockers.append("READ_ONLY_STORE_ADAPTER_REQUIRED")
    if row.get("reuses_existing_core_durable_store") is not True:
        blockers.append("EXISTING_CORE_DURABLE_STORE_REUSE_REQUIRED")
    if row.get("second_database_forbidden") is not True:
        blockers.append("SECOND_DATABASE_MUST_BE_FORBIDDEN")
    if row.get("sidecar_terminal_truth_forbidden") is not True:
        blockers.append("SIDECAR_TERMINAL_TRUTH_MUST_BE_FORBIDDEN")
    if row.get("current_core_store_live_binding_ready") is not False:
        blockers.append("CURRENT_CORE_STORE_MUST_REMAIN_NOT_LIVE_BINDABLE")
    if row.get("durable_store_extension_required") is not True:
        blockers.append("DURABLE_STORE_EXTENSION_REQUIRED")
    if row.get("missing_store_capabilities_fail_closed") is not True:
        blockers.append("MISSING_STORE_CAPABILITIES_MUST_FAIL_CLOSED")
    if row.get("store_adapter_creates_execution_authority") is not False:
        blockers.append("STORE_ADAPTER_MUST_NOT_CREATE_AUTHORITY")
    if row.get("store_adapter_authorizes_retry") is not False:
        blockers.append("STORE_ADAPTER_MUST_NOT_AUTHORIZE_RETRY")
    if row.get("store_adapter_authorizes_reopen") is not False:
        blockers.append("STORE_ADAPTER_MUST_NOT_AUTHORIZE_REOPEN")
    if row.get("store_adapter_authorizes_external_effect") is not False:
        blockers.append("STORE_ADAPTER_MUST_NOT_AUTHORIZE_EXTERNAL_EFFECT")
    if row.get("core_execution_store") != CORE_EXECUTION_STORE:
        blockers.append("CORE_EXECUTION_STORE_BINDING_MISMATCH")
    if row.get("digest_algorithm") != DIGEST_ALGORITHM:
        blockers.append("SHA256_DIGEST_REQUIRED")
    if row.get("canonical_encoding") != CANONICAL_ENCODING:
        blockers.append("UTF8_CANONICAL_JSON_REQUIRED")
    if row.get("finops_cap_cents") != FINOPS_CAP_CENTS_REQUIRED:
        blockers.append("FINOPS_CAP_MUST_REMAIN_20000_CENTS")
    if row.get("next_allowed_step") != adapter.NEXT_ALLOWED_STEP:
        blockers.append("STORE_ADAPTER_NEXT_STEP_INVALID")

    for key in adapter.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("STORE_ADAPTER_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            execution_terminal_certificate_durable_store_extension_design_only=True,
            extension_mode=EXTENSION_MODE,
            fail_closed=True,
            same_database_required=True,
            implementation_offline_only_pending=True,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        execution_terminal_certificate_durable_store_extension_design_only=True,
        extension_mode=EXTENSION_MODE,
        fail_closed=True,
        same_database_required=True,
        additive_migration_required=True,
        core_executions_table_preserved=True,
        no_sidecar_database=True,
        no_second_terminal_truth=True,
        legacy_unscoped_execution_fails_closed=True,
        scope_backfill_by_guess_forbidden=True,
        durable_terminal_revision_required=True,
        timestamp_as_revision_forbidden=True,
        append_only_terminal_chain_required=True,
        consistent_snapshot_read_required=True,
        implementation_offline_only_pending=True,
        extension_creates_execution_authority=False,
        extension_authorizes_retry=False,
        extension_authorizes_reopen=False,
        extension_authorizes_external_effect=False,
        core_execution_store=CORE_EXECUTION_STORE,
        core_execution_table=CORE_EXECUTION_TABLE,
        digest_algorithm=DIGEST_ALGORITHM,
        canonical_encoding=CANONICAL_ENCODING,
        finops_cap_cents=FINOPS_CAP_CENTS_REQUIRED,
        required_additive_tables=REQUIRED_ADDITIVE_TABLES,
        execution_scope_binding_fields=EXECUTION_SCOPE_BINDING_FIELDS,
        terminal_finalization_fields=TERMINAL_FINALIZATION_FIELDS,
        audit_seal_fields=AUDIT_SEAL_FIELDS,
        terminal_certificate_fields=TERMINAL_CERTIFICATE_FIELDS,
        required_extension_invariants=REQUIRED_EXTENSION_INVARIANTS,
        required_future_store_apis=REQUIRED_FUTURE_STORE_APIS,
        migration_gates=MIGRATION_GATES,
        forbidden_extension_behaviors=FORBIDDEN_EXTENSION_BEHAVIORS,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "EXTENSION_MODE",
    "CORE_EXECUTION_STORE",
    "CORE_EXECUTION_TABLE",
    "DIGEST_ALGORITHM",
    "CANONICAL_ENCODING",
    "FINOPS_CAP_CENTS_REQUIRED",
    "REQUIRED_ADDITIVE_TABLES",
    "EXECUTION_SCOPE_BINDING_FIELDS",
    "TERMINAL_FINALIZATION_FIELDS",
    "AUDIT_SEAL_FIELDS",
    "TERMINAL_CERTIFICATE_FIELDS",
    "REQUIRED_EXTENSION_INVARIANTS",
    "REQUIRED_FUTURE_STORE_APIS",
    "MIGRATION_GATES",
    "FORBIDDEN_EXTENSION_BEHAVIORS",
    "FALSE_FIELDS",
    "build_execution_terminal_certificate_durable_store_extension_contract",
]
