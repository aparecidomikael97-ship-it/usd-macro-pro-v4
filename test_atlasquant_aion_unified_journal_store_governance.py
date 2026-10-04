from __future__ import annotations

import json
from pathlib import Path

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
    REASON_CODES,
    JournalStoreConflict,
    JournalStoreIntegrityError,
    JournalStoreLockTimeout,
    JournalStoreRejected,
    SimulatedCrash,
    UnifiedJournalStore,
)

OBSERVED = "2026-10-03T19:30:00+00:00"


def scope(name="a"):
    return Scope(f"owner-{name}", f"tenant-{name}", f"workspace-{name}")


def journal(s=None, *, states=("ACCEPTED",), request_id="REQ-1", conv="conv-1", metadata=None):
    s = s or scope()
    value = new_request_journal(s, request_id, conv)
    for i, state in enumerate(states, start=1):
        value = append_request_event(
            value,
            event_type="REQUEST_ACCEPTED" if i == 1 else "ROLE_ROUTED",
            authorization_class="READ_ONLY",
            state=state,
            observed_at=OBSERVED,
            metadata=metadata if metadata is not None else {"message_digest": "sha256:abc"},
        )
    assert verify_request_journal(value, scope=s, request_id=request_id)["valid"] is True
    return value


def event_file(store, s, sequence=1, request_id="REQ-1"):
    request_dir = store._request_dir(s, request_id, create=False)
    files = sorted((request_dir / "events").glob(f"{sequence:08d}_*.json"))
    assert len(files) == 1
    return files[0]


def corrupt_event(store, s, mutation, sequence=1):
    path = event_file(store, s, sequence)
    if mutation == "corrupt_json":
        path.write_bytes(b"{\"schema\":")
    else:
        row = json.loads(path.read_text(encoding="utf-8"))
        if mutation == "record_digest":
            row["record_digest"] = "sha256:" + ("0" * 64)
        elif mutation == "event_digest":
            row["event"]["event_digest"] = "sha256:" + ("1" * 64)
        elif mutation == "prev_digest":
            row["prev_digest"] = "sha256:" + ("2" * 64)
        elif mutation == "sequence":
            row["sequence"] = 99
        elif mutation == "scope":
            row["tenant_id"] = "tenant-other"
        elif mutation == "request":
            row["request_id"] = "request-" + ("3" * 40)
        elif mutation == "version":
            row["persistence_version"] = 999
        path.write_text(json.dumps(row), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# GROUP A — REJECTED
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mutation", ["corrupt_json", "record_digest", "event_digest", "prev_digest", "sequence", "scope", "request", "version"])
def test_quarantined_request_blocks_persist(tmp_path, mutation):
    s = scope()
    value = journal(s, states=("ACCEPTED", "ROUTED"))
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="k1")
    corrupt_event(store, s, mutation)
    report = store.recover(scope=s, request_id="REQ-1")  # registers quarantine evidence
    assert report["persistence_state"] == QUARANTINED
    with pytest.raises(JournalStoreRejected) as excinfo:
        store.persist_event(value, scope=s, request_id="REQ-1", sequence=2, idempotency_key="k2")
    assert excinfo.value.state == "REJECTED"
    assert excinfo.value.reason_code == "REQUEST_QUARANTINED"


def test_quarantined_request_blocks_persist_journal(tmp_path):
    s = scope()
    value = journal(s, states=("ACCEPTED", "ROUTED"))
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="k1")
    corrupt_event(store, s, "corrupt_json")
    report = store.recover(scope=s, request_id="REQ-1")
    assert report["persistence_state"] == QUARANTINED
    with pytest.raises(JournalStoreRejected) as excinfo:
        store.persist_journal(value, scope=s, request_id="REQ-1", idempotency_key="kj")
    assert excinfo.value.reason_code == "REQUEST_QUARANTINED"


