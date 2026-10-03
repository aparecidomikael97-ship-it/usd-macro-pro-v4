from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading

import pytest

from aion_chat.models import Scope
import atlasquant_aion_unified_journal_store as store_module
from atlasquant_aion_unified_journal import (
    append_request_event,
    new_request_journal,
    verify_request_journal,
)
from atlasquant_aion_unified_journal_store import (
    ACKNOWLEDGED,
    DURABLE,
    QUARANTINED,
    STAGED,
    JournalStoreConflict,
    JournalStoreIntegrityError,
    JournalStoreLockTimeout,
    SimulatedCrash,
    UnifiedJournalStore,
)


OBSERVED = "2026-10-03T19:30:00+00:00"


def scope(name="a"):
    return Scope(f"owner-{name}", f"tenant-{name}", f"workspace-{name}")


def journal(s=None, *, states=("ACCEPTED", "ROUTED", "READY")):
    s = s or scope()
    value = new_request_journal(s, "REQ-1", "conv-1")
    value = append_request_event(
        value,
        event_type="REQUEST_ACCEPTED",
        authorization_class="READ_ONLY",
        state=states[0],
        observed_at=OBSERVED,
        metadata={"message_digest": "sha256:abc"},
    )
    if len(states) > 1:
        value = append_request_event(
            value,
            event_type="ROLE_ROUTED",
            selected_role="orchestrator",
            authorization_class="READ_ONLY",
            truth_state="CONFIRMED",
            state=states[1],
            observed_at=OBSERVED,
        )
    if len(states) > 2:
        value = append_request_event(
            value,
            event_type="PREFLIGHT_COMPLETED",
            selected_role="orchestrator",
            authorization_class="READ_ONLY",
            truth_state="CONFIRMED",
            state=states[2],
            observed_at=OBSERVED,
        )
    assert verify_request_journal(value, scope=s, request_id="REQ-1")["valid"] is True
    return value


def event_file(store, s, sequence=1):
    request_dir = store._request_dir(s, "REQ-1", create=False)
    files = sorted((request_dir / "events").glob(f"{sequence:08d}_*.json"))
    assert len(files) == 1
    return files[0]


def test_persist_recover_and_acknowledge_is_state_only(tmp_path):
    s = scope()
    value = journal(s)
    durable = UnifiedJournalStore(tmp_path / "spool")

    result = durable.persist_journal(
        value,
        scope=s,
        request_id="REQ-1",
        idempotency_key="run-1",
    )
    assert result["persistence_state"] == DURABLE
    recovered = durable.recover(scope=s, request_id="REQ-1")
    assert recovered["status"] == "RECOVERED"
    assert recovered["persistence_state"] == DURABLE
    assert recovered["event_count"] == 3
    assert recovered["ack_pending"] is True
    assert recovered["restores_state_only"] is True
    assert recovered["automatic_resume_executes"] is False
    assert recovered["checkpoint_written"] is False
    assert recovered["memory_promoted"] is False
    assert recovered["external_action_executed"] is False
    assert recovered["journal_integrity"]["valid"] is True

    latest = value["events"][-1]
    ack = durable.acknowledge(
        scope=s,
        request_id="REQ-1",
        sequence=3,
        event_digest=latest["event_digest"],
    )
    assert ack["persistence_state"] == ACKNOWLEDGED
    recovered = durable.recover(scope=s, request_id="REQ-1")
    assert recovered["persistence_state"] == ACKNOWLEDGED
    assert recovered["ack_pending"] is False


