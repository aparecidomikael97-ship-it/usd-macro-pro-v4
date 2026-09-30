"""AION BUSINESS Team Access Lifecycle Plan Package V1.

Validates one generated sandbox lifecycle plan artifact before it may be used by
the explicit lifecycle authorization layer.

The package is read-only and recomputes plan integrity. It never creates an
authorization record and never executes lifecycle steps.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    SCHEMA as PLAN_SCHEMA,
    REQUIRED_ACKNOWLEDGEMENTS,
    REQUIRED_DECISION_TOKEN,
    LIFECYCLE_STEP_IDS,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_LIFECYCLE_PLAN_PACKAGE_V1"
VERSION = "1"

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        return []
    rows: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            return []
        rows.append(dict(item))
    return rows


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def lifecycle_plan_package_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TEAM_ACCESS_LIFECYCLE_PLAN_PACKAGE_POLICY_DEFINED",
        "plan_integrity_recalculated": True,
        "baseline_acceptance_digest_required": True,
        "ten_step_sequence_required": True,
        "authorization_record_created": False,
        "step_execution_authorized": False,
        "production_authorized": False,
        "executes_action": False,
    }


def validate_lifecycle_plan_package(
    plan: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(plan)
    steps = _rows(row.get("steps"))

    plan_digest = _clean(row.get("plan_digest"), 80).lower()
    baseline_digest = _clean(
        row.get("baseline_evidence_digest"), 80
    ).lower()
    acceptance_digest = _clean(
        row.get("baseline_acceptance_record_digest"), 80
    ).lower()
    username = _clean(row.get("test_username"), 160)
    tenants = [
        _clean(item, 120)
        for item in list(row.get("tenant_ids") or [])
        if _clean(item, 120)
    ]
    factor = _clean(row.get("factor_type"), 60).upper()
    requested_by = _clean(row.get("requested_by"), 120)

    step_ids = [
        _clean(item.get("id"), 120).upper()
        for item in steps
    ]
    step_orders = [item.get("order") for item in steps]

    canonical_payload = {
        "baseline_evidence_digest": baseline_digest,
        "baseline_acceptance_record_digest": acceptance_digest,
        "test_username": username,
        "tenant_ids": sorted(set(tenants)),
        "factor_type": factor,
        "requested_by": requested_by,
        "steps": steps,
    }
    recomputed_digest = _digest(canonical_payload)

    gates = {
        "schema_valid": row.get("schema") == PLAN_SCHEMA,
        "state_ready": row.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_EXECUTION_DECISION",
        "plan_digest_valid": bool(_DIGEST64.fullmatch(plan_digest)),
        "plan_digest_integrity": bool(
            _DIGEST64.fullmatch(plan_digest)
            and plan_digest == recomputed_digest
        ),
        "baseline_digest_valid": bool(_DIGEST64.fullmatch(baseline_digest)),
        "acceptance_digest_valid": bool(_DIGEST64.fullmatch(acceptance_digest)),
        "sandbox_username": bool(username and username.startswith("sandbox.")),
        "tenant_scope_present": bool(tenants),
        "requested_by_present": bool(requested_by),
        "steps_count_exact": len(steps) == len(LIFECYCLE_STEP_IDS),
        "steps_ids_exact": step_ids == list(LIFECYCLE_STEP_IDS),
        "steps_order_exact": step_orders == list(
            range(1, len(LIFECYCLE_STEP_IDS) + 1)
        ),
        "decision_token_exact": row.get("required_decision_token")
        == REQUIRED_DECISION_TOKEN,
        "acknowledgements_exact": row.get("required_acknowledgements")
        == list(REQUIRED_ACKNOWLEDGEMENTS),
        "decision_not_recorded": row.get("decision_recorded") is False,
        "account_creation_not_authorized": row.get(
            "account_creation_authorized"
        ) is False,
        "mfa_enrollment_not_authorized": row.get(
            "mfa_enrollment_authorized"
        ) is False,
        "registry_write_not_authorized": row.get(
            "registry_write_authorized"
        ) is False,
        "session_revocation_not_authorized": row.get(
            "session_revocation_authorized"
        ) is False,
        "production_not_authorized": row.get("production_authorized") is False,
        "deploy_not_authorized": row.get("deploy_authorized") is False,
        "runtime_not_authorized": row.get("runtime_authorized") is False,
        "non_executing": row.get("executes_action") is False,
    }

    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers

    package_payload = {
        "plan_digest": plan_digest,
        "baseline_evidence_digest": baseline_digest,
        "baseline_acceptance_record_digest": acceptance_digest,
        "test_username": username,
        "tenant_ids": sorted(set(tenants)),
        "factor_type": factor,
        "requested_by": requested_by,
        "step_ids": step_ids,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_ADMIN_TEAM_ACCESS_LIFECYCLE_AUTHORIZATION_RECORD"
            if ready
            else "TEAM_ACCESS_LIFECYCLE_PLAN_PACKAGE_BLOCKED"
        ),
        "gates": gates,
        "blockers": blockers,
        "plan_digest": plan_digest if ready else "",
        "baseline_evidence_digest": baseline_digest if ready else "",
        "baseline_acceptance_record_digest": acceptance_digest if ready else "",
        "package_digest": _digest(package_payload) if ready else "",
        "authorization_record_created": False,
        "lifecycle_execution_authorized": False,
        "sandbox_step_execution_authorized": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "lifecycle_plan_package_policy",
    "validate_lifecycle_plan_package",
]
