"""Central, non-executing orchestration pipeline for AION.

The orchestrator composes the existing Guardian, capability metadata and truth
layer. It plans selectively; it never calls providers, tools or external
systems by itself.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

from atlasquant_aion_capabilities import (
    SPECIALIST_FEATURE_FLAGS,
    CapabilityRegistry,
    capability_feature_flags,
    default_registry,
)
from atlasquant_aion_core import cost_guard, guardian_decision
from atlasquant_aion_truth import assess_truth
from atlasquant_aion_reviewed_mission_gate import review_agentic_mission

SCHEMA = "ATLASQUANT_AION_ORCHESTRATOR_V1"


def _clean(value: Any, limit: int = 1600) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _stable_id(prefix: str, payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return prefix + "-" + sha256(raw.encode("utf-8")).hexdigest()[:14].upper()


@dataclass(frozen=True)
class AionContext:
    role: str = "USER"
    persona: str = "core"
    experience_mode: str = "BEGINNER"
    session_id: str = ""
    request_id: str = ""
    domain_hint: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AionTask:
    task_id: str
    request: str
    intent: str
    domain: str
    capability_id: str
    status: str = "PLANNED"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_context(raw: AionContext | Mapping[str, Any] | None) -> AionContext:
    item = raw.as_dict() if isinstance(raw, AionContext) else dict(raw or {})
    role = str(item.get("role") or "USER").upper()
    if role not in {"USER", "SALES", "ADMIN"}:
        role = "USER"
    mode = str(item.get("experience_mode") or "BEGINNER").upper()
    if mode not in {"BEGINNER", "ADVANCED"}:
        mode = "BEGINNER"
    return AionContext(
        role=role,
        persona=_clean(item.get("persona") or "core", 64).lower(),
        experience_mode=mode,
        session_id=_clean(item.get("session_id"), 120),
        request_id=_clean(item.get("request_id"), 120),
        domain_hint=_clean(item.get("domain_hint"), 80).lower(),
    )


def classify_risk(
    *,
    capability: Mapping[str, Any] | None,
    requested_action: Any = "read",
) -> dict[str, Any]:
    item = dict(capability or {})
    declared = str(item.get("risk") or "CRITICAL").upper()
    action = str(requested_action or "read").lower()
    if action in {"real_trade", "charge_customer", "deploy_production", "merge_main", "read_secret", "write_secret"}:
        level = "CRITICAL"
    elif action.startswith("publish") or bool(item.get("requires_confirmation")):
        level = "HIGH"
    elif str(item.get("execution_mode") or "").upper() in {"SANDBOX", "EXTERNAL"}:
        level = "MEDIUM"
    else:
        level = declared if declared in {"LOW", "MEDIUM", "HIGH", "CRITICAL"} else "CRITICAL"
    return {
        "level": level,
        "impact": "CRITICAL" if level == "CRITICAL" else "HIGH" if level == "HIGH" else "LIMITED",
        "reversible": str(item.get("execution_mode") or "READ_ONLY").upper() in {"READ_ONLY", "DRAFT_ONLY", "SANDBOX"},
        "money": action in {"real_trade", "charge_customer"},
        "credentials": action in {"read_secret", "write_secret"},
        "publication": action.startswith("publish"),
        "production": action in {"deploy_production", "merge_main"},
    }


def _permission_decision(capability: Mapping[str, Any], role: str) -> dict[str, Any]:
    roles = {str(x).upper() for x in list(capability.get("allowed_roles") or [])}
    allowed = role in roles
    return {
        "allowed": allowed,
        "role": role,
        "allowed_roles": sorted(roles),
        "reason": "ROLE_ALLOWED" if allowed else "ROLE_DENIED",
        "backend_enforced": True,
    }


def _presentation(result: Mapping[str, Any], mode: str) -> dict[str, Any]:
    truth = dict(result.get("truth") or {})
    selected = dict(result.get("selected_capability") or {})
    decision = dict(result.get("decision") or {})
    if mode == "BEGINNER":
        return {
            "mode": mode,
            "headline": (
                "AION pode preparar esta tarefa com segurança."
                if decision.get("state") == "READY"
                else "AION precisa de dados, permissão ou confirmação antes de continuar."
            ),
            "essential": [
                f"Área: {selected.get('specialist', 'core')}",
                f"Confiança: {(truth.get('confidence') or {}).get('label', 'NONE')}",
                f"Estado: {decision.get('state', 'BLOCKED')}",
            ],
            "technical_details_hidden": True,
        }
    return {
        "mode": mode,
        "headline": "Plano técnico do AION",
        "capability": selected,
        "truth": truth,
        "risk": result.get("risk"),
        "decision": decision,
        "technical_details_hidden": False,
    }


def prepare_reviewed_mission(
    objective: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    """Plan a mission and require independent review before Guardian eligibility."""
    return review_agentic_mission(objective, **kwargs)


def orchestrate(
    request: Any,
    *,
    context: AionContext | Mapping[str, Any] | None = None,
    evidence: Sequence[Mapping[str, Any]] | None = None,
    registry: CapabilityRegistry | None = None,
    requested_capability: Any = "",
    requested_action: Any = "read",
    approved: bool = False,
    feature_flags: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    ctx = normalize_context(context)
    text = _clean(request)
    reg = registry or default_registry()
    requested_key = str(requested_capability or "").strip()
    explicit = reg.get(requested_key) if requested_key else None
    routed = reg.route(text, domain_hint=ctx.domain_hint, limit=3)
    selected = (
        explicit.as_dict()
        if explicit
        else {}
        if requested_key
        else (dict(routed[0]) if routed else {})
    )
    capability_id = str(selected.get("capability_id") or "unknown")
    domain = str((selected.get("domains") or ["central"])[0])
    task_id = _stable_id("TASK", {"request": text, "context": ctx.as_dict(), "capability": capability_id})
    task = AionTask(
        task_id=task_id,
        request=text,
        intent=capability_id,
        domain=domain,
        capability_id=capability_id,
    ).as_dict()
    truth = assess_truth(evidence)
    permission = _permission_decision(selected, ctx.role) if selected else {
        "allowed": False, "role": ctx.role, "allowed_roles": [], "reason": "CAPABILITY_NOT_FOUND", "backend_enforced": True,
    }
    availability = str(selected.get("availability") or "UNAVAILABLE")
    capability_flags = capability_feature_flags(feature_flags)
    specialist_flag = SPECIALIST_FEATURE_FLAGS.get(str(selected.get("specialist") or ""))
    risk = classify_risk(capability=selected, requested_action=requested_action)
    guardian_action = str(requested_action or selected.get("guardian_action") or "read").lower()
    guardian = guardian_decision(
        guardian_action,
        {"role": ctx.role},
        approved=approved,
        feature_flags=feature_flags,
    )
    cost = cost_guard(selected.get("estimated_cost_usd", 0.0), approved=approved)

    blockers: list[str] = []
    if not selected:
        blockers.append("INVALID_CAPABILITY")
    if not permission["allowed"]:
        blockers.append("PERMISSION_DENIED")
    if availability not in {"AVAILABLE", "DEGRADED"}:
        blockers.append("CAPABILITY_UNAVAILABLE")
    if not capability_flags["AION_CORE_ENABLED"]:
        blockers.append("AION_CORE_DISABLED")
    if specialist_flag and not capability_flags.get(specialist_flag, False):
        blockers.append("CAPABILITY_FLAG_DISABLED")
    if not cost["allowed"]:
        blockers.append("COST_NOT_APPROVED")
    if risk["level"] in {"HIGH", "CRITICAL"} and not approved:
        blockers.append("EXPLICIT_APPROVAL_REQUIRED")
    if guardian_action != "read" and not guardian["allowed"]:
        blockers.append("GUARDIAN_DENIED")
    if guardian_action == "real_trade":
        blockers.append("REAL_TRADING_BLOCKED")
    blockers = list(dict.fromkeys(blockers))

    if blockers:
        state = "BLOCKED"
    elif availability == "DEGRADED" or truth["conflict_state"] == "CONFLICT":
        state = "REVIEW"
    else:
        state = "READY"
    plan_steps = [
        {"stage": "UNDERSTAND", "status": "READY", "executes_action": False},
        {"stage": "RETRIEVE_MEMORY", "status": "PLANNED", "executes_action": False},
        {"stage": "GATHER_EVIDENCE", "status": "PLANNED", "executes_action": False},
        {"stage": "SPECIALIST", "status": "PLANNED", "executes_action": False},
        {"stage": "CRITIC", "status": "REQUIRED", "executes_action": False},
        {"stage": "VALIDATE", "status": "REQUIRED", "executes_action": False},
        {"stage": "TRUTH_SAFETY_GATE", "status": state, "executes_action": False},
    ]
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "context": ctx.as_dict(),
        "task": task,
        "route_candidates": routed,
        "selected_capability": selected,
        "plan": {"steps": plan_steps, "selective": True, "all_agents_called": False},
        "truth": truth,
        "risk": risk,
        "permission": permission,
        "guardian": guardian,
        "feature_flags": capability_flags,
        "cost_guard": cost,
        "decision": {
            "state": state,
            "blockers": blockers,
            "requires_human_confirmation": bool(
                selected.get("requires_confirmation") or risk["level"] in {"HIGH", "CRITICAL"}
            ),
            "may_execute": False,
            "reason": "Preflight only; downstream execution is outside this orchestrator.",
        },
        "specialist_result": None,
        "validator_required": True,
        "critic_required": True,
        "memory_write_automatic": False,
        "learning_signal_automatic": False,
        "external_action_executed": False,
        "real_orders_enabled": False,
    }
    result["presentation"] = _presentation(result, ctx.experience_mode)
    return result


_EXTERNAL_ACTION_MARKERS = (
    "ordem real executada",
    "ordem real enviada",
    "real trade executed",
    "executed a real trade",
    "deploy em produção realizado",
    "deploy em producao realizado",
    "deployed to production",
    "cobrança efetuada",
    "cobranca efetuada",
    "charged the customer",
    "publiquei em produção",
    "publiquei em producao",
)
_ACTION_CLAIM_NAMES = ("real_trade", "deploy_production", "external_action", "charge_customer")
_DENIED_ACTION_VALUES = {
    "", "false", "0", "denied", "blocked", "não", "nao", "none", "null", "no",
}


def _text_asserts_external_action(value: Any) -> bool:
    folded = " ".join(str(value or "").casefold().split())
    return any(marker in folded for marker in _EXTERNAL_ACTION_MARKERS)


def _mapping_asserts_external_action(item: Mapping[str, Any]) -> bool:
    claim = " ".join(str(item.get("claim") or "").casefold().replace("-", " ").split())
    claim_token = claim.replace(" ", "_")
    named = any(name in claim_token for name in _ACTION_CLAIM_NAMES)
    value = item.get("value", item.get("excerpt", item.get("content")))
    if isinstance(value, bool):
        affirmed = value is True
    else:
        text = " ".join(str(value or "").casefold().split())
        affirmed = text not in _DENIED_ACTION_VALUES
    if named and affirmed:
        return True
    for key in ("value", "excerpt", "content", "claim", "response"):
        if isinstance(item.get(key), str) and _text_asserts_external_action(item.get(key)):
            return True
    return False


def classify_external_action_claim(answer: Any, evidence: Any = None) -> str:
    """Return ASSERTED, NOT_ASSERTED, or UNKNOWN.

    Classification never authorizes an external action. An unscannable answer
    stays UNKNOWN instead of being reported as a verified absence.
    """
    asserted = False
    answer_known = isinstance(answer, str) or answer is None
    if isinstance(answer, str) and _text_asserts_external_action(answer):
        asserted = True
    if isinstance(evidence, (list, tuple)):
        for item in list(evidence):
            if isinstance(item, str) and _text_asserts_external_action(item):
                asserted = True
            elif isinstance(item, Mapping) and _mapping_asserts_external_action(item):
                asserted = True
    elif evidence is not None:
        answer_known = False
    if asserted:
        return "ASSERTED"
    if not answer_known:
        return "UNKNOWN"
    return "NOT_ASSERTED"


def validation_truth_status(validation: Mapping[str, Any] | None) -> str:
    """Read the truth contract. `truth.status` is authoritative."""
    payload = validation if isinstance(validation, Mapping) else {}
    truth = payload.get("truth") if isinstance(payload.get("truth"), Mapping) else {}
    status = truth.get("status")
    if status not in (None, ""):
        return str(status)
    legacy = payload.get("truth_state")
    return str(legacy or "UNKNOWN")


def present_validated_answer(
    validation: Mapping[str, Any] | None,
    *,
    answer: Any = "",
) -> dict[str, Any]:
    """Decide what may be shown. Only PASS is a validated answer."""
    payload = validation if isinstance(validation, Mapping) else {}
    state = str(payload.get("state") or "REVISE")
    truth_status = validation_truth_status(payload)
    issues = [str(item) for item in list(payload.get("issues") or [])]
    if state == "PASS":
        body = payload.get("response")
        if body in (None, ""):
            body = answer
        return {
            "display": "ANSWER",
            "state": "PASS",
            "truth_status": truth_status,
            "text": str(body or ""),
            "notice": "",
            "issues": issues,
            "validated": True,
            "executes_action": False,
            "real_orders_enabled": False,
        }
    if state == "BLOCK":
        return {
            "display": "BLOCK",
            "state": "BLOCK",
            "truth_status": truth_status,
            "text": "",
            "notice": "Resposta bloqueada. O conteúdo não é apresentado como resposta válida.",
            "issues": issues,
            "validated": False,
            "executes_action": False,
            "real_orders_enabled": False,
        }
    return {
        "display": "REVISE",
        "state": "REVISE",
        "truth_status": truth_status,
        "text": "",
        "notice": "Revisão necessária. O conteúdo não é apresentado como resposta validada.",
        "issues": issues,
        "validated": False,
        "executes_action": False,
        "real_orders_enabled": False,
    }


def validate_specialist_result(
    orchestration: Mapping[str, Any],
    specialist_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    base = dict(orchestration or {})
    result = dict(specialist_result or {})
    evidence = result.get("evidence") if isinstance(result.get("evidence"), (list, tuple)) else []
    truth = assess_truth(evidence)
    scanned = classify_external_action_claim(result.get("response"), evidence)
    supplied = str(result.get("external_action_claim_state") or "").upper()
    if result.get("claims_external_action") is True:
        supplied = "ASSERTED"
    if scanned == "ASSERTED" or supplied == "ASSERTED":
        claim_state = "ASSERTED"
    elif scanned == "UNKNOWN" or supplied == "UNKNOWN":
        claim_state = "UNKNOWN"
    else:
        claim_state = "NOT_ASSERTED"
    issues: list[str] = []
    if not result:
        issues.append("SPECIALIST_RESULT_MISSING")
    if truth["status"] == "UNKNOWN":
        issues.append("RESULT_WITHOUT_CONFIRMED_EVIDENCE")
    if truth["conflict_state"] == "CONFLICT":
        issues.append("SOURCE_CONFLICT")
    if claim_state == "ASSERTED" and not result.get("action_evidence"):
        issues.append("ACTION_CLAIM_WITHOUT_EVIDENCE")
    elif claim_state == "UNKNOWN":
        issues.append("EXTERNAL_ACTION_CLAIM_UNVERIFIED")
    return {
        "schema": SCHEMA,
        "task_id": str((base.get("task") or {}).get("task_id") or ""),
        "state": "PASS" if not issues else "BLOCK" if "ACTION_CLAIM_WITHOUT_EVIDENCE" in issues else "REVISE",
        "issues": issues,
        "truth": truth,
        "response": _clean(result.get("response"), 4000),
        "external_action_claim_state": claim_state,
        "claims_external_action": True if claim_state == "ASSERTED" else False if claim_state == "NOT_ASSERTED" else None,
        "private_chain_of_thought_exposed": False,
        "executes_action": False,
        "real_orders_enabled": False,
    }


def build_aion_result(
    orchestration: Mapping[str, Any],
    *,
    answer: Any,
    evidence: Sequence[Mapping[str, Any]] | None = None,
    provider_state: Any = "LOCAL_DETERMINISTIC",
) -> dict[str, Any]:
    """Build one result envelope for local or external response paths."""
    normalized_evidence = []
    for index, raw in enumerate(list(evidence or [])[:100]):
        if not isinstance(raw, Mapping):
            continue
        record = {
            "claim": raw.get("claim") or raw.get("title") or raw.get("path") or f"evidence_{index + 1}",
            "value": raw.get("value", raw.get("excerpt", raw.get("content"))),
            "truth_state": raw.get("truth_state") or raw.get("kind") or "UNKNOWN",
            "source": raw.get("source") or raw.get("path") or "",
            "source_ref": raw.get("source_ref") or raw.get("path") or "",
            "source_tier": raw.get("source_tier") or "UNKNOWN",
            "timestamp": raw.get("timestamp") or raw.get("updated_at") or "",
            "ttl_seconds": raw.get("ttl_seconds"),
        }
        if "time_sensitive" in raw:
            record["time_sensitive"] = bool(raw.get("time_sensitive"))
        normalized_evidence.append(record)
    claim_state = classify_external_action_claim(answer, list(evidence or []))
    validation = validate_specialist_result(orchestration, {
        "response": answer,
        "evidence": normalized_evidence,
        "external_action_claim_state": claim_state,
    })
    task = dict(orchestration.get("task") or {})
    return {
        "schema": "ATLASQUANT_AION_RESULT_V1",
        "request_id": str((orchestration.get("context") or {}).get("request_id") or ""),
        "task_id": str(task.get("task_id") or ""),
        "domain": str(task.get("domain") or "central"),
        "capability_id": str(task.get("capability_id") or "unknown"),
        "answer": _clean(answer, 8000),
        "provider_state": _clean(provider_state, 80),
        "validation": validation,
        "truth": validation["truth"],
        "status": validation["state"],
        "external_action_claim_state": validation["external_action_claim_state"],
        "claims_external_action": validation["claims_external_action"],
        "answer_presentation": present_validated_answer(validation, answer=answer),
        "evidence_count": len(normalized_evidence),
        "private_chain_of_thought_exposed": False,
        "external_action_executed": False,
        "automatic_memory_write": False,
        "automatic_learning_change": False,
        "real_orders_enabled": False,
    }


__all__ = [
    "SCHEMA", "AionContext", "AionTask", "normalize_context", "classify_risk",
    "orchestrate", "prepare_reviewed_mission", "validate_specialist_result", "build_aion_result",
    "classify_external_action_claim", "validation_truth_status", "present_validated_answer",
]