def test_quarantined_request_blocks_acknowledge(tmp_path):
    s = scope()
    value = journal(s, states=("ACCEPTED", "ROUTED"))
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="k1")
    store.persist_event(value, scope=s, request_id="REQ-1", sequence=2, idempotency_key="k2")
    corrupt_event(store, s, "corrupt_json", sequence=2)
    report = store.recover(scope=s, request_id="REQ-1")
    assert report["persistence_state"] == QUARANTINED
    with pytest.raises(JournalStoreRejected) as excinfo:
        store.acknowledge(scope=s, request_id="REQ-1", sequence=1, event_digest=value["events"][0]["event_digest"])
    assert excinfo.value.reason_code == "REQUEST_QUARANTINED"


def test_idempotency_different_payload_rejected(tmp_path):
    s = scope()
    value = journal(s)
    other = journal(s, states=("DIFFERENT",))
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="same-key")
    with pytest.raises(JournalStoreRejected) as excinfo:
        store.persist_event(other, scope=s, request_id="REQ-1", sequence=1, idempotency_key="same-key")
    assert excinfo.value.state == "REJECTED"
    assert excinfo.value.reason_code == "IDEMPOTENCY_INDEX_MISMATCH"
    # still a conflict for legacy callers
    with pytest.raises(JournalStoreConflict):
        store.persist_event(other, scope=s, request_id="REQ-1", sequence=1, idempotency_key="same-key")


@pytest.mark.parametrize("unsafe", ["../REQ", "/tmp/REQ", r"C:\REQ", "REQ\x00evil"])
def test_unsafe_path_rejected(tmp_path, unsafe):
    store = UnifiedJournalStore(tmp_path / "spool")
    with pytest.raises(ValueError, match="request_id"):
        store.recover(scope=scope(), request_id=unsafe)


def test_symlink_escape_rejected(tmp_path):
    if not hasattr(Path, "symlink_to"):
        pytest.skip("symlink unsupported")
    s = scope()
    value = journal(s)
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="sym")
    request_dir = store._request_dir(s, "REQ-1", create=False)
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
    with pytest.raises(JournalStoreIntegrityError) as excinfo:
        store.recover(scope=s, request_id="REQ-1")
    assert excinfo.value.reason_code == "SYMLINK_ESCAPE"


def test_rejected_exception_contract(tmp_path):
    s = scope()
    value = journal(s, states=("ACCEPTED", "ROUTED"))
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="k1")
    corrupt_event(store, s, "corrupt_json")
    report = store.recover(scope=s, request_id="REQ-1")
    assert report["persistence_state"] == QUARANTINED
    with pytest.raises(JournalStoreRejected) as excinfo:
        store.persist_event(value, scope=s, request_id="REQ-1", sequence=2, idempotency_key="k2")
    err = excinfo.value
    assert err.state == "REJECTED"
    assert err.reason_code in REASON_CODES
    assert isinstance(err.reason_detail, str) and err.reason_detail


# ---------------------------------------------------------------------------
# GROUP B — ACK cumulative
# ---------------------------------------------------------------------------

def _persist_chain(tmp_path, n_states=3):
    s = scope()
    value = new_request_journal(s, "REQ-1", "conv-1")
    for i, state in enumerate(("ACCEPTED", "ROUTED", "READY")[:n_states], start=1):
        value = append_request_event(
            value,
            event_type="REQUEST_ACCEPTED" if i == 1 else "ROLE_ROUTED",
            authorization_class="READ_ONLY",
            state=state,
            observed_at=OBSERVED,
            metadata={"message_digest": "sha256:abc"},
        )
    store = UnifiedJournalStore(tmp_path / "spool")
    for i in range(1, n_states + 1):
        store.persist_event(value, scope=s, request_id="REQ-1", sequence=i, idempotency_key=f"k{i}")
    return s, value, store


def test_first_cumulative_ack_persisted_and_reloaded(tmp_path):
    s, value, store = _persist_chain(tmp_path, 1)
    latest = value["events"][0]
    result = store.acknowledge(scope=s, request_id="REQ-1", sequence=1, event_digest=latest["event_digest"])
    assert result["acked_through_sequence"] == 1
    acks_path = store._request_dir(s, "REQ-1", create=False) / "acks.json"
    raw = json.loads(acks_path.read_text(encoding="utf-8"))
    assert raw["acked_through_sequence"] == 1
    assert raw["acked_head_digest"] == latest["event_digest"]
    reloaded = UnifiedJournalStore(tmp_path / "spool")
    recovered = reloaded.recover(scope=s, request_id="REQ-1")
    assert recovered["persistence_state"] == ACKNOWLEDGED
    assert recovered["ack_status"] == ACKNOWLEDGED