def test_persistent_idempotency_survives_restart_and_conflicts_fail_closed(tmp_path):
    s = scope()
    value = journal(s, states=("ACCEPTED",))
    root = tmp_path / "spool"
    first = UnifiedJournalStore(root)
    one = first.persist_event(
        value,
        scope=s,
        request_id="REQ-1",
        sequence=1,
        idempotency_key="idem-1",
    )
    assert one["status"] == "PERSISTED"

    restarted = UnifiedJournalStore(root)
    same = restarted.persist_event(
        value,
        scope=s,
        request_id="REQ-1",
        sequence=1,
        idempotency_key="idem-1",
    )
    assert same["status"] == "IDEMPOTENT"

    changed = journal(s, states=("DIFFERENT",))
    with pytest.raises(JournalStoreConflict, match="idempotency"):
        restarted.persist_event(
            changed,
            scope=s,
            request_id="REQ-1",
            sequence=1,
            idempotency_key="idem-1",
        )


@pytest.mark.parametrize(
    "stage,expected_state,expected_status",
    [
        ("BEFORE_DURABLE_COMMIT", STAGED, "RECOVERED"),
        ("AFTER_TEMP_FSYNC", STAGED, "RECOVERED"),
        ("AFTER_EVENT_COMMIT", DURABLE, "RECOVERED_WITH_STALE_HEAD"),
        ("AFTER_HEAD_COMMIT", DURABLE, "RECOVERED"),
    ],
)
def test_crash_windows_never_fake_acknowledgement(
    tmp_path, stage, expected_state, expected_status
):
    s = scope()
    value = journal(s, states=("ACCEPTED",))

    def crash(point, context):
        if point == stage:
            raise SimulatedCrash(point)

    durable = UnifiedJournalStore(tmp_path / "spool", fault_injector=crash)
    with pytest.raises(SimulatedCrash):
        durable.persist_event(
            value,
            scope=s,
            request_id="REQ-1",
            sequence=1,
            idempotency_key="crash-1",
            acknowledge=True,
        )

    recovered = UnifiedJournalStore(tmp_path / "spool").recover(
        scope=s, request_id="REQ-1"
    )
    assert recovered["persistence_state"] == expected_state
    assert recovered["status"] == expected_status
    assert recovered["persistence_state"] != ACKNOWLEDGED
    if stage == "AFTER_TEMP_FSYNC":
        assert "ORPHAN_TEMP_QUARANTINED" in recovered["reasons"]
        assert recovered["quarantined_files"]


def test_crash_after_ack_is_idempotently_recoverable(tmp_path):
    s = scope()
    value = journal(s, states=("ACCEPTED",))

    def crash(point, context):
        if point == "AFTER_ACK_COMMIT":
            raise SimulatedCrash(point)

    durable = UnifiedJournalStore(tmp_path / "spool", fault_injector=crash)
    with pytest.raises(SimulatedCrash):
        durable.persist_event(
            value,
            scope=s,
            request_id="REQ-1",
            sequence=1,
            idempotency_key="ack-crash",
            acknowledge=True,
        )

    recovered = UnifiedJournalStore(tmp_path / "spool").recover(
        scope=s, request_id="REQ-1"
    )
    assert recovered["status"] == "RECOVERED"
    assert recovered["persistence_state"] == ACKNOWLEDGED
    assert recovered["ack_pending"] is False


@pytest.mark.parametrize("mutation", ["truncate", "payload", "version", "sequence", "prev"])
def test_corrupt_durable_record_is_quarantined_fail_closed(tmp_path, mutation):
    s = scope()
    value = journal(s, states=("ACCEPTED",))
    durable = UnifiedJournalStore(tmp_path / "spool")
    durable.persist_event(
        value,
        scope=s,
        request_id="REQ-1",
        sequence=1,
        idempotency_key="corrupt-1",
    )
    path = event_file(durable, s)

    if mutation == "truncate":
        path.write_bytes(b'{"schema":')
    else:
        row = json.loads(path.read_text(encoding="utf-8"))
        if mutation == "payload":
            row["event"]["state"] = "TAMPERED"
        elif mutation == "version":
            row["persistence_version"] = 999
        elif mutation == "sequence":
            row["sequence"] = 9
        elif mutation == "prev":
            row["prev_digest"] = "sha256:" + ("0" * 64)
        path.write_text(json.dumps(row), encoding="utf-8")

    recovered = durable.recover(scope=s, request_id="REQ-1")
    assert recovered["status"] == "QUARANTINED"
    assert recovered["persistence_state"] == QUARANTINED
    assert recovered["safe_to_resume"] is False
    assert recovered["reasons"]


