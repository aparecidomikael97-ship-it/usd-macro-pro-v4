"""AION BUSINESS Team Access Sandbox Lifecycle Plan V1.

Builds a non-executing, fail-closed manual test plan after a validated sandbox
baseline. This module does not create users, enroll MFA, write PostgreSQL,
disable accounts, revoke sessions or call providers.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

from atlasquant_access_control import normalize_username
from atlasquant_aion_business_team_access_sandbox_evidence import (
    SCHEMA as EVIDENCE_SCHEMA,
)
from atlasquant_aion_business_team_access_sandbox_baseline_acceptance import (
    verify_baseline_acceptance_binding,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_SANDBOX_LIFECYCLE_PLAN_V1"
VERSION = "1"

REQUIRED_DECISION_TOKEN = "AUTHORIZE_TEAM_ACCESS_SANDBOX_LIFECYCLE_TEST"
REQUIRED_ACKNOWLEDGEMENTS = (
    "SANDBOX_ONLY",
    "NO_PRODUCTION_TARGETS",
    "TEST_IDENTITY_ONLY",
    "SECRETS_STAY_LOCAL",
    "MANUAL_STEP_BY_STEP_APPLY",
    "STOP_ON_FIRST_MISMATCH",
    "REVOCATION_AND_CLEANUP_REQUIRED",
)

ALLOWED_FACTORS = ("PASSKEY", "SECURITY_KEY", "TOTP")
LIFECYCLE_STEP_IDS = (
    "CREATE_INDIVIDUAL_SANDBOX_ACCOUNT",
    "ENROLL_STRONG_AUTH",
    "VERIFY_STRONG_AUTH_CHALLENGE",
    "WRITE_REGISTRY_REVISION",
    "VERIFY_REGISTRY_EXACT_READBACK",
    "DISABLE_SANDBOX_ACCOUNT",
    "REVOKE_SANDBOX_SESSIONS",
    "MARK_REGISTRY_MEMBERSHIP_INACTIVE",
    "VERIFY_INACTIVE_REGISTRY_READBACK",
    "ASSEMBLE_E2E_EVIDENCE_PACKET",
)
_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _tokens(value: Any) -> set[str]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return set()
    return {_clean(item, 100).upper() for item in value if _clean(item, 100)}


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def lifecycle_plan_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TEAM_ACCESS_SANDBOX_LIFECYCLE_PLAN_POLICY_DEFINED",
        "required_decision_token": REQUIRED_DECISION_TOKEN,
        "required_acknowledgements": list(REQUIRED_ACKNOWLEDGEMENTS),
        "allowed_factors": list(ALLOWED_FACTORS),
        "baseline_acceptance_required": True,
        "sandbox_only": True,
        "automatic_apply": False,
        "production_targets_allowed": False,
        "executes_action": False,
    }


def build_lifecycle_test_plan(
    baseline_review: Mapping[str, Any] | None,
    *,
    baseline_acceptance: Mapping[str, Any] | None,
    test_username: Any,
    tenant_ids: Sequence[Any] | None,
    factor_type: Any,
    requested_by: Any,
) -> dict[str, Any]:
    baseline = _mapping(baseline_review)
    acceptance_binding = verify_baseline_acceptance_binding(
        baseline_review,
        baseline_acceptance,
    )
    username = normalize_username(test_username)
    requester = normalize_username(requested_by)
    tenants = sorted(
        {
            _clean(item, 120)
            for item in list(tenant_ids or [])
            if _clean(item, 120)
        }
    )
    factor = _clean(factor_type, 60).upper()
    baseline_digest = _clean(baseline.get("evidence_digest"), 80).lower()

    gates = {
        "baseline_schema_valid": baseline.get("schema") == EVIDENCE_SCHEMA,
        "baseline_review_ready": baseline.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_TEST_REVIEW",
        "baseline_digest_valid": bool(_DIGEST64.fullmatch(baseline_digest)),
        "baseline_non_executing": baseline.get("executes_action") is False,
        "baseline_acceptance_binding_match": (
            acceptance_binding.get("binding_match") is True
            and acceptance_binding.get("lifecycle_plan_input_authorized") is True
            and acceptance_binding.get("lifecycle_execution_authorized") is False
            and acceptance_binding.get("production_authorized") is False
            and acceptance_binding.get("executes_action") is False
        ),
        "test_username_present": bool(username),
        "test_username_sandbox_scoped": username.startswith("sandbox."),
        "tenant_scope_present": bool(tenants),
        "factor_allowed": factor in ALLOWED_FACTORS,
        "requester_present": bool(requester),
    }
    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers

    steps = [
        {
            "order": 1,
            "id": "CREATE_INDIVIDUAL_SANDBOX_ACCOUNT",
            "mutation": True,
            "requires_manual_apply": True,
            "evidence_required": [
                "account_ref",
                "username_match",
                "individual_account_verified",
                "shared_account_absent",
            ],
        },
        {
            "order": 2,
            "id": "ENROLL_STRONG_AUTH",
            "mutation": True,
            "requires_manual_apply": True,
            "evidence_required": [
                "factor_type",
                "factor_ref",
                "enrollment_verified",
            ],
        },
        {
            "order": 3,
            "id": "VERIFY_STRONG_AUTH_CHALLENGE",
            "mutation": False,
            "requires_manual_apply": True,
            "evidence_required": [
                "challenge_verified",
                "observed_at",
            ],
        },
        {
            "order": 4,
            "id": "WRITE_REGISTRY_REVISION",
            "mutation": True,
            "requires_manual_apply": True,
            "evidence_required": [
                "revision",
                "previous_revision_digest",
                "registry_digest",
            ],
        },
        {
            "order": 5,
            "id": "VERIFY_REGISTRY_EXACT_READBACK",
            "mutation": False,
            "requires_manual_apply": True,
            "evidence_required": [
                "readback_registry_digest",
                "readback_verified",
            ],
        },
        {
            "order": 6,
            "id": "DISABLE_SANDBOX_ACCOUNT",
            "mutation": True,
            "requires_manual_apply": True,
            "evidence_required": [
                "account_disabled_verified",
            ],
        },
        {
            "order": 7,
            "id": "REVOKE_SANDBOX_SESSIONS",
            "mutation": True,
            "requires_manual_apply": True,
            "evidence_required": [
                "sessions_revoked_verified",
            ],
        },
        {
            "order": 8,
            "id": "MARK_REGISTRY_MEMBERSHIP_INACTIVE",
            "mutation": True,
            "requires_manual_apply": True,
            "evidence_required": [
                "registry_membership_inactive_verified",
            ],
        },
        {
            "order": 9,
            "id": "VERIFY_INACTIVE_REGISTRY_READBACK",
            "mutation": False,
            "requires_manual_apply": True,
            "evidence_required": [
                "registry_readback_verified",
                "inactive_membership_digest",
            ],
        },
        {
            "order": 10,
            "id": "ASSEMBLE_E2E_EVIDENCE_PACKET",
            "mutation": False,
            "requires_manual_apply": True,
            "evidence_required": [
                "activation_review_evidence",
                "revocation_evidence",
            ],
        },
    ] if ready else []

    payload = {
        "baseline_evidence_digest": baseline_digest,
        "baseline_acceptance_record_digest": _clean(
            _mapping(baseline_acceptance).get("acceptance_record_digest"), 80
        ).lower(),
        "test_username": username,
        "tenant_ids": tenants,
        "factor_type": factor,
        "requested_by": requester,
        "steps": steps,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_EXECUTION_DECISION"
            if ready
            else "TEAM_ACCESS_SANDBOX_LIFECYCLE_PLAN_BLOCKED"
        ),
        "gates": gates,
        "blockers": blockers,
        "test_username": username if ready else "",
        "tenant_ids": tenants if ready else [],
        "factor_type": factor if ready else "",
        "baseline_evidence_digest": baseline_digest if ready else "",
        "baseline_acceptance_record_digest": _clean(
            _mapping(baseline_acceptance).get("acceptance_record_digest"), 80
        ).lower() if ready else "",
        "requested_by": requester if ready else "",
        "steps": steps,
        "plan_digest": _digest(payload) if ready else "",
        "required_decision_token": REQUIRED_DECISION_TOKEN if ready else "",
        "required_acknowledgements": (
            list(REQUIRED_ACKNOWLEDGEMENTS) if ready else []
        ),
        "decision_recorded": False,
        "account_creation_authorized": False,
        "mfa_enrollment_authorized": False,
        "registry_write_authorized": False,
        "session_revocation_authorized": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "REQUIRED_DECISION_TOKEN",
    "REQUIRED_ACKNOWLEDGEMENTS",
    "ALLOWED_FACTORS",
    "LIFECYCLE_STEP_IDS",
    "lifecycle_plan_policy",
    "build_lifecycle_test_plan",
]
