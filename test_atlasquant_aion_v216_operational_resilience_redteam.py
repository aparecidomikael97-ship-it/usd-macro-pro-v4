"""AION V2.16 red-team for operational resilience composition."""
from __future__ import annotations

import json

import pytest

from atlasquant_aion_operational_resilience_kernel import (
    backpressure_gate,
    build_trace_context,
    bulkhead_gate,
    evaluate_slo_window,
    operational_resilience_view,
    rate_limit_gate,
)


def trace(**kwargs):
    data = {
        "request_id": "req-001",
        "task_id": "task-001",
        "execution_id": "exe-001",
    }
    data.update(kwargs)
    return build_trace_context(**data)


def slo(**kwargs):
    data = {
        "request_count": 1000,
        "error_count": 1,
        "latency_p95_ms": 120,
        "latency_slo_ms": 500,
        "queue_depth": 10,
        "queue_capacity": 100,
        "cost_usd": 1.0,
        "cost_limit_usd": 10.0,
        "saturation_pct": 25,
        "saturation_slo_pct": 90,
        "heartbeat_age_seconds": 10,
        "heartbeat_slo_seconds": 60,
        "minimum_availability_pct": 99.0,
    }
    data.update(kwargs)
    return evaluate_slo_window(**data)


def bulk(**kwargs):
    data = {
        "scope": "core",
        "inflight": 1,
        "limit": 10,
        "reserved_critical_slots": 2,
        "critical_request": False,
    }
    data.update(kwargs)
    return bulkhead_gate(**data)


def rate(**kwargs):
    data = {
        "scope": "tenant/core",
        "requests_in_window": 10,
        "hard_limit": 100,
        "soft_limit_pct": 80,
    }
    data.update(kwargs)
    return rate_limit_gate(**data)


def pressure(**kwargs):
    data = {
        "queue_depth": 10,
        "queue_capacity": 100,
        "arrival_rate_per_sec": 5,
        "service_rate_per_sec": 10,
    }
    data.update(kwargs)
    return backpressure_gate(**data)


def view(**kwargs):
    data = {
        "trace": trace(),
        "slo": slo(),
        "component": "aion-core",
        "previous_circuit_state": "CLOSED",
        "consecutive_failures": 0,
        "error_rate_pct": 0,
        "critical_signal": False,
        "recovery_probe_passed": False,
        "heartbeat_age_seconds": 10,
        "repeated_action_count": 0,
        "unhandled_error_count": 0,
        "calls_used": 10,
        "call_limit": 100,
        "tokens_used": 1000,
        "token_limit": 100000,
        "wall_seconds_used": 10,
        "wall_seconds_limit": 300,
        "memory_mb_used": 100,
        "memory_mb_limit": 1024,
        "bulkhead": bulk(),
        "rate_limit": rate(),
        "backpressure": pressure(),
        "authority_integrity_ok": True,
        "policy_integrity_ok": True,
        "secret_exposure": False,
        "kill_switch_engaged": False,
        "backup_verified": True,
        "restore_drill_verified": True,
        "journal_recovery_verified": True,
    }
    data.update(kwargs)
    return operational_resilience_view(**data)


def test_trace_context_is_deterministic_and_payload_free():
    first = trace()
    second = trace()
    assert first == second
    assert first["trace_id"] == second["trace_id"]
    assert first["span_id"] == second["span_id"]
    assert first["contains_payload"] is False
    assert first["contains_secret_material"] is False
    assert first["executes_action"] is False


def test_trace_context_changes_with_task_or_execution():
    a = trace()
    b = trace(task_id="task-002")
    c = trace(execution_id="exe-002")
    assert a["trace_id"] != b["trace_id"]
    assert a["span_id"] != c["span_id"]


@pytest.mark.parametrize("request_id,task_id", [
    ("", "task"),
    ("req", ""),
    (None, "task"),
])
def test_trace_requires_correlation_identity(request_id, task_id):
    with pytest.raises(ValueError):
        build_trace_context(request_id=request_id, task_id=task_id)


def test_healthy_slo_window_is_explicit():
    result = slo()
    assert result["state"] == "HEALTHY"
    assert result["availability_pct"] == 99.9
    assert result["blockers"] == []
    assert result["execution_allowed"] is False


def test_no_traffic_never_fabricates_healthy_availability():
    result = slo(request_count=0, error_count=0)
    assert result["state"] == "BREACHED"
    assert result["availability_pct"] is None
    assert "SLO_NO_TRAFFIC_EVIDENCE" in result["blockers"]


