"""P0 H0: actual Outbox claim after local SQLite rollback — NEGATIVE LAB finding.

This suite is deliberately a characterization of a remaining design gap:
old SQLite snapshots can make a previously UNCERTAIN or even entirely lost
first attempt locally admissible again. PASS means the counterexample was
reproduced, NOT the root fixed, or an external effect permitted.

All databases and snapshots are TemporaryDirectory fixtures; no provider,
network calls, Worker, external credentials, or real effects.
"""
from __future__ import annotations

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

SCOPE = Scope("synthetic-h0-owner", "synthetic-h0-tenant", "synthetic-h0-space")
T0 = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)
WORKER = "lab-only-worker"


class H0RealOutboxRestoredHistoryLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-h0-restore-negative-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "execution.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(self.store, SCOPE)

    def enqueue(self):
        return self.outbox.enqueue(
            intent_ref="synthetic-once-intent",
            action="synthetic-no-provider",
            payload={"synthetic": True},
            aggregate_key="synthetic-aggregate",
            authorization_ref="non-authoritative-lab-ticket",
            policy_version="lab-only",
            created_at=T0,
            valid_until=T0 + timedelta(minutes=5),
        )

    def snapshot(self, name):
        backup = self.root / name
        with closing(sqlite3.connect(str(backup))) as destination:
            self.store.db.backup(destination)
        return backup

    def mark_unknown(self, key):
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='UNCERTAIN',dispatch_started_at=? "
                "WHERE idempotency_key=?",
                (T0.isoformat(), key),
            )
        self.assertEqual(self.outbox.get(key)["state"], "UNCERTAIN")

    def restore(self, backup):
        self.store.close()
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(self.path) + suffix)
            if sidecar.exists():
                sidecar.unlink()
        shutil.copyfile(backup, self.path)
        reopened = SQLiteChatStore(self.path)
        self.addCleanup(reopened.close)
        return ExecutionOutbox(reopened, SCOPE)

    def test_01_uncertain_survives_normal_reopen_and_cannot_reclaim(self):
        key = self.enqueue()["idempotency_key"]
        self.mark_unknown(key)
        self.store.close()
        reopened = SQLiteChatStore(self.path)
        self.addCleanup(reopened.close)
        outbox = ExecutionOutbox(reopened, SCOPE)
        self.assertEqual(outbox.get(key)["state"], "UNCERTAIN")
        self.assertIsNone(outbox.claim_next(WORKER, now=T0))
        self.assertEqual(outbox.effect_count(), 0)

    def test_02_rollback_to_pending_reopens_local_claim__THIS_IS_A_GAP(self):
        key = self.enqueue()["idempotency_key"]
        old_copy = self.snapshot("before-unknown.sqlite3")
        self.mark_unknown(key)
        outbox = self.restore(old_copy)
        # The actual implementation can claim because the local record is
        # indistinguishable from a real first PENDING action after rollback.
        claimed = outbox.claim_next(WORKER, now=T0)
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["state"], "CLAIMED")
        self.assertEqual(claimed["idempotency_key"], key)
        self.assertEqual(claimed["attempts"], 1)
        self.assertEqual(outbox.effect_count(), 0)

    def test_03_rollback_before_first_enqueue_recreates_same_claim__GAP(self):
        earlier = self.snapshot("before-first-attempt.sqlite3")
        key = self.enqueue()["idempotency_key"]
        self.mark_unknown(key)
        outbox = self.restore(earlier)
        # A lost first attempt is not observable inside its own restored DB.
        recreated = outbox.enqueue(
            intent_ref="synthetic-once-intent",
            action="synthetic-no-provider",
            payload={"synthetic": True},
            aggregate_key="synthetic-aggregate",
            authorization_ref="non-authoritative-lab-ticket",
            policy_version="lab-only",
            created_at=T0,
            valid_until=T0 + timedelta(minutes=5),
        )
        self.assertEqual(recreated["idempotency_key"], key)
        self.assertEqual(recreated["enqueue_state"], "ENQUEUED")
        self.assertEqual(outbox.claim_next(WORKER, now=T0)["state"], "CLAIMED")
        self.assertEqual(outbox.effect_count(), 0)

    def test_04_restored_claim_still_denies_unenrolled_external_producer(self):
        key = self.enqueue()["idempotency_key"]
        old_copy = self.snapshot("before-unknown.sqlite3")
        self.mark_unknown(key)
        outbox = self.restore(old_copy)
        self.assertEqual(outbox.claim_next(WORKER, now=T0)["state"], "CLAIMED")

        class HostileAdapter:
            def __getattribute__(self, attr):
                raise AssertionError("No provider adapter may be inspected in H0 LAB")

        def authorize(decision):
            return {
                "allowed": True,
                "actor_id": SCOPE.owner_id,
                "tenant_id": SCOPE.tenant_id,
                "workspace_id": SCOPE.workspace_id,
                "policy_version": "lab-only",
                "authorization_ref": "non-authoritative-lab-ticket",
            }

        with self.assertRaisesRegex(PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED"):
            outbox.dispatch_claimed(
                key, worker_id=WORKER, authorize=authorize,
                adapter=HostileAdapter(), now=T0,
            )
        self.assertEqual(outbox.get(key)["state"], "BLOCKED_PRODUCER")
        self.assertEqual(outbox.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
