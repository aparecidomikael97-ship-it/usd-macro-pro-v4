"""Research-only capacity and vendor quote sensitivity for AION external witness.

No network, credentials, account creation, cloud API, FX retrieval or payment.
This calculator is not a procurement authorization. Even a complete,
under-budget hypothetical quote NEVER grants production trust or Worker use.
CF Free quotas refer to *this modeled workload*, not account-wide actual use.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_CEILING
from typing import Any, Mapping

SCHEMA = "AION_WITNESS_BUDGET_RESEARCH_V1"
WORKERS_FREE_INBOUND_REQUESTS_PER_DAY = 100_000
WORKERS_FREE_CPU_MS_PER_INVOCATION = Decimal("10")
CAP_BRL = Decimal("200")
CF_DO_FREE_SINGLE_OBJECT_GB = Decimal("1")
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
# Must not conflate Durable Objects RPCs with inbound Worker requests.
# This is an optional unverified scenario, not real account-wide metrics.
WORKER_PROFILE_FIELDS = frozenset({
    "requests_per_read", "requests_per_write",
    "other_account_requests_per_day", "cpu_ms_per_invocation",
    "peak_day_multiplier",
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
                       quote: Mapping[str, Any] | None = None,
                       *, worker_profile: Mapping[str, Any] | None = None,
                       largest_do_storage_gb: str | None = None) -> dict[str, Any]:
    """Check *assumptions* against free quotas and optionally price a quoted basket.

    DO capacity is separate from Workers caller requests and other resources.
    Missing/incomplete vendor quote => no total in BRL. Worker inbound
    requests/CPU and peak-day traffic require a separately declared profile.
    The profile is never trusted as real account-wide metering. Any positive
    estimate remains mathematical-only and never certifies R$200.
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
    # The account's 5-GB free storage quota is not the per-object 1-GB
    # hard limit. The latter cannot be deduced from an account-wide total.
    if largest_do_storage_gb is None:
        per_object = None
        object_blockers = ["CF_DO_SINGLE_OBJECT_STORAGE_NOT_MODELED"]
    else:
        try:
            per_object = _dec(largest_do_storage_gb, "DO_SINGLE_OBJECT_STORAGE")
            if per_object > do_storage:
                raise ValueError("DO_SINGLE_OBJECT_EXCEEDS_ACCOUNT_TOTAL")
        except ValueError as ex:
            return _base("INVALID_PLAN", ["INVALID_" + str(ex)])
        object_blockers = []
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
        "do_largest_object_gb_assumed": str(per_object) if per_object is not None else None,
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
    if per_object is not None and per_object > CF_DO_FREE_SINGLE_OBJECT_GB:
        breaches.append("CF_DO_FREE_SINGLE_OBJECT_STORAGE_EXCEEDED")
    # Peak-day and Workers Free gates cannot be assumed from DO mean traffic.
    # Keep original calculations unchanged for callers that have not provided
    # a Worker profile, but surface the omission as an explicit blocker.
    if worker_profile is None:
        metrics["workers_profile_included"] = False
        metrics["workers_requests_per_day_modeled"] = None
        metrics["peak_day_multiplier"] = None
        workers_blockers = ["WORKERS_FREE_USAGE_AND_PEAK_NOT_MODELED"]
    elif not isinstance(worker_profile, Mapping) or set(worker_profile) != WORKER_PROFILE_FIELDS:
        return _base("WORKER_PROFILE_INVALID", breaches + [
            "WORKER_PROFILE_FIELDS_INVALID"], **metrics)
    else:
        try:
            worker_r = _int(worker_profile["requests_per_read"], "WORKER_REQUESTS_READ", low=0)
            worker_w = _int(worker_profile["requests_per_write"], "WORKER_REQUESTS_WRITE", low=0)
            other = _int(worker_profile["other_account_requests_per_day"], "OTHER_ACCOUNT_REQUESTS", low=0)
            cpu = _dec(worker_profile["cpu_ms_per_invocation"], "WORKER_CPU")
            peak = _dec(worker_profile["peak_day_multiplier"], "PEAK_MULTIPLIER")
            if peak < 1 or peak > 100:
                raise ValueError("PEAK_RANGE")
            if worker_r + worker_w < 1:
                raise ValueError("WORKER_TRAFFIC_ABSENT")
        except ValueError as ex:
            return _base("WORKER_PROFILE_INVALID", breaches + [
                "INVALID_" + str(ex)], **metrics)
        def ceiling(value: Decimal) -> int:
            return int(value.to_integral_value(rounding=ROUND_CEILING))
        inbound = daily_reads * worker_r + daily_writes * worker_w
        workers_peak = ceiling(Decimal(inbound + other) * peak)
        peak_do = ceiling(Decimal(daily_do) * peak)
        peak_do_rows_read = ceiling(Decimal(daily_row_read) * peak)
        peak_do_rows_written = ceiling(Decimal(daily_row_write) * peak)
        peak_do_duration = daily_duration * peak
        metrics.update({
            "workers_profile_included": True,
            "workers_requests_per_day_modeled": inbound,
            "workers_other_account_requests_per_day_assumed": other,
            "workers_total_peak_requests_per_day_modeled": workers_peak,
            "workers_cpu_ms_per_invocation_assumed": str(cpu),
            "peak_day_multiplier": str(peak),
            "do_peak_requests_per_day": peak_do,
            "do_peak_rows_read_per_day": peak_do_rows_read,
            "do_peak_rows_written_per_day": peak_do_rows_written,
            "do_peak_duration_gb_s_per_day": str(peak_do_duration),
        })
        workers_blockers = ["WORKERS_FREE_AND_OTHER_ACCOUNT_ONLY_SELF_DECLARED"]
        if workers_peak > WORKERS_FREE_INBOUND_REQUESTS_PER_DAY:
            breaches.append("CF_WORKERS_FREE_INBOUND_REQUESTS_EXCEEDED")
        if cpu > WORKERS_FREE_CPU_MS_PER_INVOCATION:
            breaches.append("CF_WORKERS_FREE_CPU_PER_INVOCATION_EXCEEDED")
        if peak_do > CF_FREE_LIMITS["do_requests_per_day"]:
            breaches.append("CF_DO_PEAK_REQUESTS_EXCEEDED")
        if peak_do_rows_read > CF_FREE_LIMITS["do_rows_read_per_day"]:
            breaches.append("CF_DO_PEAK_ROWS_READ_EXCEEDED")
        if peak_do_rows_written > CF_FREE_LIMITS["do_rows_written_per_day"]:
            breaches.append("CF_DO_PEAK_ROWS_WRITTEN_EXCEEDED")
        if peak_do_duration > CF_FREE_LIMITS["do_duration_gb_s_per_day"]:
            breaches.append("CF_DO_PEAK_DURATION_EXCEEDED")
    blockers = list(breaches) + workers_blockers + object_blockers + [
        "CF_FREE_ONLY_MODELED_NOT_ACCOUNT_VERIFIED"
    ]
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
    # Quote values are unverified, even if an optional Worker profile exists.
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
           "CF_FREE_LIMITS", "WORKER_PROFILE_FIELDS",
           "WORKERS_FREE_INBOUND_REQUESTS_PER_DAY",
           "CF_DO_FREE_SINGLE_OBJECT_GB", "model_witness_cost"]
