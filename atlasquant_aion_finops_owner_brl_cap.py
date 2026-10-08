"""Read-only owner-wide BRL cost envelope, independent of provider billing.

This complements atlasquant_aion_finops_metering (USD scoped metering).
It does NOT fetch exchange rates, authorize spend, reserve funds, call a
provider, change subscriptions, or enforce a production admission gate.
Evidence must be assembled and authenticated by a trusted caller.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_OWNER_BRL_CAP_V1"
MONTHLY_CAP_CENTS = 20_000  # R$200.00; changes require specific owner approval.
MAX_SNAPSHOT_AGE_MINUTES = 60
WARNING_PCT = 70
DEGRADE_PCT = 85
MAX_INPUT_CENTS = 10**12


def _cents(value: Any) -> int | None:
    if type(value) is not int or not 0 <= value <= MAX_INPUT_CENTS:
        return None
    return value


def _month(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 7:
        return False
    try:
        date.fromisoformat(value + "-01")
        return value[4] == "-"
    except ValueError:
        return False


def evaluate_owner_brl_cap(
    evidence: Mapping[str, Any] | None,
    request: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Pure decision for the caller to enforce; never an authority grant."""
    e = dict(evidence or {})
    q = dict(request or {})
    reasons: list[str] = []
    warnings: list[str] = []
    total: int | None = None

    month = q.get("month")
    estimate = _cents(q.get("estimated_brl_cents"))
    mode = q.get("mode")
    if not _month(month):
        reasons.append("REQUEST_MONTH_INVALID")
    if estimate is None:
        reasons.append("REQUEST_COST_UNKNOWN_OR_INVALID")
    if mode not in ("PAID", "LOCAL_ZERO_VENDOR_CHARGE"):
        reasons.append("REQUEST_MODE_INVALID")

    # This exemption is ONLY for caller-verified operations with no vendor
    # billing; upstream must authenticate the classification and pricing.
    if mode == "LOCAL_ZERO_VENDOR_CHARGE" and estimate == 0 and not reasons:
        return _result(
            state="ALLOW_LOCAL_ONLY",
            reasons=[], warnings=["LOCAL_HARDWARE_POWER_NOT_INCLUDED"],
            month=month, estimate=0, projected=None,
        )
    if mode == "LOCAL_ZERO_VENDOR_CHARGE" and estimate != 0:
        reasons.append("LOCAL_MODE_MUST_HAVE_ZERO_VENDOR_CHARGE")

    if e.get("state") != "VERIFIED":
        reasons.append("EVIDENCE_NOT_VERIFIED")
    if e.get("scope") != "OWNER_ALL_ENVIRONMENTS":
        reasons.append("OWNER_WIDE_SCOPE_REQUIRED")
    if e.get("month") != month or not _month(e.get("month")):
        reasons.append("MONTH_MISMATCH")
    if e.get("currency") != "BRL":
        reasons.append("BRL_RECONCILIATION_REQUIRED")
    if e.get("coverage_complete") is not True:
        reasons.append("PROVIDER_COVERAGE_UNKNOWN")
    if e.get("fx_reconciled") is not True:
        reasons.append("FX_EVIDENCE_REQUIRED")
    if e.get("non_overlapping_categories") is not True:
        reasons.append("DOUBLE_COUNT_RISK")

    age = e.get("snapshot_age_minutes")
    if type(age) is not int or age < 0 or age > MAX_SNAPSHOT_AGE_MINUTES:
        reasons.append("SNAPSHOT_MISSING_OR_STALE")

    fields = (
        "settled_brl_cents",
        "committed_brl_cents",
        "reserved_brl_cents",
        "unbilled_estimate_brl_cents",
    )
    numbers = [_cents(e.get(field)) for field in fields]
    if any(value is None for value in numbers):
        reasons.append("OWNER_COST_COVERAGE_INVALID")
    if not reasons:
        total = sum(numbers) + estimate
        if total >= MONTHLY_CAP_CENTS:
            reasons.append("OWNER_MONTHLY_CAP_REACHED")
        elif total * 100 >= MONTHLY_CAP_CENTS * DEGRADE_PCT:
            warnings.append("LOW_COST_LOCAL_FIRST")
        elif total * 100 >= MONTHLY_CAP_CENTS * WARNING_PCT:
            warnings.append("BUDGET_WARNING")

    if reasons:
        state = "BLOCK_PAID"
    elif "LOW_COST_LOCAL_FIRST" in warnings:
        state = "DEGRADE_PAID"
    elif "BUDGET_WARNING" in warnings:
        state = "ALLOW_WITH_WARNING"
    else:
        state = "ALLOW_PRECHECK"
    return _result(
        state=state, reasons=reasons, warnings=warnings,
        month=month, estimate=estimate, projected=total,
    )


def _result(
    *, state: str, reasons: list[str], warnings: list[str],
    month: Any, estimate: int | None, projected: int | None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "month": month,
        "currency": "BRL",
        "owner_monthly_cap_cents": MONTHLY_CAP_CENTS,
        "prospective_cost_cents": estimate,
        "projected_total_cents": projected,
        "reasons": reasons,
        "warnings": warnings,
        "requires_caller_enforcement": True,
        "evidence_is_not_provider_invoice": True,
        "automatic_model_switch": False,
        "automatic_charge": False,
        "automatic_budget_change": False,
        "grants_spending_authority": False,
        "executes_action": False,
    }


__all__ = ["SCHEMA", "MONTHLY_CAP_CENTS", "evaluate_owner_brl_cap"]
