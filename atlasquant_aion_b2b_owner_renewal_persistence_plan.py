"""AION B2B owner renewal decision persistence plan.

Pure/offline Checkpoint Master patch planner for a cryptographically verified
renewal/continuation decision. It pins the candidate to the exact current
checkpoint revision and evidence digests. It never writes the checkpoint and
never turns persistence into business-action authority.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from atlasquant_aion_b2b_owner_renewal_signature import (
    RESULT_SCHEMA as DECISION_SCHEMA,
)
from atlasquant_aion_checkpoint_master import reconstruct_checkpoint

SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_PERSISTENCE_PLAN_V1"
PATCH_SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_CHECKPOINT_PATCH_V1"
NAMESPACE = "aion_b2b_owner_renewal_decision"

_AUTHORIZATION_FIELDS = (
    "renewal_authorized",
    "expansion_authorized",
    "pause_authorized",
    "termination_authorized",
    "billing_authorized",
    "pricing_change_authorized",
    "quota_change_authorized",
    "role_change_authorized",
    "integration_change_authorized",
    "customer_contact_authorized",
    "provisioning_authorized",
    "deploy_authorized",
    "provider_called",
    "crm_write_authorized",
    "production_mutation_authorized",
    "external_action_executed",
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
        "owner_decision_recorded": False,
        "decision_persisted": False,
        "checkpoint_saved": False,
        "automatic_checkpoint_write": False,
        "requires_explicit_checkpoint_save": True,
        "requires_persistence_attestation": True,
        **{key: False for key in _AUTHORIZATION_FIELDS},
    }


def build_owner_renewal_persistence_plan(
    verified_decision: Mapping[str, Any] | None,
    *,
    checkpoint_master: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = (
        dict(verified_decision)
        if isinstance(verified_decision, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != DECISION_SCHEMA:
        blockers.append("OWNER_RENEWAL_DECISION_SCHEMA_INVALID")
    if (
        row.get("state")
        != "OWNER_RENEWAL_DECISION_VERIFIED_PENDING_PERSISTENCE"
    ):
        blockers.append("OWNER_RENEWAL_DECISION_STATE_INVALID")
    if row.get("owner_identity_signature_verified") is not True:
        blockers.append("OWNER_IDENTITY_SIGNATURE_NOT_VERIFIED")
    if row.get("owner_decision_signature_verified") is not True:
        blockers.append("OWNER_DECISION_SIGNATURE_NOT_VERIFIED")
    if row.get("owner_decision_verified") is not True:
        blockers.append("OWNER_RENEWAL_DECISION_NOT_VERIFIED")
    if row.get("owner_decision_recorded") is not False:
        blockers.append("OWNER_RENEWAL_DECISION_ALREADY_RECORDED")
    if row.get("decision_persisted") is not False:
        blockers.append("OWNER_RENEWAL_DECISION_ALREADY_PERSISTED")
    if row.get("requires_decision_persistence") is not True:
        blockers.append("OWNER_RENEWAL_PERSISTENCE_BOUNDARY_MISSING")
    if (
        row.get("generic_chat_instruction_accepted_as_decision")
        is not False
    ):
        blockers.append("GENERIC_CHAT_DECISION_BOUNDARY_UNSAFE")

    for key in _AUTHORIZATION_FIELDS:
        if row.get(key) is not False:
            blockers.append("OWNER_RENEWAL_DECISION_UNSAFE_FIELD:" + key)

    choice = _text(row.get("requested_choice"), 120)
    if not choice:
        blockers.append("OWNER_RENEWAL_DECISION_CHOICE_REQUIRED")

    record = (
        dict(row.get("decision_record"))
        if isinstance(row.get("decision_record"), Mapping)
        else {}
    )
    if not record:
        blockers.append("OWNER_RENEWAL_DECISION_RECORD_REQUIRED")
    else:
        if record.get("schema") != DECISION_SCHEMA:
            blockers.append("OWNER_RENEWAL_RECORD_SCHEMA_INVALID")
        if record.get("requested_choice") != choice:
            blockers.append("OWNER_RENEWAL_RECORD_CHOICE_MISMATCH")
        if record.get("owner_signature_verified") is not True:
            blockers.append("OWNER_RENEWAL_RECORD_SIGNATURE_NOT_VERIFIED")
        if record.get("owner_decision_verified") is not True:
            blockers.append("OWNER_RENEWAL_RECORD_DECISION_NOT_VERIFIED")
        if record.get("owner_decision_recorded") is not False:
            blockers.append("OWNER_RENEWAL_RECORD_ALREADY_RECORDED")
        if record.get("decision_persisted") is not False:
            blockers.append("OWNER_RENEWAL_RECORD_ALREADY_PERSISTED")

    record_digest = _text(row.get("decision_record_digest"), 180)
    if not record_digest:
        blockers.append("OWNER_RENEWAL_RECORD_DIGEST_REQUIRED")
    elif record and record_digest != _digest(record):
        blockers.append("OWNER_RENEWAL_RECORD_DIGEST_MISMATCH")

    required_record_fields = (
        "owner_id",
        "tenant_id",
        "workspace_id",
        "customer_id",
        "pilot_id",
        "package",
        "review_type",
        "owner_review_packet_digest",
        "cycle_evidence_digest",
        "contract_digest",
        "value_bound_conversion_digest",
        "decision_request_digest",
        "signature_request_digest",
    )
    for key in required_record_fields:
        if not _text(record.get(key), 320):
            blockers.append("OWNER_RENEWAL_RECORD_FIELD_REQUIRED:" + key)

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
        "requested_choice": choice,
        "owner_id": record["owner_id"],
        "tenant_id": record["tenant_id"],
        "workspace_id": record["workspace_id"],
        "customer_id": record["customer_id"],
        "pilot_id": record["pilot_id"],
        "package": record["package"],
        "review_type": record["review_type"],
        "owner_review_packet_digest": record[
            "owner_review_packet_digest"
        ],
        "cycle_evidence_digest": record["cycle_evidence_digest"],
        "contract_digest": record["contract_digest"],
        "value_bound_conversion_digest": record[
            "value_bound_conversion_digest"
        ],
        "decision_request_digest": record["decision_request_digest"],
        "signature_request_digest": record[
            "signature_request_digest"
        ],
        "decision_record_digest": record_digest,
        "owner_signature_verified": True,
        "owner_decision_verified": True,
        "owner_decision_recorded": False,
        "decision_persisted": False,
        "business_action_authorized": False,
        "external_action_executed": False,
        "executes_action": False,
    }

    patch = {NAMESPACE: persisted_record}
    patch_digest = _digest(patch)
    event_seed = {
        "namespace": NAMESPACE,
        "decision_record_digest": record_digest,
        "customer_id": record["customer_id"],
        "pilot_id": record["pilot_id"],
        "requested_choice": choice,
        "checkpoint_state_digest": current["state_digest"],
        "expected_revision": current["revision"],
    }
    event_id = (
        "aion-b2b-owner-renewal-decision-"
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
        "owner_decision_recorded": False,
        "decision_persisted": False,
        "business_action_authorized": False,
        "external_action_executed": False,
        "executes_action": False,
    }

    return {
        "schema": SCHEMA,
        "state": "READY_FOR_EXPLICIT_CHECKPOINT_PERSISTENCE",
        "blockers": [],
        "requested_choice": choice,
        "customer_id": record["customer_id"],
        "pilot_id": record["pilot_id"],
        "decision_record_digest": record_digest,
        "checkpoint_revision": current["revision"],
        "checkpoint_state_digest": current["state_digest"],
        "patch_candidate": patch_candidate,
        "owner_decision_recorded": False,
        "decision_persisted": False,
        "checkpoint_saved": False,
        "automatic_checkpoint_write": False,
        "requires_explicit_checkpoint_save": True,
        "requires_persistence_attestation": True,
        **{key: False for key in _AUTHORIZATION_FIELDS},
    }


__all__ = [
    "SCHEMA",
    "DECISION_SCHEMA",
    "PATCH_SCHEMA",
    "NAMESPACE",
    "build_owner_renewal_persistence_plan",
]