def test_intermediate_corruption_blocks_later_chain(tmp_path):
    s = scope()
    value = journal(s)
    durable = UnifiedJournalStore(tmp_path / "spool")
    durable.persist_journal(
        value,
        scope=s,
        request_id="REQ-1",
        idempotency_key="chain",
    )

    path = event_file(durable, s, 2)
    row = json.loads(path.read_text(encoding="utf-8"))
    row["event"]["state"] = "TAMPERED"
    path.write_text(json.dumps(row), encoding="utf-8")

    recovered = durable.recover(scope=s, request_id="REQ-1")
    assert recovered["status"] == "QUARANTINED"
    assert recovered["safe_to_resume"] is False
    assert recovered["event_count"] == 1


def test_cross_scope_replay_and_write_fail_closed(tmp_path):
    a = scope("a")
    b = scope("b")
    value = journal(a, states=("ACCEPTED",))
    durable = UnifiedJournalStore(tmp_path / "spool")
    durable.persist_event(
        value,
        scope=a,
        request_id="REQ-1",
        sequence=1,
        idempotency_key="scope-a",
    )

    with pytest.raises(LookupError):
        durable.recover(scope=b, request_id="REQ-1")
    with pytest.raises(JournalStoreIntegrityError, match="logical journal"):
        durable.persist_event(
            value,
            scope=b,
            request_id="REQ-1",
            sequence=1,
            idempotency_key="scope-b",
        )


@pytest.mark.parametrize(
    "unsafe",
    [
        "../REQ",
        r"..\REQ",
        "/tmp/REQ",
        r"C:\REQ",
        r"\\server\share",
        "REQ\x00evil",
    ],
)
def test_path_syntax_is_rejected_before_path_derivation(tmp_path, unsafe):
    durable = UnifiedJournalStore(tmp_path / "spool")
    with pytest.raises(ValueError, match="request_id"):
        durable.recover(scope=scope(), request_id=unsafe)


def test_symlink_escape_is_rejected(tmp_path):
    if not hasattr(Path, "symlink_to"):
        pytest.skip("symlink unsupported")
    s = scope()
    value = journal(s, states=("ACCEPTED",))
    durable = UnifiedJournalStore(tmp_path / "spool")
    durable.persist_event(
        value,
        scope=s,
        request_id="REQ-1",
        sequence=1,
        idempotency_key="symlink",
    )
    request_dir = durable._request_dir(s, "REQ-1", create=False)
    events = request_dir / "events"
    backup = request_dir / "events-real"
    events.rename(backup)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        events.symlink_to(outside, target_is_directory=True)
    except OSError:
        backup.rename(events)
        pytest.skip("symlink creation unavailable")

    with pytest.raises(JournalStoreIntegrityError, match="symlink"):
        durable.recover(scope=s, request_id="REQ-1")


def test_event_size_limit_fails_before_durable_visibility(tmp_path):
    s = scope()
    value = journal(s, states=("ACCEPTED",))
    durable = UnifiedJournalStore(tmp_path / "spool", max_event_bytes=256)
    with pytest.raises(ValueError, match="limit"):
        durable.persist_event(
            value,
            scope=s,
            request_id="REQ-1",
            sequence=1,
            idempotency_key="small-limit",
        )
    recovered = durable.recover(scope=s, request_id="REQ-1")
    assert recovered["event_count"] == 0
    assert recovered["persistence_state"] == STAGED


