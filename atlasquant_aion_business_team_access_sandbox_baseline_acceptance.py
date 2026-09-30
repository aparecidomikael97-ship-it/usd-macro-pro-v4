"""AION BUSINESS Team Access Sandbox Baseline Acceptance V1.

Validates an explicit human acceptance record for one exact Windows operator
handoff. Technical baseline validation is not acceptance.

A verified acceptance only authorizes using the accepted baseline as input to
the lifecycle planning layer. It never authorizes lifecycle execution,
production, deploy or runtime activation.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, Mapping
import json
import re

from atlasquant_aion_business_team_access_windows_operator_handoff import (
    SCHEMA as HANDOFF_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_SANDBOX_BASELINE_ACCEPTANCE_V1"
VERSION = "1"
DECISION_TOKEN = "ACCEPT_TEAM_ACCESS_SANDBOX_BASELINE"

REQUIRED_ACKNOWLEDGEMENTS = (
    "SAME_OPERATOR_SESSION",
    "BASELINE_READ_ONLY_EVIDENCE",
    "HANDOFF_DIGEST_BOUND",
    "BASELINE_DIGEST_BOUND",
    "NO_LIFECYCLE_EXECUTION",
    "NO_PRODUCTION_TARGETS",
)

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


def _valid_timestamp(value: Any) -> bool:
    token = _clean(value, 100)
    if not token:
        return False
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except Exception:
        return False
    return parsed.tzinfo is not None


def baseline_acceptance_requirements() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "BASELINE_ACCEPTANCE_INPUT_REQUIRED",
        "required_decision_token": DECISION_TOKEN,
        "required_acknowledgements": list(REQUIRED_ACKNOWLEDGEMENTS),
        "generic_language_is_acceptance": False,
        "baseline_accepted": False,
        "lifecycle_plan_input_authorized": False,
        "lifecycle_execution_authorized": False,
        "production_authorized": False,
        "executes_action": False,
    }


def baseline_acceptance_template(
    handoff: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(handoff)
    handoff_digest = _clean(row.get("handoff_digest"), 80).lower()
    baseline_digest = _clean(
        row.get("baseline_evidence_digest"), 80
    ).lower()
    readiness_digest = _clean(row.get("readiness_digest"), 80).lower()
    session_id = _clean(row.get("operator_session_id"), 64).lower()
    reviewer = _clean(row.get("reviewed_by"), 120)

    eligible = bool(
        row.get("schema") == HANDOFF_SCHEMA
        and row.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_REAL_BASELINE_ACCEPTANCE_REVIEW"
        and _DIGEST64.fullmatch(handoff_digest)
        and _DIGEST64.fullmatch(baseline_digest)
        and _DIGEST64.fullmatch(readiness_digest)
        and _SESSION32.fullmatch(session_id)
        and reviewer
        and row.get("baseline_accepted") is False
        and row.get("lifecycle_plan_authorized") is False
        and row.get("lifecycle_execution_authorized") is False
        and row.get("production_authorized") is False
        and row.get("executes_action") is False
    )

    return {
        **baseline_acceptance_requirements(),
        "state": "BASELINE_ACCEPTANCE_INPUT_REQUIRED" if eligible else "BLOCKED",
        "handoff_digest": handoff_digest if eligible else "",
        "baseline_evidence_digest": baseline_digest if eligible else "",
        "readiness_digest": readiness_digest if eligible else "",
        "operator_session_id": session_id if eligible else "",
        "expected_approved_by": reviewer if eligible else "",
    }


def validate_baseline_acceptance(
    handoff: Mapping[str, Any] | None,
    record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    handoff_row = _mapping(handoff)
    raw = _mapping(record)

    handoff_digest = _clean(
        handoff_row.get("handoff_digest"), 80
    ).lower()
    baseline_digest = _clean(
        handoff_row.get("baseline_evidence_digest"), 80
    ).lower()
    readiness_digest = _clean(
        handoff_row.get("readiness_digest"), 80
    ).lower()
    session_id = _clean(
        handoff_row.get("operator_session_id"), 64
    ).lower()
    expected_approver = _clean(handoff_row.get("reviewed_by"), 120)

    decision = _clean(raw.get("decision"), 160)
    supplied_handoff = _clean(raw.get("handoff_digest"), 80).lower()
    supplied_baseline = _clean(
        raw.get("baseline_evidence_digest"), 80
    ).lower()
    supplied_readiness = _clean(
        raw.get("readiness_digest"), 80
    ).lower()
    supplied_session = _clean(
        raw.get("operator_session_id"), 64
    ).lower()
    approved_by = _clean(raw.get("approved_by"), 120)
    approved_at = _clean(raw.get("approved_at"), 100)
    acknowledgements = _mapping(raw.get("acknowledgements"))

    blockers: list[str] = []

    if not (
        handoff_row.get("schema") == HANDOFF_SCHEMA
        and handoff_row.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_REAL_BASELINE_ACCEPTANCE_REVIEW"
        and _DIGEST64.fullmatch(handoff_digest)
        and _DIGEST64.fullmatch(baseline_digest)
        and _DIGEST64.fullmatch(readiness_digest)
        and _SESSION32.fullmatch(session_id)
        and handoff_row.get("baseline_accepted") is False
        and handoff_row.get("lifecycle_plan_authorized") is False
        and handoff_row.get("lifecycle_execution_authorized") is False
        and handoff_row.get("production_authorized") is False
        and handoff_row.get("executes_action") is False
    ):
        blockers.append("handoff")

    if raw.get("schema") != SCHEMA:
        blockers.append("record_schema")
    if decision != DECISION_TOKEN:
        blockers.append("decision_token")
    if supplied_handoff != handoff_digest or not _DIGEST64.fullmatch(
        supplied_handoff
    ):
        blockers.append("handoff_digest")
    if supplied_baseline != baseline_digest or not _DIGEST64.fullmatch(
        supplied_baseline
    ):
        blockers.append("baseline_evidence_digest")
    if supplied_readiness != readiness_digest or not _DIGEST64.fullmatch(
        supplied_readiness
    ):
        blockers.append("readiness_digest")
    if supplied_session != session_id or not _SESSION32.fullmatch(
        supplied_session
    ):
        blockers.append("operator_session_id")
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
        "handoff_digest": supplied_handoff,
        "baseline_evidence_digest": supplied_baseline,
        "readiness_digest": supplied_readiness,
        "operator_session_id": supplied_session,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "sandbox_only": True,
        "production_targeted": False,
        "secret_material_included": False,
        "acknowledgements": {
            name: acknowledgements.get(name) is True
            for name in REQUIRED_ACKNOWLEDGEMENTS
        },
    } if verified else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "EXPLICIT_SANDBOX_BASELINE_ACCEPTANCE_VERIFIED"
            if verified
            else "SANDBOX_BASELINE_ACCEPTANCE_REJECTED"
        ),
        "acceptance_record_verified": verified,
        "blockers": blockers,
        "missing_acknowledgements": missing_acknowledgements,
        "decision": decision if verified else "",
        "handoff_digest": handoff_digest if verified else "",
        "baseline_evidence_digest": baseline_digest if verified else "",
        "readiness_digest": readiness_digest if verified else "",
        "operator_session_id": session_id if verified else "",
        "approved_by": approved_by if verified else "",
        "approved_at": approved_at if verified else "",
        "acceptance_record_digest": _digest(payload) if verified else "",
        "baseline_accepted": verified,
        "lifecycle_plan_input_authorized": verified,
        "lifecycle_execution_authorized": False,
        "automatic_plan_creation_authorized": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


def verify_baseline_acceptance_binding(
    baseline_review: Mapping[str, Any] | None,
    acceptance: Mapping[str, Any] | None,
) -> dict[str, Any]:
    baseline = _mapping(baseline_review)
    accepted = _mapping(acceptance)

    baseline_digest = _clean(
        baseline.get("evidence_digest"), 80
    ).lower()
    baseline_session = _clean(
        baseline.get("operator_session_id"), 64
    ).lower()

    match = bool(
        _DIGEST64.fullmatch(baseline_digest)
        and _SESSION32.fullmatch(baseline_session)
        and accepted.get("schema") == SCHEMA
        and accepted.get("state")
        == "EXPLICIT_SANDBOX_BASELINE_ACCEPTANCE_VERIFIED"
        and accepted.get("acceptance_record_verified") is True
        and accepted.get("baseline_accepted") is True
        and accepted.get("lifecycle_plan_input_authorized") is True
        and _clean(accepted.get("baseline_evidence_digest"), 80).lower()
        == baseline_digest
        and _clean(accepted.get("operator_session_id"), 64).lower()
        == baseline_session
        and _DIGEST64.fullmatch(
            _clean(accepted.get("acceptance_record_digest"), 80).lower()
        )
        and accepted.get("lifecycle_execution_authorized") is False
        and accepted.get("production_authorized") is False
        and accepted.get("executes_action") is False
    )

    return {
        "schema": (
            "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_SANDBOX_"
            "BASELINE_ACCEPTANCE_BINDING_V1"
        ),
        "state": (
            "SANDBOX_BASELINE_ACCEPTANCE_BINDING_MATCH"
            if match
            else "SANDBOX_BASELINE_ACCEPTANCE_BINDING_MISMATCH"
        ),
        "binding_match": match,
        "lifecycle_plan_input_authorized": match,
        "lifecycle_execution_authorized": False,
        "production_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "DECISION_TOKEN",
    "REQUIRED_ACKNOWLEDGEMENTS",
    "baseline_acceptance_requirements",
    "baseline_acceptance_template",
    "validate_baseline_acceptance",
    "verify_baseline_acceptance_binding",
]
