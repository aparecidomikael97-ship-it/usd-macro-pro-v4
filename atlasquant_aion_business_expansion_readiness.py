"""AION BUSINESS scope expansion readiness V1.

Fail-closed administrative contracts for reviewing a future BUSINESS scope
expansion after a verified activation has frozen the current scope.

The module never expands tenants, changes runtime flags or traffic, deploys,
rolls back, publishes, bills, contacts clients, or calls external systems.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

BOUNDARY_SCHEMA = "ATLASQUANT_AION_BUSINESS_SCOPE_EXPANSION_BOUNDARY_PACKET_V1"
SCHEMA = "ATLASQUANT_AION_BUSINESS_SCOPE_EXPANSION_READINESS_V1"
VERSION = "1"

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_EXPANSION_DECISION_TOKEN = "AUTHORIZE_BUSINESS_SCOPE_EXPANSION"
MAX_BOUNDED_TENANTS = 10

ALLOWED_SCOPES = (
    "sandbox",
    "pilot",
    "bounded_production",
)

EXPANSION_ACKNOWLEDGEMENTS = (
    "current_activation_is_verified",
    "current_scope_is_frozen",
    "proposed_scope_is_bounded",
    "existing_tenants_are_preserved",
    "privacy_support_finance_are_revalidated",
    "monitoring_and_rollback_are_available",
    "capacity_and_integrations_are_ready",
    "automatic_expansion_is_forbidden",
    "billing_and_client_actions_remain_separate",
)

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


def expansion_authorization_requirements() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "EXPLICIT_EXPANSION_DECISION_REQUIRED",
        "required_decision_token": REQUIRED_EXPANSION_DECISION_TOKEN,
        "required_acknowledgements": list(EXPANSION_ACKNOWLEDGEMENTS),
        "max_bounded_tenants": MAX_BOUNDED_TENANTS,
        "generic_confirmation_is_authorization": False,
        "scope_expansion_authorized": False,
        "expansion_execution_authorized": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def expansion_preflight(
    boundary_packet: Mapping[str, Any] | None,
    *,
    proposed_scope: Any,
    proposed_tenant_ids: Any,
    monitoring_plan_ref: Any,
    rollback_plan_ref: Any,
    privacy_ready: Any,
    support_ready: Any,
    finance_guardrails_ready: Any,
    integrations_healthy: Any,
    capacity_ready: Any,
) -> dict[str, Any]:
    row = _mapping(boundary_packet)
    verification_digest = _clean(
        row.get("activation_verification_digest"), 128
    ).lower()
    current_scope = _clean(row.get("current_scope"), 80).lower()
    current_tenants = _tenant_ids(row.get("current_tenant_ids"))
    next_scope = _clean(proposed_scope, 80).lower()
    next_tenants = _tenant_ids(proposed_tenant_ids)
    monitoring_ref = _clean(monitoring_plan_ref, 300)
    rollback_ref = _clean(rollback_plan_ref, 300)

    boundary_ok = bool(
        row.get("schema") == BOUNDARY_SCHEMA
        and row.get("state") == "EXPLICIT_EXPANSION_DECISION_REQUIRED"
        and row.get("required_decision_token") == REQUIRED_EXPANSION_DECISION_TOKEN
        and row.get("generic_confirmation_is_authorization") is False
        and _DIGEST64.fullmatch(verification_digest)
        and current_scope in ALLOWED_SCOPES
        and row.get("automatic_expansion_allowed") is False
        and row.get("scope_expansion_authorized") is False
        and row.get("expansion_execution_authorized") is False
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
    proposed_bound_ok = bool(
        next_scope in {"pilot", "bounded_production"}
        and 1 <= len(next_tenants) <= MAX_BOUNDED_TENANTS
    )
    preserves_existing = set(current_tenants).issubset(set(next_tenants))

    current_rank = _scope_rank(current_scope)
    next_rank = _scope_rank(next_scope)
    no_scope_skip = bool(
        current_rank >= 0
        and next_rank >= 0
        and next_rank in {current_rank, current_rank + 1}
    )
    meaningful_expansion = bool(
        (
            next_scope == current_scope
            and len(next_tenants) > len(current_tenants)
        )
        or next_rank == current_rank + 1
    )
    sandbox_transition_ok = not (
        current_scope == "sandbox" and next_scope != "pilot"
    )
    terminal_scope_ok = not (
        current_scope == "bounded_production"
        and next_scope != "bounded_production"
    )

    privacy_ok = type(privacy_ready) is bool and privacy_ready is True
    support_ok = type(support_ready) is bool and support_ready is True
    finance_ok = (
        type(finance_guardrails_ready) is bool
        and finance_guardrails_ready is True
    )
    integrations_ok = (
        type(integrations_healthy) is bool and integrations_healthy is True
    )
    capacity_ok = type(capacity_ready) is bool and capacity_ready is True
    monitoring_ok = bool(monitoring_ref)
    rollback_ok = bool(rollback_ref)

    gates = {
        "verified_expansion_boundary": boundary_ok,
        "current_scope_bounded": current_bound_ok,
        "proposed_scope_bounded": proposed_bound_ok,
        "existing_tenants_preserved": preserves_existing,
        "no_scope_skip_or_downgrade": no_scope_skip,
        "meaningful_expansion": meaningful_expansion,
        "sandbox_may_only_promote_to_pilot": sandbox_transition_ok,
        "bounded_production_is_terminal_scope": terminal_scope_ok,
        "monitoring_plan_present": monitoring_ok,
        "rollback_plan_present": rollback_ok,
        "privacy_ready": privacy_ok,
        "support_ready": support_ok,
        "finance_guardrails_ready": finance_ok,
        "integrations_healthy": integrations_ok,
        "capacity_ready": capacity_ok,
    }
    blockers = [name for name, passed in gates.items() if not passed]
    state = (
        "READY_FOR_EXPLICIT_EXPANSION_AUTHORIZATION"
        if not blockers
        else "EXPANSION_PREFLIGHT_BLOCKED"
    )

    payload = {
        "activation_verification_digest": verification_digest,
        "current_scope": current_scope,
        "current_tenant_ids": sorted(current_tenants),
        "proposed_scope": next_scope,
        "proposed_tenant_ids": sorted(next_tenants),
        "monitoring_plan_ref": monitoring_ref,
        "rollback_plan_ref": rollback_ref,
    } if state == "READY_FOR_EXPLICIT_EXPANSION_AUTHORIZATION" else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "gates": gates,
        "blockers": blockers,
        "preflight_digest": _digest(payload) if payload else "",
        "activation_verification_digest": (
            verification_digest if boundary_ok else ""
        ),
        "current_scope": current_scope if current_bound_ok else "",
        "current_tenant_ids": current_tenants if current_bound_ok else [],
        "proposed_scope": next_scope if proposed_bound_ok else "",
        "proposed_tenant_ids": next_tenants if proposed_bound_ok else [],
        "monitoring_plan_ref": monitoring_ref if monitoring_ok else "",
        "rollback_plan_ref": rollback_ref if rollback_ok else "",
        "required_decision_token": (
            REQUIRED_EXPANSION_DECISION_TOKEN
            if state == "READY_FOR_EXPLICIT_EXPANSION_AUTHORIZATION"
            else ""
        ),
        "required_acknowledgements": (
            list(EXPANSION_ACKNOWLEDGEMENTS)
            if state == "READY_FOR_EXPLICIT_EXPANSION_AUTHORIZATION"
            else []
        ),
        "generic_confirmation_is_authorization": False,
        "scope_expansion_authorized": False,
        "expansion_execution_authorized": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def record_expansion_authorization(
    preflight: Mapping[str, Any] | None,
    *,
    decision_token: Any,
    acknowledgements: Mapping[str, Any] | None,
    actor: Any,
) -> dict[str, Any]:
    row = _mapping(preflight)
    ack = _mapping(acknowledgements)
    token = _clean(decision_token, 120)
    actor_text = _clean(actor, 120)
    preflight_digest = _clean(row.get("preflight_digest"), 128).lower()
    current_scope = _clean(row.get("current_scope"), 80).lower()
    next_scope = _clean(row.get("proposed_scope"), 80).lower()
    current_tenants = _tenant_ids(row.get("current_tenant_ids"))
    next_tenants = _tenant_ids(row.get("proposed_tenant_ids"))

    preflight_ok = bool(
        row.get("schema") == SCHEMA
        and row.get("state") == "READY_FOR_EXPLICIT_EXPANSION_AUTHORIZATION"
        and _DIGEST64.fullmatch(preflight_digest)
        and row.get("required_decision_token") == REQUIRED_EXPANSION_DECISION_TOKEN
        and row.get("generic_confirmation_is_authorization") is False
        and row.get("scope_expansion_authorized") is False
        and row.get("expansion_execution_authorized") is False
        and row.get("automatic_expansion_allowed") is False
        and row.get("executes_action") is False
    )
    scope_ok = bool(
        current_scope in ALLOWED_SCOPES
        and next_scope in {"pilot", "bounded_production"}
        and 1 <= len(next_tenants) <= MAX_BOUNDED_TENANTS
        and set(current_tenants).issubset(set(next_tenants))
    )
    token_ok = token == REQUIRED_EXPANSION_DECISION_TOKEN
    acknowledgements_ok = bool(
        all(ack.get(name) is True for name in EXPANSION_ACKNOWLEDGEMENTS)
    )
    actor_ok = bool(actor_text)
    accepted = bool(
        preflight_ok and scope_ok and token_ok and acknowledgements_ok and actor_ok
    )

    payload = {
        "preflight_digest": preflight_digest,
        "actor": actor_text,
        "current_scope": current_scope,
        "current_tenant_ids": sorted(current_tenants),
        "proposed_scope": next_scope,
        "proposed_tenant_ids": sorted(next_tenants),
        "acknowledgements": {
            name: True for name in EXPANSION_ACKNOWLEDGEMENTS
        },
    } if accepted else {}

    return {
        "schema": "ATLASQUANT_AION_BUSINESS_SCOPE_EXPANSION_AUTHORIZATION_RECORD_V1",
        "state": (
            "SCOPE_EXPANSION_AUTHORIZATION_RECORDED"
            if accepted
            else "BLOCKED"
        ),
        "authorization_recorded": accepted,
        "authorization_digest": _digest(payload) if payload else "",
        "preflight_digest": preflight_digest if accepted else "",
        "actor": actor_text if accepted else "",
        "current_scope": current_scope if accepted else "",
        "current_tenant_ids": current_tenants if accepted else [],
        "proposed_scope": next_scope if accepted else "",
        "proposed_tenant_ids": next_tenants if accepted else [],
        "scope_expansion_authorized": accepted,
        "expansion_execution_authorized": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def expansion_execution_review_packet(
    authorization: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(authorization)
    digest = _clean(row.get("authorization_digest"), 128).lower()
    current_scope = _clean(row.get("current_scope"), 80).lower()
    next_scope = _clean(row.get("proposed_scope"), 80).lower()
    current_tenants = _tenant_ids(row.get("current_tenant_ids"))
    next_tenants = _tenant_ids(row.get("proposed_tenant_ids"))

    current_rank = _scope_rank(current_scope)
    next_rank = _scope_rank(next_scope)
    scope_ok = bool(
        next_scope in {"pilot", "bounded_production"}
        and 1 <= len(next_tenants) <= MAX_BOUNDED_TENANTS
        and set(current_tenants).issubset(set(next_tenants))
        and next_rank in {current_rank, current_rank + 1}
        and (
            next_rank == current_rank + 1
            or len(next_tenants) > len(current_tenants)
        )
    )

    ready = bool(
        row.get("schema")
        == "ATLASQUANT_AION_BUSINESS_SCOPE_EXPANSION_AUTHORIZATION_RECORD_V1"
        and row.get("state") == "SCOPE_EXPANSION_AUTHORIZATION_RECORDED"
        and row.get("authorization_recorded") is True
        and row.get("scope_expansion_authorized") is True
        and row.get("expansion_execution_authorized") is False
        and row.get("automatic_expansion_allowed") is False
        and _DIGEST64.fullmatch(digest)
        and scope_ok
        and row.get("client_actions_authorized") is False
        and row.get("billing_authorized") is False
        and row.get("executes_action") is False
    )

    return {
        "schema": "ATLASQUANT_AION_BUSINESS_SCOPE_EXPANSION_EXECUTION_REVIEW_V1",
        "state": (
            "SCOPE_EXPANSION_EXECUTION_REVIEW_REQUIRED"
            if ready
            else "NOT_READY"
        ),
        "authorization_digest": digest if ready else "",
        "current_scope": current_scope if ready else "",
        "current_tenant_ids": current_tenants if ready else [],
        "proposed_scope": next_scope if ready else "",
        "proposed_tenant_ids": next_tenants if ready else [],
        "required_post_expansion_checks": (
            list(REQUIRED_POST_EXPANSION_CHECKS) if ready else []
        ),
        "expansion_execution_authorized": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "REQUIRED_EXPANSION_DECISION_TOKEN",
    "MAX_BOUNDED_TENANTS",
    "ALLOWED_SCOPES",
    "EXPANSION_ACKNOWLEDGEMENTS",
    "REQUIRED_POST_EXPANSION_CHECKS",
    "expansion_authorization_requirements",
    "expansion_preflight",
    "record_expansion_authorization",
    "expansion_execution_review_packet",
]
