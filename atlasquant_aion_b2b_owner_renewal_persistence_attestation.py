"""AION B2B owner-renewal decision persistence attestation.

Pure/offline verifier for an externally performed Checkpoint Master append.

This module does not write storage. It verifies that the exact decision record
prepared by the persistence plan was appended to the exact expected checkpoint,
and that an external consistency receipt matches that append. Persistence is not
business-action authorization.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_b2b_owner_renewal_persistence_plan import (
    DECISION_SCHEMA,
    NAMESPACE,
    PATCH_SCHEMA,
    SCHEMA as PLAN_SCHEMA,
)
from atlasquant_aion_checkpoint_master import (
    append_checkpoint_patch,
    checkpoint_master_digest,
    reconstruct_checkpoint,
)

SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_PERSISTENCE_ATTESTATION_V1"
RECEIPT_SCHEMA = (
    "ATLASQUANT_AION_B2B_OWNER_RENEWAL_CHECKPOINT_RECEIPT_V1"
)
MAX_RECEIPT_AGE_SECONDS = 300

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

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
        "owner_decision_recorded": False,
        "decision_persisted": False,
        "persistence_attested": False,
        "receipt_consistency_verified": False,
        "writer_identity_verified": False,
        "eligible_for_action_preflight": False,
        "storage_write_performed": False,
        "network_called": False,
        **{key: False for key in _AUTHORIZATION_FIELDS},
    }


def build_owner_renewal_checkpoint_receipt_body(
    *,
    persistence_plan: Mapping[str, Any] | None,
    prior_checkpoint_master: Mapping[str, Any] | None,
    observed_checkpoint_master: Mapping[str, Any] | None,
    persisted_at: str,
    writer_ref: str,
) -> dict[str, Any]:
    """Build deterministic receipt material only; performs no storage write."""
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
        "decision_record_digest": _text(
            plan.get("decision_record_digest"),
            180,
        ),
        "customer_id": _text(plan.get("customer_id"), 120),
        "pilot_id": _text(plan.get("pilot_id"), 120),
        "requested_choice": _text(plan.get("requested_choice"), 120),
        "persisted_at": _text(persisted_at, 80),
        "writer_ref": _text(writer_ref, 240),
        "writer_identity_verified": False,
        "business_action_authorized": False,
        "external_action_executed": False,
    }
    return {
        **body,
        "receipt_digest": _digest(body),
    }


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
        blockers.append("PERSISTENCE_PLAN_SCHEMA_INVALID")
    if plan.get("state") != "READY_FOR_EXPLICIT_CHECKPOINT_PERSISTENCE":
        blockers.append("PERSISTENCE_PLAN_NOT_READY")
    if plan.get("owner_decision_recorded") is not False:
        blockers.append("PERSISTENCE_PLAN_DECISION_ALREADY_RECORDED")
    if plan.get("decision_persisted") is not False:
        blockers.append("PERSISTENCE_PLAN_ALREADY_PERSISTED")
    if plan.get("checkpoint_saved") is not False:
        blockers.append("PERSISTENCE_PLAN_ALREADY_SAVED")
    if plan.get("automatic_checkpoint_write") is not False:
        blockers.append("PERSISTENCE_PLAN_AUTO_WRITE_UNSAFE")
    if plan.get("requires_explicit_checkpoint_save") is not True:
        blockers.append("PERSISTENCE_PLAN_EXPLICIT_SAVE_BOUNDARY_MISSING")
    if plan.get("requires_persistence_attestation") is not True:
        blockers.append("PERSISTENCE_PLAN_ATTESTATION_BOUNDARY_MISSING")

    for key in _AUTHORIZATION_FIELDS:
        if plan.get(key) is not False:
            blockers.append("PERSISTENCE_PLAN_UNSAFE_FIELD:" + key)

    choice = _text(plan.get("requested_choice"), 120)
    customer_id = _text(plan.get("customer_id"), 120)
    pilot_id = _text(plan.get("pilot_id"), 120)
    record_digest = _text(plan.get("decision_record_digest"), 180)
    checkpoint_digest = _text(plan.get("checkpoint_state_digest"), 180)

    if not choice:
        blockers.append("PERSISTENCE_PLAN_CHOICE_REQUIRED")
    if not customer_id:
        blockers.append("PERSISTENCE_PLAN_CUSTOMER_ID_REQUIRED")
    if not pilot_id:
        blockers.append("PERSISTENCE_PLAN_PILOT_ID_REQUIRED")
    if not _SHA256_RE.fullmatch(record_digest):
        blockers.append("PERSISTENCE_PLAN_RECORD_DIGEST_INVALID")
    if not _SHA256_RE.fullmatch(checkpoint_digest):
        blockers.append("PERSISTENCE_PLAN_CHECKPOINT_DIGEST_INVALID")

    patch = (
        dict(plan.get("patch_candidate"))
        if isinstance(plan.get("patch_candidate"), Mapping)
        else {}
    )
    if patch.get("schema") != PATCH_SCHEMA:
        blockers.append("PATCH_CANDIDATE_SCHEMA_INVALID")
    if patch.get("state") != "PATCH_CANDIDATE":
        blockers.append("PATCH_CANDIDATE_STATE_INVALID")
    if patch.get("requires_explicit_checkpoint_save") is not True:
        blockers.append("PATCH_EXPLICIT_SAVE_BOUNDARY_MISSING")
    if patch.get("requires_persistence_attestation") is not True:
        blockers.append("PATCH_ATTESTATION_BOUNDARY_MISSING")
    if patch.get("automatic_checkpoint_write") is not False:
        blockers.append("PATCH_AUTO_WRITE_UNSAFE")
    if patch.get("checkpoint_saved") is not False:
        blockers.append("PATCH_ALREADY_SAVED")
    if patch.get("owner_decision_recorded") is not False:
        blockers.append("PATCH_DECISION_ALREADY_RECORDED")
    if patch.get("decision_persisted") is not False:
        blockers.append("PATCH_ALREADY_PERSISTED")
    if patch.get("business_action_authorized") is not False:
        blockers.append("PATCH_BUSINESS_ACTION_AUTHORITY_UNSAFE")
    if patch.get("external_action_executed") is not False:
        blockers.append("PATCH_EXTERNAL_ACTION_UNSAFE")
    if patch.get("executes_action") is not False:
        blockers.append("PATCH_EXECUTION_UNSAFE")

    expected_revision = patch.get("expected_revision")
    if (
        isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision < 0
    ):
        blockers.append("PATCH_EXPECTED_REVISION_INVALID")
    if patch.get("expected_state_digest") != checkpoint_digest:
        blockers.append("PATCH_EXPECTED_STATE_DIGEST_MISMATCH")

    event_id = _text(patch.get("recommended_event_id"), 160)
    if not event_id:
        blockers.append("PATCH_EVENT_ID_REQUIRED")

    patch_body = (
        dict(patch.get("patch"))
        if isinstance(patch.get("patch"), Mapping)
        else {}
    )
    if set(patch_body) != {NAMESPACE}:
        blockers.append("PATCH_NAMESPACE_INVALID")

    record = (
        dict(patch_body.get(NAMESPACE))
        if isinstance(patch_body.get(NAMESPACE), Mapping)
        else {}
    )
    if record.get("schema") != DECISION_SCHEMA:
        blockers.append("PATCH_RECORD_SCHEMA_INVALID")
    if record.get("requested_choice") != choice:
        blockers.append("PATCH_RECORD_CHOICE_MISMATCH")
    if _text(record.get("customer_id"), 120) != customer_id:
        blockers.append("PATCH_RECORD_CUSTOMER_MISMATCH")
    if _text(record.get("pilot_id"), 120) != pilot_id:
        blockers.append("PATCH_RECORD_PILOT_MISMATCH")
    if record.get("decision_record_digest") != record_digest:
        blockers.append("PATCH_RECORD_DIGEST_MISMATCH")
    if record.get("owner_signature_verified") is not True:
        blockers.append("PATCH_RECORD_SIGNATURE_NOT_VERIFIED")
    if record.get("owner_decision_verified") is not True:
        blockers.append("PATCH_RECORD_DECISION_NOT_VERIFIED")
    if record.get("owner_decision_recorded") is not False:
        blockers.append("PATCH_RECORD_ALREADY_RECORDED")
    if record.get("decision_persisted") is not False:
        blockers.append("PATCH_RECORD_ALREADY_PERSISTED")
    if record.get("business_action_authorized") is not False:
        blockers.append("PATCH_RECORD_BUSINESS_ACTION_UNSAFE")
    if record.get("external_action_executed") is not False:
        blockers.append("PATCH_RECORD_EXTERNAL_ACTION_UNSAFE")
    if record.get("executes_action") is not False:
        blockers.append("PATCH_RECORD_EXECUTION_UNSAFE")

    supplied_patch_digest = _text(patch.get("patch_digest"), 180)
    if not _SHA256_RE.fullmatch(supplied_patch_digest):
        blockers.append("PATCH_DIGEST_INVALID")
    elif patch_body and supplied_patch_digest != _digest(patch_body):
        blockers.append("PATCH_DIGEST_MISMATCH")

    return plan, patch, record, list(dict.fromkeys(blockers))


def verify_owner_renewal_decision_persistence(
    *,
    persistence_plan: Mapping[str, Any] | None,
    prior_checkpoint_master: Mapping[str, Any] | None,
    observed_checkpoint_master: Mapping[str, Any] | None,
    checkpoint_write_receipt: Mapping[str, Any] | None,
    now_ts: str,
) -> dict[str, Any]:
    """Verify exact persistence while keeping all business actions unauthorized."""
    plan, patch, record, blockers = _validate_plan(persistence_plan)

    try:
        prior = reconstruct_checkpoint(prior_checkpoint_master or {})
    except Exception:
        blockers.append("PRIOR_CHECKPOINT_INVALID")
        prior = None
    try:
        observed = reconstruct_checkpoint(observed_checkpoint_master or {})
    except Exception:
        blockers.append("OBSERVED_CHECKPOINT_INVALID")
        observed = None

    expected = None
    if prior is not None:
        if prior["revision"] != patch.get("expected_revision"):
            blockers.append("PRIOR_CHECKPOINT_REVISION_MISMATCH")
        if prior["state_digest"] != patch.get("expected_state_digest"):
            blockers.append("PRIOR_CHECKPOINT_STATE_DIGEST_MISMATCH")

    observed_master = (
        dict(observed_checkpoint_master)
        if isinstance(observed_checkpoint_master, Mapping)
        else {}
    )
    observed_journal = (
        list(observed_master.get("journal"))
        if isinstance(observed_master.get("journal"), list)
        else []
    )
    observed_event = (
        dict(observed_journal[-1])
        if observed_journal and isinstance(observed_journal[-1], Mapping)
        else {}
    )

    if prior is not None and not blockers:
        try:
            expected = append_checkpoint_patch(
                prior_checkpoint_master or {},
                event_id=patch["recommended_event_id"],
                patch=patch["patch"],
                expected_revision=patch["expected_revision"],
                created_at=_text(observed_event.get("created_at"), 80),
                evidence_refs=[
                    plan["decision_record_digest"],
                    plan["customer_id"],
                    plan["pilot_id"],
                    plan["requested_choice"],
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
        if not observed_journal:
            blockers.append("OBSERVED_CHECKPOINT_EVENT_MISSING")
        else:
            expected_event = expected["journal"][-1]
            if observed_event != expected_event:
                blockers.append("OBSERVED_CHECKPOINT_EVENT_MISMATCH")
        observed_record = (
            observed["snapshot"].get(NAMESPACE)
            if isinstance(observed["snapshot"], Mapping)
            else None
        )
        if observed_record != record:
            blockers.append("OBSERVED_DECISION_RECORD_MISMATCH")

    receipt = (
        dict(checkpoint_write_receipt)
        if isinstance(checkpoint_write_receipt, Mapping)
        else {}
    )
    if not receipt:
        blockers.append("CHECKPOINT_WRITE_RECEIPT_REQUIRED")
    else:
        if receipt.get("schema") != RECEIPT_SCHEMA:
            blockers.append("CHECKPOINT_RECEIPT_SCHEMA_INVALID")
        if receipt.get("status") != "CONFIRMED":
            blockers.append("CHECKPOINT_RECEIPT_NOT_CONFIRMED")
        if receipt.get("storage_target") != "CHECKPOINT_MASTER":
            blockers.append("CHECKPOINT_RECEIPT_STORAGE_TARGET_INVALID")
        if receipt.get("write_mode") != "EXPLICIT_AUTHORIZED_APPEND":
            blockers.append("CHECKPOINT_RECEIPT_WRITE_MODE_INVALID")
        if receipt.get("namespace") != NAMESPACE:
            blockers.append("CHECKPOINT_RECEIPT_NAMESPACE_MISMATCH")
        if (
            receipt.get("event_id")
            != patch.get("recommended_event_id")
        ):
            blockers.append("CHECKPOINT_RECEIPT_EVENT_ID_MISMATCH")
        if prior is not None and receipt.get("base_revision") != prior["revision"]:
            blockers.append("CHECKPOINT_RECEIPT_BASE_REVISION_MISMATCH")
        if observed is not None and receipt.get("revision") != observed["revision"]:
            blockers.append("CHECKPOINT_RECEIPT_REVISION_MISMATCH")
        if receipt.get("patch_digest") != patch.get("patch_digest"):
            blockers.append("CHECKPOINT_RECEIPT_PATCH_DIGEST_MISMATCH")
        if receipt.get("decision_record_digest") != plan.get(
            "decision_record_digest"
        ):
            blockers.append(
                "CHECKPOINT_RECEIPT_DECISION_RECORD_DIGEST_MISMATCH"
            )
        if receipt.get("customer_id") != plan.get("customer_id"):
            blockers.append("CHECKPOINT_RECEIPT_CUSTOMER_MISMATCH")
        if receipt.get("pilot_id") != plan.get("pilot_id"):
            blockers.append("CHECKPOINT_RECEIPT_PILOT_MISMATCH")
        if receipt.get("requested_choice") != plan.get("requested_choice"):
            blockers.append("CHECKPOINT_RECEIPT_CHOICE_MISMATCH")
        if (
            receipt.get("writer_identity_verified") is not False
        ):
            blockers.append(
                "CHECKPOINT_RECEIPT_WRITER_IDENTITY_CLAIM_UNSUPPORTED"
            )
        if receipt.get("business_action_authorized") is not False:
            blockers.append("CHECKPOINT_RECEIPT_ACTION_AUTHORITY_UNSAFE")
        if receipt.get("external_action_executed") is not False:
            blockers.append("CHECKPOINT_RECEIPT_EXTERNAL_ACTION_UNSAFE")

        if prior is not None:
            before_digest = checkpoint_master_digest(
                prior_checkpoint_master or {}
            )
            if receipt.get("before_checkpoint_digest") != before_digest:
                blockers.append("CHECKPOINT_RECEIPT_BEFORE_DIGEST_MISMATCH")
        if observed is not None:
            after_digest = checkpoint_master_digest(
                observed_checkpoint_master or {}
            )
            if receipt.get("after_checkpoint_digest") != after_digest:
                blockers.append("CHECKPOINT_RECEIPT_AFTER_DIGEST_MISMATCH")

        supplied_receipt_digest = _text(
            receipt.get("receipt_digest"),
            180,
        )
        receipt_body = {
            key: value
            for key, value in receipt.items()
            if key != "receipt_digest"
        }
        if not _SHA256_RE.fullmatch(supplied_receipt_digest):
            blockers.append("CHECKPOINT_RECEIPT_DIGEST_INVALID")
        elif supplied_receipt_digest != _digest(receipt_body):
            blockers.append("CHECKPOINT_RECEIPT_DIGEST_MISMATCH")

        if not _text(receipt.get("writer_ref"), 240):
            blockers.append("CHECKPOINT_RECEIPT_WRITER_REF_REQUIRED")
        try:
            persisted_at = _parse_ts(receipt.get("persisted_at"))
            now = _parse_ts(now_ts)
        except ValueError:
            blockers.append("CHECKPOINT_RECEIPT_TIME_INVALID")
        else:
            age = (now - persisted_at).total_seconds()
            if age < 0:
                blockers.append("CHECKPOINT_RECEIPT_FROM_FUTURE")
            elif age > MAX_RECEIPT_AGE_SECONDS:
                blockers.append("CHECKPOINT_RECEIPT_TOO_OLD")

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return _blocked(*blockers)

    return {
        "schema": SCHEMA,
        "state": "OWNER_RENEWAL_DECISION_PERSISTENCE_ATTESTED",
        "blockers": [],
        "requested_choice": plan["requested_choice"],
        "customer_id": plan["customer_id"],
        "pilot_id": plan["pilot_id"],
        "decision_record_digest": plan["decision_record_digest"],
        "checkpoint_revision": observed["revision"],
        "checkpoint_state_digest": observed["state_digest"],
        "before_checkpoint_digest": checkpoint_master_digest(
            prior_checkpoint_master or {}
        ),
        "after_checkpoint_digest": checkpoint_master_digest(
            observed_checkpoint_master or {}
        ),
        "receipt_digest": receipt["receipt_digest"],
        "owner_decision_recorded": True,
        "decision_persisted": True,
        "persistence_attested": True,
        "receipt_consistency_verified": True,
        "writer_identity_verified": False,
        "eligible_for_action_preflight": True,
        "storage_write_performed": False,
        "network_called": False,
        **{key: False for key in _AUTHORIZATION_FIELDS},
    }


__all__ = [
    "SCHEMA",
    "RECEIPT_SCHEMA",
    "MAX_RECEIPT_AGE_SECONDS",
    "build_owner_renewal_checkpoint_receipt_body",
    "verify_owner_renewal_decision_persistence",
]
