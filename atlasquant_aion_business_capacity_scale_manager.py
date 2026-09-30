"""AION BUSINESS Capacity & Scale Manager V1.

Read-only planning contracts for deciding how many additional Business tenants
can be reviewed safely. The manager binds to an approved capacity/quota review
and combines budget, support, infrastructure, margin and current-tenant health.

It never provisions a tenant, accepts a customer, spends money, changes quotas,
alters billing/runtime, deploys, or calls external systems.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math
import re

CAPACITY_REVIEW_SCHEMA = "ATLASQUANT_AION_BUSINESS_CAPACITY_QUOTA_GUARDRAIL_V1"
SCHEMA = "ATLASQUANT_AION_BUSINESS_CAPACITY_SCALE_MANAGER_V1"
VERSION = "1"

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")
INITIAL_BUDGET_CAP_BRL = 200.0
MAX_BOUNDED_TENANTS = 10
MAX_TENANT_UTILIZATION_PCT = 85.0
MIN_INFRA_HEADROOM_AFTER_ADMISSION_PCT = 20.0


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def capacity_scale_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "CAPACITY_SCALE_EVIDENCE_REQUIRED",
        "initial_budget_cap_brl": INITIAL_BUDGET_CAP_BRL,
        "max_bounded_tenants": MAX_BOUNDED_TENANTS,
        "max_tenant_utilization_pct": MAX_TENANT_UTILIZATION_PCT,
        "min_infra_headroom_after_admission_pct": MIN_INFRA_HEADROOM_AFTER_ADMISSION_PCT,
        "automatic_customer_admission": False,
        "automatic_budget_increase": False,
        "automatic_quota_change": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def evaluate_capacity_scale(
    capacity_review: Mapping[str, Any] | None,
    *,
    usage_rows: Sequence[Mapping[str, Any]] | None,
    measurement_ref: Any,
    approved_monthly_budget_cap_brl: Any,
    shared_platform_cost_brl: Any,
    available_support_hours: Any,
    support_hours_per_new_tenant: Any,
    infra_headroom_pct: Any,
    infra_load_pct_per_new_tenant: Any,
    estimated_new_tenant_cost_brl: Any,
    expected_new_tenant_revenue_brl: Any,
) -> dict[str, Any]:
    review = _mapping(capacity_review)
    rows = list(usage_rows or [])
    measurement = _clean(measurement_ref, 300)

    review_digest = _clean(review.get("review_digest"), 128).lower()
    tenant_ids = [
        _clean(item, 120)
        for item in list(review.get("tenant_ids") or [])
        if _clean(item, 120)
    ]
    min_margin = _number(review.get("minimum_margin_pct"))
    reserve_pct = _number(review.get("reserve_capacity_pct"))
    ledger_digest = _clean(review.get("ledger_digest"), 128).lower()
    quota_rows = list(review.get("quota_rows") or [])
    canonical_quota_rows = [
        dict(item) for item in quota_rows if isinstance(item, Mapping)
    ]
    expected_review_digest = _digest({
        "ledger_digest": ledger_digest,
        "minimum_margin_pct": min_margin,
        "reserve_capacity_pct": reserve_pct,
        "quota_rows": sorted(
            canonical_quota_rows,
            key=lambda item: str(item.get("tenant_id") or ""),
        ),
    })

    review_ok = bool(
        review.get("schema") == CAPACITY_REVIEW_SCHEMA
        and review.get("state") == "CAPACITY_QUOTA_REVIEW_READY"
        and _DIGEST64.fullmatch(review_digest)
        and review_digest == expected_review_digest
        and _DIGEST64.fullmatch(ledger_digest)
        and 1 <= len(tenant_ids) <= MAX_BOUNDED_TENANTS
        and len(set(tenant_ids)) == len(tenant_ids)
        and min_margin is not None
        and 0 <= min_margin < 100
        and reserve_pct is not None
        and 0 <= reserve_pct < 100
        and review.get("quota_application_authorized") is False
        and review.get("billing_authorized") is False
        and review.get("automatic_expansion_allowed") is False
        and review.get("client_actions_authorized") is False
        and review.get("executes_action") is False
    )

    budget_cap = _number(approved_monthly_budget_cap_brl)
    shared_platform_cost = _number(shared_platform_cost_brl)
    support_available = _number(available_support_hours)
    support_per_new = _number(support_hours_per_new_tenant)
    infra_headroom = _number(infra_headroom_pct)
    infra_per_new = _number(infra_load_pct_per_new_tenant)
    new_cost = _number(estimated_new_tenant_cost_brl)
    new_revenue = _number(expected_new_tenant_revenue_brl)

    policy_values_ok = bool(
        budget_cap is not None
        and 0 < budget_cap <= INITIAL_BUDGET_CAP_BRL
        and shared_platform_cost is not None
        and shared_platform_cost >= 0
        and support_available is not None
        and support_available >= 0
        and support_per_new is not None
        and support_per_new > 0
        and infra_headroom is not None
        and 0 <= infra_headroom <= 100
        and infra_per_new is not None
        and infra_per_new > 0
        and new_cost is not None
        and new_cost > 0
        and new_revenue is not None
        and new_revenue > 0
    )

    usage_blockers: list[str] = []
    normalized_usage: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(rows, start=1):
        row = _mapping(raw)
        tenant = _clean(row.get("tenant_id"), 120)
        actual_cost = _number(row.get("current_month_cost_brl"))
        utilization = _number(row.get("max_utilization_pct"))
        incidents = row.get("active_high_severity_incidents")
        if not tenant or tenant in seen:
            usage_blockers.append(f"row_{index}_tenant_invalid_or_duplicate")
        seen.add(tenant)
        if actual_cost is None or actual_cost < 0:
            usage_blockers.append(f"row_{index}_cost_invalid")
            actual_cost = 0.0
        if utilization is None or not 0 <= utilization <= 100:
            usage_blockers.append(f"row_{index}_utilization_invalid")
            utilization = 100.0
        if isinstance(incidents, bool) or not isinstance(incidents, int) or incidents < 0:
            usage_blockers.append(f"row_{index}_incidents_invalid")
            incidents = 1

        normalized_usage.append({
            "tenant_id": tenant,
            "current_month_cost_brl": round(actual_cost, 2),
            "max_utilization_pct": round(utilization, 4),
            "active_high_severity_incidents": incidents,
        })

    usage_tenants = sorted(row["tenant_id"] for row in normalized_usage)
    tenant_set_ok = bool(
        rows
        and usage_tenants == sorted(tenant_ids)
        and len(usage_tenants) == len(set(usage_tenants))
    )
    current_health_ok = bool(
        tenant_set_ok
        and not usage_blockers
        and all(
            row["max_utilization_pct"] <= MAX_TENANT_UTILIZATION_PCT
            and row["active_high_severity_incidents"] == 0
            for row in normalized_usage
        )
    )

    tenant_cost = round(
        sum(row["current_month_cost_brl"] for row in normalized_usage),
        2,
    )
    current_cost = round(
        tenant_cost + (shared_platform_cost or 0.0),
        2,
    )
    remaining_budget = (
        max(0.0, round(budget_cap - current_cost, 2))
        if budget_cap is not None
        else 0.0
    )

    tenant_slots = max(0, MAX_BOUNDED_TENANTS - len(tenant_ids))
    budget_slots = (
        max(0, math.floor(remaining_budget / new_cost))
        if new_cost and new_cost > 0
        else 0
    )
    support_slots = (
        max(0, math.floor(support_available / support_per_new))
        if support_available is not None
        and support_per_new is not None
        and support_per_new > 0
        else 0
    )
    usable_infra = (
        max(0.0, infra_headroom - MIN_INFRA_HEADROOM_AFTER_ADMISSION_PCT)
        if infra_headroom is not None
        else 0.0
    )
    infra_slots = (
        max(0, math.floor(usable_infra / infra_per_new))
        if infra_per_new is not None and infra_per_new > 0
        else 0
    )

    projected_margin_pct = (
        round(((new_revenue - new_cost) / new_revenue) * 100, 4)
        if new_revenue is not None
        and new_revenue > 0
        and new_cost is not None
        else -100.0
    )
    margin_ok = bool(
        min_margin is not None
        and projected_margin_pct >= min_margin
    )

    gates = {
        "capacity_review_valid": review_ok,
        "measurement_reference_present": bool(measurement),
        "policy_values_valid": policy_values_ok,
        "usage_tenant_set_matches_review": tenant_set_ok,
        "current_tenants_healthy": current_health_ok,
        "new_tenant_margin_meets_floor": margin_ok,
        "budget_has_capacity": budget_slots > 0,
        "support_has_capacity": support_slots > 0,
        "infrastructure_has_capacity": infra_slots > 0,
        "bounded_tenant_slot_available": tenant_slots > 0,
    }
    blockers = [name for name, passed in gates.items() if not passed]
    blockers.extend(usage_blockers)

    safe_additional = (
        min(tenant_slots, budget_slots, support_slots, infra_slots)
        if not blockers
        else 0
    )
    state = (
        "CAPACITY_SCALE_ADMISSION_READY"
        if safe_additional > 0
        else "CAPACITY_SCALE_ADMISSION_BLOCKED"
    )

    payload = {
        "capacity_review_digest": review_digest,
        "measurement_ref": measurement,
        "tenant_ids": sorted(tenant_ids),
        "current_month_cost_brl": current_cost,
        "tenant_month_cost_brl": tenant_cost,
        "shared_platform_cost_brl": shared_platform_cost,
        "approved_monthly_budget_cap_brl": budget_cap,
        "available_support_hours": support_available,
        "support_hours_per_new_tenant": support_per_new,
        "infra_headroom_pct": infra_headroom,
        "infra_load_pct_per_new_tenant": infra_per_new,
        "estimated_new_tenant_cost_brl": new_cost,
        "expected_new_tenant_revenue_brl": new_revenue,
        "safe_additional_tenants": safe_additional,
    } if state == "CAPACITY_SCALE_ADMISSION_READY" else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "gates": gates,
        "blockers": blockers,
        "capacity_review_digest": review_digest if review_ok else "",
        "measurement_ref": measurement if measurement else "",
        "current_tenant_count": len(tenant_ids) if review_ok else 0,
        "tenant_slots": tenant_slots,
        "current_month_cost_brl": current_cost,
        "tenant_month_cost_brl": tenant_cost,
        "shared_platform_cost_brl": shared_platform_cost,
        "approved_monthly_budget_cap_brl": budget_cap,
        "remaining_budget_brl": remaining_budget,
        "budget_slots": budget_slots,
        "support_slots": support_slots,
        "infra_slots": infra_slots,
        "projected_new_tenant_margin_pct": projected_margin_pct,
        "safe_additional_tenants": safe_additional,
        "plan_digest": _digest(payload) if payload else "",
        "automatic_customer_admission": False,
        "automatic_budget_increase": False,
        "automatic_quota_change": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def prepare_customer_admission_review(
    scale_plan: Mapping[str, Any] | None,
    *,
    requested_new_tenants: Any,
    candidate_refs: Sequence[str] | None = None,
) -> dict[str, Any]:
    row = _mapping(scale_plan)
    digest = _clean(row.get("plan_digest"), 128).lower()
    safe = row.get("safe_additional_tenants")
    requested = (
        requested_new_tenants
        if isinstance(requested_new_tenants, int)
        and not isinstance(requested_new_tenants, bool)
        else -1
    )
    candidates = [
        _clean(item, 120)
        for item in list(candidate_refs or [])
        if _clean(item, 120)
    ]

    ready = bool(
        row.get("schema") == SCHEMA
        and row.get("state") == "CAPACITY_SCALE_ADMISSION_READY"
        and _DIGEST64.fullmatch(digest)
        and isinstance(safe, int)
        and safe > 0
        and 1 <= requested <= safe
        and len(candidates) == requested
        and len(set(candidates)) == len(candidates)
        and row.get("automatic_customer_admission") is False
        and row.get("automatic_budget_increase") is False
        and row.get("automatic_quota_change") is False
        and row.get("billing_authorized") is False
        and row.get("executes_action") is False
    )

    return {
        "schema": "ATLASQUANT_AION_BUSINESS_CUSTOMER_ADMISSION_REVIEW_V1",
        "state": "EXPLICIT_CUSTOMER_ADMISSION_DECISION_REQUIRED" if ready else "NOT_READY",
        "capacity_plan_digest": digest if ready else "",
        "requested_new_tenants": requested if ready else 0,
        "candidate_refs": candidates if ready else [],
        "customer_admission_authorized": False,
        "automatic_customer_admission": False,
        "billing_authorized": False,
        "budget_increase_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "INITIAL_BUDGET_CAP_BRL",
    "MAX_BOUNDED_TENANTS",
    "MAX_TENANT_UTILIZATION_PCT",
    "MIN_INFRA_HEADROOM_AFTER_ADMISSION_PCT",
    "capacity_scale_policy",
    "evaluate_capacity_scale",
    "prepare_customer_admission_review",
]
