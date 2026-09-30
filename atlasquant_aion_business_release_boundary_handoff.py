"""AION BUSINESS release-boundary handoff V1.

Builds a read-only handoff dossier after the technical consolidation has been
explicitly acknowledged. The dossier exists only to prepare a separate deploy
decision. It never deploys and never activates BUSINESS runtime.

The boundary is intentionally strict:
technical consolidation acknowledgement != deploy authorization != runtime
activation authorization.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json
import re

COMPLETION_ACK_SCHEMA = "ATLASQUANT_AION_BUSINESS_FINAL_ADMIN_ACKNOWLEDGEMENT_V1"

SCHEMA = "ATLASQUANT_AION_BUSINESS_RELEASE_BOUNDARY_HANDOFF_V1"
VERSION = "1"

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_HANDOFF_ITEMS = (
    "technical_consolidation_acknowledged",
    "final_main_sha_bound",
    "completion_ack_digest_bound",
    "target_environment_named",
    "deployment_plan_reference_present",
    "rollback_reference_present",
    "monitoring_plan_reference_present",
    "business_runtime_off_before_deploy",
    "runtime_decision_separate",
)

DEPLOY_ACKNOWLEDGEMENTS = (
    "deploy_does_not_activate_business_runtime",
    "business_runtime_remains_off_after_deploy",
    "runtime_activation_requires_separate_explicit_decision",
    "rollback_reference_is_available",
    "monitoring_plan_is_available",
    "no_real_client_action_is_implied",
)

REQUIRED_DEPLOY_DECISION_TOKEN = "AUTHORIZE_BUSINESS_DEPLOY_ONLY"


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


def release_handoff_template() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TECHNICAL_ACKNOWLEDGEMENT_REQUIRED",
        "required_items": list(REQUIRED_HANDOFF_ITEMS),
        "required_deploy_decision_token": REQUIRED_DEPLOY_DECISION_TOKEN,
        "deploy_acknowledgements": list(DEPLOY_ACKNOWLEDGEMENTS),
        "ready_for_deploy_decision_review": False,
        "deploy_authorized": False,
        "deploy_executed": False,
        "runtime_activation_authorized": False,
        "runtime_activated": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


def build_release_handoff(
    acknowledgement: Mapping[str, Any] | None,
    *,
    target_environment: Any,
    deployment_plan_ref: Any,
    rollback_reference_sha: Any,
    monitoring_plan_ref: Any,
    business_runtime_off: Any,
    runtime_decision_separate: Any,
) -> dict[str, Any]:
    ack = _mapping(acknowledgement)
    ack_digest = _clean(ack.get("acknowledgement_digest"), 128).lower()
    final_main_sha = _clean(ack.get("final_main_sha"), 80).lower()
    environment = _clean(target_environment, 80).lower()
    deployment_ref = _clean(deployment_plan_ref, 300)
    rollback_sha = _clean(rollback_reference_sha, 80).lower()
    monitoring_ref = _clean(monitoring_plan_ref, 300)

    technical_ack_ok = bool(
        ack.get("schema") == COMPLETION_ACK_SCHEMA
        and ack.get("state") == "TECHNICAL_CONSOLIDATION_ACKNOWLEDGED"
        and ack.get("technical_consolidation_complete") is True
        and ack.get("deploy_decision_required_separately") is True
        and ack.get("deploy_authorized") is False
        and ack.get("runtime_activation_authorized") is False
        and ack.get("executes_action") is False
        and _DIGEST64.fullmatch(ack_digest)
    )
    main_sha_ok = bool(_SHA40.fullmatch(final_main_sha))
    environment_ok = environment in {"staging", "production"}
    deployment_ref_ok = bool(deployment_ref)
    rollback_ok = bool(_SHA40.fullmatch(rollback_sha))
    monitoring_ok = bool(monitoring_ref)
    runtime_off_ok = type(business_runtime_off) is bool and business_runtime_off is True
    runtime_separate_ok = (
        type(runtime_decision_separate) is bool and runtime_decision_separate is True
    )

    requirements = {
        "technical_consolidation_acknowledged": technical_ack_ok,
        "final_main_sha_bound": main_sha_ok,
        "completion_ack_digest_bound": bool(_DIGEST64.fullmatch(ack_digest)),
        "target_environment_named": environment_ok,
        "deployment_plan_reference_present": deployment_ref_ok,
        "rollback_reference_present": rollback_ok,
        "monitoring_plan_reference_present": monitoring_ok,
        "business_runtime_off_before_deploy": runtime_off_ok,
        "runtime_decision_separate": runtime_separate_ok,
    }
    blockers = [name for name, passed in requirements.items() if not passed]

    if not acknowledgement:
        state = "TECHNICAL_ACKNOWLEDGEMENT_REQUIRED"
    elif blockers:
        state = "HANDOFF_BLOCKED"
    else:
        state = "READY_FOR_SEPARATE_DEPLOY_DECISION"

    payload = {
        "acknowledgement_digest": ack_digest,
        "final_main_sha": final_main_sha,
        "target_environment": environment,
        "deployment_plan_ref": deployment_ref,
        "rollback_reference_sha": rollback_sha,
        "monitoring_plan_ref": monitoring_ref,
        "business_runtime_off": runtime_off_ok,
        "runtime_decision_separate": runtime_separate_ok,
    } if state == "READY_FOR_SEPARATE_DEPLOY_DECISION" else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "requirements": requirements,
        "blockers": blockers,
        "acknowledgement_digest": ack_digest if technical_ack_ok else "",
        "final_main_sha": final_main_sha if main_sha_ok else "",
        "target_environment": environment if environment_ok else "",
        "deployment_plan_ref": deployment_ref if deployment_ref_ok else "",
        "rollback_reference_sha": rollback_sha if rollback_ok else "",
        "monitoring_plan_ref": monitoring_ref if monitoring_ok else "",
        "handoff_digest": _digest(payload) if payload else "",
        "ready_for_deploy_decision_review": state == "READY_FOR_SEPARATE_DEPLOY_DECISION",
        "deploy_authorized": False,
        "deploy_executed": False,
        "runtime_activation_authorized": False,
        "runtime_activated": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


def deploy_decision_request(
    handoff: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(handoff)
    digest = _clean(row.get("handoff_digest"), 128).lower()
    final_main_sha = _clean(row.get("final_main_sha"), 80).lower()
    rollback_sha = _clean(row.get("rollback_reference_sha"), 80).lower()

    ready = bool(
        row.get("schema") == SCHEMA
        and row.get("state") == "READY_FOR_SEPARATE_DEPLOY_DECISION"
        and row.get("ready_for_deploy_decision_review") is True
        and _DIGEST64.fullmatch(digest)
        and _SHA40.fullmatch(final_main_sha)
        and _SHA40.fullmatch(rollback_sha)
        and row.get("deploy_authorized") is False
        and row.get("runtime_activation_authorized") is False
        and row.get("executes_action") is False
    )

    return {
        "schema": "ATLASQUANT_AION_BUSINESS_DEPLOY_DECISION_REQUEST_V1",
        "state": "EXPLICIT_DEPLOY_DECISION_REQUIRED" if ready else "NOT_READY",
        "handoff_digest": digest if ready else "",
        "final_main_sha": final_main_sha if ready else "",
        "target_environment": _clean(row.get("target_environment"), 80) if ready else "",
        "rollback_reference_sha": rollback_sha if ready else "",
        "required_decision_token": REQUIRED_DEPLOY_DECISION_TOKEN if ready else "",
        "required_acknowledgements": list(DEPLOY_ACKNOWLEDGEMENTS) if ready else [],
        "generic_confirmation_is_authorization": False,
        "deploy_authorized": False,
        "deploy_executed": False,
        "runtime_activation_authorized": False,
        "runtime_activated": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "REQUIRED_HANDOFF_ITEMS",
    "DEPLOY_ACKNOWLEDGEMENTS",
    "REQUIRED_DEPLOY_DECISION_TOKEN",
    "release_handoff_template",
    "build_release_handoff",
    "deploy_decision_request",
]
