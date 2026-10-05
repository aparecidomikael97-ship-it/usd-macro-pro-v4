"""AION B2B Pilot Activation Execution Persistence Plan V1.

Pure/offline Checkpoint Master patch planner for a verified activation-execution
decision.

It accepts only:
- ACTIVATION_EXECUTION_AUTHORIZATION_VERIFIED_PENDING_PERSISTENCE
- ACTIVATION_EXECUTION_DENIAL_VERIFIED_PENDING_PERSISTENCE

The module prepares a deterministic patch candidate but never calls
append_checkpoint_patch, never persists the execution record, never generates
an activation command, and never executes pilot activation.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json
import re

from atlasquant_aion_checkpoint_master import reconstruct_checkpoint

SCHEMA = "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_EXECUTION_PERSISTENCE_PLAN_V1"
EXECUTION_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_EXECUTION_VERIFICATION_V1"
PATCH_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_EXECUTION_CHECKPOINT_PATCH_V1"
NAMESPACE = "aion_b2b_pilot_activation_execution_authorization"

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, limit: int = 320) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _blocked(*items: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "blockers": sorted(set(items)),
        "patch_candidate": None,
        "execution_record_persisted": False,
        "checkpoint_saved": False,
        "automatic_checkpoint_write": False,
        "activation_command_generated": False,
        "activation_command_executed": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
    }


def build_activation_execution_persistence_plan(
    verified_execution: Mapping[str, Any] | None,
    *,
    checkpoint_master: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Prepare but never persist the activation-execution authorization record."""
    row = (
        dict(verified_execution)
        if isinstance(verified_execution, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != EXECUTION_SCHEMA:
        blockers.append("ACTIVATION_EXECUTION_SCHEMA_INVALID")
    if row.get("state") not in {
        "ACTIVATION_EXECUTION_AUTHORIZATION_VERIFIED_PENDING_PERSISTENCE",
        "ACTIVATION_EXECUTION_DENIAL_VERIFIED_PENDING_PERSISTENCE",
    }:
        blockers.append("ACTIVATION_EXECUTION_STATE_INVALID")
    if row.get("execution_decision_verified") is not True:
        blockers.append("ACTIVATION_EXECUTION_DECISION_NOT_VERIFIED")
    if row.get("owner_execution_identity_verified") is not True:
        blockers.append("ACTIVATION_EXECUTION_OWNER_IDENTITY_NOT_VERIFIED")
    if row.get("owner_execution_signature_verified") is not True:
        blockers.append("ACTIVATION_EXECUTION_SIGNATURE_NOT_VERIFIED")
    if row.get("execution_record_persisted") is not False:
        blockers.append("ACTIVATION_EXECUTION_RECORD_ALREADY_PERSISTED")
    if row.get("activation_command_generated") is not False:
        blockers.append("ACTIVATION_COMMAND_ALREADY_GENERATED")
    if row.get("activation_command_executed") is not False:
        blockers.append("ACTIVATION_COMMAND_ALREADY_EXECUTED")
    if row.get("pilot_activation_authorized") is not False:
        blockers.append("PILOT_ACTIVATION_ALREADY_AUTHORIZED")
    if row.get("pilot_activated") is not False:
        blockers.append("PILOT_ALREADY_ACTIVATED")
    if row.get("requires_execution_record_persistence") is not True:
        blockers.append("ACTIVATION_EXECUTION_PERSISTENCE_BOUNDARY_MISSING")

    for key in (
        "customer_contact_authorized",
        "billing_authorized",
        "provisioning_authorized",
        "deploy_authorized",
        "production_mutation_authorized",
        "external_action_executed",
        "network_called",
        "executes_action",
    ):
        if row.get(key) is not False:
            blockers.append("ACTIVATION_EXECUTION_UNSAFE_FIELD:" + key)

    decision = _text(row.get("execution_decision"), 80)
    if decision not in {
        "AUTHORIZE_ACTIVATION_EXECUTION",
        "DENY_ACTIVATION_EXECUTION",
    }:
        blockers.append("ACTIVATION_EXECUTION_DECISION_INVALID")

    authorize = row.get("execution_authorization_intent") is True
    deny = row.get("execution_denial_intent") is True
    if decision == "AUTHORIZE_ACTIVATION_EXECUTION" and (
        not authorize or deny
    ):
        blockers.append("ACTIVATION_EXECUTION_AUTHORIZE_FLAGS_INVALID")
    if decision == "DENY_ACTIVATION_EXECUTION" and (
        authorize or not deny
    ):
        blockers.append("ACTIVATION_EXECUTION_DENY_FLAGS_INVALID")

    record = (
        dict(row.get("execution_record"))
        if isinstance(row.get("execution_record"), Mapping)
        else {}
    )
    if not record:
        blockers.append("ACTIVATION_EXECUTION_RECORD_REQUIRED")
    else:
        if record.get("schema") != EXECUTION_SCHEMA:
            blockers.append("ACTIVATION_EXECUTION_RECORD_SCHEMA_INVALID")
        if record.get("decision") != decision:
            blockers.append("ACTIVATION_EXECUTION_RECORD_DECISION_MISMATCH")
        if record.get("execution_decision_verified") is not True:
            blockers.append("ACTIVATION_EXECUTION_RECORD_NOT_VERIFIED")
        if record.get("execution_record_persisted") is not False:
            blockers.append("ACTIVATION_EXECUTION_RECORD_ALREADY_PERSISTED")
        if record.get("activation_command_generated") is not False:
            blockers.append("ACTIVATION_EXECUTION_RECORD_COMMAND_UNSAFE")
        if record.get("activation_command_executed") is not False:
            blockers.append("ACTIVATION_EXECUTION_RECORD_EXECUTED_UNSAFE")
        if record.get("pilot_activation_authorized") is not False:
            blockers.append("ACTIVATION_EXECUTION_RECORD_AUTHORITY_UNSAFE")
        if record.get("pilot_activated") is not False:
            blockers.append("ACTIVATION_EXECUTION_RECORD_ACTIVE_UNSAFE")

    record_digest = _text(row.get("execution_record_digest"), 180)
    if not _SHA256_RE.fullmatch(record_digest):
        blockers.append("ACTIVATION_EXECUTION_RECORD_DIGEST_INVALID")
    elif record and record_digest != _digest(record):
        blockers.append("ACTIVATION_EXECUTION_RECORD_DIGEST_MISMATCH")

    required_record_fields = (
        "owner_id",
        "tenant_id",
        "workspace_id",
        "candidate_id",
        "proposal_id",
        "pilot_id",
        "execution_environment_digest",
        "execution_preflight_digest",
        "execution_request_digest",
    )
    for key in required_record_fields:
        value = _text(record.get(key), 320)
        if not value:
            blockers.append("ACTIVATION_EXECUTION_RECORD_FIELD_REQUIRED:" + key)

    for key in (
        "execution_environment_digest",
        "execution_preflight_digest",
        "execution_request_digest",
    ):
        value = _text(record.get(key), 180)
        if value and not _SHA256_RE.fullmatch(value):
            blockers.append("ACTIVATION_EXECUTION_RECORD_DIGEST_FIELD_INVALID:" + key)

    try:
        current = reconstruct_checkpoint(checkpoint_master or {})
    except Exception:
        blockers.append("CHECKPOINT_MASTER_INVALID")
        current = None

    blockers = list(dict.fromkeys(blockers))
    if blockers or current is None:
        return _blocked(*blockers)

    persisted_record = {
        "schema": EXECUTION_SCHEMA,
        "state": row["state"],
        "decision": decision,
        "owner_id": record["owner_id"],
        "tenant_id": record["tenant_id"],
        "workspace_id": record["workspace_id"],
        "candidate_id": record["candidate_id"],
        "proposal_id": record["proposal_id"],
        "pilot_id": record["pilot_id"],
        "execution_environment_digest": record["execution_environment_digest"],
        "execution_preflight_digest": record["execution_preflight_digest"],
        "execution_request_digest": record["execution_request_digest"],
        "execution_record_digest": record_digest,
        "execution_decision_verified": True,
        "execution_record_persisted": False,
        "execution_authorization_intent": authorize,
        "execution_denial_intent": deny,
        "activation_command_generated": False,
        "activation_command_executed": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "eligible_for_activation_command_planning_after_persistence": bool(
            authorize
        ),
        "external_action_executed": False,
        "executes_action": False,
    }

    patch = {NAMESPACE: persisted_record}
    patch_digest = _digest(patch)
    event_material = {
        "namespace": NAMESPACE,
        "execution_record_digest": record_digest,
        "execution_preflight_digest": record["execution_preflight_digest"],
        "pilot_id": record["pilot_id"],
        "expected_revision": current["revision"],
    }
    event_id = (
        "aion-b2b-pilot-activation-execution-"
        + sha256(_canonical(event_material).encode("utf-8")).hexdigest()[:32]
    )

    patch_candidate = {
        "schema": PATCH_SCHEMA,
        "state": "PATCH_CANDIDATE",
        "expected_revision": current["revision"],
        "recommended_event_id": event_id,
        "patch": patch,
        "patch_digest": patch_digest,
        "requires_explicit_checkpoint_save": True,
        "requires_persistence_attestation": True,
        "automatic_checkpoint_write": False,
        "checkpoint_saved": False,
        "execution_record_persisted": False,
        "activation_command_generated": False,
        "activation_command_executed": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "external_action_executed": False,
        "executes_action": False,
    }

    return {
        "schema": SCHEMA,
        "state": "READY_FOR_EXPLICIT_EXECUTION_RECORD_PERSISTENCE",
        "blockers": [],
        "execution_decision": decision,
        "pilot_id": record["pilot_id"],
        "execution_record_digest": record_digest,
        "patch_candidate": patch_candidate,
        "execution_record_persisted": False,
        "checkpoint_saved": False,
        "automatic_checkpoint_write": False,
        "activation_command_generated": False,
        "activation_command_executed": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "requires_explicit_checkpoint_save": True,
        "requires_persistence_attestation": True,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "EXECUTION_SCHEMA",
    "PATCH_SCHEMA",
    "NAMESPACE",
    "build_activation_execution_persistence_plan",
]
