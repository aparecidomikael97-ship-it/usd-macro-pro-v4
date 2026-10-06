"""AION B2B terminal-certificate read-model UI runtime binding offline V1.

Offline-only, read-only and fail-closed.

Consumes only the formal Terminal Certificate Read Model Runtime Projection and
builds a safe panel view-model. This layer does not read the durable store,
perform live verification, call network/provider services, or expose action
controls.

The output is presentation data only. No state, badge, digest or section grants
execution authority.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import atlasquant_aion_b2b_execution_terminal_certificate_read_model_ui_v1 as ui_contract
import atlasquant_aion_b2b_terminal_certificate_read_model_runtime_projection_offline_v1 as projection

SCHEMA = "ATLASQUANT_AION_B2B_TERMINAL_CERTIFICATE_READ_MODEL_UI_RUNTIME_BINDING_OFFLINE_V1"
MODE = "OFFLINE_READ_ONLY_FAIL_CLOSED_TERMINAL_CERTIFICATE_PANEL_VIEW_MODEL"
NEXT_ALLOWED_STEP = "IMPLEMENT_TERMINAL_CERTIFICATE_PANEL_COMPONENT_OFFLINE_ONLY"

DISPLAY_STATES = ui_contract.DISPLAY_STATES
REQUIRED_UI_SECTIONS = ui_contract.REQUIRED_UI_SECTIONS

BADGE_TONES = {
    "VERIFIED": "POSITIVE_EVIDENCE_ONLY",
    "MISMATCH": "FAIL_CLOSED",
    "UNAVAILABLE": "EVIDENCE_UNAVAILABLE",
    "STALE": "REFRESH_REQUIRED",
}

FALSE_FIELDS = (
    "ui_action_available",
    "execution_authority_created",
    "retry_authorized",
    "reopen_authorized",
    "reconciliation_authorized",
    "rollback_authorized",
    "compensation_authorized",
    "external_effect_authorized",
    "network_called",
    "provider_called",
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
    "execution_command_generated",
    "execution_command_executed",
    "executes_action",
)


def _base_result(
    state: str,
    *,
    execution_id: str,
    error_code: str = "",
    **fields: Any,
) -> dict[str, Any]:
    if state not in DISPLAY_STATES:
        state = "MISMATCH"
        error_code = error_code or "UNKNOWN_UI_STATE"
    return {
        "schema": SCHEMA,
        "mode": MODE,
        "state": state,
        "execution_id": execution_id,
        "error_code": error_code,
        "badge": {
            "state": state,
            "tone": BADGE_TONES[state],
            "evidence_only": True,
        },
        "controls": (),
        "action_controls_present": False,
        "panel_is_observational_only": True,
        "next_allowed_step": NEXT_ALLOWED_STEP,
        **fields,
        **{key: False for key in FALSE_FIELDS},
    }


def _contains_forbidden_material(value: Any) -> bool:
    forbidden = set(ui_contract.FORBIDDEN_UI_MATERIAL)
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key) in forbidden:
                return True
            if _contains_forbidden_material(item):
                return True
        return False
    if isinstance(value, (list, tuple, set)):
        return any(_contains_forbidden_material(item) for item in value)
    return False


def build_terminal_certificate_panel_view_model_offline(
    *,
    read_model_projection: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build a safe read-only panel view-model from the formal read model."""
    row = dict(read_model_projection) if isinstance(read_model_projection, Mapping) else {}
    execution_id = " ".join(str(row.get("execution_id") or "").split())[:96]

    if row.get("schema") != projection.SCHEMA:
        return _base_result(
            "MISMATCH",
            execution_id=execution_id,
            error_code="READ_MODEL_RUNTIME_PROJECTION_SCHEMA_MISMATCH",
        )
    if row.get("mode") != projection.MODE:
        return _base_result(
            "MISMATCH",
            execution_id=execution_id,
            error_code="READ_MODEL_RUNTIME_PROJECTION_MODE_MISMATCH",
        )
    if row.get("contract_schema") != projection.contract.SCHEMA:
        return _base_result(
            "MISMATCH",
            execution_id=execution_id,
            error_code="READ_MODEL_CONTRACT_SCHEMA_MISMATCH",
        )
    if row.get("next_allowed_step") != projection.NEXT_ALLOWED_STEP:
        return _base_result(
            "MISMATCH",
            execution_id=execution_id,
            error_code="READ_MODEL_RUNTIME_PROJECTION_NEXT_STEP_INVALID",
        )

    state = row.get("state")
    if state not in DISPLAY_STATES:
        return _base_result(
            "MISMATCH",
            execution_id=execution_id,
            error_code="READ_MODEL_RUNTIME_PROJECTION_STATE_UNKNOWN",
        )
    if row.get("certificate_status") != state:
        return _base_result(
            "MISMATCH",
            execution_id=execution_id,
            error_code="CERTIFICATE_STATUS_STATE_MISMATCH",
        )
    if row.get("read_model_projection_is_evidence_not_authority") is not True:
        return _base_result(
            "MISMATCH",
            execution_id=execution_id,
            error_code="READ_MODEL_EVIDENCE_AUTHORITY_BOUNDARY_MISSING",
        )

    for key in projection.FALSE_FIELDS:
        if row.get(key) is not False:
            return _base_result(
                "MISMATCH",
                execution_id=execution_id,
                error_code="READ_MODEL_UNSAFE_AUTHORITY_FIELD:" + key,
            )

    if _contains_forbidden_material(row):
        return _base_result(
            "MISMATCH",
            execution_id=execution_id,
            error_code="FORBIDDEN_UI_MATERIAL_PRESENT",
        )

    error_code = str(row.get("error_code") or "")
    sections: dict[str, Any] = {
        "certificate_status": {
            "state": state,
            "error_code": error_code,
            "evidence_only": True,
        },
        "execution_identity": {
            "execution_id": execution_id,
        },
        "terminal_state": {
            "final_execution_state": str(row.get("final_execution_state") or ""),
        },
        "terminal_revision": {
            "terminal_revision": row.get("terminal_revision"),
        },
        "certificate_digest": {
            "certificate_manifest_digest": str(row.get("certificate_manifest_digest") or ""),
            "certificate_digest": str(row.get("certificate_digest") or ""),
            "certificate_persistence_record_digest": str(
                row.get("certificate_persistence_record_digest") or ""
            ),
        },
        "finalization_evidence": {
            "finalization_record_digest": str(row.get("finalization_record_digest") or ""),
            "terminal_evidence_set_digest": str(
                row.get("terminal_evidence_set_digest") or ""
            ),
        },
        "audit_seal_evidence": {
            "audit_seal_manifest_digest": str(row.get("audit_seal_manifest_digest") or ""),
            "audit_seal_persistence_record_digest": str(
                row.get("audit_seal_persistence_record_digest") or ""
            ),
            "pre_terminal_audit_chain_digest": str(
                row.get("pre_terminal_audit_chain_digest") or ""
            ),
        },
        "finops_evidence": {
            "finops_observation_digest": str(row.get("finops_observation_digest") or ""),
        },
        "observability_trace": {
            "observability_trace_id": str(row.get("observability_trace_id") or ""),
            "observed_at": str(row.get("observed_at") or ""),
            "persisted_at": str(row.get("persisted_at") or ""),
            "age_seconds": row.get("age_seconds"),
            "max_age_seconds": row.get("max_age_seconds"),
        },
        "scope_boundary": {
            "owner_id": str(row.get("owner_id") or ""),
            "tenant_id": str(row.get("tenant_id") or ""),
            "workspace_id": str(row.get("workspace_id") or ""),
        },
    }

    if tuple(sections.keys()) != REQUIRED_UI_SECTIONS:
        return _base_result(
            "MISMATCH",
            execution_id=execution_id,
            error_code="UI_SECTION_CONTRACT_MISMATCH",
        )

    if state in {"VERIFIED", "STALE"}:
        for key in (
            "owner_id",
            "tenant_id",
            "workspace_id",
            "final_execution_state",
            "terminal_revision",
            "certificate_digest",
            "finalization_record_digest",
            "audit_seal_manifest_digest",
            "audit_seal_persistence_record_digest",
            "finops_observation_digest",
            "observability_trace_id",
            "observed_at",
            "persisted_at",
        ):
            value = row.get(key)
            if value is None or value == "":
                return _base_result(
                    "MISMATCH",
                    execution_id=execution_id,
                    error_code="UI_EVIDENCE_REQUIRED:" + key,
                )

    return _base_result(
        state,
        execution_id=execution_id,
        error_code=error_code,
        title="Terminal Execution Certificate",
        sections=sections,
        visible_section_order=REQUIRED_UI_SECTIONS,
        source_schema=projection.SCHEMA,
        source_contract_schema=projection.contract.SCHEMA,
        source_digest_algorithm=row.get("digest_algorithm"),
        source_canonical_encoding=row.get("canonical_encoding"),
    )


__all__ = [
    "SCHEMA",
    "MODE",
    "NEXT_ALLOWED_STEP",
    "DISPLAY_STATES",
    "REQUIRED_UI_SECTIONS",
    "BADGE_TONES",
    "FALSE_FIELDS",
    "build_terminal_certificate_panel_view_model_offline",
]
