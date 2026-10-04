from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from aion_chat.models import Scope
from atlasquant_aion_unified_journal import append_request_event, new_request_journal, verify_request_journal
from atlasquant_aion_unified_journal_store import (
    DURABLE,
    STAGED,
    JournalStoreConflict,
    JournalStoreIntegrityError,
    SimulatedCrash,
    UnifiedJournalStore,
)
from atlasquant_aion_memory import (
    checkpoint_integrity_report,
    checkpoint_source_digest,
    default_checkpoint,
    ensure_operating_checkpoint,
)
from atlasquant_aion_recovery import recovery_preflight, restore_checkpoint_revision
from atlasquant_aion_memory import RuntimeConfig

OBSERVED = "2026-10-04T00:00:00+00:00"


def scope(name="a"):
    return Scope(f"owner-{name}", f"tenant-{name}", f"workspace-{name}")


def journal(s=None, *, state="ACCEPTED", request_id="REQ-1"):
    s = s or scope()
    value = new_request_journal(s, request_id, "conv-1")
    value = append_request_event(
        value,
        event_type="REQUEST_ACCEPTED",
        authorization_class="READ_ONLY",
        state=state,
        observed_at=OBSERVED,
        metadata={"message_digest": "sha256:abc"},
    )
    assert verify_request_journal(value, scope=s, request_id=request_id)["valid"] is True
    return value


def event_file(store, s, sequence=1, request_id="REQ-1"):
    request_dir = store._request_dir(s, request_id, create=False)
    files = sorted((request_dir / "events").glob(f"{sequence:08d}_*.json"))
    assert len(files) == 1
    return files[0]


def candidate(*, revision="a" * 40):
    cp = default_checkpoint()
    cp["aion"]["priority"] = "recovery candidate"
    return {
        "status": "CONFIRMED",
        "revision": revision,
        "checkpoint": cp,
        "integrity": checkpoint_integrity_report(cp),
        "digest": checkpoint_source_digest(cp),
    }


def current(*, mismatch=False):
    cp = default_checkpoint()
    if mismatch:
        cp["studio"]["digest"] = "tampered"
    return {
        "status": "CONFIRMED",
        "sha": "b" * 40,
        "checkpoint": cp,
        "integrity": checkpoint_integrity_report(cp),
    }


class TestDurableStoreAtomicity:
    def test_first_persist_is_durable_without_prefilled_helper(self, tmp_path):
        s = scope()
        value = journal(s)
        store = UnifiedJournalStore(tmp_path / "spool")
        result = store.persist_event(
            value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="IK-first"
        )
        assert result["status"] == "PERSISTED"
        assert result["persistence_state"] == DURABLE

    @pytest.mark.parametrize(
        "stage,expected_state",
        [
            ("BEFORE_DURABLE_COMMIT", STAGED),
            ("AFTER_TEMP_FSYNC", STAGED),
            ("AFTER_EVENT_COMMIT", DURABLE),
            ("AFTER_HEAD_COMMIT", DURABLE),
        ],
    )
    def test_fault_windows_fail_closed(self, tmp_path, stage, expected_state):
        s = scope()
        value = journal(s)

        def crash(point, context):
            if point == stage:
                raise SimulatedCrash(point)

        with pytest.raises(SimulatedCrash):
            UnifiedJournalStore(tmp_path / "spool", fault_injector=crash).persist_event(
                value,
                scope=s,
                request_id="REQ-1",
                sequence=1,
                idempotency_key=f"IK-{stage}",
            )
        report = UnifiedJournalStore(tmp_path / "spool").recover(scope=s, request_id="REQ-1")
        assert report["persistence_state"] == expected_state
        assert report["external_action_executed"] is False
        assert report["automatic_resume_executes"] is False