def test_ack_advance_persists_new_head(tmp_path):
    s, value, store = _persist_chain(tmp_path, 3)
    store.acknowledge(scope=s, request_id="REQ-1", sequence=1, event_digest=value["events"][0]["event_digest"])
    store.acknowledge(scope=s, request_id="REQ-1", sequence=3, event_digest=value["events"][2]["event_digest"])
    acks_path = store._request_dir(s, "REQ-1", create=False) / "acks.json"
    raw = json.loads(acks_path.read_text(encoding="utf-8"))
    assert raw["acked_through_sequence"] == 3
    assert raw["acked_head_digest"] == value["events"][2]["event_digest"]
    assert "1" in raw["entries"] and "3" in raw["entries"]


def test_ack_same_idempotent(tmp_path):
    s, value, store = _persist_chain(tmp_path, 2)
    digest = value["events"][1]["event_digest"]
    first = store.acknowledge(scope=s, request_id="REQ-1", sequence=2, event_digest=digest)
    second = store.acknowledge(scope=s, request_id="REQ-1", sequence=2, event_digest=digest)
    assert first["persistence_state"] == ACKNOWLEDGED
    assert second["persistence_state"] == ACKNOWLEDGED


@pytest.mark.parametrize("seq", [4, 999])
def test_ack_future_rejected(tmp_path, seq):
    s, value, store = _persist_chain(tmp_path, 3)
    acks_path = store._request_dir(s, "REQ-1", create=False) / "acks.json"
    before = acks_path.read_bytes() if acks_path.exists() else None
    with pytest.raises(JournalStoreRejected) as excinfo:
        store.acknowledge(scope=s, request_id="REQ-1", sequence=seq, event_digest=value["events"][2]["event_digest"])
    assert excinfo.value.reason_code == "ACK_INVALID"
    assert excinfo.value.state == "REJECTED"
    after = acks_path.read_bytes() if acks_path.exists() else None
    assert before == after


def test_ack_downgrade_rejected(tmp_path):
    s, value, store = _persist_chain(tmp_path, 3)
    store.acknowledge(scope=s, request_id="REQ-1", sequence=3, event_digest=value["events"][2]["event_digest"])
    before = (store._request_dir(s, "REQ-1", create=False) / "acks.json").read_bytes()
    with pytest.raises(JournalStoreRejected) as excinfo:
        store.acknowledge(scope=s, request_id="REQ-1", sequence=1, event_digest=value["events"][0]["event_digest"])
    assert excinfo.value.reason_code == "ACK_INVALID"
    assert (store._request_dir(s, "REQ-1", create=False) / "acks.json").read_bytes() == before


def test_ack_bad_digest_rejected(tmp_path):
    s, value, store = _persist_chain(tmp_path, 2)
    acks_path = store._request_dir(s, "REQ-1", create=False) / "acks.json"
    before = acks_path.read_bytes() if acks_path.exists() else None
    with pytest.raises(JournalStoreRejected) as excinfo:
        store.acknowledge(scope=s, request_id="REQ-1", sequence=2, event_digest="sha256:" + ("f" * 64))
    assert excinfo.value.reason_code == "ACK_INVALID"
    after = acks_path.read_bytes() if acks_path.exists() else None
    assert before == after


