"""AION BUSINESS Client Finance Demo V1.

Pure/offline financial modeling for one demo client. It distinguishes revenue,
cost, margin and available contribution; it does not invoice, collect payment,
move money, publish, deploy or activate runtime.

All values are caller-supplied demo inputs and must never be presented as real
bookkeeping unless separately verified by an authorized financial source.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json

SCHEMA = "ATLASQUANT_AION_BUSINESS_CLIENT_FINANCE_DEMO_V1"
VERSION = "1"

PAYMENT_STATES = ("UNKNOWN", "CURRENT", "DUE_SOON", "OVERDUE_DEMO")
CAPACITY_STATES = ("HEALTHY", "WATCH", "AT_LIMIT", "UNKNOWN")


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _money(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except Exception:
        return None
    if number < 0 or number > 1_000_000_000:
        return None
    return round(number, 2)


def _number(value: Any, *, maximum: float | None = None) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except Exception:
        return None
    if number < 0:
        return None
    if maximum is not None and number > maximum:
        return None
    return number


def _digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def normalize_client_finance(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(raw or {}) if isinstance(raw, Mapping) else {}
    payment_state = _clean(data.get("payment_state"), 40).upper()
    if payment_state not in PAYMENT_STATES:
        payment_state = "UNKNOWN"

    row = {
        "company_name": _clean(data.get("company_name"), 120) or "Empresa Demo",
        "package_label": _clean(data.get("package_label"), 160) or "A DEFINIR",
        "implementation_revenue": _money(data.get("implementation_revenue")),
        "monthly_revenue": _money(data.get("monthly_revenue")),
        "product_cost": _money(data.get("product_cost")),
        "ai_cost": _money(data.get("ai_cost")),
        "integration_cost": _money(data.get("integration_cost")),
        "support_cost": _money(data.get("support_cost")),
        "media_cost": _money(data.get("media_cost")),
        "tool_cost": _money(data.get("tool_cost")),
        "refunds": _money(data.get("refunds")),
        "tax_estimate": _money(data.get("tax_estimate")),
        "other_costs": _money(data.get("other_costs")),
        "payment_state": payment_state,
        "monthly_requests": _number(data.get("monthly_requests"), maximum=100_000_000),
        "request_quota": _number(data.get("request_quota"), maximum=100_000_000),
        "support_hours": _number(data.get("support_hours"), maximum=10_000),
        "support_hour_quota": _number(data.get("support_hour_quota"), maximum=10_000),
        "truth_state": "DEMO_USER_INPUT",
        "real_financial_record": False,
    }
    required = ("monthly_revenue",)
    row["missing"] = [name for name in required if row[name] is None]
    return row


def client_economics(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    row = normalize_client_finance(raw)
    if row["missing"]:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "INCOMPLETE",
            "input": row,
            "economics": {},
            "capacity": {},
            "executes_action": False,
        }

    cost_fields = (
        "product_cost",
        "ai_cost",
        "integration_cost",
        "support_cost",
        "media_cost",
        "tool_cost",
        "refunds",
        "tax_estimate",
        "other_costs",
    )
    costs = {key: float(row[key] or 0) for key in cost_fields}
    total_costs = round(sum(costs.values()), 2)
    monthly_revenue = float(row["monthly_revenue"] or 0)
    implementation_revenue = float(row["implementation_revenue"] or 0)
    monthly_contribution = round(monthly_revenue - total_costs, 2)
    margin_pct = round((monthly_contribution / monthly_revenue * 100), 2) if monthly_revenue > 0 else None

    req = row["monthly_requests"]
    req_quota = row["request_quota"]
    hrs = row["support_hours"]
    hrs_quota = row["support_hour_quota"]

    req_pct = round(req / req_quota * 100, 1) if req is not None and req_quota not in (None, 0) else None
    hrs_pct = round(hrs / hrs_quota * 100, 1) if hrs is not None and hrs_quota not in (None, 0) else None
    utilization_values = [x for x in (req_pct, hrs_pct) if x is not None]
    utilization = max(utilization_values) if utilization_values else None

    if utilization is None:
        capacity_state = "UNKNOWN"
    elif utilization >= 100:
        capacity_state = "AT_LIMIT"
    elif utilization >= 80:
        capacity_state = "WATCH"
    else:
        capacity_state = "HEALTHY"

    if monthly_contribution < 0:
        profitability_state = "NEGATIVE"
    elif margin_pct is not None and margin_pct < 20:
        profitability_state = "THIN"
    elif margin_pct is not None:
        profitability_state = "POSITIVE"
    else:
        profitability_state = "UNKNOWN"

    economics = {
        "implementation_revenue": implementation_revenue,
        "monthly_revenue": monthly_revenue,
        "cost_breakdown": costs,
        "total_monthly_costs": total_costs,
        "monthly_contribution": monthly_contribution,
        "margin_pct": margin_pct,
        "profitability_state": profitability_state,
        "payment_state": row["payment_state"],
        "available_for_reinvestment": None,
        "available_for_reinvestment_state": "NOT_CALCULATED_HERE",
    }
    capacity = {
        "monthly_requests": req,
        "request_quota": req_quota,
        "request_utilization_pct": req_pct,
        "support_hours": hrs,
        "support_hour_quota": hrs_quota,
        "support_utilization_pct": hrs_pct,
        "max_utilization_pct": utilization,
        "state": capacity_state,
    }

    result = {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "CALCULATED_DEMO",
        "input": row,
        "economics": economics,
        "capacity": capacity,
        "warnings": [],
        "truth_state": "DEMO_USER_INPUT",
        "real_financial_record": False,
        "invoice_created": False,
        "payment_collected": False,
        "money_moved": False,
        "executes_action": False,
    }

    if profitability_state == "NEGATIVE":
        result["warnings"].append("CUSTO_SUPERA_RECEITA")
    if profitability_state == "THIN":
        result["warnings"].append("MARGEM_BAIXA")
    if capacity_state == "WATCH":
        result["warnings"].append("CAPACIDADE_PROXIMA_DO_LIMITE")
    if capacity_state == "AT_LIMIT":
        result["warnings"].append("CAPACIDADE_NO_LIMITE")
    if row["payment_state"] == "OVERDUE_DEMO":
        result["warnings"].append("INADIMPLENCIA_DEMO")
    result["economics_digest"] = _digest({
        "company": row["company_name"],
        "monthly_revenue": monthly_revenue,
        "costs": costs,
        "capacity": capacity,
    })
    return result


def pricing_review(economics: Mapping[str, Any] | None) -> dict[str, Any]:
    row = dict(economics or {}) if isinstance(economics, Mapping) else {}
    eco = row.get("economics") if isinstance(row.get("economics"), Mapping) else {}
    capacity = row.get("capacity") if isinstance(row.get("capacity"), Mapping) else {}
    profit_state = _clean(eco.get("profitability_state"), 40)
    capacity_state = _clean(capacity.get("state"), 40)

    reasons = []
    if profit_state in {"NEGATIVE", "THIN"}:
        reasons.append("Revisar escopo, custos e preço antes de ampliar o serviço.")
    if capacity_state in {"WATCH", "AT_LIMIT"}:
        reasons.append("Revisar volume, quota e capacidade operacional.")
    if _clean(eco.get("payment_state"), 40) == "OVERDUE_DEMO":
        reasons.append("Revisar situação comercial antes de expansão.")
    if not reasons:
        reasons.append("Manter acompanhamento de custo, margem e capacidade.")

    return {
        "schema": SCHEMA,
        "state": "REVIEW_REQUIRED" if len(reasons) > 1 or profit_state in {"NEGATIVE", "THIN"} else "MONITOR",
        "reasons": reasons,
        "automatic_price_change": False,
        "automatic_charge": False,
        "requires_human_review": True,
        "executes_action": False,
    }


def portfolio_summary(rows: list[Mapping[str, Any]] | None) -> dict[str, Any]:
    items = [dict(x) for x in list(rows or [])[:100] if isinstance(x, Mapping)]
    valid = [x for x in items if x.get("state") == "CALCULATED_DEMO"]
    total_revenue = round(sum(float((x.get("economics") or {}).get("monthly_revenue") or 0) for x in valid), 2)
    total_costs = round(sum(float((x.get("economics") or {}).get("total_monthly_costs") or 0) for x in valid), 2)
    total_contribution = round(sum(float((x.get("economics") or {}).get("monthly_contribution") or 0) for x in valid), 2)
    negative = sum(1 for x in valid if (x.get("economics") or {}).get("profitability_state") == "NEGATIVE")
    near_capacity = sum(1 for x in valid if (x.get("capacity") or {}).get("state") in {"WATCH", "AT_LIMIT"})
    overdue = sum(1 for x in valid if (x.get("economics") or {}).get("payment_state") == "OVERDUE_DEMO")
    return {
        "schema": SCHEMA,
        "state": "DEMO_SUMMARY",
        "client_count": len(valid),
        "monthly_revenue": total_revenue,
        "monthly_costs": total_costs,
        "monthly_contribution": total_contribution,
        "negative_margin_clients": negative,
        "capacity_attention_clients": near_capacity,
        "overdue_demo_clients": overdue,
        "real_financial_record": False,
        "moves_money": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "PAYMENT_STATES",
    "CAPACITY_STATES",
    "normalize_client_finance",
    "client_economics",
    "pricing_review",
    "portfolio_summary",
]
