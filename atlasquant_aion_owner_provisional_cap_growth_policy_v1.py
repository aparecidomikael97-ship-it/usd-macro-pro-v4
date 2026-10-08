"""Provisional owner-funded budget growth policy for AION, planning-only V1.

No customer billing is accessed or authenticated, no approval can be granted,
no real budget is increased, and no spending/deploy is ever executed here.
"""
from __future__ import annotations

from datetime import date
import re
from typing import Any, Mapping, Sequence

SCHEMA = "ATLASQUANT_AION_OWNER_PROVISIONAL_CAP_GROWTH_POLICY_V1"
OWNER_FUNDED_INITIAL_CAP_CENTS = 20_000
MIN_PAID_MONTHS = 2
MAX_PROPOSAL_STEP_MULTIPLIER = 2
MAX_AMOUNT_CENTS = 10**12
MONTH_RE = re.compile(r"20[0-9]{2}-(?:0[1-9]|1[0-2])\Z")
CUSTOMER_KEY_RE = re.compile(r"[0-9a-f]{64}\Z")
MONTH_FIELDS = {
    "month", "customer_payment_received_cents", "fully_loaded_costs_and_taxes_cents",
    "payments_reconciled", "costs_and_taxes_reconciled", "paying_customer_keys",
}


def _money(value: Any, *, positive: bool = False) -> bool:
    return type(value) is int and (0 < value if positive else 0 <= value) and value <= MAX_AMOUNT_CENTS


def _month_number(value: Any) -> int | None:
    if type(value) is not str or not MONTH_RE.fullmatch(value):
        return None
    year, month = map(int, value.split("-"))
    return year * 12 + month - 1


def _previous_closed_month(as_of: str) -> int | None:
    try:
        parsed = date.fromisoformat(as_of)
        if type(as_of) is not str or parsed.isoformat() != as_of:
            return None
        return parsed.year * 12 + parsed.month - 2
    except (TypeError, ValueError):
        return None


