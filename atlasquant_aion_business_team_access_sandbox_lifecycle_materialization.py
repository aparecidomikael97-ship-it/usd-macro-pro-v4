"""AION BUSINESS Team Access Sandbox Lifecycle Materialization V1.

Revalidates a raw physical-sandbox baseline, binds it to one explicit baseline
acceptance record and materializes the existing ten-step lifecycle plan.

This layer never executes the lifecycle and never creates the later lifecycle
authorization record. It only produces a reviewable plan packet.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

from atlasquant_aion_business_team_access_sandbox_evidence import (
    validate_baseline_evidence,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    build_lifecycle_test_plan,
)
from atlasquant_aion_business_team_access_sandbox_baseline_acceptance import (
    SCHEMA as ACCEPTANCE_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_SANDBOX_LIFECYCLE_MATERIALIZATION_V1"
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


def lifecycle_materialization_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TEAM_ACCESS_SANDBOX_LIFECYCLE_MATERIALIZATION_POLICY_DEFINED",
        "raw_baseline_revalidation_required": True,
        "explicit_baseline_acceptance_required": True,
        "plan_review_required": True,
        "automatic_lifecycle_authorization": False,
        "automatic_step_execution": False,
        "production_authorized": False,
        "executes_action": False,
    }


def materialize_lifecycle_plan(
    raw_baseline_evidence: Mapping[str, Any] | None,
    baseline_acceptance: Mapping[str, Any] | None,
    *,
    test_username: Any,
    tenant_ids: Sequence[Any] | None,
    factor_type: Any,
    requested_by: Any,
) -> dict[str, Any]:
    raw = _mapping(raw_baseline_evidence)
    acceptance = _mapping(baseline_acceptance)
    baseline_review = validate_baseline_evidence(raw)

    plan = build_lifecycle_test_plan(
        baseline_review,
        baseline_acceptance=acceptance,
        test_username=test_username,
        tenant_ids=tenant_ids,
        factor_type=factor_type,
        requested_by=requested_by,
    )

    baseline_digest = _clean(
        baseline_review.get("evidence_digest"), 80
    ).lower()
    session_id = _clean(
        baseline_review.get("operator_session_id"), 64
    ).lower()
    acceptance_digest = _clean(
        acceptance.get("acceptance_record_digest"), 80
    ).lower()
    plan_digest = _clean(plan.get("plan_digest"), 80).lower()

    gates = {
        "baseline_revalidated": baseline_review.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_TEST_REVIEW",
        "baseline_digest_valid": bool(_DIGEST64.fullmatch(baseline_digest)),
        "operator_session_valid": bool(_SESSION32.fullmatch(session_id)),
        "acceptance_schema_valid": acceptance.get("schema") == ACCEPTANCE_SCHEMA,
        "acceptance_digest_valid": bool(_DIGEST64.fullmatch(acceptance_digest)),
        "plan_ready": plan.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_EXECUTION_DECISION",
        "plan_digest_valid": bool(_DIGEST64.fullmatch(plan_digest)),
        "plan_non_authorizing": bool(
            plan.get("decision_recorded") is False
            and plan.get("account_creation_authorized") is False
            and plan.get("mfa_enrollment_authorized") is False
            and plan.get("registry_write_authorized") is False
            and plan.get("session_revocation_authorized") is False
            and plan.get("production_authorized") is False
            and plan.get("executes_action") is False
        ),
    }
    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers

    payload = {
        "operator_session_id": session_id,
        "baseline_evidence_digest": baseline_digest,
        "baseline_acceptance_record_digest": acceptance_digest,
        "plan_digest": plan_digest,
        "test_username": plan.get("test_username"),
        "tenant_ids": plan.get("tenant_ids"),
        "factor_type": plan.get("factor_type"),
        "requested_by": plan.get("requested_by"),
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_PLAN_REVIEW"
            if ready
            else "TEAM_ACCESS_SANDBOX_LIFECYCLE_MATERIALIZATION_BLOCKED"
        ),
        "gates": gates,
        "blockers": blockers,
        "operator_session_id": session_id if ready else "",
        "baseline_evidence_digest": baseline_digest if ready else "",
        "baseline_acceptance_record_digest": acceptance_digest if ready else "",
        "plan_digest": plan_digest if ready else "",
        "materialization_digest": _digest(payload) if ready else "",
        "plan": plan if ready else {},
        "lifecycle_authorization_recorded": False,
        "lifecycle_execution_authorized": False,
        "automatic_step_execution": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "lifecycle_materialization_policy",
    "materialize_lifecycle_plan",
]
