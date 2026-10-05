"""AION B2B recurring execution-record persistence attestation.

Pure/offline proof that the exact final execution-intent record was appended to
Checkpoint Master. It never writes storage and never generates or executes a
business command.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_b2b_owner_renewal_action_execution_persistence_plan import (
    EXECUTION_SCHEMA,
    NAMESPACE,
    PATCH_SCHEMA,
    SCHEMA as PLAN_SCHEMA,
)
from atlasquant_aion_checkpoint_master import (
    append_checkpoint_patch,
    checkpoint_master_digest,
    reconstruct_checkpoint,
)

SCHEMA = (
    "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_EXECUTION_"
    "PERSISTENCE_ATTESTATION_V1"
)
RECEIPT_SCHEMA = (
    "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_EXECUTION_CHECKPOINT_RECEIPT_V1"
)
MAX_RECEIPT_AGE_SECONDS = 180

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

_LINEAGE_DIGEST_FIELDS = (
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


def _parse_ts(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp required")
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except Exception as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed.astimezone(timezone.utc)


def _blocked(*items: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "blockers": sorted(set(items)),
        "execution_record_persisted": False,
        "persistence_attested": False,
        "receipt_consistency_verified": False,
        "writer_identity_verified": False,
        "eligible_for_command_planning": False,
        "storage_write_performed": False,
        "execution_command_generated": False,
        "execution_command_executed": False,
        **{key: False for key in _AUTHORITY_FIELDS},
    }


def build_owner_execution_checkpoint_receipt_body(
    *,
    persistence_plan: Mapping[str, Any] | None,
    prior_checkpoint_master: Mapping[str, Any] | None,
    observed_checkpoint_master: Mapping[str, Any] | None,
    persisted_at: str,
    writer_ref: str,
) -> dict[str, Any]:
    plan = (
        dict(persistence_plan)
        if isinstance(persistence_plan, Mapping)
        else {}
    )
    patch = (
        dict(plan.get("patch_candidate"))
        if isinstance(plan.get("patch_candidate"), Mapping)
        else {}
    )
    prior = reconstruct_checkpoint(prior_checkpoint_master or {})
    observed = reconstruct_checkpoint(observed_checkpoint_master or {})
    body = {
        "schema": RECEIPT_SCHEMA,
        "status": "CONFIRMED",
        "storage_target": "CHECKPOINT_MASTER",
        "write_mode": "EXPLICIT_AUTHORIZED_APPEND",
        "namespace": NAMESPACE,
        "event_id": _text(patch.get("recommended_event_id"), 160),
        "base_revision": prior["revision"],
        "revision": observed["revision"],
        "patch_digest": _text(patch.get("patch_digest"), 180),
        "before_checkpoint_digest": checkpoint_master_digest(
            prior_checkpoint_master or {}
        ),
        "after_checkpoint_digest": checkpoint_master_digest(
            observed_checkpoint_master or {}
        ),
        "execution_record_digest": _text(
            plan.get("execution_record_digest"), 180
        ),
        "customer_id": _text(plan.get("customer_id"), 120),
        "pilot_id": _text(plan.get("pilot_id"), 120),
        "requested_choice": _text(plan.get("requested_choice"), 120),
        "action_family": _text(plan.get("action_family"), 120),
        "execution_decision": _text(plan.get("execution_decision"), 100),
        "persisted_at": _text(persisted_at, 80),
        "writer_ref": _text(writer_ref, 240),
        "writer_identity_verified": False,
        "execution_command_generated": False,
        "execution_command_executed": False,
        "business_action_authorized": False,
        "external_action_executed": False,
    }
    return {**body, "receipt_digest": _digest(body)}


def _validate_plan(
    persistence_plan: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[str]]:
    plan = (
        dict(persistence_plan)
        if isinstance(persistence_plan, Mapping)
        else {}
    )
    blockers: list[str] = []
    if plan.get("schema") != PLAN_SCHEMA:
        blockers.append("EXECUTION_PERSISTENCE_PLAN_SCHEMA_INVALID")
    if plan.get("state") != "READY_FOR_EXPLICIT_EXECUTION_RECORD_PERSISTENCE":
        blockers.append("EXECUTION_PERSISTENCE_PLAN_NOT_READY")
    for key in (
        "execution_record_persisted",
        "checkpoint_saved",
        "automatic_checkpoint_write",
        "eligible_for_command_planning_after_persistence",
        "execution_command_generated",
        "execution_command_executed",
    ):
        if plan.get(key) is not False:
            blockers.append("EXECUTION_PERSISTENCE_PLAN_UNSAFE_FIELD:" + key)
    if plan.get("requires_explicit_checkpoint_save") is not True:
        blockers.append("EXECUTION_EXPLICIT_SAVE_BOUNDARY_MISSING")
    if plan.get("requires_persistence_attestation") is not True:
        blockers.append("EXECUTION_ATTESTATION_BOUNDARY_MISSING")
    for key in _AUTHORITY_FIELDS:
        if plan.get(key) is not False:
            blockers.append("EXECUTION_PERSISTENCE_PLAN_UNSAFE_FIELD:" + key)

    decision = _text(plan.get("execution_decision"), 100)
    if decision not in {
        "AUTHORIZE_BUSINESS_ACTION_EXECUTION",
        "DENY_BUSINESS_ACTION_EXECUTION",
    }:
        blockers.append("EXECUTION_PERSISTENCE_DECISION_INVALID")
    for key in (
        "customer_id",
        "pilot_id",
        "requested_choice",
        "action_family",
        "execution_record_digest",
        "checkpoint_state_digest",
    ):
        if not _text(plan.get(key), 180):
            blockers.append("EXECUTION_PERSISTENCE_FIELD_REQUIRED:" + key)
    if not _SHA256_RE.fullmatch(
        _text(plan.get("execution_record_digest"), 180)
    ):
        blockers.append("EXECUTION_RECORD_DIGEST_INVALID")
    if not _SHA256_RE.fullmatch(
        _text(plan.get("checkpoint_state_digest"), 180)
    ):
        blockers.append("EXECUTION_CHECKPOINT_STATE_DIGEST_INVALID")

    patch = (
        dict(plan.get("patch_candidate"))
        if isinstance(plan.get("patch_candidate"), Mapping)
        else {}
    )
    if patch.get("schema") != PATCH_SCHEMA:
        blockers.append("EXECUTION_PATCH_SCHEMA_INVALID")
    if patch.get("state") != "PATCH_CANDIDATE":
        blockers.append("EXECUTION_PATCH_STATE_INVALID")
    if patch.get("expected_state_digest") != plan.get(
        "checkpoint_state_digest"
    ):
        blockers.append("EXECUTION_PATCH_STATE_DIGEST_MISMATCH")
    if not isinstance(patch.get("expected_revision"), int) or isinstance(
        patch.get("expected_revision"), bool
    ):
        blockers.append("EXECUTION_PATCH_REVISION_INVALID")
    if not _text(patch.get("recommended_event_id"), 160):
        blockers.append("EXECUTION_PATCH_EVENT_ID_REQUIRED")

    patch_body = (
        dict(patch.get("patch"))
        if isinstance(patch.get("patch"), Mapping)
        else {}
    )
    if set(patch_body) != {NAMESPACE}:
        blockers.append("EXECUTION_PATCH_NAMESPACE_INVALID")
    record = (
        dict(patch_body.get(NAMESPACE))
        if isinstance(patch_body.get(NAMESPACE), Mapping)
        else {}
    )
    if record.get("schema") != EXECUTION_SCHEMA:
        blockers.append("EXECUTION_PATCH_RECORD_SCHEMA_INVALID")
    if record.get("execution_decision") != decision:
        blockers.append("EXECUTION_PATCH_RECORD_DECISION_MISMATCH")
    if record.get("execution_record_persisted") is not False:
        blockers.append("EXECUTION_PATCH_RECORD_ALREADY_PERSISTED")
    if record.get("execution_command_generated") is not False:
        blockers.append("EXECUTION_PATCH_COMMAND_GENERATED_UNSAFE")
    if record.get("execution_command_executed") is not False:
        blockers.append("EXECUTION_PATCH_COMMAND_EXECUTED_UNSAFE")
    if record.get("execution_record_digest") != plan.get(
        "execution_record_digest"
    ):
        blockers.append("EXECUTION_PATCH_RECORD_DIGEST_MISMATCH")
    for key in _AUTHORITY_FIELDS:
        if record.get(key) is not False:
            blockers.append("EXECUTION_PATCH_RECORD_UNSAFE_FIELD:" + key)

    supplied_patch_digest = _text(patch.get("patch_digest"), 180)
    if not _SHA256_RE.fullmatch(supplied_patch_digest):
        blockers.append("EXECUTION_PATCH_DIGEST_INVALID")
    elif patch_body and supplied_patch_digest != _digest(patch_body):
        blockers.append("EXECUTION_PATCH_DIGEST_MISMATCH")
    return plan, patch, record, list(dict.fromkeys(blockers))


def verify_owner_execution_record_persistence(
    *,
    persistence_plan: Mapping[str, Any] | None,
    prior_checkpoint_master: Mapping[str, Any] | None,
    observed_checkpoint_master: Mapping[str, Any] | None,
    checkpoint_write_receipt: Mapping[str, Any] | None,
    now_ts: str,
) -> dict[str, Any]:
    plan, patch, record, blockers = _validate_plan(persistence_plan)

    try:
        prior = reconstruct_checkpoint(prior_checkpoint_master or {})
    except Exception:
        prior = None
        blockers.append("PRIOR_CHECKPOINT_INVALID")
    try:
        observed = reconstruct_checkpoint(observed_checkpoint_master or {})
    except Exception:
        observed = None
        blockers.append("OBSERVED_CHECKPOINT_INVALID")

    observed_master = (
        dict(observed_checkpoint_master)
        if isinstance(observed_checkpoint_master, Mapping)
        else {}
    )
    journal = (
        list(observed_master.get("journal"))
        if isinstance(observed_master.get("journal"), list)
        else []
    )
    observed_event = (
        dict(journal[-1])
        if journal and isinstance(journal[-1], Mapping)
        else {}
    )

    if prior is not None:
        if prior["revision"] != patch.get("expected_revision"):
            blockers.append("PRIOR_CHECKPOINT_REVISION_MISMATCH")
        if prior["state_digest"] != patch.get("expected_state_digest"):
            blockers.append("PRIOR_CHECKPOINT_STATE_DIGEST_MISMATCH")

    expected = None
    if prior is not None and not blockers:
        try:
            expected = append_checkpoint_patch(
                prior_checkpoint_master or {},
                event_id=patch["recommended_event_id"],
                patch=patch["patch"],
                expected_revision=patch["expected_revision"],
                created_at=_text(observed_event.get("created_at"), 80),
                evidence_refs=[
                    plan["execution_record_digest"],
                    plan["customer_id"],
                    plan["pilot_id"],
                    plan["requested_choice"],
                    plan["action_family"],
                    plan["execution_decision"],
                ],
            )
        except Exception:
            blockers.append("EXPECTED_CHECKPOINT_SIMULATION_FAILED")

    if expected is not None and observed is not None:
        if checkpoint_master_digest(expected) != checkpoint_master_digest(
            observed_checkpoint_master or {}
        ):
            blockers.append("OBSERVED_CHECKPOINT_DIGEST_MISMATCH")
        if observed["revision"] != prior["revision"] + 1:
            blockers.append("OBSERVED_CHECKPOINT_REVISION_MISMATCH")
        if not journal:
            blockers.append("OBSERVED_CHECKPOINT_EVENT_MISSING")
        elif observed_event != expected["journal"][-1]:
            blockers.append("OBSERVED_CHECKPOINT_EVENT_MISMATCH")
        if observed["snapshot"].get(NAMESPACE) != record:
            blockers.append("OBSERVED_EXECUTION_RECORD_MISMATCH")

    receipt = (
        dict(checkpoint_write_receipt)
        if isinstance(checkpoint_write_receipt, Mapping)
        else {}
    )
    if not receipt:
        blockers.append("CHECKPOINT_WRITE_RECEIPT_REQUIRED")
    else:
        exact = {
            "schema": RECEIPT_SCHEMA,
            "status": "CONFIRMED",
            "storage_target": "CHECKPOINT_MASTER",
            "write_mode": "EXPLICIT_AUTHORIZED_APPEND",
            "namespace": NAMESPACE,
            "event_id": patch.get("recommended_event_id"),
            "patch_digest": patch.get("patch_digest"),
            "execution_record_digest": plan.get("execution_record_digest"),
            "customer_id": plan.get("customer_id"),
            "pilot_id": plan.get("pilot_id"),
            "requested_choice": plan.get("requested_choice"),
            "action_family": plan.get("action_family"),
            "execution_decision": plan.get("execution_decision"),
        }
        for key, expected_value in exact.items():
            if receipt.get(key) != expected_value:
                blockers.append("EXECUTION_RECEIPT_MISMATCH:" + key)
        if prior is not None:
            if receipt.get("base_revision") != prior["revision"]:
                blockers.append("EXECUTION_RECEIPT_BASE_REVISION_MISMATCH")
            if receipt.get(
                "before_checkpoint_digest"
            ) != checkpoint_master_digest(prior_checkpoint_master or {}):
                blockers.append("EXECUTION_RECEIPT_BEFORE_DIGEST_MISMATCH")
        if observed is not None:
            if receipt.get("revision") != observed["revision"]:
                blockers.append("EXECUTION_RECEIPT_REVISION_MISMATCH")
            if receipt.get(
                "after_checkpoint_digest"
            ) != checkpoint_master_digest(observed_checkpoint_master or {}):
                blockers.append("EXECUTION_RECEIPT_AFTER_DIGEST_MISMATCH")
        for key in (
            "writer_identity_verified",
            "execution_command_generated",
            "execution_command_executed",
            "business_action_authorized",
            "external_action_executed",
        ):
            if receipt.get(key) is not False:
                blockers.append("EXECUTION_RECEIPT_UNSAFE_FIELD:" + key)
        if not _text(receipt.get("writer_ref"), 240):
            blockers.append("EXECUTION_RECEIPT_WRITER_REF_REQUIRED")
        supplied = _text(receipt.get("receipt_digest"), 180)
        body = {k: v for k, v in receipt.items() if k != "receipt_digest"}
        if not _SHA256_RE.fullmatch(supplied):
            blockers.append("EXECUTION_RECEIPT_DIGEST_INVALID")
        elif supplied != _digest(body):
            blockers.append("EXECUTION_RECEIPT_DIGEST_MISMATCH")
        try:
            persisted_at = _parse_ts(receipt.get("persisted_at"))
            now = _parse_ts(now_ts)
        except ValueError:
            blockers.append("EXECUTION_RECEIPT_TIME_INVALID")
        else:
            age = (now - persisted_at).total_seconds()
            if age < 0:
                blockers.append("EXECUTION_RECEIPT_FROM_FUTURE")
            elif age > MAX_RECEIPT_AGE_SECONDS:
                blockers.append("EXECUTION_RECEIPT_TOO_OLD")

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return _blocked(*blockers)

    authorize = (
        plan["execution_decision"]
        == "AUTHORIZE_BUSINESS_ACTION_EXECUTION"
    )
    return {
        "schema": SCHEMA,
        "state": "OWNER_RENEWAL_ACTION_EXECUTION_RECORD_PERSISTENCE_ATTESTED",
        "blockers": [],
        "execution_decision": plan["execution_decision"],
        "requested_choice": plan["requested_choice"],
        "action_family": plan["action_family"],
        "scope": {
            "owner_id": plan["owner_id"],
            "tenant_id": plan["tenant_id"],
            "workspace_id": plan["workspace_id"],
        },
        "owner_id": plan["owner_id"],
        "tenant_id": plan["tenant_id"],
        "workspace_id": plan["workspace_id"],
        "customer_id": plan["customer_id"],
        "pilot_id": plan["pilot_id"],
        "package": plan["package"],
        "review_type": plan["review_type"],
        **{
            key: _text(record.get(key), 180)
            for key in _LINEAGE_DIGEST_FIELDS
        },
        "execution_record_digest": plan["execution_record_digest"],
        "checkpoint_revision": observed["revision"],
        "checkpoint_state_digest": observed["state_digest"],
        "before_checkpoint_digest": checkpoint_master_digest(
            prior_checkpoint_master or {}
        ),
        "after_checkpoint_digest": checkpoint_master_digest(
            observed_checkpoint_master or {}
        ),
        "receipt_digest": receipt["receipt_digest"],
        "execution_record_persisted": True,
        "persistence_attested": True,
        "receipt_consistency_verified": True,
        "writer_identity_verified": False,
        "eligible_for_command_planning": bool(authorize),
        "storage_write_performed": False,
        "execution_command_generated": False,
        "execution_command_executed": False,
        **{key: False for key in _AUTHORITY_FIELDS},
    }


__all__ = [
    "SCHEMA",
    "RECEIPT_SCHEMA",
    "MAX_RECEIPT_AGE_SECONDS",
    "build_owner_execution_checkpoint_receipt_body",
    "verify_owner_execution_record_persistence",
]
