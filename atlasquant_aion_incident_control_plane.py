"""AION incident control-plane authority contract.

This module answers who may propose STOP/REENABLE for each capability. It is a
pure authorization/readiness decision layer: it never mutates a feature flag,
kills a process, rotates a secret, deploys, trades, pays, or calls a provider.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json

SCHEMA = "ATLASQUANT_AION_INCIDENT_CONTROL_AUTHORITY_V1"

CAPABILITIES = {
    "global_worker": {"critical": True, "scope": "GLOBAL"},
    "external_tools": {"critical": False, "scope": "TENANT"},
    "model_provider": {"critical": False, "scope": "TENANT"},
    "memory_promotion": {"critical": False, "scope": "TENANT"},
    "external_messaging": {"critical": False, "scope": "TENANT"},
    "crm_mutation": {"critical": False, "scope": "TENANT"},
    "payments": {"critical": True, "scope": "TENANT"},
    "real_trading": {"critical": True, "scope": "TENANT"},
    "merge_main": {"critical": True, "scope": "GLOBAL"},
    "deploy_production": {"critical": True, "scope": "GLOBAL"},
    "credential_use": {"critical": True, "scope": "TENANT"},
}

ACTORS = (
    "HUMAN_OWNER",
    "DELEGATED_ADMIN",
    "guardian",
    "sentinel",
)

DELEGATED_STOP = {
    "external_tools",
    "model_provider",
    "memory_promotion",
    "external_messaging",
    "crm_mutation",
}

INTERNAL_RECOMMEND = {
    "guardian",
    "sentinel",
}


def _text(value: Any, limit: int = 160) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def capability_authority_matrix() -> dict[str, Any]:
    rows = []
    for capability, config in CAPABILITIES.items():
        critical = bool(config["critical"])
        rows.append({
            "capability": capability,
            "critical": critical,
            "scope_mode": config["scope"],
            "human_owner_may_request_stop": True,
            "delegated_admin_may_request_stop": capability in DELEGATED_STOP,
            "guardian_may_recommend_stop": True,
            "sentinel_may_recommend_stop": True,
            "human_owner_required_for_reenable": True,
            "recovery_evidence_required_for_reenable": True,
            "incident_closure_required_for_reenable": True,
            "automatic_stop": False,
            "automatic_reenable": False,
            "executes_action": False,
        })
    return {
        "schema": SCHEMA,
        "capabilities": rows,
        "critical_capabilities": sorted(
            capability for capability, cfg in CAPABILITIES.items() if cfg["critical"]
        ),
        "internal_roles_can_recommend_but_not_mutate": True,
        "reenable_is_stricter_than_stop": True,
        "automatic_control_mutation": False,
        "executes_action": False,
    }


def evaluate_control_request(
    *,
    actor: Any,
    capability: Any,
    desired_state: Any,
    trusted_scope: Mapping[str, Any] | None,
    incident: Mapping[str, Any] | None = None,
    recovery_evidence_verified: Any = False,
    explicit_owner_approval: Any = False,
) -> dict[str, Any]:
    """Return whether a control request may progress to a downstream mutation gate."""
    actor_id = _text(actor, 80)
    cap = _text(capability, 100).lower()
    desired = _text(desired_state, 40).upper()
    scope = dict(trusted_scope or {})
    owner_id = _text(scope.get("owner_id"), 100)
    tenant_id = _text(scope.get("tenant_id"), 100)
    workspace_id = _text(scope.get("workspace_id"), 100)
    blockers: list[str] = []

    if actor_id not in ACTORS:
        blockers.append("ACTOR_NOT_AUTHORIZED")
    config = CAPABILITIES.get(cap)
    if config is None:
        blockers.append("CAPABILITY_UNKNOWN")
        config = {"critical": True, "scope": "GLOBAL"}
    if desired not in {"STOPPED", "RUNNING"}:
        blockers.append("DESIRED_STATE_INVALID")
    if not owner_id:
        blockers.append("OWNER_SCOPE_REQUIRED")
    if config["scope"] == "TENANT" and (not tenant_id or not workspace_id):
        blockers.append("TENANT_WORKSPACE_SCOPE_REQUIRED")

    incident_row = dict(incident or {})
    incident_id = _text(incident_row.get("incident_id"), 120)
    incident_status = _text(incident_row.get("status"), 40).upper()
    incident_severity = _text(incident_row.get("severity"), 40).upper()
    if desired == "STOPPED" and not incident_id:
        blockers.append("INCIDENT_REFERENCE_REQUIRED")

    owner_approval = explicit_owner_approval is True
    recovery_ok = recovery_evidence_verified is True

    recommendation_only = actor_id in INTERNAL_RECOMMEND
    request_allowed = False
    reason = "BLOCKED"

    if desired == "STOPPED" and not blockers:
        if actor_id == "HUMAN_OWNER":
            request_allowed = True
            reason = "OWNER_STOP_REQUEST"
        elif actor_id == "DELEGATED_ADMIN" and cap in DELEGATED_STOP:
            request_allowed = True
            reason = "DELEGATED_NONCRITICAL_STOP_REQUEST"
        elif recommendation_only:
            reason = "INTERNAL_ROLE_RECOMMENDATION_ONLY"
        else:
            blockers.append("STOP_AUTHORITY_INSUFFICIENT")

    if desired == "RUNNING":
        if actor_id != "HUMAN_OWNER":
            blockers.append("OWNER_REQUIRED_FOR_REENABLE")
        if not owner_approval:
            blockers.append("EXPLICIT_OWNER_APPROVAL_REQUIRED")
        if not incident_id:
            blockers.append("INCIDENT_REFERENCE_REQUIRED")
        if incident_status != "CLOSED":
            blockers.append("INCIDENT_NOT_CLOSED")
        if not recovery_ok:
            blockers.append("RECOVERY_EVIDENCE_REQUIRED")
        if not blockers:
            request_allowed = True
            reason = "OWNER_REENABLE_REQUEST_WITH_RECOVERY_EVIDENCE"

    if cap in CAPABILITIES and CAPABILITIES[cap]["critical"] and desired == "STOPPED":
        if actor_id != "HUMAN_OWNER":
            request_allowed = False
            if recommendation_only:
                reason = "INTERNAL_ROLE_RECOMMENDATION_ONLY"
            elif "OWNER_REQUIRED_FOR_CRITICAL_STOP" not in blockers:
                blockers.append("OWNER_REQUIRED_FOR_CRITICAL_STOP")

    unique = list(dict.fromkeys(blockers))
    request_allowed = bool(request_allowed and not unique)
    state = (
        "MAY_PROGRESS_TO_MUTATION_GATE"
        if request_allowed
        else "RECOMMEND_STOP"
        if recommendation_only and desired == "STOPPED" and not any(
            x in unique for x in ("ACTOR_NOT_AUTHORIZED", "CAPABILITY_UNKNOWN", "DESIRED_STATE_INVALID")
        )
        else "BLOCKED"
    )

    binding = {
        "actor": actor_id,
        "capability": cap,
        "desired_state": desired,
        "owner_id": owner_id,
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "incident_id": incident_id,
        "incident_status": incident_status,
        "incident_severity": incident_severity,
        "recovery_evidence_verified": recovery_ok,
        "explicit_owner_approval": owner_approval,
    }
    return {
        "schema": SCHEMA,
        "state": state,
        "reason": reason,
        "blockers": unique,
        "binding": binding,
        "control_request_digest": _digest(binding),
        "request_may_progress": request_allowed,
        "recommendation_only": recommendation_only,
        "critical_capability": bool(config["critical"]),
        "scope_mode": config["scope"],
        "requires_downstream_mutation_gate": request_allowed,
        "feature_flag_modified": False,
        "process_killed": False,
        "credential_rotated": False,
        "automatic_stop": False,
        "automatic_reenable": False,
        "grants_authority": False,
        "executes_action": False,
    }


def incident_shutdown_plan(
    incident: Mapping[str, Any] | None,
    *,
    capability: Any,
) -> dict[str, Any]:
    """Produce an operational runbook slice without performing containment."""
    row = dict(incident or {})
    cap = _text(capability, 100).lower()
    config = CAPABILITIES.get(cap)
    blockers = []
    if config is None:
        blockers.append("CAPABILITY_UNKNOWN")
    if not _text(row.get("incident_id"), 120):
        blockers.append("INCIDENT_REFERENCE_REQUIRED")
    severity = _text(row.get("severity"), 40).upper()
    if severity not in {"HIGH", "CRITICAL"}:
        blockers.append("HIGH_OR_CRITICAL_INCIDENT_REQUIRED")

    return {
        "schema": SCHEMA,
        "state": "PLAN_READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        "incident_id": _text(row.get("incident_id"), 120),
        "capability": cap,
        "steps": [
            "Preservar evidência e identificar o escopo afetado.",
            "Solicitar STOP ao ator autorizado para a capability.",
            "Aplicar a mudança apenas no downstream mutation gate auditado.",
            "Verificar ausência de novos efeitos e reconciliar trabalho em voo.",
            "Fechar o incidente somente com causa/impacto/evidência registrados.",
            "Exigir HUMAN_OWNER + evidência de recuperação para REENABLE.",
        ],
        "automatic_containment": False,
        "automatic_reenable": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "CAPABILITIES",
    "ACTORS",
    "capability_authority_matrix",
    "evaluate_control_request",
    "incident_shutdown_plan",
]
