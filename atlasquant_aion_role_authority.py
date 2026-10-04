"""Authority matrix for the eight official AION internal roles.

Roles are responsibilities inside one shared core. This module makes their
proposal/review boundaries explicit and never grants autonomous authority for
critical actions. Human approval does not itself execute an action; downstream
execution gates remain mandatory.
"""
from __future__ import annotations

from typing import Any

SCHEMA = "ATLASQUANT_AION_ROLE_AUTHORITY_V1"

OFFICIAL_ROLE_IDS = (
    "orchestrator",
    "architect",
    "guardian",
    "prime",
    "shadow",
    "sentinel",
    "commercial",
    "educator",
)

_PURPOSES = {
    "orchestrator": "Coordena contexto, prioridades e handoffs do núcleo.",
    "architect": "Desenha arquitetura, estratégia, dependências e evolução.",
    "guardian": "Audita políticas, riscos, escopo, aprovação e segurança.",
    "prime": "Prepara execução permitida, sem autoridade autônoma para efetivá-la.",
    "shadow": "Pesquisa, cruza fontes e prepara evidência para revisão.",
    "sentinel": "Monitora saúde, incidentes, mudanças e confiabilidade.",
    "commercial": "Opera contexto comercial, leads, CRM e valor ao cliente.",
    "educator": "Estrutura treinamento, explicações e material educacional.",
}

_CAPABILITIES = {
    "orchestrator": ("route", "coordinate", "summarize"),
    "architect": ("analyze", "design", "propose"),
    "guardian": ("audit", "block", "review"),
    "prime": ("prepare_guarded_execution", "draft_action_plan"),
    "shadow": ("research", "triage", "cross_check"),
    "sentinel": ("observe", "alert", "incident_triage"),
    "commercial": ("qualify", "draft_followup", "crm_context"),
    "educator": ("explain", "train", "draft_learning_material"),
}

CRITICAL_ACTIONS = (
    "external_execution",
    "critical_approval",
    "memory_promotion",
    "automatic_checkpoint_write",
    "merge_main",
    "deploy_production",
    "spend_money",
    "read_credentials",
    "real_trade",
)


def official_role_authority_matrix() -> dict[str, Any]:
    rows = []
    for role_id in OFFICIAL_ROLE_IDS:
        rows.append({
            "role_id": role_id,
            "role": role_id,
            "purpose": _PURPOSES[role_id],
            "capabilities": list(_CAPABILITIES[role_id]),
            "allowed_inputs": ["scoped_request", "scoped_confirmed_evidence", "task_dependencies"],
            "allowed_outputs": list(_CAPABILITIES[role_id]) + ["local_artifact", "audited_proposal"],
            "forbidden_actions": list(CRITICAL_ACTIONS),
            "requires_approval": ["external_intent", "paid_intent", "scope_change"],
            "escalation_target": "HUMAN_OWNER" if role_id == "guardian" else "guardian",
            "audit_requirements": ["mission_id", "task_id", "scope_digest", "payload_digest", "transition", "approval_digest"],
            "shared_core": True,
            "independent_ai": False,
            "may_read_scoped_context": True,
            "may_propose": True,
            "may_coordinate": role_id == "orchestrator",
            "may_block_for_safety": role_id == "guardian",
            "may_prepare_guarded_execution": role_id == "prime",
            "may_monitor": role_id == "sentinel",
            "may_research": role_id == "shadow",
            "may_manage_commercial_context": role_id == "commercial",
            "may_prepare_training": role_id == "educator",
            "may_approve_critical": False,
            "may_execute_external_without_explicit_approval": False,
            "may_promote_memory_automatically": False,
            "may_write_checkpoint_automatically": False,
            "may_merge_main": False,
            "may_deploy_production": False,
            "may_spend_money": False,
            "may_read_credentials": False,
            "may_enable_real_trade": False,
            "external_action_authority": False,
        })
    return {
        "schema": SCHEMA,
        "count": len(rows),
        "roles": rows,
        "single_shared_aion_core": True,
        "critical_approval_owner": "HUMAN_OWNER",
        "role_cannot_self_approve": True,
        "approval_does_not_equal_execution": True,
        "critical_actions": list(CRITICAL_ACTIONS),
        "external_action_executed": False,
    }


def authority_for_role(role_id: Any) -> dict[str, Any]:
    target = str(role_id or "").strip().casefold()
    for row in official_role_authority_matrix()["roles"]:
        if row["role_id"] == target:
            return dict(row)
    raise ValueError("unknown AION role")


def evaluate_role_authority(
    role_id: Any,
    action_class: Any,
    *,
    explicit_human_approval: bool = False,
) -> dict[str, Any]:
    role = authority_for_role(role_id)
    kind = str(action_class or "").strip().upper()
    if kind not in {"READ_ONLY", "LOW_RISK", "REQUIRES_APPROVAL", "BLOCKED"}:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "ACTION_CLASS_INVALID",
            "role_id": role["role_id"],
            "execution_allowed": False,
            "external_action_executed": False,
        }
    if kind == "BLOCKED":
        status = "BLOCKED"
        reason = "ACTION_CLASS_BLOCKED"
    elif kind == "REQUIRES_APPROVAL" and explicit_human_approval is not True:
        status = "WAITING_HUMAN_APPROVAL"
        reason = "EXPLICIT_HUMAN_APPROVAL_REQUIRED"
    elif kind == "REQUIRES_APPROVAL":
        status = "APPROVAL_PRESENT_EXECUTION_GATE_STILL_REQUIRED"
        reason = "APPROVAL_IS_NOT_EXECUTION_AUTHORITY"
    else:
        status = "PROPOSAL_ALLOWED"
        reason = "ROLE_MAY_PREPARE_ONLY"
    return {
        "schema": SCHEMA,
        "status": status,
        "reason": reason,
        "role_id": role["role_id"],
        "action_class": kind,
        "explicit_human_approval": explicit_human_approval is True,
        "role_may_approve_critical": False,
        "execution_allowed": False,
        "requires_downstream_execution_gate": kind != "BLOCKED",
        "external_action_executed": False,
    }


__all__ = [
    "SCHEMA", "OFFICIAL_ROLE_IDS", "CRITICAL_ACTIONS",
    "official_role_authority_matrix", "authority_for_role",
    "evaluate_role_authority",
]
