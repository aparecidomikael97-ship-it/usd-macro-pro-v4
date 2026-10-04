"""AION V2.16 red-team: observability, resilience and recovery kernel."""
from __future__ import annotations

import pytest

from atlasquant_aion_resilience_kernel import (
    BLOCKED,
    CLOSED,
    DEGRADED,
    HALF_OPEN,
    HEALTHY,
    OPEN,
    backpressure_decision,
    circuit_breaker_transition,
    evaluate_resilience_posture,
)


def healthy_metrics(**overrides):
    row = {
        "latency_p95_ms": 250.0,
        "error_rate": 0.01,
        "saturation": 0.30,
        "queue_depth": 5,
        "retry_backlog": 1,
    }
    row.update(overrides)
    return row


def healthy_integrity(**overrides):
    row = {
        "journal_verified": True,
        "audit_chain_verified": True,
        "checkpoint_verified": True,
    }
    row.update(overrides)
    return row


def healthy_runtime(**overrides):
    row = {
        "global_kill_switch": False,
        "runtime_health": "CONFIRMED",
        "read_only": False,
    }
    row.update(overrides)
    return row


def healthy_recovery(**overrides):
    row = {
        "backup_verified": True,
        "restore_drill_passed": True,
        "journal_replay_verified": True,
        "crash_recovery_verified": True,
    }
    row.update(overrides)
    return row


def healthy_posture(**kwargs):
    args = {
        "metrics": healthy_metrics(),
        "integrity": healthy_integrity(),
        "runtime": healthy_runtime(),
        "recovery": healthy_recovery(),
        "circuits": {"provider-a": {"state": CLOSED}},
    }
    args.update(kwargs)
    return evaluate_resilience_posture(**args)


def test_healthy_posture_is_confirmed_but_never_execution_authority():
    result = healthy_posture()
    assert result["state"] == HEALTHY
    assert result["blockers"] == []
    assert result["degradations"] == []
    assert result["external_effects_allowed_by_resilience"] is True
    assert result["execution_allowed"] is False
    assert result["approval_implied"] is False
    assert result["authority_implied"] is False
    assert result["worker_armed"] is False
    assert result["external_action_executed"] is False
    assert result["network_called"] is False
    assert result["state_mutated"] is False


@pytest.mark.parametrize(
    "field",
    ["journal_verified", "audit_chain_verified", "checkpoint_verified"],
)
def test_integrity_evidence_missing_is_blocked(field):
    result = healthy_posture(integrity=healthy_integrity(**{field: False}))
    assert result["state"] == BLOCKED
    assert f"INTEGRITY_NOT_VERIFIED:{field}" in result["blockers"]
    assert result["execution_allowed"] is False


@pytest.mark.parametrize(
    "field",
    ["backup_verified", "restore_drill_passed", "journal_replay_verified", "crash_recovery_verified"],
)
def test_recovery_evidence_missing_is_blocked(field):
    result = healthy_posture(recovery=healthy_recovery(**{field: False}))
    assert result["state"] == BLOCKED
    assert f"RECOVERY_NOT_VERIFIED:{field}" in result["blockers"]


def test_kill_switch_active_is_blocked():
    result = healthy_posture(runtime=healthy_runtime(global_kill_switch=True))
    assert result["state"] == BLOCKED
    assert "GLOBAL_KILL_SWITCH_NOT_RELEASED" in result["blockers"]


def test_read_only_runtime_is_not_treated_as_execution_mode():
    result = healthy_posture(runtime=healthy_runtime(read_only=True))
    assert result["state"] == BLOCKED
    assert "RUNTIME_NOT_EXECUTION_MODE" in result["blockers"]


@pytest.mark.parametrize("health", ["UNKNOWN", "DEGRADED", "FAIL", "", None])
def test_runtime_health_must_be_confirmed(health):
    result = healthy_posture(runtime=healthy_runtime(runtime_health=health))
    assert result["state"] == BLOCKED
    assert "RUNTIME_HEALTH_NOT_CONFIRMED" in result["blockers"]


def test_soft_latency_degrades_without_granting_execution():
    result = healthy_posture(metrics=healthy_metrics(latency_p95_ms=1500.0))
    assert result["state"] == DEGRADED
    assert "LATENCY_SOFT_LIMIT" in result["degradations"]
    assert result["execution_allowed"] is False


def test_hard_latency_blocks():
    result = healthy_posture(metrics=healthy_metrics(latency_p95_ms=5000.0))
    assert result["state"] == BLOCKED
    assert "LATENCY_HARD_LIMIT" in result["blockers"]


def test_soft_error_rate_degrades():
    result = healthy_posture(metrics=healthy_metrics(error_rate=0.05))
    assert result["state"] == DEGRADED
    assert "ERROR_RATE_SOFT_LIMIT" in result["degradations"]


def test_hard_error_rate_blocks():
    result = healthy_posture(metrics=healthy_metrics(error_rate=0.20))
    assert result["state"] == BLOCKED
    assert "ERROR_RATE_HARD_LIMIT" in result["blockers"]


def test_backpressure_accept_throttle_reject():
    accept = backpressure_decision(queue_depth=1, retry_backlog=0, saturation=0.1)
    throttle = backpressure_decision(queue_depth=100, retry_backlog=0, saturation=0.1)
    reject = backpressure_decision(queue_depth=500, retry_backlog=0, saturation=0.1)
    assert accept["decision"] == "ACCEPT"
    assert throttle["decision"] == "THROTTLE"
    assert reject["decision"] == "REJECT_NEW_WORK"
    for row in (accept, throttle, reject):
        assert row["queue_mutated"] is False
        assert row["execution_allowed"] is False


