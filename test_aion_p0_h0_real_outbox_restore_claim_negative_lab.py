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
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

# This is a separate interpreter with no provider, network code or worker.
# It exercises REAL SQLiteChatStore/ExecutionOutbox with fixture files.
_CHILD_H0_PROBE = r"""
import json
import sys
from datetime import datetime, timedelta, timezone
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

scope = Scope("synthetic-h0-owner", "synthetic-h0-tenant", "synthetic-h0-space")
t0 = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)
store = SQLiteChatStore(sys.argv[1])
try:
    outbox = ExecutionOutbox(store, scope)
    mode = sys.argv[2]
    result = {"mode": mode, "effects": 0, "claim": None, "enqueue": None}
    if mode == "recreate":
        r = outbox.enqueue(
            intent_ref="synthetic-once-intent",
            action="synthetic-no-provider",
            payload={"synthetic": True},
            aggregate_key="synthetic-aggregate",
            authorization_ref="non-authoritative-lab-ticket",
            policy_version="lab-only",
            created_at=t0,
            valid_until=t0 + timedelta(minutes=5),
        )
        result["enqueue"] = r["enqueue_state"]
    if mode not in ("claim", "recreate", "uncertain", "deny"):
        raise RuntimeError("unsupported H0 isolated probe")
    claim = outbox.claim_next("lab-only-worker", now=t0)
    result["claim"] = None if claim is None else {
        "state": claim["state"], "key": claim["idempotency_key"],
        "attempts": claim["attempts"],
    }
    if mode == "deny":
        class Hostile:
            def __getattribute__(self, name):
                raise AssertionError("H0 child MUST NOT inspect provider adapter")
        def authorize(_decision):
            return {
                "allowed": True, "actor_id": scope.owner_id,
                "tenant_id": scope.tenant_id, "workspace_id": scope.workspace_id,
                "policy_version": "lab-only",
                "authorization_ref": "non-authoritative-lab-ticket",
            }
        try:
            outbox.dispatch_claimed(
                claim["idempotency_key"], worker_id="lab-only-worker",
                authorize=authorize, adapter=Hostile(), now=t0,
            )
            raise AssertionError("effect admission MUST fail")
        except PermissionError as exc:
            result["producer_denial"] = str(exc)
        result["after_denial_state"] = outbox.get(claim["idempotency_key"])["state"]
    result["effects"] = outbox.effect_count()
    print("AION_H0_LAB_RESULT=" + json.dumps(result, sort_keys=True))
finally:
    store.close()
"""

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

    def run_in_fresh_process(self, database_path: Path, mode: str) -> dict:
        process = subprocess.run(
            [sys.executable, "-B", "-c", textwrap.dedent(_CHILD_H0_PROBE),
             str(database_path), mode],
            cwd=str(Path(__file__).resolve().parent),
            text=True, capture_output=True, timeout=40, check=False,
        )
        self.assertEqual(process.returncode, 0, (
            f"isolated H0 child failed; stdout={process.stdout[-1500:]!r} "
            f"stderr={process.stderr[-1500:]!r}"
        ))
        records = [line.split("=", 1)[1] for line in process.stdout.splitlines()
                   if line.startswith("AION_H0_LAB_RESULT=")]
        self.assertEqual(len(records), 1, "child must produce one bounded H0 probe")
        return json.loads(records[0])

    def test_05_fresh_interpreter_without_rollback_still_denies_reclaim(self):
        key = self.enqueue()["idempotency_key"]
        self.mark_unknown(key)
        # A new interpreter replaces the runtime; it is not a fresh SQLite
        # connection within the same process.
        self.store.close()
        result = self.run_in_fresh_process(self.path, "uncertain")
        self.assertIsNone(result["claim"])
        self.assertEqual(result["effects"], 0)
        with closing(sqlite3.connect(str(self.path))) as db:
            self.assertEqual(db.execute(
                "SELECT state FROM action_outbox WHERE idempotency_key=?",
                (key,),
            ).fetchone()[0], "UNCERTAIN")

    def test_06_fresh_interpreter_restored_pending_reclaims__OPEN_GAP(self):
        key = self.enqueue()["idempotency_key"]
        backed_up = self.snapshot("p0-h0-pre-unknown-process.sqlite3")
        self.mark_unknown(key)
        self.store.close()
        # The historical source now lives in a SEPARATE isolated SQLite file.
        result = self.run_in_fresh_process(backed_up, "claim")
        self.assertEqual(result["claim"]["state"], "CLAIMED")
        self.assertEqual(result["claim"]["key"], key)
        self.assertEqual(result["claim"]["attempts"], 1)
        self.assertEqual(result["effects"], 0)
        # Parent's latest history still shows UNCERTAIN, proving the child
        # cannot discover that fact from its restored copy.
        with closing(sqlite3.connect(str(self.path))) as db:
            self.assertEqual(db.execute(
                "SELECT state FROM action_outbox WHERE idempotency_key=?",
                (key,),
            ).fetchone()[0], "UNCERTAIN")

    def test_07_fresh_interpreter_restored_before_enqueue_recreates__OPEN_GAP(self):
        no_attempt = self.snapshot("p0-h0-before-enqueue-process.sqlite3")
        key = self.enqueue()["idempotency_key"]
        self.mark_unknown(key)
        self.store.close()
        result = self.run_in_fresh_process(no_attempt, "recreate")
        self.assertEqual(result["enqueue"], "ENQUEUED")
        self.assertEqual(result["claim"]["state"], "CLAIMED")
        self.assertEqual(result["claim"]["key"], key)
        self.assertEqual(result["effects"], 0)

    def test_08_fresh_interpreter_rollback_still_denies_adapter_access(self):
        key = self.enqueue()["idempotency_key"]
        backed_up = self.snapshot("p0-h0-untrusted-adapter-process.sqlite3")
        self.mark_unknown(key)
        self.store.close()
        result = self.run_in_fresh_process(backed_up, "deny")
        self.assertEqual(result["claim"]["key"], key)
        self.assertEqual(result["producer_denial"], "INDEPENDENT_PRODUCER_NOT_ENROLLED")
        self.assertEqual(result["after_denial_state"], "BLOCKED_PRODUCER")
        self.assertEqual(result["effects"], 0)

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
