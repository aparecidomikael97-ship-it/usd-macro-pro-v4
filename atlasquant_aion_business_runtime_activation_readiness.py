"""AION BUSINESS runtime activation readiness V1.

Administrative, fail-closed contracts for a future BUSINESS runtime activation.
The module accepts only evidence from a verified deployment boundary, validates a
bounded activation scope, records an explicit human authorization, and prepares
an execution-review packet.

It never activates runtime, changes feature flags, switches traffic, deploys,
publishes, bills, contacts clients, or calls external systems.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

BOUNDARY_SCHEMA = "ATLASQUANT_AION_BUSINESS_RUNTIME_BOUNDARY_PACKET_V1"
SCHEMA = "ATLASQUANT_AION_BUSINESS_RUNTIME_ACTIVATION_READINESS_V1"
VERSION = "1"

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_RUNTIME_DECISION_TOKEN = "AUTHORIZE_BUSINESS_RUNTIME_ACTIVATION"
ALLOWED_ACTIVATION_SCOPES = (
    "sandbox",
    "pilot",
    "bounded_production",
)
MAX_BOUNDED_TENANTS = 10

ACTIVATION_ACKNOWLEDGEMENTS = (
    "deploy_is_verified",
    "activation_scope_is_bounded",
    "monitoring_and_rollback_are_available",
    "privacy_and_tenant_isolation_are_required",
    "support_and_incident_response_are_required",
    "billing_and_client_actions_remain_separate",
    "automatic_expansion_is_forbidden",
)

REQUIRED_POST_ACTIVATION_CHECKS = (
    "application_health",
    "observability",
    "tenant_isolation",
    "privacy_guardrails",
    "support_readiness",
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
    normalized: list[str] = []
    for item in value:
        text = _clean(item, 120)
        if text and text not in normalized:
            normalized.append(text)
        if len(normalized) > MAX_BOUNDED_TENANTS:
            break
    return normalized


def activation_authorization_requirements() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "EXPLICIT_RUNTIME_DECISION_REQUIRED",
        "required_decision_token": REQUIRED_RUNTIME_DECISION_TOKEN,
        "allowed_activation_scopes": list(ALLOWED_ACTIVATION_SCOPES),
        "required_acknowledgements": list(ACTIVATION_ACKNOWLEDGEMENTS),
        "max_bounded_tenants": MAX_BOUNDED_TENANTS,
        "generic_confirmation_is_authorization": False,
        "runtime_activation_authorized": False,
        "activation_execution_authorized": False,
        "runtime_activated": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def runtime_activation_preflight(
    boundary_packet: Mapping[str, Any] | None,
    *,
    target_scope: Any,
    target_tenant_ids: Any,
    monitoring_plan_ref: Any,
    rollback_plan_ref: Any,
    privacy_ready: Any,
    support_ready: Any,
    finance_guardrails_ready: Any,
    integrations_healthy: Any,
) -> dict[str, Any]:
    row = _mapping(boundary_packet)
    scope = _clean(target_scope, 80).lower()
    tenants = _tenant_ids(target_tenant_ids)
    deployment_digest = _clean(
        row.get("deployment_verification_digest"), 128
    ).lower()
    deployed_sha = _clean(row.get("deployed_sha"), 80).lower()
    monitoring_ref = _clean(monitoring_plan_ref, 300)
    rollback_ref = _clean(rollback_plan_ref, 300)

    boundary_ok = bool(
        row.get("schema") == BOUNDARY_SCHEMA
        and row.get("state") == "EXPLICIT_RUNTIME_DECISION_REQUIRED"
        and row.get("required_decision_token") == REQUIRED_RUNTIME_DECISION_TOKEN
        and row.get("generic_confirmation_is_authorization") is False
        and _DIGEST64.fullmatch(deployment_digest)
        and _SHA40.fullmatch(deployed_sha)
        and row.get("runtime_activation_authorized") is False
        and row.get("runtime_activated") is False
        and row.get("pilot_authorized") is False
        and row.get("client_actions_authorized") is False
        and row.get("executes_action") is False
    )
    scope_ok = scope in ALLOWED_ACTIVATION_SCOPES
    tenant_scope_ok = bool(
        (scope == "sandbox" and not tenants)
        or (
            scope in {"pilot", "bounded_production"}
            and 1 <= len(tenants) <= MAX_BOUNDED_TENANTS
        )
    )
    monitoring_ok = bool(monitoring_ref)
    rollback_ok = bool(rollback_ref)
    privacy_ok = type(privacy_ready) is bool and privacy_ready is True
    support_ok = type(support_ready) is bool and support_ready is True
    finance_ok = (
        type(finance_guardrails_ready) is bool
        and finance_guardrails_ready is True
    )
    integrations_ok = (
        type(integrations_healthy) is bool and integrations_healthy is True
    )

    gates = {
        "verified_deploy_boundary": boundary_ok,
        "activation_scope_allowed": scope_ok,
        "tenant_scope_bounded": tenant_scope_ok,
        "monitoring_plan_present": monitoring_ok,
        "rollback_plan_present": rollback_ok,
        "privacy_ready": privacy_ok,
        "support_ready": support_ok,
        "finance_guardrails_ready": finance_ok,
        "integrations_healthy": integrations_ok,
    }
    blockers = [name for name, passed in gates.items() if not passed]
    state = (
        "READY_FOR_EXPLICIT_RUNTIME_AUTHORIZATION"
        if not blockers
        else "RUNTIME_ACTIVATION_PREFLIGHT_BLOCKED"
    )

    payload = {
        "deployment_verification_digest": deployment_digest,
        "deployed_sha": deployed_sha,
        "deployed_environment": _clean(row.get("deployed_environment"), 80),
        "target_scope": scope,
        "target_tenant_ids": tenants,
        "monitoring_plan_ref": monitoring_ref,
        "rollback_plan_ref": rollback_ref,
    } if state == "READY_FOR_EXPLICIT_RUNTIME_AUTHORIZATION" else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "gates": gates,
        "blockers": blockers,
        "preflight_digest": _digest(payload) if payload else "",
        "deployment_verification_digest": deployment_digest if boundary_ok else "",
        "deployed_sha": deployed_sha if boundary_ok else "",
        "deployed_environment": (
            _clean(row.get("deployed_environment"), 80) if boundary_ok else ""
        ),
        "target_scope": scope if scope_ok else "",
        "target_tenant_ids": tenants if tenant_scope_ok else [],
        "monitoring_plan_ref": monitoring_ref if monitoring_ok else "",
        "rollback_plan_ref": rollback_ref if rollback_ok else "",
        "required_decision_token": (
            REQUIRED_RUNTIME_DECISION_TOKEN
            if state == "READY_FOR_EXPLICIT_RUNTIME_AUTHORIZATION"
            else ""
        ),
        "required_acknowledgements": (
            list(ACTIVATION_ACKNOWLEDGEMENTS)
            if state == "READY_FOR_EXPLICIT_RUNTIME_AUTHORIZATION"
            else []
        ),
        "generic_confirmation_is_authorization": False,
        "runtime_activation_authorized": False,
        "activation_execution_authorized": False,
        "runtime_activated": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def record_runtime_activation_authorization(
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
    scope = _clean(row.get("target_scope"), 80).lower()
    tenants = _tenant_ids(row.get("target_tenant_ids"))

    preflight_ok = bool(
        row.get("schema") == SCHEMA
        and row.get("state") == "READY_FOR_EXPLICIT_RUNTIME_AUTHORIZATION"
        and _DIGEST64.fullmatch(preflight_digest)
        and row.get("required_decision_token") == REQUIRED_RUNTIME_DECISION_TOKEN
        and row.get("generic_confirmation_is_authorization") is False
        and row.get("runtime_activation_authorized") is False
        and row.get("activation_execution_authorized") is False
        and row.get("runtime_activated") is False
        and row.get("executes_action") is False
    )
    scope_ok = bool(
        scope in ALLOWED_ACTIVATION_SCOPES
        and (
            (scope == "sandbox" and not tenants)
            or (
                scope in {"pilot", "bounded_production"}
                and 1 <= len(tenants) <= MAX_BOUNDED_TENANTS
            )
        )
    )
    token_ok = token == REQUIRED_RUNTIME_DECISION_TOKEN
    acknowledgements_ok = bool(
        all(ack.get(name) is True for name in ACTIVATION_ACKNOWLEDGEMENTS)
    )
    actor_ok = bool(actor_text)
    accepted = bool(
        preflight_ok and scope_ok and token_ok and acknowledgements_ok and actor_ok
    )

    payload = {
        "preflight_digest": preflight_digest,
        "actor": actor_text,
        "target_scope": scope,
        "target_tenant_ids": tenants,
        "acknowledgements": {
            name: True for name in ACTIVATION_ACKNOWLEDGEMENTS
        },
    } if accepted else {}

    return {
        "schema": "ATLASQUANT_AION_BUSINESS_RUNTIME_ACTIVATION_AUTHORIZATION_RECORD_V1",
        "state": (
            "RUNTIME_ACTIVATION_AUTHORIZATION_RECORDED"
            if accepted
            else "BLOCKED"
        ),
        "authorization_recorded": accepted,
        "authorization_digest": _digest(payload) if payload else "",
        "preflight_digest": preflight_digest if accepted else "",
        "actor": actor_text if accepted else "",
        "target_scope": scope if accepted else "",
        "target_tenant_ids": tenants if accepted else [],
        "runtime_activation_authorized": accepted,
        "activation_execution_authorized": False,
        "runtime_activated": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def runtime_activation_execution_review_packet(
    authorization: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(authorization)
    digest = _clean(row.get("authorization_digest"), 128).lower()
    scope = _clean(row.get("target_scope"), 80).lower()
    tenants = _tenant_ids(row.get("target_tenant_ids"))

    ready = bool(
        row.get("schema")
        == "ATLASQUANT_AION_BUSINESS_RUNTIME_ACTIVATION_AUTHORIZATION_RECORD_V1"
        and row.get("state") == "RUNTIME_ACTIVATION_AUTHORIZATION_RECORDED"
        and row.get("authorization_recorded") is True
        and row.get("runtime_activation_authorized") is True
        and row.get("activation_execution_authorized") is False
        and row.get("runtime_activated") is False
        and row.get("automatic_expansion_allowed") is False
        and _DIGEST64.fullmatch(digest)
        and scope in ALLOWED_ACTIVATION_SCOPES
        and row.get("executes_action") is False
    )
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_RUNTIME_ACTIVATION_EXECUTION_REVIEW_V1",
        "state": (
            "RUNTIME_ACTIVATION_EXECUTION_REVIEW_REQUIRED"
            if ready
            else "NOT_READY"
        ),
        "authorization_digest": digest if ready else "",
        "target_scope": scope if ready else "",
        "target_tenant_ids": tenants if ready else [],
        "required_post_activation_checks": (
            list(REQUIRED_POST_ACTIVATION_CHECKS) if ready else []
        ),
        "activation_execution_authorized": False,
        "runtime_activated": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def post_activation_verification_template() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "POST_ACTIVATION_EVIDENCE_REQUIRED",
        "required_checks": list(REQUIRED_POST_ACTIVATION_CHECKS),
        "automatic_expansion_allowed": False,
        "runtime_health_verified": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "REQUIRED_RUNTIME_DECISION_TOKEN",
    "ALLOWED_ACTIVATION_SCOPES",
    "MAX_BOUNDED_TENANTS",
    "ACTIVATION_ACKNOWLEDGEMENTS",
    "REQUIRED_POST_ACTIVATION_CHECKS",
    "activation_authorization_requirements",
    "runtime_activation_preflight",
    "record_runtime_activation_authorization",
    "runtime_activation_execution_review_packet",
    "post_activation_verification_template",
]
