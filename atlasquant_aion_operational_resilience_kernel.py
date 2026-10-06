"""AION V2.16 operational resilience and observability composition kernel.

This module composes existing AION resilience primitives with explicit SLO,
bulkhead, rate-limit/backpressure and recovery-readiness evidence.

It is deliberately a control/readiness layer. It does not call providers,
execute tools, mutate kill switches, restore checkpoints, deploy, trade or grant
execution authority.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping

from atlasquant_aion_resilience import (
    circuit_breaker,
    resource_governor,
    safe_mode_posture,
    watchdog,
)

SCHEMA = "ATLASQUANT_AION_OPERATIONAL_RESILIENCE_V1"
TRACE_SCHEMA = "ATLASQUANT_AION_TRACE_CONTEXT_V1"
SLO_SCHEMA = "ATLASQUANT_AION_SLO_WINDOW_V1"
BULKHEAD_SCHEMA = "ATLASQUANT_AION_BULKHEAD_GATE_V1"
RATE_SCHEMA = "ATLASQUANT_AION_RATE_LIMIT_GATE_V1"
BACKPRESSURE_SCHEMA = "ATLASQUANT_AION_BACKPRESSURE_GATE_V1"

MAX_ID = 256


def _clean(value: Any, limit: int = MAX_ID) -> str:
    text = " ".join(str(value or "").replace("\x00", "").split())
    return text[:limit]


def _exact_bool(value: Any, name: str) -> bool:
    if value is not True and value is not False:
        raise ValueError(f"{name} must be an exact boolean")
    return value is True


def _finite_nonnegative(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    try:
        number = float(value)
    except Exception as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return number


def _positive(value: Any, name: str) -> float:
    number = _finite_nonnegative(value, name)
    if number <= 0:
        raise ValueError(f"{name} must be positive")
    return number


def _int_nonnegative(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _int_positive(value: Any, name: str) -> int:
    number = _int_nonnegative(value, name)
    if number <= 0:
        raise ValueError(f"{name} must be positive")
    return number


def _digest(payload: Mapping[str, Any], length: int = 32) -> str:
    raw = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:length]


def build_trace_context(
    *,
    request_id: Any,
    task_id: Any,
    execution_id: Any = "",
    parent_span_id: Any = "",
) -> dict[str, Any]:
    """Build deterministic correlation identifiers from canonical local IDs.

    This carries identifiers only; request/tool payloads and secrets are not
    accepted into the trace context.
    """
    request = _clean(request_id)
    task = _clean(task_id)
    execution = _clean(execution_id)
    parent = _clean(parent_span_id, 64)
    if not request or not task:
        raise ValueError("request_id and task_id are required")
    seed = {"request_id": request, "task_id": task}
    trace_id = _digest(seed, 32)
    span_seed = {
        "trace_id": trace_id,
        "execution_id": execution or task,
        "parent_span_id": parent,
    }
    span_id = _digest(span_seed, 16)
    return {
        "schema": TRACE_SCHEMA,
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent,
        "request_id": request,
        "task_id": task,
        "execution_id": execution,
        "contains_payload": False,
        "contains_secret_material": False,
        "executes_action": False,
    }


def evaluate_slo_window(
    *,
    request_count: Any,
    error_count: Any,
    latency_p95_ms: Any,
    latency_slo_ms: Any,
    queue_depth: Any,
    queue_capacity: Any,
    cost_usd: Any,
    cost_limit_usd: Any,
    saturation_pct: Any,
    saturation_slo_pct: Any,
    heartbeat_age_seconds: Any,
    heartbeat_slo_seconds: Any,
    minimum_availability_pct: Any = 99.0,
) -> dict[str, Any]:
    """Evaluate one explicit telemetry window without inventing missing evidence."""
    requests = _int_nonnegative(request_count, "request_count")
    errors = _int_nonnegative(error_count, "error_count")
    if errors > requests:
        raise ValueError("error_count cannot exceed request_count")
    latency = _finite_nonnegative(latency_p95_ms, "latency_p95_ms")
    latency_limit = _positive(latency_slo_ms, "latency_slo_ms")
    depth = _int_nonnegative(queue_depth, "queue_depth")
    capacity = _int_positive(queue_capacity, "queue_capacity")
    cost = _finite_nonnegative(cost_usd, "cost_usd")
    cost_limit = _positive(cost_limit_usd, "cost_limit_usd")
    saturation = _finite_nonnegative(saturation_pct, "saturation_pct")
    saturation_limit = _positive(saturation_slo_pct, "saturation_slo_pct")
    if saturation > 100 or saturation_limit > 100:
        raise ValueError("saturation percentage must be <= 100")
    heartbeat_age = _finite_nonnegative(heartbeat_age_seconds, "heartbeat_age_seconds")
    heartbeat_limit = _positive(heartbeat_slo_seconds, "heartbeat_slo_seconds")
    minimum_availability = _positive(
        minimum_availability_pct, "minimum_availability_pct"
    )
    if minimum_availability > 100:
        raise ValueError("minimum_availability_pct must be <= 100")

    availability = None
    blockers: list[str] = []
    warnings: list[str] = []
    if requests == 0:
        blockers.append("SLO_NO_TRAFFIC_EVIDENCE")
    else:
        availability = ((requests - errors) / requests) * 100.0
        if availability < minimum_availability:
            blockers.append("SLO_AVAILABILITY_BREACH")

    error_rate = (errors / requests * 100.0) if requests else None
    queue_usage = depth / capacity * 100.0

    if latency > latency_limit:
        blockers.append("SLO_LATENCY_BREACH")
    elif latency >= latency_limit * 0.8:
        warnings.append("SLO_LATENCY_NEAR_LIMIT")

    if depth >= capacity:
        blockers.append("SLO_QUEUE_CAPACITY_BREACH")
    elif queue_usage >= 80:
        warnings.append("SLO_QUEUE_NEAR_CAPACITY")

    if cost > cost_limit:
        blockers.append("SLO_COST_BREACH")
    elif cost >= cost_limit * 0.8:
        warnings.append("SLO_COST_NEAR_LIMIT")

    if saturation > saturation_limit:
        blockers.append("SLO_SATURATION_BREACH")
    elif saturation >= saturation_limit * 0.8:
        warnings.append("SLO_SATURATION_NEAR_LIMIT")

    if heartbeat_age > heartbeat_limit:
        blockers.append("SLO_HEARTBEAT_STALE")

    state = "BREACHED" if blockers else "DEGRADED" if warnings else "HEALTHY"
    return {
        "schema": SLO_SCHEMA,
        "state": state,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "request_count": requests,
        "error_count": errors,
        "error_rate_pct": round(error_rate, 4) if error_rate is not None else None,
        "availability_pct": round(availability, 4) if availability is not None else None,
        "minimum_availability_pct": minimum_availability,
        "latency_p95_ms": latency,
        "latency_slo_ms": latency_limit,
        "queue_depth": depth,
        "queue_capacity": capacity,
        "queue_usage_pct": round(queue_usage, 4),
        "cost_usd": cost,
        "cost_limit_usd": cost_limit,
        "saturation_pct": saturation,
        "saturation_slo_pct": saturation_limit,
        "heartbeat_age_seconds": heartbeat_age,
        "heartbeat_slo_seconds": heartbeat_limit,
        "execution_allowed": False,
        "executes_action": False,
    }


def bulkhead_gate(
    *,
    scope: Any,
    inflight: Any,
    limit: Any,
    reserved_critical_slots: Any = 0,
    critical_request: Any = False,
) -> dict[str, Any]:
    """Recommend admission while preserving reserved capacity between workloads."""
    name = _clean(scope, 160)
    if not name:
        raise ValueError("bulkhead scope required")
    used = _int_nonnegative(inflight, "inflight")
    ceiling = _int_positive(limit, "limit")
    reserved = _int_nonnegative(reserved_critical_slots, "reserved_critical_slots")
    if reserved >= ceiling:
        raise ValueError("reserved_critical_slots must be below limit")
    critical = _exact_bool(critical_request, "critical_request")

    effective_limit = ceiling if critical else ceiling - reserved
    if used >= ceiling:
        state = "SHED"
        reason = "BULKHEAD_FULL"
    elif used >= effective_limit:
        state = "ADMIT_CRITICAL_ONLY"
        reason = "BULKHEAD_RESERVED_CAPACITY"
    else:
        state = "ADMIT"
        reason = ""

    admit_recommended = state == "ADMIT" or (
        state == "ADMIT_CRITICAL_ONLY" and critical
    )
    return {
        "schema": BULKHEAD_SCHEMA,
        "scope": name,
        "state": state,
        "reason": reason,
        "inflight": used,
        "limit": ceiling,
        "reserved_critical_slots": reserved,
        "critical_request": critical,
        "admit_recommended": admit_recommended,
        "automatic_dispatch": False,
        "execution_allowed": False,
        "executes_action": False,
    }


def rate_limit_gate(
    *,
    scope: Any,
    requests_in_window: Any,
    hard_limit: Any,
    soft_limit_pct: Any = 80.0,
) -> dict[str, Any]:
    """Evaluate an explicit rate window; it never mutates a remote limiter."""
    name = _clean(scope, 160)
    if not name:
        raise ValueError("rate-limit scope required")
    used = _int_nonnegative(requests_in_window, "requests_in_window")
    hard = _int_positive(hard_limit, "hard_limit")
    soft_pct = _positive(soft_limit_pct, "soft_limit_pct")
    if soft_pct >= 100:
        raise ValueError("soft_limit_pct must be below 100")
    soft = max(1, math.ceil(hard * soft_pct / 100.0))

    if used >= hard:
        state = "REJECT_NEW"
        reason = "RATE_HARD_LIMIT"
    elif used >= soft:
        state = "THROTTLE"
        reason = "RATE_SOFT_LIMIT"
    else:
        state = "ALLOW"
        reason = ""

    return {
        "schema": RATE_SCHEMA,
        "scope": name,
        "state": state,
        "reason": reason,
        "requests_in_window": used,
        "soft_limit": soft,
        "hard_limit": hard,
        "admit_recommended": state == "ALLOW",
        "automatic_dispatch": False,
        "execution_allowed": False,
        "executes_action": False,
    }


def backpressure_gate(
    *,
    queue_depth: Any,
    queue_capacity: Any,
    arrival_rate_per_sec: Any,
    service_rate_per_sec: Any,
) -> dict[str, Any]:
    """Recommend producer backpressure from bounded queue/service evidence."""
    depth = _int_nonnegative(queue_depth, "queue_depth")
    capacity = _int_positive(queue_capacity, "queue_capacity")
    arrival = _finite_nonnegative(arrival_rate_per_sec, "arrival_rate_per_sec")
    service = _finite_nonnegative(service_rate_per_sec, "service_rate_per_sec")
    ratio = depth / capacity

    if depth >= capacity or (service == 0 and arrival > 0):
        state = "REJECT_NEW"
        reason = "QUEUE_SATURATED"
    elif ratio >= 0.8 or (service > 0 and arrival >= service * 1.25):
        state = "THROTTLE"
        reason = "BACKPRESSURE_REQUIRED"
    elif service > 0 and arrival > service:
        state = "DRAIN_PRIORITY"
        reason = "ARRIVAL_EXCEEDS_SERVICE"
    else:
        state = "NORMAL"
        reason = ""

    return {
        "schema": BACKPRESSURE_SCHEMA,
        "state": state,
        "reason": reason,
        "queue_depth": depth,
        "queue_capacity": capacity,
        "queue_usage_pct": round(ratio * 100.0, 4),
        "arrival_rate_per_sec": arrival,
        "service_rate_per_sec": service,
        "admit_recommended": state in {"NORMAL", "DRAIN_PRIORITY"},
        "automatic_dispatch": False,
        "execution_allowed": False,
        "executes_action": False,
    }


def operational_resilience_view(
    *,
    trace: Mapping[str, Any],
    slo: Mapping[str, Any],
    component: Any,
    previous_circuit_state: Any = "CLOSED",
    consecutive_failures: Any = 0,
    error_rate_pct: Any = 0,
    critical_signal: Any = False,
    recovery_probe_passed: Any = False,
    heartbeat_age_seconds: Any = 0,
    repeated_action_count: Any = 0,
    unhandled_error_count: Any = 0,
    calls_used: Any = 0,
    call_limit: Any = 100,
    tokens_used: Any = 0,
    token_limit: Any = 100000,
    wall_seconds_used: Any = 0,
    wall_seconds_limit: Any = 300,
    memory_mb_used: Any = 0,
    memory_mb_limit: Any = 1024,
    bulkhead: Mapping[str, Any] | None = None,
    rate_limit: Mapping[str, Any] | None = None,
    backpressure: Mapping[str, Any] | None = None,
    authority_integrity_ok: Any = True,
    policy_integrity_ok: Any = True,
    secret_exposure: Any = False,
    kill_switch_engaged: Any = False,
    backup_verified: Any = False,
    restore_drill_verified: Any = False,
    journal_recovery_verified: Any = False,
    crash_recovery_verified: Any = False,
    checkpoint_integrity_verified: Any = False,
    audit_chain_verified: Any = False,
) -> dict[str, Any]:
    """Compose one fail-closed operational posture from explicit evidence."""
    if not isinstance(trace, Mapping) or trace.get("schema") != TRACE_SCHEMA:
        raise ValueError("trusted trace context required")
    if not isinstance(slo, Mapping) or slo.get("schema") != SLO_SCHEMA:
        raise ValueError("SLO window required")

    authority_ok = _exact_bool(authority_integrity_ok, "authority_integrity_ok")
    policy_ok = _exact_bool(policy_integrity_ok, "policy_integrity_ok")
    secret = _exact_bool(secret_exposure, "secret_exposure")
    kill = _exact_bool(kill_switch_engaged, "kill_switch_engaged")
    backup_ok = _exact_bool(backup_verified, "backup_verified")
    restore_ok = _exact_bool(restore_drill_verified, "restore_drill_verified")
    journal_ok = _exact_bool(journal_recovery_verified, "journal_recovery_verified")
    crash_ok = _exact_bool(crash_recovery_verified, "crash_recovery_verified")
    checkpoint_ok = _exact_bool(checkpoint_integrity_verified, "checkpoint_integrity_verified")
    audit_ok = _exact_bool(audit_chain_verified, "audit_chain_verified")

    circuit = circuit_breaker(
        component,
        previous_state=previous_circuit_state,
        consecutive_failures=consecutive_failures,
        error_rate_pct=error_rate_pct,
        critical_signal=critical_signal,
        recovery_probe_passed=recovery_probe_passed,
    )
    watch = watchdog(
        component,
        heartbeat_age_seconds=heartbeat_age_seconds,
        repeated_action_count=repeated_action_count,
        unhandled_error_count=unhandled_error_count,
    )
    resources = resource_governor(
        component,
        call_limit=call_limit,
        calls_used=calls_used,
        token_limit=token_limit,
        tokens_used=tokens_used,
        wall_seconds_limit=wall_seconds_limit,
        wall_seconds_used=wall_seconds_used,
        memory_mb_limit=memory_mb_limit,
        memory_mb_used=memory_mb_used,
    )

    bulk = dict(bulkhead or {})
    rate = dict(rate_limit or {})
    pressure = dict(backpressure or {})
    blockers: list[str] = []

    if slo.get("state") == "BREACHED":
        blockers.extend(str(x) for x in slo.get("blockers") or [])
    if circuit.get("state") != "CLOSED":
        blockers.append("CIRCUIT_NOT_CLOSED")
    if watch.get("state") != "HEALTHY":
        blockers.append("WATCHDOG_NOT_HEALTHY")
    if resources.get("state") != "WITHIN_BUDGET":
        blockers.append("RESOURCE_GOVERNOR_RESTRICTED")
    if bulk and bulk.get("admit_recommended") is not True:
        blockers.append("BULKHEAD_RESTRICTED")
    if rate and rate.get("state") != "ALLOW":
        blockers.append("RATE_LIMIT_RESTRICTED")
    if pressure and pressure.get("state") not in {"NORMAL", "DRAIN_PRIORITY"}:
        blockers.append("BACKPRESSURE_RESTRICTED")
    if not backup_ok:
        blockers.append("BACKUP_NOT_VERIFIED")
    if not restore_ok:
        blockers.append("RESTORE_DRILL_NOT_VERIFIED")
    if not journal_ok:
        blockers.append("JOURNAL_RECOVERY_NOT_VERIFIED")
    if not crash_ok:
        blockers.append("CRASH_RECOVERY_NOT_VERIFIED")
    if not checkpoint_ok:
        blockers.append("CHECKPOINT_INTEGRITY_NOT_VERIFIED")
    if not audit_ok:
        blockers.append("AUDIT_CHAIN_NOT_VERIFIED")
    if kill:
        blockers.append("GLOBAL_KILL_SWITCH_ENGAGED")

    safe = safe_mode_posture(
        authority_integrity_ok=authority_ok,
        policy_integrity_ok=policy_ok,
        secret_exposure=secret,
        open_circuits=1 if circuit.get("state") != "CLOSED" else 0,
        isolate_recommendations=1 if watch.get("state") == "ISOLATE_RECOMMENDED" else 0,
    )

    if kill:
        posture = "STOPPED_BY_KILL_SWITCH"
    elif safe.get("mode") == "EMERGENCY_STOP_RECOMMENDED":
        posture = "EMERGENCY_STOP_RECOMMENDED"
    elif blockers or safe.get("mode") == "DEGRADED_READ_ONLY":
        posture = "DEGRADED_READ_ONLY"
    elif slo.get("state") == "DEGRADED":
        posture = "DEGRADED_MONITORED"
    else:
        posture = "NORMAL_MONITORED"

    recovery_ready = backup_ok and restore_ok and journal_ok and crash_ok
    operational_integrity_ready = checkpoint_ok and audit_ok
    operational_admission_recommended = posture in {
        "NORMAL_MONITORED",
        "DEGRADED_MONITORED",
    } and not blockers

    return {
        "schema": SCHEMA,
        "posture": posture,
        "blockers": sorted(set(blockers)),
        "trace": dict(trace),
        "slo": dict(slo),
        "circuit_breaker": circuit,
        "watchdog": watch,
        "resource_governor": resources,
        "bulkhead": bulk,
        "rate_limit": rate,
        "backpressure": pressure,
        "safe_mode": safe,
        "recovery_readiness": {
            "backup_verified": backup_ok,
            "restore_drill_verified": restore_ok,
            "journal_recovery_verified": journal_ok,
            "crash_recovery_verified": crash_ok,
            "recovery_ready": recovery_ready,
            "automatic_restore": False,
            "automatic_rollback": False,
        },
        "integrity_readiness": {
            "checkpoint_integrity_verified": checkpoint_ok,
            "audit_chain_verified": audit_ok,
            "operational_integrity_ready": operational_integrity_ready,
        },
        "immutable_journal_required": True,
        "deterministic_replay_required": True,
        "crash_recovery_required": True,
        "kill_switch_engaged": kill,
        "operational_admission_recommended": operational_admission_recommended,
        "external_side_effects_allowed": False,
        "execution_allowed": False,
        "approval_implied": False,
        "automatic_kill_switch_mutation": False,
        "automatic_restore": False,
        "automatic_rollback": False,
        "provider_called": False,
        "tool_called": False,
        "real_trading_enabled": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "TRACE_SCHEMA",
    "SLO_SCHEMA",
    "BULKHEAD_SCHEMA",
    "RATE_SCHEMA",
    "BACKPRESSURE_SCHEMA",
    "build_trace_context",
    "evaluate_slo_window",
    "bulkhead_gate",
    "rate_limit_gate",
    "backpressure_gate",
    "operational_resilience_view",
]
