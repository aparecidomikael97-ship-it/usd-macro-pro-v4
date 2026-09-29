"""Reviewed mission gate for AION agentic plans.

This bridge binds the Capability Planner to Critical Review and, for
IMPORTANT/CRITICAL missions, the existing agent-message protocol firewall.
It never calls Guardian, providers, tools, connectors or executors.
READY_FOR_GUARDIAN means only that the plan may proceed to the separate
Guardian/safety layer.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Mapping, Sequence
import unicodedata

from atlasquant_aion_capability_planner import plan_agentic_mission
from atlasquant_aion_critical_review import (
    REQUIRED_ROLES,
    adjudicate_critical_task,
    canonical_fingerprint,
    classify_blast_radius,
    validate_agent_message,
)


SCHEMA = "ATLASQUANT_AION_REVIEWED_MISSION_GATE_V1"
_BLAST_TO_TASK = {
    "LOW": "SIMPLE",
    "MEDIUM": "IMPORTANT",
    "HIGH": "CRITICAL",
    "CRITICAL": "CRITICAL",
}
_DERIVED_FACTORS = {
    "production_deploy": ("production", ("deploy", "producao", "render", "publicar sistema")),
    "real_trade": ("financial", ("trade real", "ordem real", "corretora", "execucao real")),
    "social_publish": ("external_publication", ("publicar", "postar", "instagram", "youtube", "tiktok")),
    "marketplace_publish": ("external_publication", ("marketplace", "mercado livre", "tiktok shop", "anuncio")),
    "checkpoint_write": ("code_change", ("salvar checkpoint", "persistir checkpoint", "gravar checkpoint")),
    "code_change_plan": ("code_change", ("codigo", "bug", "erro", "interface", "github", "implementar", "desenvolver", "ajustar")),
}


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _fold(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()


def _mission_binding(mission: Mapping[str, Any]) -> dict[str, Any]:
    stages = []
    for raw in list(mission.get("stages") or []):
        if not isinstance(raw, Mapping):
            continue
        stages.append({
            "order": raw.get("order"),
            "capability_id": _clean(raw.get("capability_id"), 120),
            "state": _clean(raw.get("state"), 80),
            "reason": _clean(raw.get("reason"), 240),
            "requires_explicit_approval": raw.get("requires_explicit_approval") is True,
        })
    return {
        "schema": _clean(mission.get("schema"), 120),
        "mission_id": _clean(mission.get("mission_id"), 120),
        "objective": _clean(mission.get("objective"), 1400),
        "domain": _clean(mission.get("domain"), 120),
        "readiness": _clean(mission.get("readiness"), 120),
        "stages": stages,
    }


def _protocol_gate(
    *,
    task_class: str,
    required_roles: Sequence[str],
    review_messages: Mapping[str, Mapping[str, Any]] | None,
    trusted_message_contexts: Mapping[str, Mapping[str, Any]] | None,
    trusted_assignments: Mapping[str, Any] | None,
    workspace_id: str,
    tenant_id: str,
    mission_id: str,
    plan_version: str,
    blast_level: str,
    seen_message_digests: Sequence[Any] | None,
    now: datetime | None,
    message_max_age_seconds: Any,
    evidence_verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None,
    approval_verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None,
) -> dict[str, Any]:
    if task_class not in {"IMPORTANT", "CRITICAL"}:
        return {
            "state": "NOT_REQUIRED",
            "required_roles": [],
            "expected_requested_action": "",
            "messages": [],
            "blockers": [],
            "authorization": "NONE",
            "executes_action": False,
            "grants_permission": False,
        }

    messages = {
        _clean(role, 40).upper(): dict(message)
        for role, message in dict(review_messages or {}).items()
        if isinstance(message, Mapping)
    }
    contexts = {
        _clean(role, 40).upper(): dict(context)
        for role, context in dict(trusted_message_contexts or {}).items()
        if isinstance(context, Mapping)
    }
    assignments = {
        _clean(role, 40).upper(): _clean(agent, 160)
        for role, agent in dict(trusted_assignments or {}).items()
    }
    expected_action = f"review_mission:{mission_id}:{plan_version}"
    seen = [_clean(item, 80) for item in list(seen_message_digests or []) if _clean(item, 80)]
    blockers: list[str] = []
    rows: list[dict[str, Any]] = []

    for role in required_roles:
        message = messages.get(role)
        context = contexts.get(role)
        if message is None:
            blockers.append(f"PROTOCOL_MESSAGE_MISSING:{role}")
            continue
        if context is None:
            blockers.append(f"PROTOCOL_TRUSTED_CONTEXT_MISSING:{role}")
            continue
        expected_agent = assignments.get(role, "")
        if (
            _clean(context.get("role"), 40).upper() != role
            or not expected_agent
            or _clean(context.get("agent_id"), 160) != expected_agent
            or _clean(context.get("workspace_id"), 120) != workspace_id
            or _clean(context.get("tenant_id"), 120) != tenant_id
        ):
            blockers.append(f"PROTOCOL_TRUSTED_CONTEXT_MISMATCH:{role}")
            continue

        checked = validate_agent_message(
            message,
            trusted_context=context,
            expected_workspace_id=workspace_id,
            expected_tenant_id=tenant_id,
            seen_digests=seen,
            now=now,
            max_age_seconds=message_max_age_seconds,
            evidence_verifier=evidence_verifier,
            approval_verifier=approval_verifier,
        )
        row_blockers = [str(item) for item in list(checked.get("blockers") or [])]
        if _clean(message.get("requested_action"), 240) != expected_action:
            row_blockers.append("MISSION_BINDING_MISMATCH")
        if _clean(message.get("risk_level"), 40).upper() != blast_level:
            row_blockers.append("RISK_LEVEL_MISMATCH")
        row_blockers = list(dict.fromkeys(row_blockers))
        if checked.get("state") != "INFORMATION_ONLY" or row_blockers:
            for item in row_blockers or ["MESSAGE_PROTOCOL_BLOCKED"]:
                blockers.append(f"PROTOCOL:{role}:{item}")
        digest = _clean(message.get("digest"), 80)
        if digest:
            seen.append(digest)
        rows.append({
            "role": role,
            "state": "BLOCK" if row_blockers else "INFORMATION_ONLY",
            "digest_ok": checked.get("digest_ok") is True,
            "evidence_status": checked.get("evidence_status"),
            "approval_status": checked.get("approval_status"),
            "blockers": row_blockers,
            "authorization": "NONE",
            "executes_action": False,
            "grants_permission": False,
        })

    blockers = list(dict.fromkeys(blockers))
    return {
        "state": "BLOCK" if blockers else "PASS",
        "required_roles": list(required_roles),
        "expected_requested_action": expected_action,
        "messages": rows,
        "blockers": blockers,
        "authorization": "NONE",
        "executes_action": False,
        "grants_permission": False,
    }


def review_agentic_mission(
    objective: Any,
    *,
    access: Mapping[str, Any] | None,
    trusted_context: Mapping[str, Any] | None,
    reviews: Sequence[Mapping[str, Any]] | None = None,
    trusted_assignments: Mapping[str, Any] | None = None,
    review_messages: Mapping[str, Mapping[str, Any]] | None = None,
    trusted_message_contexts: Mapping[str, Mapping[str, Any]] | None = None,
    seen_message_digests: Sequence[Any] | None = None,
    now: datetime | None = None,
    message_max_age_seconds: Any = 900,
    evidence_refs: Sequence[Any] | None = None,
    approval_refs: Sequence[Any] | None = None,
    evidence_verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None = None,
    approval_verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None = None,
    feature_flags: Mapping[str, Any] | None = None,
    system_context: Mapping[str, Any] | None = None,
    blast_factors: Mapping[str, Any] | None = None,
    user_count: Any = 1,
    estimated_cost: Any = 0,
) -> dict[str, Any]:
    """Plan one mission and require the matching independent review quorum."""
    trusted = dict(trusted_context or {})
    tenant_id = _clean(trusted.get("tenant_id"), 120)
    workspace_id = _clean(trusted.get("workspace_id"), 120)
    mission = plan_agentic_mission(
        objective,
        access=access,
        feature_flags=feature_flags,
        system_context=system_context,
    )
    binding = _mission_binding(mission)
    plan_version = canonical_fingerprint(binding)[:24]

    factors = dict(blast_factors or {})
    selected_ids = {
        _clean(row.get("capability_id"), 120)
        for row in list(mission.get("stages") or [])
        if isinstance(row, Mapping)
    }
    objective_norm = _fold(objective)
    for capability_id, (factor, terms) in _DERIVED_FACTORS.items():
        if capability_id in selected_ids and any(term in objective_norm for term in terms):
            factors[factor] = True

    blast = classify_blast_radius(
        action_name="agentic_mission",
        factors=factors,
        user_count=user_count,
        estimated_cost=estimated_cost,
    )
    blast_level = str(blast.get("level") or "CRITICAL")
    task_class = _BLAST_TO_TASK.get(blast_level, "CRITICAL")
    required_roles = list(REQUIRED_ROLES[task_class])
    mission_blocked = str(mission.get("readiness") or "").startswith("BLOCKED")

    base = {
        "schema": SCHEMA,
        "mission": mission,
        "mission_binding": binding,
        "mission_id": binding["mission_id"],
        "plan_version": plan_version,
        "task_class": task_class,
        "required_roles": required_roles,
        "blast_radius": blast,
        "eligible_for_guardian": False,
        "guardian_called": False,
        "executes_action": False,
        "grants_permission": False,
        "external_action_executed": False,
        "real_trading_enabled": False,
    }

    if mission_blocked:
        return {
            **base,
            "state": "BLOCK",
            "reason": "MISSION_NOT_READY",
            "protocol": None,
            "review": None,
        }

    if not list(reviews or []):
        return {
            **base,
            "state": "REVIEW_REQUIRED",
            "reason": "INDEPENDENT_REVIEW_REQUIRED",
            "protocol": None,
            "review": None,
        }

    protocol = _protocol_gate(
        task_class=task_class,
        required_roles=required_roles,
        review_messages=review_messages,
        trusted_message_contexts=trusted_message_contexts,
        trusted_assignments=trusted_assignments,
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        mission_id=binding["mission_id"],
        plan_version=plan_version,
        blast_level=blast_level,
        seen_message_digests=seen_message_digests,
        now=now,
        message_max_age_seconds=message_max_age_seconds,
        evidence_verifier=evidence_verifier,
        approval_verifier=approval_verifier,
    )
    if protocol.get("state") == "BLOCK":
        return {
            **base,
            "state": "BLOCK",
            "reason": "AGENT_PROTOCOL_BLOCKED",
            "protocol": protocol,
            "review": None,
        }

    sensitive = blast_level in {"HIGH", "CRITICAL"}
    review = adjudicate_critical_task(
        task_class=task_class,
        reviews=reviews,
        trusted_assignments=trusted_assignments,
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        evidence_refs=evidence_refs,
        sensitive=sensitive,
        approval_refs=approval_refs,
        task_ref=binding["mission_id"],
        plan_version=plan_version,
        evidence_verifier=evidence_verifier,
        approval_verifier=approval_verifier,
    )
    if review.get("state") == "ACCEPT_PLAN":
        state = "READY_FOR_GUARDIAN"
        reason = "INDEPENDENT_REVIEW_ACCEPTED"
    elif review.get("state") == "ESCALATE":
        state = "ESCALATE"
        reason = "REVIEW_DIVERGENCE"
    else:
        state = "BLOCK"
        reason = "REVIEW_BLOCKED"

    return {
        **base,
        "state": state,
        "reason": reason,
        "protocol": protocol,
        "review": review,
        "eligible_for_guardian": state == "READY_FOR_GUARDIAN",
    }


__all__ = ["SCHEMA", "review_agentic_mission"]
