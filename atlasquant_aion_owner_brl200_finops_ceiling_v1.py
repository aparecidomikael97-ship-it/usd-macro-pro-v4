"""AION owner-funded BRL monthly spending ceiling — pure FinOps preflight V1.

No payment, provider call, pricing feed, autonomous fallback, budget change,
real-time billing authority, permanent reservation or production enforcement.
No input is independently authenticated. This is a fail-closed planning gate,
not a bank/credit-card spending limit or a guarantee of bills under R$ 200.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

SCHEMA = "ATLASQUANT_AION_OWNER_BRL200_FINOPS_CEILING_V1"
HARD_CAP_CENTS = 20_000
SOFT_CAP_CENTS = 14_000
CRITICAL_CAP_CENTS = 18_000
FX_BUFFER_PERCENT = 10
FX_MAX_AGE_DAYS = 3
MAX_ENTRIES = 1000
MONTH = re.compile(r"20[0-9]{2}-(0[1-9]|1[0-2])\Z")
CATEGORIES = {
    "hosting", "database", "storage", "ai_api", "voice_api",
    "video_api", "communications", "domain", "observability", "other",
}
STATUSES = {"COMMITTED", "RESERVED", "SETTLED"}
EVIDENCE = {"CONFIRMED", "ESTIMATED", "UNKNOWN"}
ROW_FIELDS = {
    "entry_id", "owner_id", "month", "category", "status",
    "evidence", "currency", "brl_cents", "usd_micros",
}
QUOTE_FIELDS = {"cost_type", "currency", "brl_cents", "usd_micros"}
BRL_INPUT = "BRL"
USD_INPUT = "USD"

def _digest(data: Any) -> str:
    return sha256(json.dumps(data, sort_keys=True, ensure_ascii=True,
                             separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def _int(value: Any, minimum: int = 0) -> bool:
    return type(value) is int and value >= minimum

def _str(value: Any, limit: int = 128) -> bool:
    return type(value) is str and 1 <= len(value) <= limit and value.strip() == value and "\x00" not in value

def _fx_rate(fx: Mapping[str, Any] | None, *, as_of: str) -> tuple[Decimal | None, list[str]]:
    if not isinstance(fx, Mapping):
        return None, ["USD_FX_SNAPSHOT_REQUIRED"]
    m = dict(fx)
    errors: list[str] = []
    if set(m) != {"rate_brl_per_usd", "observed_date", "source"}:
        errors.append("FX_SNAPSHOT_EXACT_FIELDS_REQUIRED")
    if not _str(m.get("source"), 100) or m.get("source") not in {"OWNER_QUOTE", "INVOICE"}:
        errors.append("FX_SOURCE_NOT_ESTABLISHED")
    rate = None
    try:
        if type(m.get("rate_brl_per_usd")) is not str:
            raise InvalidOperation
        rate = Decimal(m["rate_brl_per_usd"])
        if not rate.is_finite() or rate <= 0 or rate > 100 or rate.as_tuple().exponent < -6:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        errors.append("FX_RATE_INVALID")
    try:
        observed = date.fromisoformat(m.get("observed_date") if type(m.get("observed_date")) is str else "")
        now = date.fromisoformat(as_of)
        age = (now - observed).days
        if age < 0 or age > FX_MAX_AGE_DAYS:
            errors.append("FX_RATE_STALE_OR_FUTURE")
    except (TypeError, ValueError):
        errors.append("FX_DATE_INVALID")
    return rate, errors

def _brl_cents(currency: Any, brl_cents: Any, usd_micros: Any, fx: Decimal | None) -> tuple[int | None, str | None]:
    if currency == BRL_INPUT:
        if not _int(brl_cents) or usd_micros is not None:
            return None, "BRL_AMOUNT_INVALID"
        return brl_cents, None
    if currency == USD_INPUT:
        if not _int(usd_micros) or brl_cents is not None or fx is None:
            return None, "USD_AMOUNT_OR_FX_INVALID"
        # USD micros => USD, then BRL cents; conservatively round up and
        # add fixed 10% exchange fluctuation buffer. Input is a cost estimate.
        amount = (Decimal(usd_micros) * fx * Decimal("100")
                  * Decimal(100 + FX_BUFFER_PERCENT) /
                  (Decimal(1_000_000) * Decimal(100)))
        return int(amount.to_integral_value(rounding=ROUND_CEILING)), None
    return None, "UNSUPPORTED_CURRENCY"

def build_owner_monthly_budget(
    entries: Sequence[Mapping[str, Any]] | None, *,
    expected_month: str, trusted_owner_id: str, as_of: str,
    fx_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Conservative owner-funded liability forecast; never independently audited."""
    errors: list[str] = []
    if not _str(trusted_owner_id, 100):
        errors.append("OWNER_ID_REQUIRED")
    if type(expected_month) is not str or not MONTH.fullmatch(expected_month):
        errors.append("MONTH_INVALID")
    try:
        today = date.fromisoformat(as_of)
        if today.strftime("%Y-%m") != expected_month:
            errors.append("ACCOUNTING_MONTH_MISMATCH")
    except (ValueError, TypeError):
        errors.append("AS_OF_DATE_INVALID")
        today = None
    if type(entries) not in (list, tuple) or len(entries) > MAX_ENTRIES:
        errors.append("ENTRY_COLLECTION_INVALID")
        entries = []
    rows = []
    ids: dict[str, str] = {}
    total_cents = 0
    needs_fx = any(isinstance(x, Mapping) and x.get("currency") == USD_INPUT for x in entries)
    fx, fx_errors = _fx_rate(fx_snapshot, as_of=as_of) if needs_fx else (None, [])
    errors.extend(fx_errors)
    for index, raw in enumerate(entries):
        if not isinstance(raw, Mapping):
            errors.append(f"ENTRY_NOT_MAPPING:{index}")
            continue
        item = dict(raw)
        if set(item) != ROW_FIELDS:
            errors.append(f"ENTRY_EXACT_FIELDS_REQUIRED:{index}")
            continue
        row_errors = []
        for key in ("entry_id", "category"):
            if not _str(item.get(key)):
                row_errors.append("ENTRY_ID_OR_CATEGORY_INVALID")
        if item.get("category") not in CATEGORIES:
            row_errors.append("ENTRY_CATEGORY_UNRECOGNIZED")
        if item.get("owner_id") != trusted_owner_id:
            row_errors.append("OWNER_SCOPE_MISMATCH")
        if item.get("month") != expected_month:
            row_errors.append("ENTRY_MONTH_MISMATCH")
        if item.get("status") not in STATUSES:
            row_errors.append("ENTRY_STATUS_UNKNOWN")
        if item.get("evidence") not in EVIDENCE or item.get("evidence") == "UNKNOWN":
            row_errors.append("AMOUNT_EVIDENCE_MISSING")
        amount, amount_error = _brl_cents(item.get("currency"),
                                          item.get("brl_cents"), item.get("usd_micros"), fx)
        if amount_error:
            row_errors.append(amount_error)
        if row_errors:
            errors.extend(f"{code}:{index}" for code in row_errors)
            continue
        key = item["entry_id"]
        item_hash = _digest(item)
        previous = ids.get(key)
        if previous is not None:
            if previous != item_hash:
                errors.append("CONFLICTING_OBLIGATION_ID:" + str(index))
            continue
        ids[key] = item_hash
        total_cents += amount
        rows.append({"entry_id": key, "category": item["category"],
                     "status": item["status"], "evidence": item["evidence"],
                     "forecast_brl_cents": amount, "source_currency": item["currency"]})
    if total_cents > HARD_CAP_CENTS:
        errors.append("OWNER_MONTHLY_CAP_EXCEEDED")
    errors = list(dict.fromkeys(errors))
    state = "BLOCKED" if errors else ("CRITICAL" if total_cents >= CRITICAL_CAP_CENTS
                                   else "DEGRADE" if total_cents >= SOFT_CAP_CENTS
                                   else "WITHIN_TARGET_PROVISIONAL")
    return {
        "schema": SCHEMA, "state": state, "blockers": errors,
        "expected_month": expected_month, "owner_id": trusted_owner_id,
        "hard_cap_brl_cents": HARD_CAP_CENTS, "soft_cap_brl_cents": SOFT_CAP_CENTS,
        "critical_cap_brl_cents": CRITICAL_CAP_CENTS,
        "forecast_brl_cents": total_cents,
        "headroom_brl_cents": max(0, HARD_CAP_CENTS-total_cents),
        "entries_count": len(rows), "evidence_digest": _digest(rows),
        "unknown_other_bills_possible": True,
        "input_costs_independently_reconciled": False,
        "completeness_of_subscriptions_verified": False,
        "cap_is_real_payment_enforcement": False,
        "auto_spending_enabled": False,
        "automatic_paid_fallback_enabled": False,
        "executes_action": False,
    }

