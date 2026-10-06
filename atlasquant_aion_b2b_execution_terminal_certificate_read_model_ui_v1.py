"""AION B2B execution terminal certificate read-model UI contract V1.

Design-only, fail-closed, read-only and non-executable.

Defines the presentation boundary for a future terminal-certificate panel. The
panel may display only evidence already admitted by the terminal certificate
read-model contract. It must never turn a status badge, evidence digest or
terminal certificate into execution authority.

No HTML is rendered here. No store is read, no certificate is issued or signed,
no provider is called and no external action is performed.

Maximum positive state:
READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_READ_MODEL_UI_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_execution_terminal_certificate_read_model_v1 as read_model

SCHEMA = "ATLASQUANT_AION_B2B_EXECUTION_TERMINAL_CERTIFICATE_READ_MODEL_UI_V1"
READY = "READY_FOR_EXECUTION_TERMINAL_CERTIFICATE_READ_MODEL_UI_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_EXECUTION_TERMINAL_CERTIFICATE_RUNTIME_READER_ONLY"

UI_MODE = "READ_ONLY_FAIL_CLOSED_TERMINAL_CERTIFICATE_PANEL"
DIGEST_ALGORITHM = "SHA256"
CANONICAL_ENCODING = "UTF8_CANONICAL_JSON"
FINOPS_CAP_CENTS_REQUIRED = 20000

DISPLAY_STATES = (
    "VERIFIED",
    "MISMATCH",
    "UNAVAILABLE",
    "STALE",
)

REQUIRED_UI_SECTIONS = (
    "certificate_status",
    "execution_identity",
    "terminal_state",
    "terminal_revision",
    "certificate_digest",
    "finalization_evidence",
    "audit_seal_evidence",
    "finops_evidence",
    "observability_trace",
    "scope_boundary",
)

REQUIRED_UI_RULES = (
    "UI_CONSUMES_READ_MODEL_ONLY",
    "TENANT_SCOPE_MUST_MATCH",
    "WORKSPACE_SCOPE_MUST_MATCH",
    "VERIFIED_REQUIRES_VERIFIED_READ_MODEL_STATE",
    "MISMATCH_MUST_RENDER_FAIL_CLOSED",
    "UNAVAILABLE_MUST_RENDER_EVIDENCE_MISSING",
    "STALE_MUST_RENDER_REFRESH_REQUIRED",
    "NO_UNKNOWN_STATE_MAY_RENDER_VERIFIED",
    "NO_STATUS_GRANTS_EXECUTION_AUTHORITY",
    "NO_STATUS_GRANTS_RETRY_AUTHORITY",
    "NO_STATUS_GRANTS_REOPEN_AUTHORITY",
    "NO_STATUS_GRANTS_EXTERNAL_EFFECT_AUTHORITY",
    "NO_UI_CONTROL_MAY_MUTATE_TERMINAL_RECORD",
    "NO_UI_CONTROL_MAY_MUTATE_CERTIFICATE_RECORD",
    "NO_UI_CONTROL_MAY_TRIGGER_PROVIDER",
    "NO_UI_CONTROL_MAY_TRIGGER_BILLING",
    "NO_UI_CONTROL_MAY_WRITE_CRM",
    "NO_UI_CONTROL_MAY_DEPLOY",
    "RAW_SECRET_MATERIAL_MUST_NEVER_RENDER",
    "RAW_PROVIDER_PAYLOAD_MUST_NEVER_RENDER",
    "RAW_CUSTOMER_MESSAGE_MUST_NEVER_RENDER",
)

FORBIDDEN_UI_CONTROLS = (
    "execute_action_button",
    "retry_button",
    "reopen_execution_button",
    "reconcile_button",
    "rollback_button",
    "compensate_button",
    "issue_certificate_button",
    "sign_certificate_button",
    "delete_certificate_button",
    "replace_certificate_button",
    "billing_button",
    "customer_contact_button",
    "crm_write_button",
    "provision_button",
    "deploy_button",
    "production_mutation_button",
)

FORBIDDEN_UI_MATERIAL = (
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
    "ui_rendered",
    "live_read_performed",
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


def build_execution_terminal_certificate_read_model_ui_contract(
    *,
    terminal_certificate_read_model_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define the future UI boundary; render nothing."""
    row = (
        dict(terminal_certificate_read_model_review)
        if isinstance(terminal_certificate_read_model_review, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != read_model.SCHEMA:
        blockers.append("TERMINAL_CERTIFICATE_READ_MODEL_SCHEMA_REQUIRED")
    if row.get("state") != read_model.READY:
        blockers.append("TERMINAL_CERTIFICATE_READ_MODEL_DESIGN_REVIEW_REQUIRED")
    if row.get("execution_terminal_certificate_read_model_design_only") is not True:
        blockers.append("TERMINAL_CERTIFICATE_READ_MODEL_NOT_DESIGN_ONLY")
    if row.get("fail_closed") is not True:
        blockers.append("FAIL_CLOSED_READ_MODEL_REQUIRED")
    if row.get("read_only") is not True:
        blockers.append("READ_ONLY_READ_MODEL_REQUIRED")
    if row.get("observational_only") is not True:
        blockers.append("OBSERVATIONAL_ONLY_READ_MODEL_REQUIRED")
    if row.get("persisted_certificate_required") is not True:
        blockers.append("PERSISTED_CERTIFICATE_REQUIRED")
    if row.get("tenant_scope_required") is not True:
        blockers.append("TENANT_SCOPE_REQUIRED")
    if row.get("workspace_scope_required") is not True:
        blockers.append("WORKSPACE_SCOPE_REQUIRED")
    if row.get("verification_status_fail_closed") is not True:
        blockers.append("FAIL_CLOSED_VERIFICATION_STATUS_REQUIRED")
    if row.get("verified_requires_all_bound_digests_match") is not True:
        blockers.append("ALL_BOUND_DIGESTS_MATCH_REQUIRED")
    if row.get("unavailable_never_implies_verified") is not True:
        blockers.append("UNAVAILABLE_MUST_NOT_IMPLY_VERIFIED")
    if row.get("stale_never_implies_verified") is not True:
        blockers.append("STALE_MUST_NOT_IMPLY_VERIFIED")
    if row.get("mismatch_never_implies_verified") is not True:
        blockers.append("MISMATCH_MUST_NOT_IMPLY_VERIFIED")
    if row.get("read_model_creates_execution_authority") is not False:
        blockers.append("READ_MODEL_MUST_NOT_CREATE_EXECUTION_AUTHORITY")
    if row.get("read_model_authorizes_retry") is not False:
        blockers.append("READ_MODEL_MUST_NOT_AUTHORIZE_RETRY")
    if row.get("read_model_authorizes_reopen") is not False:
        blockers.append("READ_MODEL_MUST_NOT_AUTHORIZE_REOPEN")
    if row.get("read_model_authorizes_external_effect") is not False:
        blockers.append("READ_MODEL_MUST_NOT_AUTHORIZE_EXTERNAL_EFFECT")
    if tuple(row.get("read_model_states") or ()) != DISPLAY_STATES:
        blockers.append("READ_MODEL_DISPLAY_STATES_MUST_MATCH")
    if row.get("digest_algorithm") != DIGEST_ALGORITHM:
        blockers.append("SHA256_DIGEST_REQUIRED")
    if row.get("canonical_encoding") != CANONICAL_ENCODING:
        blockers.append("UTF8_CANONICAL_JSON_REQUIRED")
    if row.get("finops_cap_cents") != FINOPS_CAP_CENTS_REQUIRED:
        blockers.append("FINOPS_CAP_MUST_REMAIN_20000_CENTS")
    if row.get("next_allowed_step") != read_model.NEXT_ALLOWED_STEP:
        blockers.append("TERMINAL_CERTIFICATE_READ_MODEL_NEXT_STEP_INVALID")

    for key in read_model.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("TERMINAL_CERTIFICATE_READ_MODEL_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            execution_terminal_certificate_read_model_ui_design_only=True,
            ui_mode=UI_MODE,
            fail_closed=True,
            read_only=True,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        execution_terminal_certificate_read_model_ui_design_only=True,
        ui_mode=UI_MODE,
        fail_closed=True,
        read_only=True,
        observational_only=True,
        ui_consumes_read_model_only=True,
        tenant_scope_must_match=True,
        workspace_scope_must_match=True,
        verified_badge_requires_verified_state=True,
        mismatch_badge_fail_closed=True,
        unavailable_badge_fail_closed=True,
        stale_badge_fail_closed=True,
        action_controls_forbidden=True,
        raw_secret_render_forbidden=True,
        raw_provider_payload_render_forbidden=True,
        raw_customer_message_render_forbidden=True,
        ui_creates_execution_authority=False,
        ui_authorizes_retry=False,
        ui_authorizes_reopen=False,
        ui_authorizes_external_effect=False,
        digest_algorithm=DIGEST_ALGORITHM,
        canonical_encoding=CANONICAL_ENCODING,
        finops_cap_cents=FINOPS_CAP_CENTS_REQUIRED,
        display_states=DISPLAY_STATES,
        required_ui_sections=REQUIRED_UI_SECTIONS,
        required_ui_rules=REQUIRED_UI_RULES,
        forbidden_ui_controls=FORBIDDEN_UI_CONTROLS,
        forbidden_ui_material=FORBIDDEN_UI_MATERIAL,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "UI_MODE",
    "DIGEST_ALGORITHM",
    "CANONICAL_ENCODING",
    "FINOPS_CAP_CENTS_REQUIRED",
    "DISPLAY_STATES",
    "REQUIRED_UI_SECTIONS",
    "REQUIRED_UI_RULES",
    "FORBIDDEN_UI_CONTROLS",
    "FORBIDDEN_UI_MATERIAL",
    "FALSE_FIELDS",
    "build_execution_terminal_certificate_read_model_ui_contract",
]
