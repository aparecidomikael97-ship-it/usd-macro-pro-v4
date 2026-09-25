"""Reliability & Governance contracts for AtlasQuant/AION.

Read-only governance layer that reconciles source evidence, protects truthful
operation under partial failures, summarizes cost posture and keeps recovery
advisory-only. It never calls providers, changes budgets, mutates checkpoints,
deploys, rolls back, publishes or enables trading.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA = "ATLASQUANT_AION_RELIABILITY_GOVERNANCE_V1"

SOURCE_STATES = ("OK", "DEGRADED", "STALE", "CONFLICT", "UNAVAILABLE", "UNKNOWN")
TRUTH_STATES = ("CONFIRMED", "INFERENCE", "HYPOTHESIS", "UNKNOWN")
CRITICALITY = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _upper(value: Any, limit: int = 80) -> str:
    return _clean(value, limit).upper()


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _stable(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return repr(value)


def normalize_source_observation(raw: Mapping[str, Any]) -> dict[str, Any]:
    item = dict(raw or {})
    source = _clean(item.get("source") or item.get("provider"), 160) or "unknown"
    claim = _clean(item.get("claim") or item.get("metric"), 180) or "unknown"
    truth = _upper(item.get("truth_state") or item.get("kind"))
    if truth not in TRUTH_STATES:
        truth = "UNKNOWN"

    criticality = _upper(item.get("criticality") or "MEDIUM")
    if criticality not in CRITICALITY:
        criticality = "MEDIUM"

    available_raw = item.get("available")
    available = available_raw if isinstance(available_raw, bool) else None
    healthy_raw = item.get("healthy")
    healthy = healthy_raw if isinstance(healthy_raw, bool) else None
    age = _finite(item.get("age_minutes"))
    max_age = _finite(item.get("max_age_minutes"))
    if age is not None:
        age = max(0.0, age)
    if max_age is not None:
        max_age = max(0.0, max_age)

    if available is False:
        state = "UNAVAILABLE"
    elif available is None and truth == "UNKNOWN":
        state = "UNKNOWN"
    elif age is not None and max_age is not None and age > max_age:
        state = "STALE"
    elif healthy is False:
        state = "DEGRADED"
    elif truth == "CONFIRMED" and available is not False:
        state = "OK"
    elif truth in {"INFERENCE", "HYPOTHESIS"}:
        state = "DEGRADED"
    else:
        state = "UNKNOWN"

    return {
        "source": source,
        "claim": claim,
        "value": item.get("value"),
        "truth_state": truth,
        "criticality": criticality,
        "available": available,
        "healthy": healthy,
        "age_minutes": age,
        "max_age_minutes": max_age,
        "state": state,
        "detail": _clean(item.get("detail") or item.get("note"), 700),
        "cost_state": _upper(item.get("cost_state") or "UNKNOWN"),
        "quota_remaining_pct": _finite(item.get("quota_remaining_pct")),
        "family": _clean(item.get("family") or "runtime", 80).lower() or "runtime",
        "executes_action": False,
    }


def normalize_source_observations(
    rows: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in list(rows or [])[:500]:
        if not isinstance(raw, Mapping):
            continue
        out.append(normalize_source_observation(raw))
    return out


def reconcile_sources(
    observations: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    rows = normalize_source_observations(observations)
    by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_claim[row["claim"].casefold()].append(row)

    conflicts: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []

    for _, group in sorted(by_claim.items(), key=lambda kv: kv[0]):
        fresh_confirmed = [
            row for row in group
            if row["truth_state"] == "CONFIRMED"
            and row["state"] == "OK"
        ]
        values = defaultdict(list)
        for row in fresh_confirmed:
            values[_stable(row["value"])].append(row["source"])

        conflict = len(values) > 1
        if conflict:
            conflicts.append({
                "claim": group[0]["claim"],
                "sources": sorted({x["source"] for x in fresh_confirmed}),
                "distinct_values": len(values),
            })
            for row in fresh_confirmed:
                row["state"] = "CONFLICT"

        if conflict:
            state = "CONFLICT"
        elif fresh_confirmed:
            state = "CONFIRMED"
        elif any(row["state"] == "STALE" for row in group):
            state = "STALE"
        elif any(row["state"] in {"DEGRADED", "UNAVAILABLE"} for row in group):
            state = "DEGRADED"
        else:
            state = "UNKNOWN"

        claims.append({
            "claim": group[0]["claim"],
            "state": state,
            "sources": len({row["source"] for row in group}),
            "confirmed_fresh_sources": len({row["source"] for row in fresh_confirmed}),
            "criticality": max(
                (row["criticality"] for row in group),
                key=lambda x: CRITICALITY.index(x),
            ),
            "conflict": conflict,
            "executes_action": False,
        })

    source_counts = Counter(row["state"] for row in rows)
    critical_conflicts = sum(
        1 for item in conflicts
        if any(
            c["claim"] == item["claim"]
            and c["criticality"] in {"HIGH", "CRITICAL"}
            for c in claims
        )
    )

    return {
        "schema": SCHEMA,
        "observations": rows,
        "claims": claims,
        "conflicts": conflicts,
        "conflict_count": len(conflicts),
        "critical_conflict_count": critical_conflicts,
        "source_counts": {state: int(source_counts[state]) for state in SOURCE_STATES},
        "has_conflict": bool(conflicts),
        "has_critical_conflict": critical_conflicts > 0,
        "truth_rule": "Conflito entre fontes confirmadas permanece conflito; o AION não escolhe silenciosamente.",
        "executes_action": False,
        "real_orders_enabled": False,
    }


def data_guardian_snapshot(
    observations: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    reconciled = reconcile_sources(observations)
    rows = list(reconciled.get("observations") or [])
    critical_bad = [
        row for row in rows
        if row["criticality"] in {"HIGH", "CRITICAL"}
        and row["state"] in {"STALE", "DEGRADED", "UNAVAILABLE", "UNKNOWN"}
    ]
    if reconciled["has_critical_conflict"]:
        state = "FAIL_CLOSED"
    elif critical_bad:
        state = "DEGRADED_SAFE"
    elif not rows:
        state = "UNKNOWN"
    elif reconciled["has_conflict"]:
        state = "DEGRADED_SAFE"
    elif any(row["state"] != "OK" for row in rows):
        state = "DEGRADED_SAFE"
    else:
        state = "CONTROLLED"

    next_actions: list[str] = []
    if reconciled["has_conflict"]:
        next_actions.append("Reconciliar fontes conflitantes antes de usar a afirmação como fato.")
    if any(row["state"] == "STALE" for row in rows):
        next_actions.append("Atualizar fontes stale antes de decisão sensível.")
    if any(row["state"] == "UNAVAILABLE" for row in rows):
        next_actions.append("Confirmar fallback autorizado ou manter a capacidade dependente bloqueada.")
    if not rows:
        next_actions.append("Fornecer observações de fonte para confirmar saúde dos dados.")

    return {
        "schema": SCHEMA,
        "state": state,
        "reconciliation": reconciled,
        "critical_bad_sources": len(critical_bad),
        "next_actions": next_actions,
        "allows_strong_claims": state == "CONTROLLED",
        "allows_live_market_authorization": False,
        "automatic_source_switch": False,
        "executes_action": False,
        "real_orders_enabled": False,
    }


def cost_guardian_snapshot(
    budget: Mapping[str, Any] | None,
    provider_status: Mapping[str, Any] | None = None,
    source_observations: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    b = dict(budget or {})
    provider = dict(provider_status or {})
    limit = max(0.0, _finite(b.get("monthly_limit_usd")) or 0.0)
    spent = max(
        0.0,
        _finite(b.get("spent_usd_estimate"))
        or _finite(b.get("spent_usd"))
        or 0.0,
    )
    remaining = max(0.0, limit - spent)
    allow_paid = bool(b.get("allow_paid", False))
    pct = None if limit <= 0 else round(spent / limit * 100.0, 2)

    source_rows = normalize_source_observations(source_observations)
    quota_warnings = [
        row for row in source_rows
        if row.get("quota_remaining_pct") is not None
        and float(row["quota_remaining_pct"]) <= 15.0
    ]

    provider_state = _upper(provider.get("state") or "UNKNOWN")
    if not allow_paid or limit <= 0:
        state = "ZERO_COST"
    elif spent >= limit:
        state = "BLOCKED_LIMIT"
    elif pct is not None and pct >= 85:
        state = "WARNING"
    else:
        state = "CONTROLLED"

    if quota_warnings and state == "CONTROLLED":
        state = "WARNING"

    return {
        "schema": SCHEMA,
        "state": state,
        "allow_paid": allow_paid,
        "monthly_limit_usd": round(limit, 4),
        "spent_usd_estimate": round(spent, 4),
        "remaining_usd": round(remaining, 4),
        "used_pct": pct,
        "provider_state": provider_state,
        "low_quota_sources": [row["source"] for row in quota_warnings],
        "automatic_billing": False,
        "automatic_upgrade": False,
        "automatic_paid_fallback": False,
        "executes_action": False,
    }


def memory_protection_snapshot(
    runtime_result: Mapping[str, Any] | None,
    *,
    checkpoint_dirty: bool = False,
    checkpoint_conflict: bool = False,
) -> dict[str, Any]:
    runtime = dict(runtime_result or {})
    integrity = runtime.get("integrity") if isinstance(runtime.get("integrity"), Mapping) else {}
    integrity_state = _upper(integrity.get("state") or "UNKNOWN")
    runtime_status = _upper(runtime.get("status") or "UNKNOWN")
    sha_present = bool(_clean(runtime.get("sha"), 160))

    if checkpoint_conflict:
        state = "CONFLICT"
    elif integrity_state == "MISMATCH":
        state = "INTEGRITY_MISMATCH"
    elif runtime_status == "CONFIRMED" and not sha_present:
        state = "UNSAFE_WRITE"
    elif integrity_state == "MIGRATION_REQUIRED":
        state = "MIGRATION_REQUIRED"
    elif runtime_status == "CONFIRMED" and integrity_state == "CONFIRMED":
        state = "PROTECTED"
    elif runtime_status == "NOT_FOUND":
        state = "INITIAL_CREATE"
    else:
        state = "UNKNOWN"

    write_safe = state in {"PROTECTED", "MIGRATION_REQUIRED", "INITIAL_CREATE"} and not checkpoint_conflict

    return {
        "schema": SCHEMA,
        "state": state,
        "runtime_status": runtime_status,
        "integrity_state": integrity_state,
        "sha_present": sha_present,
        "checkpoint_dirty": bool(checkpoint_dirty),
        "checkpoint_conflict": bool(checkpoint_conflict),
        "write_safe_precondition": bool(write_safe),
        "requires_explicit_save_approval": True,
        "automatic_overwrite": False,
        "automatic_delete": False,
        "executes_action": False,
    }


def rollback_governance_snapshot(
    incident_snapshot: Mapping[str, Any] | None,
    publication_truth: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    incidents = dict(incident_snapshot or {})
    publication = dict(publication_truth or {})
    recommended = bool(incidents.get("rollback_review_recommended", False))
    has_critical = bool(incidents.get("has_critical", False))
    can_claim_live = bool(publication.get("can_claim_latest_main_live", False))

    if recommended and has_critical:
        state = "REVIEW_URGENT"
    elif recommended:
        state = "REVIEW"
    elif has_critical:
        state = "INCIDENT_REVIEW"
    else:
        state = "STANDBY"

    return {
        "schema": SCHEMA,
        "state": state,
        "review_recommended": recommended,
        "has_critical_incident": has_critical,
        "production_identity_confirmed": can_claim_live,
        "reasons": [str(x) for x in list(incidents.get("rollback_reasons") or [])[:10]],
        "automatic_rollback": False,
        "automatic_deploy": False,
        "requires_human_approval": True,
        "executes_action": False,
    }


def degraded_mode_snapshot(
    *,
    data_guardian: Mapping[str, Any] | None,
    memory_protection: Mapping[str, Any] | None,
    incident_snapshot: Mapping[str, Any] | None,
    critical_surfaces: Mapping[str, Any] | None = None,
    release_gate: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    data = dict(data_guardian or {})
    memory = dict(memory_protection or {})
    incidents = dict(incident_snapshot or {})
    surfaces = dict(critical_surfaces or {})
    gate = dict(release_gate or {})

    data_state = _upper(data.get("state") or "UNKNOWN")
    memory_state = _upper(memory.get("state") or "UNKNOWN")
    gate_state = _upper(gate.get("state") or "UNKNOWN")
    surface_counts = surfaces.get("counts") if isinstance(surfaces.get("counts"), Mapping) else {}
    surface_problem = int(surface_counts.get("DEGRADED") or 0) + int(surface_counts.get("UNAVAILABLE") or 0)
    critical_incident = bool(incidents.get("has_critical", False))

    fail_closed = bool(
        critical_incident
        or data_state == "FAIL_CLOSED"
        or memory_state in {"CONFLICT", "INTEGRITY_MISMATCH", "UNSAFE_WRITE"}
    )
    degraded = bool(
        fail_closed
        or data_state in {"DEGRADED_SAFE", "UNKNOWN"}
        or surface_problem > 0
        or gate_state not in {"COMPLETE", ""}
    )
    state = "FAIL_CLOSED" if fail_closed else "DEGRADED_SAFE" if degraded else "NORMAL"

    return {
        "schema": SCHEMA,
        "state": state,
        "can_explain": True,
        "can_read_local_memory": memory_state != "INTEGRITY_MISMATCH",
        "can_save_checkpoint": bool(memory.get("write_safe_precondition", False)) and not fail_closed,
        "can_use_external_model": not fail_closed,
        "can_claim_production_ready": bool(
            gate.get("release_claim_allowed", False)
            and state == "NORMAL"
        ),
        "can_authorize_market_action": False,
        "can_auto_repair": False,
        "can_auto_rollback": False,
        "real_orders_enabled": False,
        "executes_action": False,
    }


def build_default_source_observations(
    *,
    system_context: Mapping[str, Any] | None,
    market_context: Mapping[str, Any] | None,
    provider_status: Mapping[str, Any] | None,
    runtime_result: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    system = dict(system_context or {})
    market = dict(market_context or {})
    provider = dict(provider_status or {})
    runtime = dict(runtime_result or {})
    supplied = system.get("source_observations")
    rows = [
        dict(x) for x in list(supplied or [])
        if isinstance(x, Mapping)
    ]

    rows.extend([
        {
            "source": "app_build",
            "claim": "source_build",
            "value": system.get("source_build") or "",
            "truth_state": "CONFIRMED" if system.get("source_build") else "UNKNOWN",
            "available": bool(system.get("source_build")),
            "healthy": True if system.get("source_build") else None,
            "criticality": "HIGH",
        },
        {
            "source": "runtime_checkpoint",
            "claim": "runtime_checkpoint_status",
            "value": runtime.get("status") or "UNKNOWN",
            "truth_state": "CONFIRMED" if runtime.get("status") else "UNKNOWN",
            "available": runtime.get("status") not in {"ERROR", "UNAVAILABLE", None},
            "healthy": runtime.get("status") in {"CONFIRMED", "NOT_FOUND"},
            "criticality": "CRITICAL",
        },
        {
            "source": "market_context",
            "claim": "market_freshness",
            "value": bool(market.get("fresh_confirmed", False)),
            "truth_state": "CONFIRMED",
            "available": True,
            "healthy": bool(market.get("fresh_confirmed", False)),
            "criticality": "HIGH",
            "detail": _clean(market.get("summary") or "Sem leitura fresca confirmada."),
        },
        {
            "source": "model_provider",
            "claim": "external_model_readiness",
            "value": provider.get("state") or "UNKNOWN",
            "truth_state": "CONFIRMED",
            "available": True,
            "healthy": provider.get("state") in {"ZERO_COST_LOCAL", "EXTERNAL_READY"},
            "criticality": "MEDIUM",
        },
    ])
    return rows


def reliability_snapshot(
    *,
    system_context: Mapping[str, Any] | None,
    market_context: Mapping[str, Any] | None,
    provider_status: Mapping[str, Any] | None,
    runtime_result: Mapping[str, Any] | None,
    budget: Mapping[str, Any] | None,
    incident_snapshot: Mapping[str, Any] | None,
    checkpoint_dirty: bool = False,
    checkpoint_conflict: bool = False,
) -> dict[str, Any]:
    system = dict(system_context or {})
    observations = build_default_source_observations(
        system_context=system,
        market_context=market_context,
        provider_status=provider_status,
        runtime_result=runtime_result,
    )
    data = data_guardian_snapshot(observations)
    cost = cost_guardian_snapshot(budget, provider_status, observations)
    memory = memory_protection_snapshot(
        runtime_result,
        checkpoint_dirty=checkpoint_dirty,
        checkpoint_conflict=checkpoint_conflict,
    )
    rollback = rollback_governance_snapshot(
        incident_snapshot,
        system.get("publication_truth") if isinstance(system.get("publication_truth"), Mapping) else {},
    )
    degraded = degraded_mode_snapshot(
        data_guardian=data,
        memory_protection=memory,
        incident_snapshot=incident_snapshot,
        critical_surfaces=(
            system.get("critical_surfaces")
            if isinstance(system.get("critical_surfaces"), Mapping)
            else {}
        ),
        release_gate=(
            system.get("release_gate")
            if isinstance(system.get("release_gate"), Mapping)
            else {}
        ),
    )

    if degraded["state"] == "FAIL_CLOSED":
        posture = "CRITICAL"
    elif degraded["state"] == "DEGRADED_SAFE":
        posture = "DEGRADED"
    elif data["state"] == "CONTROLLED" and memory["state"] == "PROTECTED":
        posture = "CONTROLLED"
    else:
        posture = "UNKNOWN"

    actions: list[str] = []
    actions.extend(list(data.get("next_actions") or []))
    if memory["state"] == "CONFLICT":
        actions.append("Resolver conflito do Checkpoint antes de persistir.")
    elif memory["state"] == "INTEGRITY_MISMATCH":
        actions.append("Preservar evidência e revisar integridade antes de qualquer escrita.")
    if rollback["review_recommended"]:
        actions.append("Revisar plano de rollback; nenhuma reversão é automática.")
    if cost["state"] in {"WARNING", "BLOCKED_LIMIT"}:
        actions.append("Revisar orçamento/quota antes de usar recurso pago ou limitado.")

    dedup: list[str] = []
    for item in actions:
        if item and item not in dedup:
            dedup.append(item)

    return {
        "schema": SCHEMA,
        "posture": posture,
        "data_guardian": data,
        "cost_guardian": cost,
        "memory_protection": memory,
        "rollback_governance": rollback,
        "degraded_mode": degraded,
        "next_actions": dedup[:10],
        "automatic_failover": False,
        "automatic_repair": False,
        "automatic_rollback": False,
        "automatic_paid_fallback": False,
        "real_orders_enabled": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "SOURCE_STATES",
    "TRUTH_STATES",
    "normalize_source_observation",
    "normalize_source_observations",
    "reconcile_sources",
    "data_guardian_snapshot",
    "cost_guardian_snapshot",
    "memory_protection_snapshot",
    "rollback_governance_snapshot",
    "degraded_mode_snapshot",
    "build_default_source_observations",
    "reliability_snapshot",
]
