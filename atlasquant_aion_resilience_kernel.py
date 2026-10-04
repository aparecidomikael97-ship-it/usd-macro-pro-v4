"""AION V2.16 observability, resilience and recovery kernel.

This module consolidates operational evidence into a deterministic posture.
It never executes an external action, arms a worker, changes a kill switch,
performs recovery, or grants execution authority.

It consumes explicit host evidence only:
- service/queue metrics;
- integrity evidence;
- runtime/kill-switch posture;
- recovery verification;
- dependency circuit-breaker evidence.

The kernel is deny-by-default and fail-closed.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_RESILIENCE_POSTURE_V1"
CIRCUIT_SCHEMA = "ATLASQUANT_AION_CIRCUIT_BREAKER_V1"
BACKPRESSURE_SCHEMA = "ATLASQUANT_AION_BACKPRESSURE_V1"

HEALTHY = "HEALTHY"
DEGRADED = "DEGRADED"
BLOCKED = "BLOCKED"
CLOSED = "CLOSED"
OPEN = "OPEN"
HALF_OPEN = "HALF_OPEN"

DEFAULT_POLICY = {
    "latency_p95_soft_ms": 1200.0,
    "latency_p95_hard_ms": 5000.0,
    "error_rate_soft": 0.05,
    "error_rate_hard": 0.20,
    "saturation_soft": 0.75,
    "saturation_hard": 0.95,
    "queue_depth_soft": 100,
    "queue_depth_hard": 500,
    "retry_backlog_soft": 50,
    "retry_backlog_hard": 200,
    "circuit_error_rate_open": 0.30,
    "circuit_failure_count_open": 5,
}

REQUIRED_INTEGRITY = (
    "journal_verified",
    "audit_chain_verified",
    "checkpoint_verified",
)
REQUIRED_RECOVERY = (
    "backup_verified",
    "restore_drill_passed",
    "journal_replay_verified",
    "crash_recovery_verified",
)


def _exact_bool(value: Any) -> bool:
    return value is True


def _number(value: Any, name: str, *, minimum: float = 0.0, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} invalid")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < minimum or (maximum is not None and parsed > maximum):
        raise ValueError(f"{name} invalid")
    return parsed


def _integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} invalid")
    return value


def _policy(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(DEFAULT_POLICY)
    if raw is not None:
        if not isinstance(raw, Mapping):
            raise ValueError("policy invalid")
        unknown = set(raw) - set(DEFAULT_POLICY)
        if unknown:
            raise ValueError("policy unknown fields")
        data.update(dict(raw))

    for key in (
        "latency_p95_soft_ms",
        "latency_p95_hard_ms",
        "error_rate_soft",
        "error_rate_hard",
        "saturation_soft",
        "saturation_hard",
        "circuit_error_rate_open",
    ):
        upper = 1.0 if "rate" in key or "saturation" in key else None
        data[key] = _number(data[key], key, minimum=0.0, maximum=upper)

    for key in (
        "queue_depth_soft",
        "queue_depth_hard",
        "retry_backlog_soft",
        "retry_backlog_hard",
        "circuit_failure_count_open",
    ):
        data[key] = _integer(data[key], key, minimum=0)

    pairs = (
        ("latency_p95_soft_ms", "latency_p95_hard_ms"),
        ("error_rate_soft", "error_rate_hard"),
        ("saturation_soft", "saturation_hard"),
        ("queue_depth_soft", "queue_depth_hard"),
        ("retry_backlog_soft", "retry_backlog_hard"),
    )
    for soft, hard in pairs:
        if data[soft] > data[hard]:
            raise ValueError(f"{soft} exceeds {hard}")
    return data


def circuit_breaker_transition(
    *,
    previous_state: str,
    consecutive_failures: int,
    rolling_error_rate: float,
    cooldown_elapsed: bool = False,
    probe_success: bool | None = None,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic circuit-breaker decision without calling anything."""
    p = _policy(policy)
    prev = str(previous_state or "").upper()
    if prev not in {CLOSED, OPEN, HALF_OPEN}:
        raise ValueError("invalid circuit state")
    failures = _integer(consecutive_failures, "consecutive_failures", minimum=0)
    error_rate = _number(rolling_error_rate, "rolling_error_rate", minimum=0.0, maximum=1.0)
    cooldown = _exact_bool(cooldown_elapsed)

    state = prev
    reason = "UNCHANGED"

    if prev == CLOSED:
        if (
            failures >= p["circuit_failure_count_open"]
            or error_rate >= p["circuit_error_rate_open"]
        ):
            state = OPEN
            reason = "FAILURE_THRESHOLD_EXCEEDED"
    elif prev == OPEN:
        if cooldown:
            state = HALF_OPEN
            reason = "COOLDOWN_ELAPSED"
    else:  # HALF_OPEN
        if probe_success is True:
            state = CLOSED
            reason = "PROBE_SUCCEEDED"
        elif probe_success is False:
            state = OPEN
            reason = "PROBE_FAILED"
        else:
            state = HALF_OPEN
            reason = "PROBE_REQUIRED"

    return {
        "schema": CIRCUIT_SCHEMA,
        "previous_state": prev,
        "state": state,
        "reason": reason,
        "consecutive_failures": failures,
        "rolling_error_rate": error_rate,
        "cooldown_elapsed": cooldown,
        "probe_success": probe_success if isinstance(probe_success, bool) else None,
        "dependency_call_performed": False,
        "execution_allowed": False,
    }


