"""Read-only admin projection for B2B multi-company admission.

The projection exposes aggregate capacity/admission status only. It never
exposes identities of other active tenants and never exposes tenant creation,
quota mutation, provisioning or billing controls.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_B2B_MULTI_COMPANY_READ_MODEL_V1"
SOURCE_SCHEMA = "ATLASQUANT_AION_B2B_MULTI_COMPANY_ADMISSION_V1"
_PRESENTABLE = {
    "REVIEWABLE",
    "CAPACITY_HOLD",
    "ISOLATION_HOLD",
}


def _text(value: Any, limit: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    row = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(row.get("owner_id"), 120),
        "tenant_id": _text(row.get("tenant_id"), 120),
        "workspace_id": _text(row.get("workspace_id"), 120),
    }


def build_multi_company_admission_read_model(
    admission_result: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = (
        dict(admission_result)
        if isinstance(admission_result, Mapping)
        else {}
    )
    trusted = _scope(trusted_scope)
    blockers: list[str] = []

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")
    if row.get("schema") != SOURCE_SCHEMA:
        blockers.append("MULTI_COMPANY_ADMISSION_SCHEMA_INVALID")
    if row.get("state") not in _PRESENTABLE:
        blockers.append("MULTI_COMPANY_ADMISSION_STATE_NOT_PRESENTABLE")
    if row.get("decision") not in {
        "TENANT_ADMISSION_REVIEW_CANDIDATE",
        "CAPACITY_REVIEW",
        "ISOLATION_REVIEW",
    }:
        blockers.append("MULTI_COMPANY_ADMISSION_DECISION_INVALID")
    if row.get("blockers"):
        blockers.append("MULTI_COMPANY_ADMISSION_HAS_BLOCKERS")
    if row.get("owner_admission_approval_required") is not True:
        blockers.append("OWNER_ADMISSION_BOUNDARY_MISSING")
    if not _text(row.get("evidence_digest"), 180):
        blockers.append("MULTI_COMPANY_ADMISSION_EVIDENCE_REQUIRED")

    for key in (
        "tenant_creation_authorized",
        "quota_change_authorized",
        "admission_token_issued",
        "automatic_tenant_creation",
        "automatic_quota_change",
        "automatic_package_change",
        "automatic_pricing_change",
        "automatic_contract_change",
        "automatic_billing",
        "automatic_provisioning",
        "automatic_customer_contact",
        "automatic_deploy",
        "crm_write",
        "provider_called",
        "production_mutation",
        "executes_action",
    ):
        if row.get(key) is not False:
            blockers.append("MULTI_COMPANY_ADMISSION_UNSAFE_FIELD:" + key)

    tenant_id = _text(row.get("service_tenant_id"), 80)
    package = _text(row.get("package"), 40)
    if not tenant_id:
        blockers.append("SERVICE_TENANT_ID_REQUIRED")
    if not package:
        blockers.append("PACKAGE_REQUIRED")

    projected = (
        dict(row.get("projected_portfolio"))
        if isinstance(row.get("projected_portfolio"), Mapping)
        else {}
    )
    quota_view: dict[str, dict[str, Any]] = {}
    reserve_values: list[float] = []
    share_values: list[float] = []

    for key in (
        "capacity_units",
        "calls_per_cycle",
        "tokens_per_cycle",
        "support_tickets_per_cycle",
    ):
        source = (
            dict(projected.get(key))
            if isinstance(projected.get(key), Mapping)
            else {}
        )
        if not source:
            blockers.append("PROJECTED_QUOTA_MISSING:" + key)
            continue
        reserve = source.get("reserve_pct")
        share = source.get("single_tenant_share_pct")
        if isinstance(reserve, bool) or not isinstance(reserve, (int, float)):
            blockers.append("PROJECTED_RESERVE_INVALID:" + key)
            continue
        if isinstance(share, bool) or not isinstance(share, (int, float)):
            blockers.append("PROJECTED_SHARE_INVALID:" + key)
            continue
        reserve_values.append(float(reserve))
        share_values.append(float(share))
        quota_view[key] = {
            "requested": source.get("requested"),
            "projected_allocated": source.get("projected_allocated"),
            "portfolio_limit": source.get("portfolio_limit"),
            "reserve_pct": round(float(reserve), 2),
            "single_tenant_share_pct": round(float(share), 2),
        }

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "blockers": blockers,
            "read_only": True,
            "other_tenant_identity_exposed": False,
            "tenant_creation_control_exposed": False,
            "quota_control_exposed": False,
            "grants_authority": False,
            "executes_action": False,
        }

    return {
        "schema": SCHEMA,
        "state": "READY",
        "scope": trusted,
        "admission_state": row.get("state"),
        "admission_decision": row.get("decision"),
        "service_tenant_id": tenant_id,
        "package": package,
        "projected_active_tenants": row.get("projected_active_tenants"),
        "quota_projection": quota_view,
        "minimum_portfolio_reserve_pct": (
            round(min(reserve_values), 2)
            if reserve_values
            else None
        ),
        "maximum_single_tenant_share_pct": (
            round(max(share_values), 2)
            if share_values
            else None
        ),
        "capacity_reason_count": len(
            list(row.get("capacity_reasons") or [])
        ),
        "isolation_reason_count": len(
            list(row.get("isolation_reasons") or [])
        ),
        "review_reasons": [
            _text(item, 180)
            for item in list(row.get("review_reasons") or [])[:12]
            if _text(item, 180)
        ],
        "evidence_digest": _text(row.get("evidence_digest"), 180),
        "owner_admission_approval_required": True,
        "read_only": True,
        "other_tenant_identity_exposed": False,
        "customer_identity_exposed": False,
        "tenant_creation_control_exposed": False,
        "quota_control_exposed": False,
        "provisioning_control_exposed": False,
        "billing_control_exposed": False,
        "grants_authority": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "SOURCE_SCHEMA",
    "build_multi_company_admission_read_model",
]
