"""AION FinOps Budget Governor & Treasury Policy V1.

Administrative, read-only planning contracts for:
- monthly ecosystem cost ceiling;
- cost visibility by category;
- treasury separation between Business, Trader and Investments;
- bounded initial Trader capital allocation.

No function spends money, transfers funds, changes billing, places trades,
admits customers, deploys, or calls external systems.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA = "ATLASQUANT_AION_FINOPS_BUDGET_GOVERNOR_V1"
VERSION = "1"

INITIAL_MONTHLY_ECOSYSTEM_CAP_BRL = 200.0
INITIAL_MAX_TRADER_ALLOCATION_PCT = 30.0
BUDGET_WARNING_PCT = 70.0
BUDGET_CRITICAL_PCT = 85.0


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _clean(value: Any, limit: int = 200) -> str:
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


def finops_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "FINOPS_BUDGET_GOVERNOR_ACTIVE_AS_POLICY",
        "initial_monthly_ecosystem_cap_brl": INITIAL_MONTHLY_ECOSYSTEM_CAP_BRL,
        "initial_max_trader_allocation_pct": INITIAL_MAX_TRADER_ALLOCATION_PCT,
        "business_revenue_primary_ecosystem_funding": True,
        "trader_profit_retained_in_trader_bucket": True,
        "investments_preserve_and_build_patrimony": True,
        "trade_return_target_is_guarantee": False,
        "automatic_spending": False,
        "automatic_transfer": False,
        "automatic_trade": False,
        "automatic_budget_increase": False,
        "executes_action": False,
    }


def evaluate_monthly_budget(
    cost_rows: Sequence[Mapping[str, Any]] | None,
    *,
    monthly_cap_brl: Any = INITIAL_MONTHLY_ECOSYSTEM_CAP_BRL,
    planned_new_commitment_brl: Any = 0.0,
) -> dict[str, Any]:
    cap = _num(monthly_cap_brl)
    commitment = _num(planned_new_commitment_brl)
    blockers: list[str] = []

    if cap is None or cap <= 0 or cap > INITIAL_MONTHLY_ECOSYSTEM_CAP_BRL:
        blockers.append("MONTHLY_CAP_OUTSIDE_APPROVED_BOUNDARY")
        cap = INITIAL_MONTHLY_ECOSYSTEM_CAP_BRL
    if commitment is None or commitment < 0:
        blockers.append("PLANNED_COMMITMENT_INVALID")
        commitment = 0.0

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(list(cost_rows or []), start=1):
        row = _mapping(raw)
        category = _clean(row.get("category"), 80).casefold()
        amount = _num(row.get("amount_brl"))
        recurring = row.get("recurring") is True
        if not category or category in seen:
            blockers.append(f"row_{index}_category_invalid_or_duplicate")
            continue
        seen.add(category)
        if amount is None or amount < 0:
            blockers.append(f"row_{index}_amount_invalid")
            continue
        normalized.append({
            "category": category,
            "amount_brl": round(amount, 2),
            "recurring": recurring,
        })

    current = round(sum(row["amount_brl"] for row in normalized), 2)
    projected = round(current + commitment, 2)
    usage_pct = round((projected / cap) * 100, 2) if cap else 100.0
    remaining = round(max(0.0, cap - projected), 2)

    if projected > cap:
        state = "BUDGET_BLOCKED"
    elif usage_pct >= BUDGET_CRITICAL_PCT:
        state = "BUDGET_CRITICAL_REVIEW_REQUIRED"
    elif usage_pct >= BUDGET_WARNING_PCT:
        state = "BUDGET_WARNING"
    else:
        state = "BUDGET_WITHIN_POLICY"

    allowed = not blockers and projected <= cap
    if blockers:
        state = "BUDGET_BLOCKED"

    payload = {
        "cap_brl": cap,
        "rows": normalized,
        "planned_new_commitment_brl": round(commitment, 2),
        "projected_monthly_cost_brl": projected,
    } if allowed else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "allowed_for_admin_review": allowed,
        "monthly_cap_brl": cap,
        "current_monthly_cost_brl": current,
        "planned_new_commitment_brl": round(commitment, 2),
        "projected_monthly_cost_brl": projected,
        "usage_pct": usage_pct,
        "remaining_brl": remaining,
        "blockers": blockers,
        "budget_digest": _digest(payload) if payload else "",
        "automatic_spending": False,
        "automatic_budget_increase": False,
        "executes_action": False,
    }


def evaluate_trader_capital_allocation(
    *,
    total_ecosystem_capital_brl: Any,
    requested_trader_capital_brl: Any,
) -> dict[str, Any]:
    total = _num(total_ecosystem_capital_brl)
    requested = _num(requested_trader_capital_brl)
    blockers: list[str] = []

    if total is None or total <= 0:
        blockers.append("TOTAL_CAPITAL_INVALID")
        total = 0.0
    if requested is None or requested < 0:
        blockers.append("TRADER_ALLOCATION_INVALID")
        requested = 0.0

    requested_pct = round((requested / total) * 100, 4) if total > 0 else 0.0
    within_policy = bool(
        not blockers
        and requested_pct <= INITIAL_MAX_TRADER_ALLOCATION_PCT
    )
    if not within_policy and requested_pct > INITIAL_MAX_TRADER_ALLOCATION_PCT:
        blockers.append("TRADER_ALLOCATION_ABOVE_INITIAL_30_PERCENT_POLICY")

    max_amount = round(
        total * INITIAL_MAX_TRADER_ALLOCATION_PCT / 100,
        2,
    )

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "TRADER_ALLOCATION_WITHIN_POLICY"
            if within_policy
            else "TRADER_ALLOCATION_REVIEW_BLOCKED"
        ),
        "total_ecosystem_capital_brl": round(total, 2),
        "requested_trader_capital_brl": round(requested, 2),
        "requested_trader_allocation_pct": requested_pct,
        "initial_max_trader_allocation_pct": INITIAL_MAX_TRADER_ALLOCATION_PCT,
        "initial_max_trader_allocation_brl": max_amount,
        "blockers": blockers,
        "capital_transfer_authorized": False,
        "trade_authorized": False,
        "executes_action": False,
    }


def revenue_routing_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TREASURY_ROUTING_POLICY_DEFINED",
        "business_net_cash": {
            "role": "PRIMARY_ECOSYSTEM_FUNDING_SOURCE",
            "may_fund": [
                "aion_operations",
                "cash_reserve",
                "business_growth",
                "investments",
                "future_bounded_trader_allocation",
            ],
        },
        "trader_net_profit": {
            "role": "RETAIN_IN_TRADER_BUCKET",
            "may_fund": [
                "trader_reserve",
                "future_trader_scaling_after_validation",
            ],
        },
        "investment_income": {
            "role": "PATRIMONY_AND_REINVESTMENT",
            "may_fund": [
                "investment_reinvestment",
                "long_term_reserve",
            ],
        },
        "cross_bucket_transfer_automatic": False,
        "administrator_final_authority": True,
        "executes_action": False,
    }


def trade_target_snapshot(
    *,
    trader_capital_brl: Any,
    target_monthly_profit_brl: Any,
) -> dict[str, Any]:
    capital = _num(trader_capital_brl)
    target = _num(target_monthly_profit_brl)
    valid = bool(
        capital is not None
        and capital > 0
        and target is not None
        and target >= 0
    )
    target_pct = (
        round((target / capital) * 100, 4)
        if valid and capital
        else None
    )
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TRADE_TARGET_PLANNING_ONLY" if valid else "TRADE_TARGET_INVALID",
        "trader_capital_brl": round(capital, 2) if capital is not None else None,
        "target_monthly_profit_brl": round(target, 2) if target is not None else None,
        "implied_monthly_return_pct": target_pct,
        "guaranteed": False,
        "expected_return_claim": False,
        "requires_backtest_validation": True,
        "requires_risk_controls": True,
        "requires_live_track_record_before_income_dependency": True,
        "trade_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "INITIAL_MONTHLY_ECOSYSTEM_CAP_BRL",
    "INITIAL_MAX_TRADER_ALLOCATION_PCT",
    "finops_policy",
    "evaluate_monthly_budget",
    "evaluate_trader_capital_allocation",
    "revenue_routing_policy",
    "trade_target_snapshot",
]