def test_ack_cross_scope_rejected(tmp_path):
    # Same textual request id under a different tenant scope must never be accepted.
    a = scope("a")
    b = scope("b")
    value = journal(a)
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(value, scope=a, request_id="REQ-1", sequence=1, idempotency_key="k1")
    # The request dir is derived from the scope fingerprint, so a foreign scope cannot even
    # resolve the durable request: fail-closed before any ACK semantics apply.
    with pytest.raises(LookupError):
        store.acknowledge(scope=b, request_id="REQ-1", sequence=1, event_digest=value["events"][0]["event_digest"])
    # And a same-scope ack against a record whose scope was tampered yields SCOPE_MISMATCH.
    s = scope("c")
    value_c = journal(s)
    store_c = UnifiedJournalStore(tmp_path / "spool-c")
    store_c.persist_event(value_c, scope=s, request_id="REQ-1", sequence=1, idempotency_key="k1")
    path = event_file(store_c, s)
    row = json.loads(path.read_text(encoding="utf-8"))
    row["scope_fingerprint"] = "sha256:" + ("9" * 64)
    path.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(JournalStoreIntegrityError) as excinfo:
        store_c.acknowledge(scope=s, request_id="REQ-1", sequence=1, event_digest=value_c["events"][0]["event_digest"])
    assert excinfo.value.reason_code == "SCOPE_MISMATCH"


def test_quarantined_ack_rejected_and_file_untouched(tmp_path):
    s, value, store = _persist_chain(tmp_path, 2)
    corrupt_event(store, s, "corrupt_json", sequence=1)
    report = store.recover(scope=s, request_id="REQ-1")
    assert report["persistence_state"] == QUARANTINED
    acks_path = store._request_dir(s, "REQ-1", create=False) / "acks.json"
    before = acks_path.read_bytes() if acks_path.exists() else None
    with pytest.raises(JournalStoreRejected) as excinfo:
        store.acknowledge(scope=s, request_id="REQ-1", sequence=2, event_digest=value["events"][1]["event_digest"])
    assert excinfo.value.reason_code == "REQUEST_QUARANTINED"
    after = acks_path.read_bytes() if acks_path.exists() else None
    assert before == after


def test_legacy_ack_read_normalizes_without_rewrite(tmp_path):
    s, value, store = _persist_chain(tmp_path, 2)
    acks_path = store._request_dir(s, "REQ-1", create=False) / "acks.json"
    legacy_body = {
        "schema": store_module.STORE_SCHEMA,
        "kind": "acks",
        "persistence_version": store_module.PERSISTENCE_VERSION,
        "entries": {
            "1": {"state": ACKNOWLEDGED, "event_digest": value["events"][0]["event_digest"], "acknowledged_at": OBSERVED},
        },
        "updated_at": OBSERVED,
    }
    legacy_body["record_digest"] = store_module._record_digest(legacy_body)
    acks_path.write_text(json.dumps(legacy_body), encoding="utf-8")
    before = acks_path.read_bytes()
    recovered = store.recover(scope=s, request_id="REQ-1")
    assert recovered["persistence_state"] != ACKNOWLEDGED  # seq 2 not acked
    assert acks_path.read_bytes() == before  # read did not rewrite legacy file
    # acknowledge advance now writes cumulative fields
    store.acknowledge(scope=s, request_id="REQ-1", sequence=2, event_digest=value["events"][1]["event_digest"])
    raw = json.loads(acks_path.read_text(encoding="utf-8"))
    assert raw["acked_through_sequence"] == 2
    assert "1" in raw["entries"]  # legacy entry preserved


def test_cumulative_ack_survives_new_instance(tmp_path):
    s, value, store = _persist_chain(tmp_path, 3)
    store.acknowledge(scope=s, request_id="REQ-1", sequence=3, event_digest=value["events"][2]["event_digest"])
    fresh = UnifiedJournalStore(tmp_path / "spool")
    recovered = fresh.recover(scope=s, request_id="REQ-1")
    assert recovered["persistence_state"] == ACKNOWLEDGED
    assert recovered["safe_to_resume"] is True


# ---------------------------------------------------------------------------
# GROUP C — reason codes as structured API
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "mutation,expected",
    [
        ("corrupt_json", "CORRUPT_JSON"),
        ("record_digest", "RECORD_DIGEST_MISMATCH"),
        ("event_digest", "EVENT_DIGEST_MISMATCH"),
        ("prev_digest", "PREV_DIGEST_MISMATCH"),
        ("sequence", "SEQUENCE_MISMATCH"),
        ("scope", "SCOPE_MISMATCH"),
        ("request", "REQUEST_MISMATCH"),
        ("version", "PERSISTENCE_VERSION_MISMATCH"),
    ],
)
def test_reason_codes_structured(tmp_path, mutation, expected):
    s = scope()
    value = journal(s)
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="k1")
    corrupt_event(store, s, mutation)
    report = store.recover(scope=s, request_id="REQ-1")
    assert expected in report["reason_codes"]
    assert report["safe_to_resume"] is False
    assert report["persistence_state"] == QUARANTINED


