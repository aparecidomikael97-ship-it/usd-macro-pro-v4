"""AION Negócios — read-only commercial Golden Path V1.

Composes already-governed B2B artifacts into one customer/commercial journey
view. This module never performs outreach, CRM writes, pricing commitment,
contract signature, billing, provisioning, deploy or external execution.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from atlasquant_aion_b2b_diagnostic_intake import SCHEMA as DIAGNOSTIC_SCHEMA
from atlasquant_aion_b2b_managed_service_control import SCHEMA as MANAGED_SERVICE_SCHEMA
from atlasquant_aion_b2b_pilot_activation_status_read_model import SCHEMA as ACTIVATION_SCHEMA
from atlasquant_aion_b2b_pilot_planning_read_model import SCHEMA as PLANNING_SCHEMA
from atlasquant_aion_b2b_pilot_readiness import SCHEMA as READINESS_SCHEMA
from atlasquant_aion_b2b_pilot_value_read_model import SCHEMA as VALUE_SCHEMA
from atlasquant_aion_b2b_portal_read_model import SCHEMA as PORTAL_SCHEMA
from atlasquant_aion_b2b_proposal_draft import SCHEMA as PROPOSAL_SCHEMA
from atlasquant_aion_b2b_recurring_customer_projection import SCHEMA as RECURRING_SCHEMA
from atlasquant_aion_b2b_revops_read_model import SCHEMA as REVOPS_SCHEMA

SCHEMA = "ATLASQUANT_AION_B2B_COMMERCIAL_GOLDEN_PATH_V1"

STAGE_ORDER = (
    "revops",
    "diagnostic",
    "qualification",
    "proposal",
    "pilot_planning",
    "pilot_activation",
    "pilot_value",
    "managed_service",
    "customer_portal",
    "recurring_customer",
)

STAGE_LABELS = {
    "revops": "Funil / RevOps",
    "diagnostic": "Diagnóstico",
    "qualification": "Qualificação",
    "proposal": "Proposta",
    "pilot_planning": "Planejamento do piloto",
    "pilot_activation": "Ativação do piloto",
    "pilot_value": "Valor do piloto",
    "managed_service": "Serviço recorrente",
    "customer_portal": "Portal do cliente",
    "recurring_customer": "Acompanhamento recorrente",
}

_NEXT_ACTION = {
    "revops": "INICIAR_DIAGNOSTICO",
    "diagnostic": "REALIZAR_SCORE_HUMANO",
    "qualification": "REVISAR_E_DECIDIR_PILOTO",
    "proposal": "REVISAR_PROPOSTA_E_ESCOPO",
    "pilot_planning": "DECIDIR_ATIVACAO_DO_PILOTO",
    "pilot_activation": "CONFIRMAR_EXECUCAO_DO_PILOTO",
    "pilot_value": "REVISAR_VALOR_ROI_E_RETENCAO",
    "managed_service": "DECIDIR_ATIVACAO_DO_SERVICO",
    "customer_portal": "ACOMPANHAR_SLA_ROI_SAUDE_E_QUOTAS",
    "recurring_customer": "MANTER_REVISAO_PERIODICA_DE_VALOR",
}


def _text(value: Any, limit: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(data.get("owner_id"), 120),
        "tenant_id": _text(data.get("tenant_id"), 120),
        "workspace_id": _text(data.get("workspace_id"), 120),
    }


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _source_scope(stage: str, row: Mapping[str, Any]) -> dict[str, str]:
    if stage == "diagnostic":
        return _scope(row.get("dossier") if isinstance(row.get("dossier"), Mapping) else {})
    if stage == "proposal":
        return _scope(row.get("proposal") if isinstance(row.get("proposal"), Mapping) else {})
    if stage == "managed_service":
        return _scope(row.get("contract") if isinstance(row.get("contract"), Mapping) else {})
    if stage == "recurring_customer":
        return {
            "owner_id": "",
            "tenant_id": _text(row.get("service_tenant_id"), 120),
            "workspace_id": _text(row.get("workspace_id"), 120),
        }
    return _scope(row.get("scope") if isinstance(row.get("scope"), Mapping) else {})


def _unsafe_flags(row: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    strict_false = (
        "executes_action",
        "grants_authority",
        "crm_write",
        "provider_called",
        "production_mutation",
    )
    for key in strict_false:
        if key in row and row.get(key) is not False:
            blockers.append(f"UNSAFE_FLAG:{key}")
    for key, value in row.items():
        if key.startswith("automatic_") and value is True:
            blockers.append(f"UNSAFE_FLAG:{key}")
    return blockers


def _stage(
    key: str,
    raw: Mapping[str, Any] | None,
    *,
    expected_schema: str,
    accepted_states: tuple[str, ...],
    trusted_scope: Mapping[str, Any],
    ready_status: str,
    evidence_key: str = "",
    extra_checks=None,
) -> tuple[dict[str, Any], list[str]]:
    row = _mapping(raw)
    if not row:
        return {
            "key": key,
            "label": STAGE_LABELS[key],
            "status": "NOT_STARTED",
            "source_state": "",
            "evidence_digest": "",
            "human_action_required": True,
            "read_only": True,
        }, []

    blockers: list[str] = []
    if row.get("schema") != expected_schema:
        blockers.append("SCHEMA_INVALID")
    state = _text(row.get("state"), 80)
    if state not in accepted_states:
        blockers.append("STATE_INVALID")
    blockers.extend(_unsafe_flags(row))

    source_scope = _source_scope(key, row)
    for scope_key, source_value in source_scope.items():
        if source_value and source_value != trusted_scope.get(scope_key):
            blockers.append("SCOPE_MISMATCH")
            break

    if callable(extra_checks):
        blockers.extend(extra_checks(row))

    evidence = _text(row.get(evidence_key), 180) if evidence_key else ""
    stage = {
        "key": key,
        "label": STAGE_LABELS[key],
        "status": ready_status if not blockers else "BLOCKED",
        "source_state": state,
        "evidence_digest": evidence,
        "human_action_required": True,
        "read_only": True,
    }
    if blockers:
        stage["blockers"] = list(dict.fromkeys(blockers))
    return stage, [f"{key.upper()}:{item}" for item in blockers]


def _qualification_checks(row: Mapping[str, Any]) -> list[str]:
    out = []
    if row.get("decision") != "PILOT_REVIEW_CANDIDATE":
        out.append("DECISION_NOT_PILOT_REVIEW_CANDIDATE")
    if row.get("human_owner_decision_required") is not True:
        out.append("OWNER_DECISION_BOUNDARY_MISSING")
    return out


def _proposal_checks(row: Mapping[str, Any]) -> list[str]:
    out = []
    if row.get("non_binding") is not True:
        out.append("PROPOSAL_NOT_NON_BINDING")
    if row.get("owner_review_required") is not True:
        out.append("OWNER_REVIEW_BOUNDARY_MISSING")
    if row.get("customer_send_allowed") is not False:
        out.append("CUSTOMER_SEND_BOUNDARY_UNSAFE")
    if row.get("contract_ready") is not False:
        out.append("CONTRACT_BOUNDARY_UNSAFE")
    return out


def _planning_checks(row: Mapping[str, Any]) -> list[str]:
    out = []
    if row.get("activation_state") != "BLOCKED_UNTIL_OWNER_APPROVAL":
        out.append("PILOT_ACTIVATION_BOUNDARY_UNSAFE")
    if row.get("read_only") is not True:
        out.append("READ_ONLY_REQUIRED")
    return out


def _activation_checks(row: Mapping[str, Any]) -> list[str]:
    out = []
    if row.get("execution_state") != "BLOCKED_PENDING_HUMAN_CONFIRMATION":
        out.append("EXECUTION_STATE_UNSAFE")
    if row.get("human_execution_confirmation_required") is not True:
        out.append("HUMAN_CONFIRMATION_BOUNDARY_MISSING")
    if row.get("read_only") is not True:
        out.append("READ_ONLY_REQUIRED")
    return out


def _value_checks(row: Mapping[str, Any]) -> list[str]:
    out = []
    if row.get("view") != "ADMIN":
        out.append("ADMIN_VALUE_VIEW_REQUIRED")
    if row.get("owner_review_required") is not True:
        out.append("OWNER_VALUE_REVIEW_BOUNDARY_MISSING")
    if row.get("read_only") is not True:
        out.append("READ_ONLY_REQUIRED")
    return out


def _managed_service_checks(row: Mapping[str, Any]) -> list[str]:
    out = []
    if row.get("activation_state") != "BLOCKED_UNTIL_OWNER_ACTIVATION":
        out.append("SERVICE_ACTIVATION_BOUNDARY_UNSAFE")
    if row.get("owner_activation_required") is not True:
        out.append("OWNER_ACTIVATION_BOUNDARY_MISSING")
    return out


def _portal_checks(row: Mapping[str, Any]) -> list[str]:
    out = []
    if row.get("read_only") is not True:
        out.append("READ_ONLY_REQUIRED")
    return out


def _recurring_checks(row: Mapping[str, Any]) -> list[str]:
    out = []
    if row.get("read_only") is not True:
        out.append("READ_ONLY_REQUIRED")
    if row.get("customer_safe") is not True:
        out.append("CUSTOMER_SAFE_PROJECTION_REQUIRED")
    if row.get("allowed") is not True:
        out.append("CUSTOMER_PROJECTION_NOT_ALLOWED")
    return out


def build_commercial_golden_path(
    *,
    trusted_scope: Mapping[str, Any] | None,
    revops_read_model: Mapping[str, Any] | None = None,
    diagnostic: Mapping[str, Any] | None = None,
    readiness: Mapping[str, Any] | None = None,
    proposal_draft: Mapping[str, Any] | None = None,
    pilot_planning_read_model: Mapping[str, Any] | None = None,
    pilot_activation_status_read_model: Mapping[str, Any] | None = None,
    pilot_value_read_model: Mapping[str, Any] | None = None,
    managed_service_contract: Mapping[str, Any] | None = None,
    portal_read_model: Mapping[str, Any] | None = None,
    recurring_projection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a single read-only commercial journey projection."""
    trusted = _scope(trusted_scope)
    blockers: list[str] = []
    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")

    stages: list[dict[str, Any]] = []

    stage, found = _stage(
        "revops", revops_read_model,
        expected_schema=REVOPS_SCHEMA,
        accepted_states=("READY", "PARTIAL"),
        trusted_scope=trusted,
        ready_status="FUNNEL_VISIBLE",
        evidence_key="evidence_digest",
        extra_checks=lambda row: [] if row.get("read_only") is True else ["READ_ONLY_REQUIRED"],
    )
    stages.append(stage); blockers.extend(found)

    stage, found = _stage(
        "diagnostic", diagnostic,
        expected_schema=DIAGNOSTIC_SCHEMA,
        accepted_states=("READY_FOR_HUMAN_SCORING",),
        trusted_scope=trusted,
        ready_status="WAITING_HUMAN_SCORING",
        evidence_key="diagnostic_digest",
    )
    stages.append(stage); blockers.extend(found)

    stage, found = _stage(
        "qualification", readiness,
        expected_schema=READINESS_SCHEMA,
        accepted_states=("READY_FOR_OWNER_REVIEW",),
        trusted_scope=trusted,
        ready_status="WAITING_OWNER_REVIEW",
        evidence_key="evidence_digest",
        extra_checks=_qualification_checks,
    )
    stages.append(stage); blockers.extend(found)

    stage, found = _stage(
        "proposal", proposal_draft,
        expected_schema=PROPOSAL_SCHEMA,
        accepted_states=("DRAFT_FOR_HUMAN_REVIEW",),
        trusted_scope=trusted,
        ready_status="WAITING_HUMAN_REVIEW",
        evidence_key="proposal_digest",
        extra_checks=_proposal_checks,
    )
    stages.append(stage); blockers.extend(found)

    stage, found = _stage(
        "pilot_planning", pilot_planning_read_model,
        expected_schema=PLANNING_SCHEMA,
        accepted_states=("READY",),
        trusted_scope=trusted,
        ready_status="WAITING_OWNER_APPROVAL",
        evidence_key="handoff_digest",
        extra_checks=_planning_checks,
    )
    stages.append(stage); blockers.extend(found)

    stage, found = _stage(
        "pilot_activation", pilot_activation_status_read_model,
        expected_schema=ACTIVATION_SCHEMA,
        accepted_states=("READY",),
        trusted_scope=trusted,
        ready_status="WAITING_HUMAN_EXECUTION_CONFIRMATION",
        extra_checks=_activation_checks,
    )
    stages.append(stage); blockers.extend(found)

    stage, found = _stage(
        "pilot_value", pilot_value_read_model,
        expected_schema=VALUE_SCHEMA,
        accepted_states=("READY",),
        trusted_scope=trusted,
        ready_status="WAITING_OWNER_VALUE_REVIEW",
        evidence_key="evidence_digest",
        extra_checks=_value_checks,
    )
    stages.append(stage); blockers.extend(found)

    stage, found = _stage(
        "managed_service", managed_service_contract,
        expected_schema=MANAGED_SERVICE_SCHEMA,
        accepted_states=("DRAFT_FOR_OWNER_ACTIVATION",),
        trusted_scope=trusted,
        ready_status="WAITING_OWNER_ACTIVATION",
        evidence_key="contract_digest",
        extra_checks=_managed_service_checks,
    )
    stages.append(stage); blockers.extend(found)

    stage, found = _stage(
        "customer_portal", portal_read_model,
        expected_schema=PORTAL_SCHEMA,
        accepted_states=("READY",),
        trusted_scope=trusted,
        ready_status="ACTIVE_MONITORING",
        evidence_key="evidence_digest",
        extra_checks=_portal_checks,
    )
    stages.append(stage); blockers.extend(found)

    stage, found = _stage(
        "recurring_customer", recurring_projection,
        expected_schema=RECURRING_SCHEMA,
        accepted_states=("READY",),
        trusted_scope=trusted,
        ready_status="CUSTOMER_SAFE_RECURRING_VIEW",
        evidence_key="evidence_digest",
        extra_checks=_recurring_checks,
    )
    stages.append(stage); blockers.extend(found)

    started = [row for row in stages if row["status"] != "NOT_STARTED"]
    ready_indices = [
        index for index, row in enumerate(stages)
        if row["status"] not in {"NOT_STARTED", "BLOCKED"}
    ]
    current_index = max(ready_indices) if ready_indices else -1
    current_key = STAGE_ORDER[current_index] if current_index >= 0 else ""

    gaps: list[str] = []
    if current_index >= 0:
        for index in range(0, current_index):
            if stages[index]["status"] == "NOT_STARTED":
                gaps.append(STAGE_ORDER[index])

    critical_blockers = list(dict.fromkeys(blockers))
    if critical_blockers:
        state = "BLOCKED"
    elif gaps:
        state = "READY_WITH_GAPS"
    elif started:
        state = "READY"
    else:
        state = "EMPTY"

    next_action = (
        _NEXT_ACTION.get(current_key, "CAPTURAR_E_VALIDAR_LEAD")
        if current_key
        else "CAPTURAR_E_VALIDAR_LEAD"
    )
    if current_key == "recurring_customer":
        next_action = _NEXT_ACTION["recurring_customer"]

    material = {
        "scope": trusted,
        "state": state,
        "current_stage": current_key,
        "stage_statuses": {row["key"]: row["status"] for row in stages},
        "lineage_gaps": gaps,
        "next_human_action": next_action,
    }

    return {
        "schema": SCHEMA,
        "state": state,
        "scope": trusted,
        "current_stage": current_key,
        "current_stage_label": STAGE_LABELS.get(current_key, "Lead / oportunidade"),
        "next_human_action": next_action,
        "stages": stages,
        "lineage_gaps": gaps,
        "blockers": critical_blockers,
        "evidence_digest": _digest(material),
        "read_only": True,
        "raw_lead_data_exposed": False,
        "raw_customer_data_exposed": False,
        "customer_contact_control_exposed": False,
        "crm_write": False,
        "automatic_outreach": False,
        "automatic_followup": False,
        "automatic_stage_change": False,
        "automatic_owner_assignment": False,
        "automatic_pricing": False,
        "automatic_proposal": False,
        "automatic_contract": False,
        "automatic_billing": False,
        "automatic_provisioning": False,
        "automatic_activation": False,
        "automatic_deploy": False,
        "provider_called": False,
        "production_mutation": False,
        "grants_authority": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "STAGE_ORDER",
    "STAGE_LABELS",
    "build_commercial_golden_path",
]