def preflight_owner_paid_request(
    budget: Mapping[str, Any] | None, *,
    quote: Mapping[str, Any] | None,
    fx_snapshot: Mapping[str, Any] | None = None,
    as_of: str,
) -> dict[str, Any]:
    """No paid request is executed or automatically approved, ever."""
    b = dict(budget) if isinstance(budget, Mapping) else {}
    q = dict(quote) if isinstance(quote, Mapping) else {}
    issues = []
    if b.get("schema") != SCHEMA or b.get("blockers") != []:
        issues.append("OWNER_BUDGET_NOT_READY")
    if (b.get("state") not in {"WITHIN_TARGET_PROVISIONAL", "DEGRADE", "CRITICAL"}
        or b.get("hard_cap_brl_cents") != HARD_CAP_CENTS
        or type(b.get("forecast_brl_cents")) is not int
        or b.get("forecast_brl_cents") < 0):
        issues.append("INVALID_OR_BLOCKED_BUDGET")
    if set(q) != QUOTE_FIELDS:
        issues.append("QUOTE_EXACT_FIELDS_REQUIRED")
    if q.get("cost_type") not in {"PAID_EXTERNAL", "LOCAL_ZERO_MARGINAL"}:
        issues.append("UNKNOWN_REQUEST_COST_TYPE")
    if q.get("cost_type") == "LOCAL_ZERO_MARGINAL":
        if q.get("currency") != "BRL" or q.get("brl_cents") != 0 or q.get("usd_micros") is not None:
            issues.append("LOCAL_ZERO_QUOTE_MUST_BE_ZERO")
    else:
        fx, fxerr = _fx_rate(fx_snapshot, as_of=as_of) if q.get("currency") == USD_INPUT else (None, [])
        issues.extend(fxerr)
    if q.get("cost_type") == "LOCAL_ZERO_MARGINAL" and not issues:
        return {"schema": SCHEMA, "decision": "LOCAL_ONLY_ADVISORY",
                "blockers": [], "approved_paid_spend_brl_cents": 0,
                "external_call_authorized": False, "executes_action": False}
    amount, error = _brl_cents(q.get("currency"), q.get("brl_cents"), q.get("usd_micros"),
                                fx if q.get("currency") == USD_INPUT else None)
    if error:
        issues.append(error)
    if amount is not None and _int(b.get("forecast_brl_cents")):
        if b["forecast_brl_cents"] + amount > HARD_CAP_CENTS:
            issues.append("PROJECTED_OWNER_CAP_EXCEEDED")
    else:
        issues.append("REQUEST_COST_UNVERIFIED")
    issues = list(dict.fromkeys(issues))
    return {
        "schema": SCHEMA,
        "decision": "BLOCK_PAID" if issues else "REQUIRES_SEPARATE_OWNER_APPROVAL",
        "blockers": issues,
        "requested_brl_cents_with_fx_buffer": amount,
        "approved_paid_spend_brl_cents": 0,
        "external_call_authorized": False,
        "production_ledger_reservation_recorded": False,
        "executes_action": False,
    }