def test_head_points_to_missing_event_code(tmp_path):
    s = scope()
    value = journal(s)
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="k1")
    head_path = store._request_dir(s, "REQ-1", create=False) / "head.json"
    head = json.loads(head_path.read_text(encoding="utf-8"))
    head["sequence"] = 2
    head["event_digest"] = "sha256:" + ("f" * 64)
    body = dict(head)
    body.pop("record_digest", None)
    head["record_digest"] = store_module._record_digest(body)
    head_path.write_text(json.dumps(head), encoding="utf-8")
    report = store.recover(scope=s, request_id="REQ-1")
    assert "HEAD_POINTS_TO_MISSING_EVENT" in report["reason_codes"]
    assert report["head_consistent"] is False


def test_stale_head_is_warning_not_hard(tmp_path):
    s = scope()
    value = journal(s)
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="k1")
    (store._request_dir(s, "REQ-1", create=False) / "head.json").unlink()
    report = store.recover(scope=s, request_id="REQ-1")
    assert "STALE_HEAD" in report["warnings"][0]["reason_code"] or any(
        w["reason_code"] == "STALE_HEAD" for w in report["warnings"]
    )
    assert all(h["reason_code"] != "STALE_HEAD" for h in report["hard_failures"])
    assert report["head_consistent"] is False


def test_lock_timeout_code():
    import threading

    s = scope()
    value = journal(s)
    root = Path("/tmp/gov-lock-test")
    import shutil

    shutil.rmtree(root, ignore_errors=True)
    store = UnifiedJournalStore(root, lock_timeout=0.05)
    request_dir = store._request_dir(s, "REQ-1", create=True)
    paths = store._ensure_layout(request_dir)
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
        with pytest.raises(JournalStoreLockTimeout) as excinfo:
            store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="locked")
        assert excinfo.value.reason_code == "LOCK_TIMEOUT"
    finally:
        release.set()
        thread.join(timeout=2.0)
    shutil.rmtree(root, ignore_errors=True)


def test_recovery_limit_exceeded_code(tmp_path):
    s = scope()
    value = journal(s)
    store = UnifiedJournalStore(tmp_path / "spool", max_event_bytes=128)
    with pytest.raises(Exception) as excinfo:
        store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="big")
    assert getattr(excinfo.value, "reason_code", None) == "RECOVERY_LIMIT_EXCEEDED" or "limit" in str(excinfo.value).lower()


def test_orphan_temp_code(tmp_path):
    s = scope()
    value = journal(s)

    def crash(point, context):
        if point == "AFTER_TEMP_FSYNC":
            raise SimulatedCrash(point)

    store = UnifiedJournalStore(tmp_path / "spool", fault_injector=crash)
    with pytest.raises(SimulatedCrash):
        store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="c1", acknowledge=True)
    report = UnifiedJournalStore(tmp_path / "spool").recover(scope=s, request_id="REQ-1")
    assert "ORPHAN_TEMP" in report["reason_codes"]
    assert any(w["reason_code"] == "ORPHAN_TEMP" for w in report["warnings"])
    assert all(h["reason_code"] != "ORPHAN_TEMP" for h in report["hard_failures"])
    assert report["quarantine_pending_count"] == 0
    assert report["persistence_state"] != QUARANTINED


