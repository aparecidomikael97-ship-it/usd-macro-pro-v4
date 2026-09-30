"""AION BUSINESS post-expansion verification and cycle freeze V1.

Read-only contracts for verifying a separately executed bounded scope expansion,
freezing the resulting scope, and reopening only the same explicit expansion
boundary for a future cycle.

This module never expands tenants, changes runtime flags or traffic, deploys,
rolls back, publishes, bills, contacts clients, or calls external systems.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

EXECUTION_REVIEW_SCHEMA = (
    "ATLASQUANT_AION_BUSINESS_SCOPE_EXPANSION_EXECUTION_REVIEW_V1"
)
BOUNDARY_SCHEMA = "ATLASQUANT_AION_BUSINESS_SCOPE_EXPANSION_BOUNDARY_PACKET_V1"
SCHEMA = "ATLASQUANT_AION_BUSINESS_POST_EXPANSION_CYCLE_FREEZE_V1"
VERSION = "1"

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")
MAX_BOUNDED_TENANTS = 10
ALLOWED_SCOPES = ("sandbox", "pilot", "bounded_production")
REQUIRED_EXPANSION_DECISION_TOKEN = "AUTHORIZE_BUSINESS_SCOPE_EXPANSION"

REQUIRED_POST_EXPANSION_CHECKS = (
    "application_health",
    "observability",
    "tenant_isolation",
    "privacy_guardrails",
    "support_readiness",
    "capacity_guardrail",
    "billing_guardrail",
    "rollback_ready",
)

EXPANSION_ACKNOWLEDGEMENTS = (
    "current_activation_is_verified",
    "current_scope_is_frozen",
    "new_scope_requires_separate_review",
    "privacy_support_finance_must_be_revalidated",
    "monitoring_and_rollback_must_remain_available",
    "automatic_expansion_is_forbidden",
    "client_actions_and_billing_remain_separate",
)


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


def _tenant_ids(value: Any) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return []
    result: list[str] = []
    for item in value:
        text = _clean(item, 120)
        if text and text not in result:
            result.append(text)
        if len(result) > MAX_BOUNDED_TENANTS:
            break
    return result


def _scope_rank(scope: str) -> int:
    try:
        return ALLOWED_SCOPES.index(scope)
    except ValueError:
        return -1


def post_expansion_verification_requirements() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "POST_EXPANSION_EVIDENCE_REQUIRED",
        "required_checks": list(REQUIRED_POST_EXPANSION_CHECKS),
        "proposed_scope_must_match_observed_scope": True,
        "proposed_tenants_must_match_observed_tenants": True,
        "scope_expansion_verified": False,
        "scope_frozen": False,
        "automatic_expansion_allowed": False,
        "scope_expansion_authorized": False,
        "expansion_execution_authorized": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def verify_expansion_receipt(
    execution_review: Mapping[str, Any] | None,
    *,
    observed_scope: Any,
    observed_tenant_ids: Any,
    health_checks: Mapping[str, Any] | None,
    expansion_evidence_ref: Any,
    runtime_matches_authorized_expansion: Any,
) -> dict[str, Any]:
    row = _mapping(execution_review)
    checks = _mapping(health_checks)

    authorization_digest = _clean(row.get("authorization_digest"), 128).lower()
    current_scope = _clean(row.get("current_scope"), 80).lower()
    proposed_scope = _clean(row.get("proposed_scope"), 80).lower()
    current_tenants = _tenant_ids(row.get("current_tenant_ids"))
    proposed_tenants = _tenant_ids(row.get("proposed_tenant_ids"))
    actual_scope = _clean(observed_scope, 80).lower()
    actual_tenants = _tenant_ids(observed_tenant_ids)
    evidence_ref = _clean(expansion_evidence_ref, 300)

    packet_ok = bool(
        row.get("schema") == EXECUTION_REVIEW_SCHEMA
        and row.get("state") == "SCOPE_EXPANSION_EXECUTION_REVIEW_REQUIRED"
        and _DIGEST64.fullmatch(authorization_digest)
        and current_scope in ALLOWED_SCOPES
        and proposed_scope in {"pilot", "bounded_production"}
        and row.get("expansion_execution_authorized") is False
        and row.get("automatic_expansion_allowed") is False
        and row.get("client_actions_authorized") is False
        and row.get("billing_authorized") is False
        and row.get("executes_action") is False
    )
    current_bound_ok = bool(
        (current_scope == "sandbox" and not current_tenants)
        or (
            current_scope in {"pilot", "bounded_production"}
            and 1 <= len(current_tenants) <= MAX_BOUNDED_TENANTS
        )
    )
    current_rank = _scope_rank(current_scope)
    proposed_rank = _scope_rank(proposed_scope)
    proposed_bound_ok = bool(
        proposed_scope in {"pilot", "bounded_production"}
        and 1 <= len(proposed_tenants) <= MAX_BOUNDED_TENANTS
        and set(current_tenants).issubset(set(proposed_tenants))
        and proposed_rank in {current_rank, current_rank + 1}
        and (
            proposed_rank == current_rank + 1
            or len(proposed_tenants) > len(current_tenants)
        )
        and not (
            current_scope == "sandbox"
            and proposed_scope != "pilot"
        )
        and not (
            current_scope == "bounded_production"
            and proposed_scope != "bounded_production"
        )
    )
    scope_match = actual_scope == proposed_scope
    tenants_match = sorted(actual_tenants) == sorted(proposed_tenants)
    observed_bound_ok = bool(
        actual_scope in {"pilot", "bounded_production"}
        and 1 <= len(actual_tenants) <= MAX_BOUNDED_TENANTS
    )

    normalized_checks = {
        name: _clean(checks.get(name), 40).lower()
        for name in REQUIRED_POST_EXPANSION_CHECKS
    }
    checks_ok = bool(
        checks and all(value == "success" for value in normalized_checks.values())
    )
    evidence_ok = bool(evidence_ref)
    runtime_match_ok = bool(
        type(runtime_matches_authorized_expansion) is bool
        and runtime_matches_authorized_expansion is True
    )

    gates = {
        "execution_review_packet_valid": packet_ok,
        "current_scope_bounded": current_bound_ok,
        "proposed_scope_bounded": proposed_bound_ok,
        "observed_scope_matches_proposed_scope": scope_match,
        "observed_tenants_match_proposed_tenants": tenants_match,
        "observed_scope_remains_bounded": observed_bound_ok,
        "all_post_expansion_checks_success": checks_ok,
        "expansion_evidence_reference_present": evidence_ok,
        "runtime_matches_authorized_expansion_confirmed": runtime_match_ok,
    }
    blockers = [name for name, passed in gates.items() if not passed]

    supplied = bool(
        execution_review
        or actual_scope
        or actual_tenants
        or checks
        or evidence_ref
        or runtime_matches_authorized_expansion is not None
    )
    if not supplied:
        state = "POST_EXPANSION_EVIDENCE_REQUIRED"
    elif blockers:
        state = "POST_EXPANSION_VERIFICATION_BLOCKED"
    else:
        state = "SCOPE_EXPANSION_VERIFIED_AND_FROZEN"

    payload = {
        "authorization_digest": authorization_digest,
        "previous_scope": current_scope,
        "previous_tenant_ids": sorted(current_tenants),
        "verified_scope": actual_scope,
        "verified_tenant_ids": sorted(actual_tenants),
        "health_checks": normalized_checks,
        "expansion_evidence_ref": evidence_ref,
    } if state == "SCOPE_EXPANSION_VERIFIED_AND_FROZEN" else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "gates": gates,
        "blockers": blockers,
        "authorization_digest": authorization_digest if packet_ok else "",
        "previous_scope": current_scope if current_bound_ok else "",
        "previous_tenant_ids": current_tenants if current_bound_ok else [],
        "verified_scope": actual_scope if scope_match and observed_bound_ok else "",
        "verified_tenant_ids": actual_tenants if tenants_match and observed_bound_ok else [],
        "health_checks": normalized_checks,
        "expansion_verification_digest": _digest(payload) if payload else "",
        "scope_expansion_verified": state == "SCOPE_EXPANSION_VERIFIED_AND_FROZEN",
        "scope_frozen": state == "SCOPE_EXPANSION_VERIFIED_AND_FROZEN",
        "automatic_expansion_allowed": False,
        "scope_expansion_authorized": False,
        "expansion_execution_authorized": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def renewed_expansion_boundary_packet(
    verification: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(verification)
    digest = _clean(row.get("expansion_verification_digest"), 128).lower()
    scope = _clean(row.get("verified_scope"), 80).lower()
    tenants = _tenant_ids(row.get("verified_tenant_ids"))
    scope_bound_ok = bool(
        scope in {"pilot", "bounded_production"}
        and 1 <= len(tenants) <= MAX_BOUNDED_TENANTS
    )

    ready = bool(
        row.get("schema") == SCHEMA
        and row.get("state") == "SCOPE_EXPANSION_VERIFIED_AND_FROZEN"
        and row.get("scope_expansion_verified") is True
        and row.get("scope_frozen") is True
        and _DIGEST64.fullmatch(digest)
        and scope_bound_ok
        and row.get("automatic_expansion_allowed") is False
        and row.get("scope_expansion_authorized") is False
        and row.get("expansion_execution_authorized") is False
        and row.get("client_actions_authorized") is False
        and row.get("billing_authorized") is False
        and row.get("executes_action") is False
    )

    return {
        "schema": BOUNDARY_SCHEMA,
        "state": "EXPLICIT_EXPANSION_DECISION_REQUIRED" if ready else "NOT_READY",
        "activation_verification_digest": digest if ready else "",
        "current_scope": scope if ready else "",
        "current_tenant_ids": tenants if ready else [],
        "required_decision_token": REQUIRED_EXPANSION_DECISION_TOKEN if ready else "",
        "required_acknowledgements": list(EXPANSION_ACKNOWLEDGEMENTS) if ready else [],
        "generic_confirmation_is_authorization": False,
        "automatic_expansion_allowed": False,
        "scope_expansion_authorized": False,
        "expansion_execution_authorized": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "EXECUTION_REVIEW_SCHEMA",
    "BOUNDARY_SCHEMA",
    "MAX_BOUNDED_TENANTS",
    "ALLOWED_SCOPES",
    "REQUIRED_POST_EXPANSION_CHECKS",
    "REQUIRED_EXPANSION_DECISION_TOKEN",
    "EXPANSION_ACKNOWLEDGEMENTS",
    "post_expansion_verification_requirements",
    "verify_expansion_receipt",
    "renewed_expansion_boundary_packet",
]
