"""AION BUSINESS Team Access Sandbox Lifecycle Authorization V1.

Defines and validates an explicit human authorization record bound to one exact
sandbox lifecycle plan. Generic language is never authorization.

This module records no decision by itself and never calls Keycloak, PostgreSQL,
Docker or any executor. A verified record only proves that a future manual
sandbox lifecycle may proceed step by step under the plan's constraints.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, Mapping
import json
import re

from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    SCHEMA as PLAN_SCHEMA,
    REQUIRED_ACKNOWLEDGEMENTS,
    REQUIRED_DECISION_TOKEN,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_SANDBOX_LIFECYCLE_AUTHORIZATION_V1"
VERSION = "1"

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")


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


def _valid_timestamp(value: Any) -> bool:
    token = _clean(value, 100)
    if not token:
        return False
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except Exception:
        return False
    return parsed.tzinfo is not None


def authorization_record_requirements() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "HUMAN_AUTHORIZATION_RECORD_REQUIRED",
        "required_decision_token": REQUIRED_DECISION_TOKEN,
        "required_acknowledgements": list(REQUIRED_ACKNOWLEDGEMENTS),
        "generic_language_is_authorization": False,
        "authorization_record_verified": False,
        "sandbox_lifecycle_manual_execution_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


def authorization_record_template(
    plan: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(plan)
    plan_digest = _clean(row.get("plan_digest"), 80).lower()
    baseline_digest = _clean(row.get("baseline_evidence_digest"), 80).lower()
    eligible = bool(
        row.get("schema") == PLAN_SCHEMA
        and row.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_EXECUTION_DECISION"
        and _DIGEST64.fullmatch(plan_digest)
        and _DIGEST64.fullmatch(baseline_digest)
        and row.get("decision_recorded") is False
        and row.get("executes_action") is False
    )
    return {
        **authorization_record_requirements(),
        "state": "HUMAN_AUTHORIZATION_RECORD_REQUIRED" if eligible else "BLOCKED",
        "plan_digest": plan_digest if eligible else "",
        "baseline_evidence_digest": baseline_digest if eligible else "",
        "expected_approved_by": _clean(row.get("requested_by"), 120)
        if eligible
        else "",
        "test_username": _clean(row.get("test_username"), 160) if eligible else "",
        "factor_type": _clean(row.get("factor_type"), 60) if eligible else "",
        "tenant_ids": list(row.get("tenant_ids") or []) if eligible else [],
    }


def validate_authorization_record(
    plan: Mapping[str, Any] | None,
    record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    plan_row = _mapping(plan)
    raw = _mapping(record)

    plan_digest = _clean(plan_row.get("plan_digest"), 80).lower()
    baseline_digest = _clean(
        plan_row.get("baseline_evidence_digest"), 80
    ).lower()
    expected_approver = _clean(plan_row.get("requested_by"), 120)

    decision = _clean(raw.get("decision"), 160)
    supplied_plan_digest = _clean(raw.get("plan_digest"), 80).lower()
    supplied_baseline_digest = _clean(
        raw.get("baseline_evidence_digest"), 80
    ).lower()
    approved_by = _clean(raw.get("approved_by"), 120)
    approved_at = _clean(raw.get("approved_at"), 100)
    acknowledgements = _mapping(raw.get("acknowledgements"))

    blockers: list[str] = []
    if not (
        plan_row.get("schema") == PLAN_SCHEMA
        and plan_row.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_EXECUTION_DECISION"
        and _DIGEST64.fullmatch(plan_digest)
        and _DIGEST64.fullmatch(baseline_digest)
        and plan_row.get("decision_recorded") is False
        and plan_row.get("executes_action") is False
    ):
        blockers.append("lifecycle_plan")
    if raw.get("schema") != SCHEMA:
        blockers.append("record_schema")
    if decision != REQUIRED_DECISION_TOKEN:
        blockers.append("decision_token")
    if supplied_plan_digest != plan_digest or not _DIGEST64.fullmatch(
        supplied_plan_digest
    ):
        blockers.append("plan_digest")
    if supplied_baseline_digest != baseline_digest or not _DIGEST64.fullmatch(
        supplied_baseline_digest
    ):
        blockers.append("baseline_evidence_digest")
    if not approved_by or approved_by != expected_approver:
        blockers.append("approved_by")
    if not _valid_timestamp(approved_at):
        blockers.append("approved_at")
    if raw.get("sandbox_only") is not True:
        blockers.append("sandbox_only")
    if raw.get("production_targeted") is not False:
        blockers.append("production_targeted")
    if raw.get("secret_material_included") is not False:
        blockers.append("secret_material_included")
    if raw.get("executor_enabled") is not False:
        blockers.append("executor_enabled")

    missing_acknowledgements = [
        name
        for name in REQUIRED_ACKNOWLEDGEMENTS
        if acknowledgements.get(name) is not True
    ]
    if missing_acknowledgements:
        blockers.append("acknowledgements")

    verified = not blockers
    payload = {
        "schema": SCHEMA,
        "version": VERSION,
        "decision": decision,
        "plan_digest": supplied_plan_digest,
        "baseline_evidence_digest": supplied_baseline_digest,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "sandbox_only": True,
        "production_targeted": False,
        "secret_material_included": False,
        "executor_enabled": False,
        "acknowledgements": {
            name: acknowledgements.get(name) is True
            for name in REQUIRED_ACKNOWLEDGEMENTS
        },
    } if verified else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "EXPLICIT_SANDBOX_LIFECYCLE_AUTHORIZATION_RECORD_VERIFIED"
            if verified
            else "SANDBOX_LIFECYCLE_AUTHORIZATION_REJECTED"
        ),
        "authorization_record_verified": verified,
        "blockers": blockers,
        "missing_acknowledgements": missing_acknowledgements,
        "decision": decision if verified else "",
        "plan_digest": plan_digest if verified else "",
        "baseline_evidence_digest": baseline_digest if verified else "",
        "approved_by": approved_by if verified else "",
        "approved_at": approved_at if verified else "",
        "record_digest": _digest(payload) if verified else "",
        "sandbox_lifecycle_manual_execution_authorized": verified,
        "automatic_execution_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "invalidated_by_plan_or_baseline_drift": True,
        "executes_action": False,
    }


def verify_authorization_binding(
    plan: Mapping[str, Any] | None,
    record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    plan_row = _mapping(plan)
    auth = _mapping(record)
    plan_digest = _clean(plan_row.get("plan_digest"), 80).lower()
    baseline_digest = _clean(
        plan_row.get("baseline_evidence_digest"), 80
    ).lower()

    match = bool(
        plan_row.get("schema") == PLAN_SCHEMA
        and _DIGEST64.fullmatch(plan_digest)
        and _DIGEST64.fullmatch(baseline_digest)
        and auth.get("schema") == SCHEMA
        and auth.get("state")
        == "EXPLICIT_SANDBOX_LIFECYCLE_AUTHORIZATION_RECORD_VERIFIED"
        and auth.get("authorization_record_verified") is True
        and _clean(auth.get("plan_digest"), 80).lower() == plan_digest
        and _clean(auth.get("baseline_evidence_digest"), 80).lower()
        == baseline_digest
        and _DIGEST64.fullmatch(_clean(auth.get("record_digest"), 80).lower())
        and auth.get("executor_enabled") is False
        and auth.get("production_authorized") is False
    )
    return {
        "schema": (
            "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_SANDBOX_"
            "LIFECYCLE_AUTHORIZATION_BINDING_V1"
        ),
        "state": (
            "SANDBOX_LIFECYCLE_AUTHORIZATION_BINDING_MATCH"
            if match
            else "SANDBOX_LIFECYCLE_AUTHORIZATION_BINDING_MISMATCH"
        ),
        "binding_match": match,
        "automatic_execution_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "authorization_record_requirements",
    "authorization_record_template",
    "validate_authorization_record",
    "verify_authorization_binding",
]
