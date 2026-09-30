"""AION BUSINESS Team Access Lifecycle Authorization Package V1.

Binds one explicit lifecycle authorization record to one exact materialized
sandbox lifecycle plan. The package remains non-executing and never authorizes
production, deploy or runtime activation.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json
import re

from atlasquant_aion_business_team_access_sandbox_lifecycle_authorization import (
    SCHEMA as AUTH_SCHEMA,
    validate_authorization_record,
    verify_authorization_binding,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_materialization import (
    SCHEMA as MATERIALIZATION_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_LIFECYCLE_AUTHORIZATION_PACKAGE_V1"
VERSION = "1"

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")
_SESSION32 = re.compile(r"^[0-9a-f]{32}$")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _materialization_integrity(
    materialization: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(materialization)
    plan = _mapping(row.get("plan"))

    materialization_digest = _clean(
        row.get("materialization_digest"), 80
    ).lower()
    plan_digest = _clean(row.get("plan_digest"), 80).lower()
    baseline_digest = _clean(
        row.get("baseline_evidence_digest"), 80
    ).lower()
    acceptance_digest = _clean(
        row.get("baseline_acceptance_record_digest"), 80
    ).lower()
    session_id = _clean(row.get("operator_session_id"), 64).lower()

    payload = {
        "operator_session_id": session_id,
        "baseline_evidence_digest": baseline_digest,
        "baseline_acceptance_record_digest": acceptance_digest,
        "plan_digest": plan_digest,
        "test_username": plan.get("test_username"),
        "tenant_ids": plan.get("tenant_ids"),
        "factor_type": plan.get("factor_type"),
        "requested_by": plan.get("requested_by"),
    }

    gates = {
        "schema_valid": row.get("schema") == MATERIALIZATION_SCHEMA,
        "state_ready": row.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_PLAN_REVIEW",
        "materialization_digest_valid": bool(
            _DIGEST64.fullmatch(materialization_digest)
        ),
        "materialization_digest_integrity": bool(
            _DIGEST64.fullmatch(materialization_digest)
            and materialization_digest == _digest(payload)
        ),
        "plan_digest_valid": bool(_DIGEST64.fullmatch(plan_digest)),
        "plan_digest_matches_nested_plan": bool(
            _DIGEST64.fullmatch(plan_digest)
            and plan_digest == _clean(plan.get("plan_digest"), 80).lower()
        ),
        "baseline_digest_valid": bool(_DIGEST64.fullmatch(baseline_digest)),
        "baseline_digest_matches_nested_plan": bool(
            baseline_digest
            == _clean(plan.get("baseline_evidence_digest"), 80).lower()
        ),
        "acceptance_digest_valid": bool(_DIGEST64.fullmatch(acceptance_digest)),
        "acceptance_digest_matches_nested_plan": bool(
            acceptance_digest
            == _clean(
                plan.get("baseline_acceptance_record_digest"), 80
            ).lower()
        ),
        "operator_session_valid": bool(_SESSION32.fullmatch(session_id)),
        "materialization_non_authorizing": bool(
            row.get("lifecycle_authorization_recorded") is False
            and row.get("lifecycle_execution_authorized") is False
            and row.get("automatic_step_execution") is False
            and row.get("production_authorized") is False
            and row.get("deploy_authorized") is False
            and row.get("runtime_authorized") is False
            and row.get("executes_action") is False
        ),
    }
    blockers = [name for name, passed in gates.items() if not passed]

    return {
        "valid": not blockers,
        "gates": gates,
        "blockers": blockers,
        "materialization_digest": materialization_digest,
        "plan_digest": plan_digest,
        "baseline_evidence_digest": baseline_digest,
        "baseline_acceptance_record_digest": acceptance_digest,
        "operator_session_id": session_id,
        "plan": plan,
    }


def authorization_package_requirements() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "MATERIALIZED_LIFECYCLE_AUTHORIZATION_RECORD_REQUIRED",
        "materialization_binding_required": True,
        "authorization_record_integrity_required": True,
        "generic_language_is_authorization": False,
        "authorization_package_verified": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


def validate_materialized_authorization(
    materialization: Mapping[str, Any] | None,
    record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    integrity = _materialization_integrity(materialization)
    raw = _mapping(record)
    plan = integrity["plan"]

    supplied_materialization_digest = _clean(
        raw.get("materialization_digest"), 80
    ).lower()

    blockers = list(integrity["blockers"])
    if supplied_materialization_digest != integrity["materialization_digest"]:
        blockers.append("materialization_digest")
    if not _DIGEST64.fullmatch(supplied_materialization_digest):
        blockers.append("materialization_digest_format")

    legacy = validate_authorization_record(plan, raw)
    if legacy.get("authorization_record_verified") is not True:
        blockers.append("authorization_record")
    if legacy.get("sandbox_lifecycle_manual_execution_authorized") is not True:
        blockers.append("manual_scope")
    if legacy.get("automatic_execution_authorized") is not False:
        blockers.append("automatic_execution")
    if legacy.get("executor_enabled") is not False:
        blockers.append("executor_enabled")
    if legacy.get("production_authorized") is not False:
        blockers.append("production_authorized")
    if legacy.get("executes_action") is not False:
        blockers.append("unexpected_execution_path")

    verified = not blockers
    package_payload = {
        "materialization_digest": integrity["materialization_digest"],
        "plan_digest": integrity["plan_digest"],
        "baseline_evidence_digest": integrity["baseline_evidence_digest"],
        "baseline_acceptance_record_digest": integrity[
            "baseline_acceptance_record_digest"
        ],
        "operator_session_id": integrity["operator_session_id"],
        "authorization_record_digest": _clean(
            legacy.get("record_digest"), 80
        ).lower(),
        "approved_by": _clean(legacy.get("approved_by"), 120),
        "approved_at": _clean(legacy.get("approved_at"), 100),
    } if verified else {}

    return {
        **legacy,
        "authorization_package_schema": SCHEMA,
        "authorization_package_version": VERSION,
        "state": (
            "EXPLICIT_SANDBOX_LIFECYCLE_AUTHORIZATION_RECORD_VERIFIED"
            if verified
            else "SANDBOX_LIFECYCLE_AUTHORIZATION_PACKAGE_REJECTED"
        ),
        "authorization_record_verified": verified,
        "sandbox_lifecycle_manual_execution_authorized": verified,
        "materialization_binding_verified": verified,
        "materialization_digest": integrity["materialization_digest"]
        if verified else "",
        "baseline_acceptance_record_digest": integrity[
            "baseline_acceptance_record_digest"
        ] if verified else "",
        "operator_session_id": integrity["operator_session_id"]
        if verified else "",
        "authorization_package_digest": _digest(package_payload)
        if verified else "",
        "package_blockers": blockers,
        "automatic_execution_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


def verify_materialized_authorization_binding(
    plan: Mapping[str, Any] | None,
    authorization_package: Mapping[str, Any] | None,
) -> dict[str, Any]:
    plan_row = _mapping(plan)
    auth = _mapping(authorization_package)

    legacy_binding = verify_authorization_binding(plan_row, auth)
    materialization_digest = _clean(
        auth.get("materialization_digest"), 80
    ).lower()
    acceptance_digest = _clean(
        auth.get("baseline_acceptance_record_digest"), 80
    ).lower()
    session_id = _clean(auth.get("operator_session_id"), 64).lower()
    package_digest = _clean(
        auth.get("authorization_package_digest"), 80
    ).lower()

    package_payload = {
        "materialization_digest": materialization_digest,
        "plan_digest": _clean(auth.get("plan_digest"), 80).lower(),
        "baseline_evidence_digest": _clean(
            auth.get("baseline_evidence_digest"), 80
        ).lower(),
        "baseline_acceptance_record_digest": acceptance_digest,
        "operator_session_id": session_id,
        "authorization_record_digest": _clean(
            auth.get("record_digest"), 80
        ).lower(),
        "approved_by": _clean(auth.get("approved_by"), 120),
        "approved_at": _clean(auth.get("approved_at"), 100),
    }

    match = bool(
        legacy_binding.get("binding_match") is True
        and auth.get("schema") == AUTH_SCHEMA
        and auth.get("authorization_package_schema") == SCHEMA
        and auth.get("materialization_binding_verified") is True
        and _DIGEST64.fullmatch(materialization_digest)
        and _DIGEST64.fullmatch(acceptance_digest)
        and acceptance_digest
        == _clean(
            plan_row.get("baseline_acceptance_record_digest"), 80
        ).lower()
        and _SESSION32.fullmatch(session_id)
        and _DIGEST64.fullmatch(package_digest)
        and package_digest == _digest(package_payload)
        and auth.get("automatic_execution_authorized") is False
        and auth.get("executor_enabled") is False
        and auth.get("production_authorized") is False
        and auth.get("executes_action") is False
    )

    return {
        "schema": (
            "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_MATERIALIZED_"
            "LIFECYCLE_AUTHORIZATION_BINDING_V1"
        ),
        "version": VERSION,
        "state": (
            "MATERIALIZED_LIFECYCLE_AUTHORIZATION_BINDING_MATCH"
            if match
            else "MATERIALIZED_LIFECYCLE_AUTHORIZATION_BINDING_MISMATCH"
        ),
        "binding_match": match,
        "authorization_package_digest": package_digest if match else "",
        "materialization_digest": materialization_digest if match else "",
        "automatic_execution_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "authorization_package_requirements",
    "validate_materialized_authorization",
    "verify_materialized_authorization_binding",
]