def test_head_pointing_to_missing_event_is_fail_closed(tmp_path):
    s = scope()
    value = journal(s, states=("ACCEPTED",))
    durable = UnifiedJournalStore(tmp_path / "spool")
    durable.persist_event(
        value,
        scope=s,
        request_id="REQ-1",
        sequence=1,
        idempotency_key="head",
    )
    request_dir = durable._request_dir(s, "REQ-1", create=False)
    head_path = request_dir / "head.json"
    head = json.loads(head_path.read_text(encoding="utf-8"))
    head["sequence"] = 2
    head["event_digest"] = "sha256:" + ("f" * 64)
    body = dict(head)
    body.pop("record_digest", None)
    head["record_digest"] = store_module._record_digest(body)
    head_path.write_text(json.dumps(head), encoding="utf-8")

    recovered = durable.recover(scope=s, request_id="REQ-1")
    assert recovered["status"] == "QUARANTINED"
    assert recovered["head_status"] == "INVALID"
    assert recovered["safe_to_resume"] is False


def test_same_request_same_idempotency_key_concurrent_writes_are_deduplicated(tmp_path):
    s = scope()
    value = journal(s, states=("ACCEPTED",))
    root = tmp_path / "spool"

    def write():
        durable = UnifiedJournalStore(root, lock_timeout=2.0)
        return durable.persist_event(
            value,
            scope=s,
            request_id="REQ-1",
            sequence=1,
            idempotency_key="concurrent",
        )["status"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(write), pool.submit(write)]
        statuses = sorted(f.result() for f in futures)

    assert statuses == ["IDEMPOTENT", "PERSISTED"]
    recovered = UnifiedJournalStore(root).recover(scope=s, request_id="REQ-1")
    assert recovered["event_count"] == 1
    assert recovered["journal_integrity"]["valid"] is True


def test_per_request_lock_times_out_without_deadlock(tmp_path):
    s = scope()
    value = journal(s, states=("ACCEPTED",))
    durable = UnifiedJournalStore(tmp_path / "spool", lock_timeout=0.05)
    request_dir = durable._request_dir(s, "REQ-1", create=True)
    paths = durable._ensure_layout(request_dir)
    entered = threading.Event()
    release = threading.Event()

    def holder():
        with store_module._FileLock(paths["lock"], 1.0):
            entered.set()
            release.wait(2.0)

    thread = threading.Thread(target=holder)
    thread.start()
    assert entered.wait(1.0)
    try:
        with pytest.raises(JournalStoreLockTimeout):
            durable.persist_event(
                value,
                scope=s,
                request_id="REQ-1",
                sequence=1,
                idempotency_key="locked",
            )
    finally:
        release.set()
        thread.join(timeout=2.0)
    assert not thread.is_alive()


def test_requests_and_tenants_use_distinct_lock_and_storage_scopes(tmp_path):
    root = tmp_path / "spool"
    a = scope("a")
    b = scope("b")
    ja = journal(a, states=("ACCEPTED",))
    jb = new_request_journal(b, "REQ-B", "conv-b")
    jb = append_request_event(
        jb,
        event_type="REQUEST_ACCEPTED",
        authorization_class="READ_ONLY",
        state="ACCEPTED",
        observed_at=OBSERVED,
    )

    def write_a():
        return UnifiedJournalStore(root).persist_event(
            ja,
            scope=a,
            request_id="REQ-1",
            sequence=1,
            idempotency_key="tenant-a",
        )

    def write_b():
        return UnifiedJournalStore(root).persist_event(
            jb,
            scope=b,
            request_id="REQ-B",
            sequence=1,
            idempotency_key="tenant-b",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        ra, rb = pool.submit(write_a), pool.submit(write_b)
        assert ra.result()["status"] == "PERSISTED"
        assert rb.result()["status"] == "PERSISTED"

    assert UnifiedJournalStore(root).recover(scope=a, request_id="REQ-1")["event_count"] == 1
    assert UnifiedJournalStore(root).recover(scope=b, request_id="REQ-B")["event_count"] == 1
