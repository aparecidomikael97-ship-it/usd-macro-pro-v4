"""AION B2B execution finalization persistence contract V1.

Design-only, fail-closed and non-executable.

This layer defines how a future AION runtime must durably persist a terminal
execution finalization record after the execution-finalization contract has
proved that the outcome is finalizable.

The future persistence operation must be append-only, exactly-once by canonical
execution identity and protected by compare-and-set semantics. A terminal
finalization record may never be rewritten into a different terminal state,
deleted to reopen execution, or used to grant new execution authority.

This contract reuses the existing durable execution kernel as the source of
truth. It does NOT instantiate a store, open SQLite, write a row, perform CAS,
query a provider, open network transport, retry, reconcile, compensate, bill,
contact customers, write CRM, provision, deploy or mutate production.

Maximum positive state:
READY_FOR_EXECUTION_FINALIZATION_PERSISTENCE_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_execution_finalization_contract_v1 as finalization

SCHEMA = "ATLASQUANT_AION_B2B_EXECUTION_FINALIZATION_PERSISTENCE_CONTRACT_V1"
READY = "READY_FOR_EXECUTION_FINALIZATION_PERSISTENCE_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_EXECUTION_AUDIT_SEAL_CONTRACT_ONLY"

PERSISTENCE_MODE = "APPEND_ONLY_CAS_TERMINAL_COMMIT"
FINOPS_CAP_CENTS_REQUIRED = 20000

CORE_EXECUTION_STORE = "atlasquant_aion_durable_execution_kernel.DurableExecutionStore"
CORE_EXECUTION_ID = "atlasquant_aion_durable_execution_kernel.canonical_execution_id"

TERMINAL_STATES = (
    "FINALIZED_SUCCESS",
    "FINALIZED_TERMINAL_FAILURE",
)

REQUIRED_PERSISTENCE_INVARIANTS = (
    "CANONICAL_EXECUTION_ID_REQUIRED",
    "EXISTING_EXECUTION_RECORD_REQUIRED",
    "EXPECTED_PRE_FINALIZATION_REVISION_REQUIRED",
    "COMPARE_AND_SET_REQUIRED",
    "SINGLE_TERMINAL_WINNER_REQUIRED",
    "FINALIZATION_DIGEST_UNIQUENESS_REQUIRED",
    "TERMINAL_STATE_APPEND_ONLY",
    "TERMINAL_STATE_IMMUTABLE",
    "TERMINAL_STATE_DELETE_FORBIDDEN",
    "TERMINAL_STATE_REOPEN_FORBIDDEN",
    "TERMINAL_STATE_DOWNGRADE_FORBIDDEN",
    "TERMINAL_STATE_CROSSGRADE_FORBIDDEN",
    "SAME_FINALIZATION_SAME_DIGEST_IS_IDEMPOTENT_REPLAY",
    "SAME_EXECUTION_DIFFERENT_FINALIZATION_DIGEST_IS_CONFLICT",
    "DURABLE_REOPEN_MUST_PRESERVE_TERMINAL_RECORD",
    "CRASH_AFTER_COMMIT_MUST_REPLAY_TERMINAL_RECORD",
    "CRASH_BEFORE_COMMIT_MUST_NOT_INFER_FINALIZATION",
    "AUDIT_CHAIN_DIGEST_REQUIRED",
    "OUTCOME_RECEIPT_CHAIN_DIGEST_REQUIRED",
    "RECONCILIATION_CHAIN_DIGEST_REQUIRED_WHEN_APPLICABLE",
    "ROLLBACK_COMPENSATION_SETTLEMENT_DIGEST_REQUIRED_WHEN_APPLICABLE",
    "FINOPS_OBSERVATION_DIGEST_REQUIRED",
    "NO_EXECUTION_AUTHORITY_GRANTED_BY_PERSISTENCE",
)

REQUIRED_PERSISTENCE_BINDINGS = (
    "execution_id",
    "expected_pre_finalization_revision",
    "final_execution_state",
    "execution_finalization_contract_digest",
    "external_effect_outcome_receipt_digest",
    "outcome_reconciliation_record_digest",
    "durable_dispatch_record_digest",
    "external_effect_call_boundary_digest",
    "execution_envelope_digest",
    "fresh_owner_authorization_digest",
    "provider_adapter_attestation_digest",
    "provider_capability_binding_digest",
    "idempotency_key_digest",
    "effect_key_digest",
    "provider_request_correlation_digest",
    "terminal_evidence_set_digest",
    "expected_postcondition_digest",
    "rollback_plan_digest",
    "rollback_or_compensation_settlement_digest",
    "finops_estimate_digest",
    "finops_observation_digest",
    "observability_trace_id",
    "audit_chain_digest",
    "finalization_record_digest",
)

REQUIRED_REOPEN_ASSERTIONS = (
    "TERMINAL_RECORD_EXISTS_AFTER_REOPEN",
    "TERMINAL_STATE_MATCHES_COMMITTED_STATE",
    "FINALIZATION_RECORD_DIGEST_MATCH",
    "AUDIT_CHAIN_DIGEST_MATCH",
    "EXECUTION_ID_MATCH",
    "IDEMPOTENCY_KEY_DIGEST_MATCH",
    "EFFECT_KEY_DIGEST_MATCH",
    "NO_DUPLICATE_TERMINAL_RECORD",
    "NO_TERMINAL_REVISION_REGRESSION",
)

PERSISTENCE_CONFLICTS = (
    "EXECUTION_RECORD_MISSING",
    "PRE_FINALIZATION_REVISION_MISMATCH",
    "EXECUTION_ALREADY_FINALIZED_WITH_DIFFERENT_STATE",
    "EXECUTION_ALREADY_FINALIZED_WITH_DIFFERENT_DIGEST",
    "FINALIZATION_DIGEST_CONFLICT",
    "AUDIT_CHAIN_DIGEST_CONFLICT",
    "OUTCOME_CHAIN_DIGEST_CONFLICT",
    "RECONCILIATION_CHAIN_DIGEST_CONFLICT",
    "ROLLBACK_COMPENSATION_SETTLEMENT_CONFLICT",
    "FINOPS_OBSERVATION_CONFLICT",
    "TERMINAL_RECORD_DUPLICATE_CONFLICT",
    "REOPEN_TERMINAL_RECORD_MISMATCH",
)

FORBIDDEN_PERSISTENCE_MATERIAL = (
    "sqlite_path_value",
    "database_connection_value",
    "database_cursor_value",
    "credential_value",
    "secret_value",
    "password_value",
    "api_key_value",
    "access_token_value",
    "private_key_value",
    "payload_body_value",
    "raw_provider_response_body",
    "shell_command_value",
)

FALSE_FIELDS = (
    "persistence_verified",
    "store_opened",
    "database_opened",
    "transaction_started",
    "cas_attempted",
    "cas_succeeded",
    "finalization_record_written",
    "terminal_state_persisted",
    "terminal_state_reopened",
    "terminal_state_deleted",
    "execution_reopened",
    "execution_finalized",
    "provider_status_queried",
    "provider_selected",
    "provider_bound",
    "credentials_loaded",
    "secrets_loaded",
    "network_called",
    "provider_called",
    "retry_authorized",
    "retry_performed",
    "reconciliation_authorized",
    "reconciliation_performed",
    "rollback_authorized",
    "rollback_performed",
    "compensation_authorized",
    "compensation_performed",
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


def build_execution_finalization_persistence_contract(
    *,
    execution_finalization_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define terminal persistence semantics; persist nothing."""
    row = (
        dict(execution_finalization_review)
        if isinstance(execution_finalization_review, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != finalization.SCHEMA:
        blockers.append("EXECUTION_FINALIZATION_SCHEMA_REQUIRED")
    if row.get("state") != finalization.READY:
        blockers.append("EXECUTION_FINALIZATION_DESIGN_REVIEW_REQUIRED")
    if row.get("execution_finalization_design_only") is not True:
        blockers.append("EXECUTION_FINALIZATION_NOT_DESIGN_ONLY")
    if row.get("fail_closed") is not True:
        blockers.append("FAIL_CLOSED_FINALIZATION_REQUIRED")
    if row.get("terminal_evidence_required") is not True:
        blockers.append("TERMINAL_EVIDENCE_REQUIRED")
    if row.get("unknown_outcome_finalization_forbidden") is not True:
        blockers.append("UNKNOWN_FINALIZATION_MUST_BE_FORBIDDEN")
    if row.get("still_unknown_outcome_finalization_forbidden") is not True:
        blockers.append("STILL_UNKNOWN_FINALIZATION_MUST_BE_FORBIDDEN")
    if row.get("append_only_finalization_record_required") is not True:
        blockers.append("APPEND_ONLY_FINALIZATION_RECORD_REQUIRED")
    if row.get("finalization_creates_execution_authority") is not False:
        blockers.append("FINALIZATION_MUST_NOT_CREATE_EXECUTION_AUTHORITY")
    if row.get("retry_allowed_by_finalization") is not False:
        blockers.append("FINALIZATION_MUST_NOT_ALLOW_RETRY")
    if row.get("reconciliation_allowed_by_finalization") is not False:
        blockers.append("FINALIZATION_MUST_NOT_ALLOW_RECONCILIATION")
    if row.get("rollback_allowed_by_finalization") is not False:
        blockers.append("FINALIZATION_MUST_NOT_ALLOW_ROLLBACK")
    if row.get("compensation_allowed_by_finalization") is not False:
        blockers.append("FINALIZATION_MUST_NOT_ALLOW_COMPENSATION")
    if row.get("finops_cap_cents") != FINOPS_CAP_CENTS_REQUIRED:
        blockers.append("FINOPS_CAP_MUST_REMAIN_20000_CENTS")
    if row.get("next_allowed_step") != finalization.NEXT_ALLOWED_STEP:
        blockers.append("EXECUTION_FINALIZATION_NEXT_STEP_INVALID")

    for key in finalization.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("EXECUTION_FINALIZATION_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            execution_finalization_persistence_design_only=True,
            persistence_mode=PERSISTENCE_MODE,
            fail_closed=True,
            reuses_existing_core_durable_store=True,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        execution_finalization_persistence_design_only=True,
        persistence_mode=PERSISTENCE_MODE,
        fail_closed=True,
        reuses_existing_core_durable_store=True,
        canonical_execution_identity_required=True,
        compare_and_set_required=True,
        exactly_once_terminal_commit_required=True,
        append_only_terminal_record_required=True,
        immutable_terminal_record_required=True,
        terminal_record_delete_forbidden=True,
        execution_reopen_after_terminal_forbidden=True,
        terminal_state_crossgrade_forbidden=True,
        terminal_state_downgrade_forbidden=True,
        idempotent_same_digest_replay_required=True,
        different_digest_conflict_required=True,
        durable_reopen_consistency_required=True,
        crash_before_commit_cannot_infer_finalization=True,
        crash_after_commit_replays_terminal_record=True,
        persistence_creates_execution_authority=False,
        finops_cap_cents=FINOPS_CAP_CENTS_REQUIRED,
        core_execution_store=CORE_EXECUTION_STORE,
        core_execution_id=CORE_EXECUTION_ID,
        terminal_states=TERMINAL_STATES,
        required_persistence_invariants=REQUIRED_PERSISTENCE_INVARIANTS,
        required_persistence_bindings=REQUIRED_PERSISTENCE_BINDINGS,
        required_reopen_assertions=REQUIRED_REOPEN_ASSERTIONS,
        persistence_conflicts=PERSISTENCE_CONFLICTS,
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
    "TERMINAL_STATES",
    "REQUIRED_PERSISTENCE_INVARIANTS",
    "REQUIRED_PERSISTENCE_BINDINGS",
    "REQUIRED_REOPEN_ASSERTIONS",
    "PERSISTENCE_CONFLICTS",
    "FORBIDDEN_PERSISTENCE_MATERIAL",
    "FALSE_FIELDS",
    "build_execution_finalization_persistence_contract",
]
