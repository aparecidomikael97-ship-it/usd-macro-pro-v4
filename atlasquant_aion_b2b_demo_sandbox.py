"""AION B2B Demo/Sandbox Review Gate V1.

Pure/offline governance for a synthetic demonstration sandbox.

This module decides only whether a proposed sandbox package is reviewable by a
human owner. It never creates infrastructure, provisions a tenant, uses real
customer data, enables live integrations, calls providers, bills, writes CRM,
deploys or mutates production.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json
import math
import re

SCHEMA = "ATLASQUANT_AION_B2B_DEMO_SANDBOX_V1"
ADMISSION_SCHEMA = "ATLASQUANT_AION_B2B_MULTI_COMPANY_ADMISSION_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_B2B_DEMO_SANDBOX_POLICY_V1"

_SAFE_SANDBOX_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{7,79}$")


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


def _positive_int(value: Any, *, allow_zero: bool = False) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    minimum = 0 if allow_zero else 1
    return value if value >= minimum else None


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


def _validate_admission(
    admission_result: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    row = dict(admission_result) if isinstance(admission_result, Mapping) else {}
    blockers: list[str] = []

    if row.get("schema") != ADMISSION_SCHEMA:
        blockers.append("ADMISSION_SCHEMA_INVALID")
    if row.get("state") != "REVIEWABLE":
        blockers.append("ADMISSION_NOT_REVIEWABLE")
    if row.get("decision") != "TENANT_ADMISSION_REVIEW_CANDIDATE":
        blockers.append("ADMISSION_DECISION_INVALID")
    if row.get("review_reasons"):
        blockers.append("ADMISSION_HAS_REVIEW_REASONS")
    if row.get("blockers"):
        blockers.append("ADMISSION_HAS_BLOCKERS")
    if row.get("owner_admission_approval_required") is not True:
        blockers.append("ADMISSION_OWNER_BOUNDARY_MISSING")
    if not _text(row.get("evidence_digest"), 180):
        blockers.append("ADMISSION_EVIDENCE_REQUIRED")

    unsafe_false = (
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
    )
    for key in unsafe_false:
        if row.get(key) is not False:
            blockers.append("ADMISSION_UNSAFE_FIELD:" + key)

    return row, list(dict.fromkeys(blockers))


def _validate_policy(
    policy: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    row = dict(policy) if isinstance(policy, Mapping) else {}
    blockers: list[str] = []

    if row.get("schema") != POLICY_SCHEMA:
        blockers.append("SANDBOX_POLICY_SCHEMA_INVALID")
    if row.get("state") != "VERIFIED":
        blockers.append("SANDBOX_POLICY_NOT_VERIFIED")
    if _scope(row) != _scope(trusted_scope):
        blockers.append("SANDBOX_POLICY_SCOPE_MISMATCH")

    max_duration_hours = _positive_int(row.get("max_duration_hours"))
    max_synthetic_records = _positive_int(row.get("max_synthetic_records"))
    max_concurrent_sessions = _positive_int(row.get("max_concurrent_sessions"))
    if max_duration_hours is None or max_duration_hours > 168:
        blockers.append("SANDBOX_MAX_DURATION_INVALID")
    if max_synthetic_records is None or max_synthetic_records > 100000:
        blockers.append("SANDBOX_MAX_RECORDS_INVALID")
    if max_concurrent_sessions is None or max_concurrent_sessions > 100:
        blockers.append("SANDBOX_MAX_SESSIONS_INVALID")

    if row.get("synthetic_data_only") is not True:
        blockers.append("SANDBOX_POLICY_MUST_REQUIRE_SYNTHETIC_DATA")
    if row.get("production_credentials_forbidden") is not True:
        blockers.append("SANDBOX_POLICY_MUST_FORBID_PRODUCTION_CREDENTIALS")
    if row.get("live_integrations_forbidden") is not True:
        blockers.append("SANDBOX_POLICY_MUST_FORBID_LIVE_INTEGRATIONS")
    if row.get("outbound_channels_forbidden") is not True:
        blockers.append("SANDBOX_POLICY_MUST_FORBID_OUTBOUND_CHANNELS")

    refs = _refs(row.get("evidence_refs"))
    if len(refs) < 3:
        blockers.append("SANDBOX_POLICY_EVIDENCE_INSUFFICIENT")

    normalized = {
        "max_duration_hours": max_duration_hours,
        "max_synthetic_records": max_synthetic_records,
        "max_concurrent_sessions": max_concurrent_sessions,
        "evidence_refs": refs,
    }
    return normalized, list(dict.fromkeys(blockers))


def evaluate_demo_sandbox(
    *,
    trusted_scope: Mapping[str, Any],
    admission_result: Mapping[str, Any],
    demo_request: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate a synthetic demo sandbox package without executing anything."""
    trusted = _scope(trusted_scope)
    blockers: list[str] = []

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")

    admission, admission_blockers = _validate_admission(
        admission_result,
        trusted_scope=trusted_scope,
    )
    blockers.extend(admission_blockers)

    policy_data, policy_blockers = _validate_policy(
        policy,
        trusted_scope=trusted_scope,
    )
    blockers.extend(policy_blockers)

    request = dict(demo_request) if isinstance(demo_request, Mapping) else {}
    if _scope(request) != trusted:
        blockers.append("SANDBOX_REQUEST_SCOPE_MISMATCH")

    sandbox_id = _text(request.get("sandbox_id"), 80).lower()
    if _SAFE_SANDBOX_ID.fullmatch(sandbox_id) is None:
        blockers.append("SANDBOX_ID_INVALID")

    customer_id = _text(request.get("customer_id"), 120)
    service_tenant_id = _text(request.get("service_tenant_id"), 80).lower()
    package = _text(request.get("package"), 40).upper()

    if customer_id != _text(admission.get("customer_id"), 120):
        blockers.append("SANDBOX_CUSTOMER_ADMISSION_MISMATCH")
    if service_tenant_id != _text(admission.get("service_tenant_id"), 80).lower():
        blockers.append("SANDBOX_TENANT_ADMISSION_MISMATCH")
    if package != _text(admission.get("package"), 40).upper():
        blockers.append("SANDBOX_PACKAGE_ADMISSION_MISMATCH")

    if _text(request.get("dataset_class"), 40).upper() != "SYNTHETIC":
        blockers.append("SANDBOX_DATASET_MUST_BE_SYNTHETIC")
    if request.get("contains_real_customer_data") is not False:
        blockers.append("REAL_CUSTOMER_DATA_FORBIDDEN")
    if request.get("contains_production_secrets") is not False:
        blockers.append("PRODUCTION_SECRETS_FORBIDDEN")
    if request.get("uses_live_integrations") is not False:
        blockers.append("LIVE_INTEGRATIONS_FORBIDDEN")
    if request.get("outbound_channels_enabled") is not False:
        blockers.append("OUTBOUND_CHANNELS_FORBIDDEN")
    if request.get("external_provider_required") is not False:
        blockers.append("EXTERNAL_PROVIDER_FORBIDDEN")

    duration_hours = _positive_int(request.get("duration_hours"))
    synthetic_records = _positive_int(request.get("synthetic_records"))
    concurrent_sessions = _positive_int(request.get("concurrent_sessions"))
    if duration_hours is None:
        blockers.append("SANDBOX_DURATION_INVALID")
    elif (
        policy_data.get("max_duration_hours") is not None
        and duration_hours > policy_data["max_duration_hours"]
    ):
        blockers.append("SANDBOX_DURATION_EXCEEDS_POLICY")

    if synthetic_records is None:
        blockers.append("SANDBOX_RECORD_COUNT_INVALID")
    elif (
        policy_data.get("max_synthetic_records") is not None
        and synthetic_records > policy_data["max_synthetic_records"]
    ):
        blockers.append("SANDBOX_RECORD_COUNT_EXCEEDS_POLICY")

    if concurrent_sessions is None:
        blockers.append("SANDBOX_SESSION_COUNT_INVALID")
    elif (
        policy_data.get("max_concurrent_sessions") is not None
        and concurrent_sessions > policy_data["max_concurrent_sessions"]
    ):
        blockers.append("SANDBOX_SESSION_COUNT_EXCEEDS_POLICY")

    demo_script_ref = _text(request.get("demo_script_ref"), 320)
    if not demo_script_ref:
        blockers.append("DEMO_SCRIPT_REF_REQUIRED")

    request_refs = _refs(request.get("evidence_refs"))
    if len(request_refs) < 3:
        blockers.append("SANDBOX_REQUEST_EVIDENCE_INSUFFICIENT")

    blockers = list(dict.fromkeys(blockers))
    state = "BLOCKED" if blockers else "REVIEWABLE"
    decision = "BLOCKED" if blockers else "SANDBOX_REVIEW_CANDIDATE"

    evidence = {
        "scope": trusted,
        "admission_evidence_digest": _text(admission.get("evidence_digest"), 180),
        "sandbox_id": sandbox_id,
        "customer_id": customer_id,
        "service_tenant_id": service_tenant_id,
        "package": package,
        "dataset_class": "SYNTHETIC",
        "duration_hours": duration_hours,
        "synthetic_records": synthetic_records,
        "concurrent_sessions": concurrent_sessions,
        "demo_script_ref": demo_script_ref,
        "request_evidence_refs": request_refs,
        "policy_evidence_refs": policy_data.get("evidence_refs", []),
    }

    return {
        "schema": SCHEMA,
        "state": state,
        "decision": decision,
        "sandbox_id": sandbox_id,
        "customer_id": customer_id,
        "service_tenant_id": service_tenant_id,
        "package": package,
        "dataset_class": "SYNTHETIC",
        "duration_hours": duration_hours,
        "synthetic_records": synthetic_records,
        "concurrent_sessions": concurrent_sessions,
        "blockers": blockers,
        "evidence_digest": _digest(evidence),
        "owner_sandbox_approval_required": True,
        "sandbox_creation_authorized": False,
        "tenant_creation_authorized": False,
        "quota_change_authorized": False,
        "credential_use_authorized": False,
        "live_integration_authorized": False,
        "customer_data_use_authorized": False,
        "outbound_contact_authorized": False,
        "billing_authorized": False,
        "automatic_sandbox_creation": False,
        "automatic_tenant_creation": False,
        "automatic_quota_change": False,
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
    "ADMISSION_SCHEMA",
    "POLICY_SCHEMA",
    "evaluate_demo_sandbox",
]
