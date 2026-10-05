"""Read-only pilot-planning read model for the Negócios cockpit.

Consumes a validated Proposal -> Pilot Planning Handoff and exposes only
aggregate planning metadata. It deliberately excludes proposal evidence refs,
planner refs, candidate identity, raw KPI source refs and any activation path.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_B2B_PILOT_PLANNING_READ_MODEL_V1"
SOURCE_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_PLANNING_HANDOFF_V1"


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


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def build_pilot_planning_read_model(
    handoff: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    source = dict(handoff) if isinstance(handoff, Mapping) else {}
    scope = _scope(trusted_scope)
    blockers: list[str] = []

    if not all(scope.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")
    if source.get("schema") != SOURCE_SCHEMA:
        blockers.append("PILOT_HANDOFF_SCHEMA_INVALID")
    if source.get("state") != "PLANNED_FOR_OWNER_REVIEW":
        blockers.append("PILOT_HANDOFF_STATE_INVALID")
    if source.get("activation_state") != "BLOCKED_UNTIL_OWNER_APPROVAL":
        blockers.append("PILOT_ACTIVATION_BOUNDARY_INVALID")
    if source.get("human_owner_approval_required") is not True:
        blockers.append("OWNER_APPROVAL_BOUNDARY_MISSING")
    if _scope(source.get("scope") if isinstance(source.get("scope"), Mapping) else {}) != scope:
        blockers.append("PILOT_HANDOFF_SCOPE_MISMATCH")

    safe_false = (
        "automatic_activation",
        "automatic_contract_signature",
        "automatic_customer_contact",
        "automatic_billing",
        "automatic_spend",
        "automatic_deploy",
        "crm_write",
        "provider_called",
        "production_mutation",
        "executes_action",
    )
    for key in safe_false:
        if source.get(key) is not False:
            blockers.append(f"PILOT_HANDOFF_{key.upper()}_UNSAFE")

    handoff_digest = _text(source.get("handoff_digest"), 180)
    if not handoff_digest:
        blockers.append("PILOT_HANDOFF_DIGEST_REQUIRED")

    contract = (
        dict(source.get("operating_contract"))
        if isinstance(source.get("operating_contract"), Mapping)
        else {}
    )
    if contract.get("state") != "DRAFT_FOR_OWNER_APPROVAL":
        blockers.append("OPERATING_CONTRACT_STATE_INVALID")
    if contract.get("activation_state") != "BLOCKED_UNTIL_OWNER_APPROVAL":
        blockers.append("OPERATING_CONTRACT_ACTIVATION_BOUNDARY_INVALID")
    if contract.get("human_owner_approval_required") is not True:
        blockers.append("OPERATING_CONTRACT_OWNER_BOUNDARY_MISSING")
    if contract.get("automatic_activation") is not False:
        blockers.append("OPERATING_CONTRACT_AUTOMATIC_ACTIVATION_UNSAFE")
    if contract.get("executes_action") is not False:
        blockers.append("OPERATING_CONTRACT_EXECUTION_BOUNDARY_UNSAFE")

    core = (
        dict(contract.get("contract"))
        if isinstance(contract.get("contract"), Mapping)
        else {}
    )
    if _scope(core) != scope:
        blockers.append("OPERATING_CONTRACT_SCOPE_MISMATCH")

    pilot_id = _text(source.get("pilot_id"), 120)
    if not pilot_id or pilot_id != _text(core.get("pilot_id"), 120):
        blockers.append("PILOT_ID_MISMATCH")

    proposal_id = _text(source.get("proposal_id"), 120)
    if not proposal_id:
        blockers.append("PROPOSAL_ID_REQUIRED")

    pilot_scope_items = [
        _text(item, 400)
        for item in list(source.get("pilot_scope_items") or [])[:20]
        if _text(item, 400)
    ]
    kpis = [
        item
        for item in list(core.get("kpis") or [])[:20]
        if isinstance(item, Mapping)
    ]
    stop_conditions = [
        _text(item, 400)
        for item in list(core.get("stop_conditions") or [])[:20]
        if _text(item, 400)
    ]
    rollback_steps = [
        _text(item, 400)
        for item in list(core.get("rollback_steps") or [])[:20]
        if _text(item, 400)
    ]
    objectives = [
        _text(item, 400)
        for item in list(core.get("objectives") or [])[:20]
        if _text(item, 400)
    ]
    quick_wins = [
        _text(item, 400)
        for item in list(core.get("quick_wins") or [])[:20]
        if _text(item, 400)
    ]

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "blockers": blockers,
            "read_only": True,
            "activation_control_exposed": False,
            "raw_evidence_exposed": False,
            "candidate_identity_exposed": False,
            "grants_authority": False,
            "executes_action": False,
        }

    return {
        "schema": SCHEMA,
        "state": "READY",
        "scope": scope,
        "pilot_id": pilot_id,
        "proposal_id": proposal_id,
        "activation_state": "BLOCKED_UNTIL_OWNER_APPROVAL",
        "duration_days": _number(core.get("duration_days")),
        "max_monthly_infra_brl": _number(core.get("max_monthly_infra_brl")),
        "pilot_scope_item_count": len(pilot_scope_items),
        "objective_count": len(objectives),
        "quick_win_count": len(quick_wins),
        "kpi_count": len(kpis),
        "stop_condition_count": len(stop_conditions),
        "rollback_step_count": len(rollback_steps),
        "handoff_digest": handoff_digest,
        "contract_digest": _text(contract.get("contract_digest"), 180),
        "read_only": True,
        "owner_review_required": True,
        "activation_control_exposed": False,
        "raw_evidence_exposed": False,
        "candidate_identity_exposed": False,
        "automatic_activation": False,
        "automatic_customer_contact": False,
        "automatic_billing": False,
        "automatic_deploy": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "grants_authority": False,
        "executes_action": False,
    }


__all__ = ["SCHEMA", "SOURCE_SCHEMA", "build_pilot_planning_read_model"]