@pytest.mark.parametrize("overrides,blocker", [
    ({"request_count": 100, "error_count": 5, "minimum_availability_pct": 99.0}, "SLO_AVAILABILITY_BREACH"),
    ({"latency_p95_ms": 501}, "SLO_LATENCY_BREACH"),
    ({"queue_depth": 100}, "SLO_QUEUE_CAPACITY_BREACH"),
    ({"cost_usd": 10.01}, "SLO_COST_BREACH"),
    ({"saturation_pct": 91}, "SLO_SATURATION_BREACH"),
    ({"heartbeat_age_seconds": 61}, "SLO_HEARTBEAT_STALE"),
])
def test_each_slo_breach_is_fail_closed(overrides, blocker):
    result = slo(**overrides)
    assert result["state"] == "BREACHED"
    assert blocker in result["blockers"]
    assert result["execution_allowed"] is False


@pytest.mark.parametrize("field,value", [
    ("latency_p95_ms", -1),
    ("cost_usd", float("nan")),
    ("saturation_pct", 101),
    ("queue_capacity", 0),
    ("request_count", True),
])
def test_invalid_slo_values_are_rejected(field, value):
    kwargs = {field: value}
    with pytest.raises(ValueError):
        slo(**kwargs)


def test_bulkhead_reserves_capacity_for_critical_work():
    normal = bulk(inflight=8, limit=10, reserved_critical_slots=2, critical_request=False)
    critical = bulk(inflight=8, limit=10, reserved_critical_slots=2, critical_request=True)
    assert normal["state"] == "ADMIT_CRITICAL_ONLY"
    assert normal["admit_recommended"] is False
    assert critical["state"] == "ADMIT"
    assert critical["admit_recommended"] is True


def test_bulkhead_full_sheds_even_critical_work():
    result = bulk(inflight=10, limit=10, critical_request=True)
    assert result["state"] == "SHED"
    assert result["admit_recommended"] is False
    assert result["automatic_dispatch"] is False


@pytest.mark.parametrize("used,state", [
    (10, "ALLOW"),
    (80, "THROTTLE"),
    (100, "REJECT_NEW"),
    (120, "REJECT_NEW"),
])
def test_rate_limit_postures(used, state):
    result = rate(requests_in_window=used)
    assert result["state"] == state
    assert result["automatic_dispatch"] is False
    assert result["execution_allowed"] is False


@pytest.mark.parametrize("kwargs,state", [
    ({"queue_depth": 10, "arrival_rate_per_sec": 5, "service_rate_per_sec": 10}, "NORMAL"),
    ({"queue_depth": 10, "arrival_rate_per_sec": 11, "service_rate_per_sec": 10}, "DRAIN_PRIORITY"),
    ({"queue_depth": 85, "arrival_rate_per_sec": 5, "service_rate_per_sec": 10}, "THROTTLE"),
    ({"queue_depth": 100, "arrival_rate_per_sec": 5, "service_rate_per_sec": 10}, "REJECT_NEW"),
    ({"queue_depth": 1, "arrival_rate_per_sec": 1, "service_rate_per_sec": 0}, "REJECT_NEW"),
])
def test_backpressure_postures(kwargs, state):
    result = pressure(**kwargs)
    assert result["state"] == state
    assert result["automatic_dispatch"] is False


def test_fully_healthy_operational_view_is_monitored_not_executable():
    result = view()
    assert result["posture"] == "NORMAL_MONITORED"
    assert result["blockers"] == []
    assert result["operational_admission_recommended"] is True
    assert result["recovery_readiness"]["recovery_ready"] is True
    assert result["external_side_effects_allowed"] is False
    assert result["execution_allowed"] is False
    assert result["approval_implied"] is False
    assert result["executes_action"] is False


def test_kill_switch_dominates_all_green_evidence():
    result = view(kill_switch_engaged=True)
    assert result["posture"] == "STOPPED_BY_KILL_SWITCH"
    assert "GLOBAL_KILL_SWITCH_ENGAGED" in result["blockers"]
    assert result["operational_admission_recommended"] is False
    assert result["automatic_kill_switch_mutation"] is False
    assert result["execution_allowed"] is False


