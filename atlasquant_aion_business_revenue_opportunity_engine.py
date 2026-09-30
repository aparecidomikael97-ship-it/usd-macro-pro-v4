"""AION BUSINESS Revenue Opportunity Engine V1.

Deterministic/read-only prioritization of service opportunities using explicit
administrator-supplied inputs. It is not a sales forecast, market prediction or
guarantee.

The engine first blocks opportunities that violate startup budget, minimum
margin or capacity. Only eligible opportunities receive a comparative planning
score.

No function contacts prospects, changes pricing, spends money, publishes,
charges, provisions tenants, deploys, or activates runtime.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import math

SCHEMA = "ATLASQUANT_AION_BUSINESS_REVENUE_OPPORTUNITY_ENGINE_V1"
VERSION = "1"

OPPORTUNITY_TYPES = (
    "B2B_AUTOMATION",
    "CONTENT_SERVICE",
    "ADMIN_AUTOMATION",
    "CUSTOM_B2B_SERVICE",
)

MAX_OPPORTUNITIES = 50


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


def _pct(value: Any) -> float | None:
    return _num(value, maximum=100.0)


def revenue_opportunity_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "REVENUE_OPPORTUNITY_POLICY_DEFINED",
        "strategy": "SERVICE_FIRST_RECURRING_B2B",
        "allowed_opportunity_types": list(OPPORTUNITY_TYPES),
        "dropshipping_priority": False,
        "physical_inventory_required": False,
        "score_is_probability": False,
        "sales_forecast": False,
        "automatic_sale": False,
        "automatic_spend": False,
        "automatic_price_change": False,
        "executes_action": False,
    }


def evaluate_revenue_opportunity(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(raw or {}) if isinstance(raw, Mapping) else {}

    opportunity_id = _clean(data.get("opportunity_id"), 120)
    label = _clean(data.get("label"), 180)
    opportunity_type = _clean(data.get("opportunity_type"), 80).upper()

    startup_cost = _num(data.get("startup_cost_brl"), maximum=10_000_000)
    available_budget = _num(data.get("available_startup_budget_brl"), maximum=10_000_000)
    monthly_price = _num(data.get("monthly_price_brl"), maximum=10_000_000)
    monthly_cost = _num(data.get("estimated_monthly_cost_brl"), maximum=10_000_000)
    implementation_days = _num(data.get("implementation_days"), maximum=3650)
    minimum_margin = _pct(data.get("minimum_margin_pct"))

    repeatability = _pct(data.get("repeatability_pct"))
    evidence_readiness = _pct(data.get("evidence_readiness_pct"))
    support_load = _pct(data.get("support_load_pct"))
    implementation_complexity = _pct(data.get("implementation_complexity_pct"))
    capacity_ready = data.get("capacity_ready") is True

    blockers: list[str] = []
    if not opportunity_id:
        blockers.append("OPPORTUNITY_ID_REQUIRED")
    if not label:
        blockers.append("LABEL_REQUIRED")
    if opportunity_type not in OPPORTUNITY_TYPES:
        blockers.append("OPPORTUNITY_TYPE_INVALID")

    required_numeric = {
        "startup_cost": startup_cost,
        "available_budget": available_budget,
        "monthly_price": monthly_price,
        "monthly_cost": monthly_cost,
        "implementation_days": implementation_days,
        "minimum_margin": minimum_margin,
        "repeatability": repeatability,
        "evidence_readiness": evidence_readiness,
        "support_load": support_load,
        "implementation_complexity": implementation_complexity,
    }
    if any(value is None for value in required_numeric.values()):
        blockers.append("OPPORTUNITY_INPUTS_INCOMPLETE")

    margin_pct = None
    monthly_contribution = None
    if monthly_price is not None and monthly_cost is not None and monthly_price > 0:
        monthly_contribution = round(monthly_price - monthly_cost, 2)
        margin_pct = round(monthly_contribution / monthly_price * 100, 4)
    elif monthly_price == 0:
        blockers.append("MONTHLY_PRICE_MUST_BE_POSITIVE")

    if startup_cost is not None and available_budget is not None and startup_cost > available_budget:
        blockers.append("STARTUP_COST_ABOVE_AVAILABLE_BUDGET")
    if margin_pct is not None and minimum_margin is not None and margin_pct < minimum_margin:
        blockers.append("MARGIN_BELOW_ADMIN_FLOOR")
    if not capacity_ready:
        blockers.append("CAPACITY_NOT_READY")
    if monthly_contribution is not None and monthly_contribution <= 0:
        blockers.append("MONTHLY_CONTRIBUTION_NOT_POSITIVE")

    eligible = not blockers
    score = None
    components: dict[str, float] = {}

    if eligible:
        if implementation_days <= 7:
            time_score = 100.0
        elif implementation_days <= 14:
            time_score = 85.0
        elif implementation_days <= 30:
            time_score = 65.0
        elif implementation_days <= 60:
            time_score = 40.0
        else:
            time_score = 20.0

        if available_budget <= 0:
            startup_efficiency = 100.0 if startup_cost == 0 else 0.0
        else:
            startup_efficiency = max(
                0.0,
                min(100.0, (1.0 - startup_cost / available_budget) * 100.0),
            )

        margin_score = max(0.0, min(100.0, margin_pct))
        support_efficiency = max(0.0, 100.0 - support_load)
        complexity_efficiency = max(0.0, 100.0 - implementation_complexity)

        components = {
            "margin": round(margin_score, 2),
            "time_to_cash": round(time_score, 2),
            "repeatability": round(repeatability, 2),
            "evidence_readiness": round(evidence_readiness, 2),
            "startup_efficiency": round(startup_efficiency, 2),
            "support_efficiency": round(support_efficiency, 2),
            "implementation_efficiency": round(complexity_efficiency, 2),
        }
        score = round(
            0.25 * margin_score
            + 0.20 * time_score
            + 0.15 * repeatability
            + 0.10 * evidence_readiness
            + 0.10 * startup_efficiency
            + 0.10 * support_efficiency
            + 0.10 * complexity_efficiency,
            2,
        )

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "REVENUE_OPPORTUNITY_ELIGIBLE" if eligible else "REVENUE_OPPORTUNITY_BLOCKED",
        "opportunity_id": opportunity_id,
        "label": label,
        "opportunity_type": opportunity_type,
        "startup_cost_brl": startup_cost,
        "available_startup_budget_brl": available_budget,
        "monthly_price_brl": monthly_price,
        "estimated_monthly_cost_brl": monthly_cost,
        "monthly_contribution_brl": monthly_contribution,
        "margin_pct": margin_pct,
        "minimum_margin_pct": minimum_margin,
        "implementation_days": implementation_days,
        "capacity_ready": capacity_ready,
        "score": score,
        "score_components": components,
        "score_is_probability": False,
        "sales_forecast": False,
        "blockers": blockers,
        "automatic_sale": False,
        "automatic_spend": False,
        "automatic_price_change": False,
        "executes_action": False,
    }


def rank_revenue_opportunities(
    opportunities: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    rows = (
        [dict(x) for x in opportunities if isinstance(x, Mapping)]
        if isinstance(opportunities, Sequence)
        and not isinstance(opportunities, (str, bytes, bytearray))
        else []
    )
    if not rows or len(rows) > MAX_OPPORTUNITIES:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "REVENUE_OPPORTUNITY_PORTFOLIO_BLOCKED",
            "ranked": [],
            "blocked": [],
            "reason": "PORTFOLIO_SIZE_INVALID",
            "executes_action": False,
        }

    evaluated = [evaluate_revenue_opportunity(row) for row in rows]
    eligible = [row for row in evaluated if row["state"] == "REVENUE_OPPORTUNITY_ELIGIBLE"]
    blocked = [row for row in evaluated if row["state"] == "REVENUE_OPPORTUNITY_BLOCKED"]

    ranked = sorted(
        eligible,
        key=lambda row: (
            -(row.get("score") or 0),
            row.get("startup_cost_brl") or 0,
            row.get("opportunity_id") or "",
        ),
    )

    ranked_view = []
    for index, row in enumerate(ranked, start=1):
        ranked_view.append({
            "rank": index,
            "opportunity_id": row["opportunity_id"],
            "label": row["label"],
            "opportunity_type": row["opportunity_type"],
            "score": row["score"],
            "margin_pct": row["margin_pct"],
            "monthly_contribution_brl": row["monthly_contribution_brl"],
            "startup_cost_brl": row["startup_cost_brl"],
            "implementation_days": row["implementation_days"],
            "score_components": row["score_components"],
        })

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_ADMIN_REVENUE_PRIORITY_REVIEW"
            if ranked_view
            else "NO_ELIGIBLE_REVENUE_OPPORTUNITY"
        ),
        "ranked": ranked_view,
        "blocked": [
            {
                "opportunity_id": row["opportunity_id"],
                "label": row["label"],
                "blockers": row["blockers"],
            }
            for row in blocked
        ],
        "eligible_count": len(ranked_view),
        "blocked_count": len(blocked),
        "top_opportunity_id": ranked_view[0]["opportunity_id"] if ranked_view else "",
        "top_is_sales_forecast": False,
        "top_is_automatic_decision": False,
        "administrator_final_authority": True,
        "automatic_sale": False,
        "executes_action": False,
    }


def opportunity_template_catalog() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "REVENUE_OPPORTUNITY_TEMPLATES_READY",
        "templates": [
            {
                "opportunity_id": "AION_ATTENDIMENTO_AUTOMACAO",
                "label": "AION Atendimento & Automação Comercial",
                "opportunity_type": "B2B_AUTOMATION",
                "inputs_required": True,
            },
            {
                "opportunity_id": "AION_CONTEUDO_ASSISTIDO",
                "label": "AION Conteúdo & Operação Assistida",
                "opportunity_type": "CONTENT_SERVICE",
                "inputs_required": True,
            },
            {
                "opportunity_id": "AION_ADMIN_AUTOMATION",
                "label": "AION Automação Administrativa",
                "opportunity_type": "ADMIN_AUTOMATION",
                "inputs_required": True,
            },
        ],
        "market_assumptions_embedded": False,
        "prices_embedded": False,
        "dropshipping_in_current_strategy": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "OPPORTUNITY_TYPES",
    "MAX_OPPORTUNITIES",
    "revenue_opportunity_policy",
    "evaluate_revenue_opportunity",
    "rank_revenue_opportunities",
    "opportunity_template_catalog",
]
