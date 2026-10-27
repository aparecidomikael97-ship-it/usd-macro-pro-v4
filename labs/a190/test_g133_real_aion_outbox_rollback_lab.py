"""G133: actual AION SQLiteChatStore + ExecutionOutbox rollback counterexample.

LAB only. No provider, network, Worker, external authority, customer data or SEND.
Green assertions may demonstrate a vulnerable LAB opt-in; never count as P0.
"""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
EVENT = "synthetic-original-business-event-A"


class MemoryOnlyAdapter:
    """In-process synthetic effect recorder, never an external adapter."""
    def __init__(self):
        self.send_calls = []

    def send(self, decision, key):
        self.send_calls.append((decision["intent_ref"], key))
        return {"accepted": True, "confirmed": True, "effect_ref": "FIXTURE-" + key[:16]}

    def reconcile(self, key, _decision):
        return {"found": False, "authoritative_absence": False, "fixture": True}


class G133ActualAionOutboxRollbackLab(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="a190-g133-real-outbox-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "actual-aion-outbox.sqlite3"
        self.backup_path = self.root / "pre-attempt-backup.sqlite3"
        self.scope = Scope("synthetic-owner", "synthetic-tenant", "synthetic-workspace")
        self.open_handles = []
        self.addCleanup(self._close_all)
        store, _ = self._open()
        self._close(store)
        # Back up the ACTUAL AION DDL, not a toy reservations table.
        with closing(sqlite3.connect(self.path)) as src, closing(sqlite3.connect(self.backup_path)) as dest:
            src.backup(dest)
        self.assertTrue(self.backup_path.is_file())

    def _close(self, store):
        if store in self.open_handles:
            self.open_handles.remove(store)
            store.close()

    def _close_all(self):
        for store in self.open_handles:
            store.close()
        self.open_handles.clear()

    def _open(self, *, unsafe=False):
        store = SQLiteChatStore(self.path)
        self.open_handles.append(store)
        # Even deliberately caller-supplied True callbacks MUST be quarantined by default.
        outbox = ExecutionOutbox(
            store, self.scope,
            first_attempt_guard=lambda _intent: True,
            evidence_verifier=lambda *_args: True,
            unsafe_allow_synthetic_lab_callbacks=unsafe,
        )
        return store, outbox

    def _restore(self):
        self.assertFalse(self.open_handles, "all actual AION SQLite handles must be closed before host rollback")
        for path in (self.path, Path(str(self.path) + "-wal"), Path(str(self.path) + "-shm")):
            path.unlink(missing_ok=True)
        shutil.copy2(self.backup_path, self.path)

    def _enqueue(self, outbox, *, ref="claimed-event-A"):
        return outbox.enqueue(
            intent_ref=ref,
            action="synthetic-no-real-send",
            payload={"business_event_id": EVENT, "kind": "fixed-synthetic-intent"},
            semantic_event_id_lab=EVENT,
            aggregate_key="synthetic-aggregate",
            policy_version="LAB-POLICY",
            authorization_ref="LAB-OWNER-UNVERIFIED",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )

    def _policy(self, decision):
        return {
            "allowed": True,
            "actor_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "policy_version": decision["policy_version"],
            "authorization_ref": decision["authorization_ref"],
            "reauthenticated": True,
        }

    def _dispatch(self, outbox, item, adapter):
        claimed = outbox.claim_next("synthetic-worker", now=NOW, lease_seconds=60)
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["idempotency_key"], item["idempotency_key"])
        return outbox.dispatch_claimed(
            item["idempotency_key"], worker_id="synthetic-worker",
            authorize=self._policy, adapter=adapter, now=NOW + timedelta(seconds=1),
        )

    def test_01_actual_outbox_semantic_collision_denied_while_history_intact(self):
        store, outbox = self._open()
        first = self._enqueue(outbox)
        self.assertEqual(first["enqueue_state"], "ENQUEUED")
        with self.assertRaisesRegex(ValueError, "semantic business event collision"):
            self._enqueue(outbox, ref="relabelled-technical-id")
        self.assertEqual(len(outbox.list()), 1)
        self._close(store)
        print("G133_ACTUAL_OUTBOX_INTACT_SEMANTIC_LOCK=DENIED_LOCAL_ONLY")

    def test_02_actual_outbox_reaccepts_semantic_event_after_host_rollback(self):
        store, outbox = self._open()
        first = self._enqueue(outbox)
        first_key = first["idempotency_key"]
        self._close(store)
        self._restore()
        store, outbox = self._open()
        replay = self._enqueue(outbox, ref="relabelled-technical-id")
        self.assertEqual(replay["enqueue_state"], "ENQUEUED")
        self.assertNotEqual(first_key, replay["idempotency_key"])
        self.assertEqual(len(outbox.list()), 1)
        self._close(store)
        print("G133_REAL_AION_OUTBOX_ROLLBACK=RELABELED_EVENT_READMITTED_NOT_P0")

    def test_03_default_true_callbacks_still_prevent_send_after_rollback(self):
        adapter = MemoryOnlyAdapter()
        store, outbox = self._open()
        first = self._enqueue(outbox)
        result = self._dispatch(outbox, first, adapter)
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(len(adapter.send_calls), 0)
        self._close(store)
        self._restore()
        store, outbox = self._open()
        second = self._enqueue(outbox, ref="relabelled-technical-id")
        again = self._dispatch(outbox, second, adapter)
        self.assertEqual(again["state"], "UNCERTAIN")
        self.assertEqual(len(adapter.send_calls), 0)
        self._close(store)
        print("G133_DEFAULT_REAL_OUTBOX_ROLLBACK=NO_ADAPTER_SEND")

    def test_04_explicit_unsafe_lab_optin_replays_synthetic_effect_after_rollback(self):
        adapter = MemoryOnlyAdapter()
        store, outbox = self._open(unsafe=True)
        first = self._enqueue(outbox)
        result = self._dispatch(outbox, first, adapter)
        self.assertEqual(result["state"], "CONFIRMED")
        self.assertEqual(len(adapter.send_calls), 1)
        self._close(store)
        self._restore()
        store, outbox = self._open(unsafe=True)
        second = self._enqueue(outbox, ref="relabelled-technical-id")
        result = self._dispatch(outbox, second, adapter)
        self.assertEqual(result["state"], "CONFIRMED")
        self.assertEqual(len(adapter.send_calls), 2)
        self._close(store)
        print("G133_UNSAFE_SYNTHETIC_LAB_CALLBACKS=DOUBLE_IN_MEMORY_EFFECT_NOT_P0")

    def test_05_exact_original_request_can_be_reenqueued_after_host_rollback(self):
        store, outbox = self._open()
        first = self._enqueue(outbox)
        self._close(store)
        self._restore()
        store, outbox = self._open()
        second = self._enqueue(outbox)
        self.assertEqual(second["enqueue_state"], "ENQUEUED")
        self.assertEqual(second["idempotency_key"], first["idempotency_key"])
        self._close(store)
        print("G133_REAL_OUTBOX_EXACT_REPLAY_AFTER_ROLLBACK=REQUEUED_NO_EXTERNAL_EFFECT")


if __name__ == "__main__":
    unittest.main()
