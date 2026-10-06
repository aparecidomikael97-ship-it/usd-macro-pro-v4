"""AION B2B recurring business-action execution persistence plan.

Pure/offline Checkpoint Master patch planner for a cryptographically verified
recurring business-action execution authorization or denial.

The module prepares a deterministic patch candidate only. It never writes
Checkpoint Master, never generates a command and never executes the action.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_b2b_owner_renewal_action_execution_ceremony import (
    RESULT_SCHEMA as EXECUTION_SCHEMA,
)
from atlasquant_aion_checkpoint_master import reconstruct_checkpoint

SCHEMA = (
    "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_EXECUTION_PERSISTENCE_PLAN_V1"
)
PATCH_SCHEMA = (
    "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_EXECUTION_CHECKPOINT_PATCH_V1"
)
NAMESPACE = "aion_b2b_owner_renewal_action_execution_authorization"

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

_AUTHORITY_FIELDS = (
    "business_action_authorized",
    "renewal_authorized",
    "expansion_authorized",
    "non_renewal_authorized",
    "remediation_authorized",
    "pause_authorized",
    "termination_authorized",
    "billing_authorized",
    "pricing_change_authorized",
    "quota_change_authorized",
    "package_change_authorized",
    "role_change_authorized",
    "integration_change_authorized",
    "customer_contact_authorized",
    "provisioning_authorized",
    "deploy_authorized",
    "provider_called",
    "crm_write_authorized",
    "production_mutation_authorized",
    "external_action_executed",
    "network_called",
    "executes_action",
)

_DIGEST_FIELDS = (
    "action_record_digest",
    "action_persistence_receipt_digest",
    "action_checkpoint_digest",
    "action_writer_request_digest",
    "authorization_preflight_digest",
    "action_parameters_digest",
    "execution_environment_digest",
    "execution_preflight_digest",
    "execution_request_digest",
)


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


def _text(value: Any, limit: int = 420) -> str:
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
        "requires_explicit_checkpoint_save": True,
        "requires_persistence_attestation": True,
        "eligible_for_command_planning_after_persistence": False,
        "execution_command_generated": False,
        "execution_command_executed": False,
        **{key: False for key in _AUTHORITY_FIELDS},
    }


def build_owner_renewal_action_execution_persistence_plan(
    verified_execution: Mapping[str, Any] | None,
    *,
    checkpoint_master: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = (
        dict(verified_execution)
        if isinstance(verified_execution, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != EXECUTION_SCHEMA:
        blockers.append("EXECUTION_DECISION_SCHEMA_INVALID")
    if row.get("state") not in {
        "OWNER_BUSINESS_ACTION_EXECUTION_VERIFIED_AUTHORIZE_PENDING_PERSISTENCE",
        "OWNER_BUSINESS_ACTION_EXECUTION_VERIFIED_DENY_PENDING_PERSISTENCE",
    }:
        blockers.append("EXECUTION_DECISION_STATE_INVALID")
    if row.get("owner_execution_identity_verified") is not True:
        blockers.append("OWNER_EXECUTION_IDENTITY_NOT_VERIFIED")
    if row.get("owner_execution_signature_verified") is not True:
        blockers.append("OWNER_EXECUTION_SIGNATURE_NOT_VERIFIED")
    if row.get("execution_decision_verified") is not True:
        blockers.append("EXECUTION_DECISION_NOT_VERIFIED")
    if row.get("execution_record_persisted") is not False:
        blockers.append("EXECUTION_RECORD_ALREADY_PERSISTED")
    if row.get("requires_execution_record_persistence") is not True:
        blockers.append("EXECUTION_PERSISTENCE_BOUNDARY_MISSING")
    if row.get("execution_command_generated") is not False:
        blockers.append("EXECUTION_COMMAND_ALREADY_GENERATED")
    if row.get("execution_command_executed") is not False:
        blockers.append("EXECUTION_COMMAND_ALREADY_EXECUTED")
    if (
        row.get("generic_chat_instruction_accepted_as_execution")
        is not False
    ):
        blockers.append("GENERIC_CHAT_EXECUTION_BOUNDARY_UNSAFE")

    for key in _AUTHORITY_FIELDS:
        if row.get(key) is not False:
            blockers.append("EXECUTION_DECISION_UNSAFE_FIELD:" + key)

    decision = _text(row.get("execution_decision"), 100)
    if decision not in {
        "AUTHORIZE_BUSINESS_ACTION_EXECUTION",
        "DENY_BUSINESS_ACTION_EXECUTION",
    }:
        blockers.append("EXECUTION_DECISION_INVALID")
    authorize = row.get("execution_authorization_intent") is True
    deny = row.get("execution_denial_intent") is True
    if decision == "AUTHORIZE_BUSINESS_ACTION_EXECUTION" and (
        not authorize or deny
    ):
        blockers.append("EXECUTION_AUTHORIZE_FLAGS_INVALID")
    if decision == "DENY_BUSINESS_ACTION_EXECUTION" and (
        authorize or not deny
    ):
        blockers.append("EXECUTION_DENY_FLAGS_INVALID")

    choice = _text(row.get("requested_choice"), 120)
    family = _text(row.get("action_family"), 120)
    if not choice:
        blockers.append("EXECUTION_CHOICE_REQUIRED")
    if not family:
        blockers.append("EXECUTION_ACTION_FAMILY_REQUIRED")

    record = (
        dict(row.get("execution_record"))
        if isinstance(row.get("execution_record"), Mapping)
        else {}
    )
    if not record:
        blockers.append("EXECUTION_RECORD_REQUIRED")
    else:
        if record.get("schema") != EXECUTION_SCHEMA:
            blockers.append("EXECUTION_RECORD_SCHEMA_INVALID")
        if record.get("state") != row.get("state"):
            blockers.append("EXECUTION_RECORD_STATE_MISMATCH")
        if record.get("execution_decision") != decision:
            blockers.append("EXECUTION_RECORD_DECISION_MISMATCH")
        if record.get("requested_choice") != choice:
            blockers.append("EXECUTION_RECORD_CHOICE_MISMATCH")
        if record.get("action_family") != family:
            blockers.append("EXECUTION_RECORD_FAMILY_MISMATCH")
        if record.get("owner_execution_signature_verified") is not True:
            blockers.append("EXECUTION_RECORD_SIGNATURE_NOT_VERIFIED")
        if record.get("execution_decision_verified") is not True:
            blockers.append("EXECUTION_RECORD_DECISION_NOT_VERIFIED")
        if record.get("execution_record_persisted") is not False:
            blockers.append("EXECUTION_RECORD_ALREADY_PERSISTED")
        if record.get("execution_command_generated") is not False:
            blockers.append("EXECUTION_RECORD_COMMAND_GENERATED_UNSAFE")
        if record.get("execution_command_executed") is not False:
            blockers.append("EXECUTION_RECORD_COMMAND_EXECUTED_UNSAFE")
        for key in _AUTHORITY_FIELDS:
            if record.get(key) is not False:
                blockers.append("EXECUTION_RECORD_UNSAFE_FIELD:" + key)

    record_digest = _text(row.get("execution_record_digest"), 180)
    if not _SHA256_RE.fullmatch(record_digest):
        blockers.append("EXECUTION_RECORD_DIGEST_INVALID")
    elif record and record_digest != _digest(record):
        blockers.append("EXECUTION_RECORD_DIGEST_MISMATCH")

    for key in (
        "owner_id",
        "tenant_id",
        "workspace_id",
        "customer_id",
        "pilot_id",
        "package",
        "review_type",
        "requested_choice",
        "action_family",
    ):
        if not _text(record.get(key), 160):
            blockers.append("EXECUTION_RECORD_FIELD_REQUIRED:" + key)

    for key in _DIGEST_FIELDS:
        if not _SHA256_RE.fullmatch(_text(record.get(key), 180)):
            blockers.append("EXECUTION_RECORD_DIGEST_FIELD_INVALID:" + key)

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
        "execution_decision": decision,
        "owner_id": record["owner_id"],
        "tenant_id": record["tenant_id"],
        "workspace_id": record["workspace_id"],
        "customer_id": record["customer_id"],
        "pilot_id": record["pilot_id"],
        "package": record["package"],
        "review_type": record["review_type"],
        "requested_choice": choice,
        "action_family": family,
        **{key: record[key] for key in _DIGEST_FIELDS},
        "execution_record_digest": record_digest,
        "owner_execution_signature_verified": True,
        "execution_decision_verified": True,
        "execution_authorization_intent": authorize,
        "execution_denial_intent": deny,
        "execution_record_persisted": False,
        "eligible_for_command_planning_after_persistence": bool(authorize),
        "execution_command_generated": False,
        "execution_command_executed": False,
        **{key: False for key in _AUTHORITY_FIELDS},
    }

    patch = {NAMESPACE: persisted_record}
    patch_digest = _digest(patch)
    event_seed = {
        "namespace": NAMESPACE,
        "execution_record_digest": record_digest,
        "customer_id": record["customer_id"],
        "pilot_id": record["pilot_id"],
        "requested_choice": choice,
        "action_family": family,
        "execution_decision": decision,
        "execution_preflight_digest": record["execution_preflight_digest"],
        "expected_revision": current["revision"],
        "expected_state_digest": current["state_digest"],
    }
    event_id = (
        "aion-b2b-owner-renewal-action-execution-"
        + sha256(_canonical(event_seed).encode("utf-8")).hexdigest()[:32]
    )

    patch_candidate = {
        "schema": PATCH_SCHEMA,
        "state": "PATCH_CANDIDATE",
        "expected_revision": current["revision"],
        "expected_state_digest": current["state_digest"],
        "recommended_event_id": event_id,
        "patch": patch,
        "patch_digest": patch_digest,
        "requires_explicit_checkpoint_save": True,
        "requires_persistence_attestation": True,
        "automatic_checkpoint_write": False,
        "checkpoint_saved": False,
        "execution_record_persisted": False,
        "execution_command_generated": False,
        "execution_command_executed": False,
        **{key: False for key in _AUTHORITY_FIELDS},
    }

    return {
        "schema": SCHEMA,
        "state": "READY_FOR_EXPLICIT_EXECUTION_RECORD_PERSISTENCE",
        "blockers": [],
        "execution_decision": decision,
        "requested_choice": choice,
        "action_family": family,
        "owner_id": record["owner_id"],
        "tenant_id": record["tenant_id"],
        "workspace_id": record["workspace_id"],
        "customer_id": record["customer_id"],
        "pilot_id": record["pilot_id"],
        "package": record["package"],
        "review_type": record["review_type"],
        "execution_record_digest": record_digest,
        "checkpoint_revision": current["revision"],
        "checkpoint_state_digest": current["state_digest"],
        "patch_candidate": patch_candidate,
        "execution_record_persisted": False,
        "checkpoint_saved": False,
        "automatic_checkpoint_write": False,
        "requires_explicit_checkpoint_save": True,
        "requires_persistence_attestation": True,
        "eligible_for_command_planning_after_persistence": False,
        "execution_command_generated": False,
        "execution_command_executed": False,
        **{key: False for key in _AUTHORITY_FIELDS},
    }


__all__ = [
    "SCHEMA",
    "EXECUTION_SCHEMA",
    "PATCH_SCHEMA",
    "NAMESPACE",
    "build_owner_renewal_action_execution_persistence_plan",
]
