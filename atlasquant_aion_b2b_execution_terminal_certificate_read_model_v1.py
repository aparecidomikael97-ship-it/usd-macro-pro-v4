"""AION B2B execution terminal certificate read model V1.

Design-only, fail-closed, read-only and non-executable.

This layer defines the future projection used to inspect a terminal execution
certificate after its persistence contract has proved append-only, immutable,
exactly-once storage semantics.

The read model is observational evidence only. It cannot issue a certificate,
sign anything, mutate the terminal record, reopen execution, authorize retry,
trigger external effects, bill, write CRM, provision, deploy or mutate
production.

This module reads no database, computes no live verification, opens no network,
loads no keys and performs no side effect.

Maximum positive state:
READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_READ_MODEL_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_execution_terminal_certificate_persistence_contract_v1 as persistence

SCHEMA = "ATLASQUANT_AION_B2B_EXECUTION_TERMINAL_CERTIFICATE_READ_MODEL_V1"
READY = "READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_READ_MODEL_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_EXECUTION_TERMINAL_CERTIFICATE_READ_MODEL_UI_ONLY"

READ_MODEL_MODE = "READ_ONLY_TERMINAL_CERTIFICATE_PROJECTION"
DIGEST_ALGORITHM = "SHA256"
CANONICAL_ENCODING = "UTF8_CANONICAL_JSON"
FINOPS_CAP_CENTS_REQUIRED = 20000

READ_MODEL_STATES = (
    "VERIFIED",
    "MISMATCH",
    "UNAVAILABLE",
    "STALE",
)

REQUIRED_READ_MODEL_FIELDS = (
    "schema_version",
    "tenant_id",
    "workspace_id",
    "execution_id",
    "final_execution_state",
    "terminal_revision",
    "certificate_status",
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
    "observed_at",
)

REQUIRED_READ_MODEL_INVARIANTS = (
    "PERSISTED_TERMINAL_CERTIFICATE_REQUIRED",
    "TENANT_SCOPE_REQUIRED",
    "WORKSPACE_SCOPE_REQUIRED",
    "CANONICAL_EXECUTION_ID_REQUIRED",
    "TERMINAL_EXECUTION_REQUIRED",
    "CERTIFICATE_RECORD_IMMUTABLE",
    "CERTIFICATE_RECORD_APPEND_ONLY",
    "DURABLE_REOPEN_CONSISTENCY_REQUIRED",
    "CERTIFICATE_DIGEST_MATCH_REQUIRED_FOR_VERIFIED",
    "FINALIZATION_DIGEST_MATCH_REQUIRED_FOR_VERIFIED",
    "AUDIT_SEAL_DIGEST_MATCH_REQUIRED_FOR_VERIFIED",
    "TERMINAL_REVISION_MATCH_REQUIRED_FOR_VERIFIED",
    "ANY_MISMATCH_MUST_NOT_RENDER_VERIFIED",
    "MISSING_EVIDENCE_MUST_NOT_RENDER_VERIFIED",
    "STALE_EVIDENCE_MUST_NOT_RENDER_VERIFIED",
    "READ_MODEL_IS_OBSERVATIONAL_ONLY",
    "READ_MODEL_CANNOT_ISSUE_CERTIFICATE",
    "READ_MODEL_CANNOT_SIGN_CERTIFICATE",
    "READ_MODEL_CANNOT_REOPEN_EXECUTION",
    "READ_MODEL_CANNOT_AUTHORIZE_RETRY",
    "READ_MODEL_CANNOT_AUTHORIZE_EXTERNAL_EFFECT",
    "READ_MODEL_CANNOT_CREATE_EXECUTION_AUTHORITY",
)

REQUIRED_VERIFICATION_DISPLAY_RULES = (
    "VERIFIED_REQUIRES_ALL_BOUND_DIGESTS_MATCH",
    "MISMATCH_SHOWS_FAIL_CLOSED_STATUS",
    "UNAVAILABLE_SHOWS_EVIDENCE_MISSING_STATUS",
    "STALE_SHOWS_REFRESH_REQUIRED_STATUS",
    "NO_STATUS_GRANTS_EXECUTION_AUTHORITY",
    "NO_STATUS_GRANTS_RETRY_AUTHORITY",
    "NO_STATUS_GRANTS_REOPEN_AUTHORITY",
    "NO_STATUS_GRANTS_EXTERNAL_EFFECT_AUTHORITY",
)

FORBIDDEN_READ_MODEL_MATERIAL = (
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
    "raw_customer_message_body",
    "shell_command_value",
)

FALSE_FIELDS = (
    "read_model_verified",
    "certificate_verified",
    "certificate_generated",
    "certificate_signed",
    "certificate_issued",
    "certificate_persisted",
    "store_opened",
    "database_opened",
    "certificate_record_loaded",
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


def build_execution_terminal_certificate_read_model_contract(
    *,
    terminal_certificate_persistence_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define a future read-only certificate projection; read nothing."""
    row = (
        dict(terminal_certificate_persistence_review)
        if isinstance(terminal_certificate_persistence_review, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != persistence.SCHEMA:
        blockers.append("TERMINAL_CERTIFICATE_PERSISTENCE_SCHEMA_REQUIRED")
    if row.get("state") != persistence.READY:
        blockers.append("TERMINAL_CERTIFICATE_PERSISTENCE_DESIGN_REVIEW_REQUIRED")
    if row.get("execution_terminal_certificate_persistence_design_only") is not True:
        blockers.append("TERMINAL_CERTIFICATE_PERSISTENCE_NOT_DESIGN_ONLY")
    if row.get("fail_closed") is not True:
        blockers.append("FAIL_CLOSED_CERTIFICATE_PERSISTENCE_REQUIRED")
    if row.get("compare_and_set_required") is not True:
        blockers.append("COMPARE_AND_SET_CERTIFICATE_PERSISTENCE_REQUIRED")
    if row.get("exactly_once_certificate_commit_required") is not True:
        blockers.append("EXACTLY_ONCE_CERTIFICATE_COMMIT_REQUIRED")
    if row.get("append_only_certificate_record_required") is not True:
        blockers.append("APPEND_ONLY_CERTIFICATE_RECORD_REQUIRED")
    if row.get("immutable_certificate_record_required") is not True:
        blockers.append("IMMUTABLE_CERTIFICATE_RECORD_REQUIRED")
    if row.get("durable_reopen_consistency_required") is not True:
        blockers.append("DURABLE_REOPEN_CONSISTENCY_REQUIRED")
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

    persistence_invariants = set(
        row.get("required_certificate_persistence_invariants") or ()
    )
    for marker in (
        "TERMINAL_EXECUTION_REQUIRED",
        "CERTIFICATE_RECORD_APPEND_ONLY",
        "CERTIFICATE_RECORD_IMMUTABLE",
        "DURABLE_REOPEN_MUST_PRESERVE_CERTIFICATE_RECORD",
        "CERTIFICATE_PERSISTENCE_DOES_NOT_CREATE_EXECUTION_AUTHORITY",
    ):
        if marker not in persistence_invariants:
            blockers.append("CERTIFICATE_PERSISTENCE_INVARIANT_REQUIRED:" + marker)

    reopen_assertions = set(row.get("required_certificate_reopen_assertions") or ())
    for marker in (
        "CERTIFICATE_RECORD_EXISTS_AFTER_REOPEN",
        "EXECUTION_ID_MATCH",
        "TERMINAL_REVISION_MATCH",
        "CERTIFICATE_MANIFEST_DIGEST_MATCH",
        "CERTIFICATE_DIGEST_MATCH",
        "NO_DUPLICATE_CERTIFICATE_RECORD",
        "NO_CERTIFICATE_REVISION_REGRESSION",
    ):
        if marker not in reopen_assertions:
            blockers.append("CERTIFICATE_REOPEN_ASSERTION_REQUIRED:" + marker)

    if row.get("next_allowed_step") != persistence.NEXT_ALLOWED_STEP:
        blockers.append("TERMINAL_CERTIFICATE_PERSISTENCE_NEXT_STEP_INVALID")

    for key in persistence.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("TERMINAL_CERTIFICATE_PERSISTENCE_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            execution_terminal_certificate_read_model_design_only=True,
            read_model_mode=READ_MODEL_MODE,
            fail_closed=True,
            read_only=True,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        execution_terminal_certificate_read_model_design_only=True,
        read_model_mode=READ_MODEL_MODE,
        fail_closed=True,
        read_only=True,
        observational_only=True,
        persisted_certificate_required=True,
        tenant_scope_required=True,
        workspace_scope_required=True,
        verification_status_fail_closed=True,
        verified_requires_all_bound_digests_match=True,
        unavailable_never_implies_verified=True,
        stale_never_implies_verified=True,
        mismatch_never_implies_verified=True,
        read_model_creates_execution_authority=False,
        read_model_authorizes_retry=False,
        read_model_authorizes_reopen=False,
        read_model_authorizes_external_effect=False,
        digest_algorithm=DIGEST_ALGORITHM,
        canonical_encoding=CANONICAL_ENCODING,
        finops_cap_cents=FINOPS_CAP_CENTS_REQUIRED,
        read_model_states=READ_MODEL_STATES,
        required_read_model_fields=REQUIRED_READ_MODEL_FIELDS,
        required_read_model_invariants=REQUIRED_READ_MODEL_INVARIANTS,
        required_verification_display_rules=REQUIRED_VERIFICATION_DISPLAY_RULES,
        forbidden_read_model_material=FORBIDDEN_READ_MODEL_MATERIAL,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "READ_MODEL_MODE",
    "DIGEST_ALGORITHM",
    "CANONICAL_ENCODING",
    "FINOPS_CAP_CENTS_REQUIRED",
    "READ_MODEL_STATES",
    "REQUIRED_READ_MODEL_FIELDS",
    "REQUIRED_READ_MODEL_INVARIANTS",
    "REQUIRED_VERIFICATION_DISPLAY_RULES",
    "FORBIDDEN_READ_MODEL_MATERIAL",
    "FALSE_FIELDS",
    "build_execution_terminal_certificate_read_model_contract",
]