def test_idempotency_index_stale_vs_mismatch(tmp_path):
    # crash window: index absent after event commit -> STALE warning
    s = scope()
    value = journal(s)

    def crash(point, context):
        if point == "AFTER_EVENT_COMMIT":
            raise SimulatedCrash(point)

    store = UnifiedJournalStore(tmp_path / "spool", fault_injector=crash)
    with pytest.raises(SimulatedCrash):
        store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="c1")
    report = UnifiedJournalStore(tmp_path / "spool").recover(scope=s, request_id="REQ-1")
    assert "IDEMPOTENCY_INDEX_STALE" in report["reason_codes"]
    assert "IDEMPOTENCY_INDEX_MISMATCH" not in report["reason_codes"]

    # real contradiction: index present with divergent entry -> MISMATCH hard
    s2 = scope("b")
    value2 = journal(s2)
    store2 = UnifiedJournalStore(tmp_path / "spool2")
    store2.persist_event(value2, scope=s2, request_id="REQ-1", sequence=1, idempotency_key="k1")
    index_path = store2._request_dir(s2, "REQ-1", create=False) / "idempotency.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    key = list(index["entries"].keys())[0]
    index["entries"][key]["event_digest"] = "sha256:" + ("e" * 64)
    index["entries"][key]["idempotency_payload_digest"] = "sha256:" + ("d" * 64)
    body = dict(index)
    body.pop("record_digest", None)
    index["record_digest"] = store_module._record_digest(body)
    index_path.write_text(json.dumps(index), encoding="utf-8")
    report2 = store2.recover(scope=s2, request_id="REQ-1")
    assert "IDEMPOTENCY_INDEX_MISMATCH" in report2["reason_codes"]
    assert report2["safe_to_resume"] is False


# ---------------------------------------------------------------------------
# GROUP D — manifest integrity + secret redaction
# ---------------------------------------------------------------------------

def test_manifest_created_with_valid_chain(tmp_path):
    s = scope()
    value = journal(s)
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="k1")
    corrupt_event(store, s, "corrupt_json")
    report = store.recover(scope=s, request_id="REQ-1")
    manifest_path = store._request_dir(s, "REQ-1", create=False) / "quarantine" / "manifest.jsonl"
    assert manifest_path.exists()
    lines = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 1
    first = lines[0]
    assert first["schema"] == "ATLASQUANT_AION_UNIFIED_JOURNAL_QUARANTINE_MANIFEST_V1"
    assert first["persistence_version"] == store_module.PERSISTENCE_VERSION
    assert first["previous_manifest_digest"] == store_module.GENESIS
    assert first["manifest_record_digest"] == store_module.UnifiedJournalStore._manifest_record_digest(store, first)
    assert first["recovery_attempt_id"]
    assert first["quarantine_status"] in {"COPIED", "MOVED", "PENDING"}
    assert report["quarantine_count"] >= 1


def test_manifest_tamper_fail_closed(tmp_path):
    s = scope()
    value = journal(s)
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="k1")
    corrupt_event(store, s, "corrupt_json")
    store.recover(scope=s, request_id="REQ-1")
    manifest_path = store._request_dir(s, "REQ-1", create=False) / "quarantine" / "manifest.jsonl"
    text = manifest_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    row = json.loads(lines[0])
    row["reason_code"] = "TAMPERED"
    lines[0] = json.dumps(row)
    manifest_path.write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(JournalStoreIntegrityError):
        store._load_quarantine_manifest(manifest_path)


def test_manifest_invalid_json_fail_closed(tmp_path):
    s = scope()
    value = journal(s)
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="k1")
    corrupt_event(store, s, "corrupt_json")
    store.recover(scope=s, request_id="REQ-1")
    manifest_path = store._request_dir(s, "REQ-1", create=False) / "quarantine" / "manifest.jsonl"
    manifest_path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(JournalStoreIntegrityError) as excinfo:
        store._load_quarantine_manifest(manifest_path)
    assert excinfo.value.reason_code == "CORRUPT_JSON"


def test_manifest_secret_not_leaked(tmp_path):
    s = scope()
    secret_value = journal(s, metadata={"token": "secret-example", "note": "keep me private"})
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(secret_value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="k1")
    corrupt_event(store, s, "corrupt_json")
    store.recover(scope=s, request_id="REQ-1")
    manifest_path = store._request_dir(s, "REQ-1", create=False) / "quarantine" / "manifest.jsonl"
    manifest_text = manifest_path.read_text(encoding="utf-8")
    assert "secret-example" not in manifest_text
    # full payload must not appear either
    assert "keep me private" not in manifest_text


