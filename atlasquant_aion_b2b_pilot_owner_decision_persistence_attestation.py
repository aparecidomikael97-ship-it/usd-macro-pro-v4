"""AION B2B Pilot Owner Decision Persistence Attestation V1.

Pure/offline verifier for a B2B pilot owner-decision Checkpoint Master write.

This module never performs storage I/O. It:
- validates the previously prepared persistence plan;
- reconstructs the prior Checkpoint Master;
- computes the exact expected post-write master in memory;
- compares it against an externally supplied observed master;
- validates an externally supplied consistency receipt;
- attests only the persistence of the exact decision record.

Even an attested APPROVE_PILOT does not authorize or activate the pilot.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping
import json
import re

from atlasquant_aion_checkpoint_master import (
    append_checkpoint_patch,
    checkpoint_master_digest,
    reconstruct_checkpoint,
)

SCHEMA = "ATLASQUANT_AION_B2B_PILOT_OWNER_DECISION_PERSISTENCE_ATTESTATION_V1"
PLAN_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_OWNER_DECISION_PERSISTENCE_PLAN_V1"
PATCH_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_OWNER_DECISION_CHECKPOINT_PATCH_V1"
DECISION_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_OWNER_DECISION_VERIFICATION_V1"
RECEIPT_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_DECISION_CHECKPOINT_RECEIPT_V1"
NAMESPACE = "aion_b2b_pilot_owner_decision"
MAX_RECEIPT_AGE_SECONDS = 300

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
        "decision_record_persisted": False,
        "persistence_attested": False,
        "receipt_consistency_verified": False,
        "writer_identity_verified": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "customer_contact_authorized": False,
        "contract_signature_authorized": False,
        "billing_authorized": False,
        "spend_authorized": False,
        "deploy_authorized": False,
        "crm_write_authorized": False,
        "production_mutation_authorized": False,
        "storage_write_performed": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
    }


def build_checkpoint_write_receipt_body(
    *,
    persistence_plan: Mapping[str, Any] | None,
    prior_checkpoint_master: Mapping[str, Any] | None,
    observed_checkpoint_master: Mapping[str, Any] | None,
    persisted_at: str,
    writer_ref: str,
) -> dict[str, Any]:
    """Build deterministic receipt material only; does not write or attest it."""
    plan = (
        dict(persistence_plan)
        if isinstance(persistence_plan, Mapping)
        else {}
    )
    patch_candidate = (
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
        "event_id": _text(
            patch_candidate.get("recommended_event_id"),
            160,
        ),
        "base_revision": prior["revision"],
        "revision": observed["revision"],
        "patch_digest": _text(
            patch_candidate.get("patch_digest"),
            180,
        ),
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
        "pilot_id": _text(plan.get("pilot_id"), 120),
        "persisted_at": _text(persisted_at, 80),
        "writer_ref": _text(writer_ref, 240),
        "writer_identity_verified": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "external_action_executed": False,
    }
    return {
        **body,
        "receipt_digest": _digest(body),
    }


def _plan_blockers(
    persistence_plan: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
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
    if plan.get("decision_record_persisted") is not False:
        blockers.append("PERSISTENCE_PLAN_ALREADY_PERSISTED")
    if plan.get("checkpoint_saved") is not False:
        blockers.append("PERSISTENCE_PLAN_ALREADY_SAVED")
    if plan.get("automatic_checkpoint_write") is not False:
        blockers.append("PERSISTENCE_PLAN_AUTO_WRITE_UNSAFE")
    if plan.get("pilot_activation_authorized") is not False:
        blockers.append("PERSISTENCE_PLAN_ACTIVATION_UNSAFE")
    if plan.get("pilot_activated") is not False:
        blockers.append("PERSISTENCE_PLAN_ACTIVE_UNSAFE")
    if plan.get("requires_explicit_checkpoint_save") is not True:
        blockers.append("PERSISTENCE_PLAN_EXPLICIT_SAVE_BOUNDARY_MISSING")
    if plan.get("requires_persistence_attestation") is not True:
        blockers.append("PERSISTENCE_PLAN_ATTESTATION_BOUNDARY_MISSING")
    if plan.get("external_action_executed") is not False:
        blockers.append("PERSISTENCE_PLAN_EXTERNAL_ACTION_UNSAFE")
    if plan.get("network_called") is not False:
        blockers.append("PERSISTENCE_PLAN_NETWORK_UNSAFE")
    if plan.get("executes_action") is not False:
        blockers.append("PERSISTENCE_PLAN_EXECUTION_UNSAFE")

    decision = _text(plan.get("decision"), 80)
    if decision not in {"APPROVE_PILOT", "DENY_PILOT"}:
        blockers.append("PERSISTENCE_PLAN_DECISION_INVALID")

    decision_record_digest = _text(
        plan.get("decision_record_digest"),
        180,
    )
    if not _SHA256_RE.fullmatch(decision_record_digest):
        blockers.append("PERSISTENCE_PLAN_DECISION_RECORD_DIGEST_INVALID")

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
    if patch.get("decision_record_persisted") is not False:
        blockers.append("PATCH_ALREADY_PERSISTED")
    if patch.get("pilot_activation_authorized") is not False:
        blockers.append("PATCH_ACTIVATION_UNSAFE")
    if patch.get("pilot_activated") is not False:
        blockers.append("PATCH_ACTIVE_UNSAFE")
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
        blockers.append("PATCH_DECISION_RECORD_SCHEMA_INVALID")
    if record.get("decision") != decision:
        blockers.append("PATCH_DECISION_CHOICE_MISMATCH")
    if record.get("decision_record_digest") != decision_record_digest:
        blockers.append("PATCH_DECISION_RECORD_DIGEST_MISMATCH")
    if record.get("owner_decision_verified") is not True:
        blockers.append("PATCH_DECISION_NOT_VERIFIED")
    if record.get("owner_decision_recorded") is not False:
        blockers.append("PATCH_DECISION_ALREADY_RECORDED")
    if record.get("decision_record_persisted") is not False:
        blockers.append("PATCH_DECISION_ALREADY_PERSISTED")
    if record.get("pilot_activation_authorized") is not False:
        blockers.append("PATCH_DECISION_ACTIVATION_UNSAFE")
    if record.get("pilot_activated") is not False:
        blockers.append("PATCH_DECISION_ACTIVE_UNSAFE")

    supplied_patch_digest = _text(patch.get("patch_digest"), 180)
    if not _SHA256_RE.fullmatch(supplied_patch_digest):
        blockers.append("PATCH_DIGEST_INVALID")
    elif patch_body and supplied_patch_digest != _digest(patch_body):
        blockers.append("PATCH_DIGEST_MISMATCH")

    pilot_id = _text(plan.get("pilot_id"), 120)
    if not pilot_id:
        blockers.append("PERSISTENCE_PLAN_PILOT_ID_REQUIRED")
    if record and _text(record.get("pilot_id"), 120) != pilot_id:
        blockers.append("PATCH_PILOT_ID_MISMATCH")

    return plan, patch, list(dict.fromkeys(blockers))


def _receipt_blockers(
    receipt: Mapping[str, Any] | None,
    *,
    plan: Mapping[str, Any],
    patch: Mapping[str, Any],
    prior_master: Mapping[str, Any],
    observed_master: Mapping[str, Any],
    now_ts: str,
) -> list[str]:
    row = dict(receipt) if isinstance(receipt, Mapping) else {}
    blockers: list[str] = []

    if row.get("schema") != RECEIPT_SCHEMA:
        blockers.append("CHECKPOINT_RECEIPT_SCHEMA_INVALID")
    if row.get("status") != "CONFIRMED":
        blockers.append("CHECKPOINT_RECEIPT_NOT_CONFIRMED")
    if row.get("storage_target") != "CHECKPOINT_MASTER":
        blockers.append("CHECKPOINT_RECEIPT_TARGET_INVALID")
    if row.get("write_mode") != "EXPLICIT_AUTHORIZED_APPEND":
        blockers.append("CHECKPOINT_RECEIPT_WRITE_MODE_INVALID")
    if row.get("namespace") != NAMESPACE:
        blockers.append("CHECKPOINT_RECEIPT_NAMESPACE_INVALID")
    if (
        row.get("event_id")
        != _text(patch.get("recommended_event_id"), 160)
    ):
        blockers.append("CHECKPOINT_RECEIPT_EVENT_ID_MISMATCH")
    if row.get("base_revision") != patch.get("expected_revision"):
        blockers.append("CHECKPOINT_RECEIPT_BASE_REVISION_MISMATCH")
    if row.get("revision") != patch.get("expected_revision") + 1:
        blockers.append("CHECKPOINT_RECEIPT_REVISION_MISMATCH")
    if row.get("patch_digest") != patch.get("patch_digest"):
        blockers.append("CHECKPOINT_RECEIPT_PATCH_DIGEST_MISMATCH")
    if (
        row.get("decision_record_digest")
        != plan.get("decision_record_digest")
    ):
        blockers.append(
            "CHECKPOINT_RECEIPT_DECISION_RECORD_DIGEST_MISMATCH"
        )
    if row.get("pilot_id") != plan.get("pilot_id"):
        blockers.append("CHECKPOINT_RECEIPT_PILOT_ID_MISMATCH")

    before_digest = checkpoint_master_digest(prior_master)
    after_digest = checkpoint_master_digest(observed_master)
    if row.get("before_checkpoint_digest") != before_digest:
        blockers.append("CHECKPOINT_RECEIPT_BEFORE_DIGEST_MISMATCH")
    if row.get("after_checkpoint_digest") != after_digest:
        blockers.append("CHECKPOINT_RECEIPT_AFTER_DIGEST_MISMATCH")

    writer_ref = _text(row.get("writer_ref"), 240)
    if not writer_ref:
        blockers.append("CHECKPOINT_RECEIPT_WRITER_REF_REQUIRED")
    if row.get("writer_identity_verified") is not False:
        blockers.append(
            "CHECKPOINT_RECEIPT_WRITER_IDENTITY_CLAIM_UNSUPPORTED"
        )
    if row.get("pilot_activation_authorized") is not False:
        blockers.append("CHECKPOINT_RECEIPT_ACTIVATION_UNSAFE")
    if row.get("pilot_activated") is not False:
        blockers.append("CHECKPOINT_RECEIPT_ACTIVE_UNSAFE")
    if row.get("external_action_executed") is not False:
        blockers.append("CHECKPOINT_RECEIPT_EXTERNAL_ACTION_UNSAFE")

    supplied_receipt_digest = _text(
        row.get("receipt_digest"),
        180,
    )
    body = {
        key: value
        for key, value in row.items()
        if key != "receipt_digest"
    }
    if not _SHA256_RE.fullmatch(supplied_receipt_digest):
        blockers.append("CHECKPOINT_RECEIPT_DIGEST_INVALID")
    elif supplied_receipt_digest != _digest(body):
        blockers.append("CHECKPOINT_RECEIPT_DIGEST_MISMATCH")

    try:
        persisted = _parse_ts(row.get("persisted_at"))
        now = _parse_ts(now_ts)
    except ValueError:
        blockers.append("CHECKPOINT_RECEIPT_TIME_INVALID")
    else:
        age = (now - persisted).total_seconds()
        if age < -5:
            blockers.append("CHECKPOINT_RECEIPT_FROM_FUTURE")
        elif age > MAX_RECEIPT_AGE_SECONDS:
            blockers.append("CHECKPOINT_RECEIPT_TOO_OLD")

    return list(dict.fromkeys(blockers))


def verify_pilot_owner_decision_persistence(
    *,
    persistence_plan: Mapping[str, Any] | None,
    prior_checkpoint_master: Mapping[str, Any] | None,
    observed_checkpoint_master: Mapping[str, Any] | None,
    checkpoint_write_receipt: Mapping[str, Any] | None,
    now_ts: str,
) -> dict[str, Any]:
    """Attest exact persistence without performing any storage write."""
    plan, patch, blockers = _plan_blockers(persistence_plan)

    prior_master = (
        dict(prior_checkpoint_master)
        if isinstance(prior_checkpoint_master, Mapping)
        else {}
    )
    observed_master = (
        dict(observed_checkpoint_master)
        if isinstance(observed_checkpoint_master, Mapping)
        else {}
    )

    try:
        prior = reconstruct_checkpoint(prior_master)
    except Exception:
        blockers.append("PRIOR_CHECKPOINT_MASTER_INVALID")
        prior = None

    try:
        observed = reconstruct_checkpoint(observed_master)
    except Exception:
        blockers.append("OBSERVED_CHECKPOINT_MASTER_INVALID")
        observed = None

    if prior is not None and patch:
        if prior["revision"] != patch.get("expected_revision"):
            blockers.append("PRIOR_CHECKPOINT_REVISION_MISMATCH")

    expected_master = None
    expected = None
    if not blockers and prior is not None:
        try:
            expected_master = append_checkpoint_patch(
                prior_master,
                event_id=patch["recommended_event_id"],
                patch=patch["patch"],
                expected_revision=patch["expected_revision"],
                created_at="1970-01-01T00:00:00+00:00",
                evidence_refs=[
                    _text(plan.get("decision_record_digest"), 180),
                    _text(plan.get("pilot_id"), 120),
                ],
            )
            expected = reconstruct_checkpoint(expected_master)
        except Exception:
            blockers.append("EXPECTED_CHECKPOINT_SIMULATION_FAILED")

    if expected is not None and observed is not None:
        if observed["revision"] != expected["revision"]:
            blockers.append("OBSERVED_CHECKPOINT_REVISION_MISMATCH")
        if observed["snapshot"] != expected["snapshot"]:
            blockers.append("OBSERVED_CHECKPOINT_SNAPSHOT_MISMATCH")

        expected_event = dict(expected_master.get("journal", [])[-1])
        observed_journal = list(observed_master.get("journal", []))
        if not observed_journal:
            blockers.append("OBSERVED_CHECKPOINT_EVENT_MISSING")
        else:
            actual_event = dict(observed_journal[-1])
            for key in (
                "event_id",
                "base_revision",
                "revision",
                "event_type",
                "patch",
                "patch_digest",
                "evidence_refs",
            ):
                if actual_event.get(key) != expected_event.get(key):
                    blockers.append(
                        "OBSERVED_CHECKPOINT_EVENT_MISMATCH:" + key
                    )

    if (
        prior is not None
        and observed is not None
        and isinstance(checkpoint_write_receipt, Mapping)
    ):
        blockers.extend(
            _receipt_blockers(
                checkpoint_write_receipt,
                plan=plan,
                patch=patch,
                prior_master=prior_master,
                observed_master=observed_master,
                now_ts=now_ts,
            )
        )
    elif not isinstance(checkpoint_write_receipt, Mapping):
        blockers.append("CHECKPOINT_WRITE_RECEIPT_REQUIRED")

    blockers = list(dict.fromkeys(blockers))
    if blockers or observed is None:
        return _blocked(*blockers)

    snapshot = dict(observed["snapshot"])
    persisted_record = (
        dict(snapshot.get(NAMESPACE))
        if isinstance(snapshot.get(NAMESPACE), Mapping)
        else {}
    )
    expected_record = dict(patch["patch"][NAMESPACE])
    if persisted_record != expected_record:
        return _blocked("PERSISTED_DECISION_RECORD_MISMATCH")

    decision = _text(plan.get("decision"), 80)
    approved = decision == "APPROVE_PILOT"
    denied = decision == "DENY_PILOT"

    attestation_material = {
        "decision": decision,
        "pilot_id": plan["pilot_id"],
        "decision_record_digest": plan["decision_record_digest"],
        "patch_digest": patch["patch_digest"],
        "checkpoint_revision": observed["revision"],
        "checkpoint_state_digest": observed["state_digest"],
        "checkpoint_master_digest": checkpoint_master_digest(
            observed_master
        ),
        "receipt_digest": checkpoint_write_receipt["receipt_digest"],
    }

    return {
        "schema": SCHEMA,
        "state": (
            "DECISION_RECORD_PERSISTENCE_ATTESTED_APPROVE"
            if approved
            else "DECISION_RECORD_PERSISTENCE_ATTESTED_DENY"
        ),
        "blockers": [],
        "decision": decision,
        "pilot_id": plan["pilot_id"],
        "decision_record_digest": plan["decision_record_digest"],
        "checkpoint_revision": observed["revision"],
        "checkpoint_state_digest": observed["state_digest"],
        "checkpoint_master_digest": checkpoint_master_digest(
            observed_master
        ),
        "receipt_digest": checkpoint_write_receipt["receipt_digest"],
        "attestation_digest": _digest(attestation_material),
        "owner_decision_recorded": True,
        "decision_record_persisted": True,
        "persistence_attested": True,
        "receipt_consistency_verified": True,
        "writer_identity_verified": False,
        "pilot_approved": approved,
        "pilot_denied": denied,
        "eligible_for_activation_ceremony": bool(approved),
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "customer_contact_authorized": False,
        "contract_signature_authorized": False,
        "billing_authorized": False,
        "spend_authorized": False,
        "deploy_authorized": False,
        "crm_write_authorized": False,
        "production_mutation_authorized": False,
        "storage_write_performed": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "PLAN_SCHEMA",
    "PATCH_SCHEMA",
    "DECISION_SCHEMA",
    "RECEIPT_SCHEMA",
    "NAMESPACE",
    "MAX_RECEIPT_AGE_SECONDS",
    "build_checkpoint_write_receipt_body",
    "verify_pilot_owner_decision_persistence",
]
