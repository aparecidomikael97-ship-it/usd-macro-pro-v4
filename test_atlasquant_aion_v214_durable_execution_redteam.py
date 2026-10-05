"""AION V2.14 adversarial tests for durable execution safety."""
from __future__ import annotations

import threading

import pytest

from atlasquant_aion_durable_execution_kernel import (
    DurableExecutionError,
    DurableExecutionStore,
    canonical_execution_id,
    deterministic_backoff_seconds,
)


NOW = "2026-10-04T18:00:00Z"
LATER = "2026-10-04T18:01:00Z"
DEADLINE = "2026-10-04T20:00:00Z"


def prepare(store, **changes):
    values = dict(
        task_id="DUR-ABC",
        step_id="S001",
        idempotency_key="idem-001",
        effect_key="effect-001",
        payload_digest="a" * 64,
        mode="LOCAL_SAFE",
        now_ts=NOW,
        deadline_at=DEADLINE,
        max_attempts=4,
        poison_threshold=3,
    )
    values.update(changes)
    return store.prepare(**values)


def lease(store, execution_id, **changes):
    values = dict(owner="worker-a", now_ts=NOW, lease_seconds=120, lease_token="lease-token-a")
    values.update(changes)
    return store.acquire_lease(execution_id, **values)


def test_canonical_execution_id_is_stable_and_bound():
    a = canonical_execution_id("task", "step", "idem", "digest")
    b = canonical_execution_id("task", "step", "idem", "digest")
    c = canonical_execution_id("task", "step", "idem2", "digest")
    assert a == b
    assert a.startswith("EXE-")
    assert a != c


@pytest.mark.parametrize("attempt,expected", [(1, 5), (2, 10), (3, 20), (4, 40), (8, 300), (20, 300)])
def test_backoff_is_deterministic_and_capped(attempt, expected):
    assert deterministic_backoff_seconds(attempt) == expected


