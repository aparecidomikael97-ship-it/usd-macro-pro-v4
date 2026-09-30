"""AION BUSINESS capacity and quota guardrail V1.

Administrative, fail-closed review of per-tenant usage quotas and cost budgets
bound to the latest verified expansion ledger state.

No quota is applied here. The module does not change runtime, billing, tenants,
traffic, deploys, integrations or external systems.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math
import re

LEDGER_SCHEMA = "ATLASQUANT_AION_BUSINESS_EXPANSION_CYCLE_AUDIT_LEDGER_V1"
SCHEMA = "ATLASQUANT_AION_BUSINESS_CAPACITY_QUOTA_GUARDRAIL_V1"
VERSION = "1"

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")
MAX_BOUNDED_TENANTS = 10

REQUIRED_QUOTA_FIELDS = (
    "tenant_id",
    "max_ai_requests",
    "max_integration_calls",
    "max_workflow_runs",
    "max_storage_mb",
    "ai_cost_budget",
    "integration_cost_budget",
    "support_cost_budget",
    "infra_cost_budget",
    "expected_revenue",
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def capacity_policy_requirements() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "CAPACITY_POLICY_REQUIRED",
        "required_quota_fields": list(REQUIRED_QUOTA_FIELDS),
        "max_bounded_tenants": MAX_BOUNDED_TENANTS,
        "minimum_margin_pct_must_be_explicit": True,
        "quota_application_authorized": False,
        "billing_authorized": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


def build_capacity_quota_review(
    ledger_audit: Mapping[str, Any] | None,
    *,
    quota_rows: Sequence[Mapping[str, Any]] | None,
    minimum_margin_pct: Any,
    reserve_capacity_pct: Any,
) -> dict[str, Any]:
    audit = _mapping(ledger_audit)
    rows = list(quota_rows or [])
    minimum_margin = _number(minimum_margin_pct)
    reserve_pct = _number(reserve_capacity_pct)

    ledger_digest = _clean(audit.get("ledger_digest"), 128).lower()
    tenant_ids = [
        _clean(item, 120)
        for item in list(audit.get("last_verified_tenant_ids") or [])
        if _clean(item, 120)
    ]

    ledger_ok = bool(
        audit.get("schema") == LEDGER_SCHEMA
        and audit.get("state") == "LEDGER_INTEGRITY_VERIFIED"
        and audit.get("integrity_verified") is True
        and _DIGEST64.fullmatch(ledger_digest)
        and 1 <= len(tenant_ids) <= MAX_BOUNDED_TENANTS
        and len(set(tenant_ids)) == len(tenant_ids)
        and audit.get("automatic_expansion_allowed") is False
        and audit.get("scope_expansion_authorized") is False
        and audit.get("expansion_execution_authorized") is False
        and audit.get("client_actions_authorized") is False
        and audit.get("billing_authorized") is False
        and audit.get("executes_action") is False
    )

    policy_ok = bool(
        minimum_margin is not None
        and 0 <= minimum_margin < 100
        and reserve_pct is not None
        and 0 <= reserve_pct < 100
    )

    normalized: list[dict[str, Any]] = []
    row_blockers: list[str] = []
    seen: set[str] = set()

    for index, raw in enumerate(rows, start=1):
        row = _mapping(raw)
        tenant_id = _clean(row.get("tenant_id"), 120)
        if not tenant_id:
            row_blockers.append(f"row_{index}_tenant_id_missing")
            continue
        if tenant_id in seen:
            row_blockers.append(f"row_{index}_duplicate_tenant")
        seen.add(tenant_id)

        usage = {}
        for field in (
            "max_ai_requests",
            "max_integration_calls",
            "max_workflow_runs",
            "max_storage_mb",
        ):
            value = _number(row.get(field))
            if value is None or value <= 0 or not value.is_integer():
                row_blockers.append(f"row_{index}_{field}_invalid")
            usage[field] = int(value) if value is not None and value > 0 and value.is_integer() else 0

        money = {}
        for field in (
            "ai_cost_budget",
            "integration_cost_budget",
            "support_cost_budget",
            "infra_cost_budget",
            "expected_revenue",
        ):
            value = _number(row.get(field))
            if value is None or value < 0:
                row_blockers.append(f"row_{index}_{field}_invalid")
                value = 0.0
            money[field] = round(float(value), 2)

        if money["expected_revenue"] <= 0:
            row_blockers.append(f"row_{index}_expected_revenue_must_be_positive")

        total_budgeted_cost = round(
            money["ai_cost_budget"]
            + money["integration_cost_budget"]
            + money["support_cost_budget"]
            + money["infra_cost_budget"],
            2,
        )
        budgeted_margin_pct = (
            round(
                ((money["expected_revenue"] - total_budgeted_cost)
                 / money["expected_revenue"]) * 100,
                4,
            )
            if money["expected_revenue"] > 0
            else -100.0
        )
        reserve_adjusted_cost = (
            round(total_budgeted_cost / (1 - reserve_pct / 100), 2)
            if reserve_pct is not None and 0 <= reserve_pct < 100
            else total_budgeted_cost
        )
        reserve_adjusted_margin_pct = (
            round(
                ((money["expected_revenue"] - reserve_adjusted_cost)
                 / money["expected_revenue"]) * 100,
                4,
            )
            if money["expected_revenue"] > 0
            else -100.0
        )

        if (
            minimum_margin is not None
            and reserve_adjusted_margin_pct < minimum_margin
        ):
            row_blockers.append(f"row_{index}_minimum_margin_not_met")

        normalized.append({
            "tenant_id": tenant_id,
            **usage,
            **money,
            "total_budgeted_cost": total_budgeted_cost,
            "reserve_adjusted_cost": reserve_adjusted_cost,
            "budgeted_margin_pct": budgeted_margin_pct,
            "reserve_adjusted_margin_pct": reserve_adjusted_margin_pct,
        })

    quota_tenants = sorted(row["tenant_id"] for row in normalized)
    ledger_tenants = sorted(tenant_ids)
    tenant_set_ok = bool(
        rows
        and quota_tenants == ledger_tenants
        and len(quota_tenants) == len(set(quota_tenants))
    )

    blockers = []
    if not ledger_ok:
        blockers.append("verified_ledger_required")
    if not policy_ok:
        blockers.append("capacity_policy_invalid")
    if not tenant_set_ok:
        blockers.append("quota_tenant_set_must_match_ledger")
    blockers.extend(row_blockers)

    state = (
        "CAPACITY_QUOTA_REVIEW_READY"
        if not blockers
        else "CAPACITY_QUOTA_REVIEW_BLOCKED"
    )
    payload = {
        "ledger_digest": ledger_digest,
        "minimum_margin_pct": minimum_margin,
        "reserve_capacity_pct": reserve_pct,
        "quota_rows": sorted(normalized, key=lambda x: x["tenant_id"]),
    } if state == "CAPACITY_QUOTA_REVIEW_READY" else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "ledger_digest": ledger_digest if ledger_ok else "",
        "tenant_ids": ledger_tenants if ledger_ok else [],
        "minimum_margin_pct": minimum_margin if policy_ok else None,
        "reserve_capacity_pct": reserve_pct if policy_ok else None,
        "quota_rows": normalized if tenant_set_ok else [],
        "review_digest": _digest(payload) if payload else "",
        "blockers": blockers,
        "quota_application_authorized": False,
        "billing_authorized": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


def quota_application_review_packet(
    review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(review)
    digest = _clean(row.get("review_digest"), 128).lower()
    tenant_ids = [
        _clean(item, 120)
        for item in list(row.get("tenant_ids") or [])
        if _clean(item, 120)
    ]
    quota_rows = list(row.get("quota_rows") or [])

    ready = bool(
        row.get("schema") == SCHEMA
        and row.get("state") == "CAPACITY_QUOTA_REVIEW_READY"
        and _DIGEST64.fullmatch(digest)
        and 1 <= len(tenant_ids) <= MAX_BOUNDED_TENANTS
        and len(quota_rows) == len(tenant_ids)
        and sorted(_clean(item.get("tenant_id"), 120) for item in quota_rows)
        == sorted(tenant_ids)
        and row.get("quota_application_authorized") is False
        and row.get("billing_authorized") is False
        and row.get("automatic_expansion_allowed") is False
        and row.get("client_actions_authorized") is False
        and row.get("executes_action") is False
    )

    return {
        "schema": "ATLASQUANT_AION_BUSINESS_QUOTA_APPLICATION_REVIEW_V1",
        "state": "QUOTA_APPLICATION_DECISION_REQUIRED" if ready else "NOT_READY",
        "capacity_review_digest": digest if ready else "",
        "tenant_ids": tenant_ids if ready else [],
        "quota_application_authorized": False,
        "billing_authorized": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "LEDGER_SCHEMA",
    "MAX_BOUNDED_TENANTS",
    "REQUIRED_QUOTA_FIELDS",
    "capacity_policy_requirements",
    "build_capacity_quota_review",
    "quota_application_review_packet",
]
