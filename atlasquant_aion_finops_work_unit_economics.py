"""AION FinOps work-unit economics.

Pure/offline unit-economics layer over the existing FinOps metering ledger.
It answers how much evidenced AI/tool usage was associated with completed work
without treating missing cost evidence as zero and without becoming a billing
source of truth.

One metering event may belong to at most one work unit in V1. If a provider cost
covers multiple work units, upstream metering must split it into explicit events.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA = "ATLASQUANT_AION_FINOPS_WORK_UNIT_ECONOMICS_V1"
METERING_SCHEMA = "ATLASQUANT_AION_FINOPS_METERING_V1"
WORK_STATES = ("COMPLETED", "FAILED", "CANCELLED", "IN_PROGRESS")
MAX_WORK_UNITS = 5000
MAX_ALLOCATIONS = 10000


def _text(value: Any, limit: int = 180) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _money(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out) or out < 0:
        return None
    return round(out, 9)


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    item = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(item.get("owner_id"), 100),
        "tenant_id": _text(item.get("tenant_id"), 100),
        "workspace_id": _text(item.get("workspace_id"), 100),
    }


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _normalize_work(
    raw: Mapping[str, Any],
    *,
    trusted_scope: Mapping[str, str],
) -> dict[str, Any]:
    item = dict(raw or {})
    blockers: list[str] = []
    for key, expected in trusted_scope.items():
        claimed = _text(item.get(key), 100)
        if claimed and claimed != expected:
            blockers.append("WORK_SCOPE_MISMATCH")

    work_id = _text(item.get("work_id"), 140)
    work_type = _text(item.get("work_type"), 120).lower()
    state = _text(item.get("state"), 40).upper()
    completed_at = _text(item.get("completed_at"), 96)
    evidence_refs = [
        _text(x, 240)
        for x in list(item.get("evidence_refs") or [])[:40]
        if _text(x, 240)
    ]

    if not work_id:
        blockers.append("WORK_ID_REQUIRED")
    if not work_type:
        blockers.append("WORK_TYPE_REQUIRED")
    if state not in WORK_STATES:
        blockers.append("WORK_STATE_INVALID")
    if state == "COMPLETED" and not completed_at:
        blockers.append("COMPLETED_AT_REQUIRED")
    if state == "COMPLETED" and not evidence_refs:
        blockers.append("COMPLETION_EVIDENCE_REQUIRED")

    identity = {
        **trusted_scope,
        "work_id": work_id,
        "work_type": work_type,
        "state": state,
        "completed_at": completed_at,
        "evidence_refs": evidence_refs,
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        **identity,
        "state_valid": not blockers,
        "blockers": blockers,
        "work_digest": _digest(identity),
    }


def build_work_unit_economics(
    metering_ledger: Mapping[str, Any] | None,
    *,
    work_units: Sequence[Mapping[str, Any]] | None,
    allocations: Sequence[Mapping[str, Any]] | None,
    trusted_scope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build evidence-bound cost per completed work from a metering ledger."""
    scope = _scope(trusted_scope)
    blockers: list[str] = []
    warnings: list[str] = []

    if not all(scope.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")

    ledger = dict(metering_ledger) if isinstance(metering_ledger, Mapping) else {}
    if ledger.get("schema") != METERING_SCHEMA:
        blockers.append("METERING_LEDGER_SCHEMA_INVALID")
    if ledger.get("state") != "READY":
        blockers.append("METERING_LEDGER_NOT_READY")
    if _scope(ledger) != scope:
        blockers.append("METERING_LEDGER_SCOPE_MISMATCH")
    if ledger.get("source_of_truth_for_billing") is not False:
        blockers.append("METERING_BILLING_BOUNDARY_UNSAFE")
    if ledger.get("executes_action") is not False:
        blockers.append("METERING_EXECUTION_BOUNDARY_UNSAFE")

    normalized_work: list[dict[str, Any]] = []
    work_by_id: dict[str, dict[str, Any]] = {}
    for raw in list(work_units or [])[:MAX_WORK_UNITS]:
        if not isinstance(raw, Mapping):
            blockers.append("WORK_ITEM_INVALID")
            continue
        row = _normalize_work(raw, trusted_scope=scope)
        if row["blockers"]:
            blockers.extend(row["blockers"])
            continue
        wid = row["work_id"]
        if wid in work_by_id:
            blockers.append("WORK_ID_DUPLICATE")
            continue
        work_by_id[wid] = row
        normalized_work.append(row)

    accepted_events = [
        dict(x)
        for x in list(ledger.get("accepted_events") or [])[:MAX_ALLOCATIONS]
        if isinstance(x, Mapping)
    ]
    event_by_id: dict[str, dict[str, Any]] = {}
    for row in accepted_events:
        event_id = _text(row.get("event_id"), 160)
        if not event_id:
            blockers.append("METER_EVENT_ID_MISSING")
            continue
        if event_id in event_by_id:
            blockers.append("METER_EVENT_ID_DUPLICATE")
            continue
        event_by_id[event_id] = row

    event_to_work: dict[str, str] = {}
    allocation_rows: list[dict[str, str]] = []
    for raw in list(allocations or [])[:MAX_ALLOCATIONS]:
        if not isinstance(raw, Mapping):
            blockers.append("ALLOCATION_INVALID")
            continue
        event_id = _text(raw.get("event_id"), 160)
        work_id = _text(raw.get("work_id"), 140)
        if not event_id or not work_id:
            blockers.append("ALLOCATION_KEYS_REQUIRED")
            continue
        if event_id not in event_by_id:
            blockers.append("ALLOCATION_EVENT_NOT_IN_LEDGER")
            continue
        if work_id not in work_by_id:
            blockers.append("ALLOCATION_WORK_NOT_FOUND")
            continue
        if event_id in event_to_work:
            blockers.append("METER_EVENT_ALLOCATED_MORE_THAN_ONCE")
            continue
        event_to_work[event_id] = work_id
        allocation_rows.append({"event_id": event_id, "work_id": work_id})

    completed = [row for row in normalized_work if row["state"] == "COMPLETED"]
    failed = [row for row in normalized_work if row["state"] == "FAILED"]
    cancelled = [row for row in normalized_work if row["state"] == "CANCELLED"]
    in_progress = [row for row in normalized_work if row["state"] == "IN_PROGRESS"]

    costed_completed: dict[str, dict[str, Any]] = {}
    by_type: dict[str, dict[str, Any]] = {}
    for work in completed:
        linked = [
            event_by_id[event_id]
            for event_id, wid in event_to_work.items()
            if wid == work["work_id"]
        ]
        if not linked:
            warnings.append("COMPLETED_WORK_WITHOUT_COST_EVIDENCE")
            continue

        predicted_values = [_money(row.get("predicted_cost_usd")) for row in linked]
        actual_values = [_money(row.get("actual_cost_usd")) for row in linked]
        if any(value is None for value in predicted_values):
            warnings.append("COMPLETED_WORK_PREDICTED_COST_INCOMPLETE")
        predicted_total = (
            None
            if any(value is None for value in predicted_values)
            else round(sum(value or 0.0 for value in predicted_values), 9)
        )
        actual_complete = all(value is not None for value in actual_values)
        actual_total = (
            round(sum(value or 0.0 for value in actual_values), 9)
            if actual_complete
            else None
        )
        if not actual_complete:
            warnings.append("COMPLETED_WORK_ACTUAL_COST_INCOMPLETE")

        row = {
            "work_id": work["work_id"],
            "work_type": work["work_type"],
            "meter_event_ids": [
                _text(event.get("event_id"), 160) for event in linked
            ],
            "predicted_cost_usd": predicted_total,
            "actual_cost_usd": actual_total,
            "actual_cost_complete": actual_complete,
        }
        costed_completed[work["work_id"]] = row

        bucket = by_type.setdefault(
            work["work_type"],
            {
                "completed": 0,
                "costed_completed": 0,
                "predicted_cost_usd": 0.0,
                "actual_cost_usd": 0.0,
                "actual_cost_complete_count": 0,
            },
        )
        bucket["completed"] += 1
        bucket["costed_completed"] += 1
        if predicted_total is not None:
            bucket["predicted_cost_usd"] = round(
                float(bucket["predicted_cost_usd"]) + predicted_total, 9
            )
        if actual_total is not None:
            bucket["actual_cost_usd"] = round(
                float(bucket["actual_cost_usd"]) + actual_total, 9
            )
            bucket["actual_cost_complete_count"] += 1

    for work in completed:
        by_type.setdefault(
            work["work_type"],
            {
                "completed": 0,
                "costed_completed": 0,
                "predicted_cost_usd": 0.0,
                "actual_cost_usd": 0.0,
                "actual_cost_complete_count": 0,
            },
        )
    for bucket in by_type.values():
        bucket["completed"] = sum(
            1 for row in completed if row["work_type"] in by_type and row["work_type"] == next(
                key for key, value in by_type.items() if value is bucket
            )
        )

    unallocated_event_ids = sorted(set(event_by_id) - set(event_to_work))
    if unallocated_event_ids:
        warnings.append("METER_EVENTS_UNALLOCATED")

    allocated_completed_events = [
        event_id
        for event_id, work_id in event_to_work.items()
        if work_by_id[work_id]["state"] == "COMPLETED"
    ]
    allocated_noncompleted_events = [
        event_id
        for event_id, work_id in event_to_work.items()
        if work_by_id[work_id]["state"] != "COMPLETED"
    ]

    predicted_complete_rows = [
        row for row in costed_completed.values()
        if row["predicted_cost_usd"] is not None
    ]
    actual_complete_rows = [
        row for row in costed_completed.values()
        if row["actual_cost_complete"] is True
    ]

    predicted_cost_total = round(
        sum(float(row["predicted_cost_usd"]) for row in predicted_complete_rows),
        9,
    )
    actual_cost_total = round(
        sum(float(row["actual_cost_usd"]) for row in actual_complete_rows),
        9,
    )

    completed_count = len(completed)
    costed_completed_count = len(costed_completed)
    cost_coverage_pct = (
        round(costed_completed_count / completed_count * 100.0, 4)
        if completed_count
        else None
    )
    actual_coverage_pct = (
        round(len(actual_complete_rows) / completed_count * 100.0, 4)
        if completed_count
        else None
    )

    observed_predicted_per_costed = (
        round(predicted_cost_total / len(predicted_complete_rows), 9)
        if predicted_complete_rows
        else None
    )
    observed_actual_per_costed = (
        round(actual_cost_total / len(actual_complete_rows), 9)
        if actual_complete_rows
        else None
    )

    fully_covered = bool(
        completed_count > 0
        and costed_completed_count == completed_count
        and len(predicted_complete_rows) == completed_count
        and len(actual_complete_rows) == completed_count
        and not unallocated_event_ids
    )
    confirmed_actual_cost_per_completed = (
        round(actual_cost_total / completed_count, 9)
        if fully_covered
        else None
    )

    blockers = list(dict.fromkeys(blockers))
    warnings = list(dict.fromkeys(warnings))
    if blockers:
        state = "BLOCKED"
    elif not completed_count:
        state = "NO_COMPLETED_WORK"
    elif fully_covered:
        state = "CONFIRMED"
    else:
        state = "PARTIAL"

    integrity_material = {
        "scope": scope,
        "works": [
            {"work_id": row["work_id"], "work_digest": row["work_digest"]}
            for row in normalized_work
        ],
        "allocations": allocation_rows,
        "ledger_digest": _text(ledger.get("ledger_digest"), 180),
    }

    return {
        "schema": SCHEMA,
        "state": state,
        "scope": scope,
        "blockers": blockers,
        "warnings": warnings,
        "work_counts": {
            "total": len(normalized_work),
            "completed": completed_count,
            "failed": len(failed),
            "cancelled": len(cancelled),
            "in_progress": len(in_progress),
            "costed_completed": costed_completed_count,
        },
        "allocation": {
            "accepted_meter_events": len(event_by_id),
            "allocated_events": len(event_to_work),
            "allocated_completed_events": len(allocated_completed_events),
            "allocated_noncompleted_events": len(allocated_noncompleted_events),
            "unallocated_events": len(unallocated_event_ids),
            "unallocated_event_ids": unallocated_event_ids[:100],
        },
        "coverage": {
            "completed_work_cost_coverage_pct": cost_coverage_pct,
            "completed_work_actual_cost_coverage_pct": actual_coverage_pct,
            "fully_covered": fully_covered,
        },
        "economics": {
            "observed_predicted_cost_usd": predicted_cost_total,
            "observed_actual_cost_usd": actual_cost_total,
            "observed_predicted_cost_per_costed_completed_work_usd": observed_predicted_per_costed,
            "observed_actual_cost_per_costed_completed_work_usd": observed_actual_per_costed,
            "confirmed_actual_cost_per_completed_work_usd": confirmed_actual_cost_per_completed,
        },
        "completed_work": list(costed_completed.values()),
        "by_work_type": by_type,
        "snapshot_digest": _digest(integrity_material),
        "source_of_truth_for_billing": False,
        "missing_cost_is_zero": False,
        "automatic_charge": False,
        "automatic_pricing_change": False,
        "automatic_budget_change": False,
        "automatic_provider_switch": False,
        "grants_authority": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "METERING_SCHEMA",
    "WORK_STATES",
    "build_work_unit_economics",
]