def test_soft_backpressure_degrades_posture():
    result = healthy_posture(metrics=healthy_metrics(queue_depth=100))
    assert result["state"] == DEGRADED
    assert "BACKPRESSURE_SOFT_LIMIT" in result["degradations"]


def test_hard_backpressure_blocks_posture():
    result = healthy_posture(metrics=healthy_metrics(retry_backlog=200))
    assert result["state"] == BLOCKED
    assert "BACKPRESSURE_HARD_LIMIT" in result["blockers"]


def test_closed_circuit_opens_at_failure_threshold():
    result = circuit_breaker_transition(
        previous_state=CLOSED,
        consecutive_failures=5,
        rolling_error_rate=0.01,
    )
    assert result["state"] == OPEN
    assert result["reason"] == "FAILURE_THRESHOLD_EXCEEDED"
    assert result["dependency_call_performed"] is False
    assert result["execution_allowed"] is False


def test_closed_circuit_opens_at_error_rate_threshold():
    result = circuit_breaker_transition(
        previous_state=CLOSED,
        consecutive_failures=0,
        rolling_error_rate=0.30,
    )
    assert result["state"] == OPEN


def test_open_circuit_stays_open_until_exact_cooldown_true():
    for flag in [False, None, 1, "true"]:
        result = circuit_breaker_transition(
            previous_state=OPEN,
            consecutive_failures=5,
            rolling_error_rate=0.5,
            cooldown_elapsed=flag,
        )
        assert result["state"] == OPEN

    result = circuit_breaker_transition(
        previous_state=OPEN,
        consecutive_failures=5,
        rolling_error_rate=0.5,
        cooldown_elapsed=True,
    )
    assert result["state"] == HALF_OPEN


def test_half_open_probe_success_closes_and_failure_reopens():
    ok = circuit_breaker_transition(
        previous_state=HALF_OPEN,
        consecutive_failures=0,
        rolling_error_rate=0.0,
        probe_success=True,
    )
    bad = circuit_breaker_transition(
        previous_state=HALF_OPEN,
        consecutive_failures=0,
        rolling_error_rate=0.0,
        probe_success=False,
    )
    waiting = circuit_breaker_transition(
        previous_state=HALF_OPEN,
        consecutive_failures=0,
        rolling_error_rate=0.0,
        probe_success=None,
    )
    assert ok["state"] == CLOSED
    assert bad["state"] == OPEN
    assert waiting["state"] == HALF_OPEN


def test_open_dependency_circuit_blocks_posture():
    result = healthy_posture(circuits={"provider-a": {"state": OPEN}})
    assert result["state"] == BLOCKED
    assert "CIRCUIT_OPEN" in result["blockers"]
    assert result["open_circuits"] == ["provider-a"]


def test_half_open_dependency_degrades_posture():
    result = healthy_posture(circuits={"provider-a": {"state": HALF_OPEN}})
    assert result["state"] == DEGRADED
    assert "CIRCUIT_HALF_OPEN" in result["degradations"]


def test_invalid_circuit_evidence_blocks():
    result = healthy_posture(circuits={"provider-a": {"state": "FORGED"}})
    assert result["state"] == BLOCKED
    assert "CIRCUIT_STATE_INVALID:provider-a" in result["blockers"]


@pytest.mark.parametrize(
    "metrics",
    [
        healthy_metrics(error_rate=float("nan")),
        healthy_metrics(error_rate=float("inf")),
        healthy_metrics(saturation=-0.1),
        healthy_metrics(queue_depth=-1),
        healthy_metrics(queue_depth=True),
    ],
)
def test_noncanonical_metrics_are_rejected(metrics):
    with pytest.raises(ValueError):
        healthy_posture(metrics=metrics)


def test_unknown_policy_fields_are_rejected():
    with pytest.raises(ValueError):
        healthy_posture(policy={"allow_execution": True})


def test_policy_cannot_invert_soft_hard_thresholds():
    with pytest.raises(ValueError):
        healthy_posture(policy={"queue_depth_soft": 1000, "queue_depth_hard": 100})


def test_payload_claims_cannot_forge_authority_or_execution():
    result = evaluate_resilience_posture(
        metrics={**healthy_metrics(), "execution_allowed": True, "authority_verified": True},
        integrity={**healthy_integrity(), "approval": True},
        runtime={**healthy_runtime(), "worker_armed": True, "execution_allowed": True},
        recovery={**healthy_recovery(), "execution_allowed": True},
        circuits={"provider-a": {"state": CLOSED, "execution_allowed": True}},
    )
    assert result["state"] == HEALTHY
    assert result["execution_allowed"] is False
    assert result["approval_implied"] is False
    assert result["authority_implied"] is False
    assert result["worker_armed"] is False


def test_multiple_blockers_are_deterministic_and_sorted():
    result = evaluate_resilience_posture(
        metrics=healthy_metrics(latency_p95_ms=9000, retry_backlog=999),
        integrity=healthy_integrity(journal_verified=False),
        runtime=healthy_runtime(global_kill_switch=True, runtime_health="FAIL", read_only=True),
        recovery=healthy_recovery(backup_verified=False),
        circuits={"z": {"state": OPEN}, "a": {"state": "INVALID"}},
    )
    assert result["state"] == BLOCKED
    assert result["blockers"] == sorted(result["blockers"])
    assert result["execution_allowed"] is False
