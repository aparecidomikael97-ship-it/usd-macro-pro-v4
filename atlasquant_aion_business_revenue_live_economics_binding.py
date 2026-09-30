"""AION BUSINESS Revenue Live Economics Binding V1.

Read-only bridge that replaces two manual Revenue Opportunity Engine inputs with
verified operational evidence:

- estimated_monthly_cost_brl is derived from selected entries in a verified
  FinOps live-cost ledger using explicit allocation percentages;
- capacity_ready is derived from a LIVE_CAPACITY_REVIEW_READY result.

Commercial price, startup budget and qualitative planning scores remain explicit
administrator inputs. This module does not contact prospects, change prices,
spend money, admit customers, charge, deploy or activate runtime.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

from atlasquant_aion_business_revenue_opportunity_engine import (
    evaluate_revenue_opportunity,
    rank_revenue_opportunities,
)
from atlasquant_aion_business_capacity_live_metrics_binding import (
    SCHEMA as LIVE_CAPACITY_SCHEMA,
)
from atlasquant_aion_finops_live_cost_ledger import (
    SCHEMA as FINOPS_LEDGER_SCHEMA,
    verify_hash_chained_ledger,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_REVENUE_LIVE_ECONOMICS_BINDING_V1"
VERSION = "1"

MAX_ALLOCATIONS_PER_OPPORTUNITY = 100
MAX_PORTFOLIO = 50


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


def live_economics_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "REVENUE_LIVE_ECONOMICS_CONTRACT_DEFINED",
        "monthly_cost_source": "VERIFIED_FINOPS_LEDGER_ALLOCATIONS",
        "capacity_source": "LIVE_CAPACITY_REVIEW",
        "commercial_price_source": "ADMIN_INPUT",
        "startup_budget_source": "ADMIN_INPUT",
        "allocation_percent_is_admin_input": True,
        "score_is_probability": False,
        "automatic_sale": False,
        "automatic_spend": False,
        "automatic_price_change": False,
        "automatic_customer_admission": False,
        "executes_action": False,
    }


def derive_opportunity_monthly_cost(
    ledger: Mapping[str, Any] | None,
    allocation_rows: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    ledger_row = _mapping(ledger)
    verified = verify_hash_chained_ledger(ledger_row)
    blockers: list[str] = []

    if verified.get("valid") is not True:
        blockers.append("FINOPS_LEDGER_NOT_VERIFIED")

    entries = ledger_row.get("entries")
    if not isinstance(entries, list):
        entries = []

    by_id: dict[str, dict[str, Any]] = {}
    if verified.get("valid") is True:
        for raw in entries:
            item = _mapping(raw)
            entry_id = _clean(item.get("entry_id"), 160)
            if entry_id:
                by_id[entry_id] = item

    rows = (
        [dict(x) for x in allocation_rows if isinstance(x, Mapping)]
        if isinstance(allocation_rows, Sequence)
        and not isinstance(allocation_rows, (str, bytes, bytearray))
        else []
    )
    if not rows:
        blockers.append("COST_ALLOCATIONS_REQUIRED")
    if len(rows) > MAX_ALLOCATIONS_PER_OPPORTUNITY:
        blockers.append("COST_ALLOCATION_LIMIT_EXCEEDED")
        rows = rows[:MAX_ALLOCATIONS_PER_OPPORTUNITY]

    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    total = 0.0

    for index, row in enumerate(rows, start=1):
        entry_id = _clean(row.get("entry_id"), 160)
        pct = _num(row.get("allocation_pct"), maximum=100)

        if not entry_id or entry_id in seen:
            blockers.append(f"allocation_{index}_entry_invalid_or_duplicate")
            continue
        seen.add(entry_id)

        entry = by_id.get(entry_id)
        if not entry:
            blockers.append(f"allocation_{index}_ledger_entry_not_found")
            continue
        if entry.get("recurring") is not True:
            blockers.append(f"allocation_{index}_nonrecurring_entry_for_monthly_cost")
            continue
        if pct is None or pct <= 0:
            blockers.append(f"allocation_{index}_pct_invalid")
            continue

        amount = _num(entry.get("amount_brl"), maximum=100_000_000)
        if amount is None:
            blockers.append(f"allocation_{index}_amount_invalid")
            continue

        allocated = round(amount * pct / 100.0, 2)
        total += allocated
        normalized.append({
            "entry_id": entry_id,
            "entry_digest": entry.get("entry_digest"),
            "provider_ref": entry.get("provider_ref"),
            "category": entry.get("category"),
            "source_amount_brl": round(amount, 2),
            "allocation_pct": round(pct, 4),
            "allocated_monthly_cost_brl": allocated,
        })

    ready = bool(normalized and not blockers)
    payload = {
        "ledger_digest": ledger_row.get("ledger_digest"),
        "allocations": normalized,
        "derived_monthly_cost_brl": round(total, 2),
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "OPPORTUNITY_MONTHLY_COST_DERIVED"
            if ready
            else "OPPORTUNITY_MONTHLY_COST_BLOCKED"
        ),
        "ledger_digest": ledger_row.get("ledger_digest") if ready else "",
        "allocations": normalized,
        "derived_monthly_cost_brl": round(total, 2) if ready else None,
        "cost_binding_digest": _digest(payload) if ready else "",
        "blockers": blockers,
        "allocation_percent_is_admin_input": True,
        "ledger_modified": False,
        "automatic_spend": False,
        "executes_action": False,
    }


def bind_revenue_opportunity_to_live_economics(
    opportunity: Mapping[str, Any] | None,
    *,
    ledger: Mapping[str, Any] | None,
    cost_allocations: Sequence[Mapping[str, Any]] | None,
    live_capacity_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw = _mapping(opportunity)
    cost = derive_opportunity_monthly_cost(ledger, cost_allocations)
    capacity = _mapping(live_capacity_review)

    capacity_ready = bool(
        capacity.get("schema") == LIVE_CAPACITY_SCHEMA
        and capacity.get("state") == "LIVE_CAPACITY_REVIEW_READY"
        and int(capacity.get("safe_additional_tenants") or 0) > 0
        and capacity.get("automatic_customer_admission") is False
        and capacity.get("customer_admission_authorized") is False
        and capacity.get("executes_action") is False
    )

    blockers: list[str] = []
    if cost.get("state") != "OPPORTUNITY_MONTHLY_COST_DERIVED":
        blockers.append("LIVE_COST_BINDING_NOT_READY")
    if not capacity_ready:
        blockers.append("LIVE_CAPACITY_NOT_READY")

    bound = dict(raw)
    if not blockers:
        bound["estimated_monthly_cost_brl"] = cost["derived_monthly_cost_brl"]
        bound["capacity_ready"] = True

    evaluated = (
        evaluate_revenue_opportunity(bound)
        if not blockers
        else {
            "state": "REVENUE_OPPORTUNITY_BLOCKED",
            "opportunity_id": _clean(raw.get("opportunity_id"), 120),
            "label": _clean(raw.get("label"), 180),
            "blockers": list(blockers),
            "score": None,
            "score_is_probability": False,
        }
    )

    if evaluated.get("state") != "REVENUE_OPPORTUNITY_ELIGIBLE":
        blockers.extend(
            item for item in list(evaluated.get("blockers") or [])
            if item not in blockers
        )

    ready = not blockers and evaluated.get("state") == "REVENUE_OPPORTUNITY_ELIGIBLE"
    payload = {
        "opportunity_id": evaluated.get("opportunity_id"),
        "cost_binding_digest": cost.get("cost_binding_digest"),
        "live_capacity_snapshot_digest": capacity.get("live_snapshot_digest"),
        "capacity_plan_digest": _mapping(capacity.get("capacity_plan")).get("plan_digest"),
        "evaluated": evaluated,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "LIVE_ECONOMICS_REVENUE_OPPORTUNITY_ELIGIBLE"
            if ready
            else "LIVE_ECONOMICS_REVENUE_OPPORTUNITY_BLOCKED"
        ),
        "opportunity": evaluated,
        "derived_monthly_cost_brl": cost.get("derived_monthly_cost_brl"),
        "cost_binding_digest": cost.get("cost_binding_digest") if ready else "",
        "live_capacity_snapshot_digest": (
            capacity.get("live_snapshot_digest") if capacity_ready else ""
        ),
        "safe_additional_tenants": (
            int(capacity.get("safe_additional_tenants") or 0)
            if capacity_ready
            else 0
        ),
        "blockers": blockers,
        "binding_digest": _digest(payload) if ready else "",
        "score_is_probability": False,
        "sales_forecast": False,
        "automatic_sale": False,
        "automatic_spend": False,
        "automatic_price_change": False,
        "automatic_customer_admission": False,
        "executes_action": False,
    }


def rank_live_economics_opportunities(
    bound_rows: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    rows = (
        [dict(x) for x in bound_rows if isinstance(x, Mapping)]
        if isinstance(bound_rows, Sequence)
        and not isinstance(bound_rows, (str, bytes, bytearray))
        else []
    )
    if not rows or len(rows) > MAX_PORTFOLIO:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "LIVE_ECONOMICS_PORTFOLIO_BLOCKED",
            "ranked": [],
            "blocked": [],
            "reason": "PORTFOLIO_SIZE_INVALID",
            "executes_action": False,
        }

    eligible_inputs: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    binding_digests: list[str] = []

    for row in rows:
        if (
            row.get("schema") == SCHEMA
            and row.get("state") == "LIVE_ECONOMICS_REVENUE_OPPORTUNITY_ELIGIBLE"
            and row.get("binding_digest")
        ):
            opportunity = _mapping(row.get("opportunity"))
            eligible_inputs.append({
                "opportunity_id": opportunity.get("opportunity_id"),
                "label": opportunity.get("label"),
                "opportunity_type": opportunity.get("opportunity_type"),
                "startup_cost_brl": opportunity.get("startup_cost_brl"),
                "available_startup_budget_brl": opportunity.get("available_startup_budget_brl"),
                "monthly_price_brl": opportunity.get("monthly_price_brl"),
                "estimated_monthly_cost_brl": opportunity.get("estimated_monthly_cost_brl"),
                "implementation_days": opportunity.get("implementation_days"),
                "minimum_margin_pct": opportunity.get("minimum_margin_pct"),
                "repeatability_pct": opportunity.get("score_components", {}).get("repeatability"),
                "evidence_readiness_pct": opportunity.get("score_components", {}).get("evidence_readiness"),
                "support_load_pct": (
                    100.0 - float(opportunity.get("score_components", {}).get("support_efficiency") or 0)
                ),
                "implementation_complexity_pct": (
                    100.0 - float(opportunity.get("score_components", {}).get("implementation_efficiency") or 0)
                ),
                "capacity_ready": True,
            })
            binding_digests.append(str(row.get("binding_digest")))
        else:
            blocked.append({
                "opportunity_id": _mapping(row.get("opportunity")).get("opportunity_id"),
                "blockers": list(row.get("blockers") or []),
            })

    if not eligible_inputs:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "NO_LIVE_ECONOMICS_ELIGIBLE_OPPORTUNITY",
            "ranked": [],
            "blocked": blocked,
            "automatic_sale": False,
            "executes_action": False,
        }

    ranked = rank_revenue_opportunities(eligible_inputs)
    payload = {
        "binding_digests": sorted(binding_digests),
        "ranked": ranked.get("ranked"),
    }

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_ADMIN_LIVE_REVENUE_PRIORITY_REVIEW"
            if ranked.get("state") == "READY_FOR_ADMIN_REVENUE_PRIORITY_REVIEW"
            else "LIVE_REVENUE_PRIORITY_BLOCKED"
        ),
        "ranked": ranked.get("ranked") or [],
        "blocked": blocked + list(ranked.get("blocked") or []),
        "top_opportunity_id": ranked.get("top_opportunity_id") or "",
        "portfolio_digest": _digest(payload),
        "score_is_probability": False,
        "top_is_sales_forecast": False,
        "top_is_automatic_decision": False,
        "administrator_final_authority": True,
        "automatic_sale": False,
        "automatic_spend": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "MAX_ALLOCATIONS_PER_OPPORTUNITY",
    "MAX_PORTFOLIO",
    "live_economics_policy",
    "derive_opportunity_monthly_cost",
    "bind_revenue_opportunity_to_live_economics",
    "rank_live_economics_opportunities",
]
