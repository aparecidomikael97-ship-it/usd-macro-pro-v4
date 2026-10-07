"""AION B2B execution terminal certificate contract V1.

Design-only, fail-closed and non-executable.

This layer defines a deterministic, verification-only certificate descriptor
for a B2B execution whose terminal finalization and audit seal have already
been durably committed.

The certificate is evidence of terminal chain integrity only. It is not an
execution authorization, retry token, reopen token, provider acknowledgement,
legal signature or cryptographic signature.

This module does NOT read a database, generate a live certificate, load signing
keys, sign, persist, query providers, open network transport, retry, reconcile,
rollback, compensate, bill, contact customers, write CRM, provision, deploy or
mutate production.

Maximum positive state:
READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_execution_audit_seal_persistence_contract_v1 as seal_persistence

SCHEMA = "ATLASQUANT_AION_B2B_EXECUTION_TERMINAL_CERTIFICATE_CONTRACT_V1"
READY = "READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_EXECUTION_TERMINAL_CERTIFICATE_PERSISTENCE_CONTRACT_ONLY"

CERTIFICATE_MODE = "VERIFICATION_ONLY_TERMINAL_CHAIN_CERTIFICATE"
DIGEST_ALGORITHM = "SHA256"
CANONICAL_ENCODING = "UTF8_CANONICAL_JSON"
FINOPS_CAP_CENTS_REQUIRED = 20000

REQUIRED_CERTIFICATE_BINDINGS = (
    "schema_version",
    "execution_id",
    "final_execution_state",
    "terminal_revision",
    "finalization_record_digest",
    "execution_finalization_persistence_record_digest",
    "audit_seal_manifest_digest",
    "audit_seal_persistence_record_digest",
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
    "certificate_manifest_digest",
)

REQUIRED_CERTIFICATE_INVARIANTS = (
    "TERMINAL_EXECUTION_REQUIRED",
    "PERSISTED_FINALIZATION_RECORD_REQUIRED",
    "PERSISTED_AUDIT_SEAL_REQUIRED",
    "DURABLE_AUDIT_SEAL_REOPEN_CONSISTENCY_REQUIRED",
    "PERSISTED_AUDIT_SEAL_DIGEST_MATCH_REQUIRED",
    "CANONICAL_CERTIFICATE_MANIFEST_REQUIRED",
    "DETERMINISTIC_CERTIFICATE_DIGEST_REQUIRED",
    "SHA256_DIGEST_REQUIRED",
    "CANONICAL_ENCODING_REQUIRED",
    "SAME_CERTIFICATE_MANIFEST_SAME_DIGEST",
    "ANY_BOUND_FIELD_CHANGE_CHANGES_CERTIFICATE_DIGEST",
    "NO_OUTCOME_UNKNOWN",
    "NO_STILL_OUTCOME_UNKNOWN",
    "NO_PENDING_RECONCILIATION",
    "NO_PENDING_ROLLBACK",
    "NO_PENDING_COMPENSATION",
    "NO_TERMINAL_REVISION_REGRESSION",
    "CERTIFICATE_IS_READ_ONLY",
    "CERTIFICATE_DOES_NOT_CREATE_EXECUTION_AUTHORITY",
    "CERTIFICATE_DOES_NOT_AUTHORIZE_RETRY",
    "CERTIFICATE_DOES_NOT_AUTHORIZE_REOPEN",
    "CERTIFICATE_DOES_NOT_AUTHORIZE_EXTERNAL_EFFECT",
    "CERTIFICATE_IS_NOT_A_REAL_SIGNATURE",
)

REQUIRED_VERIFICATION_RULES = (
    "RECOMPUTE_CERTIFICATE_MANIFEST_DIGEST",
    "VERIFY_CERTIFICATE_DIGEST_MATCH",
    "VERIFY_EXECUTION_ID_MATCH",
    "VERIFY_FINAL_EXECUTION_STATE_MATCH",
    "VERIFY_TERMINAL_REVISION_MATCH",
    "VERIFY_FINALIZATION_RECORD_DIGEST_MATCH",
    "VERIFY_AUDIT_SEAL_MANIFEST_DIGEST_MATCH",
    "VERIFY_AUDIT_SEAL_PERSISTENCE_RECORD_DIGEST_MATCH",
    "VERIFY_IDEMPOTENCY_KEY_DIGEST_MATCH",
    "VERIFY_EFFECT_KEY_DIGEST_MATCH",
    "VERIFY_PROVIDER_CORRELATION_MATCH",
    "VERIFY_TERMINAL_EVIDENCE_DIGEST_MATCH",
    "VERIFY_ROLLBACK_COMPENSATION_SETTLEMENT_WHEN_APPLICABLE",
    "VERIFY_FINOPS_DIGESTS_MATCH",
    "VERIFY_PRE_TERMINAL_AUDIT_CHAIN_DIGEST_MATCH",
    "ANY_MISMATCH_FAILS_CLOSED",
)

CERTIFICATE_INVALIDATORS = (
    "TERMINAL_EXECUTION_RECORD_MISSING",
    "FINALIZATION_RECORD_MISSING",
    "AUDIT_SEAL_RECORD_MISSING",
    "AUDIT_SEAL_REOPEN_RECORD_MISMATCH",
    "NON_TERMINAL_EXECUTION_STATE",
    "OUTCOME_UNKNOWN_PRESENT",
    "STILL_OUTCOME_UNKNOWN_PRESENT",
    "SCHEMA_VERSION_MISMATCH",
    "CANONICAL_ENCODING_MISMATCH",
    "DIGEST_ALGORITHM_MISMATCH",
    "EXECUTION_ID_MISMATCH",
    "TERMINAL_STATE_MISMATCH",
    "TERMINAL_REVISION_MISMATCH",
    "FINALIZATION_RECORD_DIGEST_MISMATCH",
    "AUDIT_SEAL_MANIFEST_DIGEST_MISMATCH",
    "AUDIT_SEAL_PERSISTENCE_RECORD_DIGEST_MISMATCH",
    "IDEMPOTENCY_KEY_DIGEST_MISMATCH",
    "EFFECT_KEY_DIGEST_MISMATCH",
    "PROVIDER_CORRELATION_MISMATCH",
    "TERMINAL_EVIDENCE_DIGEST_MISMATCH",
    "ROLLBACK_COMPENSATION_SETTLEMENT_DIGEST_MISMATCH",
    "FINOPS_DIGEST_MISMATCH",
    "AUDIT_CHAIN_DIGEST_MISMATCH",
    "CERTIFICATE_DIGEST_MISMATCH",
)

FORBIDDEN_CERTIFICATE_MATERIAL = (
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
    "certificate_verified",
    "certificate_generated",
    "certificate_signed",
    "certificate_persisted",
    "certificate_issued",
    "private_key_loaded",
    "signing_key_loaded",
    "store_opened",
    "database_opened",
    "seal_record_loaded",
    "seal_record_mutated",
    "terminal_record_mutated",
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


def build_execution_terminal_certificate_contract(
    *,
    audit_seal_persistence_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define terminal certificate semantics; issue nothing."""
    row = (
        dict(audit_seal_persistence_review)
        if isinstance(audit_seal_persistence_review, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != seal_persistence.SCHEMA:
        blockers.append("AUDIT_SEAL_PERSISTENCE_SCHEMA_REQUIRED")
    if row.get("state") != seal_persistence.READY:
        blockers.append("AUDIT_SEAL_PERSISTENCE_DESIGN_REVIEW_REQUIRED")
    if row.get("execution_audit_seal_persistence_design_only") is not True:
        blockers.append("AUDIT_SEAL_PERSISTENCE_NOT_DESIGN_ONLY")
    if row.get("fail_closed") is not True:
        blockers.append("FAIL_CLOSED_SEAL_PERSISTENCE_REQUIRED")
    if row.get("compare_and_set_required") is not True:
        blockers.append("COMPARE_AND_SET_REQUIREMENT_REQUIRED")
    if row.get("exactly_once_seal_commit_required") is not True:
        blockers.append("EXACTLY_ONCE_SEAL_COMMIT_REQUIRED")
    if row.get("append_only_seal_record_required") is not True:
        blockers.append("APPEND_ONLY_SEAL_RECORD_REQUIRED")
    if row.get("immutable_seal_record_required") is not True:
        blockers.append("IMMUTABLE_SEAL_RECORD_REQUIRED")
    if row.get("durable_reopen_consistency_required") is not True:
        blockers.append("DURABLE_REOPEN_CONSISTENCY_REQUIRED")
    if row.get("seal_replace_forbidden") is not True:
        blockers.append("SEAL_REPLACE_MUST_BE_FORBIDDEN")
    if row.get("terminal_execution_reopen_forbidden") is not True:
        blockers.append("TERMINAL_EXECUTION_REOPEN_MUST_BE_FORBIDDEN")
    if row.get("persistence_creates_execution_authority") is not False:
        blockers.append("PERSISTENCE_MUST_NOT_CREATE_EXECUTION_AUTHORITY")
    if row.get("digest_algorithm") != DIGEST_ALGORITHM:
        blockers.append("SHA256_DIGEST_REQUIRED")
    if row.get("canonical_encoding") != CANONICAL_ENCODING:
        blockers.append("UTF8_CANONICAL_JSON_REQUIRED")
    if row.get("finops_cap_cents") != FINOPS_CAP_CENTS_REQUIRED:
        blockers.append("FINOPS_CAP_MUST_REMAIN_20000_CENTS")

    persistence_invariants = set(row.get("required_seal_persistence_invariants") or ())
    for marker in (
        "DURABLE_REOPEN_MUST_PRESERVE_SEAL_RECORD",
        "SEAL_RECORD_IMMUTABLE",
        "TERMINAL_EXECUTION_REOPEN_FORBIDDEN",
        "SEAL_PERSISTENCE_DOES_NOT_CREATE_EXECUTION_AUTHORITY",
    ):
        if marker not in persistence_invariants:
            blockers.append("SEAL_PERSISTENCE_INVARIANT_REQUIRED:" + marker)

    reopen_assertions = set(row.get("required_seal_reopen_assertions") or ())
    for marker in (
        "SEAL_RECORD_EXISTS_AFTER_REOPEN",
        "AUDIT_SEAL_MANIFEST_DIGEST_MATCH",
        "AUDIT_SEAL_DIGEST_MATCH",
        "NO_DUPLICATE_SEAL_RECORD",
        "NO_SEAL_REVISION_REGRESSION",
    ):
        if marker not in reopen_assertions:
            blockers.append("SEAL_REOPEN_ASSERTION_REQUIRED:" + marker)
    if row.get("next_allowed_step") != seal_persistence.NEXT_ALLOWED_STEP:
        blockers.append("AUDIT_SEAL_PERSISTENCE_NEXT_STEP_INVALID")

    for key in seal_persistence.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("AUDIT_SEAL_PERSISTENCE_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            execution_terminal_certificate_design_only=True,
            certificate_mode=CERTIFICATE_MODE,
            fail_closed=True,
            verification_only=True,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        execution_terminal_certificate_design_only=True,
        certificate_mode=CERTIFICATE_MODE,
        fail_closed=True,
        verification_only=True,
        deterministic_certificate_manifest_required=True,
        canonical_encoding=CANONICAL_ENCODING,
        digest_algorithm=DIGEST_ALGORITHM,
        same_manifest_same_digest_required=True,
        any_bound_field_change_changes_digest_required=True,
        any_verification_mismatch_fails_closed=True,
        persisted_audit_seal_required=True,
        audit_seal_reopen_consistency_required=True,
        terminal_execution_required=True,
        certificate_read_only=True,
        certificate_is_real_signature=False,
        certificate_creates_execution_authority=False,
        certificate_authorizes_retry=False,
        certificate_authorizes_reopen=False,
        certificate_authorizes_external_effect=False,
        finops_cap_cents=FINOPS_CAP_CENTS_REQUIRED,
        required_certificate_bindings=REQUIRED_CERTIFICATE_BINDINGS,
        required_certificate_invariants=REQUIRED_CERTIFICATE_INVARIANTS,
        required_verification_rules=REQUIRED_VERIFICATION_RULES,
        certificate_invalidators=CERTIFICATE_INVALIDATORS,
        forbidden_certificate_material=FORBIDDEN_CERTIFICATE_MATERIAL,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "CERTIFICATE_MODE",
    "DIGEST_ALGORITHM",
    "CANONICAL_ENCODING",
    "FINOPS_CAP_CENTS_REQUIRED",
    "REQUIRED_CERTIFICATE_BINDINGS",
    "REQUIRED_CERTIFICATE_INVARIANTS",
    "REQUIRED_VERIFICATION_RULES",
    "CERTIFICATE_INVALIDATORS",
    "FORBIDDEN_CERTIFICATE_MATERIAL",
    "FALSE_FIELDS",
    "build_execution_terminal_certificate_contract",
]
