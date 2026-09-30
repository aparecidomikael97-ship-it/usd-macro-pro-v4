"""AION BUSINESS deploy verification and runtime boundary V1.

Defines the administrative contracts around a future deploy. The module can
record an explicit deploy-only authorization, build a non-executing deployment
preflight, verify a separately executed deployment receipt, and prepare a
separate runtime decision request.

It never performs deploy, rollback, traffic switch, publication, billing,
client contact or runtime activation.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json
import re

DEPLOY_REQUEST_SCHEMA = "ATLASQUANT_AION_BUSINESS_DEPLOY_DECISION_REQUEST_V1"

SCHEMA = "ATLASQUANT_AION_BUSINESS_DEPLOY_VERIFICATION_RUNTIME_BOUNDARY_V1"
VERSION = "1"

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_DEPLOY_DECISION_TOKEN = "AUTHORIZE_BUSINESS_DEPLOY_ONLY"
REQUIRED_RUNTIME_DECISION_TOKEN = "AUTHORIZE_BUSINESS_RUNTIME_ACTIVATION"

DEPLOY_ACKNOWLEDGEMENTS = (
    "deploy_does_not_activate_business_runtime",
    "business_runtime_remains_off_after_deploy",
    "runtime_activation_requires_separate_explicit_decision",
    "rollback_reference_is_available",
    "monitoring_plan_is_available",
    "no_real_client_action_is_implied",
)

REQUIRED_DEPLOY_HEALTH_CHECKS = (
    "application_health",
    "ui_smoke",
    "mobile_dom",
    "observability",
    "rollback_ready",
)

RUNTIME_BOUNDARY_ACKNOWLEDGEMENTS = (
    "deploy_is_verified_before_runtime_review",
    "runtime_activation_is_separate_from_deploy",
    "runtime_scope_must_be_explicit",
    "pilot_or_client_scope_must_be_explicit",
    "rollback_and_monitoring_must_remain_available",
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


def deploy_authorization_requirements() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "EXPLICIT_DEPLOY_DECISION_REQUIRED",
        "required_decision_token": REQUIRED_DEPLOY_DECISION_TOKEN,
        "required_acknowledgements": list(DEPLOY_ACKNOWLEDGEMENTS),
        "generic_confirmation_is_authorization": False,
        "deploy_authorized": False,
        "deploy_executed": False,
        "runtime_activation_authorized": False,
        "runtime_activated": False,
        "executes_action": False,
    }


def record_deploy_authorization(
    request: Mapping[str, Any] | None,
    *,
    decision_token: Any,
    acknowledgements: Mapping[str, Any] | None,
    actor: Any,
) -> dict[str, Any]:
    row = _mapping(request)
    ack = _mapping(acknowledgements)
    token = _clean(decision_token, 120)
    actor_text = _clean(actor, 120)
    handoff_digest = _clean(row.get("handoff_digest"), 128).lower()
    final_main_sha = _clean(row.get("final_main_sha"), 80).lower()
    rollback_sha = _clean(row.get("rollback_reference_sha"), 80).lower()
    environment = _clean(row.get("target_environment"), 80).lower()

    request_ok = bool(
        row.get("schema") == DEPLOY_REQUEST_SCHEMA
        and row.get("state") == "EXPLICIT_DEPLOY_DECISION_REQUIRED"
        and row.get("required_decision_token") == REQUIRED_DEPLOY_DECISION_TOKEN
        and row.get("generic_confirmation_is_authorization") is False
        and row.get("deploy_authorized") is False
        and row.get("runtime_activation_authorized") is False
        and _DIGEST64.fullmatch(handoff_digest)
        and _SHA40.fullmatch(final_main_sha)
        and _SHA40.fullmatch(rollback_sha)
        and environment in {"staging", "production"}
    )
    token_ok = token == REQUIRED_DEPLOY_DECISION_TOKEN
    acknowledgements_ok = bool(
        all(ack.get(name) is True for name in DEPLOY_ACKNOWLEDGEMENTS)
    )
    actor_ok = bool(actor_text)
    accepted = bool(request_ok and token_ok and acknowledgements_ok and actor_ok)

    payload = {
        "handoff_digest": handoff_digest,
        "final_main_sha": final_main_sha,
        "rollback_reference_sha": rollback_sha,
        "target_environment": environment,
        "actor": actor_text,
        "acknowledgements": {name: True for name in DEPLOY_ACKNOWLEDGEMENTS},
    } if accepted else {}

    return {
        "schema": "ATLASQUANT_AION_BUSINESS_DEPLOY_AUTHORIZATION_RECORD_V1",
        "state": "DEPLOY_AUTHORIZATION_RECORDED" if accepted else "BLOCKED",
        "deploy_authorization_recorded": accepted,
        "authorization_digest": _digest(payload) if payload else "",
        "handoff_digest": handoff_digest if accepted else "",
        "final_main_sha": final_main_sha if accepted else "",
        "rollback_reference_sha": rollback_sha if accepted else "",
        "target_environment": environment if accepted else "",
        "actor": actor_text if accepted else "",
        "deploy_execution_authorized": accepted,
        "deploy_executed": False,
        "runtime_activation_authorized": False,
        "runtime_activated": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


def deployment_preflight(
    authorization: Mapping[str, Any] | None,
    *,
    deployment_plan_ref: Any,
    monitoring_plan_ref: Any,
    business_runtime_off: Any,
    current_main_sha: Any,
) -> dict[str, Any]:
    row = _mapping(authorization)
    auth_digest = _clean(row.get("authorization_digest"), 128).lower()
    expected_sha = _clean(row.get("final_main_sha"), 80).lower()
    current_sha = _clean(current_main_sha, 80).lower()
    rollback_sha = _clean(row.get("rollback_reference_sha"), 80).lower()
    deployment_ref = _clean(deployment_plan_ref, 300)
    monitoring_ref = _clean(monitoring_plan_ref, 300)

    auth_ok = bool(
        row.get("state") == "DEPLOY_AUTHORIZATION_RECORDED"
        and row.get("deploy_authorization_recorded") is True
        and row.get("deploy_execution_authorized") is True
        and row.get("deploy_executed") is False
        and row.get("runtime_activation_authorized") is False
        and row.get("executes_action") is False
        and _DIGEST64.fullmatch(auth_digest)
    )
    main_ok = bool(
        _SHA40.fullmatch(expected_sha)
        and _SHA40.fullmatch(current_sha)
        and current_sha == expected_sha
    )
    rollback_ok = bool(
        _SHA40.fullmatch(rollback_sha)
        and rollback_sha != expected_sha
    )
    runtime_ok = type(business_runtime_off) is bool and business_runtime_off is True
    deployment_ref_ok = bool(deployment_ref)
    monitoring_ok = bool(monitoring_ref)

    gates = {
        "deploy_authorization_recorded": auth_ok,
        "main_sha_matches_authorized_sha": main_ok,
        "rollback_reference_valid": rollback_ok,
        "deployment_plan_present": deployment_ref_ok,
        "monitoring_plan_present": monitoring_ok,
        "business_runtime_off": runtime_ok,
    }
    blockers = [name for name, passed in gates.items() if not passed]
    state = "DEPLOY_EXECUTION_REVIEW_REQUIRED" if not blockers else "DEPLOY_PREFLIGHT_BLOCKED"

    payload = {
        "authorization_digest": auth_digest,
        "expected_main_sha": expected_sha,
        "rollback_reference_sha": rollback_sha,
        "target_environment": _clean(row.get("target_environment"), 80).lower(),
        "deployment_plan_ref": deployment_ref,
        "monitoring_plan_ref": monitoring_ref,
        "business_runtime_off": runtime_ok,
    } if state == "DEPLOY_EXECUTION_REVIEW_REQUIRED" else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "gates": gates,
        "blockers": blockers,
        "preflight_digest": _digest(payload) if payload else "",
        "expected_main_sha": expected_sha if main_ok else "",
        "rollback_reference_sha": rollback_sha if rollback_ok else "",
        "target_environment": _clean(row.get("target_environment"), 80).lower() if auth_ok else "",
        "deployment_plan_ref": deployment_ref if deployment_ref_ok else "",
        "monitoring_plan_ref": monitoring_ref if monitoring_ok else "",
        "deploy_execution_authorized": False,
        "deploy_executed": False,
        "runtime_activation_authorized": False,
        "runtime_activated": False,
        "executes_action": False,
    }


def deployment_verification_template() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "DEPLOY_RECEIPT_REQUIRED",
        "required_health_checks": list(REQUIRED_DEPLOY_HEALTH_CHECKS),
        "deploy_verified": False,
        "runtime_decision_required_separately": True,
        "runtime_activation_authorized": False,
        "runtime_activated": False,
        "executes_action": False,
    }


def verify_deployment_receipt(
    preflight: Mapping[str, Any] | None,
    *,
    deployed_sha: Any,
    deployed_environment: Any,
    health_checks: Mapping[str, Any] | None,
    business_runtime_off_after_deploy: Any,
    deploy_evidence_ref: Any,
) -> dict[str, Any]:
    row = _mapping(preflight)
    checks = _mapping(health_checks)
    preflight_digest = _clean(row.get("preflight_digest"), 128).lower()
    expected_sha = _clean(row.get("expected_main_sha"), 80).lower()
    deployed = _clean(deployed_sha, 80).lower()
    expected_env = _clean(row.get("target_environment"), 80).lower()
    observed_env = _clean(deployed_environment, 80).lower()
    evidence_ref = _clean(deploy_evidence_ref, 300)

    preflight_ok = bool(
        row.get("schema") == SCHEMA
        and row.get("state") == "DEPLOY_EXECUTION_REVIEW_REQUIRED"
        and _DIGEST64.fullmatch(preflight_digest)
        and _SHA40.fullmatch(expected_sha)
        and row.get("deploy_execution_authorized") is False
        and row.get("runtime_activation_authorized") is False
        and row.get("executes_action") is False
    )
    sha_ok = bool(_SHA40.fullmatch(deployed) and deployed == expected_sha)
    environment_ok = bool(expected_env and observed_env == expected_env)
    normalized_checks = {
        name: _clean(checks.get(name), 40).lower()
        for name in REQUIRED_DEPLOY_HEALTH_CHECKS
    }
    checks_ok = bool(
        checks
        and all(value == "success" for value in normalized_checks.values())
    )
    runtime_off_ok = (
        type(business_runtime_off_after_deploy) is bool
        and business_runtime_off_after_deploy is True
    )
    evidence_ok = bool(evidence_ref)

    gates = {
        "preflight_valid": preflight_ok,
        "deployed_sha_matches_authorized_main": sha_ok,
        "environment_matches_target": environment_ok,
        "all_deploy_health_checks_success": checks_ok,
        "business_runtime_off_after_deploy": runtime_off_ok,
        "deploy_evidence_reference_present": evidence_ok,
    }
    blockers = [name for name, passed in gates.items() if not passed]

    evidence_supplied = bool(
        preflight
        or deployed
        or observed_env
        or checks
        or business_runtime_off_after_deploy is not None
        or evidence_ref
    )
    if not evidence_supplied:
        state = "DEPLOY_RECEIPT_REQUIRED"
    elif blockers:
        state = "DEPLOY_VERIFICATION_BLOCKED"
    else:
        state = "DEPLOY_VERIFIED_RUNTIME_DECISION_SEPARATE"

    payload = {
        "preflight_digest": preflight_digest,
        "deployed_sha": deployed,
        "deployed_environment": observed_env,
        "health_checks": normalized_checks,
        "business_runtime_off_after_deploy": runtime_off_ok,
        "deploy_evidence_ref": evidence_ref,
    } if state == "DEPLOY_VERIFIED_RUNTIME_DECISION_SEPARATE" else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "gates": gates,
        "blockers": blockers,
        "deployed_sha": deployed if sha_ok else "",
        "deployed_environment": observed_env if environment_ok else "",
        "health_checks": normalized_checks,
        "deployment_verification_digest": _digest(payload) if payload else "",
        "deploy_verified": state == "DEPLOY_VERIFIED_RUNTIME_DECISION_SEPARATE",
        "runtime_decision_required_separately": True,
        "runtime_activation_authorized": False,
        "runtime_activated": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


def runtime_boundary_packet(
    verification: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(verification)
    digest = _clean(row.get("deployment_verification_digest"), 128).lower()
    deployed_sha = _clean(row.get("deployed_sha"), 80).lower()
    ready = bool(
        row.get("schema") == SCHEMA
        and row.get("state") == "DEPLOY_VERIFIED_RUNTIME_DECISION_SEPARATE"
        and row.get("deploy_verified") is True
        and row.get("runtime_decision_required_separately") is True
        and _DIGEST64.fullmatch(digest)
        and _SHA40.fullmatch(deployed_sha)
        and row.get("runtime_activation_authorized") is False
        and row.get("runtime_activated") is False
        and row.get("executes_action") is False
    )
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_RUNTIME_BOUNDARY_PACKET_V1",
        "state": "EXPLICIT_RUNTIME_DECISION_REQUIRED" if ready else "NOT_READY",
        "deployment_verification_digest": digest if ready else "",
        "deployed_sha": deployed_sha if ready else "",
        "deployed_environment": _clean(row.get("deployed_environment"), 80) if ready else "",
        "required_decision_token": REQUIRED_RUNTIME_DECISION_TOKEN if ready else "",
        "required_acknowledgements": list(RUNTIME_BOUNDARY_ACKNOWLEDGEMENTS) if ready else [],
        "generic_confirmation_is_authorization": False,
        "runtime_activation_authorized": False,
        "runtime_activated": False,
        "pilot_authorized": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "REQUIRED_DEPLOY_DECISION_TOKEN",
    "REQUIRED_RUNTIME_DECISION_TOKEN",
    "DEPLOY_ACKNOWLEDGEMENTS",
    "REQUIRED_DEPLOY_HEALTH_CHECKS",
    "RUNTIME_BOUNDARY_ACKNOWLEDGEMENTS",
    "deploy_authorization_requirements",
    "record_deploy_authorization",
    "deployment_preflight",
    "deployment_verification_template",
    "verify_deployment_receipt",
    "runtime_boundary_packet",
]
