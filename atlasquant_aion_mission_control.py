"""AION Mission Control V1.

Read-only projection over existing AION health, FinOps, confidence, readiness,
incident and durable-task sources. It creates no second source of truth, never
mutates the inputs and never authorizes execution.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json

SCHEMA = "ATLASQUANT_AION_MISSION_CONTROL_V1"

HEALTH_SCHEMA = "ATLASQUANT_AION_SYSTEM_HEALTH_CENTER_V1"
FINOPS_SCHEMA = "ATLASQUANT_AION_FINOPS_METERING_V1"
CONFIDENCE_SCHEMA = "ATLASQUANT_AION_RELEASE_CONFIDENCE_V1"
READINESS_SCHEMA = "ATLASQUANT_AION_POST_HARDENING_READINESS_V2"
INCIDENT_SCHEMA = "ATLASQUANT_AION_INCIDENT_CENTER_V1"
TASK_SCHEMA = "ATLASQUANT_AION_DURABLE_TASK_REPOSITORY_V1"

_TASK_STATES = (
    "PLANNED", "RUNNING", "PAUSED", "WAITING_APPROVAL",
    "BLOCKED", "DONE", "CANCELED",
)


def _text(value: Any, limit: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    item = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(item.get("owner_id") or item.get("actor_id"), 120),
        "tenant_id": _text(item.get("tenant_id"), 120),
        "workspace_id": _text(item.get("workspace_id"), 120),
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
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _false(value: Any) -> bool:
    return value is False


def _health_view(raw: Mapping[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    item = dict(raw) if isinstance(raw, Mapping) else {}
    blockers: list[str] = []
    if item.get("schema") != HEALTH_SCHEMA:
        blockers.append("HEALTH_SCHEMA_INVALID")
    state = _text(item.get("state"), 40).upper()
    if state not in {"HEALTHY", "DEGRADED", "BLOCKED", "UNKNOWN"}:
        blockers.append("HEALTH_STATE_INVALID")
        state = "UNKNOWN"
    if item.get("read_only") is not True:
        blockers.append("HEALTH_MUST_BE_READ_ONLY")
    if not _false(item.get("executes_action")):
        blockers.append("HEALTH_MUST_NOT_EXECUTE")
    if not _false(item.get("execution_authorized")):
        blockers.append("HEALTH_MUST_NOT_AUTHORIZE_EXECUTION")
    total = _nonnegative_int(item.get("total_domains"))
    healthy = _nonnegative_int(item.get("healthy_domains"))
    if total is None or healthy is None or healthy > total:
        blockers.append("HEALTH_COUNTS_INVALID")
    unresolved = item.get("unresolved_domains")
    if not isinstance(unresolved, (list, tuple)):
        blockers.append("HEALTH_UNRESOLVED_INVALID")
        unresolved_count = None
    else:
        unresolved_count = len(unresolved)
    return {
        "state": state,
        "healthy_domains": healthy,
        "total_domains": total,
        "unresolved_domains": unresolved_count,
        "all_confirmed_healthy": item.get("all_confirmed_healthy") is True,
    }, blockers


def _finops_view(
    raw: Mapping[str, Any] | None,
    trusted: Mapping[str, str],
) -> tuple[dict[str, Any], list[str]]:
    item = dict(raw) if isinstance(raw, Mapping) else {}
    blockers: list[str] = []
    if item.get("schema") != FINOPS_SCHEMA:
        blockers.append("FINOPS_SCHEMA_INVALID")
    state = _text(item.get("state"), 40).upper()
    if state not in {"ALLOW", "DEGRADE", "BLOCK"}:
        blockers.append("FINOPS_STATE_INVALID")
        state = "BLOCK"
    scope = _scope(item.get("scope") if isinstance(item.get("scope"), Mapping) else {})
    if scope != dict(trusted):
        blockers.append("FINOPS_SCOPE_MISMATCH")
    for field in (
        "automatic_provider_call",
        "automatic_model_switch",
        "automatic_charge",
        "grants_authority",
        "executes_action",
    ):
        if not _false(item.get(field)):
            blockers.append("FINOPS_UNSAFE_FIELD:" + field)
    projected = item.get("projected") if isinstance(item.get("projected"), Mapping) else {}
    return {
        "state": state,
        "mode": _text(item.get("mode"), 60).upper(),
        "projected_calls": projected.get("calls"),
        "projected_tokens": projected.get("tokens"),
        "projected_cost_usd": projected.get("predicted_cost_usd"),
        "reconciliation_state": _text(
            (item.get("reconciliation") or {}).get("state")
            if isinstance(item.get("reconciliation"), Mapping)
            else "",
            60,
        ).upper(),
    }, blockers


def _confidence_view(raw: Mapping[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    item = dict(raw) if isinstance(raw, Mapping) else {}
    blockers: list[str] = []
    if item.get("schema") != CONFIDENCE_SCHEMA:
        blockers.append("CONFIDENCE_SCHEMA_INVALID")
    state = _text(item.get("state"), 60).upper()
    if state not in {"HUMAN_REVIEW_READY", "NEEDS_EVIDENCE", "BLOCKED"}:
        blockers.append("CONFIDENCE_STATE_INVALID")
        state = "BLOCKED"
    for field in ("merge_allowed", "deploy_allowed", "real_trading_enabled"):
        if not _false(item.get(field)):
            blockers.append("CONFIDENCE_UNSAFE_FIELD:" + field)
    if item.get("automatic_promotion") is not False:
        blockers.append("CONFIDENCE_AUTOMATIC_PROMOTION_FORBIDDEN")
    confirmed = _nonnegative_int(item.get("confirmed_dimensions"))
    total = _nonnegative_int(item.get("total_dimensions"))
    coverage = item.get("evidence_coverage_pct")
    if confirmed is None or total is None or confirmed > total:
        blockers.append("CONFIDENCE_COUNTS_INVALID")
    if isinstance(coverage, bool) or not isinstance(coverage, (int, float)) or not 0 <= float(coverage) <= 100:
        blockers.append("CONFIDENCE_COVERAGE_INVALID")
        coverage = None
    return {
        "state": state,
        "candidate_ref": _text(item.get("candidate_ref"), 160),
        "confirmed_dimensions": confirmed,
        "total_dimensions": total,
        "evidence_coverage_pct": coverage,
        "digest": _text(item.get("digest"), 128),
    }, blockers


def _readiness_view(
    raw: Mapping[str, Any] | None,
    trusted: Mapping[str, str],
) -> tuple[dict[str, Any], list[str]]:
    item = dict(raw) if isinstance(raw, Mapping) else {}
    blockers: list[str] = []
    if item.get("schema") != READINESS_SCHEMA:
        blockers.append("READINESS_SCHEMA_INVALID")
    state = _text(item.get("state"), 60).upper()
    if state not in {"READY_FOR_HUMAN_OWNER_REVIEW", "BLOCKED"}:
        blockers.append("READINESS_STATE_INVALID")
        state = "BLOCKED"
    scope = _scope(item.get("scope") if isinstance(item.get("scope"), Mapping) else {})
    if scope != dict(trusted):
        blockers.append("READINESS_SCOPE_MISMATCH")
    for field in (
        "production_ready_claim",
        "activation_authorized",
        "merge_authorized",
        "deploy_authorized",
        "core_freeze_authorized",
        "worker_arming_authorized",
        "provider_activation_authorized",
        "recovery_authorized",
        "real_trading_authorized",
        "payment_authorized",
        "executes_action",
    ):
        if not _false(item.get(field)):
            blockers.append("READINESS_UNSAFE_FIELD:" + field)
    stages = item.get("stages") if isinstance(item.get("stages"), Mapping) else {}
    verified = sum(
        1
        for value in stages.values()
        if isinstance(value, Mapping) and value.get("state") == "VERIFIED"
    )
    return {
        "state": state,
        "verified_stages": verified,
        "required_stages": len(item.get("required_stages") or [])
        if isinstance(item.get("required_stages"), (list, tuple))
        else None,
        "readiness_digest": _text(item.get("readiness_digest"), 128),
    }, blockers


def _incident_view(raw: Mapping[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    item = dict(raw) if isinstance(raw, Mapping) else {}
    blockers: list[str] = []
    if item.get("schema") != INCIDENT_SCHEMA:
        blockers.append("INCIDENT_SCHEMA_INVALID")
    total = _nonnegative_int(item.get("total"))
    if total is None:
        blockers.append("INCIDENT_COUNT_INVALID")
    counts = item.get("counts") if isinstance(item.get("counts"), Mapping) else {}
    normalized_counts: dict[str, int] = {}
    for severity in ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"):
        count = _nonnegative_int(counts.get(severity))
        if count is None:
            blockers.append("INCIDENT_SEVERITY_COUNT_INVALID:" + severity)
            count = 0
        normalized_counts[severity] = count
    if total is not None and sum(normalized_counts.values()) != total:
        blockers.append("INCIDENT_COUNT_MISMATCH")
    for field in (
        "automatic_containment",
        "automatic_rollback",
        "automatic_secret_rotation",
        "automatic_account_mutation",
        "real_orders_enabled",
        "executes_action",
    ):
        if not _false(item.get(field)):
            blockers.append("INCIDENT_UNSAFE_FIELD:" + field)
    return {
        "total": total,
        "highest_severity": _text(item.get("highest_severity"), 40).upper(),
        "has_critical": item.get("has_critical") is True,
        "counts": normalized_counts,
        "rollback_review_recommended": item.get("rollback_review_recommended") is True,
    }, blockers


def _tasks_view(
    integrity_raw: Mapping[str, Any] | None,
    projection_raw: Mapping[str, Any] | None,
    trusted: Mapping[str, str],
) -> tuple[dict[str, Any], list[str]]:
    integrity = dict(integrity_raw) if isinstance(integrity_raw, Mapping) else {}
    projection = dict(projection_raw) if isinstance(projection_raw, Mapping) else {}
    blockers: list[str] = []
    if integrity.get("schema") != TASK_SCHEMA:
        blockers.append("TASK_INTEGRITY_SCHEMA_INVALID")
    if integrity.get("state") != "MATCH":
        blockers.append("TASK_REPOSITORY_INTEGRITY_MISMATCH")
    scope = _scope(integrity.get("scope") if isinstance(integrity.get("scope"), Mapping) else {})
    if scope != dict(trusted):
        blockers.append("TASK_SCOPE_MISMATCH")
    if integrity.get("atomic_cas") is not True:
        blockers.append("TASK_ATOMIC_CAS_REQUIRED")
    if not _false(integrity.get("executes_action")):
        blockers.append("TASK_REPOSITORY_MUST_NOT_EXECUTE")
    if not _false(integrity.get("automatic_resume_executes")):
        blockers.append("TASK_AUTO_RESUME_EXECUTION_FORBIDDEN")

    if projection.get("projection_only") is not True:
        blockers.append("TASK_PROJECTION_ONLY_REQUIRED")
    if projection.get("source") != "ATOMIC_DURABLE_TASK_REPOSITORY":
        blockers.append("TASK_PROJECTION_SOURCE_INVALID")
    if projection.get("authoritative_store") != "SQLITE_CAS":
        blockers.append("TASK_AUTHORITATIVE_STORE_INVALID")
    if not _false(projection.get("executes_action")):
        blockers.append("TASK_PROJECTION_MUST_NOT_EXECUTE")
    if not _false(projection.get("automatic_resume_executes")):
        blockers.append("TASK_PROJECTION_AUTO_RESUME_FORBIDDEN")
    if _text(projection.get("repository_digest"), 128) != _text(integrity.get("repository_digest"), 128):
        blockers.append("TASK_REPOSITORY_DIGEST_MISMATCH")

    records = projection.get("records")
    state_counts = {state: 0 for state in _TASK_STATES}
    if not isinstance(records, (list, tuple)):
        blockers.append("TASK_RECORDS_INVALID")
        records = []
    for raw in records:
        if not isinstance(raw, Mapping):
            blockers.append("TASK_RECORD_INVALID")
            continue
        state = _text(raw.get("state"), 40).upper()
        if state not in state_counts:
            blockers.append("TASK_STATE_INVALID")
            continue
        state_counts[state] += 1
    if _nonnegative_int(integrity.get("tasks")) != len(records):
        blockers.append("TASK_COUNT_MISMATCH")

    return {
        "total": len(records),
        "by_state": state_counts,
        "active": sum(state_counts[x] for x in ("PLANNED", "RUNNING", "PAUSED", "WAITING_APPROVAL", "BLOCKED")),
        "blocked": state_counts["BLOCKED"],
        "waiting_approval": state_counts["WAITING_APPROVAL"],
        "done": state_counts["DONE"],
        "repository_digest": _text(integrity.get("repository_digest"), 128),
    }, blockers


def build_mission_control(
    *,
    trusted_scope: Mapping[str, Any] | None,
    health_snapshot: Mapping[str, Any] | None,
    finops_snapshot: Mapping[str, Any] | None,
    confidence_snapshot: Mapping[str, Any] | None,
    readiness_snapshot: Mapping[str, Any] | None,
    incident_snapshot: Mapping[str, Any] | None,
    task_integrity: Mapping[str, Any] | None,
    task_projection: Mapping[str, Any] | None,
) -> dict[str, Any]:
    trusted = _scope(trusted_scope)
    blockers: list[str] = []
    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_REQUIRED")

    health, errors = _health_view(health_snapshot)
    blockers.extend(errors)
    finops, errors = _finops_view(finops_snapshot, trusted)
    blockers.extend(errors)
    confidence, errors = _confidence_view(confidence_snapshot)
    blockers.extend(errors)
    readiness, errors = _readiness_view(readiness_snapshot, trusted)
    blockers.extend(errors)
    incidents, errors = _incident_view(incident_snapshot)
    blockers.extend(errors)
    tasks, errors = _tasks_view(task_integrity, task_projection, trusted)
    blockers.extend(errors)

    hard_operational = []
    degraded = []
    if health["state"] in {"BLOCKED", "UNKNOWN"}:
        hard_operational.append("HEALTH_NOT_READY")
    elif health["state"] == "DEGRADED":
        degraded.append("HEALTH_DEGRADED")

    if finops["state"] == "BLOCK":
        hard_operational.append("FINOPS_BLOCK")
    elif finops["state"] == "DEGRADE":
        degraded.append("FINOPS_DEGRADED")

    if confidence["state"] == "BLOCKED":
        hard_operational.append("CONFIDENCE_BLOCKED")
    elif confidence["state"] == "NEEDS_EVIDENCE":
        degraded.append("CONFIDENCE_NEEDS_EVIDENCE")

    if readiness["state"] != "READY_FOR_HUMAN_OWNER_REVIEW":
        hard_operational.append("READINESS_BLOCKED")

    if incidents["has_critical"]:
        hard_operational.append("CRITICAL_INCIDENT_OPEN")
    elif (incidents["total"] or 0) > 0:
        degraded.append("INCIDENTS_OPEN")

    if tasks["blocked"] > 0:
        degraded.append("TASKS_BLOCKED")

    blockers.extend(hard_operational)
    blockers = list(dict.fromkeys(blockers))
    degraded = list(dict.fromkeys(degraded))

    if blockers:
        state = "BLOCKED"
    elif degraded:
        state = "DEGRADED"
    else:
        state = "READY_FOR_HUMAN_REVIEW"

    views = {
        "health": health,
        "finops": finops,
        "confidence": confidence,
        "readiness": readiness,
        "incidents": incidents,
        "tasks": tasks,
    }
    return {
        "schema": SCHEMA,
        "state": state,
        "blockers": blockers,
        "degrade_reasons": degraded,
        "scope": trusted,
        "views": views,
        "mission_control_digest": _digest({
            "scope": trusted,
            "state": state,
            "blockers": blockers,
            "degrade_reasons": degraded,
            "views": views,
        }),
        "source_of_truth": False,
        "projection_only": True,
        "raw_payloads_exposed": False,
        "requires_human_review": state == "READY_FOR_HUMAN_REVIEW",
        "automatic_repair": False,
        "automatic_restart": False,
        "automatic_budget_change": False,
        "automatic_incident_control": False,
        "automatic_task_transition": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "worker_arming_authorized": False,
        "provider_activation_authorized": False,
        "recovery_authorized": False,
        "real_trading_authorized": False,
        "payment_authorized": False,
        "executes_action": False,
    }


def mission_control_contract() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "sources": [
            HEALTH_SCHEMA,
            FINOPS_SCHEMA,
            CONFIDENCE_SCHEMA,
            READINESS_SCHEMA,
            INCIDENT_SCHEMA,
            TASK_SCHEMA,
        ],
        "source_of_truth": False,
        "projection_only": True,
        "raw_payloads_exposed": False,
        "automatic_repair": False,
        "automatic_incident_control": False,
        "automatic_task_transition": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "build_mission_control",
    "mission_control_contract",
]
