"""Mission-review protocol bridge over the existing AION agent message firewall.

This module does not create a second trust system. It reuses
seal_agent_message()/validate_agent_message() and converts only validated,
scope-bound, fresh, non-replayed review messages into information-only review
rows for adjudicate_critical_task().
"""
from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Callable, Mapping, Sequence

from atlasquant_aion_critical_review import (
    VERDICTS,
    seal_agent_message,
    validate_agent_message,
)


SCHEMA = "ATLASQUANT_AION_AGENT_REVIEW_PROTOCOL_V1"
CONTENT_SCHEMA = "ATLASQUANT_AION_MISSION_REVIEW_CONTENT_V1"
REVIEW_CAPABILITY = "REVIEW"
REVIEW_ACTION = "review_mission"
_CONTENT_FIELDS = frozenset({"schema", "mission_id", "plan_version", "verdict"})


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _upper(value: Any, limit: int = 40) -> str:
    return _clean(value, limit).upper()


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def seal_mission_review_message(
    *,
    verdict: Any,
    mission_id: Any,
    plan_version: Any,
    trusted_context: Mapping[str, Any] | None,
    evidence_refs: Sequence[Any] | None,
    approval_refs: Sequence[Any] | None = None,
    issued_at: Any,
    nonce: Any,
    risk_level: Any = "LOW",
    confidence: Any = "MEDIUM",
) -> dict[str, Any]:
    """Seal one reviewer opinion using the existing closed agent-message schema."""
    content = _canonical({
        "schema": CONTENT_SCHEMA,
        "mission_id": _clean(mission_id, 120),
        "plan_version": _clean(plan_version, 80),
        "verdict": _upper(verdict, 40),
    })
    return seal_agent_message(
        {
            "capability": REVIEW_CAPABILITY,
            "requested_action": REVIEW_ACTION,
            "evidence_refs": list(evidence_refs or []),
            "confidence": confidence,
            "risk_level": risk_level,
            "permissions": [],
            "approval_refs": list(approval_refs or []),
            "issued_at": issued_at,
            "nonce": nonce,
            "content": content,
        },
        trusted_context=trusted_context,
    )


