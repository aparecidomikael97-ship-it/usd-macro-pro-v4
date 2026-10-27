"""G134 adversarial test: real AION Outbox + separate LOCAL custodian process.

Everything is synthetic. This proves a *narrow local fail-closed contract*,
NOT independent authority, authentic HUMAN_OWNER, provider acknowledgement,
off-host monotonic custody, or a production adapter. A green negative test
can still mean an open P0. No network/Worker/provider SEND.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from labs.a190.g134_process_custody_lab import (
    ADMITTED, BAD_INPUT, BAD_STATE, LOST_ACK, UNCERTAIN, UNAVAILABLE,
)


NOW = datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)
EVENT = "synthetic-original-event-A"
PAYLOAD = {"business_event_id": EVENT, "kind": "SYNTHETIC-NO-EFFECT"}
DIGEST = sha256(b"single-synthetic-economic-operation-v1").hexdigest()


class NoExternalAdapter:
    def __init__(self):
        self.send_calls = 0

    def send(self, _decision, _key):
        self.send_calls += 1
        raise AssertionError("G134_MUST_NOT_REACH_FAKE_SEND")

    def reconcile(self, _key, _decision):
        raise AssertionError("G134_MUST_NOT_RECONCILE_FAKE_PROVIDER")


class G134ProcessSeparatedLocalCustodyLabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-g134-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.chat_db = self.root / "aion" / "real-outbox.sqlite3"
        self.chat_db.parent.mkdir()
        self.custody_db = self.root / "process-local-custody" / "custody.sqlite3"
        self.old_chat = self.root / "chat-before-intent.sqlite3"
        self.old_custody = self.root / "custody-before-intent.sqlite3"
        self.scope = Scope("synthetic-owner", "synthetic-tenant", "synthetic-workspace")
        self.stores = []
        self.addCleanup(self._close_all)

        init = self._run("bootstrap", self.custody_db)
        self.assertEqual(init, "G134_EXPLICIT_LOCAL_FIXTURE_BOOTSTRAP")
        store, _ = self._open()
        self._close(store)
        with closing(sqlite3.connect(self.chat_db)) as src:
            with closing(sqlite3.connect(self.old_chat)) as dst:
                src.backup(dst)
        shutil.copy2(self.custody_db, self.old_custody)

    @staticmethod
    def _command(*args):
        return [sys.executable, "-B", "-m", "labs.a190.g134_process_custody_lab", *map(str, args)]

    def _run(self, *args):
        p = subprocess.run(
            self._command(*args), text=True, capture_output=True, timeout=12,
            check=True,
        )
        return p.stdout.strip()

    def _reserve(self, ref="request-first", event=EVENT, *, lost=False,
                 digest=DIGEST, tenant=None):
        args = (
            "reserve", self.custody_db, tenant or self.scope.tenant_id,
            event, digest, ref,
        )
        return self._run(*args, *(("lose-ack",) if lost else ()))

    def _open(self):
        store = SQLiteChatStore(self.chat_db)
        self.stores.append(store)
        outbox = ExecutionOutbox(
            store, self.scope,
            first_attempt_guard=lambda _: True,
            evidence_verifier=lambda *_: True,
            # Deliberately NO unsafe_allow_synthetic_lab_callbacks.
        )
        return store, outbox

    def _close(self, store):
        if store in self.stores:
            self.stores.remove(store)
            store.close()

    def _close_all(self):
        while self.stores:
            self.stores.pop().close()

    def _restore_chat(self):
        self.assertFalse(self.stores, "AION connections must close before restoring")
        for p in (self.chat_db, Path(str(self.chat_db) + "-wal"),
                  Path(str(self.chat_db) + "-shm")):
            p.unlink(missing_ok=True)
        shutil.copy2(self.old_chat, self.chat_db)

    def _restore_custody(self):
        # NEGATIVE control only: same-host privileged compromise defeats fixture.
        for p in (self.custody_db, Path(str(self.custody_db) + "-wal"),
                  Path(str(self.custody_db) + "-shm")):
            p.unlink(missing_ok=True)
        shutil.copy2(self.old_custody, self.custody_db)

    def _stage_only_if_reserved(self, outbox, *, ref="request-first", event=EVENT):
        # The isolated LAB bridge is a CALLER-level staging protocol, not a
        # production change to ExecutionOutbox.enqueue(). Direct bypass remains!
        status = self._reserve(ref=ref, event=event)
        if status != ADMITTED:
            return status, None
        item = outbox.enqueue(
            intent_ref=ref, action="no-real-send",
            payload={"business_event_id": event, "kind": "SYNTHETIC-NO-EFFECT"},
            semantic_event_id_lab=event,
            aggregate_key="synthetic-aggregate",
            policy_version="LAB-POLICY",
            authorization_ref="NOT_AUTHENTICATED_LAB_OWNER",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )
        return status, item

    def test_01_real_outbox_host_only_rollback_rejected_by_separate_local_custody(self):
        store, outbox = self._open()
        status, item = self._stage_only_if_reserved(outbox)
        self.assertEqual(status, ADMITTED)
        self.assertEqual(item["enqueue_state"], "ENQUEUED")
        self._close(store)
        self._restore_chat()
        store, outbox = self._open()
        again, staged = self._stage_only_if_reserved(
            outbox, ref="new-request-after-host-rollback")
        self.assertEqual(again, UNCERTAIN)
        self.assertIsNone(staged)
        self.assertEqual(len(outbox.list()), 0)
        self._close(store)
        print("G134_AION_SQLITE_ROLLBACK_WITH_CUSTODY_INTACT=SECOND_STAGE_DENIED_LAB_ONLY")

    def test_02_joint_rollback_defeats_same_host_custody_not_p0(self):
        store, outbox = self._open()
        self.assertEqual(self._stage_only_if_reserved(outbox)[0], ADMITTED)
        self._close(store)
        self._restore_chat()
        self._restore_custody()
        store, outbox = self._open()
        status, item = self._stage_only_if_reserved(
            outbox, ref="new-request-after-joint-rollback")
        self.assertEqual(status, ADMITTED)
        self.assertEqual(item["enqueue_state"], "ENQUEUED")
        self._close(store)
        print("G134_JOINT_AION_AND_CUSTODIAN_ROLLBACK=READMISSION_RED_NOT_P0")

    def test_03_lost_custodian_ack_after_commit_is_uncertain_without_restage(self):
        store, outbox = self._open()
        self.assertEqual(self._reserve(lost=True), LOST_ACK)
        status, item = self._stage_only_if_reserved(
            outbox, ref="blind-retry-forbidden")
        self.assertEqual(status, UNCERTAIN)
        self.assertIsNone(item)
        self.assertEqual(outbox.list(), [])
        self._close(store)
        print("G134_CUSTODY_POST_COMMIT_LOST_ACK=UNCERTAIN_ZERO_AUTO_RESEND")

    def test_04_missing_custody_does_not_create_fresh_trust_root(self):
        store, outbox = self._open()
        self.custody_db.unlink()
        status, item = self._stage_only_if_reserved(outbox)
        self.assertEqual(status, UNAVAILABLE)
        self.assertIsNone(item)
        self.assertFalse(self.custody_db.exists())
        self.assertEqual(outbox.list(), [])
        self._close(store)
        print("G134_CUSTODY_UNAVAILABLE=DENY_WITHOUT_BOOTSTRAP_OR_SEND")

    def test_05_corrupted_local_custody_blocks_outbox_staging(self):
        store, outbox = self._open()
        self.custody_db.write_bytes(b"not a SQLite database")
        status, item = self._stage_only_if_reserved(outbox)
        self.assertEqual(status, BAD_STATE)
        self.assertIsNone(item)
        self.assertEqual(outbox.list(), [])
        self._close(store)

    def test_06_different_request_id_same_event_denied_by_atomic_unique_constraint(self):
        store, outbox = self._open()
        self.assertEqual(self._stage_only_if_reserved(outbox)[0], ADMITTED)
        status, item = self._stage_only_if_reserved(outbox, ref="different-request")
        self.assertEqual(status, UNCERTAIN)
        self.assertIsNone(item)
        self.assertEqual(len(outbox.list()), 1)
        self._close(store)

    def test_07_untrusted_original_event_relabel_still_bypasses_identity(self):
        store, outbox = self._open()
        self.assertEqual(self._stage_only_if_reserved(outbox)[0], ADMITTED)
        status, item = self._stage_only_if_reserved(
            outbox, ref="request-b", event="attacker-claimed-original-event-B")
        self.assertEqual(status, ADMITTED)
        self.assertEqual(item["enqueue_state"], "ENQUEUED")
        self.assertEqual(len(outbox.list()), 2)
        self._close(store)
        print("G134_CALLER_RELABELED_ORIGINAL_EVENT=SECOND_STAGE_RED_NO_HUMAN_OWNER_AUTH")

    def test_08_reservation_before_local_db_failure_is_never_blindly_replayed(self):
        store, outbox = self._open()
        self.assertEqual(self._reserve(), ADMITTED)
        # Host process died BEFORE it could stage; do not infer absence
        # or create a second reservation from missing AION outbox row.
        self._close(store)
        self._restore_chat()
        store, outbox = self._open()
        self.assertEqual(outbox.list(), [])
        status, item = self._stage_only_if_reserved(outbox, ref="retry-after-crash")
        self.assertEqual(status, UNCERTAIN)
        self.assertIsNone(item)
        self._close(store)
        print("G134_CRASH_BETWEEN_CUSTODY_AND_AION_COMMIT=NO_BLIND_RESTAGE")

    def test_09_default_execution_outbox_keeps_adapter_send_quarantined(self):
        store, outbox = self._open()
        status, item = self._stage_only_if_reserved(outbox)
        self.assertEqual(status, ADMITTED)
        claimed = outbox.claim_next("synthetic-worker", now=NOW, lease_seconds=60)
        self.assertIsNotNone(claimed)
        adapter = NoExternalAdapter()

        def policy(decision):
            return {
                "allowed": True, "actor_id": self.scope.owner_id,
                "tenant_id": self.scope.tenant_id,
                "workspace_id": self.scope.workspace_id,
                "policy_version": decision["policy_version"],
                "authorization_ref": decision["authorization_ref"],
                "reauthenticated": True,
            }

        result = outbox.dispatch_claimed(
            item["idempotency_key"], worker_id="synthetic-worker",
            authorize=policy, adapter=adapter, now=NOW + timedelta(seconds=1),
        )
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(adapter.send_calls, 0)
        self._close(store)
        print("G134_PROCESS_SEPARATED_LOCAL_RESERVATION=DEFAULT_OUTBOX_NO_SEND")

    def test_10_competing_subprocesses_reserve_only_once(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(
                lambda request: self._reserve(ref=request),
                ("concurrent-request-a", "concurrent-request-b"),
            ))
        self.assertCountEqual(results, [ADMITTED, UNCERTAIN])
        with closing(sqlite3.connect(self.custody_db)) as db:
            self.assertEqual(db.execute("SELECT sequence FROM custody_state WHERE slot=1").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0], 1)
        print("G134_CONCURRENT_PROCESS_RESERVATION=ONE_LOCAL_WINNER_NO_PROVIDER")

    def test_11_untrusted_input_is_rejected_before_any_sqlite_write(self):
        self.assertEqual(self._reserve(event="../bad-path"), BAD_INPUT)
        self.assertEqual(self._reserve(digest="forged"), BAD_INPUT)
        with closing(sqlite3.connect(self.custody_db)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
