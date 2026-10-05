"""AION B2B Pilot Activation Authorization Persistence Plan V1.

Pure/offline Checkpoint Master patch planner for a verified pilot activation
decision.

It accepts only:
- ACTIVATION_AUTHORIZATION_VERIFIED_PENDING_PERSISTENCE
- ACTIVATION_DENIAL_VERIFIED_PENDING_PERSISTENCE

The module prepares a deterministic patch candidate but never calls
append_checkpoint_patch, never persists the activation record and never
authorizes or executes pilot activation.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json
import re

from atlasquant_aion_checkpoint_master import reconstruct_checkpoint

SCHEMA = "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_PERSISTENCE_PLAN_V1"
ACTIVATION_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_VERIFICATION_V1"
PATCH_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_CHECKPOINT_PATCH_V1"
NAMESPACE = "aion_b2b_pilot_activation_authorization"

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
        "activation_record_persisted": False,
        "checkpoint_saved": False,
        "automatic_checkpoint_write": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
    }


def build_pilot_activation_persistence_plan(
    verified_activation: Mapping[str, Any] | None,
    *,
    checkpoint_master: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Prepare but never persist the activation authorization record."""
    row = (
        dict(verified_activation)
        if isinstance(verified_activation, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != ACTIVATION_SCHEMA:
        blockers.append("PILOT_ACTIVATION_SCHEMA_INVALID")
    if row.get("state") not in {
        "ACTIVATION_AUTHORIZATION_VERIFIED_PENDING_PERSISTENCE",
        "ACTIVATION_DENIAL_VERIFIED_PENDING_PERSISTENCE",
    }:
        blockers.append("PILOT_ACTIVATION_STATE_INVALID")
    if row.get("activation_decision_verified") is not True:
        blockers.append("PILOT_ACTIVATION_DECISION_NOT_VERIFIED")
    if row.get("owner_activation_identity_verified") is not True:
        blockers.append("PILOT_ACTIVATION_OWNER_IDENTITY_NOT_VERIFIED")
    if row.get("owner_activation_signature_verified") is not True:
        blockers.append("PILOT_ACTIVATION_SIGNATURE_NOT_VERIFIED")
    if row.get("activation_record_persisted") is not False:
        blockers.append("PILOT_ACTIVATION_RECORD_ALREADY_PERSISTED")
    if row.get("pilot_activation_authorized") is not False:
        blockers.append("PILOT_ACTIVATION_ALREADY_AUTHORIZED")
    if row.get("pilot_activated") is not False:
        blockers.append("PILOT_ALREADY_ACTIVATED")
    if row.get("requires_activation_record_persistence") is not True:
        blockers.append("ACTIVATION_PERSISTENCE_BOUNDARY_MISSING")

    for key in (
        "customer_contact_authorized",
        "contract_signature_authorized",
        "billing_authorized",
        "spend_authorized",
        "provisioning_authorized",
        "deploy_authorized",
        "crm_write_authorized",
        "provider_called",
        "production_mutation_authorized",
        "external_action_executed",
        "network_called",
        "executes_action",
    ):
        if row.get(key) is not False:
            blockers.append("PILOT_ACTIVATION_UNSAFE_FIELD:" + key)

    decision = _text(row.get("activation_decision"), 80)
    if decision not in {
        "AUTHORIZE_PILOT_ACTIVATION",
        "DENY_PILOT_ACTIVATION",
    }:
        blockers.append("PILOT_ACTIVATION_DECISION_INVALID")

    authorize = row.get("activation_authorization_intent") is True
    deny = row.get("activation_denial_intent") is True
    if decision == "AUTHORIZE_PILOT_ACTIVATION" and (
        not authorize or deny
    ):
        blockers.append("PILOT_ACTIVATION_AUTHORIZE_FLAGS_INVALID")
    if decision == "DENY_PILOT_ACTIVATION" and (
        authorize or not deny
    ):
        blockers.append("PILOT_ACTIVATION_DENY_FLAGS_INVALID")

    record = (
        dict(row.get("activation_record"))
        if isinstance(row.get("activation_record"), Mapping)
        else {}
    )
    if not record:
        blockers.append("PILOT_ACTIVATION_RECORD_REQUIRED")
    else:
        if record.get("schema") != ACTIVATION_SCHEMA:
            blockers.append("PILOT_ACTIVATION_RECORD_SCHEMA_INVALID")
        if record.get("decision") != decision:
            blockers.append("PILOT_ACTIVATION_RECORD_DECISION_MISMATCH")
        if record.get("activation_decision_verified") is not True:
            blockers.append("PILOT_ACTIVATION_RECORD_NOT_VERIFIED")
        if record.get("activation_record_persisted") is not False:
            blockers.append("PILOT_ACTIVATION_RECORD_ALREADY_PERSISTED")
        if record.get("pilot_activation_authorized") is not False:
            blockers.append("PILOT_ACTIVATION_RECORD_AUTHORITY_UNSAFE")
        if record.get("pilot_activated") is not False:
            blockers.append("PILOT_ACTIVATION_RECORD_ACTIVE_UNSAFE")

    record_digest = _text(row.get("activation_record_digest"), 180)
    if not _SHA256_RE.fullmatch(record_digest):
        blockers.append("PILOT_ACTIVATION_RECORD_DIGEST_INVALID")
    elif record and record_digest != _digest(record):
        blockers.append("PILOT_ACTIVATION_RECORD_DIGEST_MISMATCH")

    required_record_fields = (
        "owner_id",
        "tenant_id",
        "workspace_id",
        "candidate_id",
        "proposal_id",
        "pilot_id",
        "environment_digest",
        "preflight_digest",
        "activation_request_digest",
    )
    for key in required_record_fields:
        value = _text(record.get(key), 320)
        if not value:
            blockers.append(
                "PILOT_ACTIVATION_RECORD_FIELD_REQUIRED:" + key
            )
    for key in (
        "environment_digest",
        "preflight_digest",
        "activation_request_digest",
    ):
        value = _text(record.get(key), 180)
        if value and not _SHA256_RE.fullmatch(value):
            blockers.append(
                "PILOT_ACTIVATION_RECORD_DIGEST_FIELD_INVALID:" + key
            )

    try:
        current = reconstruct_checkpoint(checkpoint_master or {})
    except Exception:
        blockers.append("CHECKPOINT_MASTER_INVALID")
        current = None

    blockers = list(dict.fromkeys(blockers))
    if blockers or current is None:
        return _blocked(*blockers)

    persisted_record = {
        "schema": ACTIVATION_SCHEMA,
        "state": row["state"],
        "decision": decision,
        "owner_id": record["owner_id"],
        "tenant_id": record["tenant_id"],
        "workspace_id": record["workspace_id"],
        "candidate_id": record["candidate_id"],
        "proposal_id": record["proposal_id"],
        "pilot_id": record["pilot_id"],
        "environment_digest": record["environment_digest"],
        "preflight_digest": record["preflight_digest"],
        "activation_request_digest": record["activation_request_digest"],
        "activation_record_digest": record_digest,
        "activation_decision_verified": True,
        "activation_record_persisted": False,
        "activation_authorization_intent": authorize,
        "activation_denial_intent": deny,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "eligible_for_activation_execution_after_persistence": bool(
            authorize
        ),
        "external_action_executed": False,
        "executes_action": False,
    }

    patch = {NAMESPACE: persisted_record}
    patch_digest = _digest(patch)
    event_material = {
        "namespace": NAMESPACE,
        "activation_record_digest": record_digest,
        "preflight_digest": record["preflight_digest"],
        "pilot_id": record["pilot_id"],
        "expected_revision": current["revision"],
    }
    event_id = (
        "aion-b2b-pilot-activation-"
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
        "activation_record_persisted": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "external_action_executed": False,
        "executes_action": False,
    }

    return {
        "schema": SCHEMA,
        "state": "READY_FOR_EXPLICIT_ACTIVATION_RECORD_PERSISTENCE",
        "blockers": [],
        "activation_decision": decision,
        "pilot_id": record["pilot_id"],
        "activation_record_digest": record_digest,
        "patch_candidate": patch_candidate,
        "activation_record_persisted": False,
        "checkpoint_saved": False,
        "automatic_checkpoint_write": False,
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
    "ACTIVATION_SCHEMA",
    "PATCH_SCHEMA",
    "NAMESPACE",
    "build_pilot_activation_persistence_plan",
]
