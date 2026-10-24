"""A190 G35 — BEGIN acknowledgement ambiguity and abrupt child-process exit.

Real SQLite files + faulting wrappers; os._exit only in DISPOSABLE CHILD
processes. NO provider, Worker, network, customer records or live AION.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from aion_chat.models import Message, Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from atlasquant_aion_execution_outbox import ExecutionOutbox

SCOPE = Scope("g35-owner", "g35-tenant", "g35-workspace")
NOW = datetime(2026, 10, 24, 16, tzinfo=timezone.utc)
WORKER = "g35-synthetic-worker"


class BeginFaultProxy:
    def __init__(self, real, *, after, fail_close=False):
        self.real = real
        self.after = after
        self.fail_close = fail_close
        self.begins = 0
        self.rollbacks = 0
        self.closes = 0

    def execute(self, sql, *args, **kwargs):
        if sql == "BEGIN IMMEDIATE":
            self.begins += 1
            if self.after:
                self.real.execute(sql, *args, **kwargs)
            raise OSError("G35_BEGIN_ACK_UNKNOWN")
        return self.real.execute(sql, *args, **kwargs)

    def rollback(self):
        self.rollbacks += 1
        return self.real.rollback()

    def close(self):
        self.closes += 1
        self.real.close()
        if self.fail_close:
            raise OSError("G35_CLOSE_SECONDARY_FAULT")

    def __getattr__(self, item):
        return getattr(self.real, item)


class TrapAdapter:
    def __init__(self):
        self.lookups = 0

    @property
    def send(self):
        self.lookups += 1
        raise AssertionError("G35_PROVIDER_LOOKUP_FORBIDDEN")


CHILD_SCRIPT = r"""
import os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
scope=Scope("g35-owner","g35-tenant","g35-workspace")
now=datetime(2026,10,24,16,tzinfo=timezone.utc)
store=SQLiteChatStore(Path(sys.argv[1]))
outbox=ExecutionOutbox(store,scope)
staged=outbox.enqueue(intent_ref="g35-process-intent", action="synthetic_no_effect",
    payload={"amount_minor":1000}, aggregate_key="g35-process-aggregate",
    policy_version="p1",authorization_ref="a1",
    created_at=now,valid_until=now+timedelta(minutes=5))
mode=sys.argv[2]
if mode=="post-stage":
    os._exit(91)
db=store.db
db.execute("BEGIN IMMEDIATE")
db.execute("UPDATE action_outbox SET state='UNCERTAIN',last_error='G35_CRASH_SYNTHETIC' WHERE idempotency_key=?",
    (staged["idempotency_key"],))
if mode=="after-commit":
    db.commit()
