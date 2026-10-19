"""P0 REAL SQLite first-attempt restart/restore adversarial tests on A118 original.

Uses original ExecutionOutbox and SQLiteChatStore (unmodified); subprocess
os._exit emulates abrupt *process* death, NOT power-loss or disk-flush proof.
Direct test-only SQL writes synthetic UNCERTAIN/SENT states: the original
productive dispatcher still denies before any adapter or external effect.
No provider, network, Worker, real credentials or live send.

Crucial: a snapshot restore on the same machine resets local Outbox history.
This test records that REAL GAP without declaring an operational bypass:
original send remains hard-denied and the independent antirollback witness
is still missing.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 19, 19, 30, tzinfo=timezone.utc)
OWNER = Scope("p0-lab-owner", "p0-lab-tenant", "p0-lab-workspace")
CRASH_HELPER = r"""
import json, os, sqlite3, sys
path, state, time_marker, commit = sys.argv[1:]
db = sqlite3.connect(path, isolation_level=None, timeout=10)
db.execute("PRAGMA synchronous=FULL")
db.execute("PRAGMA foreign_keys=ON")
db.execute("BEGIN IMMEDIATE")
c = db.execute(
    "UPDATE action_outbox SET state=?,dispatch_started_at=? WHERE state='CLAIMED'",
    (state, time_marker),
)
assert c.rowcount == 1, c.rowcount
if commit == "yes":
    db.execute("COMMIT")