def test_prepare_is_idempotent_replay(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    first = prepare(store)
    second = prepare(store)
    assert first.replay is False
    assert second.replay is True
    assert first.record["execution_id"] == second.record["execution_id"]
    assert store.count() == 1


def test_same_idempotency_different_payload_is_conflict(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    prepare(store)
    with pytest.raises(DurableExecutionError) as exc:
        prepare(store, payload_digest="b" * 64)
    assert exc.value.result["error_code"] == "IDEMPOTENCY_CONFLICT"
    assert store.count() == 1


def test_effect_key_cannot_be_registered_twice(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    prepare(store)
    with pytest.raises(DurableExecutionError) as exc:
        prepare(
            store,
            idempotency_key="idem-002",
            step_id="S002",
            payload_digest="b" * 64,
        )
    assert exc.value.result["error_code"] == "EFFECT_ALREADY_REGISTERED"


def test_local_safe_lease_complete_and_replay(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    execution_id = prepare(store).record["execution_id"]
    row = lease(store, execution_id)
    assert row["state"] == "LEASED"
    assert row["attempt"] == 1
    done = store.complete(
        execution_id,
        lease_token="lease-token-a",
        result_digest="result-1",
        now_ts=LATER,
    )
    assert done["state"] == "COMPLETED"
    assert done["executes_action"] is False
    repeat = store.complete(
        execution_id,
        lease_token="ignored-after-complete",
        result_digest="result-1",
        now_ts=LATER,
    )
    assert repeat == done
    with pytest.raises(DurableExecutionError) as conflict:
        store.complete(
            execution_id,
            lease_token="ignored",
            result_digest="different",
            now_ts=LATER,
        )
    assert conflict.value.result["error_code"] == "RESULT_REPLAY_CONFLICT"


def test_only_one_concurrent_lease_wins(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    execution_id = prepare(store).record["execution_id"]
    successes = []
    errors = []

    def worker(index):
        try:
            row = store.acquire_lease(
                execution_id,
                owner=f"worker-{index}",
                now_ts=NOW,
                lease_seconds=120,
                lease_token=f"token-{index}",
            )
            successes.append(row["lease_token"])
        except DurableExecutionError as exc:
            errors.append(exc.result["error_code"])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(successes) == 1
    assert errors.count("LEASE_CONFLICT") == 9


def test_heartbeat_requires_current_token(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    execution_id = prepare(store).record["execution_id"]
    lease(store, execution_id)
    with pytest.raises(DurableExecutionError) as exc:
        store.heartbeat(
            execution_id,
            lease_token="wrong",
            now_ts="2026-10-04T18:00:30Z",
        )
    assert exc.value.result["error_code"] == "LEASE_TOKEN_MISMATCH"
    row = store.heartbeat(
        execution_id,
        lease_token="lease-token-a",
        now_ts="2026-10-04T18:00:30Z",
        lease_seconds=120,
    )
    assert row["state"] == "LEASED"
    assert row["lease_expires_at"] == "2026-10-04T18:02:30Z"


def test_local_failure_schedules_exponential_retry(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    execution_id = prepare(store).record["execution_id"]
    lease(store, execution_id)
    row = store.fail_before_dispatch(
        execution_id,
        lease_token="lease-token-a",
        error_fingerprint="network-local-read",
        now_ts=NOW,
        retryable=True,
    )
    assert row["state"] == "RETRY_WAIT"
    assert row["next_attempt_at"] == "2026-10-04T18:00:05Z"
    assert row["automatic_retry_allowed"] is True

    with pytest.raises(DurableExecutionError) as early:
        store.acquire_lease(
            execution_id,
            owner="worker-b",
            now_ts="2026-10-04T18:00:04Z",
            lease_token="b",
        )
    assert early.value.result["error_code"] == "RETRY_NOT_DUE"

    second = store.acquire_lease(
        execution_id,
        owner="worker-b",
        now_ts="2026-10-04T18:00:05Z",
        lease_token="b",
    )
    assert second["attempt"] == 2


def test_non_retryable_failure_goes_dlq(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    execution_id = prepare(store).record["execution_id"]
    lease(store, execution_id)
    row = store.fail_before_dispatch(
        execution_id,
        lease_token="lease-token-a",
        error_fingerprint="invalid-contract",
        now_ts=NOW,
        retryable=False,
    )
    assert row["state"] == "DLQ"
    assert row["automatic_retry_allowed"] is False
    assert store.list_dlq()[0]["execution_id"] == execution_id


def test_poison_task_repeated_error_goes_dlq(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    execution_id = prepare(store, max_attempts=5, poison_threshold=3).record["execution_id"]
    now_values = [
        ("2026-10-04T18:00:00Z", "2026-10-04T18:00:05Z"),
        ("2026-10-04T18:00:05Z", "2026-10-04T18:00:15Z"),
        ("2026-10-04T18:00:15Z", None),
    ]
    for index, (now_ts, expected_next) in enumerate(now_values, 1):
        row = store.acquire_lease(
            execution_id,
            owner=f"w{index}",
            now_ts=now_ts,
            lease_token=f"t{index}",
        )
        row = store.fail_before_dispatch(
            execution_id,
            lease_token=f"t{index}",
            error_fingerprint="same-error",
            now_ts=now_ts,
            retryable=True,
        )
        if expected_next is not None:
            assert row["state"] == "RETRY_WAIT"
            assert row["next_attempt_at"] == expected_next
        else:
            assert row["state"] == "DLQ"
            assert row["same_error_count"] == 3


def test_different_error_resets_poison_counter(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    execution_id = prepare(store, poison_threshold=3).record["execution_id"]
    lease(store, execution_id)
    first = store.fail_before_dispatch(
        execution_id, lease_token="lease-token-a",
        error_fingerprint="e1", now_ts=NOW, retryable=True,
    )
    assert first["same_error_count"] == 1
    store.acquire_lease(
        execution_id, owner="w2",
        now_ts=first["next_attempt_at"], lease_token="t2",
    )
    second = store.fail_before_dispatch(
        execution_id, lease_token="t2",
        error_fingerprint="e2", now_ts=first["next_attempt_at"], retryable=True,
    )
    assert second["same_error_count"] == 1
    assert second["state"] == "RETRY_WAIT"


def test_external_effect_requires_dispatch_record_before_complete(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    execution_id = prepare(
        store,
        mode="EXTERNAL_EFFECT",
        effect_key="crm-write:customer-1",
    ).record["execution_id"]
    lease(store, execution_id)
    with pytest.raises(DurableExecutionError) as blocked:
        store.complete(
            execution_id,
            lease_token="lease-token-a",
            result_digest="receipt",
            now_ts=LATER,
        )
    assert blocked.value.result["error_code"] == "COMPLETE_STATE_BLOCKED"
    dispatch = store.record_dispatch_started(
        execution_id,
        lease_token="lease-token-a",
        now_ts=NOW,
    )
    assert dispatch["state"] == "DISPATCH_RECORDED"
    done = store.complete(
        execution_id,
        lease_token="lease-token-a",
        result_digest="provider-receipt-digest",
        now_ts=LATER,
    )
    assert done["state"] == "COMPLETED"


def test_crash_after_external_dispatch_becomes_outcome_unknown(tmp_path):
    path = tmp_path / "exec.sqlite3"
    store = DurableExecutionStore(path)
    execution_id = prepare(
        store,
        mode="EXTERNAL_EFFECT",
        effect_key="email:message-1",
    ).record["execution_id"]
    store.acquire_lease(
        execution_id,
        owner="worker-a",
        now_ts=NOW,
        lease_seconds=1,
        lease_token="dispatch-token",
    )
    store.record_dispatch_started(
        execution_id,
        lease_token="dispatch-token",
        now_ts=NOW,
    )

    reopened = DurableExecutionStore(path)
    recovered = reopened.recover_expired_leases(
        now_ts="2026-10-04T18:00:02Z"
    )
    assert len(recovered) == 1
    row = recovered[0]
    assert row["state"] == "OUTCOME_UNKNOWN"
    assert row["automatic_retry_allowed"] is False
    with pytest.raises(DurableExecutionError) as blocked:
        reopened.acquire_lease(
            execution_id,
            owner="worker-b",
            now_ts="2026-10-04T18:00:03Z",
            lease_token="retry-forbidden",
        )
    assert blocked.value.result["error_code"] == "LEASE_STATE_BLOCKED"


def test_external_explicit_unknown_never_auto_retries(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    execution_id = prepare(
        store, mode="EXTERNAL_EFFECT", effect_key="payment:invoice-1"
    ).record["execution_id"]
    lease(store, execution_id)
    store.record_dispatch_started(
        execution_id, lease_token="lease-token-a", now_ts=NOW
    )
    row = store.mark_outcome_unknown(
        execution_id,
        lease_token="lease-token-a",
        error_fingerprint="provider-timeout-after-send",
        now_ts=LATER,
    )
    assert row["state"] == "OUTCOME_UNKNOWN"
    assert row["automatic_retry_allowed"] is False


@pytest.mark.parametrize("flag", [False, None, 1, "true", "yes"])
def test_unknown_reconciliation_requires_exact_boolean_true(tmp_path, flag):
    store = DurableExecutionStore(tmp_path / f"exec-{str(flag)}.sqlite3")
    execution_id = prepare(
        store, mode="EXTERNAL_EFFECT", effect_key=f"external:{str(flag)}"
    ).record["execution_id"]
    lease(store, execution_id)
    store.record_dispatch_started(
        execution_id, lease_token="lease-token-a", now_ts=NOW
    )
    store.mark_outcome_unknown(
        execution_id,
        lease_token="lease-token-a",
        error_fingerprint="unknown",
        now_ts=LATER,
    )
    with pytest.raises(DurableExecutionError) as exc:
        store.reconcile_unknown(
            execution_id,
            outcome="CONFIRMED_EFFECT",
            evidence_digest="evidence",
            reconciliation_authorized=flag,
            now_ts="2026-10-04T18:02:00Z",
        )
    assert exc.value.result["error_code"] == "RECONCILIATION_AUTHORIZATION_REQUIRED"


def test_reconcile_confirmed_effect_closes_without_retry(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    execution_id = prepare(
        store, mode="EXTERNAL_EFFECT", effect_key="external:confirmed"
    ).record["execution_id"]
    lease(store, execution_id)
    store.record_dispatch_started(
        execution_id, lease_token="lease-token-a", now_ts=NOW
    )
    store.mark_outcome_unknown(
        execution_id, lease_token="lease-token-a",
        error_fingerprint="timeout", now_ts=LATER,
    )
    row = store.reconcile_unknown(
        execution_id,
        outcome="CONFIRMED_EFFECT",
        evidence_digest="provider-receipt-verified",
        reconciliation_authorized=True,
        now_ts="2026-10-04T18:02:00Z",
    )
    assert row["state"] == "COMPLETED"
    assert row["result_digest"] == "provider-receipt-verified"
    assert row["automatic_retry_allowed"] is False


def test_reconcile_confirmed_no_effect_can_retry(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    execution_id = prepare(
        store, mode="EXTERNAL_EFFECT", effect_key="external:no-effect"
    ).record["execution_id"]
    lease(store, execution_id)
    store.record_dispatch_started(
        execution_id, lease_token="lease-token-a", now_ts=NOW
    )
    store.mark_outcome_unknown(
        execution_id, lease_token="lease-token-a",
        error_fingerprint="timeout", now_ts=LATER,
    )
    row = store.reconcile_unknown(
        execution_id,
        outcome="CONFIRMED_NO_EFFECT",
        evidence_digest="provider-query-no-effect",
        reconciliation_authorized=True,
        now_ts="2026-10-04T18:02:00Z",
    )
    assert row["state"] == "RETRY_WAIT"
    assert row["automatic_retry_allowed"] is True
    assert row["reconciliation_evidence_digest"] == "provider-query-no-effect"


def test_expired_lease_before_dispatch_is_recoverable(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    execution_id = prepare(store).record["execution_id"]
    store.acquire_lease(
        execution_id, owner="w", now_ts=NOW,
        lease_seconds=1, lease_token="t",
    )
    rows = store.recover_expired_leases(now_ts="2026-10-04T18:00:02Z")
    assert rows[0]["state"] == "RETRY_WAIT"
    assert rows[0]["automatic_retry_allowed"] is True


def test_cancel_before_dispatch_is_safe(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    execution_id = prepare(store).record["execution_id"]
    row = store.cancel(execution_id, now_ts=LATER)
    assert row["state"] == "CANCELED"
    assert row["executes_action"] is False


def test_cancel_after_dispatch_is_blocked(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    execution_id = prepare(
        store, mode="EXTERNAL_EFFECT", effect_key="external:cancel"
    ).record["execution_id"]
    lease(store, execution_id)
    store.record_dispatch_started(
        execution_id, lease_token="lease-token-a", now_ts=NOW
    )
    with pytest.raises(DurableExecutionError) as exc:
        store.cancel(execution_id, now_ts=LATER)
    assert exc.value.result["error_code"] == "CANCEL_OUTCOME_UNCERTAIN_OR_TERMINAL"


def test_deadline_blocks_new_lease_and_deadletters(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    execution_id = prepare(
        store, deadline_at="2026-10-04T18:00:01Z"
    ).record["execution_id"]
    with pytest.raises(DurableExecutionError) as exc:
        store.acquire_lease(
            execution_id,
            owner="w",
            now_ts="2026-10-04T18:00:01Z",
            lease_token="t",
        )
    assert exc.value.result["error_code"] == "DEADLINE_EXCEEDED"
    assert store.get(execution_id)["state"] == "DLQ"


def test_persistence_survives_reopen(tmp_path):
    path = tmp_path / "exec.sqlite3"
    store = DurableExecutionStore(path)
    prepared = prepare(store)
    execution_id = prepared.record["execution_id"]
    lease(store, execution_id)
    reopened = DurableExecutionStore(path)
    row = reopened.get(execution_id)
    assert row["state"] == "LEASED"
    assert row["attempt"] == 1
    assert reopened.count() == 1


def test_external_pre_dispatch_failure_may_retry_safely(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    execution_id = prepare(
        store, mode="EXTERNAL_EFFECT", effect_key="external:pre-dispatch"
    ).record["execution_id"]
    lease(store, execution_id)
    row = store.fail_before_dispatch(
        execution_id,
        lease_token="lease-token-a",
        error_fingerprint="connection-not-opened",
        now_ts=NOW,
        retryable=True,
    )
    assert row["state"] == "RETRY_WAIT"
    assert row["dispatch_recorded_at"] == ""
    assert row["automatic_retry_allowed"] is True


def test_no_method_claims_to_execute_external_action(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    row = prepare(store).record
    assert row["executes_action"] is False
    assert row["external_effect_performed"] is False
    leased = lease(store, row["execution_id"])
    assert leased["executes_action"] is False
    assert leased["external_effect_performed"] is False


def test_local_safe_cannot_enter_external_dispatch_state(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    execution_id = prepare(store).record["execution_id"]
    lease(store, execution_id)
    with pytest.raises(DurableExecutionError) as exc:
        store.record_dispatch_started(
            execution_id,
            lease_token="lease-token-a",
            now_ts=NOW,
        )
    assert exc.value.result["error_code"] == "DISPATCH_MODE_BLOCKED"


def test_cancel_during_active_lease_is_blocked(tmp_path):
    store = DurableExecutionStore(tmp_path / "exec.sqlite3")
    execution_id = prepare(store).record["execution_id"]
    lease(store, execution_id)
    with pytest.raises(DurableExecutionError) as exc:
        store.cancel(execution_id, now_ts=LATER)
    assert exc.value.result["error_code"] == "CANCEL_ACTIVE_LEASE_BLOCKED"
    assert store.get(execution_id)["state"] == "LEASED"
