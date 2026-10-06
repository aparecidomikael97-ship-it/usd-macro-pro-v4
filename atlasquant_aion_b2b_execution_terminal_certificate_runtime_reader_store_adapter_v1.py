"""AION B2B terminal-certificate runtime-reader store adapter V1.

Design-only, fail-closed, read-only and non-executable.

Defines the store-adapter boundary for the terminal-certificate runtime reader.
The adapter must reuse the existing DurableExecutionStore as the physical source
of truth and must never invent a sidecar database or a second terminal truth.

Important current-state finding:
The existing durable execution store exposes execution records by execution_id,
but it does not yet expose a terminal-certificate record API and its execution
schema does not contain tenant/workspace scope fields. Therefore this design
MUST NOT claim that live certificate reads are currently bindable.

This module opens no database, instantiates no store, performs no query and
executes no external action.

Maximum positive state:
READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_RUNTIME_READER_STORE_ADAPTER_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_execution_terminal_certificate_runtime_reader_v1 as reader

SCHEMA = (
    "ATLASQUANT_AION_B2B_EXECUTION_TERMINAL_CERTIFICATE_RUNTIME_READER_STORE_ADAPTER_V1"
)
READY = (
    "READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_RUNTIME_READER_STORE_ADAPTER_DESIGN_REVIEW"
)
NEXT_ALLOWED_STEP = "DESIGN_EXECUTION_TERMINAL_CERTIFICATE_DURABLE_STORE_EXTENSION_ONLY"

STORE_ADAPTER_MODE = "READ_ONLY_FAIL_CLOSED_CORE_DURABLE_STORE_ADAPTER"
CORE_EXECUTION_STORE = "atlasquant_aion_durable_execution_kernel.DurableExecutionStore"
CORE_EXECUTION_ID = "atlasquant_aion_durable_execution_kernel.canonical_execution_id"
DIGEST_ALGORITHM = "SHA256"
CANONICAL_ENCODING = "UTF8_CANONICAL_JSON"
FINOPS_CAP_CENTS_REQUIRED = 20000

CURRENT_CORE_STORE_CAPABILITIES = (
    "EXECUTION_RECORD_BY_EXECUTION_ID",
    "IDEMPOTENCY_KEY_UNIQUENESS",
    "EFFECT_KEY_UNIQUENESS",
    "DURABLE_EXECUTION_STATE",
    "RESULT_DIGEST",
    "RECONCILIATION_EVIDENCE_DIGEST",
)

MISSING_REQUIRED_LIVE_CAPABILITIES = (
    "TERMINAL_CERTIFICATE_RECORD_READ_API",
    "TERMINAL_CERTIFICATE_DIGEST_READ_API",
    "TERMINAL_CERTIFICATE_REVISION_READ_API",
    "TENANT_SCOPE_BINDING",
    "WORKSPACE_SCOPE_BINDING",
    "CERTIFICATE_TO_EXECUTION_FOREIGN_KEY_BINDING",
    "APPEND_ONLY_CERTIFICATE_RECORD_STORAGE",
    "CERTIFICATE_REOPEN_CONSISTENCY_READ",
)

REQUIRED_STORE_ADAPTER_RULES = (
    "REUSE_EXISTING_CORE_DURABLE_STORE",
    "SECOND_DATABASE_FORBIDDEN",
    "SIDECAR_TERMINAL_TRUTH_FORBIDDEN",
    "CANONICAL_EXECUTION_ID_REQUIRED",
    "EXACT_TENANT_SCOPE_REQUIRED",
    "EXACT_WORKSPACE_SCOPE_REQUIRED",
    "CERTIFICATE_RECORD_MUST_BE_DURABLY_PERSISTED",
    "CERTIFICATE_RECORD_MUST_BIND_TO_EXECUTION_RECORD",
    "CERTIFICATE_TERMINAL_REVISION_MUST_MATCH",
    "CERTIFICATE_DIGEST_MUST_MATCH",
    "FINALIZATION_DIGEST_MUST_MATCH",
    "AUDIT_SEAL_DIGEST_MUST_MATCH",
    "SNAPSHOT_CONSISTENCY_REQUIRED",
    "MISSING_STORE_CAPABILITY_MUST_FAIL_CLOSED",
    "STORE_SCHEMA_MISMATCH_MUST_FAIL_CLOSED",
    "CERTIFICATE_RECORD_MISSING_MUST_RETURN_UNAVAILABLE",
    "DIGEST_MISMATCH_MUST_RETURN_MISMATCH",
    "STALE_EVIDENCE_MUST_RETURN_STALE",
    "UNKNOWN_STORE_STATE_MUST_FAIL_CLOSED",
    "READ_ONLY_TRANSACTION_REQUIRED_WHEN_IMPLEMENTED",
    "NO_STORE_MUTATION_FROM_READER_ADAPTER",
    "NO_PROVIDER_FALLBACK",
    "NO_NETWORK_FALLBACK",
    "NO_READ_STATUS_GRANTS_AUTHORITY",
)

REQUIRED_FUTURE_STORE_EXTENSION_FIELDS = (
    "execution_id",
    "tenant_id",
    "workspace_id",
    "terminal_revision",
    "final_execution_state",
    "certificate_manifest_digest",
    "certificate_digest",
    "certificate_persistence_record_digest",
    "finalization_record_digest",
    "audit_seal_manifest_digest",
    "audit_seal_persistence_record_digest",
    "terminal_evidence_set_digest",
    "finops_observation_digest",
    "observability_trace_id",
    "pre_terminal_audit_chain_digest",
    "digest_algorithm",
    "canonical_encoding",
    "persisted_at",
)

FORBIDDEN_STORE_ADAPTER_BEHAVIORS = (
    "create_sidecar_database",
    "create_second_terminal_truth",
    "write_execution_record",
    "write_certificate_record",
    "delete_certificate_record",
    "replace_certificate_record",
    "reopen_execution",
    "retry_execution",
    "reconcile_outcome",
    "rollback_execution",
    "compensate_effect",
    "call_provider",
    "open_network_fallback",
    "bill_customer",
    "write_crm",
    "provision_service",
    "deploy_service",
    "mutate_production",
)

FALSE_FIELDS = (
    "live_binding_available",
    "store_adapter_connected",
    "store_opened",
    "database_opened",
    "read_transaction_started",
    "runtime_read_performed",
    "certificate_record_loaded",
    "certificate_verified_live",
    "tenant_scope_verified_live",
    "workspace_scope_verified_live",
    "certificate_record_mutated",
    "terminal_record_mutated",
    "seal_record_mutated",
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


def build_execution_terminal_certificate_runtime_reader_store_adapter_contract(
    *,
    runtime_reader_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define a future read-only store adapter; connect to no store."""
    row = dict(runtime_reader_review) if isinstance(runtime_reader_review, Mapping) else {}
    blockers: list[str] = []

    if row.get("schema") != reader.SCHEMA:
        blockers.append("TERMINAL_CERTIFICATE_RUNTIME_READER_SCHEMA_REQUIRED")
    if row.get("state") != reader.READY:
        blockers.append("TERMINAL_CERTIFICATE_RUNTIME_READER_DESIGN_REVIEW_REQUIRED")
    if row.get("execution_terminal_certificate_runtime_reader_design_only") is not True:
        blockers.append("TERMINAL_CERTIFICATE_RUNTIME_READER_NOT_DESIGN_ONLY")
    if row.get("fail_closed") is not True:
        blockers.append("FAIL_CLOSED_RUNTIME_READER_REQUIRED")
    if row.get("read_only") is not True:
        blockers.append("READ_ONLY_RUNTIME_READER_REQUIRED")
    if row.get("observational_only") is not True:
        blockers.append("OBSERVATIONAL_ONLY_RUNTIME_READER_REQUIRED")
    if row.get("read_model_is_only_logical_source") is not True:
        blockers.append("READ_MODEL_MUST_REMAIN_ONLY_LOGICAL_SOURCE")
    if row.get("persisted_certificate_required") is not True:
        blockers.append("PERSISTED_CERTIFICATE_REQUIRED")
    if row.get("canonical_execution_id_required") is not True:
        blockers.append("CANONICAL_EXECUTION_ID_REQUIRED")
    if row.get("tenant_scope_must_match") is not True:
        blockers.append("TENANT_SCOPE_MATCH_REQUIRED")
    if row.get("workspace_scope_must_match") is not True:
        blockers.append("WORKSPACE_SCOPE_MATCH_REQUIRED")
    if row.get("snapshot_consistency_required") is not True:
        blockers.append("SNAPSHOT_CONSISTENCY_REQUIRED")
    if row.get("provider_fallback_forbidden") is not True:
        blockers.append("PROVIDER_FALLBACK_MUST_BE_FORBIDDEN")
    if row.get("network_fallback_forbidden") is not True:
        blockers.append("NETWORK_FALLBACK_MUST_BE_FORBIDDEN")
    if row.get("mutation_forbidden") is not True:
        blockers.append("RUNTIME_READER_MUTATION_MUST_BE_FORBIDDEN")
    if row.get("runtime_reader_creates_execution_authority") is not False:
        blockers.append("RUNTIME_READER_MUST_NOT_CREATE_AUTHORITY")
    if row.get("runtime_reader_authorizes_retry") is not False:
        blockers.append("RUNTIME_READER_MUST_NOT_AUTHORIZE_RETRY")
    if row.get("runtime_reader_authorizes_reopen") is not False:
        blockers.append("RUNTIME_READER_MUST_NOT_AUTHORIZE_REOPEN")
    if row.get("runtime_reader_authorizes_external_effect") is not False:
        blockers.append("RUNTIME_READER_MUST_NOT_AUTHORIZE_EXTERNAL_EFFECT")
    if row.get("digest_algorithm") != DIGEST_ALGORITHM:
        blockers.append("SHA256_DIGEST_REQUIRED")
    if row.get("canonical_encoding") != CANONICAL_ENCODING:
        blockers.append("UTF8_CANONICAL_JSON_REQUIRED")
    if row.get("finops_cap_cents") != FINOPS_CAP_CENTS_REQUIRED:
        blockers.append("FINOPS_CAP_MUST_REMAIN_20000_CENTS")
    if row.get("next_allowed_step") != reader.NEXT_ALLOWED_STEP:
        blockers.append("TERMINAL_CERTIFICATE_RUNTIME_READER_NEXT_STEP_INVALID")

    for key in reader.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("TERMINAL_CERTIFICATE_RUNTIME_READER_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            execution_terminal_certificate_runtime_reader_store_adapter_design_only=True,
            store_adapter_mode=STORE_ADAPTER_MODE,
            fail_closed=True,
            read_only=True,
            current_core_store_live_binding_ready=False,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        execution_terminal_certificate_runtime_reader_store_adapter_design_only=True,
        store_adapter_mode=STORE_ADAPTER_MODE,
        fail_closed=True,
        read_only=True,
        observational_only=True,
        reuses_existing_core_durable_store=True,
        second_database_forbidden=True,
        sidecar_terminal_truth_forbidden=True,
        current_core_store_live_binding_ready=False,
        durable_store_extension_required=True,
        missing_store_capabilities_fail_closed=True,
        store_adapter_creates_execution_authority=False,
        store_adapter_authorizes_retry=False,
        store_adapter_authorizes_reopen=False,
        store_adapter_authorizes_external_effect=False,
        core_execution_store=CORE_EXECUTION_STORE,
        core_execution_id=CORE_EXECUTION_ID,
        digest_algorithm=DIGEST_ALGORITHM,
        canonical_encoding=CANONICAL_ENCODING,
        finops_cap_cents=FINOPS_CAP_CENTS_REQUIRED,
        current_core_store_capabilities=CURRENT_CORE_STORE_CAPABILITIES,
        missing_required_live_capabilities=MISSING_REQUIRED_LIVE_CAPABILITIES,
        required_store_adapter_rules=REQUIRED_STORE_ADAPTER_RULES,
        required_future_store_extension_fields=REQUIRED_FUTURE_STORE_EXTENSION_FIELDS,
        forbidden_store_adapter_behaviors=FORBIDDEN_STORE_ADAPTER_BEHAVIORS,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "STORE_ADAPTER_MODE",
    "CORE_EXECUTION_STORE",
    "CORE_EXECUTION_ID",
    "DIGEST_ALGORITHM",
    "CANONICAL_ENCODING",
    "FINOPS_CAP_CENTS_REQUIRED",
    "CURRENT_CORE_STORE_CAPABILITIES",
    "MISSING_REQUIRED_LIVE_CAPABILITIES",
    "REQUIRED_STORE_ADAPTER_RULES",
    "REQUIRED_FUTURE_STORE_EXTENSION_FIELDS",
    "FORBIDDEN_STORE_ADAPTER_BEHAVIORS",
    "FALSE_FIELDS",
    "build_execution_terminal_certificate_runtime_reader_store_adapter_contract",
]
