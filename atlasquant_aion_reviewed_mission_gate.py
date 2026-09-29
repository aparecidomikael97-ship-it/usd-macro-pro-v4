"""Reviewed mission gate for AION agentic plans.

This bridge binds the existing Capability Planner to the existing Critical
Review contract. It does not call Guardian, providers, tools, connectors or
executors. ACCEPT_PLAN means only that the plan may proceed to the separate
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
)
from atlasquant_aion_agent_review_protocol import validate_mission_review_batch


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


def review_agentic_mission(
    objective: Any,
    *,
    access: Mapping[str, Any] | None,
    trusted_context: Mapping[str, Any] | None,
    review_messages: Sequence[Mapping[str, Any]] | None = None,
    trusted_reviewer_contexts: Mapping[str, Mapping[str, Any]] | None = None,
    seen_message_digests: Sequence[Any] | None = None,
    now: datetime | None = None,
    max_message_age_seconds: Any = 900,
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
    task_class = _BLAST_TO_TASK.get(str(blast.get("level") or ""), "CRITICAL")
    required_roles = list(REQUIRED_ROLES[task_class])
    mission_blocked = str(mission.get("readiness") or "").startswith("BLOCKED")

    if mission_blocked:
        return {
            "schema": SCHEMA,
            "state": "BLOCK",
            "reason": "MISSION_NOT_READY",
            "mission": mission,
            "mission_binding": binding,
            "mission_id": binding["mission_id"],
            "plan_version": plan_version,
            "task_class": task_class,
            "required_roles": required_roles,
            "blast_radius": blast,
            "review": None,
            "review_protocol": None,
            "eligible_for_guardian": False,
            "guardian_called": False,
            "executes_action": False,
            "grants_permission": False,
            "external_action_executed": False,
            "real_trading_enabled": False,
        }

    if not list(review_messages or []):
        return {
            "schema": SCHEMA,
            "state": "REVIEW_REQUIRED",
            "reason": "INDEPENDENT_REVIEW_REQUIRED",
            "mission": mission,
            "mission_binding": binding,
            "mission_id": binding["mission_id"],
            "plan_version": plan_version,
            "task_class": task_class,
            "required_roles": required_roles,
            "blast_radius": blast,
            "review": None,
            "review_protocol": None,
            "eligible_for_guardian": False,
            "guardian_called": False,
            "executes_action": False,
            "grants_permission": False,
            "external_action_executed": False,
            "real_trading_enabled": False,
        }

    sensitive = str(blast.get("level") or "") in {"HIGH", "CRITICAL"}
    protocol = validate_mission_review_batch(
        review_messages,
        trusted_reviewer_contexts=trusted_reviewer_contexts,
        expected_workspace_id=workspace_id,
        expected_tenant_id=tenant_id,
        expected_mission_id=binding["mission_id"],
        expected_plan_version=plan_version,
        seen_digests=seen_message_digests,
        now=now,
        max_age_seconds=max_message_age_seconds,
        evidence_verifier=evidence_verifier,
        approval_verifier=approval_verifier,
    )
    if protocol.get("state") != "PASS":
        return {
            "schema": SCHEMA,
            "state": "BLOCK",
            "reason": "PROTOCOL_FIREWALL_BLOCKED",
            "mission": mission,
            "mission_binding": binding,
            "mission_id": binding["mission_id"],
            "plan_version": plan_version,
            "task_class": task_class,
            "required_roles": required_roles,
            "blast_radius": blast,
            "review": None,
            "review_protocol": protocol,
            "eligible_for_guardian": False,
            "guardian_called": False,
            "executes_action": False,
            "grants_permission": False,
            "external_action_executed": False,
            "real_trading_enabled": False,
        }

    review = adjudicate_critical_task(
        task_class=task_class,
        reviews=protocol.get("reviews"),
        trusted_assignments=protocol.get("trusted_assignments"),
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
        "schema": SCHEMA,
        "state": state,
        "reason": reason,
        "mission": mission,
        "mission_binding": binding,
        "mission_id": binding["mission_id"],
        "plan_version": plan_version,
        "task_class": task_class,
        "required_roles": required_roles,
        "blast_radius": blast,
        "review": review,
        "review_protocol": protocol,
        "eligible_for_guardian": state == "READY_FOR_GUARDIAN",
        "guardian_called": False,
        "executes_action": False,
        "grants_permission": False,
        "external_action_executed": False,
        "real_trading_enabled": False,
    }


__all__ = ["SCHEMA", "review_agentic_mission"]
