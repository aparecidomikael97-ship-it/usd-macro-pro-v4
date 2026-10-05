"""AION B2B controlled-pilot operating contract.

Pure/offline contract builder and checkpoint evaluator. This module turns an
owner-review candidate into a bounded pilot specification, but it never starts,
stops, deploys, bills, contacts a customer, or mutates production.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA = "ATLASQUANT_AION_B2B_PILOT_OPERATING_CONTRACT_V1"
MIN_DURATION_DAYS = 7
MAX_DURATION_DAYS = 30
MAX_MONTHLY_INFRA_BRL = 200.0
MIN_KPIS = 3
MAX_KPIS = 8


def _text(value: Any, limit: int = 300) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(data.get("owner_id"), 120),
        "tenant_id": _text(data.get("tenant_id"), 120),
        "workspace_id": _text(data.get("workspace_id"), 120),
    }


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _unique_texts(value: Any, *, limit: int, item_limit: int = 300) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:limit]:
        item = _text(raw, item_limit)
        if item and item not in out:
            out.append(item)
    return out


def _validate_readiness(readiness: Mapping[str, Any] | None) -> list[str]:
    data = dict(readiness) if isinstance(readiness, Mapping) else {}
    blockers: list[str] = []
    if data.get("decision") != "PILOT_REVIEW_CANDIDATE":
        blockers.append("READINESS_NOT_PILOT_REVIEW_CANDIDATE")
    if data.get("state") != "READY_FOR_OWNER_REVIEW":
        blockers.append("READINESS_STATE_INVALID")
    if data.get("human_owner_decision_required") is not True:
        blockers.append("OWNER_DECISION_BOUNDARY_MISSING")
    if data.get("blockers"):
        blockers.append("READINESS_HAS_BLOCKERS")
    if not _text(data.get("evidence_digest"), 180):
        blockers.append("READINESS_EVIDENCE_DIGEST_REQUIRED")
    if data.get("automatic_acceptance") is not False:
        blockers.append("READINESS_AUTOMATIC_ACCEPTANCE_UNSAFE")
    if data.get("production_mutation") is not False:
        blockers.append("READINESS_PRODUCTION_BOUNDARY_UNSAFE")
    return blockers


def _normalize_kpis(value: Any) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(value, (list, tuple)):
        return [], ["KPIS_REQUIRED"]
    blockers: list[str] = []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    if len(value) < MIN_KPIS or len(value) > MAX_KPIS:
        blockers.append("KPI_COUNT_INVALID")

    for raw in value[:MAX_KPIS]:
        if not isinstance(raw, Mapping):
            blockers.append("KPI_INVALID")
            continue
        metric_id = _text(raw.get("metric_id"), 100)
        label = _text(raw.get("label"), 160)
        unit = _text(raw.get("unit"), 60)
        source_ref = _text(raw.get("source_ref"), 320)
        direction = _text(raw.get("direction"), 20).upper()
        baseline = _number(raw.get("baseline"))
        target = _number(raw.get("target"))

        if not metric_id or metric_id in seen:
            blockers.append("KPI_ID_INVALID_OR_DUPLICATE")
            continue
        seen.add(metric_id)
        if not label or not unit or not source_ref:
            blockers.append(f"KPI_METADATA_INCOMPLETE:{metric_id}")
        if direction not in {"HIGHER", "LOWER"}:
            blockers.append(f"KPI_DIRECTION_INVALID:{metric_id}")
        if baseline is None or target is None:
            blockers.append(f"KPI_VALUE_INVALID:{metric_id}")
        elif direction == "HIGHER" and target <= baseline:
            blockers.append(f"KPI_TARGET_NOT_IMPROVEMENT:{metric_id}")
        elif direction == "LOWER" and target >= baseline:
            blockers.append(f"KPI_TARGET_NOT_IMPROVEMENT:{metric_id}")

        out.append(
            {
                "metric_id": metric_id,
                "label": label,
                "unit": unit,
                "direction": direction,
                "baseline": baseline,
                "target": target,
                "source_ref": source_ref,
            }
        )

    return out, list(dict.fromkeys(blockers))


def build_pilot_operating_contract(
    *,
    trusted_scope: Mapping[str, Any],
    readiness: Mapping[str, Any],
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    data = dict(spec) if isinstance(spec, Mapping) else {}
    trusted = _scope(trusted_scope)
    scope = _scope(data)
    blockers = _validate_readiness(readiness)

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")
    if scope != trusted:
        blockers.append("PILOT_SCOPE_MISMATCH")

    pilot_id = _text(data.get("pilot_id"), 120)
    candidate_id = _text(data.get("candidate_id"), 120)
    if not pilot_id:
        blockers.append("PILOT_ID_REQUIRED")
    if not candidate_id:
        blockers.append("CANDIDATE_ID_REQUIRED")

    duration = data.get("duration_days")
    if (
        isinstance(duration, bool)
        or not isinstance(duration, int)
        or duration < MIN_DURATION_DAYS
        or duration > MAX_DURATION_DAYS
    ):
        blockers.append("PILOT_DURATION_OUT_OF_RANGE")

    monthly_infra = _number(data.get("max_monthly_infra_brl"))
    if monthly_infra is None or monthly_infra < 0:
        blockers.append("PILOT_INFRA_BUDGET_INVALID")
    elif monthly_infra > MAX_MONTHLY_INFRA_BRL:
        blockers.append("PILOT_INFRA_BUDGET_EXCEEDS_CAP")

    objectives = _unique_texts(data.get("objectives"), limit=5, item_limit=400)
    quick_wins = _unique_texts(data.get("quick_wins"), limit=5, item_limit=400)
    stop_conditions = _unique_texts(data.get("stop_conditions"), limit=10, item_limit=400)
    rollback_steps = _unique_texts(data.get("rollback_steps"), limit=10, item_limit=400)
    evidence_refs = _unique_texts(data.get("evidence_refs"), limit=20, item_limit=320)

    if not objectives:
        blockers.append("PILOT_OBJECTIVE_REQUIRED")
    if not quick_wins:
        blockers.append("QUICK_WIN_REQUIRED")
    if len(stop_conditions) < 3:
        blockers.append("STOP_CONDITIONS_INSUFFICIENT")
    if len(rollback_steps) < 2:
        blockers.append("ROLLBACK_PLAN_INSUFFICIENT")
    if len(evidence_refs) < 3:
        blockers.append("PILOT_EVIDENCE_INSUFFICIENT")

    kpis, kpi_blockers = _normalize_kpis(data.get("kpis"))
    blockers.extend(kpi_blockers)

    contract_core = {
        "pilot_id": pilot_id,
        "candidate_id": candidate_id,
        **scope,
        "duration_days": duration if isinstance(duration, int) and not isinstance(duration, bool) else None,
        "max_monthly_infra_brl": monthly_infra,
        "objectives": objectives,
        "quick_wins": quick_wins,
        "kpis": kpis,
        "stop_conditions": stop_conditions,
        "rollback_steps": rollback_steps,
        "evidence_refs": evidence_refs,
        "readiness_evidence_digest": _text(readiness.get("evidence_digest"), 180),
    }

    return {
        "schema": SCHEMA,
        "state": "DRAFT_FOR_OWNER_APPROVAL" if not blockers else "BLOCKED",
        "activation_state": "BLOCKED_UNTIL_OWNER_APPROVAL",
        "contract": contract_core,
        "blockers": list(dict.fromkeys(blockers)),
        "contract_digest": _digest(contract_core),
        "human_owner_approval_required": True,
        "automatic_activation": False,
        "automatic_contract_signature": False,
        "automatic_customer_contact": False,
        "automatic_billing": False,
        "automatic_spend": False,
        "automatic_deploy": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }


def evaluate_pilot_checkpoint(
    contract_result: Mapping[str, Any],
    *,
    measurements: Sequence[Mapping[str, Any]] | None,
    security_incident: bool = False,
    scope_breach: bool = False,
    privacy_breach: bool = False,
    budget_breach: bool = False,
) -> dict[str, Any]:
    contract_result = dict(contract_result) if isinstance(contract_result, Mapping) else {}
    blockers: list[str] = []

    if contract_result.get("state") != "DRAFT_FOR_OWNER_APPROVAL":
        blockers.append("CONTRACT_NOT_REVIEWABLE")
    if contract_result.get("blockers"):
        blockers.append("CONTRACT_HAS_BLOCKERS")

    hard_stop_reasons: list[str] = []
    for flag, reason in (
        (security_incident, "SECURITY_INCIDENT"),
        (scope_breach, "SCOPE_BREACH"),
        (privacy_breach, "PRIVACY_BREACH"),
        (budget_breach, "BUDGET_BREACH"),
    ):
        if flag is True:
            hard_stop_reasons.append(reason)

    core = contract_result.get("contract")
    core = dict(core) if isinstance(core, Mapping) else {}
    expected_kpis = {
        item.get("metric_id"): item
        for item in (core.get("kpis") or [])
        if isinstance(item, Mapping) and item.get("metric_id")
    }

    supplied: dict[str, Mapping[str, Any]] = {}
    measurement_blockers: list[str] = []
    for raw in measurements or []:
        if not isinstance(raw, Mapping):
            measurement_blockers.append("MEASUREMENT_INVALID")
            continue
        metric_id = _text(raw.get("metric_id"), 100)
        if not metric_id or metric_id in supplied:
            measurement_blockers.append("MEASUREMENT_ID_INVALID_OR_DUPLICATE")
            continue
        supplied[metric_id] = raw

    progress: dict[str, dict[str, Any]] = {}
    target_hits = 0
    valid_measurements = 0
    for metric_id, kpi in expected_kpis.items():
        raw = supplied.get(metric_id)
        if raw is None:
            progress[metric_id] = {"state": "MISSING", "target_hit": False}
            continue
        current = _number(raw.get("current"))
        source_ref = _text(raw.get("source_ref"), 320)
        if current is None or not source_ref:
            progress[metric_id] = {"state": "INVALID", "target_hit": False}
            measurement_blockers.append(f"MEASUREMENT_INVALID:{metric_id}")
            continue

        valid_measurements += 1
        direction = kpi.get("direction")
        target = kpi.get("target")
        hit = bool(
            (direction == "HIGHER" and current >= target)
            or (direction == "LOWER" and current <= target)
        )
        if hit:
            target_hits += 1
        progress[metric_id] = {
            "state": "MEASURED",
            "current": current,
            "target": target,
            "target_hit": hit,
            "source_ref": source_ref,
        }

    total_kpis = len(expected_kpis)
    completion_pct = round((valid_measurements / total_kpis) * 100.0, 2) if total_kpis else 0.0
    target_hit_pct = round((target_hits / total_kpis) * 100.0, 2) if total_kpis else 0.0

    if blockers:
        state = "BLOCKED"
    elif hard_stop_reasons:
        state = "STOP_REVIEW"
    elif measurement_blockers or valid_measurements < total_kpis:
        state = "EVIDENCE_INCOMPLETE"
    elif target_hit_pct >= 66.67:
        state = "ON_TRACK"
    else:
        state = "AT_RISK"

    return {
        "schema": SCHEMA,
        "state": state,
        "hard_stop_reasons": hard_stop_reasons,
        "measurement_blockers": list(dict.fromkeys(measurement_blockers)),
        "kpi_completion_pct": completion_pct,
        "kpi_target_hit_pct": target_hit_pct,
        "progress": progress,
        "owner_review_required": True,
        "automatic_stop": False,
        "automatic_expand_scope": False,
        "automatic_contract_change": False,
        "automatic_billing": False,
        "automatic_deploy": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "MIN_DURATION_DAYS",
    "MAX_DURATION_DAYS",
    "MAX_MONTHLY_INFRA_BRL",
    "build_pilot_operating_contract",
    "evaluate_pilot_checkpoint",
]
