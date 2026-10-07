"""AION B2B execution terminal certificate runtime reader contract V1.

Design-only, fail-closed, read-only and non-executable.

Defines the safety boundary for a future runtime reader of persisted terminal
certificate evidence. This layer performs no live read. It does not open a
store, query a provider, render a UI, mutate records or create execution
authority.

Maximum positive state:
READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_RUNTIME_READER_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_execution_terminal_certificate_read_model_ui_v1 as ui

SCHEMA = "ATLASQUANT_AION_B2B_EXECUTION_TERMINAL_CERTIFICATE_RUNTIME_READER_V1"
READY = "READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_RUNTIME_READER_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = (
    "DESIGN_EXECUTION_TERMINAL_CERTIFICATE_RUNTIME_READER_STORE_ADAPTER_ONLY"
)

RUNTIME_READER_MODE = "READ_ONLY_FAIL_CLOSED_TERMINAL_CERTIFICATE_RUNTIME_READER"
DIGEST_ALGORITHM = "SHA256"
CANONICAL_ENCODING = "UTF8_CANONICAL_JSON"
FINOPS_CAP_CENTS_REQUIRED = 20000

RUNTIME_READER_STATES = (
    "VERIFIED",
    "MISMATCH",
    "UNAVAILABLE",
    "STALE",
)

REQUIRED_RUNTIME_READER_RULES = (
    "READ_MODEL_IS_ONLY_LOGICAL_SOURCE",
    "PERSISTED_CERTIFICATE_REQUIRED",
    "CANONICAL_EXECUTION_ID_REQUIRED",
    "TENANT_SCOPE_MUST_MATCH",
    "WORKSPACE_SCOPE_MUST_MATCH",
    "TERMINAL_REVISION_MUST_MATCH",
    "SNAPSHOT_CONSISTENCY_REQUIRED",
    "CERTIFICATE_DIGEST_MUST_MATCH_FOR_VERIFIED",
    "FINALIZATION_DIGEST_MUST_MATCH_FOR_VERIFIED",
    "AUDIT_SEAL_DIGEST_MUST_MATCH_FOR_VERIFIED",
    "ANY_MISMATCH_MUST_FAIL_CLOSED",
    "MISSING_EVIDENCE_MUST_RETURN_UNAVAILABLE",
    "STALE_EVIDENCE_MUST_RETURN_STALE",
    "UNKNOWN_STATE_MUST_FAIL_CLOSED",
    "NO_PROVIDER_FALLBACK",
    "NO_NETWORK_FALLBACK",
    "NO_UI_STATE_MAY_CREATE_AUTHORITY",
    "NO_READ_STATUS_GRANTS_EXECUTION_AUTHORITY",
    "NO_READ_STATUS_GRANTS_RETRY_AUTHORITY",
    "NO_READ_STATUS_GRANTS_REOPEN_AUTHORITY",
    "NO_READ_STATUS_GRANTS_EXTERNAL_EFFECT_AUTHORITY",
    "NO_RUNTIME_READER_MUTATION",
)

FORBIDDEN_RUNTIME_READER_MATERIAL = (
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
    "runtime_read_performed",
    "runtime_reader_connected",
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

def build_execution_terminal_certificate_runtime_reader_contract(
    *,
    terminal_certificate_read_model_ui_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define a future runtime reader boundary; perform no runtime read."""
    row = (
        dict(terminal_certificate_read_model_ui_review)
        if isinstance(terminal_certificate_read_model_ui_review, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != ui.SCHEMA:
        blockers.append("TERMINAL_CERTIFICATE_READ_MODEL_UI_SCHEMA_REQUIRED")
    if row.get("state") != ui.READY:
        blockers.append("TERMINAL_CERTIFICATE_READ_MODEL_UI_DESIGN_REVIEW_REQUIRED")
    if row.get("execution_terminal_certificate_read_model_ui_design_only") is not True:
        blockers.append("TERMINAL_CERTIFICATE_READ_MODEL_UI_NOT_DESIGN_ONLY")
    if row.get("fail_closed") is not True:
        blockers.append("FAIL_CLOSED_UI_REQUIRED")
    if row.get("read_only") is not True:
        blockers.append("READ_ONLY_UI_REQUIRED")
    if row.get("observational_only") is not True:
        blockers.append("OBSERVATIONAL_ONLY_UI_REQUIRED")
    if row.get("ui_consumes_read_model_only") is not True:
        blockers.append("UI_MUST_CONSUME_READ_MODEL_ONLY")
    if row.get("tenant_scope_must_match") is not True:
        blockers.append("TENANT_SCOPE_MATCH_REQUIRED")
    if row.get("workspace_scope_must_match") is not True:
        blockers.append("WORKSPACE_SCOPE_MATCH_REQUIRED")
    if row.get("verified_badge_requires_verified_state") is not True:
        blockers.append("VERIFIED_BADGE_MUST_REQUIRE_VERIFIED_STATE")
    if row.get("mismatch_badge_fail_closed") is not True:
        blockers.append("MISMATCH_BADGE_MUST_FAIL_CLOSED")
    if row.get("unavailable_badge_fail_closed") is not True:
        blockers.append("UNAVAILABLE_BADGE_MUST_FAIL_CLOSED")
    if row.get("stale_badge_fail_closed") is not True:
        blockers.append("STALE_BADGE_MUST_FAIL_CLOSED")
    if row.get("action_controls_forbidden") is not True:
        blockers.append("ACTION_CONTROLS_MUST_REMAIN_FORBIDDEN")
    if row.get("ui_creates_execution_authority") is not False:
        blockers.append("UI_MUST_NOT_CREATE_EXECUTION_AUTHORITY")
    if row.get("ui_authorizes_retry") is not False:
        blockers.append("UI_MUST_NOT_AUTHORIZE_RETRY")
    if row.get("ui_authorizes_reopen") is not False:
        blockers.append("UI_MUST_NOT_AUTHORIZE_REOPEN")
    if row.get("ui_authorizes_external_effect") is not False:
        blockers.append("UI_MUST_NOT_AUTHORIZE_EXTERNAL_EFFECT")
    if tuple(row.get("display_states") or ()) != RUNTIME_READER_STATES:
        blockers.append("RUNTIME_READER_STATES_MUST_MATCH_UI_STATES")
    if row.get("digest_algorithm") != DIGEST_ALGORITHM:
        blockers.append("SHA256_DIGEST_REQUIRED")
    if row.get("canonical_encoding") != CANONICAL_ENCODING:
        blockers.append("UTF8_CANONICAL_JSON_REQUIRED")
    if row.get("finops_cap_cents") != FINOPS_CAP_CENTS_REQUIRED:
        blockers.append("FINOPS_CAP_MUST_REMAIN_20000_CENTS")
    if row.get("next_allowed_step") != ui.NEXT_ALLOWED_STEP:
        blockers.append("TERMINAL_CERTIFICATE_UI_NEXT_STEP_INVALID")

    for key in ui.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("TERMINAL_CERTIFICATE_UI_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            execution_terminal_certificate_runtime_reader_design_only=True,
            runtime_reader_mode=RUNTIME_READER_MODE,
            fail_closed=True,
            read_only=True,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        execution_terminal_certificate_runtime_reader_design_only=True,
        runtime_reader_mode=RUNTIME_READER_MODE,
        fail_closed=True,
        read_only=True,
        observational_only=True,
        read_model_is_only_logical_source=True,
        persisted_certificate_required=True,
        canonical_execution_id_required=True,
        tenant_scope_must_match=True,
        workspace_scope_must_match=True,
        terminal_revision_must_match=True,
        snapshot_consistency_required=True,
        verified_requires_bound_digest_match=True,
        mismatch_returns_fail_closed=True,
        unavailable_returns_fail_closed=True,
        stale_returns_fail_closed=True,
        provider_fallback_forbidden=True,
        network_fallback_forbidden=True,
        mutation_forbidden=True,
        runtime_reader_creates_execution_authority=False,
        runtime_reader_authorizes_retry=False,
        runtime_reader_authorizes_reopen=False,
        runtime_reader_authorizes_external_effect=False,
        digest_algorithm=DIGEST_ALGORITHM,
        canonical_encoding=CANONICAL_ENCODING,
        finops_cap_cents=FINOPS_CAP_CENTS_REQUIRED,
        runtime_reader_states=RUNTIME_READER_STATES,
        required_runtime_reader_rules=REQUIRED_RUNTIME_READER_RULES,
        forbidden_runtime_reader_material=FORBIDDEN_RUNTIME_READER_MATERIAL,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        next_allowed_step=NEXT_ALLOWED_STEP,
    )

__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "RUNTIME_READER_MODE",
    "DIGEST_ALGORITHM",
    "CANONICAL_ENCODING",
    "FINOPS_CAP_CENTS_REQUIRED",
    "RUNTIME_READER_STATES",
    "REQUIRED_RUNTIME_READER_RULES",
    "FORBIDDEN_RUNTIME_READER_MATERIAL",
    "FALSE_FIELDS",
    "build_execution_terminal_certificate_runtime_reader_contract",
]
