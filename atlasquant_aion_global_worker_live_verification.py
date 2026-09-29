"""AION Global Worker Live Activation Verification V1.

Read-only verifier for the period after the repository activation flag becomes
ENABLED. It never changes the feature flag, runtime Checkpoint, schedules, or
worker state.

A flag write is not treated as proof that the worker is live. The verifier
requires shared runtime heartbeat/tick evidence after the activation boundary.
GLOBAL_WORKER receipts are additional proof that due work actually executed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from atlasquant_aion_background_executor import load_executor_receipts
from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_intelligence.evidence import utc
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_global_worker import load_global_worker_state


SCHEMA = "ATLASQUANT_AION_GLOBAL_WORKER_LIVE_VERIFICATION_V1"
LIVE_HEARTBEAT_MAX_WAIT_SECONDS = 4500


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


def _max_time(*values: Any) -> datetime | None:
    parsed = [item for item in (_parse_iso(x) for x in values) if item is not None]
    return max(parsed) if parsed else None


def activation_boundary(
    flag_evidence: Mapping[str, Any],
    activation_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve the earliest trustworthy boundary for post-activation evidence."""
    flag_updated = _parse_iso(flag_evidence.get("updated_at"))
    activated_at = (
        _parse_iso((activation_result or {}).get("activated_at"))
        if isinstance(activation_result, Mapping)
        else None
    )
    boundary = _max_time(flag_updated, activated_at)
    if boundary is None:
        return {
            "state": "BLOCKED",
            "reason": "ACTIVATION_TIMESTAMP_EVIDENCE_REQUIRED",
            "boundary": "",
        }

    if isinstance(activation_result, Mapping):
        status = str(activation_result.get("status") or "")
        if status and status != "ACTIVATED_PENDING_LIVE_EVIDENCE":
            return {
                "state": "BLOCKED",
                "reason": "ACTIVATION_RESULT_NOT_PENDING_LIVE_EVIDENCE",
                "boundary": "",
            }

    return {
        "state": "READY",
        "reason": "",
        "boundary": boundary.isoformat(),
        "flag_updated_at": flag_updated.isoformat() if flag_updated else "",
        "activation_result_at": activated_at.isoformat() if activated_at else "",
    }


