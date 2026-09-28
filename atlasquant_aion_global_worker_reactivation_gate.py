"""AION Global Worker Post-Incident Reactivation Safety Gate V1.

Read-only safety gate that must be green before any activation plan can be
created after a durable Global Worker incident closure exists.

The gate does not authorize activation. It only proves that post-incident
blockers are absent at a specific, short-lived evidence point.

Safety principles:
- OPEN / REOPENED / OPEN_NEW_AFTER_CLOSURE block;
- invalid or unavailable closure reconciliation blocks;
- the latest durable closure record must appear in verified closed history;
- runtime / ledger / readiness / flag evidence are bound into the gate digest;
- gate readiness never mutates the flag, runtime, Worker, or trading state.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from atlasquant_aion_core_intelligence.evidence import digest, utc
from atlasquant_aion_global_worker_durable_incident_closure import (
    load_closure_ledger,
)
from atlasquant_aion_memory import checkpoint_source_digest


SCHEMA = "ATLASQUANT_AION_GLOBAL_WORKER_POST_INCIDENT_REACTIVATION_GATE_V1"
READY_STATUS = "REACTIVATION_GATE_READY"
NOT_REQUIRED_STATUS = "REACTIVATION_GATE_NOT_REQUIRED"
BLOCKED_STATUS = "REACTIVATION_GATE_BLOCKED"

SAFE_RECONCILIATION_STATES = {
    "NO_GLOBAL_WORKER_INCIDENT",
    "CLOSED_HISTORY_RECOGNIZED",
}
SAFE_FLAG_STATES = {"UNSET", "DISABLED"}
DEFAULT_GATE_TTL_SECONDS = 300
MIN_GATE_TTL_SECONDS = 120
MAX_GATE_TTL_SECONDS = 600


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return utc(parsed)
    except Exception:
        return None


def _payload_digest(value: Mapping[str, Any], field: str) -> str:
    raw = dict(value)
    raw.pop(field, None)
    return digest(raw)


def _runtime_ledger_state(
    runtime_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    runtime = dict(runtime_result or {})
    if str(runtime.get("status") or "").upper() != "CONFIRMED":
        return {
            "state": "BLOCKED",
            "reason": "CONFIRMED_RUNTIME_REQUIRED",
            "required": True,
        }
    checkpoint = runtime.get("checkpoint")
    if not isinstance(checkpoint, Mapping):
        return {
            "state": "BLOCKED",
            "reason": "RUNTIME_CHECKPOINT_REQUIRED",
            "required": True,
        }

    ledger, ledger_status = load_closure_ledger(checkpoint)
    if ledger_status.get("state") == "MISMATCH":
        return {
            "state": "BLOCKED",
            "reason": str(
                ledger_status.get("reason")
                or "DURABLE_CLOSURE_LEDGER_MISMATCH"
            ),
            "required": True,
        }
    rows = [
        dict(row)
        for row in list(ledger.get("records") or [])
        if isinstance(row, Mapping)
    ]
    required = bool(rows)
    return {
        "state": "CONFIRMED",
        "reason": "",
        "required": required,
        "record_count": len(rows),
        "ledger_digest": str(ledger.get("digest") or ""),
        "latest_record_id": str(ledger.get("latest_record_id") or ""),
        "runtime_sha": str(runtime.get("sha") or ""),
        "runtime_checkpoint_digest": checkpoint_source_digest(checkpoint),
    }


def reactivation_gate_requirement(
    runtime_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return whether durable incident history makes the safety gate mandatory."""
    state = _runtime_ledger_state(runtime_result)
    return {
        "schema": SCHEMA,
        "state": str(state.get("state") or "BLOCKED"),
        "reason": str(state.get("reason") or ""),
        "required": bool(state.get("required")),
        "durable_closure_records": int(state.get("record_count") or 0),
        "ledger_digest": str(state.get("ledger_digest") or ""),
        "latest_record_id": str(state.get("latest_record_id") or ""),
        "executes_action": False,
    }