class TestDurableStoreLostResponse:
    def test_same_key_same_payload_is_idempotent(self, tmp_path):
        s = scope()
        value = journal(s)
        store = UnifiedJournalStore(tmp_path / "spool")
        first = store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="IK")
        again = store.persist_event(value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="IK")
        assert first["status"] == "PERSISTED"
        assert again["status"] == "IDEMPOTENT"
        assert store.recover(scope=s, request_id="REQ-1")["event_count"] == 1

    def test_same_key_different_payload_conflicts(self, tmp_path):
        s = scope()
        store = UnifiedJournalStore(tmp_path / "spool")
        store.persist_event(journal(s, state="A"), scope=s, request_id="REQ-1", sequence=1, idempotency_key="IK")
        with pytest.raises(JournalStoreConflict):
            store.persist_event(journal(s, state="B"), scope=s, request_id="REQ-1", sequence=1, idempotency_key="IK")


class TestDurableStoreCorruption:
    @pytest.mark.parametrize("mode", ["truncated", "empty", "digest", "missing"])
    def test_corruption_never_becomes_safe_state(self, tmp_path, mode):
        s = scope()
        store = UnifiedJournalStore(tmp_path / "spool")
        store.persist_event(journal(s), scope=s, request_id="REQ-1", sequence=1, idempotency_key="IK")
        path = event_file(store, s)
        if mode == "truncated":
            path.write_bytes(b'{"schema":')
        elif mode == "empty":
            path.write_bytes(b"")
        elif mode == "digest":
            row = json.loads(path.read_text(encoding="utf-8"))
            row["record_digest"] = "sha256:" + "0" * 64
            path.write_text(json.dumps(row), encoding="utf-8")
        else:
            path.unlink()
        report = store.recover(scope=s, request_id="REQ-1")
        assert report["external_action_executed"] is False
        assert report["automatic_resume_executes"] is False
        if mode != "missing":
            assert report["safe_to_resume"] is False


class TestDurableStorePathAndIsolation:
    @pytest.mark.parametrize(
        "bad",
        [
            "../x", r"..\x", "/x", r"C:\x", "\\server\share", "x\x00y",
            "", ".", "..", "CON", "PRN", "AUX", "NUL", "COM1", "LPT1",
            "name.", "name ", "x" * 300,
        ],
    )
    def test_bad_request_identifiers_rejected(self, tmp_path, bad):
        store = UnifiedJournalStore(tmp_path / "spool")
        with pytest.raises((ValueError, JournalStoreIntegrityError, LookupError)):
            store.recover(scope=scope(), request_id=bad)

    def test_symlink_root_rejected(self, tmp_path):
        if not hasattr(Path, "symlink_to"):
            pytest.skip("symlink unsupported")
        outside = tmp_path / "outside"
        outside.mkdir()
        root = tmp_path / "spool"
        try:
            root.symlink_to(outside, target_is_directory=True)
        except OSError:
            pytest.skip("symlink creation unavailable")
        with pytest.raises((ValueError, JournalStoreIntegrityError)):
            UnifiedJournalStore(root)

    @pytest.mark.parametrize("kind", ["tenant", "owner", "workspace"])
    def test_cross_scope_recovery_fails_closed(self, tmp_path, kind):
        a = scope("a")
        b = scope("b")
        if kind == "tenant":
            b = Scope(a.owner_id, "tenant-b", a.workspace_id)
        elif kind == "owner":
            b = Scope("owner-b", a.tenant_id, a.workspace_id)
        else:
            b = Scope(a.owner_id, a.tenant_id, "workspace-b")
        store = UnifiedJournalStore(tmp_path / "spool")
        store.persist_event(journal(a), scope=a, request_id="REQ-1", sequence=1, idempotency_key="IK")
        with pytest.raises(LookupError):
            store.recover(scope=b, request_id="REQ-1")

    def test_same_idempotency_key_isolated_between_tenants(self, tmp_path):
        a, b = scope("a"), scope("b")
        root = tmp_path / "spool"
        sa = UnifiedJournalStore(root)
        sb = UnifiedJournalStore(root)
        ra = sa.persist_event(journal(a), scope=a, request_id="REQ-1", sequence=1, idempotency_key="IK")
        rb = sb.persist_event(journal(b), scope=b, request_id="REQ-1", sequence=1, idempotency_key="IK")
        assert ra["status"] == rb["status"] == "PERSISTED"


