"""AION B2B execution audit seal persistence contract V1.

Design-only, fail-closed and non-executable.

Defines how a future terminal audit seal must be durably persisted after the
Execution Audit Seal Contract has produced a valid deterministic seal manifest.

Persistence is append-only and exactly-once for the canonical execution +
terminal revision. The same seal digest may be replayed idempotently; a
different seal digest for the same terminal identity is a conflict. A persisted
seal cannot be deleted, replaced, crossgraded, or used to reopen execution.

This module does NOT open a store, write a row, perform CAS, generate/sign a
seal, load a private key, query a provider, open network transport, retry,
reconcile, compensate, bill, contact customers, write CRM, deploy or mutate
production.

Maximum positive state:
READY_FOR_EXECUTION_AUDIT_SEAL_PERSISTENCE_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_execution_audit_seal_contract_v1 as seal

SCHEMA = "ATLASQUANT_AION_B2B_EXECUTION_AUDIT_SEAL_PERSISTENCE_CONTRACT_V1"
READY = "READY_FOR_EXECUTION_AUDIT_SEAL_PERSISTENCE_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_EXECUTION_TERMINAL_CERTIFICATE_CONTRACT_ONLY"

PERSISTENCE_MODE = "APPEND_ONLY_CAS_AUDIT_SEAL_COMMIT"
FINOPS_CAP_CENTS_REQUIRED = 20000

CORE_EXECUTION_STORE = "atlasquant_aion_durable_execution_kernel.DurableExecutionStore"
CORE_EXECUTION_ID = "atlasquant_aion_durable_execution_kernel.canonical_execution_id"

REQUIRED_SEAL_PERSISTENCE_INVARIANTS = (
    "CANONICAL_EXECUTION_ID_REQUIRED",
    "TERMINAL_REVISION_REQUIRED",
    "TERMINAL_FINALIZATION_RECORD_REQUIRED",
    "VALID_AUDIT_SEAL_CONTRACT_REQUIRED",
    "AUDIT_SEAL_DIGEST_REQUIRED",
    "EXPECTED_PRE_SEAL_REVISION_REQUIRED",
    "COMPARE_AND_SET_REQUIRED",
    "SINGLE_SEAL_WINNER_REQUIRED",
    "AUDIT_SEAL_DIGEST_UNIQUENESS_REQUIRED",
    "SEAL_RECORD_APPEND_ONLY",
    "SEAL_RECORD_IMMUTABLE",
    "SEAL_RECORD_DELETE_FORBIDDEN",
    "SEAL_RECORD_REPLACE_FORBIDDEN",
    "TERMINAL_EXECUTION_REOPEN_FORBIDDEN",
    "SAME_SEAL_SAME_DIGEST_IS_IDEMPOTENT_REPLAY",
    "SAME_TERMINAL_IDENTITY_DIFFERENT_SEAL_DIGEST_IS_CONFLICT",
    "DURABLE_REOPEN_MUST_PRESERVE_SEAL_RECORD",
    "CRASH_AFTER_SEAL_COMMIT_MUST_REPLAY_SEAL_RECORD",
    "CRASH_BEFORE_SEAL_COMMIT_MUST_NOT_INFER_PERSISTED_SEAL",
    "SEAL_PERSISTENCE_DOES_NOT_CREATE_EXECUTION_AUTHORITY",
)

REQUIRED_SEAL_PERSISTENCE_BINDINGS = (
    "execution_id",
    "terminal_revision",
    "expected_pre_seal_revision",
    "final_execution_state",
    "finalization_record_digest",
    "execution_finalization_persistence_record_digest",
    "execution_audit_seal_contract_digest",
    "audit_seal_manifest_digest",
    "audit_seal_digest",
    "digest_algorithm",
    "canonical_encoding",
    "pre_terminal_audit_chain_digest",
    "finops_observation_digest",
    "observability_trace_id",
)

REQUIRED_SEAL_REOPEN_ASSERTIONS = (
    "SEAL_RECORD_EXISTS_AFTER_REOPEN",
    "EXECUTION_ID_MATCH",
    "TERMINAL_REVISION_MATCH",
    "FINAL_EXECUTION_STATE_MATCH",
    "FINALIZATION_RECORD_DIGEST_MATCH",
    "AUDIT_SEAL_MANIFEST_DIGEST_MATCH",
    "AUDIT_SEAL_DIGEST_MATCH",
    "DIGEST_ALGORITHM_MATCH",
    "CANONICAL_ENCODING_MATCH",
    "NO_DUPLICATE_SEAL_RECORD",
    "NO_SEAL_REVISION_REGRESSION",
)

SEAL_PERSISTENCE_CONFLICTS = (
    "TERMINAL_RECORD_MISSING",
    "PRE_SEAL_REVISION_MISMATCH",
    "AUDIT_SEAL_CONTRACT_INVALID",
    "AUDIT_SEAL_DIGEST_MISSING",
    "EXECUTION_ALREADY_SEALED_WITH_DIFFERENT_DIGEST",
    "TERMINAL_REVISION_ALREADY_SEALED_WITH_DIFFERENT_DIGEST",
    "FINALIZATION_RECORD_DIGEST_CONFLICT",
    "SEAL_MANIFEST_DIGEST_CONFLICT",
    "DIGEST_ALGORITHM_CONFLICT",
    "CANONICAL_ENCODING_CONFLICT",
    "AUDIT_CHAIN_DIGEST_CONFLICT",
    "FINOPS_OBSERVATION_CONFLICT",
    "REOPEN_SEAL_RECORD_MISMATCH",
)

FORBIDDEN_PERSISTENCE_MATERIAL = (
    "sqlite_path_value",
    "database_connection_value",
    "private_signing_key_value",
    "credential_value",
    "secret_value",
    "api_key_value",
    "access_token_value",
    "private_key_value",
    "payload_body_value",
    "shell_command_value",
)

FALSE_FIELDS = (
    "persistence_verified",
    "store_opened",
    "database_opened",
    "transaction_started",
    "cas_attempted",
    "cas_succeeded",
    "seal_generated",
    "seal_signed",
    "seal_record_written",
    "seal_persisted",
    "seal_reopened",
    "seal_deleted",
    "seal_replaced",
    "private_key_loaded",
    "terminal_record_mutated",
    "execution_reopened",
    "execution_authority_created",
    "retry_authorized",
    "retry_performed",
    "reconciliation_performed",
    "rollback_performed",
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


def build_execution_audit_seal_persistence_contract(
    *,
    audit_seal_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define durable audit-seal persistence semantics; persist nothing."""
    row = dict(audit_seal_review) if isinstance(audit_seal_review, Mapping) else {}
    blockers: list[str] = []

    if row.get("schema") != seal.SCHEMA:
        blockers.append("AUDIT_SEAL_SCHEMA_REQUIRED")
    if row.get("state") != seal.READY:
        blockers.append("AUDIT_SEAL_DESIGN_REVIEW_REQUIRED")
    if row.get("execution_audit_seal_design_only") is not True:
        blockers.append("AUDIT_SEAL_NOT_DESIGN_ONLY")
    if row.get("fail_closed") is not True:
        blockers.append("FAIL_CLOSED_AUDIT_SEAL_REQUIRED")
    if row.get("deterministic_manifest_required") is not True:
        blockers.append("DETERMINISTIC_MANIFEST_REQUIRED")
    if row.get("canonical_encoding_required") is not True:
        blockers.append("CANONICAL_ENCODING_REQUIRED")
    if row.get("digest_algorithm") != "SHA256":
        blockers.append("SHA256_DIGEST_REQUIRED")
    if row.get("canonical_encoding") != "UTF8_CANONICAL_JSON":
        blockers.append("UTF8_CANONICAL_JSON_REQUIRED")
    if row.get("seal_immutable") is not True:
        blockers.append("IMMUTABLE_SEAL_REQUIRED")
    if row.get("seal_append_only") is not True:
        blockers.append("APPEND_ONLY_SEAL_REQUIRED")
    if row.get("seal_creates_execution_authority") is not False:
        blockers.append("SEAL_MUST_NOT_CREATE_EXECUTION_AUTHORITY")
    if row.get("seal_authorizes_retry") is not False:
        blockers.append("SEAL_MUST_NOT_AUTHORIZE_RETRY")
    if row.get("seal_authorizes_reopen") is not False:
        blockers.append("SEAL_MUST_NOT_AUTHORIZE_REOPEN")
    if row.get("seal_authorizes_external_effect") is not False:
        blockers.append("SEAL_MUST_NOT_AUTHORIZE_EXTERNAL_EFFECT")
    if row.get("finops_cap_cents") != FINOPS_CAP_CENTS_REQUIRED:
        blockers.append("FINOPS_CAP_MUST_REMAIN_20000_CENTS")
    if row.get("next_allowed_step") != seal.NEXT_ALLOWED_STEP:
        blockers.append("AUDIT_SEAL_NEXT_STEP_INVALID")

    for key in seal.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("AUDIT_SEAL_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            execution_audit_seal_persistence_design_only=True,
            persistence_mode=PERSISTENCE_MODE,
            fail_closed=True,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        execution_audit_seal_persistence_design_only=True,
        persistence_mode=PERSISTENCE_MODE,
        fail_closed=True,
        reuses_existing_core_durable_store=True,
        canonical_execution_identity_required=True,
        compare_and_set_required=True,
        exactly_once_seal_commit_required=True,
        append_only_seal_record_required=True,
        immutable_seal_record_required=True,
        seal_delete_forbidden=True,
        seal_replace_forbidden=True,
        terminal_execution_reopen_forbidden=True,
        idempotent_same_digest_replay_required=True,
        different_digest_conflict_required=True,
        durable_reopen_consistency_required=True,
        crash_before_commit_cannot_infer_persisted_seal=True,
        crash_after_commit_replays_seal_record=True,
        persistence_creates_execution_authority=False,
        digest_algorithm="SHA256",
        canonical_encoding="UTF8_CANONICAL_JSON",
        finops_cap_cents=FINOPS_CAP_CENTS_REQUIRED,
        core_execution_store=CORE_EXECUTION_STORE,
        core_execution_id=CORE_EXECUTION_ID,
        required_seal_persistence_invariants=REQUIRED_SEAL_PERSISTENCE_INVARIANTS,
        required_seal_persistence_bindings=REQUIRED_SEAL_PERSISTENCE_BINDINGS,
        required_seal_reopen_assertions=REQUIRED_SEAL_REOPEN_ASSERTIONS,
        seal_persistence_conflicts=SEAL_PERSISTENCE_CONFLICTS,
        forbidden_persistence_material=FORBIDDEN_PERSISTENCE_MATERIAL,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "PERSISTENCE_MODE",
    "FINOPS_CAP_CENTS_REQUIRED",
    "CORE_EXECUTION_STORE",
    "CORE_EXECUTION_ID",
    "REQUIRED_SEAL_PERSISTENCE_INVARIANTS",
    "REQUIRED_SEAL_PERSISTENCE_BINDINGS",
    "REQUIRED_SEAL_REOPEN_ASSERTIONS",
    "SEAL_PERSISTENCE_CONFLICTS",
    "FORBIDDEN_PERSISTENCE_MATERIAL",
    "FALSE_FIELDS",
    "build_execution_audit_seal_persistence_contract",
]
