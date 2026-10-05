"""AION B2B Pilot Owner Decision Persistence Plan V1.

Pure/offline checkpoint patch planner for a verified B2B pilot owner decision.

This module validates a cryptographically verified APPROVE_PILOT/DENY_PILOT
result and prepares a deterministic Checkpoint Master patch candidate.

It never calls append_checkpoint_patch, never writes the checkpoint, never
claims persistence, and never authorizes pilot activation.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json

from atlasquant_aion_checkpoint_master import reconstruct_checkpoint

SCHEMA = "ATLASQUANT_AION_B2B_PILOT_OWNER_DECISION_PERSISTENCE_PLAN_V1"
DECISION_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_OWNER_DECISION_VERIFICATION_V1"
PATCH_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_OWNER_DECISION_CHECKPOINT_PATCH_V1"
NAMESPACE = "aion_b2b_pilot_owner_decision"


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
        "decision_record_persisted": False,
        "checkpoint_saved": False,
        "automatic_checkpoint_write": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
    }


def build_pilot_owner_decision_persistence_plan(
    verified_decision: Mapping[str, Any] | None,
    *,
    checkpoint_master: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Prepare but never persist a Checkpoint Master patch candidate."""
    row = (
        dict(verified_decision)
        if isinstance(verified_decision, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != DECISION_SCHEMA:
        blockers.append("PILOT_OWNER_DECISION_SCHEMA_INVALID")
    if row.get("state") not in {
        "OWNER_DECISION_VERIFIED_APPROVE_PENDING_PERSISTENCE",
        "OWNER_DECISION_VERIFIED_DENY_PENDING_PERSISTENCE",
    }:
        blockers.append("PILOT_OWNER_DECISION_STATE_INVALID")
    if row.get("owner_decision_verified") is not True:
        blockers.append("PILOT_OWNER_DECISION_NOT_VERIFIED")
    if row.get("owner_decision_recorded") is not False:
        blockers.append("PILOT_OWNER_DECISION_ALREADY_RECORDED")
    if row.get("decision_record_persisted") is not False:
        blockers.append("PILOT_OWNER_DECISION_ALREADY_PERSISTED")
    if row.get("pilot_activation_authorized") is not False:
        blockers.append("PILOT_OWNER_DECISION_ACTIVATION_UNSAFE")
    if row.get("pilot_activated") is not False:
        blockers.append("PILOT_OWNER_DECISION_ALREADY_ACTIVE")

    for key in (
        "customer_contact_authorized",
        "contract_signature_authorized",
        "billing_authorized",
        "spend_authorized",
        "deploy_authorized",
        "crm_write_authorized",
        "production_mutation_authorized",
        "external_action_executed",
        "network_called",
        "executes_action",
    ):
        if row.get(key) is not False:
            blockers.append(
                f"PILOT_OWNER_DECISION_{key.upper()}_UNSAFE"
            )

    decision = _text(row.get("owner_decision"), 80)
    if decision not in {"APPROVE_PILOT", "DENY_PILOT"}:
        blockers.append("PILOT_OWNER_DECISION_CHOICE_INVALID")

    approved = row.get("pilot_approved") is True
    denied = row.get("pilot_denied") is True
    if decision == "APPROVE_PILOT" and (not approved or denied):
        blockers.append("PILOT_OWNER_DECISION_APPROVE_FLAGS_INVALID")
    if decision == "DENY_PILOT" and (approved or not denied):
        blockers.append("PILOT_OWNER_DECISION_DENY_FLAGS_INVALID")

    record = (
        dict(row.get("decision_record"))
        if isinstance(row.get("decision_record"), Mapping)
        else {}
    )
    if not record:
        blockers.append("PILOT_OWNER_DECISION_RECORD_REQUIRED")
    else:
        if record.get("schema") != DECISION_SCHEMA:
            blockers.append("PILOT_OWNER_DECISION_RECORD_SCHEMA_INVALID")
        if record.get("decision") != decision:
            blockers.append("PILOT_OWNER_DECISION_RECORD_CHOICE_MISMATCH")
        if record.get("owner_decision_verified") is not True:
            blockers.append("PILOT_OWNER_DECISION_RECORD_NOT_VERIFIED")
        if record.get("owner_decision_recorded") is not False:
            blockers.append("PILOT_OWNER_DECISION_RECORD_ALREADY_RECORDED")
        if record.get("decision_record_persisted") is not False:
            blockers.append("PILOT_OWNER_DECISION_RECORD_ALREADY_PERSISTED")
        if record.get("pilot_activation_authorized") is not False:
            blockers.append("PILOT_OWNER_DECISION_RECORD_ACTIVATION_UNSAFE")
        if record.get("pilot_activated") is not False:
            blockers.append("PILOT_OWNER_DECISION_RECORD_ACTIVE_UNSAFE")

    record_digest = _text(row.get("decision_record_digest"), 180)
    if not record_digest:
        blockers.append("PILOT_OWNER_DECISION_RECORD_DIGEST_REQUIRED")
    elif record and record_digest != _digest(record):
        blockers.append("PILOT_OWNER_DECISION_RECORD_DIGEST_MISMATCH")

    required_ids = (
        "owner_id",
        "tenant_id",
        "workspace_id",
        "candidate_id",
        "proposal_id",
        "pilot_id",
        "packet_digest",
        "decision_request_digest",
    )
    for key in required_ids:
        if not _text(record.get(key), 320):
            blockers.append(
                "PILOT_OWNER_DECISION_RECORD_FIELD_REQUIRED:" + key
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
        "schema": DECISION_SCHEMA,
        "state": row["state"],
        "decision": decision,
        "owner_id": record["owner_id"],
        "tenant_id": record["tenant_id"],
        "workspace_id": record["workspace_id"],
        "candidate_id": record["candidate_id"],
        "proposal_id": record["proposal_id"],
        "pilot_id": record["pilot_id"],
        "packet_digest": record["packet_digest"],
        "decision_request_digest": record["decision_request_digest"],
        "decision_record_digest": record_digest,
        "owner_decision_verified": True,
        "owner_decision_recorded": False,
        "decision_record_persisted": False,
        "pilot_approved": approved,
        "pilot_denied": denied,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "eligible_for_activation_ceremony_after_persistence": bool(
            approved
        ),
        "external_action_executed": False,
        "executes_action": False,
    }

    patch = {NAMESPACE: persisted_record}
    patch_digest = _digest(patch)
    event_seed = {
        "namespace": NAMESPACE,
        "decision_record_digest": record_digest,
        "packet_digest": record["packet_digest"],
        "pilot_id": record["pilot_id"],
        "expected_revision": current["revision"],
    }
    event_id = (
        "aion-b2b-pilot-owner-decision-"
        + sha256(_canonical(event_seed).encode("utf-8")).hexdigest()[:32]
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
        "decision_record_persisted": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "external_action_executed": False,
        "executes_action": False,
    }

    return {
        "schema": SCHEMA,
        "state": "READY_FOR_EXPLICIT_CHECKPOINT_PERSISTENCE",
        "blockers": [],
        "decision": decision,
        "pilot_id": record["pilot_id"],
        "decision_record_digest": record_digest,
        "patch_candidate": patch_candidate,
        "decision_record_persisted": False,
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
    "DECISION_SCHEMA",
    "PATCH_SCHEMA",
    "NAMESPACE",
    "build_pilot_owner_decision_persistence_plan",
]