def backpressure_decision(
    *,
    queue_depth: int,
    retry_backlog: int,
    saturation: float,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return ACCEPT/THROTTLE/REJECT_NEW_WORK without mutating any queue."""
    p = _policy(policy)
    queue = _integer(queue_depth, "queue_depth")
    retries = _integer(retry_backlog, "retry_backlog")
    sat = _number(saturation, "saturation", minimum=0.0, maximum=1.0)

    hard = (
        queue >= p["queue_depth_hard"]
        or retries >= p["retry_backlog_hard"]
        or sat >= p["saturation_hard"]
    )
    soft = (
        queue >= p["queue_depth_soft"]
        or retries >= p["retry_backlog_soft"]
        or sat >= p["saturation_soft"]
    )

    if hard:
        decision = "REJECT_NEW_WORK"
    elif soft:
        decision = "THROTTLE"
    else:
        decision = "ACCEPT"

    return {
        "schema": BACKPRESSURE_SCHEMA,
        "decision": decision,
        "queue_depth": queue,
        "retry_backlog": retries,
        "saturation": sat,
        "backpressure_required": decision != "ACCEPT",
        "queue_mutated": False,
        "execution_allowed": False,
    }


def evaluate_resilience_posture(
    *,
    metrics: Mapping[str, Any],
    integrity: Mapping[str, Any],
    runtime: Mapping[str, Any],
    recovery: Mapping[str, Any],
    circuits: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate canonical operational posture from explicit evidence.

    Positive posture never grants execution authority.
    """
    if not all(isinstance(x, Mapping) for x in (metrics, integrity, runtime, recovery)):
        raise ValueError("resilience evidence must be mappings")
    if circuits is not None and not isinstance(circuits, Mapping):
        raise ValueError("circuits invalid")

    p = _policy(policy)
    latency = _number(metrics.get("latency_p95_ms"), "latency_p95_ms")
    error_rate = _number(metrics.get("error_rate"), "error_rate", maximum=1.0)
    saturation = _number(metrics.get("saturation"), "saturation", maximum=1.0)
    queue_depth = _integer(metrics.get("queue_depth"), "queue_depth")
    retry_backlog = _integer(metrics.get("retry_backlog"), "retry_backlog")

    blockers: list[str] = []
    degradations: list[str] = []

    for key in REQUIRED_INTEGRITY:
        if not _exact_bool(integrity.get(key)):
            blockers.append(f"INTEGRITY_NOT_VERIFIED:{key}")

    for key in REQUIRED_RECOVERY:
        if not _exact_bool(recovery.get(key)):
            blockers.append(f"RECOVERY_NOT_VERIFIED:{key}")

    kill_switch = runtime.get("global_kill_switch")
    if kill_switch is not False:
        blockers.append("GLOBAL_KILL_SWITCH_NOT_RELEASED")

    runtime_health = str(runtime.get("runtime_health") or "").upper()
    if runtime_health not in {"HEALTHY", "CONFIRMED", "PASS"}:
        blockers.append("RUNTIME_HEALTH_NOT_CONFIRMED")

    read_only = runtime.get("read_only")
    if read_only is not False:
        blockers.append("RUNTIME_NOT_EXECUTION_MODE")

    bp = backpressure_decision(
        queue_depth=queue_depth,
        retry_backlog=retry_backlog,
        saturation=saturation,
        policy=p,
    )
    if bp["decision"] == "REJECT_NEW_WORK":
        blockers.append("BACKPRESSURE_HARD_LIMIT")
    elif bp["decision"] == "THROTTLE":
        degradations.append("BACKPRESSURE_SOFT_LIMIT")

    if latency >= p["latency_p95_hard_ms"]:
        blockers.append("LATENCY_HARD_LIMIT")
    elif latency >= p["latency_p95_soft_ms"]:
        degradations.append("LATENCY_SOFT_LIMIT")

    if error_rate >= p["error_rate_hard"]:
        blockers.append("ERROR_RATE_HARD_LIMIT")
    elif error_rate >= p["error_rate_soft"]:
        degradations.append("ERROR_RATE_SOFT_LIMIT")

    open_circuits: list[str] = []
    half_open_circuits: list[str] = []
    for name, raw in sorted((circuits or {}).items(), key=lambda item: str(item[0])):
        if not isinstance(name, str) or not name or not isinstance(raw, Mapping):
            blockers.append("CIRCUIT_EVIDENCE_INVALID")
            continue
        state = str(raw.get("state") or "").upper()
        if state == OPEN:
            open_circuits.append(name)
        elif state == HALF_OPEN:
            half_open_circuits.append(name)
        elif state != CLOSED:
            blockers.append(f"CIRCUIT_STATE_INVALID:{name}")

    if open_circuits:
        blockers.append("CIRCUIT_OPEN")
    if half_open_circuits:
        degradations.append("CIRCUIT_HALF_OPEN")

    if blockers:
        state = BLOCKED
    elif degradations:
        state = DEGRADED
    else:
        state = HEALTHY

    return {
        "schema": SCHEMA,
        "state": state,
        "blockers": sorted(set(blockers)),
        "degradations": sorted(set(degradations)),
        "metrics": {
            "latency_p95_ms": latency,
            "error_rate": error_rate,
            "saturation": saturation,
            "queue_depth": queue_depth,
            "retry_backlog": retry_backlog,
        },
        "backpressure": bp,
        "open_circuits": open_circuits,
        "half_open_circuits": half_open_circuits,
        "integrity_verified": all(_exact_bool(integrity.get(k)) for k in REQUIRED_INTEGRITY),
        "recovery_verified": all(_exact_bool(recovery.get(k)) for k in REQUIRED_RECOVERY),
        "runtime_health_confirmed": runtime_health in {"HEALTHY", "CONFIRMED", "PASS"},
        "global_kill_switch": bool(kill_switch),
        "read_only": read_only is True,
        "external_effects_allowed_by_resilience": state == HEALTHY,
        "execution_allowed": False,
        "approval_implied": False,
        "authority_implied": False,
        "worker_armed": False,
        "external_action_executed": False,
        "network_called": False,
        "state_mutated": False,
    }


__all__ = [
    "SCHEMA",
    "CIRCUIT_SCHEMA",
    "BACKPRESSURE_SCHEMA",
    "DEFAULT_POLICY",
    "circuit_breaker_transition",
    "backpressure_decision",
    "evaluate_resilience_posture",
]
