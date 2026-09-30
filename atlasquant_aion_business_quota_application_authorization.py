"""AION BUSINESS quota application authorization boundary V1.

Administrative contracts for explicitly authorizing a reviewed capacity/quota
plan and preparing a non-executing application preflight.

This module never applies quotas, changes billing, runtime, tenants, traffic,
deploys, integrations, storage, AI limits, or external systems.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

REVIEW_SCHEMA = "ATLASQUANT_AION_BUSINESS_QUOTA_APPLICATION_REVIEW_V1"
SCHEMA = "ATLASQUANT_AION_BUSINESS_QUOTA_APPLICATION_AUTHORIZATION_V1"
VERSION = "1"

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")
MAX_BOUNDED_TENANTS = 10
REQUIRED_QUOTA_DECISION_TOKEN = "AUTHORIZE_BUSINESS_QUOTA_APPLICATION"

QUOTA_ACKNOWLEDGEMENTS = (
    "capacity_review_is_bound_to_exact_plan",
    "tenant_set_is_verified_and_frozen",
    "minimum_margin_and_capacity_reserve_were_reviewed",
    "monitoring_is_required_before_application",
    "rollback_or_restore_plan_is_required",
    "billing_changes_remain_separate",
    "automatic_quota_changes_are_forbidden",
    "client_actions_remain_separate",
)

REQUIRED_POST_APPLICATION_CHECKS = (
    "quota_values_match_authorized_plan",
    "tenant_set_unchanged",
    "application_health",
    "observability",
    "cost_guardrail",
    "margin_guardrail",
    "support_readiness",
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
        tenant = _clean(item, 120)
        if tenant and tenant not in result:
            result.append(tenant)
        if len(result) > MAX_BOUNDED_TENANTS:
            break
    return result


def quota_application_authorization_requirements() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "EXPLICIT_QUOTA_APPLICATION_DECISION_REQUIRED",
        "required_decision_token": REQUIRED_QUOTA_DECISION_TOKEN,
        "required_acknowledgements": list(QUOTA_ACKNOWLEDGEMENTS),
        "generic_confirmation_is_authorization": False,
        "quota_application_authorized": False,
        "quota_application_execution_authorized": False,
        "billing_authorized": False,
        "automatic_quota_changes_allowed": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


def record_quota_application_authorization(
    review_packet: Mapping[str, Any] | None,
    *,
    decision_token: Any,
    acknowledgements: Mapping[str, Any] | None,
    actor: Any,
) -> dict[str, Any]:
    row = _mapping(review_packet)
    ack = _mapping(acknowledgements)
    token = _clean(decision_token, 120)
    actor_text = _clean(actor, 120)
    capacity_review_digest = _clean(
        row.get("capacity_review_digest"), 128
    ).lower()
    tenants = _tenant_ids(row.get("tenant_ids"))

    packet_ok = bool(
        row.get("schema") == REVIEW_SCHEMA
        and row.get("state") == "QUOTA_APPLICATION_DECISION_REQUIRED"
        and _DIGEST64.fullmatch(capacity_review_digest)
        and 1 <= len(tenants) <= MAX_BOUNDED_TENANTS
        and len(set(tenants)) == len(tenants)
        and row.get("quota_application_authorized") is False
        and row.get("billing_authorized") is False
        and row.get("automatic_expansion_allowed") is False
        and row.get("client_actions_authorized") is False
        and row.get("executes_action") is False
    )
    token_ok = token == REQUIRED_QUOTA_DECISION_TOKEN
    acknowledgements_ok = bool(
        all(ack.get(name) is True for name in QUOTA_ACKNOWLEDGEMENTS)
    )
    actor_ok = bool(actor_text)
    accepted = bool(packet_ok and token_ok and acknowledgements_ok and actor_ok)

    payload = {
        "capacity_review_digest": capacity_review_digest,
        "tenant_ids": sorted(tenants),
        "actor": actor_text,
        "acknowledgements": {
            name: True for name in QUOTA_ACKNOWLEDGEMENTS
        },
    } if accepted else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "QUOTA_APPLICATION_AUTHORIZATION_RECORDED"
            if accepted
            else "BLOCKED"
        ),
        "authorization_recorded": accepted,
        "authorization_digest": _digest(payload) if payload else "",
        "capacity_review_digest": capacity_review_digest if accepted else "",
        "tenant_ids": tenants if accepted else [],
        "actor": actor_text if accepted else "",
        "quota_application_authorized": accepted,
        "quota_application_execution_authorized": False,
        "billing_authorized": False,
        "automatic_quota_changes_allowed": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


def quota_application_preflight(
    authorization: Mapping[str, Any] | None,
    *,
    change_window_ref: Any,
    monitoring_plan_ref: Any,
    rollback_plan_ref: Any,
    dry_run_verified: Any,
    support_ready: Any,
    incident_response_ready: Any,
) -> dict[str, Any]:
    row = _mapping(authorization)
    authorization_digest = _clean(row.get("authorization_digest"), 128).lower()
    capacity_review_digest = _clean(
        row.get("capacity_review_digest"), 128
    ).lower()
    tenants = _tenant_ids(row.get("tenant_ids"))
    change_window = _clean(change_window_ref, 300)
    monitoring = _clean(monitoring_plan_ref, 300)
    rollback = _clean(rollback_plan_ref, 300)

    authorization_ok = bool(
        row.get("schema") == SCHEMA
        and row.get("state") == "QUOTA_APPLICATION_AUTHORIZATION_RECORDED"
        and row.get("authorization_recorded") is True
        and row.get("quota_application_authorized") is True
        and row.get("quota_application_execution_authorized") is False
        and _DIGEST64.fullmatch(authorization_digest)
        and _DIGEST64.fullmatch(capacity_review_digest)
        and 1 <= len(tenants) <= MAX_BOUNDED_TENANTS
        and len(set(tenants)) == len(tenants)
        and row.get("billing_authorized") is False
        and row.get("automatic_quota_changes_allowed") is False
        and row.get("automatic_expansion_allowed") is False
        and row.get("client_actions_authorized") is False
        and row.get("executes_action") is False
    )

    gates = {
        "authorization_record_valid": authorization_ok,
        "change_window_present": bool(change_window),
        "monitoring_plan_present": bool(monitoring),
        "rollback_plan_present": bool(rollback),
        "dry_run_verified": type(dry_run_verified) is bool and dry_run_verified is True,
        "support_ready": type(support_ready) is bool and support_ready is True,
        "incident_response_ready": (
            type(incident_response_ready) is bool
            and incident_response_ready is True
        ),
    }
    blockers = [name for name, passed in gates.items() if not passed]
    state = (
        "QUOTA_APPLICATION_EXECUTION_REVIEW_REQUIRED"
        if not blockers
        else "QUOTA_APPLICATION_PREFLIGHT_BLOCKED"
    )

    payload = {
        "authorization_digest": authorization_digest,
        "capacity_review_digest": capacity_review_digest,
        "tenant_ids": sorted(tenants),
        "change_window_ref": change_window,
        "monitoring_plan_ref": monitoring,
        "rollback_plan_ref": rollback,
    } if state == "QUOTA_APPLICATION_EXECUTION_REVIEW_REQUIRED" else {}

    return {
        "schema": "ATLASQUANT_AION_BUSINESS_QUOTA_APPLICATION_PREFLIGHT_V1",
        "state": state,
        "gates": gates,
        "blockers": blockers,
        "preflight_digest": _digest(payload) if payload else "",
        "authorization_digest": authorization_digest if authorization_ok else "",
        "capacity_review_digest": capacity_review_digest if authorization_ok else "",
        "tenant_ids": tenants if authorization_ok else [],
        "change_window_ref": change_window if change_window else "",
        "monitoring_plan_ref": monitoring if monitoring else "",
        "rollback_plan_ref": rollback if rollback else "",
        "required_post_application_checks": (
            list(REQUIRED_POST_APPLICATION_CHECKS)
            if state == "QUOTA_APPLICATION_EXECUTION_REVIEW_REQUIRED"
            else []
        ),
        "quota_application_authorized": authorization_ok,
        "quota_application_execution_authorized": False,
        "billing_authorized": False,
        "automatic_quota_changes_allowed": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


def quota_application_execution_review_packet(
    preflight: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(preflight)
    digest = _clean(row.get("preflight_digest"), 128).lower()
    auth_digest = _clean(row.get("authorization_digest"), 128).lower()
    capacity_digest = _clean(row.get("capacity_review_digest"), 128).lower()
    tenants = _tenant_ids(row.get("tenant_ids"))

    ready = bool(
        row.get("schema") == "ATLASQUANT_AION_BUSINESS_QUOTA_APPLICATION_PREFLIGHT_V1"
        and row.get("state") == "QUOTA_APPLICATION_EXECUTION_REVIEW_REQUIRED"
        and _DIGEST64.fullmatch(digest)
        and _DIGEST64.fullmatch(auth_digest)
        and _DIGEST64.fullmatch(capacity_digest)
        and 1 <= len(tenants) <= MAX_BOUNDED_TENANTS
        and len(set(tenants)) == len(tenants)
        and bool(_clean(row.get("change_window_ref"), 300))
        and bool(_clean(row.get("monitoring_plan_ref"), 300))
        and bool(_clean(row.get("rollback_plan_ref"), 300))
        and row.get("quota_application_authorized") is True
        and row.get("quota_application_execution_authorized") is False
        and row.get("billing_authorized") is False
        and row.get("automatic_quota_changes_allowed") is False
        and row.get("automatic_expansion_allowed") is False
        and row.get("client_actions_authorized") is False
        and row.get("executes_action") is False
    )

    return {
        "schema": "ATLASQUANT_AION_BUSINESS_QUOTA_APPLICATION_EXECUTION_REVIEW_V1",
        "state": "QUOTA_APPLICATION_EXECUTION_REVIEW_REQUIRED" if ready else "NOT_READY",
        "preflight_digest": digest if ready else "",
        "authorization_digest": auth_digest if ready else "",
        "capacity_review_digest": capacity_digest if ready else "",
        "tenant_ids": tenants if ready else [],
        "required_post_application_checks": (
            list(REQUIRED_POST_APPLICATION_CHECKS) if ready else []
        ),
        "quota_application_execution_authorized": False,
        "billing_authorized": False,
        "automatic_quota_changes_allowed": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "REVIEW_SCHEMA",
    "MAX_BOUNDED_TENANTS",
    "REQUIRED_QUOTA_DECISION_TOKEN",
    "QUOTA_ACKNOWLEDGEMENTS",
    "REQUIRED_POST_APPLICATION_CHECKS",
    "quota_application_authorization_requirements",
    "record_quota_application_authorization",
    "quota_application_preflight",
    "quota_application_execution_review_packet",
]
