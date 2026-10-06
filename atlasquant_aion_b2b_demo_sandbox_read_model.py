"""Read-only Admin projection for the governed B2B demo sandbox.

This projection exposes only synthetic demo configuration and review state.
It deliberately omits customer identity, evidence internals, credentials,
provider details, and all creation/provisioning controls.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_B2B_DEMO_SANDBOX_READ_MODEL_V1"
SOURCE_SCHEMA = "ATLASQUANT_AION_B2B_DEMO_SANDBOX_V1"


def _text(value: Any, limit: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def build_demo_sandbox_read_model(
    sandbox_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = dict(sandbox_result) if isinstance(sandbox_result, Mapping) else {}
    blockers: list[str] = []

    if row.get("schema") != SOURCE_SCHEMA:
        blockers.append("DEMO_SANDBOX_SCHEMA_INVALID")
    if row.get("state") != "REVIEWABLE":
        blockers.append("DEMO_SANDBOX_NOT_REVIEWABLE")
    if row.get("decision") != "SANDBOX_REVIEW_CANDIDATE":
        blockers.append("DEMO_SANDBOX_DECISION_INVALID")
    if row.get("blockers"):
        blockers.append("DEMO_SANDBOX_HAS_BLOCKERS")
    if row.get("owner_sandbox_approval_required") is not True:
        blockers.append("DEMO_SANDBOX_OWNER_BOUNDARY_MISSING")
    if not _text(row.get("evidence_digest"), 180):
        blockers.append("DEMO_SANDBOX_EVIDENCE_REQUIRED")
    if _text(row.get("dataset_class"), 40).upper() != "SYNTHETIC":
        blockers.append("DEMO_SANDBOX_NOT_SYNTHETIC")

    for key in (
        "sandbox_creation_authorized",
        "tenant_creation_authorized",
        "quota_change_authorized",
        "credential_use_authorized",
        "live_integration_authorized",
        "customer_data_use_authorized",
        "outbound_contact_authorized",
        "billing_authorized",
        "automatic_sandbox_creation",
        "automatic_tenant_creation",
        "automatic_quota_change",
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
            blockers.append("DEMO_SANDBOX_UNSAFE_FIELD:" + key)

    sandbox_id = _text(row.get("sandbox_id"), 80)
    service_tenant_id = _text(row.get("service_tenant_id"), 80)
    package = _text(row.get("package"), 40)
    duration = row.get("duration_hours")
    records = row.get("synthetic_records")
    sessions = row.get("concurrent_sessions")

    if not sandbox_id:
        blockers.append("SANDBOX_ID_REQUIRED")
    if not service_tenant_id:
        blockers.append("SERVICE_TENANT_ID_REQUIRED")
    if not package:
        blockers.append("PACKAGE_REQUIRED")

    for key, value in (
        ("duration_hours", duration),
        ("synthetic_records", records),
        ("concurrent_sessions", sessions),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            blockers.append("INVALID_" + key.upper())

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "blockers": blockers,
            "read_only": True,
            "synthetic_only": True,
            "customer_identity_exposed": False,
            "evidence_internals_exposed": False,
            "credential_details_exposed": False,
            "provider_details_exposed": False,
            "sandbox_creation_control_exposed": False,
            "tenant_creation_control_exposed": False,
            "quota_control_exposed": False,
            "provisioning_control_exposed": False,
            "billing_control_exposed": False,
            "customer_contact_control_exposed": False,
            "grants_authority": False,
            "executes_action": False,
        }

    return {
        "schema": SCHEMA,
        "state": "READY",
        "sandbox_state": row.get("state"),
        "sandbox_decision": row.get("decision"),
        "sandbox_id": sandbox_id,
        "service_tenant_id": service_tenant_id,
        "package": package,
        "dataset_class": "SYNTHETIC",
        "duration_hours": duration,
        "synthetic_records": records,
        "concurrent_sessions": sessions,
        "evidence_digest": _text(row.get("evidence_digest"), 180),
        "owner_sandbox_approval_required": True,
        "read_only": True,
        "synthetic_only": True,
        "customer_identity_exposed": False,
        "evidence_internals_exposed": False,
        "credential_details_exposed": False,
        "provider_details_exposed": False,
        "sandbox_creation_control_exposed": False,
        "tenant_creation_control_exposed": False,
        "quota_control_exposed": False,
        "provisioning_control_exposed": False,
        "billing_control_exposed": False,
        "customer_contact_control_exposed": False,
        "grants_authority": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "SOURCE_SCHEMA",
    "build_demo_sandbox_read_model",
]