def verify_global_worker_live_activation(
    access: Mapping[str, Any] | None,
    runtime_result: Mapping[str, Any],
    flag_evidence: Mapping[str, Any],
    *,
    activation_result: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    max_wait_seconds: int = LIVE_HEARTBEAT_MAX_WAIT_SECONDS,
) -> dict[str, Any]:
    """Verify a real shared heartbeat/tick after feature-flag activation."""
    current = utc(now or _now())
    if type(max_wait_seconds) is not int or not 300 <= max_wait_seconds <= 21600:
        raise ValueError("invalid live verification timeout")

    context = authenticated_context(access, Domain.ADMIN)
    if context.role != "ADMIN":
        raise ValueError("ADMIN_REQUIRED")

    if (
        str(flag_evidence.get("status") or "") != "CONFIRMED"
        or str(flag_evidence.get("state") or "") != "ENABLED"
    ):
        return {
            "schema": SCHEMA,
            "status": "NOT_ENABLED",
            "reason": "FEATURE_FLAG_ENABLED_EVIDENCE_REQUIRED",
            "read_only": True,
            "runtime_modified": False,
            "feature_flag_modified": False,
            "real_trading_enabled": False,
        }

    boundary = activation_boundary(flag_evidence, activation_result)
    if boundary["state"] != "READY":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": boundary["reason"],
            "read_only": True,
            "runtime_modified": False,
            "feature_flag_modified": False,
            "real_trading_enabled": False,
        }
    activated_at = _parse_iso(boundary["boundary"])
    assert activated_at is not None

    if str(runtime_result.get("status") or "") != "CONFIRMED":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "RUNTIME_NOT_CONFIRMED",
            "read_only": True,
            "runtime_modified": False,
            "feature_flag_modified": False,
            "real_trading_enabled": False,
        }
    checkpoint = runtime_result.get("checkpoint")
    if not isinstance(checkpoint, Mapping):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "RUNTIME_CHECKPOINT_REQUIRED",
            "read_only": True,
            "runtime_modified": False,
            "feature_flag_modified": False,
            "real_trading_enabled": False,
        }

    try:
        worker, worker_status = load_global_worker_state(checkpoint)
    except Exception:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "GLOBAL_WORKER_STATE_INVALID",
            "read_only": True,
            "runtime_modified": False,
            "feature_flag_modified": False,
            "real_trading_enabled": False,
        }

    if worker_status.get("state") != "CONNECTED" or worker.get("state") != "ARMED":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "PERSISTED_ARMED_STATE_REQUIRED",
            "read_only": True,
            "runtime_modified": False,
            "feature_flag_modified": False,
            "real_trading_enabled": False,
        }
    if worker.get("kill_switch") is not False:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "GLOBAL_KILL_SWITCH_ACTIVE",
            "read_only": True,
            "runtime_modified": False,
            "feature_flag_modified": False,
            "real_trading_enabled": False,
        }

    stats = worker.get("stats") if isinstance(worker.get("stats"), Mapping) else {}
    lease = worker.get("lease") if isinstance(worker.get("lease"), Mapping) else {}
    inflight = (
        worker.get("inflight_tick")
        if isinstance(worker.get("inflight_tick"), Mapping)
        else {}
    )

    last_heartbeat_at = _parse_iso(stats.get("last_heartbeat_at"))
    last_tick_at = _parse_iso(stats.get("last_tick_at"))
    last_runtime_id = str(stats.get("last_runtime_id") or "")
    ticks = int(stats.get("ticks") or 0)

    lease_owner = str(lease.get("owner") or "")
    lease_expires = _parse_iso(lease.get("expires_at"))
    stale_lease = bool(
        lease_owner
        and lease_expires is not None
        and lease_expires <= current
    )

    heartbeat_after_activation = bool(
        last_heartbeat_at is not None
        and last_heartbeat_at >= activated_at
        and last_runtime_id.startswith("gha-")
    )
    tick_after_activation = bool(
        last_tick_at is not None
        and last_tick_at >= activated_at
        and last_runtime_id.startswith("gha-")
    )

    try:
        receipts, receipt_state = load_executor_receipts(context, checkpoint)
    except Exception:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "EXECUTOR_RECEIPT_CONTEXT_OR_INTEGRITY_INVALID",
            "read_only": True,
            "runtime_modified": False,
            "feature_flag_modified": False,
            "real_trading_enabled": False,
        }

    receipt_store_state = str(receipt_state.get("state") or "")
    if receipt_store_state not in {"EMPTY", "CONNECTED"}:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "EXECUTOR_RECEIPT_CONTEXT_OR_INTEGRITY_INVALID",
            "receipt_store_state": receipt_store_state or "UNKNOWN",
            "read_only": True,
            "runtime_modified": False,
            "feature_flag_modified": False,
            "real_trading_enabled": False,
        }

    live_receipts = []
    unsafe_receipts = []
    for row in receipts:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("authorization_mode") or "") != "GLOBAL_WORKER":
            continue
        completed = _parse_iso(row.get("completed_at"))
        if completed is None or completed < activated_at:
            continue
        copied = dict(row)
        live_receipts.append(copied)
        if (
            copied.get("provider_called") is True
            or copied.get("external_action_executed") is True
            or copied.get("real_trading_enabled") is True
        ):
            unsafe_receipts.append(copied)

    age_seconds = max(0, int((current - activated_at).total_seconds()))

    if unsafe_receipts:
        status = "BLOCKED_UNSAFE_RECEIPT"
        reason = "GLOBAL_WORKER_RECEIPT_REPORTED_EXTERNAL_OR_TRADING_EFFECT"
    elif inflight:
        status = "BLOCKED_INFLIGHT_RECONCILIATION"
        reason = "GLOBAL_WORKER_INFLIGHT_TICK_REQUIRES_RECONCILIATION"
    elif stale_lease:
        status = "BLOCKED_STALE_LEASE"
        reason = "GLOBAL_WORKER_LEASE_EXPIRED_WITH_OWNER"
    elif tick_after_activation and heartbeat_after_activation:
        status = (
            "LIVE_CONFIRMED_WITH_WORK"
            if live_receipts
            else "LIVE_CONFIRMED_IDLE"
        )
        reason = ""
    elif heartbeat_after_activation:
        status = "LIVE_HEARTBEAT_CONFIRMED_AWAITING_TICK"
        reason = ""
    elif age_seconds > max_wait_seconds:
        status = "LIVE_EVIDENCE_TIMEOUT"
        reason = "NO_SHARED_HEARTBEAT_AFTER_ACTIVATION_TIMEOUT"
    else:
        status = "AWAITING_LIVE_EVIDENCE"
        reason = ""

    live_confirmed = status in {
        "LIVE_CONFIRMED_WITH_WORK",
        "LIVE_CONFIRMED_IDLE",
    }
    return {
        "schema": SCHEMA,
        "status": status,
        "reason": reason,
        "live_confirmed": live_confirmed,
        "heartbeat_confirmed": heartbeat_after_activation,
        "tick_confirmed": tick_after_activation,
        "work_receipt_confirmed": bool(live_receipts),
        "global_receipts_after_activation": len(live_receipts),
        "unsafe_receipts_after_activation": len(unsafe_receipts),
        "activation_boundary": activated_at.isoformat(),
        "age_seconds": age_seconds,
        "max_wait_seconds": max_wait_seconds,
        "ticks": ticks,
        "last_heartbeat_at": (
            last_heartbeat_at.isoformat() if last_heartbeat_at else ""
        ),
        "last_tick_at": last_tick_at.isoformat() if last_tick_at else "",
        "last_runtime_id": last_runtime_id,
        "lease_owner": lease_owner,
        "lease_expires_at": lease_expires.isoformat() if lease_expires else "",
        "stale_lease": stale_lease,
        "inflight_reconciliation_required": bool(inflight),
        "inflight_owner": str(inflight.get("owner") or ""),
        "inflight_fencing_token": int(inflight.get("fencing_token") or 0),
        "inflight_since": str(inflight.get("claimed_at") or ""),
        "receipt_store_state": str(receipt_state.get("state") or ""),
        "read_only": True,
        "runtime_modified": False,
        "feature_flag_modified": False,
        "global_worker_executed_by_verifier": False,
        "external_business_action_executed": False,
        "real_trading_enabled": False,
    }


__all__ = [
    "SCHEMA",
    "LIVE_HEARTBEAT_MAX_WAIT_SECONDS",
    "activation_boundary",
    "verify_global_worker_live_activation",
]
