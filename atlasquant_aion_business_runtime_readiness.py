"""AION BUSINESS runtime readiness gate.

This module prepares a certified BUSINESS specialist for a future sandbox/runtime
decision without activating runtime. It is pure/offline and fail-closed.

Certification is necessary but not sufficient for runtime. Production runtime
requires a separate future approval gate and remains unavailable here.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

SCHEMA = "ATLASQUANT_AION_BUSINESS_RUNTIME_READINESS_V1"
VERSION = "1"
SPECIALIST = "BUSINESS"
CERTIFICATION_DECISION_SCHEMA = "ATLASQUANT_AION_BUSINESS_CERTIFICATION_DECISION_V1"
STATES = (
    "NOT_ELIGIBLE",
    "SANDBOX_READY",
    "RUNTIME_APPROVAL_REQUIRED",
)
_ALLOWED_SANDBOX_ACTIONS = ("read", "analyze", "draft")
_DENIED_ACTIONS = (
    "external_contact",
    "sign_contract",
    "charge",
    "payment",
    "spend",
    "publish",
    "publication",
    "deploy",
    "real_trade",
    "move_money",
)
_SHA = re.compile(r"^[0-9a-f]{40,64}$")
_FP = re.compile(r"^[0-9a-f]{64}$")


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _exact_true(value: Any) -> bool:
    return type(value) is bool and value is True


def _exact_false(value: Any) -> bool:
    return type(value) is bool and value is False


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Mapping[str, Any]) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def normalize_certification_decision(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    data = _mapping(raw)
    sha = _clean(data.get("reviewed_sha"), 80).lower()
    fp = _clean(data.get("evidence_fingerprint"), 128).lower()
    valid = bool(
        data.get("schema") == CERTIFICATION_DECISION_SCHEMA
        and _clean(data.get("specialist"), 40).upper() == SPECIALIST
        and data.get("state") == "CERTIFIED"
        and bool(_SHA.fullmatch(sha))
        and bool(_FP.fullmatch(fp))
        and _exact_true(data.get("human_review_verified"))
        and _exact_true(data.get("ci_evidence_verified"))
        and _exact_false(data.get("runtime_activated"))
        and _exact_false(data.get("merge_authorized"))
        and _exact_false(data.get("deploy_authorized"))
        and _exact_false(data.get("external_contact_authorized"))
        and _exact_false(data.get("contract_signature_authorized"))
        and _exact_false(data.get("payment_authorized"))
        and _exact_false(data.get("publication_authorized"))
        and _exact_false(data.get("spend_authorized"))
        and _exact_false(data.get("real_trading_authorized"))
    )
    return {
        "schema": CERTIFICATION_DECISION_SCHEMA,
        "specialist": SPECIALIST,
        "state": "CERTIFIED" if valid else "REJECTED",
        "valid": valid,
        "reviewed_sha": sha if valid else "",
        "evidence_fingerprint": fp if valid else "",
        "human_review_verified": valid,
        "ci_evidence_verified": valid,
        "runtime_activated": False,
    }


def business_sandbox_readiness(
    certification_decision: Mapping[str, Any] | None,
    *,
    expected_sha: Any,
    expected_fingerprint: Any,
    sandbox_isolated: Any,
    external_network_disabled: Any,
    payment_disabled: Any,
    publication_disabled: Any,
    deploy_disabled: Any,
    real_trading_disabled: Any,
    audit_enabled: Any,
    rollback_ready: Any,
    kill_switch_ready: Any,
) -> dict[str, Any]:
    cert = normalize_certification_decision(certification_decision)
    sha = _clean(expected_sha, 80).lower()
    fp = _clean(expected_fingerprint, 128).lower()

    gates = {
        "certification_valid": cert["valid"],
        "sha_bound": cert["reviewed_sha"] == sha and bool(_SHA.fullmatch(sha)),
        "fingerprint_bound": cert["evidence_fingerprint"] == fp and bool(_FP.fullmatch(fp)),
        "sandbox_isolated": _exact_true(sandbox_isolated),
        "external_network_disabled": _exact_true(external_network_disabled),
        "payment_disabled": _exact_true(payment_disabled),
        "publication_disabled": _exact_true(publication_disabled),
        "deploy_disabled": _exact_true(deploy_disabled),
        "real_trading_disabled": _exact_true(real_trading_disabled),
        "audit_enabled": _exact_true(audit_enabled),
        "rollback_ready": _exact_true(rollback_ready),
        "kill_switch_ready": _exact_true(kill_switch_ready),
    }
    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers
    plan = {
        "specialist": SPECIALIST,
        "mode": "SANDBOX_ONLY",
        "allowed_actions": list(_ALLOWED_SANDBOX_ACTIONS),
        "denied_actions": list(_DENIED_ACTIONS),
        "reviewed_sha": cert["reviewed_sha"],
        "evidence_fingerprint": cert["evidence_fingerprint"],
        "runtime_activation_requested": False,
        "runtime_activation_approved": False,
        "runtime_activated": False,
        "external_side_effects_allowed": False,
    }
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "SANDBOX_READY" if ready else "NOT_ELIGIBLE",
        "sandbox_ready": ready,
        "runtime_approval_required": ready,
        "production_runtime_allowed": False,
        "runtime_capability_available": False,
        "runtime_activated": False,
        "gates": gates,
        "blockers": blockers,
        "plan": plan,
        "plan_digest": _digest(plan) if ready else "",
        "provider_called": False,
        "external_write": False,
        "payment_executed": False,
        "publication_executed": False,
        "deploy_executed": False,
        "real_trading_enabled": False,
    }


def business_runtime_approval_packet(
    readiness: Mapping[str, Any] | None,
    *,
    requested_by: Any,
    reason: Any,
) -> dict[str, Any]:
    """Prepare, but never approve, a future runtime activation request."""
    row = _mapping(readiness)
    requester = _clean(requested_by, 120)
    why = _clean(reason, 500)
    eligible = bool(
        row.get("schema") == SCHEMA
        and row.get("state") == "SANDBOX_READY"
        and _exact_true(row.get("sandbox_ready"))
        and _exact_true(row.get("runtime_approval_required"))
        and _exact_false(row.get("production_runtime_allowed"))
        and _exact_false(row.get("runtime_activated"))
        and requester
        and why
        and _clean(row.get("plan_digest"), 128)
    )
    packet = {
        "schema": "ATLASQUANT_AION_BUSINESS_RUNTIME_APPROVAL_PACKET_V1",
        "specialist": SPECIALIST,
        "state": "RUNTIME_APPROVAL_REQUIRED" if eligible else "BLOCKED",
        "requested_by": requester if eligible else "",
        "reason": why if eligible else "",
        "sandbox_plan_digest": _clean(row.get("plan_digest"), 128) if eligible else "",
        "approval_scope": "RUNTIME_ACTIVATION_ONLY",
        "runtime_activation_approved": False,
        "runtime_activated": False,
        "external_actions_authorized": False,
        "payment_authorized": False,
        "publication_authorized": False,
        "deploy_authorized": False,
        "real_trading_authorized": False,
    }
    return {
        **packet,
        "packet_digest": _digest(packet) if eligible else "",
        "eligible_for_human_runtime_review": eligible,
    }


def business_runtime_posture(
    readiness: Mapping[str, Any] | None,
    approval_packet: Mapping[str, Any] | None,
) -> dict[str, Any]:
    ready = _mapping(readiness)
    packet = _mapping(approval_packet)
    awaiting = bool(
        ready.get("state") == "SANDBOX_READY"
        and packet.get("state") == "RUNTIME_APPROVAL_REQUIRED"
        and _exact_false(packet.get("runtime_activation_approved"))
    )
    return {
        "schema": SCHEMA,
        "specialist": SPECIALIST,
        "certification_state": "CERTIFIED" if ready.get("sandbox_ready") is True else "UNVERIFIED",
        "sandbox_state": ready.get("state") or "NOT_ELIGIBLE",
        "runtime_state": "RUNTIME_APPROVAL_REQUIRED" if awaiting else "OFF",
        "runtime_capability_available": False,
        "runtime_activated": False,
        "external_actions_enabled": False,
        "payment_enabled": False,
        "publication_enabled": False,
        "deploy_enabled": False,
        "real_trading_enabled": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "SPECIALIST",
    "CERTIFICATION_DECISION_SCHEMA",
    "STATES",
    "normalize_certification_decision",
    "business_sandbox_readiness",
    "business_runtime_approval_packet",
    "business_runtime_posture",
]