os._exit(91)
"""


class G35BeginAndProcessCrash(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aion-g35-")
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "synthetic.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(self.store, SCOPE)
        self.raw = self.store.db

    def stage(self):
        return self.outbox.enqueue(
            intent_ref="g35-intent", action="synthetic_no_effect",
            payload={"amount_minor":1000}, aggregate_key="g35-aggregate",
            policy_version="p1", authorization_ref="a1",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        )

    def claim(self):
        self.stage()
        return self.outbox.claim_next(WORKER, now=NOW, lease_seconds=60)

    def inject(self, after, *, fail_close=False):
        proxy = BeginFaultProxy(self.raw, after=after, fail_close=fail_close)
        self.store.db = proxy
        self.outbox.db = proxy
        return proxy

    def expect_quarantine(self, fn, *, after, close_fails=False):
        proxy = self.inject(after, fail_close=close_fails)
        with self.assertRaisesRegex(OSError, "G35_BEGIN_ACK_UNKNOWN") as caught:
            fn()
        self.assertEqual(proxy.begins, 1)
        self.assertEqual(proxy.rollbacks, 0)
        self.assertEqual(proxy.closes, 1)
        self.assertIsNone(self.store.db)
        self.assertIsNone(self.outbox.db)
        self.assertEqual(self.store.storage_health()["state"], "failed")
        self.assertTrue(any("BEGIN_OUTCOME_UNCERTAIN" in n for n in
                            getattr(caught.exception, "__notes__", [])))
        with self.assertRaises(StorageUnavailableError):
            self.store.require_healthy()
        with self.assertRaises(StorageUnavailableError):
            self.stage()
        return caught.exception

    def reopened(self):
        store = SQLiteChatStore(self.path)
        return store, ExecutionOutbox(store, SCOPE)

    def test_01_chat_create_begin_denied_before_start(self):
        proxy = BeginFaultProxy(self.raw, after=False)
        self.store.db = proxy
        with self.assertRaisesRegex(OSError, "G35_BEGIN_ACK_UNKNOWN"):
            self.store.create_conversation(SCOPE, "synthetic")
        self.assertIsNone(self.store.db)
        self.assertEqual(proxy.rollbacks, 0)
        print("G35_CHAT_BEGIN_BEFORE_GREEN=STORE_QUARANTINED")

    def test_02_chat_create_begin_started_but_ack_lost(self):
        proxy = BeginFaultProxy(self.raw, after=True)
        self.store.db = proxy
        with self.assertRaisesRegex(OSError, "G35_BEGIN_ACK_UNKNOWN"):
            self.store.create_conversation(SCOPE, "synthetic")
        self.assertIsNone(self.store.db)
        self.assertEqual(proxy.rollbacks, 0)
        reopened = SQLiteChatStore(self.path)
        try:
            self.assertEqual(len(reopened.list_conversations(SCOPE).items), 0)
        finally:
            reopened.close()
        print("G35_CHAT_BEGIN_AFTER_RED=TRANSACTION_STARTED_ACK_LOST")

    def test_03_chat_append_begin_before(self):
        convo = self.store.create_conversation(SCOPE, "test")
        proxy = BeginFaultProxy(self.raw, after=False)
        self.store.db = proxy
        with self.assertRaisesRegex(OSError, "G35_BEGIN_ACK_UNKNOWN"):
            self.store.append_message(SCOPE, Message(convo.id, "user", "synthetic"))
        self.assertIsNone(self.store.db)

    def test_04_chat_append_begin_after(self):
        convo = self.store.create_conversation(SCOPE, "test")
        proxy = BeginFaultProxy(self.raw, after=True)
        self.store.db = proxy
        with self.assertRaisesRegex(OSError, "G35_BEGIN_ACK_UNKNOWN"):
            self.store.append_message(SCOPE, Message(convo.id, "user", "synthetic"))
        self.assertIsNone(self.store.db)

    def test_05_outbox_enqueue_begin_before(self):
        self.expect_quarantine(lambda: self.stage(), after=False)
        store, outbox = self.reopened()
        try:
            self.assertEqual(outbox.list(), [])
        finally:
            store.close()

    def test_06_outbox_enqueue_begin_after(self):
        self.expect_quarantine(lambda: self.stage(), after=True)
        store, outbox = self.reopened()
        try:
            self.assertEqual(outbox.list(), [])
        finally:
            store.close()
        print("G35_OUTBOX_BEGIN_AFTER_RED=LOCK_ACQUIRED_ACK_UNKNOWN_QUARANTINE")

    def test_07_outbox_claim_begin_before(self):
        self.stage()
        self.expect_quarantine(
            lambda: self.outbox.claim_next(WORKER, now=NOW),
            after=False,
        )
        store, outbox = self.reopened()
        try:
            self.assertEqual(outbox.list()[0]["state"], "PENDING")
        finally:
            store.close()

    def test_08_outbox_claim_begin_after(self):
        self.stage()
        self.expect_quarantine(
            lambda: self.outbox.claim_next(WORKER, now=NOW),
            after=True,
        )
        store, outbox = self.reopened()
        try:
            self.assertEqual(outbox.list()[0]["state"], "PENDING")
        finally:
            store.close()

    def test_09_outbox_dispatch_begin_before(self):
        claim = self.claim()
        adapter = TrapAdapter()
        auth = lambda _: {"allowed": True, "actor_id": SCOPE.owner_id,
                          "policy_version":"p1", "authorization_ref":"a1"}
        self.expect_quarantine(lambda: self.outbox.dispatch_claimed(
            claim["idempotency_key"], worker_id=WORKER, authorize=auth,
            adapter=adapter, now=NOW + timedelta(seconds=1)), after=False)
        self.assertEqual(adapter.lookups, 0)

    def test_10_outbox_dispatch_begin_after(self):
        claim = self.claim()
        adapter = TrapAdapter()
        auth = lambda _: {"allowed": True, "actor_id": SCOPE.owner_id,
                          "policy_version":"p1", "authorization_ref":"a1"}
        self.expect_quarantine(lambda: self.outbox.dispatch_claimed(
            claim["idempotency_key"], worker_id=WORKER, authorize=auth,
            adapter=adapter, now=NOW + timedelta(seconds=1)), after=True)
        self.assertEqual(adapter.lookups, 0)

    def test_11_close_failure_does_not_unquarantine(self):
        self.expect_quarantine(lambda: self.stage(), after=True, close_fails=True)

    def test_12_no_new_outbox_from_quarantined_store(self):
        self.expect_quarantine(lambda: self.stage(), after=False)
        with self.assertRaises(StorageUnavailableError):
            ExecutionOutbox(self.store, SCOPE)

    def crash_child(self, mode):
        with tempfile.TemporaryDirectory(prefix="g35-crash-child-") as directory:
            path = Path(directory) / "child.sqlite3"
            proc = subprocess.run(
                [sys.executable, "-B", "-c", CHILD_SCRIPT, str(path), mode],
                cwd=str(Path(__file__).resolve().parents[2]),
                capture_output=True, text=True,
                timeout=20,
                check=False,
            )
            self.assertEqual(proc.returncode, 91, proc.stderr)
            store = SQLiteChatStore(path)
            try:
                outbox = ExecutionOutbox(store, SCOPE)
                rows = outbox.list()
                self.assertEqual(len(rows), 1)
                return rows[0], outbox.effect_count()
            finally:
                store.close()

    def test_13_abrupt_process_exit_before_commit_rolls_back(self):
        row, effects = self.crash_child("before-commit")
        self.assertEqual(row["state"], "PENDING")
        self.assertEqual(effects, 0)
        print("G35_CRASH_PRECOMMIT_GREEN=UNCOMMITTED_UPDATE_ROLLED_BACK")

    def test_14_abrupt_process_exit_after_commit_persists_uncertain(self):
        row, effects = self.crash_child("after-commit")
        self.assertEqual(row["state"], "UNCERTAIN")
        self.assertEqual(row["last_error"], "G35_CRASH_SYNTHETIC")
        self.assertEqual(effects, 0)
        print("G35_CRASH_POSTCOMMIT_RED=UNCERTAIN_STATE_PERSISTED_AFTER_EXIT")

    def test_15_abrupt_exit_after_stage_persists_pending(self):
        row, effects = self.crash_child("post-stage")
        self.assertEqual(row["state"], "PENDING")
        self.assertEqual(effects, 0)

    def test_16_crash_testing_not_external_custody(self):
        row, effects = self.crash_child("after-commit")
        self.assertEqual(row["state"], "UNCERTAIN")
        self.assertEqual(effects, 0)
        self.assertFalse(row["executes_action"])

    def test_17_fresh_local_store_after_begin_failure_cannot_prove_witness(self):
        self.expect_quarantine(lambda: self.stage(), after=True)
        store, outbox = self.reopened()
        try:
            self.assertEqual(store.require_healthy()["state"], "healthy")
            self.assertEqual(outbox.list(), [])
        finally:
            store.close()
        print("G35_LOCAL_REOPEN_LIMIT=NOT_INDEPENDENT_FIRST_SEND_EVIDENCE")

    def test_18_begin_fail_after_start_does_not_leave_db_locked(self):
        self.expect_quarantine(lambda: self.stage(), after=True)
        store, outbox = self.reopened()
        try:
            data = outbox.enqueue(
                intent_ref="fresh", action="synthetic_no_effect",
                payload={"amount_minor":1000}, aggregate_key="fresh-aggregate",
                policy_version="p1", authorization_ref="a1",
                created_at=NOW, valid_until=NOW + timedelta(minutes=5),
            )
            self.assertEqual(data["enqueue_state"], "ENQUEUED")
            self.assertEqual(outbox.effect_count(), 0)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
