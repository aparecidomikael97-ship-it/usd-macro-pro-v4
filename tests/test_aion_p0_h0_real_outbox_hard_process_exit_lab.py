"""AION P0 H0 negative LAB: hard process termination of REAL Outbox.

Five cases exercise SQLiteChatStore + ExecutionOutbox on disposable SQLite
files. os._exit happens in a child Python interpreter, not a mock exception.
No external adapter is called; positive admission remains a LOCAL claim.
PASS on restored snapshots reproduces the still-OPEN H0 rollback defect.
This is NOT a power-failure/independent-witness or trust-enrollment proof.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

SCOPE = Scope("h0-exit-owner", "h0-exit-tenant", "h0-exit-space")
T0 = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)
WORKER = "h0-lab-local-worker"
CHILD = r"""
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

scope = Scope("h0-exit-owner", "h0-exit-tenant", "h0-exit-space")
t0 = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)
store = SQLiteChatStore(sys.argv[1])
out = ExecutionOutbox(store, scope)
mode = sys.argv[2]
if mode == "enqueue":
    out.enqueue(
        intent_ref="one-synthetic-attempt",
        action="synthetic-no-provider",
        payload={"synthetic": True},
        aggregate_key="aggregate-h0-hard-exit",
        policy_version="lab-only",
        authorization_ref="non-authoritative-test",
        created_at=t0, valid_until=t0 + timedelta(minutes=5),
    )
    os._exit(71)
if mode in ("claim", "unknown"):
    item = out.claim_next("h0-lab-local-worker", now=t0, lease_seconds=15)
    if item is None or item["state"] != "CLAIMED":
        os._exit(91)
    if mode == "claim":
        os._exit(72)
    with store.db:
        store.db.execute(
            "UPDATE action_outbox SET state='UNCERTAIN',dispatch_started_at=? "
            "WHERE idempotency_key=?",
            (t0.isoformat(), item["idempotency_key"]),
        )
    os._exit(73)
os._exit(92)
"""


class P0RealOutboxHardProcessExitLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-h0-real-outbox-exit-")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.path = self.directory / "one.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(self.store, SCOPE)

    def enqueue(self):
        return self.outbox.enqueue(
            intent_ref="one-synthetic-attempt",
            action="synthetic-no-provider",
            payload={"synthetic": True},
            aggregate_key="aggregate-h0-hard-exit",
            policy_version="lab-only",
            authorization_ref="non-authoritative-test",
            created_at=T0, valid_until=T0 + timedelta(minutes=5),
        )

    def reopen(self, path=None):
        store = SQLiteChatStore(path or self.path)
        self.addCleanup(store.close)
        return ExecutionOutbox(store, SCOPE)

    def child(self, mode):
        proc = subprocess.run(
            [sys.executable, "-B", "-c", textwrap.dedent(CHILD),
             str(self.path), mode],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True, text=True, timeout=35, check=False,
        )
        self.assertEqual(proc.stdout, "", "os._exit child must not claim success via stdout")
        self.assertEqual(proc.stderr, "", f"hard-exit {mode}: {proc.stderr[-1700:]}")
        return proc.returncode

    def snapshot(self):
        backup = self.directory / "pre-unknown-snapshot.sqlite3"
        with closing(sqlite3.connect(str(backup))) as dest:
            self.store.db.backup(dest)
        return backup

    def test_01_hard_exit_after_durable_enqueue_is_locally_pending(self):
        self.store.close()
        self.assertEqual(self.child("enqueue"), 71)
        reopened = self.reopen()
        rows = reopened.list()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["state"], "PENDING")
        self.assertEqual(rows[0]["attempts"], 0)
        self.assertEqual(reopened.effect_count(), 0)

    def test_02_hard_exit_after_predispatch_claim_reclaims_after_lease(self):
        key = self.enqueue()["idempotency_key"]
        self.store.close()
        self.assertEqual(self.child("claim"), 72)
        reopened = self.reopen()
        self.assertEqual(reopened.get(key)["state"], "CLAIMED")
        self.assertIsNone(reopened.claim_next(WORKER, now=T0 + timedelta(seconds=5)))
        claimed = reopened.claim_next(WORKER, now=T0 + timedelta(seconds=31))
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["state"], "CLAIMED")
        self.assertEqual(claimed["idempotency_key"], key)
        self.assertEqual(claimed["attempts"], 2)
        self.assertEqual(reopened.effect_count(), 0)

    def test_03_hard_exit_after_uncertain_mark_never_reclaims_normally(self):
        key = self.enqueue()["idempotency_key"]
        self.store.close()
        self.assertEqual(self.child("unknown"), 73)
        reopened = self.reopen()
        self.assertEqual(reopened.get(key)["state"], "UNCERTAIN")
        self.assertIsNone(reopened.claim_next(WORKER, now=T0 + timedelta(seconds=31)))
        self.assertEqual(reopened.effect_count(), 0)

    def test_04_hard_exit_then_restore_preunknown_reclaims_OPEN_H0(self):
        key = self.enqueue()["idempotency_key"]
        backup = self.snapshot()
        self.store.close()
        self.assertEqual(self.child("unknown"), 73)
        current = self.reopen()
        self.assertEqual(current.get(key)["state"], "UNCERTAIN")
        self.assertEqual(current.effect_count(), 0)
        restored = self.reopen(backup)
        # Intentionally prove OPEN gap: independently reading the pre-UNKNOWN
        # SQLite cannot reveal that a later first attempt became UNCERTAIN.
        replay = restored.claim_next(WORKER, now=T0)
        self.assertEqual(replay["state"], "CLAIMED")
        self.assertEqual(replay["idempotency_key"], key)
        self.assertEqual(replay["attempts"], 1)
        self.assertEqual(restored.effect_count(), 0)

    def test_05_hard_exit_pre_dispatch_still_denies_any_provider_adapter(self):
        key = self.enqueue()["idempotency_key"]
        self.store.close()
        self.assertEqual(self.child("claim"), 72)
        reopened = self.reopen()

        class Hostile:
            def __getattribute__(self, name):
                raise AssertionError("NO_EXTERNAL_PROVIDER_ADAPTER_MAY_BE_TOUCHED")

        def pretend_authorized(_):
            # Local authorization checks intentionally run twice before the
            # unconditional external producer hardstop. These fixture claims
            # are untrusted and MUST NOT grant real producer enrollment.
            return {
                "allowed": True,
                "actor_id": SCOPE.owner_id,
                "tenant_id": SCOPE.tenant_id,
                "workspace_id": SCOPE.workspace_id,
                "policy_version": "lab-only",
                "authorization_ref": "non-authoritative-test",
            }

        with self.assertRaisesRegex(
                PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED"):
            reopened.dispatch_claimed(
                key, worker_id=WORKER, authorize=pretend_authorized,
                adapter=Hostile(), now=T0,
            )
        self.assertEqual(reopened.get(key)["state"], "BLOCKED_PRODUCER")
        self.assertEqual(reopened.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
