"""AION B2B execution terminal certificate persistence contract V1.

Design-only, fail-closed and non-executable.

This layer defines how a future AION runtime must durably persist a terminal
certificate descriptor after the execution terminal certificate contract has
proved the terminal chain eligible for certificate issuance.

The future persistence operation must be append-only, exactly-once by canonical
terminal execution identity and guarded by compare-and-set semantics. A stored
certificate may never be rewritten, deleted to reopen execution, replaced by a
different digest, or used to grant execution authority.

This module does NOT instantiate a store, open SQLite, perform CAS, generate or
sign a certificate, load keys, write a record, query providers, open network
transport, retry, reconcile, rollback, compensate, bill, contact customers,
write CRM, provision, deploy or mutate production.

Maximum positive state:
READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_PERSISTENCE_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_execution_terminal_certificate_contract_v1 as certificate

SCHEMA = "ATLASQUANT_AION_B2B_EXECUTION_TERMINAL_CERTIFICATE_PERSISTENCE_CONTRACT_V1"
READY = "READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_PERSISTENCE_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_EXECUTION_TERMINAL_CERTIFICATE_READ_MODEL_ONLY"

PERSISTENCE_MODE = "APPEND_ONLY_CAS_TERMINAL_CERTIFICATE_COMMIT"
DIGEST_ALGORITHM = "SHA256"
CANONICAL_ENCODING = "UTF8_CANONICAL_JSON"
FINOPS_CAP_CENTS_REQUIRED = 20000

CORE_EXECUTION_STORE = "atlasquant_aion_durable_execution_kernel.DurableExecutionStore"
CORE_EXECUTION_ID = "atlasquant_aion_durable_execution_kernel.canonical_execution_id"

REQUIRED_CERTIFICATE_PERSISTENCE_INVARIANTS = (
    "CANONICAL_EXECUTION_ID_REQUIRED",
    "TERMINAL_EXECUTION_REQUIRED",
    "TERMINAL_REVISION_REQUIRED",
    "PERSISTED_FINALIZATION_RECORD_REQUIRED",
    "PERSISTED_AUDIT_SEAL_REQUIRED",
    "VALID_TERMINAL_CERTIFICATE_CONTRACT_REQUIRED",
    "CERTIFICATE_MANIFEST_DIGEST_REQUIRED",
    "CERTIFICATE_DIGEST_REQUIRED",
    "EXPECTED_PRE_CERTIFICATE_REVISION_REQUIRED",
    "COMPARE_AND_SET_REQUIRED",
    "SINGLE_CERTIFICATE_WINNER_REQUIRED",
    "CERTIFICATE_DIGEST_UNIQUENESS_REQUIRED",
    "CERTIFICATE_RECORD_APPEND_ONLY",
    "CERTIFICATE_RECORD_IMMUTABLE",
    "CERTIFICATE_RECORD_DELETE_FORBIDDEN",
    "CERTIFICATE_RECORD_REPLACE_FORBIDDEN",
    "TERMINAL_EXECUTION_REOPEN_FORBIDDEN",
    "SAME_CERTIFICATE_SAME_DIGEST_IS_IDEMPOTENT_REPLAY",
    "SAME_TERMINAL_IDENTITY_DIFFERENT_CERTIFICATE_DIGEST_IS_CONFLICT",
    "DURABLE_REOPEN_MUST_PRESERVE_CERTIFICATE_RECORD",
    "CRASH_AFTER_CERTIFICATE_COMMIT_MUST_REPLAY_CERTIFICATE_RECORD",
    "CRASH_BEFORE_CERTIFICATE_COMMIT_MUST_NOT_INFER_PERSISTED_CERTIFICATE",
    "CERTIFICATE_PERSISTENCE_DOES_NOT_CREATE_EXECUTION_AUTHORITY",
)

REQUIRED_CERTIFICATE_PERSISTENCE_BINDINGS = (
    "execution_id",
    "terminal_revision",
    "expected_pre_certificate_revision",
    "final_execution_state",
    "finalization_record_digest",
    "execution_finalization_persistence_record_digest",
    "audit_seal_manifest_digest",
    "audit_seal_persistence_record_digest",
    "execution_terminal_certificate_contract_digest",
    "certificate_manifest_digest",
    "certificate_digest",
    "digest_algorithm",
    "canonical_encoding",
    "idempotency_key_digest",
    "effect_key_digest",
    "provider_request_correlation_digest",
    "terminal_evidence_set_digest",
    "rollback_or_compensation_settlement_digest",
    "finops_estimate_digest",
    "finops_observation_digest",
    "observability_trace_id",
    "pre_terminal_audit_chain_digest",
)

REQUIRED_CERTIFICATE_REOPEN_ASSERTIONS = (
    "CERTIFICATE_RECORD_EXISTS_AFTER_REOPEN",
    "EXECUTION_ID_MATCH",
    "TERMINAL_REVISION_MATCH",
    "FINAL_EXECUTION_STATE_MATCH",
    "FINALIZATION_RECORD_DIGEST_MATCH",
    "AUDIT_SEAL_MANIFEST_DIGEST_MATCH",
    "AUDIT_SEAL_PERSISTENCE_RECORD_DIGEST_MATCH",
    "CERTIFICATE_MANIFEST_DIGEST_MATCH",
    "CERTIFICATE_DIGEST_MATCH",
    "DIGEST_ALGORITHM_MATCH",
    "CANONICAL_ENCODING_MATCH",
    "NO_DUPLICATE_CERTIFICATE_RECORD",
    "NO_CERTIFICATE_REVISION_REGRESSION",
)

CERTIFICATE_PERSISTENCE_CONFLICTS = (
    "TERMINAL_EXECUTION_RECORD_MISSING",
    "FINALIZATION_RECORD_MISSING",
    "AUDIT_SEAL_RECORD_MISSING",
    "TERMINAL_CERTIFICATE_CONTRACT_INVALID",
    "PRE_CERTIFICATE_REVISION_MISMATCH",
    "CERTIFICATE_MANIFEST_DIGEST_MISSING",
    "CERTIFICATE_DIGEST_MISSING",
    "EXECUTION_ALREADY_CERTIFIED_WITH_DIFFERENT_DIGEST",
    "TERMINAL_REVISION_ALREADY_CERTIFIED_WITH_DIFFERENT_DIGEST",
    "FINALIZATION_RECORD_DIGEST_CONFLICT",
    "AUDIT_SEAL_DIGEST_CONFLICT",
    "CERTIFICATE_MANIFEST_DIGEST_CONFLICT",
    "DIGEST_ALGORITHM_CONFLICT",
    "CANONICAL_ENCODING_CONFLICT",
    "TERMINAL_EVIDENCE_DIGEST_CONFLICT",
    "FINOPS_OBSERVATION_CONFLICT",
    "AUDIT_CHAIN_DIGEST_CONFLICT",
    "REOPEN_CERTIFICATE_RECORD_MISMATCH",
)

FORBIDDEN_PERSISTENCE_MATERIAL = (
    "sqlite_path_value",
    "database_connection_value",
    "database_cursor_value",
    "private_signing_key_value",
    "signing_key_value",
    "credential_value",
    "secret_value",
    "password_value",
    "api_key_value",
    "access_token_value",
    "private_key_value",
    "authorization_header_value",
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
    "certificate_verified",
    "certificate_generated",
    "certificate_signed",
    "certificate_record_written",
    "certificate_persisted",
    "certificate_issued",
    "certificate_reopened",
    "certificate_deleted",
    "certificate_replaced",
    "private_key_loaded",
    "signing_key_loaded",
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


def build_execution_terminal_certificate_persistence_contract(
    *,
    terminal_certificate_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define durable terminal-certificate persistence semantics; persist nothing."""
    row = (
        dict(terminal_certificate_review)
        if isinstance(terminal_certificate_review, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != certificate.SCHEMA:
        blockers.append("TERMINAL_CERTIFICATE_SCHEMA_REQUIRED")
    if row.get("state") != certificate.READY:
        blockers.append("TERMINAL_CERTIFICATE_DESIGN_REVIEW_REQUIRED")
    if row.get("execution_terminal_certificate_design_only") is not True:
        blockers.append("TERMINAL_CERTIFICATE_NOT_DESIGN_ONLY")
    if row.get("fail_closed") is not True:
        blockers.append("FAIL_CLOSED_TERMINAL_CERTIFICATE_REQUIRED")
    if row.get("verification_only") is not True:
        blockers.append("VERIFICATION_ONLY_CERTIFICATE_REQUIRED")
    if row.get("deterministic_certificate_manifest_required") is not True:
        blockers.append("DETERMINISTIC_CERTIFICATE_MANIFEST_REQUIRED")
    if row.get("certificate_read_only") is not True:
        blockers.append("READ_ONLY_CERTIFICATE_REQUIRED")
    if row.get("certificate_is_real_signature") is not False:
        blockers.append("CERTIFICATE_MUST_NOT_BE_REAL_SIGNATURE")
    if row.get("certificate_creates_execution_authority") is not False:
        blockers.append("CERTIFICATE_MUST_NOT_CREATE_EXECUTION_AUTHORITY")
    if row.get("certificate_authorizes_retry") is not False:
        blockers.append("CERTIFICATE_MUST_NOT_AUTHORIZE_RETRY")
    if row.get("certificate_authorizes_reopen") is not False:
        blockers.append("CERTIFICATE_MUST_NOT_AUTHORIZE_REOPEN")
    if row.get("certificate_authorizes_external_effect") is not False:
        blockers.append("CERTIFICATE_MUST_NOT_AUTHORIZE_EXTERNAL_EFFECT")
    if row.get("persisted_audit_seal_required") is not True:
        blockers.append("PERSISTED_AUDIT_SEAL_REQUIRED")
    if row.get("audit_seal_reopen_consistency_required") is not True:
        blockers.append("AUDIT_SEAL_REOPEN_CONSISTENCY_REQUIRED")
    if row.get("digest_algorithm") != DIGEST_ALGORITHM:
        blockers.append("SHA256_DIGEST_REQUIRED")
    if row.get("canonical_encoding") != CANONICAL_ENCODING:
        blockers.append("UTF8_CANONICAL_JSON_REQUIRED")
    if row.get("finops_cap_cents") != FINOPS_CAP_CENTS_REQUIRED:
        blockers.append("FINOPS_CAP_MUST_REMAIN_20000_CENTS")

    invariants = set(row.get("required_certificate_invariants") or ())
    for marker in (
        "TERMINAL_EXECUTION_REQUIRED",
        "PERSISTED_FINALIZATION_RECORD_REQUIRED",
        "PERSISTED_AUDIT_SEAL_REQUIRED",
        "DURABLE_AUDIT_SEAL_REOPEN_CONSISTENCY_REQUIRED",
        "CERTIFICATE_DOES_NOT_CREATE_EXECUTION_AUTHORITY",
        "CERTIFICATE_DOES_NOT_AUTHORIZE_RETRY",
        "CERTIFICATE_DOES_NOT_AUTHORIZE_REOPEN",
        "CERTIFICATE_DOES_NOT_AUTHORIZE_EXTERNAL_EFFECT",
    ):
        if marker not in invariants:
            blockers.append("TERMINAL_CERTIFICATE_INVARIANT_REQUIRED:" + marker)

    verification_rules = set(row.get("required_verification_rules") or ())
    for marker in (
        "RECOMPUTE_CERTIFICATE_MANIFEST_DIGEST",
        "VERIFY_CERTIFICATE_DIGEST_MATCH",
        "VERIFY_EXECUTION_ID_MATCH",
        "VERIFY_FINAL_EXECUTION_STATE_MATCH",
        "VERIFY_TERMINAL_REVISION_MATCH",
        "ANY_MISMATCH_FAILS_CLOSED",
    ):
        if marker not in verification_rules:
            blockers.append("CERTIFICATE_VERIFICATION_RULE_REQUIRED:" + marker)

    if row.get("next_allowed_step") != certificate.NEXT_ALLOWED_STEP:
        blockers.append("TERMINAL_CERTIFICATE_NEXT_STEP_INVALID")

    for key in certificate.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("TERMINAL_CERTIFICATE_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            execution_terminal_certificate_persistence_design_only=True,
            persistence_mode=PERSISTENCE_MODE,
            fail_closed=True,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        execution_terminal_certificate_persistence_design_only=True,
        persistence_mode=PERSISTENCE_MODE,
        fail_closed=True,
        reuses_existing_core_durable_store=True,
        canonical_execution_identity_required=True,
        compare_and_set_required=True,
        exactly_once_certificate_commit_required=True,
        append_only_certificate_record_required=True,
        immutable_certificate_record_required=True,
        certificate_delete_forbidden=True,
        certificate_replace_forbidden=True,
        terminal_execution_reopen_forbidden=True,
        idempotent_same_digest_replay_required=True,
        different_digest_conflict_required=True,
        durable_reopen_consistency_required=True,
        crash_before_commit_cannot_infer_persisted_certificate=True,
        crash_after_commit_replays_certificate_record=True,
        persistence_creates_execution_authority=False,
        digest_algorithm=DIGEST_ALGORITHM,
        canonical_encoding=CANONICAL_ENCODING,
        finops_cap_cents=FINOPS_CAP_CENTS_REQUIRED,
        core_execution_store=CORE_EXECUTION_STORE,
        core_execution_id=CORE_EXECUTION_ID,
        required_certificate_persistence_invariants=REQUIRED_CERTIFICATE_PERSISTENCE_INVARIANTS,
        required_certificate_persistence_bindings=REQUIRED_CERTIFICATE_PERSISTENCE_BINDINGS,
        required_certificate_reopen_assertions=REQUIRED_CERTIFICATE_REOPEN_ASSERTIONS,
        certificate_persistence_conflicts=CERTIFICATE_PERSISTENCE_CONFLICTS,
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
    "DIGEST_ALGORITHM",
    "CANONICAL_ENCODING",
    "FINOPS_CAP_CENTS_REQUIRED",
    "CORE_EXECUTION_STORE",
    "CORE_EXECUTION_ID",
    "REQUIRED_CERTIFICATE_PERSISTENCE_INVARIANTS",
    "REQUIRED_CERTIFICATE_PERSISTENCE_BINDINGS",
    "REQUIRED_CERTIFICATE_REOPEN_ASSERTIONS",
    "CERTIFICATE_PERSISTENCE_CONFLICTS",
    "FORBIDDEN_PERSISTENCE_MATERIAL",
    "FALSE_FIELDS",
    "build_execution_terminal_certificate_persistence_contract",
]