def test_finalized_corruption_copies_evidence(tmp_path):
    s = scope()
    value = journal(s)
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="k1")
    path = event_file(store, s)
    corrupted_bytes = b"{\"schema\":"
    path.write_bytes(corrupted_bytes)
    report = store.recover(scope=s, request_id="REQ-1")
    assert report["persistence_state"] == QUARANTINED
    assert report["safe_to_resume"] is False
    quarantine_dir = store._request_dir(s, "REQ-1", create=False) / "quarantine"
    copies = [p for p in quarantine_dir.iterdir() if p.name.startswith("event-")]
    assert len(copies) == 1
    assert copies[0].read_bytes() == corrupted_bytes
    assert path.read_bytes() == corrupted_bytes  # original preserved


# ---------------------------------------------------------------------------
# GROUP H — safe_to_resume matrix
# ---------------------------------------------------------------------------

def test_safe_to_resume_healthy_true(tmp_path):
    s = scope()
    value = journal(s)
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="k1")
    report = store.recover(scope=s, request_id="REQ-1")
    assert report["safe_to_resume"] is True
    for flag in ("scope_valid", "request_valid", "chain_valid", "version_accepted",
                 "idempotency_consistent", "ack_consistent", "quarantine_clear",
                 "deterministic_recovery"):
        assert report[flag] is True, flag


@pytest.mark.parametrize("mutation", ["corrupt_json", "record_digest", "event_digest", "prev_digest", "sequence", "scope", "request", "version"])
def test_safe_to_resume_false_on_corruption(tmp_path, mutation):
    s = scope()
    value = journal(s)
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="k1")
    corrupt_event(store, s, mutation)
    report = store.recover(scope=s, request_id="REQ-1")
    assert report["safe_to_resume"] is False


def test_safe_to_resume_false_on_bad_ack_index(tmp_path):
    s = scope()
    value = journal(s)
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="k1")
    acks_path = store._request_dir(s, "REQ-1", create=False) / "acks.json"
    acks_path.write_bytes(b"{broken")
    report = store.recover(scope=s, request_id="REQ-1")
    assert report["safe_to_resume"] is False
    assert report["ack_consistent"] is False


# ---------------------------------------------------------------------------
# GROUP I — recovery report contract + state-only invariants
# ---------------------------------------------------------------------------

REPORT_FIELDS = (
    "schema", "persistence_version", "scope_fingerprint", "request_id_safe", "recovery_attempt_id",
    "events_scanned", "last_valid_sequence", "recovered_head_digest",
    "scope_valid", "request_valid", "chain_valid", "version_accepted", "head_consistent",
    "idempotency_consistent", "ack_consistent", "quarantine_clear", "deterministic_recovery",
    "quarantine_count", "quarantine_pending_count", "warnings", "hard_failures", "reason_codes",
    "safe_to_resume",
)
LEGACY_FIELDS = ("status", "persistence_state", "event_count", "journal_integrity", "head_status", "ack_status", "quarantined_files", "reasons")
STATE_ONLY = ("restores_state_only", "automatic_resume_executes", "checkpoint_written", "external_action_executed", "memory_promoted")


def test_recovery_report_contract_healthy(tmp_path):
    s = scope()
    value = journal(s)
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="k1")
    report = store.recover(scope=s, request_id="REQ-1")
    for field in REPORT_FIELDS:
        assert field in report, field
    for field in LEGACY_FIELDS:
        assert field in report, field
    assert report["events_scanned"] == 1
    assert report["last_valid_sequence"] == 1
    assert report["recovered_head_digest"] == value["events"][0]["event_digest"]
    for field in STATE_ONLY:
        expected = field == "restores_state_only"
        assert report[field] is expected, field


def test_recovery_report_contract_corrupted(tmp_path):
    s = scope()
    value = journal(s)
    store = UnifiedJournalStore(tmp_path / "spool")
    store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="k1")
    corrupt_event(store, s, "event_digest")
    report = store.recover(scope=s, request_id="REQ-1")
    for field in REPORT_FIELDS:
        assert field in report, field
    for field in STATE_ONLY:
        expected = field == "restores_state_only"
        assert report[field] is expected, field
    assert report["safe_to_resume"] is False