"""AION BUSINESS Team Access Real Sandbox Baseline Acceptance V1.

Separates a technically valid operator handoff from an explicit administrative
acceptance of the real sandbox baseline for lifecycle planning.

The acceptance contract is non-executing. It never starts Docker, never mutates
Keycloak/PostgreSQL and never authorizes lifecycle execution or production.
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

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_REAL_BASELINE_ACCEPTANCE_V1"
VERSION = "1"

REQUIRED_DECISION_TOKEN = "ACCEPT_TEAM_ACCESS_REAL_SANDBOX_BASELINE"
REQUIRED_ACKNOWLEDGEMENTS = (
    "SAME_OPERATOR_SESSION_VERIFIED",
    "BASELINE_DIGEST_FROZEN",
    "SANDBOX_ONLY",
    "NO_PRODUCTION_PROMOTION",
    "NO_LIFECYCLE_EXECUTION_AUTHORITY",
    "SEPARATE_LIFECYCLE_AUTHORIZATION_REQUIRED",
)

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")
_SESSION32 = re.compile(r"^[0-9a-f]{32}$")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _timestamp_valid(value: Any) -> bool:
    token = _clean(value, 100)
    if not token:
        return False
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except Exception:
        return False
    return parsed.tzinfo is not None


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def baseline_acceptance_requirements() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "REAL_SANDBOX_BASELINE_ACCEPTANCE_RECORD_REQUIRED",
        "required_decision_token": REQUIRED_DECISION_TOKEN,
        "required_acknowledgements": list(REQUIRED_ACKNOWLEDGEMENTS),
        "generic_language_is_acceptance": False,
        "baseline_accepted": False,
        "lifecycle_plan_creation_eligible": False,
        "lifecycle_execution_authorized": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
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
    session_id = _clean(row.get("operator_session_id"), 64).lower()
    reviewer = _clean(row.get("reviewed_by"), 120)

    eligible = bool(
        row.get("schema") == HANDOFF_SCHEMA
        and row.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_REAL_BASELINE_ACCEPTANCE_REVIEW"
        and _DIGEST64.fullmatch(handoff_digest)
        and _DIGEST64.fullmatch(baseline_digest)
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
        "state": (
            "REAL_SANDBOX_BASELINE_ACCEPTANCE_RECORD_REQUIRED"
            if eligible
            else "REAL_SANDBOX_BASELINE_ACCEPTANCE_TEMPLATE_BLOCKED"
        ),
        "handoff_digest": handoff_digest if eligible else "",
        "baseline_evidence_digest": baseline_digest if eligible else "",
        "operator_session_id": session_id if eligible else "",
        "expected_accepted_by": reviewer if eligible else "",
    }


def validate_baseline_acceptance_record(
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
    session_id = _clean(
        handoff_row.get("operator_session_id"), 64
    ).lower()
    expected_acceptor = _clean(
        handoff_row.get("reviewed_by"), 120
    )

    decision = _clean(raw.get("decision"), 180)
    accepted_by = _clean(raw.get("accepted_by"), 120)
    accepted_at = _clean(raw.get("accepted_at"), 100)
    acknowledgements = _mapping(raw.get("acknowledgements"))

    blockers: list[str] = []

    if not (
        handoff_row.get("schema") == HANDOFF_SCHEMA
        and handoff_row.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_REAL_BASELINE_ACCEPTANCE_REVIEW"
        and _DIGEST64.fullmatch(handoff_digest)
        and _DIGEST64.fullmatch(baseline_digest)
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
    if decision != REQUIRED_DECISION_TOKEN:
        blockers.append("decision_token")
    if _clean(raw.get("handoff_digest"), 80).lower() != handoff_digest:
        blockers.append("handoff_digest")
    if (
        _clean(raw.get("baseline_evidence_digest"), 80).lower()
        != baseline_digest
    ):
        blockers.append("baseline_evidence_digest")
    if _clean(raw.get("operator_session_id"), 64).lower() != session_id:
        blockers.append("operator_session_id")
    if not accepted_by or accepted_by != expected_acceptor:
        blockers.append("accepted_by")
    if not _timestamp_valid(accepted_at):
        blockers.append("accepted_at")
    if raw.get("sandbox_only") is not True:
        blockers.append("sandbox_only")
    if raw.get("production_promotion_requested") is not False:
        blockers.append("production_promotion_requested")
    if raw.get("lifecycle_execution_requested") is not False:
        blockers.append("lifecycle_execution_requested")
    if raw.get("secret_material_included") is not False:
        blockers.append("secret_material_included")

    missing_acknowledgements = [
        name
        for name in REQUIRED_ACKNOWLEDGEMENTS
        if acknowledgements.get(name) is not True
    ]
    if missing_acknowledgements:
        blockers.append("acknowledgements")

    accepted = not blockers

    payload = {
        "schema": SCHEMA,
        "version": VERSION,
        "decision": decision,
        "handoff_digest": handoff_digest,
        "baseline_evidence_digest": baseline_digest,
        "operator_session_id": session_id,
        "accepted_by": accepted_by,
        "accepted_at": accepted_at,
        "sandbox_only": True,
        "production_promotion_requested": False,
        "lifecycle_execution_requested": False,
        "secret_material_included": False,
        "acknowledgements": {
            name: acknowledgements.get(name) is True
            for name in REQUIRED_ACKNOWLEDGEMENTS
        },
    } if accepted else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "REAL_SANDBOX_BASELINE_ACCEPTED_FOR_LIFECYCLE_PLANNING"
            if accepted
            else "REAL_SANDBOX_BASELINE_ACCEPTANCE_REJECTED"
        ),
        "blockers": blockers,
        "missing_acknowledgements": missing_acknowledgements,
        "baseline_accepted": accepted,
        "handoff_digest": handoff_digest if accepted else "",
        "baseline_evidence_digest": baseline_digest if accepted else "",
        "operator_session_id": session_id if accepted else "",
        "accepted_by": accepted_by if accepted else "",
        "accepted_at": accepted_at if accepted else "",
        "acceptance_digest": _digest(payload) if accepted else "",
        "lifecycle_plan_creation_eligible": accepted,
        "lifecycle_execution_authorized": False,
        "sandbox_step_execution_authorized": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


def verify_baseline_acceptance_binding(
    handoff: Mapping[str, Any] | None,
    acceptance: Mapping[str, Any] | None,
) -> dict[str, Any]:
    handoff_row = _mapping(handoff)
    row = _mapping(acceptance)

    match = bool(
        handoff_row.get("schema") == HANDOFF_SCHEMA
        and handoff_row.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_REAL_BASELINE_ACCEPTANCE_REVIEW"
        and row.get("schema") == SCHEMA
        and row.get("state")
        == "REAL_SANDBOX_BASELINE_ACCEPTED_FOR_LIFECYCLE_PLANNING"
        and row.get("baseline_accepted") is True
        and row.get("lifecycle_plan_creation_eligible") is True
        and _clean(row.get("handoff_digest"), 80).lower()
        == _clean(handoff_row.get("handoff_digest"), 80).lower()
        and _clean(row.get("baseline_evidence_digest"), 80).lower()
        == _clean(handoff_row.get("baseline_evidence_digest"), 80).lower()
        and _clean(row.get("operator_session_id"), 64).lower()
        == _clean(handoff_row.get("operator_session_id"), 64).lower()
        and _DIGEST64.fullmatch(
            _clean(row.get("acceptance_digest"), 80).lower()
        )
        and row.get("lifecycle_execution_authorized") is False
        and row.get("production_authorized") is False
        and row.get("executes_action") is False
    )

    return {
        "schema": (
            "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_REAL_BASELINE_"
            "ACCEPTANCE_BINDING_V1"
        ),
        "version": VERSION,
        "state": (
            "REAL_SANDBOX_BASELINE_ACCEPTANCE_BINDING_MATCH"
            if match
            else "REAL_SANDBOX_BASELINE_ACCEPTANCE_BINDING_MISMATCH"
        ),
        "binding_match": match,
        "lifecycle_plan_creation_eligible": match,
        "lifecycle_execution_authorized": False,
        "production_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "REQUIRED_DECISION_TOKEN",
    "REQUIRED_ACKNOWLEDGEMENTS",
    "baseline_acceptance_requirements",
    "baseline_acceptance_template",
    "validate_baseline_acceptance_record",
    "verify_baseline_acceptance_binding",
]
