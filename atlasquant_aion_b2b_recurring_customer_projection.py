"""Customer-safe recurring service projection for the AION B2B portal.

This pure/offline projection consumes an already-authorized customer portal
access decision, the value-bound recurring service cycle, and the existing
managed-service read model. It exposes only customer-safe health, value, usage
and SLA evidence. Internal FinOps, margin, retention, renewal/expansion
recommendations, review reasons and owner choices are deliberately omitted.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from atlasquant_aion_b2b_customer_portal import SCHEMA as PORTAL_SCHEMA
from atlasquant_aion_b2b_value_bound_service_cycle import (
    SCHEMA as SERVICE_CYCLE_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_B2B_RECURRING_CUSTOMER_PROJECTION_V1"
READ_MODEL_SCHEMA = "ATLASQUANT_AION_B2B_PORTAL_READ_MODEL_V1"

SAFE_STATUS = {
    "HEALTHY": "SAUDÁVEL",
    "REMEDIATION": "EM ACOMPANHAMENTO",
    "CAPACITY_HOLD": "CAPACIDADE EM REVISÃO",
    "INCIDENT_REVIEW": "EM ANÁLISE",
}

UNSAFE_CYCLE_FIELDS = (
    "automatic_renewal",
    "automatic_expansion",
    "automatic_package_change",
    "automatic_pause",
    "automatic_termination",
    "automatic_billing",
    "automatic_quota_increase",
    "automatic_role_change",
    "automatic_integration_change",
    "automatic_customer_contact",
    "automatic_provisioning",
    "automatic_deploy",
    "provider_called",
    "production_mutation",
    "executes_action",
)


def _text(value: Any, limit: int = 320) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


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
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _copy_usage(raw: Any) -> dict[str, dict[str, Any]]:
    source = raw if isinstance(raw, Mapping) else {}
    out: dict[str, dict[str, Any]] = {}
    for key in ("capacity", "calls", "tokens", "support_tickets"):
        row = source.get(key) if isinstance(source.get(key), Mapping) else {}
        out[key] = {
            "used": row.get("used"),
            "limit": row.get("limit"),
            "utilization_pct": row.get("utilization_pct"),
        }
    return out


def build_recurring_customer_projection(
    *,
    portal_access_result: Mapping[str, Any],
    service_cycle: Mapping[str, Any],
    service_read_model: Mapping[str, Any],
) -> dict[str, Any]:
    access = (
        dict(portal_access_result)
        if isinstance(portal_access_result, Mapping)
        else {}
    )
    cycle = dict(service_cycle) if isinstance(service_cycle, Mapping) else {}
    model = (
        dict(service_read_model)
        if isinstance(service_read_model, Mapping)
        else {}
    )
    blockers: list[str] = []

    if access.get("schema") != PORTAL_SCHEMA:
        blockers.append("PORTAL_ACCESS_SCHEMA_INVALID")
    if access.get("state") != "ALLOW" or access.get("allowed") is not True:
        blockers.append("PORTAL_ACCESS_NOT_ALLOWED")
    if access.get("read_only") is not True:
        blockers.append("PORTAL_ACCESS_NOT_READ_ONLY")
    if access.get("other_tenant_access") is not False:
        blockers.append("PORTAL_ACCESS_CROSS_TENANT_UNSAFE")
    if access.get("admin_memory_access") is not False:
        blockers.append("PORTAL_ACCESS_ADMIN_MEMORY_UNSAFE")
    if access.get("grants_authority") is not False:
        blockers.append("PORTAL_ACCESS_AUTHORITY_UNSAFE")
    if access.get("executes_action") is not False:
        blockers.append("PORTAL_ACCESS_EXECUTION_UNSAFE")

    customer_id = _text(access.get("customer_id"), 120)
    service_tenant_id = _text(access.get("service_tenant_id"), 120)
    workspace_id = _text(access.get("workspace_id"), 120)
    package = _text(access.get("package"), 40).upper()
    if not customer_id:
        blockers.append("PORTAL_CUSTOMER_ID_REQUIRED")
    if not service_tenant_id:
        blockers.append("PORTAL_SERVICE_TENANT_REQUIRED")
    if not workspace_id:
        blockers.append("PORTAL_WORKSPACE_REQUIRED")
    if not package:
        blockers.append("PORTAL_PACKAGE_REQUIRED")

    if cycle.get("schema") != SERVICE_CYCLE_SCHEMA:
        blockers.append("SERVICE_CYCLE_SCHEMA_INVALID")
    if cycle.get("blockers"):
        blockers.append("SERVICE_CYCLE_HAS_BLOCKERS")
    if cycle.get("owner_review_required") is not True:
        blockers.append("SERVICE_CYCLE_OWNER_REVIEW_BOUNDARY_MISSING")
    if cycle.get("customer_visible") is not False:
        blockers.append("SERVICE_CYCLE_INTERNAL_VISIBILITY_UNSAFE")
    if cycle.get("contains_internal_finops") is not True:
        blockers.append("SERVICE_CYCLE_INTERNAL_FINOPS_MARKER_REQUIRED")
    if cycle.get("requires_customer_safe_projection") is not True:
        blockers.append("SERVICE_CYCLE_SAFE_PROJECTION_BOUNDARY_MISSING")

    cycle_scope = _scope(cycle.get("scope"))
    if cycle_scope["tenant_id"] != service_tenant_id:
        blockers.append("SERVICE_CYCLE_TENANT_MISMATCH")
    if cycle_scope["workspace_id"] != workspace_id:
        blockers.append("SERVICE_CYCLE_WORKSPACE_MISMATCH")
    if _text(cycle.get("customer_id"), 120) != customer_id:
        blockers.append("SERVICE_CYCLE_CUSTOMER_MISMATCH")
    if _text(cycle.get("package"), 40).upper() != package:
        blockers.append("SERVICE_CYCLE_PACKAGE_MISMATCH")

    pilot_id = _text(cycle.get("pilot_id"), 120)
    if not pilot_id:
        blockers.append("SERVICE_CYCLE_PILOT_ID_REQUIRED")
    if cycle.get("state") not in SAFE_STATUS:
        blockers.append("SERVICE_CYCLE_STATE_NOT_CUSTOMER_PROJECTABLE")
    if not _text(cycle.get("evidence_digest"), 180):
        blockers.append("SERVICE_CYCLE_EVIDENCE_REQUIRED")

    for key in UNSAFE_CYCLE_FIELDS:
        if cycle.get(key) is not False:
            blockers.append("SERVICE_CYCLE_UNSAFE_FIELD:" + key)

    if model.get("schema") != READ_MODEL_SCHEMA:
        blockers.append("SERVICE_READ_MODEL_SCHEMA_INVALID")
    if model.get("state") != "READY":
        blockers.append("SERVICE_READ_MODEL_NOT_READY")
    if model.get("read_only") is not True:
        blockers.append("SERVICE_READ_MODEL_NOT_READ_ONLY")
    if model.get("grants_authority") is not False:
        blockers.append("SERVICE_READ_MODEL_AUTHORITY_UNSAFE")
    if model.get("executes_action") is not False:
        blockers.append("SERVICE_READ_MODEL_EXECUTION_UNSAFE")
    if not _text(model.get("evidence_digest"), 180):
        blockers.append("SERVICE_READ_MODEL_EVIDENCE_REQUIRED")

    model_scope = _scope(model.get("scope"))
    if model_scope["tenant_id"] != service_tenant_id:
        blockers.append("SERVICE_READ_MODEL_TENANT_MISMATCH")
    if model_scope["workspace_id"] != workspace_id:
        blockers.append("SERVICE_READ_MODEL_WORKSPACE_MISMATCH")
    if _text(model.get("customer_id"), 120) != customer_id:
        blockers.append("SERVICE_READ_MODEL_CUSTOMER_MISMATCH")
    if _text(model.get("package"), 40).upper() != package:
        blockers.append("SERVICE_READ_MODEL_PACKAGE_MISMATCH")

    if model.get("service_state") != cycle.get("state"):
        blockers.append("SERVICE_STATE_LINEAGE_MISMATCH")

    support = (
        dict(model.get("support"))
        if isinstance(model.get("support"), Mapping)
        else {}
    )
    generated_at = _text(model.get("generated_at"), 96)
    if not generated_at:
        blockers.append("GENERATED_AT_REQUIRED")

    safe_status = SAFE_STATUS.get(str(cycle.get("state")), "")
    safe_usage = _copy_usage(model.get("usage"))
    safe_support = {
        "avg_first_response_hours": support.get("avg_first_response_hours"),
        "avg_resolution_hours": support.get("avg_resolution_hours"),
        "critical_open_tickets": support.get("critical_open_tickets"),
        "first_response_sla_met": support.get("first_response_sla_met") is True,
        "resolution_sla_met": support.get("resolution_sla_met") is True,
    }

    evidence = {
        "customer_id": customer_id,
        "pilot_id": pilot_id,
        "service_tenant_id": service_tenant_id,
        "workspace_id": workspace_id,
        "package": package,
        "service_status": safe_status,
        "health_score": model.get("health_score"),
        "observed_roi_pct": model.get("observed_roi_pct"),
        "usage": safe_usage,
        "support": safe_support,
        "service_cycle_digest": _text(cycle.get("evidence_digest"), 180),
        "service_read_model_digest": _text(
            model.get("evidence_digest"),
            180,
        ),
        "generated_at": generated_at,
    }

    if blockers:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "allowed": False,
            "customer_id": customer_id,
            "pilot_id": pilot_id,
            "service_tenant_id": service_tenant_id,
            "workspace_id": workspace_id,
            "package": package,
            "blockers": list(dict.fromkeys(blockers)),
            "read_only": True,
            "customer_safe": True,
            "internal_service_cost_exposed": False,
            "provider_margin_exposed": False,
            "retention_risk_exposed": False,
            "internal_recommendation_exposed": False,
            "internal_review_reasons_exposed": False,
            "other_tenant_access": False,
            "admin_memory_access": False,
            "grants_authority": False,
            "automatic_billing": False,
            "automatic_renewal": False,
            "automatic_expansion": False,
            "automatic_customer_contact": False,
            "automatic_deploy": False,
            "production_mutation": False,
            "executes_action": False,
        }

    return {
        "schema": SCHEMA,
        "state": "READY",
        "allowed": True,
        "customer_id": customer_id,
        "pilot_id": pilot_id,
        "service_tenant_id": service_tenant_id,
        "workspace_id": workspace_id,
        "package": package,
        "service_status": safe_status,
        "health_label": safe_status,
        "health_score": model.get("health_score"),
        "observed_roi_pct": model.get("observed_roi_pct"),
        "usage": safe_usage,
        "support": safe_support,
        "generated_at": generated_at,
        "service_cycle_evidence_digest": _text(
            cycle.get("evidence_digest"),
            180,
        ),
        "service_read_model_evidence_digest": _text(
            model.get("evidence_digest"),
            180,
        ),
        "evidence_digest": _digest(evidence),
        "blockers": [],
        "read_only": True,
        "customer_safe": True,
        "internal_service_cost_exposed": False,
        "provider_margin_exposed": False,
        "retention_risk_exposed": False,
        "internal_recommendation_exposed": False,
        "internal_review_reasons_exposed": False,
        "other_tenant_access": False,
        "admin_memory_access": False,
        "grants_authority": False,
        "automatic_billing": False,
        "automatic_renewal": False,
        "automatic_expansion": False,
        "automatic_customer_contact": False,
        "automatic_deploy": False,
        "production_mutation": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "READ_MODEL_SCHEMA",
    "SAFE_STATUS",
    "build_recurring_customer_projection",
]
