"""AION B2B recurring business-action authorization persistence plan.

Pure/offline Checkpoint Master patch planner for a cryptographically verified
recurring business-action authorization or denial.

The planner never writes Checkpoint Master and never converts persisted owner
intent into business-action authority.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_b2b_owner_renewal_action_ceremony import (
    RESULT_SCHEMA as ACTION_SCHEMA,
)
from atlasquant_aion_checkpoint_master import reconstruct_checkpoint

SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_PERSISTENCE_PLAN_V1"
PATCH_SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_CHECKPOINT_PATCH_V1"
NAMESPACE = "aion_b2b_owner_renewal_action_authorization"

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
        "action_record_persisted": False,
        "checkpoint_saved": False,
        "automatic_checkpoint_write": False,
        "requires_explicit_checkpoint_save": True,
        "requires_persistence_attestation": True,
        "eligible_for_action_execution_preflight_after_persistence": False,
        **{key: False for key in _AUTHORITY_FIELDS},
    }


def build_owner_renewal_action_persistence_plan(
    verified_action: Mapping[str, Any] | None,
    *,
    checkpoint_master: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = (
        dict(verified_action)
        if isinstance(verified_action, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != ACTION_SCHEMA:
        blockers.append("BUSINESS_ACTION_DECISION_SCHEMA_INVALID")
    if row.get("state") not in {
        "OWNER_BUSINESS_ACTION_DECISION_VERIFIED_AUTHORIZE_PENDING_PERSISTENCE",
        "OWNER_BUSINESS_ACTION_DECISION_VERIFIED_DENY_PENDING_PERSISTENCE",
    }:
        blockers.append("BUSINESS_ACTION_DECISION_STATE_INVALID")
    if row.get("owner_action_identity_verified") is not True:
        blockers.append("OWNER_ACTION_IDENTITY_NOT_VERIFIED")
    if row.get("owner_action_signature_verified") is not True:
        blockers.append("OWNER_ACTION_SIGNATURE_NOT_VERIFIED")
    if row.get("action_decision_verified") is not True:
        blockers.append("BUSINESS_ACTION_DECISION_NOT_VERIFIED")
    if row.get("action_record_persisted") is not False:
        blockers.append("BUSINESS_ACTION_RECORD_ALREADY_PERSISTED")
    if row.get("requires_action_record_persistence") is not True:
        blockers.append("BUSINESS_ACTION_PERSISTENCE_BOUNDARY_MISSING")
    if (
        row.get("generic_chat_instruction_accepted_as_action_authorization")
        is not False
    ):
        blockers.append("GENERIC_CHAT_ACTION_AUTHORIZATION_UNSAFE")

    for key in _AUTHORITY_FIELDS:
        if row.get(key) is not False:
            blockers.append("BUSINESS_ACTION_DECISION_UNSAFE_FIELD:" + key)

    decision = _text(row.get("authorization_decision"), 80)
    if decision not in {
        "AUTHORIZE_BUSINESS_ACTION",
        "DENY_BUSINESS_ACTION",
    }:
        blockers.append("BUSINESS_ACTION_AUTHORIZATION_DECISION_INVALID")

    authorize = row.get("action_authorization_intent") is True
    deny = row.get("action_denial_intent") is True
    if decision == "AUTHORIZE_BUSINESS_ACTION" and (
        not authorize or deny
    ):
        blockers.append("BUSINESS_ACTION_AUTHORIZE_FLAGS_INVALID")
    if decision == "DENY_BUSINESS_ACTION" and (
        authorize or not deny
    ):
        blockers.append("BUSINESS_ACTION_DENY_FLAGS_INVALID")

    requested_choice = _text(row.get("requested_choice"), 120)
    action_family = _text(row.get("action_family"), 120)
    if not requested_choice:
        blockers.append("BUSINESS_ACTION_CHOICE_REQUIRED")
    if not action_family:
        blockers.append("BUSINESS_ACTION_FAMILY_REQUIRED")

    record = (
        dict(row.get("action_record"))
        if isinstance(row.get("action_record"), Mapping)
        else {}
    )
    if not record:
        blockers.append("BUSINESS_ACTION_RECORD_REQUIRED")
    else:
        if record.get("schema") != ACTION_SCHEMA:
            blockers.append("BUSINESS_ACTION_RECORD_SCHEMA_INVALID")
        if record.get("state") != row.get("state"):
            blockers.append("BUSINESS_ACTION_RECORD_STATE_MISMATCH")
        if record.get("authorization_decision") != decision:
            blockers.append("BUSINESS_ACTION_RECORD_DECISION_MISMATCH")
        if record.get("requested_choice") != requested_choice:
            blockers.append("BUSINESS_ACTION_RECORD_CHOICE_MISMATCH")
        if record.get("action_family") != action_family:
            blockers.append("BUSINESS_ACTION_RECORD_FAMILY_MISMATCH")
        if record.get("owner_action_signature_verified") is not True:
            blockers.append("BUSINESS_ACTION_RECORD_SIGNATURE_NOT_VERIFIED")
        if record.get("action_decision_verified") is not True:
            blockers.append("BUSINESS_ACTION_RECORD_DECISION_NOT_VERIFIED")
        if record.get("action_record_persisted") is not False:
            blockers.append("BUSINESS_ACTION_RECORD_ALREADY_PERSISTED")
        if record.get("business_action_authorized") is not False:
            blockers.append("BUSINESS_ACTION_RECORD_AUTHORITY_UNSAFE")
        if record.get("external_action_executed") is not False:
            blockers.append("BUSINESS_ACTION_RECORD_EXTERNAL_ACTION_UNSAFE")
        if record.get("executes_action") is not False:
            blockers.append("BUSINESS_ACTION_RECORD_EXECUTION_UNSAFE")

    record_digest = _text(row.get("action_record_digest"), 180)
    if not _SHA256_RE.fullmatch(record_digest):
        blockers.append("BUSINESS_ACTION_RECORD_DIGEST_INVALID")
    elif record and record_digest != _digest(record):
        blockers.append("BUSINESS_ACTION_RECORD_DIGEST_MISMATCH")

    required_record_fields = (
        "owner_id",
        "tenant_id",
        "workspace_id",
        "customer_id",
        "pilot_id",
        "package",
        "review_type",
        "requested_choice",
        "action_family",
        "owner_review_packet_digest",
        "cycle_evidence_digest",
        "contract_digest",
        "value_bound_conversion_digest",
        "decision_record_digest",
        "persistence_receipt_digest",
        "checkpoint_digest",
        "writer_request_digest",
        "environment_digest",
        "preflight_digest",
        "authorization_request_digest",
    )
    for key in required_record_fields:
        if not _text(record.get(key), 320):
            blockers.append("BUSINESS_ACTION_RECORD_FIELD_REQUIRED:" + key)

    for key in (
        "owner_review_packet_digest",
        "cycle_evidence_digest",
        "contract_digest",
        "value_bound_conversion_digest",
        "decision_record_digest",
        "persistence_receipt_digest",
        "checkpoint_digest",
        "writer_request_digest",
        "environment_digest",
        "preflight_digest",
        "authorization_request_digest",
    ):
        value = _text(record.get(key), 180)
        if value and not _SHA256_RE.fullmatch(value):
            blockers.append("BUSINESS_ACTION_RECORD_DIGEST_FIELD_INVALID:" + key)

    try:
        current = reconstruct_checkpoint(checkpoint_master or {})
    except Exception:
        blockers.append("CHECKPOINT_MASTER_INVALID")
        current = None

    blockers = list(dict.fromkeys(blockers))
    if blockers or current is None:
        return _blocked(*blockers)

    persisted_record = {
        "schema": ACTION_SCHEMA,
        "state": row["state"],
        "authorization_decision": decision,
        "owner_id": record["owner_id"],
        "tenant_id": record["tenant_id"],
        "workspace_id": record["workspace_id"],
        "customer_id": record["customer_id"],
        "pilot_id": record["pilot_id"],
        "package": record["package"],
        "review_type": record["review_type"],
        "requested_choice": requested_choice,
        "action_family": action_family,
        "owner_review_packet_digest": record[
            "owner_review_packet_digest"
        ],
        "cycle_evidence_digest": record["cycle_evidence_digest"],
        "contract_digest": record["contract_digest"],
        "value_bound_conversion_digest": record[
            "value_bound_conversion_digest"
        ],
        "decision_record_digest": record["decision_record_digest"],
        "persistence_receipt_digest": record[
            "persistence_receipt_digest"
        ],
        "checkpoint_digest": record["checkpoint_digest"],
        "writer_request_digest": record["writer_request_digest"],
        "environment_digest": record["environment_digest"],
        "preflight_digest": record["preflight_digest"],
        "authorization_request_digest": record[
            "authorization_request_digest"
        ],
        "action_record_digest": record_digest,
        "owner_action_signature_verified": True,
        "action_decision_verified": True,
        "action_authorization_intent": authorize,
        "action_denial_intent": deny,
        "action_record_persisted": False,
        "business_action_authorized": False,
        "eligible_for_action_execution_preflight_after_persistence": bool(
            authorize
        ),
        "external_action_executed": False,
        "executes_action": False,
    }

    patch = {NAMESPACE: persisted_record}
    patch_digest = _digest(patch)
    event_seed = {
        "namespace": NAMESPACE,
        "action_record_digest": record_digest,
        "customer_id": record["customer_id"],
        "pilot_id": record["pilot_id"],
        "requested_choice": requested_choice,
        "authorization_decision": decision,
        "checkpoint_state_digest": current["state_digest"],
        "expected_revision": current["revision"],
    }
    event_id = (
        "aion-b2b-owner-renewal-action-"
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
        "action_record_persisted": False,
        "business_action_authorized": False,
        "external_action_executed": False,
        "executes_action": False,
    }

    return {
        "schema": SCHEMA,
        "state": "READY_FOR_EXPLICIT_ACTION_RECORD_PERSISTENCE",
        "blockers": [],
        "authorization_decision": decision,
        "requested_choice": requested_choice,
        "action_family": action_family,
        "owner_id": record["owner_id"],
        "tenant_id": record["tenant_id"],
        "workspace_id": record["workspace_id"],
        "customer_id": record["customer_id"],
        "pilot_id": record["pilot_id"],
        "package": record["package"],
        "review_type": record["review_type"],
        "action_record_digest": record_digest,
        "checkpoint_revision": current["revision"],
        "checkpoint_state_digest": current["state_digest"],
        "patch_candidate": patch_candidate,
        "action_record_persisted": False,
        "checkpoint_saved": False,
        "automatic_checkpoint_write": False,
        "requires_explicit_checkpoint_save": True,
        "requires_persistence_attestation": True,
        "eligible_for_action_execution_preflight_after_persistence": False,
        **{key: False for key in _AUTHORITY_FIELDS},
    }


__all__ = [
    "SCHEMA",
    "ACTION_SCHEMA",
    "PATCH_SCHEMA",
    "NAMESPACE",
    "build_owner_renewal_action_persistence_plan",
]
