"""AION BUSINESS Team Access Windows Operator Handoff V1.

Binds one validated Windows operator readiness review to one validated physical
sandbox baseline from the same non-secret operator session.

The handoff is read-only. It does not start Docker, create identities, enroll
MFA, write the registry, revoke sessions or authorize the lifecycle.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping
import json
import re

from atlasquant_aion_business_team_access_windows_operator_kit import (
    SCHEMA as OPERATOR_SCHEMA,
)
from atlasquant_aion_business_team_access_sandbox_evidence import (
    SCHEMA as BASELINE_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_WINDOWS_OPERATOR_HANDOFF_V1"
VERSION = "1"

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")
_SESSION32 = re.compile(r"^[0-9a-f]{32}$")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _parse_time(value: Any) -> datetime | None:
    token = _clean(value, 100)
    if not token:
        return None
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def operator_handoff_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TEAM_ACCESS_WINDOWS_OPERATOR_HANDOFF_POLICY_DEFINED",
        "same_operator_session_required": True,
        "readiness_before_baseline_required": True,
        "validated_readiness_required": True,
        "validated_baseline_required": True,
        "raw_secrets_allowed": False,
        "lifecycle_authorization_created": False,
        "production_authorized": False,
        "executes_action": False,
    }


def build_operator_baseline_handoff(
    readiness_review: Mapping[str, Any] | None,
    baseline_review: Mapping[str, Any] | None,
    *,
    reviewed_by: Any,
) -> dict[str, Any]:
    readiness = _mapping(readiness_review)
    baseline = _mapping(baseline_review)

    readiness_digest = _clean(
        readiness.get("readiness_digest"), 80
    ).lower()
    baseline_digest = _clean(
        baseline.get("evidence_digest"), 80
    ).lower()
    readiness_session = _clean(
        readiness.get("operator_session_id"), 64
    ).lower()
    baseline_session = _clean(
        baseline.get("operator_session_id"), 64
    ).lower()
    readiness_time = _parse_time(readiness.get("captured_at"))
    baseline_time = _parse_time(baseline.get("captured_at"))
    reviewer = _clean(reviewed_by, 120)

    gates = {
        "readiness_schema_valid": readiness.get("schema") == OPERATOR_SCHEMA,
        "readiness_state_ready": readiness.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_WINDOWS_SANDBOX_START_DECISION",
        "readiness_digest_valid": bool(_DIGEST64.fullmatch(readiness_digest)),
        "readiness_session_valid": bool(_SESSION32.fullmatch(readiness_session)),
        "readiness_non_authorizing": bool(
            readiness.get("sandbox_start_authorized") is False
            and readiness.get("baseline_collection_authorized") is False
            and readiness.get("lifecycle_execution_authorized") is False
            and readiness.get("production_authorized") is False
            and readiness.get("executes_action") is False
        ),
        "baseline_schema_valid": baseline.get("schema") == BASELINE_SCHEMA,
        "baseline_state_ready": baseline.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_TEST_REVIEW",
        "baseline_digest_valid": bool(_DIGEST64.fullmatch(baseline_digest)),
        "baseline_session_valid": bool(_SESSION32.fullmatch(baseline_session)),
        "same_operator_session": bool(
            readiness_session
            and baseline_session
            and readiness_session == baseline_session
        ),
        "timestamps_valid": readiness_time is not None and baseline_time is not None,
        "baseline_not_before_readiness": bool(
            readiness_time is not None
            and baseline_time is not None
            and baseline_time >= readiness_time
        ),
        "baseline_non_authorizing": bool(
            baseline.get("lifecycle_mutation_authorized") is False
            and baseline.get("production_authorized") is False
            and baseline.get("deploy_authorized") is False
            and baseline.get("runtime_authorized") is False
            and baseline.get("executes_action") is False
        ),
        "reviewer_present": bool(reviewer),
    }
    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers

    payload = {
        "operator_session_id": readiness_session,
        "readiness_digest": readiness_digest,
        "baseline_evidence_digest": baseline_digest,
        "readiness_captured_at": readiness_time.isoformat()
        if readiness_time
        else "",
        "baseline_captured_at": baseline_time.isoformat()
        if baseline_time
        else "",
        "reviewed_by": reviewer,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_ADMIN_TEAM_ACCESS_REAL_BASELINE_ACCEPTANCE_REVIEW"
            if ready
            else "TEAM_ACCESS_WINDOWS_OPERATOR_HANDOFF_BLOCKED"
        ),
        "gates": gates,
        "blockers": blockers,
        "operator_session_id": readiness_session if ready else "",
        "readiness_digest": readiness_digest if ready else "",
        "baseline_evidence_digest": baseline_digest if ready else "",
        "reviewed_by": reviewer if ready else "",
        "handoff_digest": _digest(payload) if ready else "",
        "baseline_accepted": False,
        "lifecycle_plan_authorized": False,
        "lifecycle_execution_authorized": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "operator_handoff_policy",
    "build_operator_baseline_handoff",
]
