"""Session-scoped autonomous runtime for safe local AION scheduled work.

Worker Runtime V1 runs only inside an authenticated active Streamlit session
after explicit ADMIN arming. It uses the working Checkpoint Mestre for lease,
heartbeat, retry-queue and kill-switch state. It is deliberately not claimed
as multi-instance or 24/7 safe and never grants external/physical authority.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import secrets
from typing import Any, Mapping

from atlasquant_aion_background_executor import (
    MAX_ATTEMPTS,
    MAX_JOBS_PER_RUN,
    _execute_due_local_work_authorized,
    load_executor_receipts,
)
from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_intelligence.evidence import digest, safe_text, utc
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_core_voice_automation import CheckpointAutomationAdapter
from atlasquant_aion_loop_governor import govern_agent_plan


SCHEMA = "ATLASQUANT_AION_WORKER_RUNTIME_V1"
WORKER_NAMESPACE = "aion_core_worker_v1"
WORKER_SCHEMA = "AION_CORE_WORKER_CHECKPOINT_V1"
WORKER_STATES = ("DISABLED", "ARMED", "PAUSED", "KILLED")
DEFAULT_INTERVAL_SECONDS = 60
MIN_INTERVAL_SECONDS = 60
MAX_INTERVAL_SECONDS = 900
DEFAULT_LEASE_SECONDS = 150
MIN_LEASE_SECONDS = 90
MAX_LEASE_SECONDS = 1800
MAX_RETRY_QUEUE = 200


def _scope_payload(context) -> list[str]:
    return json.loads(context.key)


def _bundle_digest(bundle: Mapping[str, Any]) -> str:
    raw = dict(bundle or {})
    raw.pop("digest", None)
    return digest(raw)


def _parse_iso(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return utc(parsed)
    except Exception:
        return None


def _exact_int(value: Any, *, minimum: int, maximum: int, name: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("invalid " + name)
    return value


def _validated_runtime_id(value: Any) -> str:
    if type(value) is not str:
        raise ValueError("invalid worker runtime id")
    runtime = value.strip()
    if not runtime or len(runtime) > 160:
        raise ValueError("invalid worker runtime id")
    normalized = safe_text(runtime, 160)
    if not normalized or normalized != runtime:
        raise ValueError("invalid worker runtime id")
    return normalized


def _empty_lease() -> dict[str, Any]:
    return {
        "owner": "",
        "token": "",
        "acquired_at": "",
        "heartbeat_at": "",
        "expires_at": "",
    }


def _empty_stats() -> dict[str, Any]:
    return {
        "ticks": 0,
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "blocked": 0,
        "lease_reclaims": 0,
        "crash_recoveries": 0,
        "last_tick_at": "",
        "last_tick_status": "NEVER",
        "last_heartbeat_at": "",
    }


def _normalize_stats(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    source = dict(raw or {})
    base = _empty_stats()
    for key in (
        "ticks", "processed", "succeeded", "failed", "blocked",
        "lease_reclaims", "crash_recoveries",
    ):
        value = source.get(key, 0)
        if type(value) is int and value >= 0:
            base[key] = value
    for key in ("last_tick_at", "last_heartbeat_at"):
        value = str(source.get(key) or "")
        if value and _parse_iso(value) is None:
            raise ValueError("invalid worker timestamp")
        base[key] = value
    base["last_tick_status"] = safe_text(
        str(source.get("last_tick_status") or "NEVER"),
        120,
    )
    return base


def _normalize_retry_queue(raw: Any) -> list[dict[str, Any]]:
    if raw in (None, []):
        return []
    if not isinstance(raw, list):
        raise ValueError("invalid worker retry queue")
    rows = []
    seen = set()
    for item in raw[-MAX_RETRY_QUEUE:]:
        if not isinstance(item, Mapping):
            raise ValueError("invalid worker retry row")
        occurrence_key = safe_text(str(item.get("occurrence_key") or ""), 128)
        if occurrence_key in seen:
            continue
        seen.add(occurrence_key)
        retry_after = str(item.get("retry_after") or "")
        if retry_after and _parse_iso(retry_after) is None:
            raise ValueError("invalid retry timestamp")
        attempt = item.get("attempt", 0)
        if type(attempt) is not int or attempt < 1 or attempt > MAX_ATTEMPTS:
            raise ValueError("invalid retry attempt")
        rows.append({
            "occurrence_key": occurrence_key,
            "schedule_id": safe_text(str(item.get("schedule_id") or "UNKNOWN"), 120),
            "capability": safe_text(str(item.get("capability") or "UNKNOWN"), 80),
            "attempt": attempt,
            "retry_after": retry_after,
            "state": "WAITING_BACKOFF" if retry_after else "READY",
        })
    return rows


def _normalize_lease(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    item = dict(raw or {})
    if not any(str(item.get(key) or "") for key in ("owner", "token", "acquired_at", "heartbeat_at", "expires_at")):
        return _empty_lease()
    owner = safe_text(str(item.get("owner") or ""), 160)
    token = safe_text(str(item.get("token") or ""), 180)
    acquired_at = str(item.get("acquired_at") or "")
    heartbeat_at = str(item.get("heartbeat_at") or "")
    expires_at = str(item.get("expires_at") or "")
    for value in (acquired_at, heartbeat_at, expires_at):
        if _parse_iso(value) is None:
            raise ValueError("invalid worker lease timestamp")
    if not owner or not token:
        raise ValueError("incomplete worker lease")
    return {
        "owner": owner,
        "token": token,
        "acquired_at": acquired_at,
        "heartbeat_at": heartbeat_at,
        "expires_at": expires_at,
    }


def worker_integrity(raw: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        return {"state": "ABSENT", "stored": "", "expected": ""}
    if raw.get("schema") != WORKER_SCHEMA:
        return {"state": "MISMATCH", "stored": "", "expected": WORKER_SCHEMA}
    supplied = str(raw.get("digest") or "").strip()
    expected = _bundle_digest(raw)
    return {
        "state": "MATCH" if supplied and supplied == expected else "MISMATCH",
        "stored": supplied,
        "expected": expected,
    }


def _default_state(context) -> dict[str, Any]:
    state = {
        "schema": WORKER_SCHEMA,
        "scope": _scope_payload(context),
        "revision": 0,
        "state": "DISABLED",
        "kill_switch": True,
        "armed_by": "",
        "armed_at": "",
        "arm_digest": "",
        "runtime_mode": "SESSION_FRAGMENT_V1",
        "interval_seconds": DEFAULT_INTERVAL_SECONDS,
        "lease_seconds": DEFAULT_LEASE_SECONDS,
        "lease": _empty_lease(),
        "retry_queue": [],
        "stats": _empty_stats(),
        "session_autonomy": True,
        "multi_instance_safe": False,
        "concurrency_scope": "CALLER_CHECKPOINT_ONLY",
        "lease_external_persistence": False,
        "continuous_24x7_confirmed": False,
        "external_persistence": "EXPLICIT_CHECKPOINT_SAVE",
        "physical_action_adapter": "UNAVAILABLE",
        "provider_calls_allowed": False,
        "publication_allowed": False,
        "payment_allowed": False,
        "deploy_allowed": False,
        "real_trading_enabled": False,
    }
    state["digest"] = _bundle_digest(state)
    return state


def _normalize_state(context, raw: Mapping[str, Any]) -> dict[str, Any]:
    if raw.get("schema") != WORKER_SCHEMA:
        raise ValueError("WORKER_CHECKPOINT_MISMATCH")
    if worker_integrity(raw)["state"] != "MATCH":
        raise ValueError("WORKER_CHECKPOINT_MISMATCH")
    if raw.get("scope") != _scope_payload(context):
        raise ValueError("WORKER_CONTEXT_MISMATCH")
    state_name = str(raw.get("state") or "").strip().upper()
    if state_name not in WORKER_STATES:
        raise ValueError("invalid worker state")
    revision = raw.get("revision", 0)
    if type(revision) is not int or revision < 0:
        raise ValueError("invalid worker revision")
    interval = _exact_int(
        raw.get("interval_seconds", DEFAULT_INTERVAL_SECONDS),
        minimum=MIN_INTERVAL_SECONDS,
        maximum=MAX_INTERVAL_SECONDS,
        name="worker interval",
    )
    lease_seconds = _exact_int(
        raw.get("lease_seconds", DEFAULT_LEASE_SECONDS),
        minimum=MIN_LEASE_SECONDS,
        maximum=MAX_LEASE_SECONDS,
        name="worker lease",
    )
    armed_at = str(raw.get("armed_at") or "")
    if armed_at and _parse_iso(armed_at) is None:
        raise ValueError("invalid worker armed timestamp")
    result = {
        "schema": WORKER_SCHEMA,
        "scope": _scope_payload(context),
        "revision": revision,
        "state": state_name,
        "kill_switch": bool(raw.get("kill_switch", True)),
        "armed_by": str(raw.get("armed_by") or ""),
        "armed_at": armed_at,
        "arm_digest": str(raw.get("arm_digest") or ""),
        "runtime_mode": "SESSION_FRAGMENT_V1",
        "interval_seconds": interval,
        "lease_seconds": lease_seconds,
        "lease": _normalize_lease(raw.get("lease") if isinstance(raw.get("lease"), Mapping) else {}),
        "retry_queue": _normalize_retry_queue(raw.get("retry_queue")),
        "stats": _normalize_stats(raw.get("stats") if isinstance(raw.get("stats"), Mapping) else {}),
        "session_autonomy": True,
        "multi_instance_safe": False,
        "concurrency_scope": "CALLER_CHECKPOINT_ONLY",
        "lease_external_persistence": False,
        "continuous_24x7_confirmed": False,
        "external_persistence": "EXPLICIT_CHECKPOINT_SAVE",
        "physical_action_adapter": "UNAVAILABLE",
        "provider_calls_allowed": False,
        "publication_allowed": False,
        "payment_allowed": False,
        "deploy_allowed": False,
        "real_trading_enabled": False,
    }
    if result["state"] == "ARMED" and (
        result["kill_switch"]
        or not result["armed_by"]
        or not result["armed_at"]
        or not result["arm_digest"]
    ):
        raise ValueError("invalid armed worker state")
    result["digest"] = _bundle_digest(result)
    return result


def load_worker_state(
    context,
    checkpoint: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = dict(checkpoint or {})
    raw = payload.get(WORKER_NAMESPACE)
    if raw is None:
        return _default_state(context), {
            "state": "EMPTY",
            "reason": "WORKER_NAMESPACE_ABSENT",
        }
    if not isinstance(raw, Mapping):
        raise ValueError("WORKER_CHECKPOINT_MISMATCH")
    try:
        state = _normalize_state(context, raw)
    except ValueError as exc:
        if str(exc) == "WORKER_CONTEXT_MISMATCH":
            return _default_state(context), {
                "state": "CONTEXT_ISOLATED",
                "reason": "WORKER_CONTEXT_MISMATCH",
            }
        raise
    return state, {
        "state": "CONNECTED",
        "reason": "",
        "revision": state["revision"],
    }


def attach_worker_state(
    checkpoint: Mapping[str, Any],
    context,
    state: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = _normalize_state(context, state)
    out = deepcopy(dict(checkpoint or {}))
    previous = out.get(WORKER_NAMESPACE)
    if isinstance(previous, Mapping) and previous.get("scope") != _scope_payload(context):
        raise ValueError("WORKER_CONTEXT_MISMATCH")
    out[WORKER_NAMESPACE] = normalized
    return out


def _mutated(current_state: Mapping[str, Any], **changes: Any) -> dict[str, Any]:
    out = deepcopy(dict(current_state))
    out.update(changes)
    out["revision"] = int(out.get("revision") or 0) + 1
    out["digest"] = _bundle_digest(out)
    return out


def arm_worker(
    access: Mapping[str, Any] | None,
    checkpoint: Mapping[str, Any],
    *,
    runtime_id: str,
    confirmation: bool,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    if confirmation is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "EXPLICIT_ADMIN_ARMING_REQUIRED",
            "checkpoint": dict(checkpoint or {}),
            "worker_armed": False,
            "external_persisted": False,
        }
    current = utc(now or datetime.now(timezone.utc))
    context = authenticated_context(access, Domain.ADMIN)
    runtime = _validated_runtime_id(runtime_id)
    interval = _exact_int(
        interval_seconds,
        minimum=MIN_INTERVAL_SECONDS,
        maximum=MAX_INTERVAL_SECONDS,
        name="worker interval",
    )
    lease_for = _exact_int(
        lease_seconds,
        minimum=MIN_LEASE_SECONDS,
        maximum=MAX_LEASE_SECONDS,
        name="worker lease",
    )
    state, status = load_worker_state(context, checkpoint)
    if status["state"] == "CONTEXT_ISOLATED":
        raise ValueError("WORKER_CONTEXT_MISMATCH")
    armed_at = current.isoformat()
    arm_digest = digest({
        "actor": context.actor_id,
        "scope": context.key,
        "runtime_id": runtime,
        "armed_at": armed_at,
        "interval_seconds": interval,
        "lease_seconds": lease_for,
    })
    state = _mutated(
        state,
        state="ARMED",
        kill_switch=False,
        armed_by=context.actor_id,
        armed_at=armed_at,
        arm_digest=arm_digest,
        interval_seconds=interval,
        lease_seconds=lease_for,
        lease=_empty_lease(),
    )
    return {
        "schema": SCHEMA,
        "status": "ARMED",
        "checkpoint": attach_worker_state(checkpoint, context, state),
        "worker": state,
        "worker_armed": True,
        "external_persisted": False,
        "requires_checkpoint_save": True,
        "autonomy_scope": "ACTIVE_STREAMLIT_SESSION",
        "multi_instance_safe": False,
        "continuous_24x7_confirmed": False,
        "external_action_executed": False,
        "real_trading_enabled": False,
    }


def pause_worker(
    access: Mapping[str, Any] | None,
    checkpoint: Mapping[str, Any],
    *,
    confirmation: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    if confirmation is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "EXPLICIT_ADMIN_CONFIRMATION_REQUIRED",
            "checkpoint": dict(checkpoint or {}),
        }
    context = authenticated_context(access, Domain.ADMIN)
    state, status = load_worker_state(context, checkpoint)
    if status["state"] == "CONTEXT_ISOLATED":
        raise ValueError("WORKER_CONTEXT_MISMATCH")
    state = _mutated(
        state,
        state="PAUSED",
        kill_switch=False,
        lease=_empty_lease(),
    )
    return {
        "schema": SCHEMA,
        "status": "PAUSED",
        "checkpoint": attach_worker_state(checkpoint, context, state),
        "worker": state,
        "external_persisted": False,
    }


def kill_worker(
    access: Mapping[str, Any] | None,
    checkpoint: Mapping[str, Any],
    *,
    confirmation: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    if confirmation is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "EXPLICIT_ADMIN_CONFIRMATION_REQUIRED",
            "checkpoint": dict(checkpoint or {}),
        }
    context = authenticated_context(access, Domain.ADMIN)
    state, status = load_worker_state(context, checkpoint)
    if status["state"] == "CONTEXT_ISOLATED":
        raise ValueError("WORKER_CONTEXT_MISMATCH")
    state = _mutated(
        state,
        state="KILLED",
        kill_switch=True,
        lease=_empty_lease(),
    )
    return {
        "schema": SCHEMA,
        "status": "KILLED",
        "checkpoint": attach_worker_state(checkpoint, context, state),
        "worker": state,
        "external_persisted": False,
    }


def _lease_is_active(lease: Mapping[str, Any], now: datetime) -> bool:
    expiry = _parse_iso(lease.get("expires_at"))
    return bool(expiry and expiry > utc(now))


def _claim_lease(
    state: Mapping[str, Any],
    *,
    runtime_id: str,
    now: datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current = utc(now)
    runtime = _validated_runtime_id(runtime_id)
    lease = _normalize_lease(
        state.get("lease") if isinstance(state.get("lease"), Mapping) else {}
    )
    active = _lease_is_active(lease, current)
    if active and lease["owner"] != runtime:
        return deepcopy(dict(state)), {
            "state": "LEASE_HELD",
            "owner": lease["owner"],
            "expires_at": lease["expires_at"],
            "reclaimed": False,
        }

    stats = _normalize_stats(
        state.get("stats") if isinstance(state.get("stats"), Mapping) else {}
    )
    reclaimed = bool(
        lease["owner"]
        and lease["owner"] != runtime
        and not active
    )
    if reclaimed:
        stats["lease_reclaims"] += 1
        stats["crash_recoveries"] += 1

    token = (
        lease["token"]
        if active and lease["owner"] == runtime and lease["token"]
        else secrets.token_urlsafe(24)
    )
    acquired_at = (
        lease["acquired_at"]
        if active and lease["owner"] == runtime and lease["acquired_at"]
        else current.isoformat()
    )
    expires = current + timedelta(seconds=int(state["lease_seconds"]))
    next_lease = {
        "owner": runtime,
        "token": token,
        "acquired_at": acquired_at,
        "heartbeat_at": current.isoformat(),
        "expires_at": expires.isoformat(),
    }
    stats["last_heartbeat_at"] = current.isoformat()
    updated = _mutated(
        state,
        lease=next_lease,
        stats=stats,
    )
    return updated, {
        "state": "CLAIMED",
        "owner": runtime,
        "token": token,
        "expires_at": expires.isoformat(),
        "reclaimed": reclaimed,
    }


def _retry_queue_from_receipts(
    context,
    checkpoint: Mapping[str, Any],
    now: datetime,
) -> list[dict[str, Any]]:
    receipts, status = load_executor_receipts(context, checkpoint)
    if status["state"] == "CONTEXT_ISOLATED":
        raise ValueError("EXECUTOR_CONTEXT_MISMATCH")
    latest: dict[str, dict[str, Any]] = {}
    for row in receipts:
        key = str(row.get("occurrence_key") or "")
        current = latest.get(key)
        if current is None or int(row.get("attempt") or 0) >= int(current.get("attempt") or 0):
            latest[key] = row
    queue = []
    for row in latest.values():
        if str(row.get("state") or "") != "FAILED":
            continue
        attempt = int(row.get("attempt") or 0)
        if attempt >= MAX_ATTEMPTS:
            continue
        retry_after = str(row.get("retry_after") or "")
        parsed = _parse_iso(retry_after)
        queue.append({
            "occurrence_key": str(row.get("occurrence_key") or ""),
            "schedule_id": str(row.get("schedule_id") or "UNKNOWN"),
            "capability": str(row.get("capability") or "UNKNOWN"),
            "attempt": attempt,
            "retry_after": retry_after,
            "state": "READY" if parsed and parsed <= utc(now) else "WAITING_BACKOFF",
        })
    queue.sort(key=lambda x: (str(x.get("retry_after") or ""), x["occurrence_key"]))
    return queue[:MAX_RETRY_QUEUE]


def worker_snapshot(
    access: Mapping[str, Any] | None,
    checkpoint: Mapping[str, Any] | None,
    *,
    runtime_id: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    runtime = _validated_runtime_id(runtime_id)
    if type(max_jobs) is not int or not 1 <= max_jobs <= MAX_JOBS_PER_RUN:
        raise ValueError("invalid worker batch size")
    current = utc(now or datetime.now(timezone.utc))
    context = authenticated_context(access, Domain.ADMIN)
    state, status = load_worker_state(context, checkpoint)
    lease = state["lease"]
    lease_active = _lease_is_active(lease, current)
    return {
        "schema": SCHEMA,
        "status": status["state"],
        "state": state["state"],
        "revision": state["revision"],
        "kill_switch": state["kill_switch"],
        "armed_by": state["armed_by"],
        "armed_at": state["armed_at"],
        "runtime_mode": state["runtime_mode"],
        "interval_seconds": state["interval_seconds"],
        "lease_seconds": state["lease_seconds"],
        "lease_owner": lease["owner"],
        "lease_active": lease_active,
        "lease_expires_at": lease["expires_at"],
        "lease_owned_by_this_runtime": bool(
            runtime_id and lease_active and lease["owner"] == runtime_id
        ),
        "retry_queue": deepcopy(state["retry_queue"]),
        "retry_queue_count": len(state["retry_queue"]),
        "stats": deepcopy(state["stats"]),
        "session_autonomy": True,
        "multi_instance_safe": False,
        "concurrency_scope": "CALLER_CHECKPOINT_ONLY",
        "lease_external_persistence": False,
        "continuous_24x7_confirmed": False,
        "external_persistence": "EXPLICIT_CHECKPOINT_SAVE",
        "physical_action_adapter": "UNAVAILABLE",
        "provider_calls_allowed": False,
        "publication_allowed": False,
        "payment_allowed": False,
        "deploy_allowed": False,
        "real_trading_enabled": False,
    }


def _govern_due_batch(
    context,
    checkpoint: Mapping[str, Any],
    *,
    current: datetime,
    max_jobs: int,
) -> dict[str, Any]:
    scheduler = CheckpointAutomationAdapter(context, checkpoint).snapshot(current)
    due = [
        row for row in list(scheduler.get("schedules") or [])
        if isinstance(row, Mapping) and row.get("due") is True
    ]
    due.sort(key=lambda row: (
        str(row.get("due_at") or ""),
        str(row.get("schedule_id") or ""),
    ))
    selected = due[:max_jobs]
    if not selected:
        return {
            "state": "NOT_REQUIRED",
            "blockers": [],
            "due_count": 0,
            "selected_count": 0,
            "grants_permission": False,
            "executes_action": False,
            "starts_worker": False,
        }

    nodes = [{
        "node_id": "worker-batch",
        "parent_id": "",
        "tenant_id": context.tenant_id,
        "workspace_id": context.workspace_id,
        "guardian_risk": "READ",
        "impact": "LOW",
        "uncertainty_pct": 0,
        "reversible": False,
        "external_side_effects": False,
    }]
    capabilities = sorted({
        str(row.get("capability") or "").strip().upper()
        for row in selected
        if str(row.get("capability") or "").strip()
    })
    for capability in capabilities:
        nodes.append({
            "node_id": "cap-" + capability.lower().replace("_", "-"),
            "parent_id": "worker-batch",
            "tenant_id": context.tenant_id,
            "workspace_id": context.workspace_id,
            "guardian_risk": "DRAFT" if capability in {"VOICE", "CONTENT"} else "READ",
            "impact": "LOW",
            "uncertainty_pct": 0,
            "reversible": False,
            "external_side_effects": False,
        })
    decision = govern_agent_plan(
        nodes,
        trusted_context={
            "tenant_id": context.tenant_id,
            "workspace_id": context.workspace_id,
        },
        max_depth=2,
        max_fanout=8,
        max_nodes=16,
        call_limit=max_jobs,
        calls_used=0,
        token_limit=100000,
        tokens_used=0,
        wall_seconds_limit=300,
        wall_seconds_used=0,
        memory_mb_limit=1024,
        memory_mb_used=0,
    )
    decision = dict(decision)
    decision["due_count"] = len(due)
    decision["selected_count"] = len(selected)
    decision["capabilities"] = capabilities
    return decision


def worker_tick(
    access: Mapping[str, Any] | None,
    checkpoint: Mapping[str, Any],
    *,
    runtime_id: str,
    system_context: Mapping[str, Any] | None = None,
    voice_status: Mapping[str, Any] | None = None,
    max_jobs: int = 5,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = utc(now or datetime.now(timezone.utc))
    context = authenticated_context(access, Domain.ADMIN)
    state, status = load_worker_state(context, checkpoint)
    if status["state"] == "CONTEXT_ISOLATED":
        raise ValueError("WORKER_CONTEXT_MISMATCH")

    if state["kill_switch"] or state["state"] == "KILLED":
        return {
            "schema": SCHEMA,
            "status": "KILLED",
            "checkpoint": dict(checkpoint or {}),
            "processed": 0,
            "lease": {"state": "NOT_CLAIMED"},
            "external_action_executed": False,
        }
    if state["state"] != "ARMED":
        return {
            "schema": SCHEMA,
            "status": state["state"],
            "checkpoint": dict(checkpoint or {}),
            "processed": 0,
            "lease": {"state": "NOT_CLAIMED"},
            "external_action_executed": False,
        }

    loop_governor = _govern_due_batch(
        context,
        checkpoint,
        current=current,
        max_jobs=max_jobs,
    )
    if loop_governor.get("state") == "BLOCK":
        return {
            "schema": SCHEMA,
            "status": "LOOP_GOVERNOR_BLOCKED",
            "checkpoint": dict(checkpoint or {}),
            "processed": 0,
            "lease": {"state": "NOT_CLAIMED"},
            "loop_governor": loop_governor,
            "external_action_executed": False,
            "real_trading_enabled": False,
        }

    claimed_state, lease_result = _claim_lease(
        state,
        runtime_id=runtime,
        now=current,
    )
    if lease_result["state"] == "LEASE_HELD":
        return {
            "schema": SCHEMA,
            "status": "LEASE_HELD",
            "checkpoint": dict(checkpoint or {}),
            "processed": 0,
            "lease": lease_result,
            "external_action_executed": False,
        }

    staged = attach_worker_state(checkpoint, context, claimed_state)
    authorization_digest = digest({
        "mode": "ARMED_WORKER",
        "actor": context.actor_id,
        "scope": context.key,
        "arm_digest": claimed_state["arm_digest"],
        "runtime_id": runtime,
        "lease_token": lease_result["token"],
        "lease_expires_at": lease_result["expires_at"],
    })
    batch = _execute_due_local_work_authorized(
        access,
        staged,
        system_context=system_context,
        voice_status=voice_status,
        authorization_mode="ARMED_WORKER",
        authorization_digest=authorization_digest,
        max_jobs=max_jobs,
        now=current,
    )
    result_checkpoint = batch.get("checkpoint") or staged
    state_after, state_status = load_worker_state(context, result_checkpoint)
    if state_status["state"] == "CONTEXT_ISOLATED":
        raise ValueError("WORKER_CONTEXT_MISMATCH")
    stats = _normalize_stats(state_after["stats"])
    stats["ticks"] += 1
    stats["processed"] += int(batch.get("processed") or 0)
    stats["succeeded"] += int(batch.get("succeeded") or 0)
    stats["failed"] += int(batch.get("failed") or 0)
    stats["blocked"] += int(batch.get("blocked") or 0)
    stats["last_tick_at"] = current.isoformat()
    stats["last_tick_status"] = str(batch.get("status") or "UNKNOWN")[:120]
    stats["last_heartbeat_at"] = current.isoformat()
    retry_queue = _retry_queue_from_receipts(context, result_checkpoint, current)
    next_state = _mutated(
        state_after,
        retry_queue=retry_queue,
        stats=stats,
    )
    final_checkpoint = attach_worker_state(
        result_checkpoint,
        context,
        next_state,
    )
    return {
        "schema": SCHEMA,
        "status": "TICK_COMPLETED",
        "checkpoint": final_checkpoint,
        "lease": lease_result,
        "worker": next_state,
        "loop_governor": loop_governor,
        "batch_status": str(batch.get("status") or "UNKNOWN"),
        "processed": int(batch.get("processed") or 0),
        "succeeded": int(batch.get("succeeded") or 0),
        "failed": int(batch.get("failed") or 0),
        "blocked": int(batch.get("blocked") or 0),
        "action_receipts": list(batch.get("action_receipts") or []),
        "action_receipts_are_authority": False,
        "retry_queue_count": len(retry_queue),
        "requires_checkpoint_save": True,
        "external_persisted": False,
        "session_autonomy": True,
        "multi_instance_safe": False,
        "concurrency_scope": "CALLER_CHECKPOINT_ONLY",
        "lease_external_persistence": False,
        "continuous_24x7_confirmed": False,
        "provider_called": False,
        "external_action_executed": False,
        "real_trading_enabled": False,
        "payment_executed": False,
        "publication_executed": False,
        "deploy_executed": False,
    }


__all__ = [
    "SCHEMA",
    "WORKER_NAMESPACE",
    "WORKER_SCHEMA",
    "WORKER_STATES",
    "DEFAULT_INTERVAL_SECONDS",
    "DEFAULT_LEASE_SECONDS",
    "worker_integrity",
    "load_worker_state",
    "attach_worker_state",
    "arm_worker",
    "pause_worker",
    "kill_worker",
    "worker_snapshot",
    "worker_tick",
]