def _active_global_worker_incidents(
    incident_snapshot: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    rows = []
    for item in list((incident_snapshot or {}).get("incidents") or []):
        if not isinstance(item, Mapping):
            continue
        if str(item.get("response_key") or "") != "global_worker":
            continue
        rows.append(dict(item))
    return rows


def assess_post_incident_reactivation_gate(
    runtime_result: Mapping[str, Any] | None,
    incident_snapshot: Mapping[str, Any] | None,
    readiness: Mapping[str, Any] | None,
    flag_evidence: Mapping[str, Any] | None,
    *,
    ttl_seconds: int = DEFAULT_GATE_TTL_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Assess a short-lived, read-only reactivation safety gate."""
    current = utc(now or _now())
    if type(ttl_seconds) is not int or not (
        MIN_GATE_TTL_SECONDS <= ttl_seconds <= MAX_GATE_TTL_SECONDS
    ):
        raise ValueError("invalid reactivation gate ttl")

    ledger_state = _runtime_ledger_state(runtime_result)
    if ledger_state.get("state") != "CONFIRMED":
        return {
            "schema": SCHEMA,
            "status": BLOCKED_STATUS,
            "gate_required": True,
            "gate_ready": False,
            "activation_plan_allowed": False,
            "reason": str(ledger_state.get("reason") or ""),
            "reactivation_authorized": False,
            "executes_action": False,
        }

    if not ledger_state.get("required"):
        return {
            "schema": SCHEMA,
            "status": NOT_REQUIRED_STATUS,
            "gate_required": False,
            "gate_ready": True,
            "activation_plan_allowed": True,
            "reason": "",
            "durable_closure_records": 0,
            "reactivation_authorized": False,
            "feature_flag_modified": False,
            "runtime_modified": False,
            "global_worker_modified": False,
            "real_trading_enabled": False,
            "executes_action": False,
        }

    snapshot = dict(incident_snapshot or {})
    reconciliation = (
        dict(snapshot.get("global_worker_reconciliation") or {})
        if isinstance(snapshot.get("global_worker_reconciliation"), Mapping)
        else {}
    )
    readiness_row = dict(readiness or {})
    flag = dict(flag_evidence or {})

    blockers: list[str] = []

    if not reconciliation:
        blockers.append("GLOBAL_WORKER_RECONCILIATION_REQUIRED")
    else:
        recon_state = str(reconciliation.get("state") or "UNKNOWN")
        if reconciliation.get("fail_open") is True:
            blockers.append("GLOBAL_WORKER_RECONCILIATION_FAIL_OPEN")
        if str(reconciliation.get("durable_history_state") or "") != "CONFIRMED":
            blockers.append("DURABLE_HISTORY_NOT_CONFIRMED")
        if recon_state not in SAFE_RECONCILIATION_STATES:
            blockers.append("ACTIVE_OR_UNSAFE_RECONCILIATION_STATE")
        if int(reconciliation.get("durable_closure_records") or 0) != int(
            ledger_state.get("record_count") or 0
        ):
            blockers.append("DURABLE_CLOSURE_COUNT_MISMATCH")

    active = _active_global_worker_incidents(snapshot)
    if active:
        blockers.append("ACTIVE_GLOBAL_WORKER_INCIDENT_PRESENT")

    latest_record_id = str(ledger_state.get("latest_record_id") or "")
    closed_rows = [
        dict(row)
        for row in list(snapshot.get("closed_incidents") or [])
        if isinstance(row, Mapping)
    ]
    latest_closed = next(
        (
            row
            for row in closed_rows
            if str(row.get("closure_record_id") or "") == latest_record_id
            and str(row.get("status") or "") == "CLOSED_HUMAN_VERIFIED"
        ),
        None,
    )
    if not latest_closed:
        blockers.append("LATEST_DURABLE_CLOSURE_NOT_RECONCILED")

    if (
        str(readiness_row.get("status") or "") != "PASS"
        or str(readiness_row.get("activation_stage") or "")
        != "READY_FOR_FLAG_ENABLE"
        or list(readiness_row.get("blockers") or [])
    ):
        blockers.append("ACTIVATION_READINESS_NOT_READY")

    checked_at = _parse_iso(readiness_row.get("checked_at"))
    if checked_at is None:
        blockers.append("ACTIVATION_READINESS_TIMESTAMP_REQUIRED")

    flag_state = str(flag.get("state") or "").upper()
    if (
        str(flag.get("status") or "").upper() != "CONFIRMED"
        or flag_state not in SAFE_FLAG_STATES
        or flag.get("safe_for_arming_persistence") is not True
    ):
        blockers.append("FEATURE_FLAG_NOT_PROVEN_DISABLED")

    recon_at = _parse_iso(reconciliation.get("reconciled_at"))
    if recon_at is None:
        blockers.append("RECONCILIATION_TIMESTAMP_REQUIRED")

    blockers = sorted(set(blockers))
    if blockers:
        return {
            "schema": SCHEMA,
            "status": BLOCKED_STATUS,
            "gate_required": True,
            "gate_ready": False,
            "activation_plan_allowed": False,
            "reason": blockers[0],
            "blockers": blockers,
            "durable_closure_records": int(
                ledger_state.get("record_count") or 0
            ),
            "latest_closure_record_id": latest_record_id,
            "reactivation_authorized": False,
            "feature_flag_modified": False,
            "runtime_modified": False,
            "global_worker_modified": False,
            "real_trading_enabled": False,
            "executes_action": False,
        }

    expires = current + timedelta(seconds=ttl_seconds)
    gate = {
        "schema": SCHEMA,
        "status": READY_STATUS,
        "gate_required": True,
        "gate_ready": True,
        "activation_plan_allowed": True,
        "runtime_sha": str(ledger_state.get("runtime_sha") or ""),
        "runtime_checkpoint_digest": str(
            ledger_state.get("runtime_checkpoint_digest") or ""
        ),
        "closure_ledger_digest": str(
            ledger_state.get("ledger_digest") or ""
        ),
        "latest_closure_record_id": latest_record_id,
        "durable_closure_records": int(
            ledger_state.get("record_count") or 0
        ),
        "reconciliation_state": str(
            reconciliation.get("state") or ""
        ),
        "reconciled_at": str(reconciliation.get("reconciled_at") or ""),
        "readiness_checked_at": str(
            readiness_row.get("checked_at") or ""
        ),
        "feature_flag_state": flag_state,
        "created_at": current.isoformat(),
        "expires_at": expires.isoformat(),
        "ttl_seconds": ttl_seconds,
        "reactivation_authorized": False,
        "automatic_reactivation": False,
        "feature_flag_modified": False,
        "runtime_modified": False,
        "global_worker_modified": False,
        "real_trading_enabled": False,
        "executes_action": False,
    }
    gate["gate_digest"] = _payload_digest(gate, "gate_digest")
    return gate


def gate_integrity(
    gate: Mapping[str, Any] | None,
) -> dict[str, str]:
    if not isinstance(gate, Mapping):
        return {"state": "ABSENT", "stored": "", "expected": ""}
    if str(gate.get("schema") or "") != SCHEMA:
        return {
            "state": "MISMATCH",
            "stored": str(gate.get("gate_digest") or ""),
            "expected": SCHEMA,
        }
    stored = str(gate.get("gate_digest") or "")
    expected = _payload_digest(gate, "gate_digest")
    return {
        "state": "MATCH" if stored and stored == expected else "MISMATCH",
        "stored": stored,
        "expected": expected,
    }


def validate_reactivation_gate_for_plan(
    runtime_result: Mapping[str, Any] | None,
    readiness: Mapping[str, Any] | None,
    flag_evidence: Mapping[str, Any] | None,
    gate: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Revalidate gate bindings before creating an activation plan."""
    current = utc(now or _now())
    ledger_state = _runtime_ledger_state(runtime_result)
    if ledger_state.get("state") != "CONFIRMED":
        return {
            "state": "BLOCKED",
            "reason": str(ledger_state.get("reason") or ""),
        }
    if not ledger_state.get("required"):
        return {
            "state": "READY",
            "reason": "",
            "gate_required": False,
            "gate_digest": "",
        }

    if gate_integrity(gate)["state"] != "MATCH":
        return {
            "state": "BLOCKED",
            "reason": "POST_INCIDENT_REACTIVATION_GATE_INTEGRITY_MISMATCH",
        }
    row = dict(gate or {})
    if (
        str(row.get("status") or "") != READY_STATUS
        or row.get("gate_required") is not True
        or row.get("gate_ready") is not True
        or row.get("activation_plan_allowed") is not True
        or row.get("reactivation_authorized") is not False
    ):
        return {
            "state": "BLOCKED",
            "reason": "POST_INCIDENT_REACTIVATION_GATE_NOT_READY",
        }

    expires = _parse_iso(row.get("expires_at"))
    if expires is None or current >= expires:
        return {
            "state": "BLOCKED",
            "reason": "POST_INCIDENT_REACTIVATION_GATE_EXPIRED",
        }

    runtime = dict(runtime_result or {})
    checkpoint = runtime.get("checkpoint")
    if not isinstance(checkpoint, Mapping):
        return {"state": "BLOCKED", "reason": "RUNTIME_CHECKPOINT_REQUIRED"}

    checks = (
        (
            str(row.get("runtime_sha") or ""),
            str(runtime.get("sha") or ""),
            "POST_INCIDENT_GATE_RUNTIME_SHA_CHANGED",
        ),
        (
            str(row.get("runtime_checkpoint_digest") or ""),
            checkpoint_source_digest(checkpoint),
            "POST_INCIDENT_GATE_RUNTIME_DIGEST_CHANGED",
        ),
        (
            str(row.get("closure_ledger_digest") or ""),
            str(ledger_state.get("ledger_digest") or ""),
            "POST_INCIDENT_GATE_LEDGER_CHANGED",
        ),
        (
            str(row.get("latest_closure_record_id") or ""),
            str(ledger_state.get("latest_record_id") or ""),
            "POST_INCIDENT_GATE_LATEST_CLOSURE_CHANGED",
        ),
        (
            str(row.get("readiness_checked_at") or ""),
            str((readiness or {}).get("checked_at") or ""),
            "POST_INCIDENT_GATE_READINESS_CHANGED",
        ),
        (
            str(row.get("feature_flag_state") or ""),
            str((flag_evidence or {}).get("state") or "").upper(),
            "POST_INCIDENT_GATE_FLAG_STATE_CHANGED",
        ),
    )
    for stored, observed, reason in checks:
        if not stored or stored != observed:
            return {"state": "BLOCKED", "reason": reason}

    return {
        "state": "READY",
        "reason": "",
        "gate_required": True,
        "gate_digest": str(row.get("gate_digest") or ""),
        "closure_ledger_digest": str(
            row.get("closure_ledger_digest") or ""
        ),
        "latest_closure_record_id": str(
            row.get("latest_closure_record_id") or ""
        ),
        "expires_at": str(row.get("expires_at") or ""),
    }


def validate_reactivation_gate_for_execution(
    runtime_result: Mapping[str, Any] | None,
    flag_evidence: Mapping[str, Any] | None,
    activation_approval: Mapping[str, Any] | None,
    gate: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate a freshly assessed gate immediately before flag enable."""
    current = utc(now or _now())
    approval = dict(activation_approval or {})
    gate_required = approval.get("post_incident_gate_required") is True

    ledger_state = _runtime_ledger_state(runtime_result)
    if ledger_state.get("state") != "CONFIRMED":
        return {
            "state": "BLOCKED",
            "reason": str(ledger_state.get("reason") or ""),
        }

    if bool(ledger_state.get("required")) != gate_required:
        return {
            "state": "BLOCKED",
            "reason": "POST_INCIDENT_GATE_REQUIREMENT_CHANGED",
        }
    if not gate_required:
        return {"state": "READY", "reason": "", "gate_required": False}

    if gate_integrity(gate)["state"] != "MATCH":
        return {
            "state": "BLOCKED",
            "reason": "FRESH_POST_INCIDENT_GATE_INTEGRITY_MISMATCH",
        }
    row = dict(gate or {})
    if (
        str(row.get("status") or "") != READY_STATUS
        or row.get("gate_ready") is not True
        or row.get("activation_plan_allowed") is not True
    ):
        return {
            "state": "BLOCKED",
            "reason": "FRESH_POST_INCIDENT_GATE_NOT_READY",
        }
    expires = _parse_iso(row.get("expires_at"))
    if expires is None or current >= expires:
        return {
            "state": "BLOCKED",
            "reason": "FRESH_POST_INCIDENT_GATE_EXPIRED",
        }

    runtime = dict(runtime_result or {})
    checkpoint = runtime.get("checkpoint")
    observed_flag = str((flag_evidence or {}).get("state") or "").upper()
    if not isinstance(checkpoint, Mapping):
        return {"state": "BLOCKED", "reason": "RUNTIME_CHECKPOINT_REQUIRED"}

    checks = (
        (
            str(row.get("runtime_sha") or ""),
            str(runtime.get("sha") or ""),
            "FRESH_POST_INCIDENT_GATE_RUNTIME_SHA_CHANGED",
        ),
        (
            str(row.get("runtime_checkpoint_digest") or ""),
            checkpoint_source_digest(checkpoint),
            "FRESH_POST_INCIDENT_GATE_RUNTIME_DIGEST_CHANGED",
        ),
        (
            str(row.get("closure_ledger_digest") or ""),
            str(ledger_state.get("ledger_digest") or ""),
            "FRESH_POST_INCIDENT_GATE_LEDGER_CHANGED",
        ),
        (
            str(row.get("latest_closure_record_id") or ""),
            str(ledger_state.get("latest_record_id") or ""),
            "FRESH_POST_INCIDENT_GATE_LATEST_CLOSURE_CHANGED",
        ),
        (
            str(row.get("closure_ledger_digest") or ""),
            str(approval.get("post_incident_closure_ledger_digest") or ""),
            "POST_INCIDENT_APPROVAL_LEDGER_BINDING_CHANGED",
        ),
        (
            str(row.get("latest_closure_record_id") or ""),
            str(approval.get("post_incident_latest_closure_record_id") or ""),
            "POST_INCIDENT_APPROVAL_CLOSURE_BINDING_CHANGED",
        ),
        (
            str(row.get("feature_flag_state") or ""),
            observed_flag,
            "FRESH_POST_INCIDENT_GATE_FLAG_STATE_CHANGED",
        ),
    )
    for stored, observed, reason in checks:
        if not stored or stored != observed:
            return {"state": "BLOCKED", "reason": reason}

    return {
        "state": "READY",
        "reason": "",
        "gate_required": True,
        "gate_digest": str(row.get("gate_digest") or ""),
        "reactivation_authorized": False,
    }


__all__ = [
    "SCHEMA",
    "READY_STATUS",
    "NOT_REQUIRED_STATUS",
    "BLOCKED_STATUS",
    "reactivation_gate_requirement",
    "assess_post_incident_reactivation_gate",
    "gate_integrity",
    "validate_reactivation_gate_for_plan",
    "validate_reactivation_gate_for_execution",
]