os._exit(73)
"""


class FirstAttemptSQLiteCrashLabTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="aion-p0-first-attempt-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "outbox.sqlite3"
        store, outbox = self.open_outbox()
        self.key = outbox.enqueue(
            intent_ref="first-attempt-fixture-1",
            action="synthetic_stage_no_provider",
            payload={"note": "test-only-no-external-effect"},
            aggregate_key="first-attempt-sequence",
            policy_version="fixture-policy",
            authorization_ref="fixture-authority",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )["idempotency_key"]
        self.assertEqual(outbox.get(self.key)["state"], "PENDING")
        store.close()

    def open_outbox(self, scope=OWNER):
        store = SQLiteChatStore(self.path)
        outbox = ExecutionOutbox(store, scope)
        return store, outbox

    def claim(self):
        store, outbox = self.open_outbox()
        row = outbox.claim_next("lab-worker", now=NOW+timedelta(seconds=1), lease_seconds=45)
        self.assertIsNotNone(row)
        self.assertEqual(row["state"], "CLAIMED")
        store.close()
        return row

    def direct_fixture_state(self, state, dispatch_marker=""):
        # TEST-ONLY raw fixture, NEVER import as an authorization helper.
        with sqlite3.connect(str(self.path)) as db:
            c = db.execute(
                "UPDATE action_outbox SET state=?,dispatch_started_at=? WHERE idempotency_key=?",
                (state, dispatch_marker, self.key),
            )
            self.assertEqual(c.rowcount, 1)

    def crash_after_sql(self, *, committed, state="UNCERTAIN"):
        proc = subprocess.run(
            [sys.executable, "-B", "-c", CRASH_HELPER,
             str(self.path), state, NOW.isoformat(), "yes" if committed else "no"],
            capture_output=True, text=True, timeout=20, check=False,
        )
        self.assertEqual(proc.returncode, 73, proc.stderr)

    def assert_not_reclaimable(self):
        store, outbox = self.open_outbox()
        before = outbox.get(self.key)
        self.assertEqual(outbox.release_expired_claims(now=NOW+timedelta(minutes=2)), 0)
        self.assertIsNone(outbox.claim_next("second-worker", now=NOW+timedelta(minutes=2)))
        self.assertEqual(outbox.get(self.key), before)
        self.assertEqual(outbox.effect_count(), 0)
        store.close()

    def test_01_original_enqueue_writes_intent_and_decision_durably(self):
        store, outbox = self.open_outbox()
        row = outbox.get(self.key)
        self.assertEqual(row["state"], "PENDING")
        self.assertEqual(row["decision"]["intent_ref"], "first-attempt-fixture-1")
        self.assertEqual(row["decision"]["idempotency_key"], self.key)
        self.assertEqual(outbox.effect_count(), 0)
        store.close()

    def test_02_crash_after_committed_uncertain_survives_reopen_and_expiry(self):
        self.claim()
        self.crash_after_sql(committed=True)
        store, outbox = self.open_outbox()
        observed = outbox.get(self.key)
        self.assertEqual(observed["state"], "UNCERTAIN")
        self.assertTrue(observed["dispatch_started_at"])
        store.close()
        self.assert_not_reclaimable()

    def test_03_crash_before_committing_uncertain_rolls_back_to_pre_send_claim(self):
        self.claim()
        self.crash_after_sql(committed=False)
        store, outbox = self.open_outbox()
        self.assertEqual(outbox.get(self.key)["state"], "CLAIMED")
        self.assertEqual(outbox.get(self.key)["dispatch_started_at"], "")
        self.assertEqual(outbox.release_expired_claims(now=NOW+timedelta(minutes=2)), 1)
        self.assertEqual(outbox.get(self.key)["state"], "RETRY")
        # No provider had even been inspected. This is only pre-dispatch lease
        # recycling, never proof that a previous external attempt did not run.
        self.assertEqual(outbox.effect_count(), 0)
        store.close()

    def test_04_committed_sent_never_recycled_after_restart(self):
        self.claim()
        self.crash_after_sql(committed=True, state="SENT")
        self.assert_not_reclaimable()
        store, outbox = self.open_outbox()
        self.assertEqual(outbox.get(self.key)["state"], "SENT")
        store.close()

    def test_05_claim_with_possible_effect_marker_never_recycled(self):
        self.claim()
        self.direct_fixture_state("CLAIMED", NOW.isoformat())
        self.assert_not_reclaimable()

    def test_06_lease_expiry_without_dispatch_marker_can_recycle_pre_send_only(self):
        self.claim()
        store, outbox = self.open_outbox()
        self.assertEqual(outbox.release_expired_claims(now=NOW+timedelta(minutes=2)), 1)
        self.assertEqual(outbox.get(self.key)["state"], "RETRY")
        self.assertEqual(outbox.effect_count(), 0)
        store.close()

    def test_07_reconciliation_never_inspects_unenrolled_adapter(self):
        self.claim()
        self.direct_fixture_state("UNCERTAIN", NOW.isoformat())
        class Trap:
            @property
            def reconcile(self):
                raise AssertionError("adapter property accessed despite hard stop")
        store, outbox = self.open_outbox()
        before = outbox.get(self.key)
        with self.assertRaisesRegex(PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED"):
            outbox.reconcile(self.key, adapter=Trap(), authorize=lambda _: {"allowed": True},
                             now=NOW+timedelta(seconds=20))
        self.assertEqual(outbox.get(self.key), before)
        store.close()

    def test_08_foreign_scope_cannot_read_first_attempt_after_reopen(self):
        other = Scope("other-owner", "p0-lab-tenant", "p0-lab-workspace")
        store, outbox = self.open_outbox(other)
        with self.assertRaises(LookupError):
            outbox.get(self.key)
        self.assertIsNone(outbox.claim_next("other-worker", now=NOW+timedelta(seconds=2)))
        store.close()

    def test_09_restoring_older_sqlite_snapshot_erases_unknown_without_external_witness(self):
        # This is the actual LOCAL-ONLY antirollback gap. Back up *before*
        # the uncertain attempt, then restore the old DB after recording it.
        # There is no provider and no real effect, so this is NOT a live bypass.
        snapshot = Path(self.directory.name) / "before-attempt.sqlite3"
        src = sqlite3.connect(str(self.path))
        dst = sqlite3.connect(str(snapshot))
        src.backup(dst)
        dst.close()
        src.close()
        self.claim()
        self.crash_after_sql(committed=True)
        store, outbox = self.open_outbox()
        self.assertEqual(outbox.get(self.key)["state"], "UNCERTAIN")
        store.close()
        for suffix in ("-wal", "-shm"):
            candidate = Path(str(self.path) + suffix)
            if candidate.exists():
                candidate.unlink()
        shutil.copyfile(snapshot, self.path)  # test-only simulated restore
        store, outbox = self.open_outbox()
        self.assertEqual(outbox.get(self.key)["state"], "PENDING")
        recycled = outbox.claim_next("restored-worker", now=NOW+timedelta(seconds=2))
        self.assertIsNotNone(recycled)
        self.assertEqual(recycled["state"], "CLAIMED")
        self.assertEqual(recycled["attempts"], 1)
        # No independent epoch/high-water exists in this original local DB.
        # Original A118 sends are still BLOCKED_PRODUCER; no adapter used.
        store.close()

    def test_10_original_p0_unenrolled_sender_denies_before_adapter_property(self):
        store, outbox = self.open_outbox()
        row = outbox.claim_next("worker-p0", now=NOW+timedelta(seconds=1), lease_seconds=45)
        self.assertEqual(row["state"], "CLAIMED")
        class Trap:
            @property
            def send(self):
                raise AssertionError("send property invoked")
        def policy(_):
            return {
                "allowed": True,
                "actor_id": OWNER.owner_id,
                "tenant_id": OWNER.tenant_id,
                "workspace_id": OWNER.workspace_id,
                "policy_version": "fixture-policy",
                "authorization_ref": "fixture-authority",
            }
        before_count = outbox.effect_count()
        with self.assertRaisesRegex(PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED"):
            outbox.dispatch_claimed(self.key, worker_id="worker-p0", authorize=policy,
                                   adapter=Trap(), now=NOW+timedelta(seconds=2))
        self.assertEqual(outbox.get(self.key)["state"], "BLOCKED_PRODUCER")
        self.assertEqual(outbox.effect_count(), before_count)
        store.close()