def evaluate_owner_cap_growth_review(
    *,
    as_of: str,
    paid_months: Sequence[Mapping[str, Any]],
    declared_current_cap_cents: int,
    proposed_cap_cents: int,
    available_working_capital_cents: int | None,
) -> dict[str, Any]:
    """Review eligibility, never spending permission or real financial proof.

    Customer keys are SHA-256-format *opaque references*, not raw identifiers.
    All reconciliation flags and amounts are declarations, not verified here.
    """
    blockers: list[str] = []
    previous_month = _previous_closed_month(as_of)
    if previous_month is None:
        blockers.append("REVIEW_DATE_INVALID")
    if not _money(declared_current_cap_cents, positive=True) or declared_current_cap_cents < OWNER_FUNDED_INITIAL_CAP_CENTS:
        blockers.append("DECLARED_CURRENT_CAP_INVALID")
    if not _money(proposed_cap_cents, positive=True):
        blockers.append("PROPOSED_CAP_INVALID")
    if (_money(declared_current_cap_cents, positive=True)
            and _money(proposed_cap_cents, positive=True)):
        if proposed_cap_cents <= declared_current_cap_cents:
            blockers.append("INCREASE_REQUIRED_FOR_GROWTH_REVIEW")
        if proposed_cap_cents > declared_current_cap_cents * MAX_PROPOSAL_STEP_MULTIPLIER:
            blockers.append("PROPOSAL_STEP_TOO_LARGE")
    if not _money(available_working_capital_cents):
        blockers.append("WORKING_CAPITAL_UNVERIFIED")
    elif _money(proposed_cap_cents, positive=True) and available_working_capital_cents < proposed_cap_cents:
        blockers.append("WORKING_CAPITAL_BELOW_PROPOSED_MONTHLY_CAP")

    if type(paid_months) not in (list, tuple) or len(paid_months) != MIN_PAID_MONTHS:
        blockers.append("EXACTLY_TWO_PAID_MONTHS_REQUIRED")
        paid_months = []

    seen_months: set[int] = set()
    paid_customer_sets: list[set[str]] = []
    months: list[int] = []
    declared_profit_cents = 0
    for index, raw in enumerate(paid_months):
        if not isinstance(raw, Mapping) or set(raw) != MONTH_FIELDS:
            blockers.append(f"MONTH_EXACT_FIELDS_REQUIRED:{index}")
            continue
        row = dict(raw)
        period = _month_number(row["month"])
        if period is None:
            blockers.append(f"MONTH_FORMAT_INVALID:{index}")
        elif period in seen_months:
            blockers.append("DUPLICATE_ACCOUNTING_MONTH")
        else:
            seen_months.add(period)
            months.append(period)
        receipts = row["customer_payment_received_cents"]
        full_costs = row["fully_loaded_costs_and_taxes_cents"]
        if not _money(receipts, positive=True):
            blockers.append(f"SETTLED_RECEIPTS_REQUIRED:{index}")
        if not _money(full_costs):
            blockers.append(f"FULL_COSTS_INVALID:{index}")
        if row["payments_reconciled"] is not True or row["costs_and_taxes_reconciled"] is not True:
            blockers.append(f"PAYMENT_AND_COST_RECONCILIATION_REQUIRED:{index}")
        if _money(receipts, positive=True) and _money(full_costs):
            margin = receipts - full_costs
            if margin <= 0:
                blockers.append(f"NONPOSITIVE_MONTHLY_NET_RESULT:{index}")
            else:
                declared_profit_cents += margin

        keys = row["paying_customer_keys"]
        if (type(keys) not in (list, tuple) or not 1 <= len(keys) <= 100
                or any(type(k) is not str or not CUSTOMER_KEY_RE.fullmatch(k) for k in keys)):
            blockers.append(f"OPAQUE_PAYING_CUSTOMERS_REQUIRED:{index}")
        elif len(set(keys)) != len(keys):
            blockers.append(f"DUPLICATE_PAYING_CUSTOMER:{index}")
        else:
            paid_customer_sets.append(set(keys))

    if len(months) == MIN_PAID_MONTHS:
        if max(months) - min(months) != 1:
            blockers.append("PAID_MONTHS_MUST_BE_CONSECUTIVE")
        if previous_month is not None and max(months) != previous_month:
            blockers.append("TWO_MOST_RECENT_CLOSED_MONTHS_REQUIRED")
    if len(paid_customer_sets) == MIN_PAID_MONTHS and not (paid_customer_sets[0] & paid_customer_sets[1]):
        blockers.append("NO_CONTINUING_PAYING_CUSTOMER")

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": SCHEMA,
        "status": "ELIGIBLE_FOR_OWNER_REVIEW_ONLY" if not blockers else "NOT_ELIGIBLE_FOR_REVIEW",
        "blockers": blockers,
        "owner_funded_initial_cap_brl_cents": OWNER_FUNDED_INITIAL_CAP_CENTS,
        "current_production_cap_changed": False,
        "declared_current_cap_brl_cents": declared_current_cap_cents if _money(declared_current_cap_cents, positive=True) else None,
        "proposed_cap_brl_cents": proposed_cap_cents if _money(proposed_cap_cents, positive=True) else None,
        "consecutive_paid_months_required": MIN_PAID_MONTHS,
        "declared_positive_net_result_brl_cents": declared_profit_cents if not blockers else None,
        "receipts_and_costs_independently_verified": False,
        "customer_identity_independently_verified": False,
        "available_working_capital_independently_verified": False,
        "requires_independent_reconciliation": True,
        "requires_explicit_human_owner_approval": True,
        "requires_separate_supplier_purchase_approval": True,
        "budget_increase_approved": False,
        "paid_api_call_authorized": False,
        "subscription_purchase_authorized": False,
        "automatic_cap_escalation_enabled": False,
        "executes_action": False,
    }
