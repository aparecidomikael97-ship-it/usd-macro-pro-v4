"""AION BUSINESS Capacity Live Metrics Binding V1.

Read-only bridge from externally attested operational metrics into the existing
Capacity & Scale Manager.

The module does not probe infrastructure, call providers, modify quotas, admit
customers, increase budget, bill, deploy or activate runtime. It only validates
caller-supplied evidence and converts it into the existing capacity planner
inputs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

from atlasquant_aion_business_capacity_scale_manager import (
    evaluate_capacity_scale,
)
from atlasquant_aion_finops_live_cost_ledger import SCHEMA as FINOPS_LEDGER_SCHEMA

SCHEMA = "ATLASQUANT_AION_BUSINESS_CAPACITY_LIVE_METRICS_BINDING_V1"
VERSION = "1"

ALLOWED_SOURCES = (
    "FINOPS",
    "SUPPORT",
    "INFRA",
    "INCIDENTS",
)
MAX_AGE_HOURS = 24.0
MAX_TENANTS = 10


def _clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _num(value: Any, *, minimum: float = 0.0, maximum: float | None = None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number < minimum:
        return None
    if maximum is not None and number > maximum:
        return None
    return number


def _parse_time(value: Any) -> datetime | None:
    token = _clean(value, 80)
    if not token:
        return None
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def live_capacity_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "CAPACITY_LIVE_METRICS_CONTRACT_DEFINED",
        "sources": list(ALLOWED_SOURCES),
        "default_max_age_hours": MAX_AGE_HOURS,
        "max_tenants": MAX_TENANTS,
        "external_probe_executed_here": False,
        "automatic_customer_admission": False,
        "automatic_budget_increase": False,
        "automatic_quota_change": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def metrics_source_attestation(
    *,
    source_type: Any,
    source_ref: Any,
    authentication_verified: Any,
    read_only_scope_verified: Any,
    write_scope_present: Any,
    observed_at: Any,
) -> dict[str, Any]:
    source = _clean(source_type, 80).upper()
    ref = _clean(source_ref, 300)
    observed = _parse_time(observed_at)
    gates = {
        "source_allowed": source in ALLOWED_SOURCES,
        "source_ref_present": bool(ref),
        "authentication_verified": authentication_verified is True,
        "read_only_scope_verified": read_only_scope_verified is True,
        "write_scope_absent": write_scope_present is False,
        "observed_at_valid": observed is not None,
    }
    ready = all(gates.values())
    payload = {
        "source_type": source,
        "source_ref": ref,
        "observed_at": observed.isoformat() if observed else "",
    } if ready else {}
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "METRICS_SOURCE_ATTESTATION_READY" if ready else "METRICS_SOURCE_ATTESTATION_BLOCKED",
        "source_type": source if ready else "",
        "source_ref": ref if ready else "",
        "observed_at": observed.isoformat() if ready and observed else "",
        "gates": gates,
        "attestation_digest": _digest(payload) if ready else "",
        "external_probe_executed_by_module": False,
        "write_scope_present": False if ready else None,
        "executes_action": False,
    }


def normalize_live_capacity_snapshot(
    *,
    tenant_metrics: Sequence[Mapping[str, Any]] | None,
    platform_metrics: Mapping[str, Any] | None,
    source_attestations: Sequence[Mapping[str, Any]] | None,
    now: datetime | None = None,
    max_age_hours: Any = MAX_AGE_HOURS,
) -> dict[str, Any]:
    current = now.astimezone(timezone.utc) if isinstance(now, datetime) else datetime.now(timezone.utc)
    max_age = _num(max_age_hours, minimum=0.01, maximum=168.0)
    blockers: list[str] = []
    if max_age is None:
        blockers.append("MAX_AGE_INVALID")
        max_age = MAX_AGE_HOURS

    attested: dict[str, dict[str, Any]] = {}
    for raw in list(source_attestations or []):
        row = _mapping(raw)
        if row.get("schema") != SCHEMA or row.get("state") != "METRICS_SOURCE_ATTESTATION_READY":
            continue
        source = _clean(row.get("source_type"), 80).upper()
        if source in ALLOWED_SOURCES:
            attested[source] = row

    required_sources = {"FINOPS", "SUPPORT", "INFRA", "INCIDENTS"}
    if not required_sources.issubset(attested):
        blockers.append("REQUIRED_SOURCE_ATTESTATION_MISSING")

    raw_tenants = [dict(x) for x in list(tenant_metrics or []) if isinstance(x, Mapping)]
    if not raw_tenants:
        blockers.append("TENANT_METRICS_REQUIRED")
    if len(raw_tenants) > MAX_TENANTS:
        blockers.append("TENANT_LIMIT_EXCEEDED")
        raw_tenants = raw_tenants[:MAX_TENANTS]

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(raw_tenants, start=1):
        tenant = _clean(row.get("tenant_id"), 120)
        cost = _num(row.get("current_month_cost_brl"), maximum=100_000_000)
        utilization = _num(row.get("max_utilization_pct"), maximum=100)
        incidents = row.get("active_high_severity_incidents")
        observed = _parse_time(row.get("observed_at"))
        finops_digest = _clean(row.get("finops_cost_digest"), 128).lower()

        if not tenant or tenant in seen:
            blockers.append(f"tenant_{index}_invalid_or_duplicate")
            continue
        seen.add(tenant)
        if cost is None:
            blockers.append(f"tenant_{index}_cost_invalid")
            continue
        if utilization is None:
            blockers.append(f"tenant_{index}_utilization_invalid")
            continue
        if isinstance(incidents, bool) or not isinstance(incidents, int) or incidents < 0:
            blockers.append(f"tenant_{index}_incidents_invalid")
            continue
        if observed is None:
            blockers.append(f"tenant_{index}_observed_at_invalid")
            continue
        age_hours = max(0.0, (current - observed).total_seconds() / 3600)
        if age_hours > max_age:
            blockers.append(f"tenant_{index}_stale")
            continue
        if len(finops_digest) != 64 or any(ch not in "0123456789abcdef" for ch in finops_digest):
            blockers.append(f"tenant_{index}_finops_digest_invalid")
            continue

        normalized.append({
            "tenant_id": tenant,
            "current_month_cost_brl": round(cost, 2),
            "max_utilization_pct": round(utilization, 4),
            "active_high_severity_incidents": incidents,
            "observed_at": observed.isoformat(),
            "age_hours": round(age_hours, 3),
            "finops_cost_digest": finops_digest,
        })

    platform = _mapping(platform_metrics)
    shared_cost = _num(platform.get("shared_platform_cost_brl"), maximum=100_000_000)
    support_available = _num(platform.get("available_support_hours"), maximum=100_000)
    infra_headroom = _num(platform.get("infra_headroom_pct"), maximum=100)
    observed_platform = _parse_time(platform.get("observed_at"))

    if shared_cost is None:
        blockers.append("PLATFORM_SHARED_COST_INVALID")
    if support_available is None:
        blockers.append("PLATFORM_SUPPORT_CAPACITY_INVALID")
    if infra_headroom is None:
        blockers.append("PLATFORM_INFRA_HEADROOM_INVALID")
    if observed_platform is None:
        blockers.append("PLATFORM_OBSERVED_AT_INVALID")
    elif max(0.0, (current - observed_platform).total_seconds() / 3600) > max_age:
        blockers.append("PLATFORM_METRICS_STALE")

    ready = bool(normalized and not blockers)
    payload = {
        "tenants": normalized,
        "platform": {
            "shared_platform_cost_brl": shared_cost,
            "available_support_hours": support_available,
            "infra_headroom_pct": infra_headroom,
            "observed_at": observed_platform.isoformat() if observed_platform else "",
        },
        "attestation_digests": sorted(
            str(attested[source].get("attestation_digest") or "")
            for source in sorted(required_sources)
        ),
        "max_age_hours": max_age,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "CAPACITY_LIVE_METRICS_SNAPSHOT_READY" if ready else "CAPACITY_LIVE_METRICS_SNAPSHOT_BLOCKED",
        "tenant_metrics": normalized,
        "platform_metrics": payload.get("platform", {}) if ready else {},
        "tenant_count": len(normalized),
        "blockers": blockers,
        "snapshot_digest": _digest(payload) if ready else "",
        "measurement_ref": (
            f"capacity-live://{_digest(payload)[:24]}" if ready else ""
        ),
        "truth_state": "EXTERNALLY_ATTESTED_READ_ONLY_INPUT" if ready else "UNVERIFIED",
        "automatic_customer_admission": False,
        "automatic_budget_increase": False,
        "automatic_quota_change": False,
        "executes_action": False,
    }


def evaluate_capacity_from_live_metrics(
    capacity_review: Mapping[str, Any] | None,
    live_snapshot: Mapping[str, Any] | None,
    *,
    approved_monthly_budget_cap_brl: Any,
    support_hours_per_new_tenant: Any,
    infra_load_pct_per_new_tenant: Any,
    estimated_new_tenant_cost_brl: Any,
    expected_new_tenant_revenue_brl: Any,
) -> dict[str, Any]:
    snap = _mapping(live_snapshot)
    if snap.get("schema") != SCHEMA or snap.get("state") != "CAPACITY_LIVE_METRICS_SNAPSHOT_READY":
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "LIVE_CAPACITY_EVALUATION_BLOCKED",
            "reason": "LIVE_METRICS_SNAPSHOT_NOT_READY",
            "automatic_customer_admission": False,
            "executes_action": False,
        }

    platform = _mapping(snap.get("platform_metrics"))
    plan = evaluate_capacity_scale(
        capacity_review,
        usage_rows=list(snap.get("tenant_metrics") or []),
        measurement_ref=snap.get("measurement_ref"),
        approved_monthly_budget_cap_brl=approved_monthly_budget_cap_brl,
        shared_platform_cost_brl=platform.get("shared_platform_cost_brl"),
        available_support_hours=platform.get("available_support_hours"),
        support_hours_per_new_tenant=support_hours_per_new_tenant,
        infra_headroom_pct=platform.get("infra_headroom_pct"),
        infra_load_pct_per_new_tenant=infra_load_pct_per_new_tenant,
        estimated_new_tenant_cost_brl=estimated_new_tenant_cost_brl,
        expected_new_tenant_revenue_brl=expected_new_tenant_revenue_brl,
    )

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "LIVE_CAPACITY_REVIEW_READY"
            if plan.get("state") == "CAPACITY_SCALE_ADMISSION_READY"
            else "LIVE_CAPACITY_REVIEW_BLOCKED"
        ),
        "live_snapshot_digest": snap.get("snapshot_digest"),
        "capacity_plan": plan,
        "safe_additional_tenants": int(plan.get("safe_additional_tenants") or 0),
        "automatic_customer_admission": False,
        "customer_admission_authorized": False,
        "automatic_budget_increase": False,
        "automatic_quota_change": False,
        "billing_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "ALLOWED_SOURCES",
    "MAX_AGE_HOURS",
    "live_capacity_policy",
    "metrics_source_attestation",
    "normalize_live_capacity_snapshot",
    "evaluate_capacity_from_live_metrics",
]