class TestDurableStoreConcurrencyAndQuarantine:
    def test_two_writers_one_persist_one_idempotent(self, tmp_path):
        s = scope()
        root = tmp_path / "spool"
        value = journal(s)

        def write():
            return UnifiedJournalStore(root, lock_timeout=2.0).persist_event(
                value, scope=s, request_id="REQ-1", sequence=1, idempotency_key="IK"
            )["status"]

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = sorted(x.result() for x in [pool.submit(write), pool.submit(write)])
        assert statuses == ["IDEMPOTENT", "PERSISTED"]

    def test_quarantine_preserves_corrupt_evidence(self, tmp_path):
        s = scope()
        store = UnifiedJournalStore(tmp_path / "spool")
        store.persist_event(journal(s), scope=s, request_id="REQ-1", sequence=1, idempotency_key="IK")
        path = event_file(store, s)
        path.write_bytes(b"CORRUPT")
        report = store.recover(scope=s, request_id="REQ-1")
        assert report["safe_to_resume"] is False
        qdir = store._request_dir(s, "REQ-1", create=False) / "quarantine"
        quarantined = [p for p in qdir.iterdir() if p.is_file() and p.name != "manifest.jsonl"]
        assert quarantined
        assert any(p.read_bytes() == b"CORRUPT" for p in quarantined)

    def test_multiple_corrupts_are_isolated_over_retries(self, tmp_path):
        s = scope()
        value = new_request_journal(s, "REQ-1", "conv-1")
        value = append_request_event(value, event_type="REQUEST_ACCEPTED", authorization_class="READ_ONLY", state="A", observed_at=OBSERVED)
        value = append_request_event(value, event_type="ROLE_ROUTED", authorization_class="READ_ONLY", state="B", observed_at=OBSERVED)
        store = UnifiedJournalStore(tmp_path / "spool")
        store.persist_journal(value, scope=s, request_id="REQ-1", idempotency_key="IK")
        event_file(store, s, 1).write_bytes(b"CORRUPT-1")
        event_file(store, s, 2).write_bytes(b"CORRUPT-2")
        one = store.recover(scope=s, request_id="REQ-1")
        two = store.recover(scope=s, request_id="REQ-1")
        assert one["safe_to_resume"] is False
        assert two["safe_to_resume"] is False
        qdir = store._request_dir(s, "REQ-1", create=False) / "quarantine"
        evidence = [p for p in qdir.iterdir() if p.is_file() and p.name != "manifest.jsonl"]
        assert len(evidence) >= 2

    def test_recovery_flags_never_claim_execution(self, tmp_path):
        s = scope()
        store = UnifiedJournalStore(tmp_path / "spool")
        store.persist_event(journal(s), scope=s, request_id="REQ-1", sequence=1, idempotency_key="IK")
        report = store.recover(scope=s, request_id="REQ-1")
        assert report["external_action_executed"] is False
        assert report["automatic_resume_executes"] is False
        assert report["memory_promoted"] is False
        assert report["restores_state_only"] is True


class TestRecoveryRedTeam:
    def test_good_candidate_allowed_and_read_only(self):
        result = recovery_preflight(current(mismatch=True), candidate())
        assert result["allowed"] is True
        assert result["executes_action"] is False

    def test_digest_mismatch_fails_closed(self):
        c = candidate()
        c["digest"] = "0" * 64
        result = recovery_preflight(current(), c)
        assert result["allowed"] is False
        assert "digest" in result["reason"].lower()

    def test_same_content_is_rejected(self):
        cur = current()
        c = candidate()
        c["checkpoint"] = deepcopy(cur["checkpoint"])
        c["integrity"] = checkpoint_integrity_report(c["checkpoint"])
        c["digest"] = checkpoint_source_digest(c["checkpoint"])
        assert recovery_preflight(cur, c)["allowed"] is False

    def test_runtime_sha_missing_fails_closed(self):
        cur = current()
        cur["sha"] = ""
        result = recovery_preflight(cur, candidate())
        assert result["allowed"] is False

    def test_candidate_mismatch_fails_closed(self):
        c = candidate()
        c["checkpoint"]["business"]["digest"] = "wrong"
        c["integrity"] = checkpoint_integrity_report(c["checkpoint"])
        result = recovery_preflight(current(), c)
        assert result["allowed"] is False

    @pytest.mark.parametrize("approved", [False, 1, 0, "true", None, {}, []])
    def test_approval_requires_exact_true(self, approved):
        cfg = RuntimeConfig(token="x", repo="owner/repo", branch="atlasquant-runtime")
        with patch("atlasquant_aion_recovery.save_runtime_checkpoint") as save, patch(
            "atlasquant_aion_recovery.load_checkpoint_revision"
        ) as load:
            result = restore_checkpoint_revision(candidate(), current(mismatch=True), cfg, approved=approved)
        assert result["status"] == "BLOCKED"
        save.assert_not_called()
        load.assert_not_called()


