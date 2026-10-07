"""AION Ecosystem Learning Hub V1.

Pure/offline registry and learning-policy layer for owner education across
Trader, Negocios, Investimentos and AION. No live execution authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

SCHEMA = "ATLASQUANT_AION_ECOSYSTEM_LEARNING_HUB_V1"

MODES = (
    "PROFESSOR",
    "VISUAL_EXPLAINER",
    "SOCRATIC",
    "GUIDED_PRACTICE",
    "REVIEW",
    "OWNER_ADVISOR",
)

PROGRESS_STATES = (
    "NOT_STARTED",
    "LEARNING",
    "PRACTICE_READY",
    "UNDERSTOOD",
    "REVIEW_DUE",
)

BLOCKED_LIVE_ACTIONS = frozenset({
    "OUTREACH_SEND",
    "TRADE_EXECUTE",
    "MONEY_MOVE",
    "CONTRACT_SIGN",
    "PUBLISH",
    "CRM_PRODUCTION_WRITE",
    "PERMISSION_CHANGE",
    "LIVE_INTEGRATION_ACTIVATE",
})


def _clean(value: Any, limit: int = 120) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


@dataclass(frozen=True)
class DomainRegistration:
    domain_id: str
    topics: tuple[str, ...]
    prerequisites: tuple[str, ...] = ()
    glossary_terms: tuple[str, ...] = ()
    simulation_types: tuple[str, ...] = ()


def normalize_registration(raw: DomainRegistration) -> DomainRegistration:
    domain_id = _clean(raw.domain_id, 80).upper()
    if not domain_id:
        raise ValueError("domain_id required")
    topics = tuple(dict.fromkeys(_clean(x, 120) for x in raw.topics if _clean(x, 120)))
    if not topics:
        raise ValueError("at least one topic required")
    return DomainRegistration(
        domain_id=domain_id,
        topics=topics,
        prerequisites=tuple(dict.fromkeys(_clean(x, 120) for x in raw.prerequisites if _clean(x, 120))),
        glossary_terms=tuple(dict.fromkeys(_clean(x, 120) for x in raw.glossary_terms if _clean(x, 120))),
        simulation_types=tuple(dict.fromkeys(_clean(x, 120) for x in raw.simulation_types if _clean(x, 120))),
    )


def registry_snapshot(registrations: Iterable[DomainRegistration]) -> dict[str, Any]:
    domains: dict[str, dict[str, Any]] = {}
    for raw in registrations:
        item = normalize_registration(raw)
        if item.domain_id in domains:
            raise ValueError("duplicate domain_id")
        domains[item.domain_id] = {
            "topics": list(item.topics),
            "prerequisites": list(item.prerequisites),
            "glossary_terms": list(item.glossary_terms),
            "simulation_types": list(item.simulation_types),
        }
    return {
        "schema": SCHEMA,
        "state": "READY" if domains else "EMPTY",
        "domains": domains,
        "dynamic_registration": True,
        "grants_authority": False,
        "executes_action": False,
    }


def learning_action_policy(*, mode: Any, action: Any) -> dict[str, Any]:
    normalized_mode = _clean(mode, 80).upper()
    normalized_action = _clean(action, 100).upper()
    blockers: list[str] = []

    if normalized_mode not in MODES:
        blockers.append("LEARNING_MODE_INVALID")

    if normalized_action in BLOCKED_LIVE_ACTIONS:
        blockers.append("LIVE_ACTION_BLOCKED_IN_LEARNING_HUB")

    return {
        "schema": SCHEMA,
        "mode": normalized_mode,
        "action": normalized_action,
        "state": "BLOCKED" if blockers else "ALLOWED_BY_LEARNING_POLICY",
        "blockers": blockers,
        "grants_authority": False,
        "executes_action": False,
        "production_mutation": False,
    }


def owner_advisor_result(
    *,
    subject: Any,
    known_facts: list[str] | tuple[str, ...],
    estimates: list[str] | tuple[str, ...] = (),
    unknowns: list[str] | tuple[str, ...] = (),
    recommendation: Any = "",
    reserved_owner_decision: bool = False,
) -> dict[str, Any]:
    facts = [_clean(x, 500) for x in known_facts if _clean(x, 500)]
    est = [_clean(x, 500) for x in estimates if _clean(x, 500)]
    unk = [_clean(x, 500) for x in unknowns if _clean(x, 500)]
    rec = _clean(recommendation, 1200)
    return {
        "schema": SCHEMA,
        "mode": "OWNER_ADVISOR",
        "subject": _clean(subject, 240),
        "known_facts": facts,
        "estimates": est,
        "unknowns": unk,
        "recommendation": rec,
        "reserved_owner_decision": bool(reserved_owner_decision),
        "confidence": "LOW" if unk and not facts else ("MEDIUM" if unk else "HIGH"),
        "decision_executed": False,
        "grants_authority": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "MODES",
    "PROGRESS_STATES",
    "BLOCKED_LIVE_ACTIONS",
    "DomainRegistration",
    "normalize_registration",
    "registry_snapshot",
    "learning_action_policy",
    "owner_advisor_result",
]
