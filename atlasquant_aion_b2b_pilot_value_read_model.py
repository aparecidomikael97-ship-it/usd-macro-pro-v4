"""Read-only projections for B2B pilot value realization.

Admin projection may expose internal unit economics to the trusted AtlasQuant
business cockpit. Customer projection intentionally removes provider margin,
delivery cost, retention-risk scoring and internal recommendation logic.

Neither projection grants authority or executes actions.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_B2B_PILOT_VALUE_READ_MODEL_V1"
SOURCE_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_VALUE_REALIZATION_V1"

_PRESENTABLE_STATES = {
    "STRONG_VALUE",
    "VALUE_CONFIRMED",
    "VALUE_AT_RISK",
    "LOW_VALUE",
    "STOP_REVIEW",
    "EVIDENCE_INCOMPLETE",
}


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


def _validate(
    value_result: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, str], list[str]]:
    row = dict(value_result) if isinstance(value_result, Mapping) else {}
    trusted = _scope(trusted_scope)
    blockers: list[str] = []

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")
    if row.get("schema") != SOURCE_SCHEMA:
        blockers.append("VALUE_REALIZATION_SCHEMA_INVALID")
    if row.get("state") not in _PRESENTABLE_STATES:
        blockers.append("VALUE_REALIZATION_STATE_NOT_PRESENTABLE")
    if row.get("recommendation") in {None, "", "BLOCKED"}:
        blockers.append("VALUE_REALIZATION_RECOMMENDATION_INVALID")
    if _scope(row.get("scope")) != trusted:
        blockers.append("VALUE_REALIZATION_SCOPE_MISMATCH")
    if not _text(row.get("pilot_id"), 120):
        blockers.append("VALUE_REALIZATION_PILOT_ID_REQUIRED")
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

    return row, trusted, list(dict.fromkeys(blockers))


def build_pilot_value_admin_read_model(
    value_result: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row, trusted, blockers = _validate(
        value_result,
        trusted_scope=trusted_scope,
    )
    if blockers:
        return {
            "schema": SCHEMA,
            "view": "ADMIN",
            "state": "BLOCKED",
            "blockers": blockers,
            "read_only": True,
            "internal_economics_visible": False,
            "customer_safe": False,
            "grants_authority": False,
            "executes_action": False,
        }

    packet = (
        dict(row.get("review_packet"))
        if isinstance(row.get("review_packet"), Mapping)
        else {}
    )
    return {
        "schema": SCHEMA,
        "view": "ADMIN",
        "state": "READY",
        "scope": trusted,
        "pilot_id": _text(row.get("pilot_id"), 120),
        "value_state": row.get("state"),
        "recommendation": row.get("recommendation"),
        "health_score": row.get("health_score"),
        "value_trend": row.get("value_trend"),
        "quick_win_completion_pct": row.get("quick_win_completion_pct"),
        "quick_win_achieved_pct": row.get("quick_win_achieved_pct"),
        "observed_savings_brl": row.get("observed_savings_brl"),
        "observed_roi_pct": row.get("observed_roi_pct"),
        "customer_fee_brl": row.get("customer_fee_brl"),
        "customer_value_to_fee_ratio": row.get(
            "customer_value_to_fee_ratio"
        ),
        "customer_net_value_brl": row.get("customer_net_value_brl"),
        "customer_payback_covered": row.get("customer_payback_covered"),
        "provider_delivery_cost_brl": row.get(
            "provider_delivery_cost_brl"
        ),
        "provider_gross_margin_brl": row.get(
            "provider_gross_margin_brl"
        ),
        "provider_gross_margin_pct": row.get(
            "provider_gross_margin_pct"
        ),
        "retention_risk": row.get("retention_risk"),
        "retention_risk_score": row.get("retention_risk_score"),
        "low_value_alert": row.get("low_value_alert") is True,
        "review_reasons": [
            _text(item, 180)
            for item in list(packet.get("review_reasons") or [])[:12]
            if _text(item, 180)
        ],
        "evidence_digest": _text(row.get("evidence_digest"), 180),
        "owner_review_required": True,
        "read_only": True,
        "internal_economics_visible": True,
        "customer_safe": False,
        "renewal_control_exposed": False,
        "expansion_control_exposed": False,
        "billing_control_exposed": False,
        "customer_contact_control_exposed": False,
        "grants_authority": False,
        "executes_action": False,
    }


def build_pilot_value_customer_read_model(
    value_result: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row, trusted, blockers = _validate(
        value_result,
        trusted_scope=trusted_scope,
    )
    if blockers:
        return {
            "schema": SCHEMA,
            "view": "CUSTOMER",
            "state": "BLOCKED",
            "blockers": blockers,
            "read_only": True,
            "internal_economics_visible": False,
            "customer_safe": True,
            "grants_authority": False,
            "executes_action": False,
        }

    quick_wins: list[dict[str, Any]] = []
    for raw in list(row.get("quick_win_progress") or [])[:5]:
        if not isinstance(raw, Mapping):
            continue
        quick_wins.append(
            {
                "quick_win": _text(raw.get("quick_win"), 240),
                "state": _text(raw.get("state"), 40),
                "achieved": raw.get("achieved") is True,
            }
        )

    return {
        "schema": SCHEMA,
        "view": "CUSTOMER",
        "state": "READY",
        "scope": {
            "tenant_id": trusted["tenant_id"],
            "workspace_id": trusted["workspace_id"],
        },
        "pilot_id": _text(row.get("pilot_id"), 120),
        "value_state": row.get("state"),
        "health_score": row.get("health_score"),
        "value_trend": row.get("value_trend"),
        "quick_win_completion_pct": row.get("quick_win_completion_pct"),
        "quick_win_achieved_pct": row.get("quick_win_achieved_pct"),
        "quick_wins": quick_wins,
        "observed_savings_brl": row.get("observed_savings_brl"),
        "observed_roi_pct": row.get("observed_roi_pct"),
        "customer_fee_brl": row.get("customer_fee_brl"),
        "customer_value_to_fee_ratio": row.get(
            "customer_value_to_fee_ratio"
        ),
        "customer_net_value_brl": row.get("customer_net_value_brl"),
        "customer_payback_covered": row.get("customer_payback_covered"),
        "evidence_digest": _text(row.get("evidence_digest"), 180),
        "read_only": True,
        "internal_economics_visible": False,
        "customer_safe": True,
        "provider_delivery_cost_exposed": False,
        "provider_margin_exposed": False,
        "retention_risk_exposed": False,
        "internal_recommendation_exposed": False,
        "renewal_control_exposed": False,
        "expansion_control_exposed": False,
        "billing_control_exposed": False,
        "customer_contact_control_exposed": False,
        "grants_authority": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "SOURCE_SCHEMA",
    "build_pilot_value_admin_read_model",
    "build_pilot_value_customer_read_model",
]
