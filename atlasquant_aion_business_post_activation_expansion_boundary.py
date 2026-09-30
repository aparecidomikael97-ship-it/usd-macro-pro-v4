"""AION BUSINESS post-activation verification and expansion boundary V1.

Read-only contracts for verifying a separately executed bounded runtime activation
and opening a new administrative boundary before any scope expansion.

This module never activates runtime, changes feature flags or traffic, expands
tenant scope, deploys, rolls back, bills, publishes, contacts clients, or calls
external systems.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

EXECUTION_REVIEW_SCHEMA = (
    "ATLASQUANT_AION_BUSINESS_RUNTIME_ACTIVATION_EXECUTION_REVIEW_V1"
)
SCHEMA = "ATLASQUANT_AION_BUSINESS_POST_ACTIVATION_EXPANSION_BOUNDARY_V1"
VERSION = "1"

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_ACTIVATION_SCOPES = (
    "sandbox",
    "pilot",
    "bounded_production",
)
MAX_BOUNDED_TENANTS = 10
REQUIRED_EXPANSION_DECISION_TOKEN = "AUTHORIZE_BUSINESS_SCOPE_EXPANSION"

REQUIRED_POST_ACTIVATION_CHECKS = (
    "application_health",
    "observability",
    "tenant_isolation",
    "privacy_guardrails",
    "support_readiness",
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


def post_activation_verification_requirements() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "POST_ACTIVATION_EVIDENCE_REQUIRED",
        "required_checks": list(REQUIRED_POST_ACTIVATION_CHECKS),
        "scope_must_match_authorization": True,
        "tenant_set_must_match_authorization": True,
        "automatic_expansion_allowed": False,
        "scope_expansion_authorized": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def verify_activation_receipt(
    execution_review: Mapping[str, Any] | None,
    *,
    activated_scope: Any,
    activated_tenant_ids: Any,
    health_checks: Mapping[str, Any] | None,
    activation_evidence_ref: Any,
    runtime_enabled_for_authorized_scope: Any,
) -> dict[str, Any]:
    row = _mapping(execution_review)
    checks = _mapping(health_checks)

    authorization_digest = _clean(row.get("authorization_digest"), 128).lower()
    expected_scope = _clean(row.get("target_scope"), 80).lower()
    observed_scope = _clean(activated_scope, 80).lower()
    expected_tenants = _tenant_ids(row.get("target_tenant_ids"))
    observed_tenants = _tenant_ids(activated_tenant_ids)
    evidence_ref = _clean(activation_evidence_ref, 300)

    packet_ok = bool(
        row.get("schema") == EXECUTION_REVIEW_SCHEMA
        and row.get("state") == "RUNTIME_ACTIVATION_EXECUTION_REVIEW_REQUIRED"
        and _DIGEST64.fullmatch(authorization_digest)
        and expected_scope in ALLOWED_ACTIVATION_SCOPES
        and row.get("activation_execution_authorized") is False
        and row.get("runtime_activated") is False
        and row.get("automatic_expansion_allowed") is False
        and row.get("client_actions_authorized") is False
        and row.get("billing_authorized") is False
        and row.get("executes_action") is False
    )

    scope_ok = observed_scope == expected_scope
    tenant_set_ok = sorted(observed_tenants) == sorted(expected_tenants)
    tenant_bound_ok = bool(
        (expected_scope == "sandbox" and not expected_tenants)
        or (
            expected_scope in {"pilot", "bounded_production"}
            and 1 <= len(expected_tenants) <= MAX_BOUNDED_TENANTS
        )
    )
    normalized_checks = {
        name: _clean(checks.get(name), 40).lower()
        for name in REQUIRED_POST_ACTIVATION_CHECKS
    }
    checks_ok = bool(
        checks and all(value == "success" for value in normalized_checks.values())
    )
    evidence_ok = bool(evidence_ref)
    runtime_scope_ok = bool(
        type(runtime_enabled_for_authorized_scope) is bool
        and runtime_enabled_for_authorized_scope is True
    )

    gates = {
        "execution_review_packet_valid": packet_ok,
        "activated_scope_matches_authorized_scope": scope_ok,
        "activated_tenants_match_authorized_tenants": tenant_set_ok,
        "authorized_scope_remains_bounded": tenant_bound_ok,
        "all_post_activation_checks_success": checks_ok,
        "activation_evidence_reference_present": evidence_ok,
        "runtime_enabled_only_for_authorized_scope_confirmed": runtime_scope_ok,
    }
    blockers = [name for name, passed in gates.items() if not passed]

    supplied = bool(
        execution_review
        or observed_scope
        or observed_tenants
        or checks
        or evidence_ref
        or runtime_enabled_for_authorized_scope is not None
    )
    if not supplied:
        state = "POST_ACTIVATION_EVIDENCE_REQUIRED"
    elif blockers:
        state = "POST_ACTIVATION_VERIFICATION_BLOCKED"
    else:
        state = "RUNTIME_ACTIVATION_VERIFIED_SCOPE_FROZEN"

    payload = {
        "authorization_digest": authorization_digest,
        "activated_scope": observed_scope,
        "activated_tenant_ids": sorted(observed_tenants),
        "health_checks": normalized_checks,
        "activation_evidence_ref": evidence_ref,
    } if state == "RUNTIME_ACTIVATION_VERIFIED_SCOPE_FROZEN" else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "gates": gates,
        "blockers": blockers,
        "authorization_digest": authorization_digest if packet_ok else "",
        "activated_scope": observed_scope if scope_ok else "",
        "activated_tenant_ids": observed_tenants if tenant_set_ok else [],
        "health_checks": normalized_checks,
        "activation_verification_digest": _digest(payload) if payload else "",
        "runtime_activation_verified": (
            state == "RUNTIME_ACTIVATION_VERIFIED_SCOPE_FROZEN"
        ),
        "scope_frozen": state == "RUNTIME_ACTIVATION_VERIFIED_SCOPE_FROZEN",
        "automatic_expansion_allowed": False,
        "scope_expansion_authorized": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def expansion_boundary_packet(
    verification: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(verification)
    digest = _clean(row.get("activation_verification_digest"), 128).lower()
    scope = _clean(row.get("activated_scope"), 80).lower()
    tenants = _tenant_ids(row.get("activated_tenant_ids"))
    tenant_bound_ok = bool(
        (scope == "sandbox" and not tenants)
        or (
            scope in {"pilot", "bounded_production"}
            and 1 <= len(tenants) <= MAX_BOUNDED_TENANTS
        )
    )

    ready = bool(
        row.get("schema") == SCHEMA
        and row.get("state") == "RUNTIME_ACTIVATION_VERIFIED_SCOPE_FROZEN"
        and row.get("runtime_activation_verified") is True
        and row.get("scope_frozen") is True
        and _DIGEST64.fullmatch(digest)
        and scope in ALLOWED_ACTIVATION_SCOPES
        and tenant_bound_ok
        and row.get("automatic_expansion_allowed") is False
        and row.get("scope_expansion_authorized") is False
        and row.get("client_actions_authorized") is False
        and row.get("billing_authorized") is False
        and row.get("executes_action") is False
    )

    return {
        "schema": "ATLASQUANT_AION_BUSINESS_SCOPE_EXPANSION_BOUNDARY_PACKET_V1",
        "state": "EXPLICIT_EXPANSION_DECISION_REQUIRED" if ready else "NOT_READY",
        "activation_verification_digest": digest if ready else "",
        "current_scope": scope if ready else "",
        "current_tenant_ids": tenants if ready else [],
        "required_decision_token": (
            REQUIRED_EXPANSION_DECISION_TOKEN if ready else ""
        ),
        "required_acknowledgements": (
            list(EXPANSION_ACKNOWLEDGEMENTS) if ready else []
        ),
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
    "ALLOWED_ACTIVATION_SCOPES",
    "MAX_BOUNDED_TENANTS",
    "REQUIRED_POST_ACTIVATION_CHECKS",
    "REQUIRED_EXPANSION_DECISION_TOKEN",
    "EXPANSION_ACKNOWLEDGEMENTS",
    "post_activation_verification_requirements",
    "verify_activation_receipt",
    "expansion_boundary_packet",
]