def validate_mission_review_message(
    message: Mapping[str, Any] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
    expected_workspace_id: Any,
    expected_tenant_id: Any,
    expected_mission_id: Any,
    expected_plan_version: Any,
    seen_digests: Sequence[Any] | None = None,
    now: datetime | None = None,
    max_age_seconds: Any = 900,
    evidence_verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None = None,
    approval_verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate one sealed review message and bind it to exactly one mission plan."""
    raw = dict(message or {})
    base = validate_agent_message(
        raw,
        trusted_context=trusted_context,
        expected_workspace_id=expected_workspace_id,
        expected_tenant_id=expected_tenant_id,
        seen_digests=seen_digests,
        now=now,
        max_age_seconds=max_age_seconds,
        evidence_verifier=evidence_verifier,
        approval_verifier=approval_verifier,
    )
    blockers = list(base.get("blockers") or [])

    if _upper(raw.get("capability"), 80) != REVIEW_CAPABILITY:
        blockers.append("REVIEW_CAPABILITY_INVALID")
    if _clean(raw.get("requested_action"), 160) != REVIEW_ACTION:
        blockers.append("REVIEW_ACTION_INVALID")

    parsed: dict[str, Any] = {}
    try:
        candidate = json.loads(str(raw.get("content") or ""))
        if isinstance(candidate, Mapping):
            parsed = dict(candidate)
        else:
            blockers.append("REVIEW_CONTENT_INVALID")
    except (TypeError, ValueError, json.JSONDecodeError):
        blockers.append("REVIEW_CONTENT_INVALID")

    if parsed:
        unknown = sorted(set(parsed) - _CONTENT_FIELDS)
        missing = sorted(_CONTENT_FIELDS - set(parsed))
        if unknown:
            blockers.append("REVIEW_CONTENT_UNKNOWN_FIELD:" + str(unknown[0]))
        if missing:
            blockers.append("REVIEW_CONTENT_MISSING:" + str(missing[0]))
        if parsed.get("schema") != CONTENT_SCHEMA:
            blockers.append("REVIEW_CONTENT_SCHEMA_INVALID")

    mission_id = _clean(parsed.get("mission_id"), 120)
    plan_version = _clean(parsed.get("plan_version"), 80)
    verdict = _upper(parsed.get("verdict"), 40)
    if mission_id != _clean(expected_mission_id, 120):
        blockers.append("REVIEW_MISSION_MISMATCH")
    if plan_version != _clean(expected_plan_version, 80):
        blockers.append("REVIEW_PLAN_MISMATCH")
    if verdict not in VERDICTS:
        blockers.append("REVIEW_VERDICT_INVALID")

    blockers = list(dict.fromkeys(blockers))
    valid = not blockers and base.get("state") == "INFORMATION_ONLY"
    review = None
    if valid:
        review = {
            "role": _upper(raw.get("role"), 40),
            "agent_id": _clean(raw.get("agent_id"), 160),
            "verdict": verdict,
            "tenant_id": _clean(raw.get("tenant_id"), 120),
            "workspace_id": _clean(raw.get("workspace_id"), 120),
            "task_ref": mission_id,
            "plan_version": plan_version,
        }

    return {
        "schema": SCHEMA,
        "state": "INFORMATION_ONLY" if valid else "BLOCK",
        "blockers": blockers,
        "digest": _clean(raw.get("digest"), 80),
        "role": _upper(raw.get("role"), 40),
        "agent_id": _clean(raw.get("agent_id"), 160),
        "review": review,
        "authorization": "NONE",
        "content_is_authority": False,
        "executes_action": False,
        "grants_permission": False,
    }


def validate_mission_review_batch(
    messages: Sequence[Mapping[str, Any]] | None,
    *,
    trusted_reviewer_contexts: Mapping[str, Mapping[str, Any]] | None,
    expected_workspace_id: Any,
    expected_tenant_id: Any,
    expected_mission_id: Any,
    expected_plan_version: Any,
    seen_digests: Sequence[Any] | None = None,
    now: datetime | None = None,
    max_age_seconds: Any = 900,
    evidence_verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None = None,
    approval_verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate a bounded batch and return review rows only for firewall-clean messages."""
    contexts = {
        _upper(role, 40): dict(context)
        for role, context in dict(trusted_reviewer_contexts or {}).items()
        if isinstance(context, Mapping)
    }
    seen = [_clean(item, 80) for item in list(seen_digests or []) if _clean(item, 80)]
    reports: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []

    raw_messages = list(messages or [])
    if len(raw_messages) > 12:
        blockers.append("REVIEW_MESSAGE_LIMIT_EXCEEDED")
        raw_messages = raw_messages[:12]

    for index, raw in enumerate(raw_messages):
        if not isinstance(raw, Mapping):
            blockers.append(f"REVIEW_MESSAGE_INVALID:{index}")
            continue
        role = _upper(raw.get("role"), 40)
        context = contexts.get(role, {})
        report = validate_mission_review_message(
            raw,
            trusted_context=context,
            expected_workspace_id=expected_workspace_id,
            expected_tenant_id=expected_tenant_id,
            expected_mission_id=expected_mission_id,
            expected_plan_version=expected_plan_version,
            seen_digests=seen,
            now=now,
            max_age_seconds=max_age_seconds,
            evidence_verifier=evidence_verifier,
            approval_verifier=approval_verifier,
        )
        reports.append(report)
        if report.get("state") != "INFORMATION_ONLY":
            blockers.extend(
                f"PROTOCOL:{role or index}:{item}"
                for item in list(report.get("blockers") or [])
            )
            continue
        digest = _clean(raw.get("digest"), 80)
        if digest:
            seen.append(digest)
        if isinstance(report.get("review"), Mapping):
            rows.append(dict(report["review"]))

    assignments = {
        role: _clean(context.get("agent_id"), 160)
        for role, context in contexts.items()
        if _clean(context.get("agent_id"), 160)
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": SCHEMA,
        "state": "PASS" if not blockers else "BLOCK",
        "blockers": blockers,
        "reviews": rows,
        "trusted_assignments": assignments,
        "message_reports": reports,
        "authorization": "NONE",
        "executes_action": False,
        "grants_permission": False,
    }


__all__ = [
    "SCHEMA",
    "CONTENT_SCHEMA",
    "REVIEW_CAPABILITY",
    "REVIEW_ACTION",
    "seal_mission_review_message",
    "validate_mission_review_message",
    "validate_mission_review_batch",
]
