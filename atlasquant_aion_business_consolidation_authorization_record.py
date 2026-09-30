"""AION BUSINESS consolidation explicit authorization record V1.

Defines and validates a digest-bound human authorization record for the exact
Business consolidation request. The module does not execute GitHub actions and
never interprets generic language such as "ok", "pode seguir" or "vamos lá" as
authorization.

A verified record is evidence of an explicit human decision only. Merge
execution remains a separate step and is never performed here.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json
import re

from atlasquant_aion_business_consolidation_decision_request import (
    DECISION_SCOPE,
    SCHEMA as DECISION_REQUEST_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_CONSOLIDATION_AUTHORIZATION_RECORD_V1"
VERSION = "1"
DECISION_TOKEN = "AUTHORIZE_STACK_CONSOLIDATION_394_412"

REQUIRED_ACKNOWLEDGEMENTS = (
    "scope_is_only_394_412",
    "deploy_remains_separate",
    "pilot_remains_separate",
    "runtime_remains_off",
    "post_step_ci_required",
    "stop_on_any_drift",
)

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def authorization_record_requirements() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "AUTHORIZATION_INPUT_REQUIRED",
        "required_decision_token": DECISION_TOKEN,
        "required_decision_scope": DECISION_SCOPE,
        "required_acknowledgements": list(REQUIRED_ACKNOWLEDGEMENTS),
        "generic_language_is_authorization": False,
        "authorization_record_verified": False,
        "merge_execution_authorized": False,
        "deploy_authorized": False,
        "pilot_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


def authorization_record_template(
    request: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(request)
    request_digest = _clean(row.get("request_digest"), 128).lower()
    eligible_request = bool(
        row.get("schema") == DECISION_REQUEST_SCHEMA
        and row.get("state") == "HUMAN_AUTHORIZATION_RECORD_REQUIRED"
        and row.get("eligible_for_explicit_human_authorization") is True
        and _DIGEST64.fullmatch(request_digest)
        and row.get("authorization_recorded") is False
        and row.get("merge_authorized") is False
    )
    return {
        **authorization_record_requirements(),
        "state": "AUTHORIZATION_INPUT_REQUIRED" if eligible_request else "BLOCKED",
        "request_digest": request_digest if eligible_request else "",
        "expected_approved_by": _clean(row.get("reviewer"), 120) if eligible_request else "",
        "decision_scope": _clean(row.get("decision_scope"), 120) if eligible_request else "",
    }


def validate_authorization_record(
    request: Mapping[str, Any] | None,
    record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    req = _mapping(request)
    raw = _mapping(record)

    request_digest = _clean(req.get("request_digest"), 128).lower()
    expected_reviewer = _clean(req.get("reviewer"), 120)
    expected_scope = _clean(req.get("decision_scope"), 120)
    decision = _clean(raw.get("decision"), 160)
    approved_by = _clean(raw.get("approved_by"), 120)
    approved_at = _clean(raw.get("approved_at"), 100)
    supplied_request_digest = _clean(raw.get("request_digest"), 128).lower()
    scope = _clean(raw.get("decision_scope"), 120)
    acknowledgements = _mapping(raw.get("acknowledgements"))

    blockers = []
    request_valid = bool(
        req.get("schema") == DECISION_REQUEST_SCHEMA
        and req.get("state") == "HUMAN_AUTHORIZATION_RECORD_REQUIRED"
        and req.get("eligible_for_explicit_human_authorization") is True
        and _DIGEST64.fullmatch(request_digest)
        and req.get("authorization_recorded") is False
        and req.get("merge_authorized") is False
    )
    if not request_valid:
        blockers.append("decision_request")
    if raw.get("schema") != SCHEMA:
        blockers.append("record_schema")
    if decision != DECISION_TOKEN:
        blockers.append("decision_token")
    if supplied_request_digest != request_digest or not _DIGEST64.fullmatch(supplied_request_digest):
        blockers.append("request_digest")
    if scope != DECISION_SCOPE or scope != expected_scope:
        blockers.append("decision_scope")
    if not approved_by or approved_by != expected_reviewer:
        blockers.append("approved_by")
    if not approved_at:
        blockers.append("approved_at")

    missing_acknowledgements = [
        name for name in REQUIRED_ACKNOWLEDGEMENTS
        if acknowledgements.get(name) is not True
    ]
    if missing_acknowledgements:
        blockers.append("acknowledgements")

    verified = not blockers
    payload = {
        "schema": SCHEMA,
        "version": VERSION,
        "decision": decision,
        "request_digest": supplied_request_digest,
        "decision_scope": scope,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "acknowledgements": {
            name: acknowledgements.get(name) is True
            for name in REQUIRED_ACKNOWLEDGEMENTS
        },
    } if verified else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "EXPLICIT_AUTHORIZATION_RECORD_VERIFIED" if verified else "REJECTED",
        "authorization_record_verified": verified,
        "blockers": blockers,
        "missing_acknowledgements": missing_acknowledgements,
        "request_digest": request_digest if verified else "",
        "record_digest": _canonical_digest(payload) if verified else "",
        "decision": decision if verified else "",
        "decision_scope": scope if verified else "",
        "approved_by": approved_by if verified else "",
        "approved_at": approved_at if verified else "",
        "invalidated_by_request_drift": True,
        "single_request_scope": True,
        "merge_execution_authorized": False,
        "auto_merge_enabled": False,
        "deploy_authorized": False,
        "pilot_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


def verify_authorization_record_binding(
    request: Mapping[str, Any] | None,
    verified_record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    req = _mapping(request)
    record = _mapping(verified_record)
    request_digest = _clean(req.get("request_digest"), 128).lower()
    record_request_digest = _clean(record.get("request_digest"), 128).lower()

    match = bool(
        req.get("schema") == DECISION_REQUEST_SCHEMA
        and req.get("state") == "HUMAN_AUTHORIZATION_RECORD_REQUIRED"
        and _DIGEST64.fullmatch(request_digest)
        and record.get("schema") == SCHEMA
        and record.get("state") == "EXPLICIT_AUTHORIZATION_RECORD_VERIFIED"
        and record.get("authorization_record_verified") is True
        and record_request_digest == request_digest
        and _clean(record.get("decision_scope"), 120) == DECISION_SCOPE
        and _DIGEST64.fullmatch(_clean(record.get("record_digest"), 128).lower())
    )

    return {
        "schema": "ATLASQUANT_AION_BUSINESS_CONSOLIDATION_AUTHORIZATION_BINDING_V1",
        "state": "AUTHORIZATION_BINDING_MATCH" if match else "AUTHORIZATION_BINDING_MISMATCH",
        "binding_match": match,
        "merge_execution_authorized": False,
        "deploy_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "DECISION_TOKEN",
    "REQUIRED_ACKNOWLEDGEMENTS",
    "authorization_record_requirements",
    "authorization_record_template",
    "validate_authorization_record",
    "verify_authorization_record_binding",
]
