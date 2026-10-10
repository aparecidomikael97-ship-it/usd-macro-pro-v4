"""Research-only capacity and vendor quote sensitivity for AION external witness.

No network, credentials, account creation, cloud API, FX retrieval or payment.
This calculator is not a procurement authorization. Even a complete,
under-budget hypothetical quote NEVER grants production trust or Worker use.
CF Free quotas refer to *this modeled workload*, not account-wide actual use.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

SCHEMA = "AION_WITNESS_BUDGET_RESEARCH_V1"
CAP_BRL = Decimal("200")
DAYS_PER_MONTH = 30
CF_FREE_LIMITS = {
    "do_requests_per_day": 100_000,
    "do_duration_gb_s_per_day": Decimal("13000"),
    "do_rows_read_per_day": 5_000_000,
    "do_rows_written_per_day": 100_000,
    "do_stored_gb": Decimal("5"),
}
PLAN_FIELDS = frozenset({
    "tenant_count", "reads_per_tenant_per_day", "writes_per_tenant_per_day",
    "do_requests_per_read", "do_requests_per_write",
    "do_rows_read_per_request", "do_rows_written_per_write",
    "do_duration_gb_s_per_request", "do_storage_gb",
    "s3_receipt_bytes", "s3_retention_days",
})
QUOTE_FIELDS = frozenset({
    "fx_brl_per_usd", "existing_infra_brl_month",
    "s3_storage_usd_per_gb_month", "s3_put_usd_per_1000",
    "s3_get_usd_per_1000", "s3_list_usd_per_1000",
    "s3_egress_usd_month", "kms_usd_month",
    "monitoring_usd_month", "tax_percent", "reserve_percent",
})
NO_AUTHORITY = {
    "spending_approved": False,
    "provider_enrollment_verified": False,
    "independent_witness_production_verified": False,
    "worker_authorized": False,
    "merge_authorized": False,
    "deploy_authorized": False,
    "automatic_retry_allowed": False,
    "budget_certified": False,
}

def _dec(value: Any, name: str) -> Decimal:
    if type(value) is not str or not value or len(value) > 45:
        raise ValueError(name)
    try:
        d = Decimal(value)
    except InvalidOperation:
        raise ValueError(name) from None
    if not d.is_finite() or d < 0 or d > Decimal("1000000000"):
        raise ValueError(name)
    return d

def _int(value: Any, name: str, *, low: int = 1, high: int = 1_000_000) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(name)
    return value

def _base(status: str, blockers: list[str], **metrics: Any) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": status,
        "blockers": sorted(set(blockers)),
        "currency": "BRL",
        "quote_is_self_reported": True,
        "cloudflare_free_account_usage_verified": False,
        "workers_caller_quota_verified": False,
        "aws_billing_verified": False,
        "source_verification_production_verified": False,
        "full_stack_monthly_cost_brl": None,
        "budget_within_cap_math_only": None,
        "monthly_cap_brl": "200.00",
        "assumptions": "30d model, flat daily traffic, steady state retained S3 receipts; fees and actual quotas require independent validation",
        **NO_AUTHORITY,
        **metrics,
    }

def model_witness_cost(plan: Mapping[str, Any] | None,
                       quote: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Check *assumptions* against free quotas and optionally price a quoted basket.

    DO capacity is separate from Workers caller requests and other resources.
    Missing/incomplete vendor quote => no total in BRL. Any positive estimate
    remains mathematical-only and never certifies the R$200 ceiling.
    """
    if not isinstance(plan, Mapping) or set(plan) != PLAN_FIELDS:
        return _base("INVALID_PLAN", ["PLAN_FIELDS_INVALID"])
    try:
        tenants = _int(plan["tenant_count"], "TENANTS")
        reads = _int(plan["reads_per_tenant_per_day"], "READS", low=0)
        writes = _int(plan["writes_per_tenant_per_day"], "WRITES", low=0)
        if reads + writes < 1:
            raise ValueError("TRAFFIC_MISSING")
        req_read = _int(plan["do_requests_per_read"], "REQ_READ")
        req_write = _int(plan["do_requests_per_write"], "REQ_WRITE")
        rows_read = _int(plan["do_rows_read_per_request"], "ROWS_READ")
        rows_write = _int(plan["do_rows_written_per_write"], "ROWS_WRITE")
        gb_s = _dec(plan["do_duration_gb_s_per_request"], "DO_DURATION")
        do_storage = _dec(plan["do_storage_gb"], "DO_STORAGE")
        receipt_bytes = _int(plan["s3_receipt_bytes"], "RECEIPT_BYTES", low=100, high=1_000_000)
        retention = _int(plan["s3_retention_days"], "RETENTION", low=1, high=3650)
    except ValueError as ex:
        return _base("INVALID_PLAN", ["INVALID_" + str(ex)])
    daily_reads = tenants * reads
    daily_writes = tenants * writes
    daily_do = daily_reads * req_read + daily_writes * req_write
    daily_row_read = daily_do * rows_read
    daily_row_write = daily_writes * rows_write
    daily_duration = gb_s * daily_do
    daily_storage_versions = daily_writes
    monthly_storage_gb_lower_bound = Decimal(daily_storage_versions * retention * receipt_bytes) / Decimal(1_000_000_000)
    metrics = {
        "modeled_tenants": tenants,
        "do_requests_per_day": daily_do,
        "do_rows_read_per_day": daily_row_read,
        "do_rows_written_per_day": daily_row_write,
        "do_duration_gb_s_per_day": str(daily_duration),
        "do_stored_gb_assumed": str(do_storage),
        "s3_put_per_month": daily_writes * DAYS_PER_MONTH,
        "s3_get_per_month": daily_reads * DAYS_PER_MONTH,
        "s3_list_per_month": daily_reads * DAYS_PER_MONTH,
        "s3_versions_retained_steady_state": daily_writes * retention,
        "s3_gb_month_lower_bound": str(monthly_storage_gb_lower_bound),
        "s3_minimum_object_or_metadata_overheads_included": False,
        "cloudflare_workers_caller_usage_included": False,
        "s3_cross_region_transfer_included": False,
    }
    breaches = []
    for key in ("do_requests_per_day", "do_rows_read_per_day", "do_rows_written_per_day"):
        if metrics[key] > CF_FREE_LIMITS[key]:
            breaches.append("CF_FREE_" + key.upper() + "_EXCEEDED")
    if daily_duration > CF_FREE_LIMITS["do_duration_gb_s_per_day"]:
        breaches.append("CF_FREE_DURATION_EXCEEDED")
    if do_storage > CF_FREE_LIMITS["do_stored_gb"]:
        breaches.append("CF_FREE_STORAGE_EXCEEDED")
    blockers = breaches or ["CF_FREE_ONLY_MODELED_NOT_ACCOUNT_VERIFIED"]
    if quote is None:
        return _base("FREE_CAPACITY_EXCEEDED" if breaches else "COST_NOT_QUOTED",
                     blockers + ["AWS_FX_EXISTING_COSTS_NOT_QUOTED"], **metrics)
    if not isinstance(quote, Mapping) or set(quote) != QUOTE_FIELDS:
        return _base("COST_NOT_QUOTED", blockers + ["QUOTE_FIELDS_MISSING"], **metrics)
    try:
        amounts = {k: _dec(v, k.upper()) for k, v in quote.items()}
        if amounts["fx_brl_per_usd"] == 0:
            raise ValueError("FX_ZERO")
        if amounts["tax_percent"] > 100 or amounts["reserve_percent"] > 100:
            raise ValueError("RATE_TOO_HIGH")
    except ValueError as ex:
        return _base("COST_NOT_QUOTED", blockers + ["INVALID_" + str(ex)], **metrics)
    # Quote values are unverified and omit CF calling Worker/other tenants.
    # Do NOT compute a misleading full-stack total or budget approval.
    s3_storage = monthly_storage_gb_lower_bound * amounts["s3_storage_usd_per_gb_month"]
    requests = (
        Decimal(metrics["s3_put_per_month"]) / 1000 * amounts["s3_put_usd_per_1000"]
        + Decimal(metrics["s3_get_per_month"]) / 1000 * amounts["s3_get_usd_per_1000"]
        + Decimal(metrics["s3_list_per_month"]) / 1000 * amounts["s3_list_usd_per_1000"]
    )
    usd_partial = (s3_storage + requests
                   + amounts["s3_egress_usd_month"]
                   + amounts["kms_usd_month"] + amounts["monitoring_usd_month"])
    subtotal_brl = usd_partial * amounts["fx_brl_per_usd"] + amounts["existing_infra_brl_month"]
    partial_brl = subtotal_brl * (Decimal(1) + amounts["tax_percent"]/100) * (
        Decimal(1) + amounts["reserve_percent"]/100)
    rendered = str(partial_brl.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return _base("FREE_CAPACITY_EXCEEDED" if breaches else "PARTIAL_MATH_NOT_CERTIFIED",
                 blockers + ["UNQUOTED_CF_CALLER_AND_ACCOUNT_WIDE_USAGE",
                             "S3_VERSION_METADATA_AND_REAL_REGION_UNVERIFIED",
                             "PROVIDER_QUOTE_NOT_AUTHENTICATED",
                             "NO_OWNER_FINANCIAL_APPROVAL"],
                 quoted_partial_brl=rendered,
                 quoted_partial_over_cap_math_only=partial_brl > CAP_BRL,
                 **metrics)

__all__ = ["SCHEMA", "PLAN_FIELDS", "QUOTE_FIELDS", "NO_AUTHORITY",
           "CF_FREE_LIMITS", "model_witness_cost"]