class TestMemoryRedTeam:
    def test_default_checkpoint_integrity_confirmed(self):
        cp = default_checkpoint()
        assert checkpoint_integrity_report(cp)["state"] == "CONFIRMED"

    def test_tamper_is_mismatch(self):
        cp = default_checkpoint()
        cp["operating"]["tasks"].append({"task_id": "T"})
        assert checkpoint_integrity_report(cp)["state"] == "MISMATCH"

    def test_none_is_unknown(self):
        assert checkpoint_integrity_report(None)["state"] == "UNKNOWN"

    def test_partial_checkpoint_requires_migration(self):
        result = checkpoint_integrity_report({"checkpoint_version": 1, "project": "AtlasQuant"})
        assert result["state"] in {"MIGRATION_REQUIRED", "UNKNOWN"}

    def test_source_digest_changes_with_content(self):
        a = default_checkpoint()
        b = deepcopy(a)
        b["evidence"]["extra"] = "changed"
        assert checkpoint_source_digest(a) != checkpoint_source_digest(b)

    def test_duplicate_effective_version_is_detectable_by_digest(self):
        a = default_checkpoint()
        b = deepcopy(a)
        assert checkpoint_source_digest(a) == checkpoint_source_digest(b)

    def test_internal_whitespace_is_not_collapsed_by_norm(self):
        import atlasquant_aion_memory as memory
        assert memory._norm("a  b") != memory._norm("a b")

    def test_ensure_preserves_area_states_without_execution_promotion(self):
        cp = default_checkpoint()
        cp["areas"]["trader"] = "CUSTOM"
        upgraded = ensure_operating_checkpoint(cp)
        assert upgraded["areas"]["trader"] == "CUSTOM"
        assert upgraded["aion"]["real_trading"] is False


class TestSideEffectGuards:
    def test_store_recover_uses_no_socket_or_subprocess(self, tmp_path):
        s = scope()
        store = UnifiedJournalStore(tmp_path / "spool")
        store.persist_event(journal(s), scope=s, request_id="REQ-1", sequence=1, idempotency_key="IK")
        with patch("socket.socket", side_effect=AssertionError("socket forbidden")), patch(
            "subprocess.Popen", side_effect=AssertionError("subprocess forbidden")
        ):
            report = store.recover(scope=s, request_id="REQ-1")
        assert report["external_action_executed"] is False

    def test_memory_pure_helpers_use_no_socket_or_subprocess(self):
        with patch("socket.socket", side_effect=AssertionError("socket forbidden")), patch(
            "subprocess.Popen", side_effect=AssertionError("subprocess forbidden")
        ):
            cp = default_checkpoint()
            assert checkpoint_integrity_report(cp)["state"] == "CONFIRMED"
            assert checkpoint_source_digest(cp)

    def test_recovery_preflight_uses_no_socket_or_subprocess(self):
        with patch("socket.socket", side_effect=AssertionError("socket forbidden")), patch(
            "subprocess.Popen", side_effect=AssertionError("subprocess forbidden")
        ):
            result = recovery_preflight(current(mismatch=True), candidate())
        assert result["allowed"] is True
        assert result["executes_action"] is False