def minimum_customer_monthly_margin(*, revenue_brl_cents: Any,
                                    operating_cost_brl_cents: Any) -> dict[str, Any]:
    """Conservative estimate only, excluding omitted taxes, support and overhead."""
    valid = _int(revenue_brl_cents) and revenue_brl_cents > 0 and _int(operating_cost_brl_cents)
    margin = (revenue_brl_cents-operating_cost_brl_cents) if valid else None
    return {
        "schema": SCHEMA,
        "state": "ESTIMATED_POSITIVE_MARGIN" if valid and margin > 0
                 else ("ESTIMATED_NONPOSITIVE_MARGIN" if valid else "BLOCKED"),
        "gross_margin_brl_cents": margin,
        "all_costs_and_taxes_confirmed": False,
        "customer_payment_received": False,
        "automatic_customer_charge": False,
        "customer_scale_authorized": False,
        "executes_action": False,
    }

def owner_budget_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA, "currency": "BRL", "hard_cap_brl_cents": HARD_CAP_CENTS,
        "soft_cap_brl_cents": SOFT_CAP_CENTS,
        "critical_cap_brl_cents": CRITICAL_CAP_CENTS,
        "monthly_owner_operating_costs_only": True,
        "excluded_hardware_internet_electricity": True,
        "production_enforcement_active": False,
        "real_billing_sources_connected": False,
        "automatic_provider_purchase": False,
        "automatic_paid_fallback": False,
        "automatic_customer_charge": False,
        "merges_or_deploys": False,
    }