@pytest.mark.parametrize("field", [
    "backup_verified",
    "restore_drill_verified",
    "journal_recovery_verified",
])
def test_recovery_evidence_is_required_for_normal_posture(field):
    result = view(**{field: False})
    assert result["posture"] == "DEGRADED_READ_ONLY"
    assert result["recovery_readiness"]["recovery_ready"] is False
    assert result["operational_admission_recommended"] is False
    assert result["automatic_restore"] is False
    assert result["automatic_rollback"] is False


def test_circuit_open_forces_degraded_read_only():
    result = view(consecutive_failures=3)
    assert result["circuit_breaker"]["state"] == "OPEN"
    assert result["posture"] == "DEGRADED_READ_ONLY"
    assert "CIRCUIT_NOT_CLOSED" in result["blockers"]


def test_watchdog_isolation_forces_degraded_read_only():
    result = view(repeated_action_count=5)
    assert result["watchdog"]["state"] == "ISOLATE_RECOMMENDED"
    assert result["posture"] == "DEGRADED_READ_ONLY"
    assert "WATCHDOG_NOT_HEALTHY" in result["blockers"]


def test_resource_saturation_forces_degraded_read_only():
    result = view(calls_used=100, call_limit=100)
    assert result["resource_governor"]["state"] == "CIRCUIT_BREAK"
    assert result["posture"] == "DEGRADED_READ_ONLY"
    assert "RESOURCE_GOVERNOR_RESTRICTED" in result["blockers"]


def test_bulkhead_restriction_forces_degraded_read_only():
    result = view(bulkhead=bulk(inflight=10, limit=10))
    assert result["posture"] == "DEGRADED_READ_ONLY"
    assert "BULKHEAD_RESTRICTED" in result["blockers"]


def test_rate_limit_restriction_forces_degraded_read_only():
    result = view(rate_limit=rate(requests_in_window=80))
    assert result["posture"] == "DEGRADED_READ_ONLY"
    assert "RATE_LIMIT_RESTRICTED" in result["blockers"]


def test_backpressure_restriction_forces_degraded_read_only():
    result = view(backpressure=pressure(queue_depth=85))
    assert result["posture"] == "DEGRADED_READ_ONLY"
    assert "BACKPRESSURE_RESTRICTED" in result["blockers"]


def test_slo_breach_forces_degraded_read_only():
    result = view(slo=slo(latency_p95_ms=900))
    assert result["posture"] == "DEGRADED_READ_ONLY"
    assert "SLO_LATENCY_BREACH" in result["blockers"]


def test_near_limit_slo_is_monitored_degraded_without_execution():
    near = slo(latency_p95_ms=450)
    assert near["state"] == "DEGRADED"
    result = view(slo=near)
    assert result["posture"] == "DEGRADED_MONITORED"
    assert result["operational_admission_recommended"] is True
    assert result["execution_allowed"] is False


@pytest.mark.parametrize("kwargs", [
    {"authority_integrity_ok": False},
    {"policy_integrity_ok": False},
    {"secret_exposure": True},
])
def test_integrity_or_secret_failure_requests_emergency_stop(kwargs):
    result = view(**kwargs)
    assert result["posture"] == "EMERGENCY_STOP_RECOMMENDED"
    assert result["execution_allowed"] is False
    assert result["external_side_effects_allowed"] is False


@pytest.mark.parametrize("field,value", [
    ("authority_integrity_ok", 1),
    ("policy_integrity_ok", "true"),
    ("secret_exposure", None),
    ("kill_switch_engaged", "false"),
    ("backup_verified", 1),
])
def test_security_booleans_are_exact(field, value):
    with pytest.raises(ValueError):
        view(**{field: value})


def test_operational_view_requires_canonical_trace_and_slo():
    with pytest.raises(ValueError):
        view(trace={"schema": "FORGED"})
    with pytest.raises(ValueError):
        view(slo={"schema": "FORGED"})


def test_output_is_json_deterministic_for_same_evidence():
    first = view()
    second = view()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_no_nested_component_can_grant_execution():
    result = view()
    assert result["execution_allowed"] is False
    assert result["safe_mode"]["external_side_effects_allowed"] is False
    assert result["circuit_breaker"]["executes_action"] is False
    assert result["watchdog"]["executes_action"] is False
    assert result["resource_governor"]["executes_action"] is False
    assert result["bulkhead"]["executes_action"] is False
    assert result["rate_limit"]["executes_action"] is False
    assert result["backpressure"]["executes_action"] is False
