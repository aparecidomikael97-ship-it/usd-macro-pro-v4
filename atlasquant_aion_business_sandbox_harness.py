"""Deterministic sandbox harness for AION BUSINESS.

This is not production runtime. It exercises only read/analyze/draft behavior
against caller-supplied fixture data. No provider, network, filesystem write,
external contact, payment, publication, deploy or trading action exists here.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

from atlasquant_aion_business_runtime_readiness import SCHEMA as READINESS_SCHEMA

SCHEMA = "ATLASQUANT_AION_BUSINESS_SANDBOX_HARNESS_V1"
VERSION = "1"
MAX_CASES = 20
ALLOWED_CASES = (
    "FAQ_DRAFT",
    "LEAD_QUALIFICATION",
    "FOLLOWUP_DRAFT",
    "BUSINESS_RADAR",
)
DENIED_ACTIONS = (
    "external_contact",
    "sign_contract",
    "charge",
    "payment",
    "spend",
    "publish",
    "publication",
    "deploy",
    "real_trade",
    "move_money",
)


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _seq(value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return list(value)[:MAX_CASES]


def _digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def create_business_sandbox_session(
    readiness: Mapping[str, Any] | None,
    *,
    tenant_id: Any,
    workspace_id: Any,
    actor_id: Any,
    session_id: Any,
) -> dict[str, Any]:
    row = _mapping(readiness)
    tenant = _clean(tenant_id, 120)
    workspace = _clean(workspace_id, 120)
    actor = _clean(actor_id, 120)
    session = _clean(session_id, 120)
    eligible = bool(
        row.get("schema") == READINESS_SCHEMA
        and row.get("state") == "SANDBOX_READY"
        and row.get("sandbox_ready") is True
        and row.get("runtime_activated") is False
        and row.get("production_runtime_allowed") is False
        and tenant
        and workspace
        and actor
        and session
    )
    identity = {
        "tenant_id": tenant,
        "workspace_id": workspace,
        "actor_id": actor,
        "session_id": session,
    }
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "OPEN" if eligible else "BLOCKED",
        "mode": "SIMULATION_ONLY",
        "identity": identity if eligible else {},
        "session_digest": _digest(identity) if eligible else "",
        "allowed_cases": list(ALLOWED_CASES) if eligible else [],
        "denied_actions": list(DENIED_ACTIONS),
        "provider_called": False,
        "network_called": False,
        "external_write": False,
        "runtime_activated": False,
        "external_action_executed": False,
    }


def _lead_score(data: Mapping[str, Any]) -> dict[str, Any]:
    score = 0
    if _clean(data.get("name"), 120):
        score += 15
    if _clean(data.get("contact"), 160):
        score += 20
    need = _clean(data.get("need"), 400)
    if need:
        score += 25
    budget = data.get("budget_confirmed")
    if budget is True:
        score += 20
    urgency = _clean(data.get("urgency"), 40).lower()
    if urgency in {"high", "alta", "immediate", "imediata"}:
        score += 20
    elif urgency:
        score += 10
    score = min(score, 100)
    band = "HOT" if score >= 75 else "WARM" if score >= 45 else "COLD"
    return {
        "score": score,
        "band": band,
        "recommendation": {
            "HOT": "prioritize_human_review",
            "WARM": "continue_qualification",
            "COLD": "nurture_or_close",
        }[band],
    }


def _faq_draft(data: Mapping[str, Any]) -> dict[str, Any]:
    question = _clean(data.get("question"), 500)
    facts = [_clean(item, 300) for item in _seq(data.get("approved_facts"))]
    facts = [item for item in facts if item]
    if not question or not facts:
        return {
            "state": "INCOMPLETE",
            "answer_draft": "",
            "missing": ["question"] if not question else ["approved_facts"],
        }
    return {
        "state": "DRAFT",
        "answer_draft": " ".join(facts[:5]),
        "question": question,
        "uses_only_approved_facts": True,
    }


def _followup_draft(data: Mapping[str, Any]) -> dict[str, Any]:
    name = _clean(data.get("name"), 120) or "cliente"
    context = _clean(data.get("context"), 500)
    next_step = _clean(data.get("next_step"), 300)
    if not context or not next_step:
        return {
            "state": "INCOMPLETE",
            "draft": "",
            "requires_human_review": True,
        }
    return {
        "state": "DRAFT",
        "draft": f"Olá, {name}. Sobre {context}, o próximo passo sugerido é {next_step}.",
        "requires_human_review": True,
        "sent": False,
    }


def _business_radar(data: Mapping[str, Any]) -> dict[str, Any]:
    leads = data.get("leads_open")
    response_hours = data.get("avg_response_hours")
    abandoned = data.get("abandoned_quotes")
    values = {
        "leads_open": leads if isinstance(leads, int) and not isinstance(leads, bool) and leads >= 0 else None,
        "avg_response_hours": response_hours if isinstance(response_hours, (int, float)) and not isinstance(response_hours, bool) and response_hours >= 0 else None,
        "abandoned_quotes": abandoned if isinstance(abandoned, int) and not isinstance(abandoned, bool) and abandoned >= 0 else None,
    }
    missing = [key for key, value in values.items() if value is None]
    if missing:
        return {"state": "INCOMPLETE", "missing": missing, "alerts": []}
    alerts: list[str] = []
    if values["avg_response_hours"] > 2:
        alerts.append("RESPONSE_TIME_HIGH")
    if values["abandoned_quotes"] > 0:
        alerts.append("ABANDONED_QUOTES_PRESENT")
    if values["leads_open"] > 30:
        alerts.append("LEAD_BACKLOG_HIGH")
    return {
        "state": "ANALYZED",
        "metrics": values,
        "alerts": alerts,
        "simple_summary": "attention_required" if alerts else "stable",
    }


def run_business_sandbox_case(
    session: Mapping[str, Any] | None,
    *,
    case_type: Any,
    data: Mapping[str, Any] | None,
    requested_action: Any = "",
) -> dict[str, Any]:
    row = _mapping(session)
    case = _clean(case_type, 80).upper()
    action = _clean(requested_action, 80).lower()
    if (
        row.get("schema") != SCHEMA
        or row.get("state") != "OPEN"
        or row.get("mode") != "SIMULATION_ONLY"
        or row.get("runtime_activated") is not False
    ):
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "reason": "SESSION_NOT_OPEN",
            "runtime_activated": False,
            "external_action_executed": False,
        }
    if action and action in set(DENIED_ACTIONS):
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "reason": "ACTION_DENIED",
            "requested_action": action,
            "runtime_activated": False,
            "external_action_executed": False,
        }
    if case not in ALLOWED_CASES:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "reason": "CASE_NOT_ALLOWED",
            "runtime_activated": False,
            "external_action_executed": False,
        }

    payload = _mapping(data)
    if case == "FAQ_DRAFT":
        result = _faq_draft(payload)
    elif case == "LEAD_QUALIFICATION":
        result = {"state": "ANALYZED", **_lead_score(payload)}
    elif case == "FOLLOWUP_DRAFT":
        result = _followup_draft(payload)
    else:
        result = _business_radar(payload)

    envelope = {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "COMPLETED",
        "case_type": case,
        "session_digest": _clean(row.get("session_digest"), 128),
        "result": result,
        "provider_called": False,
        "network_called": False,
        "external_write": False,
        "runtime_activated": False,
        "external_action_executed": False,
        "payment_executed": False,
        "publication_executed": False,
        "deploy_executed": False,
        "real_trading_enabled": False,
    }
    envelope["result_digest"] = _digest({
        "case_type": case,
        "session_digest": envelope["session_digest"],
        "result": result,
    })
    return envelope


def sandbox_batch(
    session: Mapping[str, Any] | None,
    cases: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    items = _seq(cases)
    overflow = isinstance(cases, Sequence) and not isinstance(cases, (str, bytes, bytearray)) and len(cases) > MAX_CASES
    if overflow:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "reason": "CASE_LIMIT_EXCEEDED",
            "count": 0,
            "results": [],
            "runtime_activated": False,
            "external_action_executed": False,
        }
    results = []
    for item in items:
        row = _mapping(item)
        results.append(run_business_sandbox_case(
            session,
            case_type=row.get("case_type"),
            data=_mapping(row.get("data")),
            requested_action=row.get("requested_action", ""),
        ))
    return {
        "schema": SCHEMA,
        "state": "COMPLETED" if all(item.get("state") == "COMPLETED" for item in results) else "PARTIAL_OR_BLOCKED",
        "count": len(results),
        "results": results,
        "runtime_activated": False,
        "external_action_executed": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "MAX_CASES",
    "ALLOWED_CASES",
    "DENIED_ACTIONS",
    "create_business_sandbox_session",
    "run_business_sandbox_case",
    "sandbox_batch",
]
