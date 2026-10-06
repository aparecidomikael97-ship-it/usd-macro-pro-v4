"""AION B2B execution audit seal contract V1.

Design-only, fail-closed and non-executable.

This layer defines the immutable audit-seal manifest for a future terminal B2B
execution after its finalization record has been durably committed.

The audit seal is a chain-of-custody proof descriptor. It binds the canonical
execution identity, terminal state, authorization lineage, dispatch/outcome
lineage, reconciliation lineage when applicable, rollback/compensation
settlement when applicable, FinOps observations and the terminal persistence
record into one deterministic manifest digest.

The seal does NOT grant authority, reopen an execution, retry, reconcile,
rollback, compensate, query providers, open network transport, sign with a real
key, persist a seal, bill, contact customers, write CRM, provision, deploy or
mutate production.

Maximum positive state:
READY_FOR_EXECUTION_AUDIT_SEAL_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_execution_finalization_persistence_contract_v1 as persistence

SCHEMA = "ATLASQUANT_AION_B2B_EXECUTION_AUDIT_SEAL_CONTRACT_V1"
READY = "READY_FOR_EXECUTION_AUDIT_SEAL_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_EXECUTION_AUDIT_SEAL_PERSISTENCE_CONTRACT_ONLY"

SEAL_MODE = "DETERMINISTIC_TERMINAL_CHAIN_OF_CUSTODY_MANIFEST"
DIGEST_ALGORITHM = "SHA256"
CANONICAL_ENCODING = "UTF8_CANONICAL_JSON"
FINOPS_CAP_CENTS_REQUIRED = 20000

REQUIRED_SEAL_BINDINGS = (
    "schema_version",
    "execution_id",
    "final_execution_state",
    "terminal_revision",
    "finalization_record_digest",
    "execution_finalization_contract_digest",
    "execution_finalization_persistence_contract_digest",
    "durable_dispatch_record_digest",
    "external_effect_call_boundary_digest",
    "external_effect_outcome_receipt_digest",
    "outcome_reconciliation_record_digest",
    "execution_envelope_digest",
    "pre_dispatch_attestation_digest",
    "fresh_owner_authorization_digest",
    "reconciliation_authorization_digest",
    "provider_adapter_attestation_digest",
    "provider_capability_binding_digest",
    "provider_identity_ref",
    "provider_adapter_digest",
    "idempotency_key_digest",
    "effect_key_digest",
    "provider_request_correlation_digest",
    "terminal_evidence_set_digest",
    "before_state_digest",
    "expected_postcondition_digest",
    "rollback_plan_digest",
    "rollback_or_compensation_settlement_digest",
    "finops_estimate_digest",
    "finops_observation_digest",
    "observability_trace_id",
    "pre_terminal_audit_chain_digest",
)

REQUIRED_SEAL_INVARIANTS = (
    "CANONICAL_EXECUTION_ID_REQUIRED",
    "TERMINAL_PERSISTENCE_RECORD_REQUIRED",
    "TERMINAL_STATE_REQUIRED",
    "TERMINAL_REVISION_REQUIRED",
    "FINALIZATION_RECORD_DIGEST_REQUIRED",
    "ALL_REQUIRED_BINDINGS_PRESENT",
    "CANONICAL_FIELD_ORDER_REQUIRED",
    "CANONICAL_ENCODING_REQUIRED",
    "DETERMINISTIC_DIGEST_REQUIRED",
    "SHA256_DIGEST_REQUIRED",
    "SAME_MANIFEST_SAME_DIGEST",
    "ANY_BOUND_FIELD_CHANGE_CHANGES_DIGEST",
    "CHAIN_OF_CUSTODY_COMPLETE",
    "NO_UNRESOLVED_OUTCOME_UNKNOWN",
    "NO_PENDING_RECONCILIATION",
    "NO_PENDING_ROLLBACK",
    "NO_PENDING_COMPENSATION",
    "FINOPS_OBSERVATION_BOUND",
    "AUDIT_CHAIN_BOUND",
    "SEAL_IS_IMMUTABLE",
    "SEAL_IS_APPEND_ONLY",
    "SEAL_DOES_NOT_CREATE_EXECUTION_AUTHORITY",
    "SEAL_DOES_NOT_AUTHORIZE_RETRY",
    "SEAL_DOES_NOT_AUTHORIZE_REOPEN",
    "SEAL_DOES_NOT_AUTHORIZE_EXTERNAL_EFFECT",
)

REQUIRED_VERIFICATION_RULES = (
    "RECOMPUTE_CANONICAL_MANIFEST_DIGEST",
    "COMPARE_EXPECTED_AND_RECOMPUTED_SEAL_DIGEST",
    "VERIFY_TERMINAL_RECORD_DIGEST_MATCH",
    "VERIFY_EXECUTION_ID_MATCH",
    "VERIFY_TERMINAL_STATE_MATCH",
    "VERIFY_TERMINAL_REVISION_MATCH",
    "VERIFY_IDEMPOTENCY_KEY_DIGEST_MATCH",
    "VERIFY_EFFECT_KEY_DIGEST_MATCH",
    "VERIFY_PROVIDER_CORRELATION_MATCH",
    "VERIFY_OUTCOME_CHAIN_DIGESTS_MATCH",
    "VERIFY_RECONCILIATION_CHAIN_WHEN_APPLICABLE",
    "VERIFY_ROLLBACK_COMPENSATION_SETTLEMENT_WHEN_APPLICABLE",
    "VERIFY_FINOPS_DIGESTS_MATCH",
    "VERIFY_PRE_TERMINAL_AUDIT_CHAIN_DIGEST_MATCH",
    "ANY_MISMATCH_FAILS_CLOSED",
)

SEAL_INVALIDATORS = (
    "MISSING_TERMINAL_PERSISTENCE_RECORD",
    "NON_TERMINAL_EXECUTION_STATE",
    "OUTCOME_UNKNOWN_PRESENT",
    "STILL_OUTCOME_UNKNOWN_PRESENT",
    "MISSING_REQUIRED_BINDING",
    "SCHEMA_VERSION_MISMATCH",
    "CANONICAL_ENCODING_MISMATCH",
    "DIGEST_ALGORITHM_MISMATCH",
    "FINALIZATION_RECORD_DIGEST_MISMATCH",
    "EXECUTION_ID_MISMATCH",
    "TERMINAL_STATE_MISMATCH",
    "TERMINAL_REVISION_MISMATCH",
    "IDEMPOTENCY_KEY_DIGEST_MISMATCH",
    "EFFECT_KEY_DIGEST_MISMATCH",
    "PROVIDER_CORRELATION_MISMATCH",
    "OUTCOME_CHAIN_DIGEST_MISMATCH",
    "RECONCILIATION_CHAIN_DIGEST_MISMATCH",
    "ROLLBACK_COMPENSATION_SETTLEMENT_DIGEST_MISMATCH",
    "FINOPS_DIGEST_MISMATCH",
    "AUDIT_CHAIN_DIGEST_MISMATCH",
    "SEAL_DIGEST_MISMATCH",
)

FORBIDDEN_SEAL_MATERIAL = (
    "private_signing_key_value",
    "secret_value",
    "credential_value",
    "password_value",
    "api_key_value",
    "access_token_value",
    "refresh_token_value",
    "private_key_value",
    "authorization_header_value",
    "cookie_value",
    "payload_body_value",
    "raw_provider_response_body",
    "shell_command_value",
)

FALSE_FIELDS = (
    "seal_verified",
    "seal_generated",
    "seal_signed",
    "seal_persisted",
    "seal_replayed",
    "private_key_loaded",
    "signing_key_loaded",
    "store_opened",
    "database_opened",
    "terminal_record_loaded",
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


def build_execution_audit_seal_contract(
    *,
    finalization_persistence_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define deterministic terminal audit-seal semantics; seal nothing."""
    row = (
        dict(finalization_persistence_review)
        if isinstance(finalization_persistence_review, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != persistence.SCHEMA:
        blockers.append("FINALIZATION_PERSISTENCE_SCHEMA_REQUIRED")
    if row.get("state") != persistence.READY:
        blockers.append("FINALIZATION_PERSISTENCE_DESIGN_REVIEW_REQUIRED")
    if row.get("execution_finalization_persistence_design_only") is not True:
        blockers.append("FINALIZATION_PERSISTENCE_NOT_DESIGN_ONLY")
    if row.get("fail_closed") is not True:
        blockers.append("FAIL_CLOSED_PERSISTENCE_REQUIRED")
    if row.get("canonical_execution_identity_required") is not True:
        blockers.append("CANONICAL_EXECUTION_ID_REQUIRED")
    if row.get("compare_and_set_required") is not True:
        blockers.append("COMPARE_AND_SET_REQUIREMENT_REQUIRED")
    if row.get("exactly_once_terminal_commit_required") is not True:
        blockers.append("EXACTLY_ONCE_TERMINAL_COMMIT_REQUIRED")
    if row.get("append_only_terminal_record_required") is not True:
        blockers.append("APPEND_ONLY_TERMINAL_RECORD_REQUIRED")
    if row.get("immutable_terminal_record_required") is not True:
        blockers.append("IMMUTABLE_TERMINAL_RECORD_REQUIRED")
    if row.get("execution_reopen_after_terminal_forbidden") is not True:
        blockers.append("TERMINAL_REOPEN_MUST_BE_FORBIDDEN")
    if row.get("durable_reopen_consistency_required") is not True:
        blockers.append("DURABLE_REOPEN_CONSISTENCY_REQUIRED")
    if row.get("persistence_creates_execution_authority") is not False:
        blockers.append("PERSISTENCE_MUST_NOT_CREATE_EXECUTION_AUTHORITY")
    if row.get("finops_cap_cents") != FINOPS_CAP_CENTS_REQUIRED:
        blockers.append("FINOPS_CAP_MUST_REMAIN_20000_CENTS")
    if row.get("next_allowed_step") != persistence.NEXT_ALLOWED_STEP:
        blockers.append("FINALIZATION_PERSISTENCE_NEXT_STEP_INVALID")

    for key in persistence.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("FINALIZATION_PERSISTENCE_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            execution_audit_seal_design_only=True,
            seal_mode=SEAL_MODE,
            fail_closed=True,
            deterministic_manifest_required=True,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        execution_audit_seal_design_only=True,
        seal_mode=SEAL_MODE,
        fail_closed=True,
        deterministic_manifest_required=True,
        canonical_encoding_required=True,
        digest_algorithm=DIGEST_ALGORITHM,
        canonical_encoding=CANONICAL_ENCODING,
        terminal_chain_of_custody_required=True,
        all_bound_fields_immutable=True,
        same_manifest_same_digest_required=True,
        any_bound_field_change_changes_digest_required=True,
        any_verification_mismatch_fails_closed=True,
        seal_immutable=True,
        seal_append_only=True,
        seal_creates_execution_authority=False,
        seal_authorizes_retry=False,
        seal_authorizes_reopen=False,
        seal_authorizes_external_effect=False,
        finops_cap_cents=FINOPS_CAP_CENTS_REQUIRED,
        required_seal_bindings=REQUIRED_SEAL_BINDINGS,
        required_seal_invariants=REQUIRED_SEAL_INVARIANTS,
        required_verification_rules=REQUIRED_VERIFICATION_RULES,
        seal_invalidators=SEAL_INVALIDATORS,
        forbidden_seal_material=FORBIDDEN_SEAL_MATERIAL,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "SEAL_MODE",
    "DIGEST_ALGORITHM",
    "CANONICAL_ENCODING",
    "FINOPS_CAP_CENTS_REQUIRED",
    "REQUIRED_SEAL_BINDINGS",
    "REQUIRED_SEAL_INVARIANTS",
    "REQUIRED_VERIFICATION_RULES",
    "SEAL_INVALIDATORS",
    "FORBIDDEN_SEAL_MATERIAL",
    "FALSE_FIELDS",
    "build_execution_audit_seal_contract",
]
