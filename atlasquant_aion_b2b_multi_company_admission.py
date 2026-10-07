"""AION B2B Multi-Company Admission & Tenant Quota Gate V1.

Pure/offline admission planning for managed-service customers.

This layer sits after evidence-backed pilot value realization and the existing
commercial conversion/capacity gate. It validates tenant uniqueness, per-tenant
quotas, portfolio reserve, concentration and noisy-neighbor signals.

It never creates a tenant, changes quotas, provisions resources, bills,
contacts customers, calls providers, deploys or mutates production.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math
import re

SCHEMA = "ATLASQUANT_AION_B2B_MULTI_COMPANY_ADMISSION_V1"
VALUE_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_VALUE_REALIZATION_V1"
CONVERSION_SCHEMA = "ATLASQUANT_AION_B2B_CONVERSION_CAPACITY_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_B2B_MULTI_COMPANY_POLICY_V1"
PORTFOLIO_SCHEMA = "ATLASQUANT_AION_B2B_MULTI_COMPANY_PORTFOLIO_V1"

_SAFE_TENANT_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{7,79}$")
QUOTA_KEYS = (
    "capacity_units",
    "calls_per_cycle",
    "tokens_per_cycle",
    "support_tickets_per_cycle",
)
TOTAL_LIMIT_KEYS = {
    "capacity_units": "max_total_capacity_units",
    "calls_per_cycle": "max_total_calls_per_cycle",
    "tokens_per_cycle": "max_total_tokens_per_cycle",
    "support_tickets_per_cycle": "max_total_support_tickets_per_cycle",
}


def _text(value: Any, limit: int = 320) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _positive_int(value: Any, *, allow_zero: bool = False) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    minimum = 0 if allow_zero else 1
    return value if value >= minimum else None


def _pct(value: Any) -> float | None:
    out = _number(value)
    if out is None or out < 0 or out > 100:
        return None
    return out


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(data.get("owner_id"), 120),
        "tenant_id": _text(data.get("tenant_id"), 120),
        "workspace_id": _text(data.get("workspace_id"), 120),
    }


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _refs(value: Any, limit: int = 80) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:limit]:
        item = _text(raw, 320)
        if item and item not in out:
            out.append(item)
    return out


def _validate_value(
    value_result: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    row = dict(value_result) if isinstance(value_result, Mapping) else {}
    blockers: list[str] = []
    if row.get("schema") != VALUE_SCHEMA:
        blockers.append("VALUE_REALIZATION_SCHEMA_INVALID")
    if row.get("state") not in {"STRONG_VALUE", "VALUE_CONFIRMED"}:
        blockers.append("VALUE_REALIZATION_NOT_CONVERSION_READY")
    if row.get("recommendation") not in {
        "EXPANSION_REVIEW_CANDIDATE",
        "CONTINUE_REVIEW_CANDIDATE",
    }:
        blockers.append("VALUE_REALIZATION_RECOMMENDATION_INVALID")
    if _scope(row.get("scope")) != _scope(trusted_scope):
        blockers.append("VALUE_REALIZATION_SCOPE_MISMATCH")
    if row.get("low_value_alert") is not False:
        blockers.append("VALUE_REALIZATION_LOW_VALUE_ALERT")
    if row.get("owner_review_required") is not True:
        blockers.append("VALUE_REALIZATION_OWNER_BOUNDARY_MISSING")
    if row.get("blockers"):
        blockers.append("VALUE_REALIZATION_HAS_BLOCKERS")
    if not _text(row.get("evidence_digest"), 180):
        blockers.append("VALUE_REALIZATION_EVIDENCE_REQUIRED")

    for key in (
        "automatic_renewal",
        "automatic_expansion",
        "automatic_pause",
        "automatic_termination",
        "automatic_scope_change",
        "automatic_contract_change",
        "automatic_billing",
        "automatic_customer_contact",
        "automatic_provisioning",
        "automatic_deploy",
        "crm_write",
        "provider_called",
        "production_mutation",
        "executes_action",
    ):
        if row.get(key) is not False:
            blockers.append("VALUE_REALIZATION_UNSAFE_FIELD:" + key)
    return row, list(dict.fromkeys(blockers))


def _validate_conversion(
    conversion: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    row = dict(conversion) if isinstance(conversion, Mapping) else {}
    blockers: list[str] = []
    if row.get("schema") != CONVERSION_SCHEMA:
        blockers.append("CONVERSION_SCHEMA_INVALID")
    if row.get("state") != "REVIEWABLE":
        blockers.append("CONVERSION_NOT_REVIEWABLE")
    if row.get("decision") != "COMMERCIAL_REVIEW_CANDIDATE":
        blockers.append("CONVERSION_DECISION_INVALID")
    if row.get("review_reasons"):
        blockers.append("CONVERSION_HAS_REVIEW_REASONS")
    if row.get("blockers"):
        blockers.append("CONVERSION_HAS_BLOCKERS")
    if row.get("owner_commercial_approval_required") is not True:
        blockers.append("CONVERSION_OWNER_BOUNDARY_MISSING")
    if not _text(row.get("evidence_digest"), 180):
        blockers.append("CONVERSION_EVIDENCE_REQUIRED")

    for key in (
        "automatic_conversion",
        "automatic_package_change",
        "automatic_pricing_change",
        "automatic_contract",
        "automatic_billing",
        "automatic_provisioning",
        "automatic_customer_contact",
        "automatic_deploy",
        "production_mutation",
        "executes_action",
    ):
        if row.get(key) is not False:
            blockers.append("CONVERSION_UNSAFE_FIELD:" + key)
    return row, list(dict.fromkeys(blockers))


def _validate_policy(
    policy: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, int], list[str]]:
    row = dict(policy) if isinstance(policy, Mapping) else {}
    blockers: list[str] = []

    if row.get("schema") != POLICY_SCHEMA:
        blockers.append("MULTI_COMPANY_POLICY_SCHEMA_INVALID")
    if row.get("state") != "VERIFIED":
        blockers.append("MULTI_COMPANY_POLICY_NOT_VERIFIED")
    if _scope(row) != _scope(trusted_scope):
        blockers.append("MULTI_COMPANY_POLICY_SCOPE_MISMATCH")

    max_active = _positive_int(row.get("max_active_tenants"))
    if max_active is None:
        blockers.append("MAX_ACTIVE_TENANTS_INVALID")

    limits: dict[str, int] = {}
    for quota_key, limit_key in TOTAL_LIMIT_KEYS.items():
        value = _positive_int(row.get(limit_key))
        if value is None:
            blockers.append(limit_key.upper() + "_INVALID")
        else:
            limits[quota_key] = value

    min_reserve_pct = _pct(row.get("min_portfolio_reserve_pct"))
    max_single_share_pct = _pct(row.get("max_single_tenant_share_pct"))
    max_tenant_utilization_pct = _pct(
        row.get("max_tenant_utilization_pct")
    )
    if min_reserve_pct is None or min_reserve_pct <= 0 or min_reserve_pct >= 100:
        blockers.append("MIN_PORTFOLIO_RESERVE_PCT_INVALID")
    if (
        max_single_share_pct is None
        or max_single_share_pct <= 0
        or max_single_share_pct > 100
    ):
        blockers.append("MAX_SINGLE_TENANT_SHARE_PCT_INVALID")
    if (
        max_tenant_utilization_pct is None
        or max_tenant_utilization_pct <= 0
        or max_tenant_utilization_pct > 100
    ):
        blockers.append("MAX_TENANT_UTILIZATION_PCT_INVALID")

    max_channels = _positive_int(row.get("max_channels_per_tenant"))
    max_integrations = _positive_int(
        row.get("max_integrations_per_tenant")
    )
    if max_channels is None:
        blockers.append("MAX_CHANNELS_PER_TENANT_INVALID")
    if max_integrations is None:
        blockers.append("MAX_INTEGRATIONS_PER_TENANT_INVALID")

    refs = _refs(row.get("evidence_refs"))
    if len(refs) < 4:
        blockers.append("MULTI_COMPANY_POLICY_EVIDENCE_INSUFFICIENT")

    normalized = {
        "max_active_tenants": max_active,
        "limits": limits,
        "min_portfolio_reserve_pct": min_reserve_pct,
        "max_single_tenant_share_pct": max_single_share_pct,
        "max_tenant_utilization_pct": max_tenant_utilization_pct,
        "max_channels_per_tenant": max_channels,
        "max_integrations_per_tenant": max_integrations,
        "evidence_refs": refs,
    }
    return normalized, limits, list(dict.fromkeys(blockers))


def _normalize_portfolio(
    portfolio: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any],
    max_tenant_utilization_pct: float | None,
) -> tuple[
    list[dict[str, Any]],
    dict[str, int],
    list[str],
    list[str],
]:
    row = dict(portfolio) if isinstance(portfolio, Mapping) else {}
    blockers: list[str] = []
    review_reasons: list[str] = []

    if row.get("schema") != PORTFOLIO_SCHEMA:
        blockers.append("MULTI_COMPANY_PORTFOLIO_SCHEMA_INVALID")
    if row.get("state") != "VERIFIED":
        blockers.append("MULTI_COMPANY_PORTFOLIO_NOT_VERIFIED")
    if _scope(row) != _scope(trusted_scope):
        blockers.append("MULTI_COMPANY_PORTFOLIO_SCOPE_MISMATCH")

    tenants_raw = row.get("active_tenants")
    if not isinstance(tenants_raw, (list, tuple)):
        blockers.append("ACTIVE_TENANTS_INVALID")
        tenants_raw = []

    tenants: list[dict[str, Any]] = []
    seen_tenants: set[str] = set()
    seen_customers: set[str] = set()
    allocated = {key: 0 for key in QUOTA_KEYS}

    for raw in list(tenants_raw)[:500]:
        if not isinstance(raw, Mapping):
            blockers.append("ACTIVE_TENANT_ITEM_INVALID")
            continue
        tenant_id = _text(raw.get("service_tenant_id"), 80).lower()
        customer_id = _text(raw.get("customer_id"), 120)
        package = _text(raw.get("package"), 40).upper()
        if (
            _SAFE_TENANT_ID.fullmatch(tenant_id) is None
            or tenant_id in seen_tenants
            or not customer_id
            or customer_id in seen_customers
            or not package
        ):
            blockers.append("ACTIVE_TENANT_IDENTITY_INVALID_OR_DUPLICATE")
            continue

        quotas_raw = raw.get("quotas")
        quotas_raw = (
            dict(quotas_raw)
            if isinstance(quotas_raw, Mapping)
            else {}
        )
        quotas: dict[str, int] = {}
        for key in QUOTA_KEYS:
            value = _positive_int(quotas_raw.get(key))
            if value is None:
                blockers.append("ACTIVE_TENANT_QUOTA_INVALID:" + key)
            else:
                quotas[key] = value
                allocated[key] += value

        utilization_raw = raw.get("utilization_pct")
        utilization_raw = (
            dict(utilization_raw)
            if isinstance(utilization_raw, Mapping)
            else {}
        )
        utilization: dict[str, float] = {}
        for key in QUOTA_KEYS:
            value = _pct(utilization_raw.get(key))
            if value is None:
                blockers.append(
                    "ACTIVE_TENANT_UTILIZATION_INVALID:" + key
                )
            else:
                utilization[key] = value
                if (
                    max_tenant_utilization_pct is not None
                    and value > max_tenant_utilization_pct
                ):
                    review_reasons.append(
                        "NOISY_NEIGHBOR_UTILIZATION_PRESENT:"
                        + tenant_id
                        + ":"
                        + key
                    )

        seen_tenants.add(tenant_id)
        seen_customers.add(customer_id)
        tenants.append(
            {
                "service_tenant_id": tenant_id,
                "customer_id": customer_id,
                "package": package,
                "quotas": quotas,
                "utilization_pct": utilization,
            }
        )

    refs = _refs(row.get("evidence_refs"))
    if len(refs) < 4:
        blockers.append("MULTI_COMPANY_PORTFOLIO_EVIDENCE_INSUFFICIENT")

    return (
        tenants,
        allocated,
        list(dict.fromkeys(blockers)),
        list(dict.fromkeys(review_reasons)),
    )


def evaluate_multi_company_admission(
    *,
    trusted_scope: Mapping[str, Any],
    value_realization: Mapping[str, Any],
    conversion_capacity: Mapping[str, Any],
    admission_request: Mapping[str, Any],
    portfolio_state: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    trusted = _scope(trusted_scope)
    blockers: list[str] = []
    review_reasons: list[str] = []

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")

    value, value_blockers = _validate_value(
        value_realization,
        trusted_scope=trusted_scope,
    )
    blockers.extend(value_blockers)

    conversion, conversion_blockers = _validate_conversion(
        conversion_capacity,
        trusted_scope=trusted_scope,
    )
    blockers.extend(conversion_blockers)

    policy_data, limits, policy_blockers = _validate_policy(
        policy,
        trusted_scope=trusted_scope,
    )
    blockers.extend(policy_blockers)

    (
        tenants,
        allocated,
        portfolio_blockers,
        portfolio_reasons,
    ) = _normalize_portfolio(
        portfolio_state,
        trusted_scope=trusted_scope,
        max_tenant_utilization_pct=policy_data.get(
            "max_tenant_utilization_pct"
        ),
    )
    blockers.extend(portfolio_blockers)
    review_reasons.extend(portfolio_reasons)

    request = (
        dict(admission_request)
        if isinstance(admission_request, Mapping)
        else {}
    )
    if _scope(request) != trusted:
        blockers.append("ADMISSION_REQUEST_SCOPE_MISMATCH")

    customer_id = _text(request.get("customer_id"), 120)
    service_tenant_id = _text(
        request.get("service_tenant_id"),
        80,
    ).lower()
    package = _text(request.get("package"), 40).upper()

    if not customer_id:
        blockers.append("ADMISSION_CUSTOMER_ID_REQUIRED")
    if _SAFE_TENANT_ID.fullmatch(service_tenant_id) is None:
        blockers.append("SERVICE_TENANT_ID_INVALID")
    if not package:
        blockers.append("ADMISSION_PACKAGE_REQUIRED")

    conversion_customer = _text(conversion.get("customer_id"), 120)
    conversion_package = _text(
        conversion.get("recommended_package"),
        40,
    ).upper()
    if customer_id != conversion_customer:
        blockers.append("ADMISSION_CUSTOMER_CONVERSION_MISMATCH")
    if package != conversion_package:
        blockers.append("ADMISSION_PACKAGE_CONVERSION_MISMATCH")

    if any(
        tenant["service_tenant_id"] == service_tenant_id
        for tenant in tenants
    ):
        review_reasons.append("SERVICE_TENANT_ID_ALREADY_EXISTS")
    if any(
        tenant["customer_id"] == customer_id
        for tenant in tenants
    ):
        review_reasons.append("CUSTOMER_ALREADY_ADMITTED")

    requested_quotas_raw = request.get("requested_quotas")
    requested_quotas_raw = (
        dict(requested_quotas_raw)
        if isinstance(requested_quotas_raw, Mapping)
        else {}
    )
    requested_quotas: dict[str, int] = {}
    for key in QUOTA_KEYS:
        value_int = _positive_int(requested_quotas_raw.get(key))
        if value_int is None:
            blockers.append("REQUESTED_QUOTA_INVALID:" + key)
        else:
            requested_quotas[key] = value_int

    channel_count = _positive_int(request.get("channel_count"))
    integration_count = _positive_int(request.get("integration_count"))
    expected_peak_utilization_pct = _pct(
        request.get("expected_peak_utilization_pct")
    )
    if channel_count is None:
        blockers.append("ADMISSION_CHANNEL_COUNT_INVALID")
    if integration_count is None:
        blockers.append("ADMISSION_INTEGRATION_COUNT_INVALID")
    if expected_peak_utilization_pct is None:
        blockers.append("EXPECTED_PEAK_UTILIZATION_INVALID")

    if (
        channel_count is not None
        and policy_data.get("max_channels_per_tenant") is not None
        and channel_count > policy_data["max_channels_per_tenant"]
    ):
        review_reasons.append("TENANT_CHANNEL_LIMIT_EXCEEDED")
    if (
        integration_count is not None
        and policy_data.get("max_integrations_per_tenant") is not None
        and integration_count > policy_data["max_integrations_per_tenant"]
    ):
        review_reasons.append("TENANT_INTEGRATION_LIMIT_EXCEEDED")
    if (
        expected_peak_utilization_pct is not None
        and policy_data.get("max_tenant_utilization_pct") is not None
        and expected_peak_utilization_pct
        > policy_data["max_tenant_utilization_pct"]
    ):
        review_reasons.append("REQUESTED_TENANT_PEAK_UTILIZATION_TOO_HIGH")

    request_refs = _refs(request.get("evidence_refs"))
    if len(request_refs) < 3:
        blockers.append("ADMISSION_REQUEST_EVIDENCE_INSUFFICIENT")

    projected: dict[str, dict[str, Any]] = {}
    for key in QUOTA_KEYS:
        limit = limits.get(key)
        current = allocated.get(key, 0)
        requested = requested_quotas.get(key)
        if limit is None or requested is None:
            continue

        projected_value = current + requested
        reserve_pct = round(
            max(0.0, (limit - projected_value) / limit * 100.0),
            2,
        )
        tenant_share_pct = round(
            requested / limit * 100.0,
            2,
        )
        projected[key] = {
            "current_allocated": current,
            "requested": requested,
            "projected_allocated": projected_value,
            "portfolio_limit": limit,
            "reserve_pct": reserve_pct,
            "single_tenant_share_pct": tenant_share_pct,
        }

        if projected_value > limit:
            review_reasons.append(
                "PORTFOLIO_QUOTA_EXCEEDED:" + key
            )
        if (
            policy_data.get("min_portfolio_reserve_pct") is not None
            and reserve_pct
            < policy_data["min_portfolio_reserve_pct"]
        ):
            review_reasons.append(
                "PORTFOLIO_RESERVE_BELOW_POLICY:" + key
            )
        if (
            policy_data.get("max_single_tenant_share_pct") is not None
            and tenant_share_pct
            > policy_data["max_single_tenant_share_pct"]
        ):
            review_reasons.append(
                "SINGLE_TENANT_CONCENTRATION_EXCEEDED:" + key
            )

    projected_active_tenants = len(tenants) + 1
    if (
        policy_data.get("max_active_tenants") is not None
        and projected_active_tenants
        > policy_data["max_active_tenants"]
    ):
        review_reasons.append("ACTIVE_TENANT_LIMIT_EXCEEDED")

    isolation_reasons = [
        item
        for item in review_reasons
        if item in {
            "SERVICE_TENANT_ID_ALREADY_EXISTS",
            "CUSTOMER_ALREADY_ADMITTED",
        }
    ]
    capacity_reasons = [
        item
        for item in review_reasons
        if (
            item.startswith("PORTFOLIO_QUOTA_EXCEEDED:")
            or item.startswith("PORTFOLIO_RESERVE_BELOW_POLICY:")
            or item.startswith("SINGLE_TENANT_CONCENTRATION_EXCEEDED:")
            or item.startswith("NOISY_NEIGHBOR_UTILIZATION_PRESENT:")
            or item in {
                "ACTIVE_TENANT_LIMIT_EXCEEDED",
                "TENANT_CHANNEL_LIMIT_EXCEEDED",
                "TENANT_INTEGRATION_LIMIT_EXCEEDED",
                "REQUESTED_TENANT_PEAK_UTILIZATION_TOO_HIGH",
            }
        )
    ]

    blockers = list(dict.fromkeys(blockers))
    review_reasons = list(dict.fromkeys(review_reasons))

    if blockers:
        state = "BLOCKED"
        decision = "BLOCKED"
    elif isolation_reasons:
        state = "ISOLATION_HOLD"
        decision = "ISOLATION_REVIEW"
    elif capacity_reasons:
        state = "CAPACITY_HOLD"
        decision = "CAPACITY_REVIEW"
    else:
        state = "REVIEWABLE"
        decision = "TENANT_ADMISSION_REVIEW_CANDIDATE"

    evidence = {
        "scope": trusted,
        "pilot_id": _text(value.get("pilot_id"), 120),
        "value_evidence_digest": _text(
            value.get("evidence_digest"),
            180,
        ),
        "conversion_evidence_digest": _text(
            conversion.get("evidence_digest"),
            180,
        ),
        "customer_id": customer_id,
        "service_tenant_id": service_tenant_id,
        "package": package,
        "requested_quotas": requested_quotas,
        "projected_active_tenants": projected_active_tenants,
        "projected_quotas": projected,
        "request_evidence_refs": request_refs,
        "portfolio_evidence_refs": _refs(
            dict(portfolio_state or {}).get("evidence_refs")
        ),
        "policy_evidence_refs": policy_data.get("evidence_refs", []),
    }

    return {
        "schema": SCHEMA,
        "state": state,
        "decision": decision,
        "customer_id": customer_id,
        "service_tenant_id": service_tenant_id,
        "package": package,
        "proposed_quotas": requested_quotas,
        "projected_active_tenants": projected_active_tenants,
        "projected_portfolio": projected,
        "review_reasons": review_reasons,
        "isolation_reasons": isolation_reasons,
        "capacity_reasons": capacity_reasons,
        "blockers": blockers,
        "evidence_digest": _digest(evidence),
        "owner_admission_approval_required": True,
        "tenant_creation_authorized": False,
        "quota_change_authorized": False,
        "admission_token_issued": False,
        "automatic_tenant_creation": False,
        "automatic_quota_change": False,
        "automatic_package_change": False,
        "automatic_pricing_change": False,
        "automatic_contract_change": False,
        "automatic_billing": False,
        "automatic_provisioning": False,
        "automatic_customer_contact": False,
        "automatic_deploy": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VALUE_SCHEMA",
    "CONVERSION_SCHEMA",
    "POLICY_SCHEMA",
    "PORTFOLIO_SCHEMA",
    "QUOTA_KEYS",
    "TOTAL_LIMIT_KEYS",
    "evaluate_multi_company_admission",
]
