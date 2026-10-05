"""Bind customer-safe pilot value evidence to one authenticated customer portal.

Pure/offline, fail-closed boundary. The binding requires an already-authorized
read-only customer portal session, an explicit pilot-to-customer binding, and
the CUSTOMER projection of Pilot Value Realization.

It never exposes AtlasQuant internal economics, retention-risk scoring, or
internal recommendations, and it never grants business or production authority.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json

SCHEMA = "ATLASQUANT_AION_B2B_PILOT_CUSTOMER_VALUE_BINDING_V1"
BINDING_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_CUSTOMER_BINDING_V1"
PORTAL_ACCESS_SCHEMA = "ATLASQUANT_AION_B2B_CUSTOMER_PORTAL_V1"
VALUE_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_VALUE_READ_MODEL_V1"

_FORBIDDEN_VALUE_KEYS = {
    "provider_delivery_cost_brl",
    "provider_gross_margin_brl",
    "provider_gross_margin_pct",
    "retention_risk",
    "retention_risk_score",
    "recommendation",
    "review_reasons",
    "low_value_reasons",
    "internal_recommendation",
    "evidence_refs",
}


def _text(value: Any, limit: int = 320) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


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


def _refs(value: Any, limit: int = 50) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:limit]:
        item = _text(raw, 320)
        if item and item not in out:
            out.append(item)
    return out


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    row = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "tenant_id": _text(row.get("tenant_id"), 120),
        "workspace_id": _text(row.get("workspace_id"), 120),
    }


def bind_pilot_value_to_customer_portal(
    *,
    portal_access_result: Mapping[str, Any] | None,
    pilot_binding: Mapping[str, Any] | None,
    pilot_value_read_model: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return a customer-safe pilot-value bundle for one exact portal customer."""
    access = (
        dict(portal_access_result)
        if isinstance(portal_access_result, Mapping)
        else {}
    )
    binding = (
        dict(pilot_binding)
        if isinstance(pilot_binding, Mapping)
        else {}
    )
    value = (
        dict(pilot_value_read_model)
        if isinstance(pilot_value_read_model, Mapping)
        else {}
    )
    blockers: list[str] = []

    if access.get("schema") != PORTAL_ACCESS_SCHEMA:
        blockers.append("PORTAL_ACCESS_SCHEMA_INVALID")
    if access.get("state") != "ALLOW" or access.get("allowed") is not True:
        blockers.append("PORTAL_ACCESS_NOT_ALLOWED")
    if access.get("read_only") is not True:
        blockers.append("PORTAL_ACCESS_NOT_READ_ONLY")
    if access.get("admin_memory_access") is not False:
        blockers.append("PORTAL_ACCESS_ADMIN_MEMORY_UNSAFE")
    if access.get("other_tenant_access") is not False:
        blockers.append("PORTAL_ACCESS_CROSS_TENANT_UNSAFE")
    if access.get("grants_authority") is not False:
        blockers.append("PORTAL_ACCESS_AUTHORITY_UNSAFE")
    if access.get("executes_action") is not False:
        blockers.append("PORTAL_ACCESS_EXECUTION_UNSAFE")
    for key in (
        "automatic_billing",
        "automatic_renewal",
        "automatic_quota_change",
        "automatic_role_change",
        "automatic_customer_contact",
        "automatic_deploy",
        "production_mutation",
    ):
        if access.get(key) is not False:
            blockers.append("PORTAL_ACCESS_UNSAFE_FIELD:" + key)

    customer_id = _text(access.get("customer_id"), 120)
    service_tenant_id = _text(access.get("service_tenant_id"), 120)
    workspace_id = _text(access.get("workspace_id"), 120)
    if not customer_id:
        blockers.append("PORTAL_CUSTOMER_ID_REQUIRED")
    if not service_tenant_id:
        blockers.append("PORTAL_SERVICE_TENANT_REQUIRED")
    if not workspace_id:
        blockers.append("PORTAL_WORKSPACE_REQUIRED")

    if binding.get("schema") != BINDING_SCHEMA:
        blockers.append("PILOT_CUSTOMER_BINDING_SCHEMA_INVALID")
    if _text(binding.get("state"), 40).upper() != "CONFIRMED":
        blockers.append("PILOT_CUSTOMER_BINDING_NOT_CONFIRMED")
    if binding.get("enabled") is not True:
        blockers.append("PILOT_CUSTOMER_BINDING_DISABLED")

    binding_customer = _text(binding.get("customer_id"), 120)
    binding_pilot = _text(binding.get("pilot_id"), 120)
    binding_tenant = _text(binding.get("service_tenant_id"), 120)
    binding_workspace = _text(binding.get("workspace_id"), 120)
    binding_ref = _text(binding.get("binding_ref"), 320)
    if not binding_customer:
        blockers.append("PILOT_BINDING_CUSTOMER_ID_REQUIRED")
    if not binding_pilot:
        blockers.append("PILOT_BINDING_PILOT_ID_REQUIRED")
    if not binding_tenant:
        blockers.append("PILOT_BINDING_SERVICE_TENANT_REQUIRED")
    if not binding_workspace:
        blockers.append("PILOT_BINDING_WORKSPACE_REQUIRED")
    if not binding_ref:
        blockers.append("PILOT_BINDING_REF_REQUIRED")
    binding_refs = _refs(binding.get("evidence_refs"))
    if len(binding_refs) < 3:
        blockers.append("PILOT_BINDING_EVIDENCE_INSUFFICIENT")

    if binding_customer != customer_id:
        blockers.append("PILOT_BINDING_CUSTOMER_MISMATCH")
    if binding_tenant != service_tenant_id:
        blockers.append("PILOT_BINDING_TENANT_MISMATCH")
    if binding_workspace != workspace_id:
        blockers.append("PILOT_BINDING_WORKSPACE_MISMATCH")

    if value.get("schema") != VALUE_SCHEMA:
        blockers.append("PILOT_VALUE_SCHEMA_INVALID")
    if value.get("view") != "CUSTOMER":
        blockers.append("PILOT_VALUE_NOT_CUSTOMER_PROJECTION")
    if value.get("state") != "READY":
        blockers.append("PILOT_VALUE_NOT_READY")
    if value.get("read_only") is not True:
        blockers.append("PILOT_VALUE_NOT_READ_ONLY")
    if value.get("customer_safe") is not True:
        blockers.append("PILOT_VALUE_NOT_CUSTOMER_SAFE")
    if value.get("internal_economics_visible") is not False:
        blockers.append("PILOT_VALUE_INTERNAL_ECONOMICS_UNSAFE")
    if value.get("grants_authority") is not False:
        blockers.append("PILOT_VALUE_AUTHORITY_UNSAFE")
    if value.get("executes_action") is not False:
        blockers.append("PILOT_VALUE_EXECUTION_UNSAFE")

    for key in (
        "provider_delivery_cost_exposed",
        "provider_margin_exposed",
        "retention_risk_exposed",
        "internal_recommendation_exposed",
        "renewal_control_exposed",
        "expansion_control_exposed",
        "billing_control_exposed",
        "customer_contact_control_exposed",
    ):
        if value.get(key) is not False:
            blockers.append("PILOT_VALUE_UNSAFE_FIELD:" + key)

    forbidden_present = sorted(
        key for key in _FORBIDDEN_VALUE_KEYS if key in value
    )
    if forbidden_present:
        blockers.extend(
            "PILOT_VALUE_FORBIDDEN_FIELD:" + key
            for key in forbidden_present
        )

    value_scope = _scope(
        value.get("scope")
        if isinstance(value.get("scope"), Mapping)
        else {}
    )
    if value_scope["tenant_id"] != binding_tenant:
        blockers.append("PILOT_VALUE_TENANT_MISMATCH")
    if value_scope["workspace_id"] != binding_workspace:
        blockers.append("PILOT_VALUE_WORKSPACE_MISMATCH")
    if _text(value.get("pilot_id"), 120) != binding_pilot:
        blockers.append("PILOT_VALUE_PILOT_MISMATCH")
    value_digest = _text(value.get("evidence_digest"), 180)
    if not value_digest:
        blockers.append("PILOT_VALUE_EVIDENCE_REQUIRED")

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "allowed": False,
            "blockers": blockers,
            "read_only": True,
            "customer_safe": True,
            "internal_economics_exposed": False,
            "retention_risk_exposed": False,
            "internal_recommendation_exposed": False,
            "grants_authority": False,
            "automatic_billing": False,
            "automatic_renewal": False,
            "automatic_expansion": False,
            "automatic_customer_contact": False,
            "automatic_deploy": False,
            "production_mutation": False,
            "executes_action": False,
        }

    quick_wins: list[dict[str, Any]] = []
    for raw in list(value.get("quick_wins") or [])[:5]:
        if not isinstance(raw, Mapping):
            continue
        quick_wins.append(
            {
                "quick_win": _text(raw.get("quick_win"), 240),
                "state": _text(raw.get("state"), 40),
                "achieved": raw.get("achieved") is True,
            }
        )

    safe_value = {
        "value_state": _text(value.get("value_state"), 80),
        "health_score": value.get("health_score"),
        "value_trend": _text(value.get("value_trend"), 40),
        "quick_win_completion_pct": value.get("quick_win_completion_pct"),
        "quick_win_achieved_pct": value.get("quick_win_achieved_pct"),
        "quick_wins": quick_wins,
        "observed_savings_brl": value.get("observed_savings_brl"),
        "observed_roi_pct": value.get("observed_roi_pct"),
        "customer_fee_brl": value.get("customer_fee_brl"),
        "customer_value_to_fee_ratio": value.get(
            "customer_value_to_fee_ratio"
        ),
        "customer_net_value_brl": value.get("customer_net_value_brl"),
        "customer_payback_covered": value.get(
            "customer_payback_covered"
        ),
        "evidence_digest": value_digest,
    }
    evidence = {
        "customer_id": customer_id,
        "pilot_id": binding_pilot,
        "service_tenant_id": service_tenant_id,
        "workspace_id": workspace_id,
        "binding_ref": binding_ref,
        "binding_evidence_refs": binding_refs,
        "pilot_value_evidence_digest": value_digest,
        "pilot_value": safe_value,
    }

    return {
        "schema": SCHEMA,
        "state": "READY",
        "allowed": True,
        "customer_id": customer_id,
        "pilot_id": binding_pilot,
        "service_tenant_id": service_tenant_id,
        "workspace_id": workspace_id,
        "binding_ref": binding_ref,
        "pilot_value": safe_value,
        "evidence_digest": _digest(evidence),
        "read_only": True,
        "customer_safe": True,
        "internal_economics_exposed": False,
        "retention_risk_exposed": False,
        "internal_recommendation_exposed": False,
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
    "BINDING_SCHEMA",
    "PORTAL_ACCESS_SCHEMA",
    "VALUE_SCHEMA",
    "bind_pilot_value_to_customer_portal",
]
