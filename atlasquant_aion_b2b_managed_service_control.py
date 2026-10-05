"""AION B2B managed-service control contract and recurring review gate.

Pure/offline decision support for a customer that has already passed the pilot
and commercial conversion gates. It defines bounded service terms and reviews
tenant/SLA/quota/FinOps/customer-health evidence. It never signs, bills,
provisions, deploys, renews, contacts a customer, or mutates production.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA = "ATLASQUANT_AION_B2B_MANAGED_SERVICE_CONTROL_V1"
PACKAGES = ("ESSENCIAL", "PROFISSIONAL", "COMPLETO")
MAX_ALLOWED_WORKFLOWS = 20


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


def _pct(value: Any) -> float | None:
    out = _number(value)
    if out is None or out < 0 or out > 100:
        return None
    return out


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _positive_int(value: Any) -> int | None:
    out = _nonnegative_int(value)
    return out if out is not None and out > 0 else None


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(data.get("owner_id"), 120),
        "tenant_id": _text(data.get("tenant_id"), 120),
        "workspace_id": _text(data.get("workspace_id"), 120),
    }


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _unique_texts(value: Any, limit: int, item_limit: int = 220) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:limit]:
        item = _text(raw, item_limit)
        if item and item not in out:
            out.append(item)
    return out


def _validate_conversion(
    conversion: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    data = dict(conversion) if isinstance(conversion, Mapping) else {}
    blockers: list[str] = []
    if data.get("state") != "REVIEWABLE":
        blockers.append("CONVERSION_NOT_REVIEWABLE")
    if data.get("decision") != "COMMERCIAL_REVIEW_CANDIDATE":
        blockers.append("CONVERSION_NOT_COMMERCIAL_REVIEW_CANDIDATE")
    if data.get("blockers"):
        blockers.append("CONVERSION_HAS_BLOCKERS")
    if data.get("review_reasons"):
        blockers.append("CONVERSION_HAS_REVIEW_REASONS")
    if data.get("owner_commercial_approval_required") is not True:
        blockers.append("COMMERCIAL_OWNER_BOUNDARY_MISSING")
    if not _text(data.get("evidence_digest"), 180):
        blockers.append("CONVERSION_EVIDENCE_DIGEST_REQUIRED")
    package = _text(data.get("recommended_package"), 40).upper()
    if package not in PACKAGES:
        blockers.append("CONVERSION_PACKAGE_INVALID")
    customer_id = _text(data.get("customer_id"), 120)
    if not customer_id:
        blockers.append("CONVERSION_CUSTOMER_ID_REQUIRED")
    return data, blockers


def _validate_owner_commercial_approval(
    approval: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any],
    customer_id: str,
    package: str,
) -> list[str]:
    data = dict(approval) if isinstance(approval, Mapping) else {}
    blockers: list[str] = []
    if data.get("state") != "CONFIRMED":
        blockers.append("COMMERCIAL_OWNER_APPROVAL_NOT_CONFIRMED")
    if data.get("approved_by_owner") is not True:
        blockers.append("COMMERCIAL_OWNER_APPROVAL_REQUIRED")
    if _scope(data) != _scope(trusted_scope):
        blockers.append("COMMERCIAL_OWNER_APPROVAL_SCOPE_MISMATCH")
    if _text(data.get("customer_id"), 120) != customer_id:
        blockers.append("COMMERCIAL_OWNER_APPROVAL_CUSTOMER_MISMATCH")
    if _text(data.get("package"), 40).upper() != package:
        blockers.append("COMMERCIAL_OWNER_APPROVAL_PACKAGE_MISMATCH")
    if not _text(data.get("approval_ref"), 320):
        blockers.append("COMMERCIAL_OWNER_APPROVAL_REF_REQUIRED")
    return blockers


def build_managed_service_contract(
    *,
    trusted_scope: Mapping[str, Any],
    conversion: Mapping[str, Any],
    owner_commercial_approval: Mapping[str, Any],
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    conversion_data, blockers = _validate_conversion(conversion, trusted_scope=trusted_scope)
    trusted = _scope(trusted_scope)
    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")

    customer_id = _text(conversion_data.get("customer_id"), 120)
    package = _text(conversion_data.get("recommended_package"), 40).upper()
    blockers.extend(
        _validate_owner_commercial_approval(
            owner_commercial_approval,
            trusted_scope=trusted_scope,
            customer_id=customer_id,
            package=package,
        )
    )

    data = dict(spec) if isinstance(spec, Mapping) else {}
    if _scope(data) != trusted:
        blockers.append("SERVICE_SPEC_SCOPE_MISMATCH")
    if _text(data.get("customer_id"), 120) != customer_id:
        blockers.append("SERVICE_SPEC_CUSTOMER_MISMATCH")
    if _text(data.get("package"), 40).upper() != package:
        blockers.append("SERVICE_SPEC_PACKAGE_MISMATCH")

    monthly_price = _number(data.get("monthly_price_brl"))
    monthly_cost_cap = _number(data.get("monthly_service_cost_cap_brl"))
    if monthly_price is None or monthly_price <= 0:
        blockers.append("SERVICE_MONTHLY_PRICE_INVALID")
    if monthly_cost_cap is None or monthly_cost_cap < 0:
        blockers.append("SERVICE_MONTHLY_COST_CAP_INVALID")
    if (
        monthly_price is not None
        and monthly_cost_cap is not None
        and monthly_cost_cap >= monthly_price
    ):
        blockers.append("SERVICE_COST_CAP_ERASES_MARGIN")

    max_capacity_units = _positive_int(data.get("max_capacity_units"))
    max_calls = _positive_int(data.get("max_calls_per_cycle"))
    max_tokens = _positive_int(data.get("max_tokens_per_cycle"))
    max_support_tickets = _positive_int(data.get("max_support_tickets_per_cycle"))
    for name, value in (
        ("MAX_CAPACITY_UNITS", max_capacity_units),
        ("MAX_CALLS_PER_CYCLE", max_calls),
        ("MAX_TOKENS_PER_CYCLE", max_tokens),
        ("MAX_SUPPORT_TICKETS_PER_CYCLE", max_support_tickets),
    ):
        if value is None:
            blockers.append(f"{name}_INVALID")

    first_response_hours = _number(data.get("sla_first_response_hours"))
    resolution_hours = _number(data.get("sla_resolution_hours"))
    if first_response_hours is None or first_response_hours <= 0:
        blockers.append("SLA_FIRST_RESPONSE_INVALID")
    if resolution_hours is None or resolution_hours <= 0:
        blockers.append("SLA_RESOLUTION_INVALID")
    if (
        first_response_hours is not None
        and resolution_hours is not None
        and resolution_hours < first_response_hours
    ):
        blockers.append("SLA_RESOLUTION_BELOW_FIRST_RESPONSE")

    allowed_workflows = _unique_texts(data.get("allowed_workflows"), MAX_ALLOWED_WORKFLOWS, 120)
    if not allowed_workflows:
        blockers.append("ALLOWED_WORKFLOW_REQUIRED")
    if isinstance(data.get("allowed_workflows"), (list, tuple)) and len(data.get("allowed_workflows")) > MAX_ALLOWED_WORKFLOWS:
        blockers.append("ALLOWED_WORKFLOW_LIMIT_EXCEEDED")

    integration_refs = _unique_texts(data.get("integration_refs"), 20, 220)
    if not integration_refs:
        blockers.append("INTEGRATION_REF_REQUIRED")

    roles = _unique_texts(data.get("allowed_roles"), 10, 80)
    required_roles = {"OWNER", "ADMIN", "MANAGER", "COLLABORATOR"}
    if not required_roles.issubset(set(roles)):
        blockers.append("RBAC_ROLE_SET_INCOMPLETE")

    evidence_refs = _unique_texts(data.get("evidence_refs"), 30, 320)
    if len(evidence_refs) < 5:
        blockers.append("SERVICE_EVIDENCE_INSUFFICIENT")

    core = {
        **trusted,
        "customer_id": customer_id,
        "package": package,
        "monthly_price_brl": monthly_price,
        "monthly_service_cost_cap_brl": monthly_cost_cap,
        "max_capacity_units": max_capacity_units,
        "max_calls_per_cycle": max_calls,
        "max_tokens_per_cycle": max_tokens,
        "max_support_tickets_per_cycle": max_support_tickets,
        "sla_first_response_hours": first_response_hours,
        "sla_resolution_hours": resolution_hours,
        "allowed_workflows": allowed_workflows,
        "integration_refs": integration_refs,
        "allowed_roles": roles,
        "evidence_refs": evidence_refs,
        "conversion_evidence_digest": _text(conversion_data.get("evidence_digest"), 180),
        "owner_commercial_approval_ref": _text(owner_commercial_approval.get("approval_ref"), 320),
    }

    return {
        "schema": SCHEMA,
        "state": "DRAFT_FOR_OWNER_ACTIVATION" if not blockers else "BLOCKED",
        "activation_state": "BLOCKED_UNTIL_OWNER_ACTIVATION",
        "contract": core,
        "blockers": list(dict.fromkeys(blockers)),
        "contract_digest": _digest(core),
        "owner_activation_required": True,
        "automatic_activation": False,
        "automatic_contract_signature": False,
        "automatic_billing": False,
        "automatic_provisioning": False,
        "automatic_integration_enablement": False,
        "automatic_role_grant": False,
        "automatic_deploy": False,
        "production_mutation": False,
        "executes_action": False,
    }


def evaluate_managed_service_cycle(
    contract_result: Mapping[str, Any],
    *,
    owner_activation_attestation: Mapping[str, Any],
    tenant_evidence: Mapping[str, Any],
    finops_evidence: Mapping[str, Any],
    quota_evidence: Mapping[str, Any],
    support_evidence: Mapping[str, Any],
    customer_health_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    contract_result = dict(contract_result) if isinstance(contract_result, Mapping) else {}
    blockers: list[str] = []
    if contract_result.get("state") != "DRAFT_FOR_OWNER_ACTIVATION":
        blockers.append("SERVICE_CONTRACT_NOT_REVIEWABLE")
    if contract_result.get("activation_state") != "BLOCKED_UNTIL_OWNER_ACTIVATION":
        blockers.append("SERVICE_ACTIVATION_BOUNDARY_INVALID")
    if contract_result.get("blockers"):
        blockers.append("SERVICE_CONTRACT_HAS_BLOCKERS")

    core = contract_result.get("contract")
    core = dict(core) if isinstance(core, Mapping) else {}
    scope = _scope(core)
    customer_id = _text(core.get("customer_id"), 120)
    package = _text(core.get("package"), 40).upper()

    activation = dict(owner_activation_attestation) if isinstance(owner_activation_attestation, Mapping) else {}
    if activation.get("state") != "CONFIRMED":
        blockers.append("OWNER_SERVICE_ACTIVATION_NOT_CONFIRMED")
    if activation.get("approved_by_owner") is not True:
        blockers.append("OWNER_SERVICE_ACTIVATION_REQUIRED")
    if _scope(activation) != scope:
        blockers.append("OWNER_SERVICE_ACTIVATION_SCOPE_MISMATCH")
    if _text(activation.get("customer_id"), 120) != customer_id:
        blockers.append("OWNER_SERVICE_ACTIVATION_CUSTOMER_MISMATCH")
    if _text(activation.get("package"), 40).upper() != package:
        blockers.append("OWNER_SERVICE_ACTIVATION_PACKAGE_MISMATCH")
    if not _text(activation.get("activation_ref"), 320):
        blockers.append("OWNER_SERVICE_ACTIVATION_REF_REQUIRED")

    tenant = dict(tenant_evidence) if isinstance(tenant_evidence, Mapping) else {}
    if _scope(tenant) != scope:
        blockers.append("TENANT_EVIDENCE_SCOPE_MISMATCH")
    if tenant.get("state") != "PASS":
        blockers.append("TENANT_ISOLATION_NOT_PASS")
    if tenant.get("cross_tenant_access") is not False:
        blockers.append("CROSS_TENANT_ACCESS_UNSAFE")
    if tenant.get("tenant_data_isolated") is not True:
        blockers.append("TENANT_DATA_ISOLATION_REQUIRED")

    finops = dict(finops_evidence) if isinstance(finops_evidence, Mapping) else {}
    if _scope(finops) != scope:
        blockers.append("FINOPS_SCOPE_MISMATCH")
    if finops.get("state") not in {"ALLOW", "DEGRADE"}:
        blockers.append("FINOPS_STATE_NOT_ADMISSIBLE")
    actual_service_cost = _number(finops.get("actual_service_cost_brl"))
    if actual_service_cost is None or actual_service_cost < 0:
        blockers.append("FINOPS_ACTUAL_SERVICE_COST_INVALID")
    cost_cap = _number(core.get("monthly_service_cost_cap_brl"))
    if (
        actual_service_cost is not None
        and cost_cap is not None
        and actual_service_cost > cost_cap
    ):
        blockers.append("SERVICE_COST_CAP_EXCEEDED")

    quota = dict(quota_evidence) if isinstance(quota_evidence, Mapping) else {}
    if _scope(quota) != scope:
        blockers.append("QUOTA_SCOPE_MISMATCH")
    used_capacity = _nonnegative_int(quota.get("used_capacity_units"))
    calls = _nonnegative_int(quota.get("calls"))
    tokens = _nonnegative_int(quota.get("tokens"))
    tickets = _nonnegative_int(quota.get("support_tickets"))
    for name, value in (
        ("USED_CAPACITY_UNITS", used_capacity),
        ("CALLS", calls),
        ("TOKENS", tokens),
        ("SUPPORT_TICKETS", tickets),
    ):
        if value is None:
            blockers.append(f"{name}_INVALID")

    quota_review: list[str] = []
    if used_capacity is not None and core.get("max_capacity_units") is not None and used_capacity > core["max_capacity_units"]:
        quota_review.append("CAPACITY_QUOTA_EXCEEDED")
    if calls is not None and core.get("max_calls_per_cycle") is not None and calls > core["max_calls_per_cycle"]:
        quota_review.append("CALL_QUOTA_EXCEEDED")
    if tokens is not None and core.get("max_tokens_per_cycle") is not None and tokens > core["max_tokens_per_cycle"]:
        quota_review.append("TOKEN_QUOTA_EXCEEDED")
    if tickets is not None and core.get("max_support_tickets_per_cycle") is not None and tickets > core["max_support_tickets_per_cycle"]:
        quota_review.append("SUPPORT_TICKET_QUOTA_EXCEEDED")

    support = dict(support_evidence) if isinstance(support_evidence, Mapping) else {}
    if _scope(support) != scope:
        blockers.append("SUPPORT_SCOPE_MISMATCH")
    first_response = _number(support.get("avg_first_response_hours"))
    resolution = _number(support.get("avg_resolution_hours"))
    critical_open = _nonnegative_int(support.get("critical_open_tickets"))
    if first_response is None or first_response < 0:
        blockers.append("SUPPORT_FIRST_RESPONSE_INVALID")
    if resolution is None or resolution < 0:
        blockers.append("SUPPORT_RESOLUTION_INVALID")
    if critical_open is None:
        blockers.append("SUPPORT_CRITICAL_OPEN_INVALID")

    sla_review: list[str] = []
    if first_response is not None and core.get("sla_first_response_hours") is not None and first_response > core["sla_first_response_hours"]:
        sla_review.append("FIRST_RESPONSE_SLA_MISSED")
    if resolution is not None and core.get("sla_resolution_hours") is not None and resolution > core["sla_resolution_hours"]:
        sla_review.append("RESOLUTION_SLA_MISSED")
    if critical_open is not None and critical_open > 0:
        sla_review.append("CRITICAL_SUPPORT_TICKET_OPEN")

    health = dict(customer_health_evidence) if isinstance(customer_health_evidence, Mapping) else {}
    if _scope(health) != scope:
        blockers.append("CUSTOMER_HEALTH_SCOPE_MISMATCH")
    health_score = _pct(health.get("health_score"))
    roi_pct = _number(health.get("observed_roi_pct"))
    value_confirmed = health.get("value_confirmed")
    if health_score is None:
        blockers.append("CUSTOMER_HEALTH_SCORE_INVALID")
    if roi_pct is None:
        blockers.append("CUSTOMER_ROI_INVALID")
    if value_confirmed is not True:
        blockers.append("CUSTOMER_VALUE_NOT_CONFIRMED")

    incident_reasons: list[str] = []
    if tenant.get("security_incident") is True:
        incident_reasons.append("TENANT_SECURITY_INCIDENT")
    if tenant.get("privacy_incident") is True:
        incident_reasons.append("TENANT_PRIVACY_INCIDENT")
    if tenant.get("scope_breach") is True:
        incident_reasons.append("TENANT_SCOPE_BREACH")

    review_reasons = list(dict.fromkeys(quota_review + sla_review))
    if finops.get("state") == "DEGRADE":
        review_reasons.append("FINOPS_DEGRADED")
    if health_score is not None and health_score < 70:
        review_reasons.append("CUSTOMER_HEALTH_BELOW_TARGET")
    if roi_pct is not None and roi_pct < 0:
        review_reasons.append("CUSTOMER_VALUE_NEGATIVE")

    if blockers:
        state = "BLOCKED"
        decision = "BLOCKED"
    elif incident_reasons:
        state = "INCIDENT_REVIEW"
        decision = "INCIDENT_REVIEW"
    elif quota_review:
        state = "CAPACITY_HOLD"
        decision = "CAPACITY_REVIEW"
    elif review_reasons:
        state = "REMEDIATION"
        decision = "REMEDIATE_REVIEW"
    else:
        state = "HEALTHY"
        decision = "RENEWAL_REVIEW_CANDIDATE"

    evidence = {
        "contract_digest": _text(contract_result.get("contract_digest"), 180),
        "customer_id": customer_id,
        "package": package,
        "scope": scope,
        "actual_service_cost_brl": actual_service_cost,
        "health_score": health_score,
        "observed_roi_pct": roi_pct,
        "quota_review": quota_review,
        "sla_review": sla_review,
        "incident_reasons": incident_reasons,
    }

    return {
        "schema": SCHEMA,
        "state": state,
        "decision": decision,
        **scope,
        "customer_id": customer_id,
        "package": package,
        "actual_service_cost_brl": actual_service_cost,
        "health_score": health_score,
        "observed_roi_pct": roi_pct,
        "review_reasons": list(dict.fromkeys(review_reasons)),
        "incident_reasons": incident_reasons,
        "blockers": list(dict.fromkeys(blockers)),
        "evidence_digest": _digest(evidence),
        "owner_review_required": True,
        "automatic_renewal": False,
        "automatic_pause": False,
        "automatic_termination": False,
        "automatic_billing": False,
        "automatic_quota_increase": False,
        "automatic_role_change": False,
        "automatic_integration_change": False,
        "automatic_customer_contact": False,
        "automatic_deploy": False,
        "production_mutation": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "PACKAGES",
    "MAX_ALLOWED_WORKFLOWS",
    "build_managed_service_contract",
    "evaluate_managed_service_cycle",
]
