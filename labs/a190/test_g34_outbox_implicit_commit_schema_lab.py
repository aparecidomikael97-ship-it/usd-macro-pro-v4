"""G34: real Outbox implicit transaction -> atomic explicit transaction LAB.

Fault proxy throws before physical COMMIT or AFTER a successful COMMIT, using
real local SQLite and synthetic actors; never dispatch to provider.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from atlasquant_aion_execution_outbox import ExecutionOutbox

SCOPE = Scope("g34-owner", "g34-tenant", "g34-workspace")
NOW = datetime(2026, 10, 24, 16, tzinfo=timezone.utc)
WORKER = "g34-synthetic-worker"


class CommitFault:
    def __init__(self, real, *, after=False, fail_at=1, ddl_fault=""):
        self.real, self.after, self.fail_at = real, after, fail_at
        self.ddl_fault = ddl_fault
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0

    def execute(self, sql, *args, **kwargs):
        if self.ddl_fault and self.ddl_fault in sql:
            raise RuntimeError("G34_SCHEMA_DDL_INJECTED_FAILURE")
        return self.real.execute(sql, *args, **kwargs)

    def commit(self):
        self.commits += 1
        if self.commits != self.fail_at:
            return self.real.commit()
        if self.after:
            self.real.commit()
        raise OSError("G34_IMPLICIT_COMMIT_ACK_UNKNOWN")

    def rollback(self):
        self.rollbacks += 1
        return self.real.rollback()

    def close(self):
        self.closes += 1
        return self.real.close()

    def __getattr__(self, name):
        return getattr(self.real, name)


class TrapAdapter:
    def __init__(self):
        self.lookups = 0

    @property
    def send(self):
        self.lookups += 1
        raise AssertionError("G34_PROVIDER_ACCESS_UNEXPECTED")


class G34ImplicitTransactions(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aion-g34-")
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "chat.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(self.store, SCOPE)
        self.raw = self.store.db
        self.adapter = TrapAdapter()

    def stage(self, *, intent="g34-intent"):
        return self.outbox.enqueue(
            intent_ref=intent,
            action="synthetic_no_provider",
            payload={"amount_minor": 1000},
            aggregate_key="g34-aggregate",
            policy_version="p1",
            authorization_ref="a1",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=10),
        )

    def claim(self):
        staged = self.stage()
        claimed = self.outbox.claim_next(WORKER, now=NOW, lease_seconds=60)
        self.assertEqual(staged["idempotency_key"], claimed["idempotency_key"])
        return claimed

    def auth(self, claimed, *, allowed=True, policy="p1"):
        return {
            "allowed": allowed,
            "actor_id": SCOPE.owner_id,
            "tenant_id": SCOPE.tenant_id,
            "workspace_id": SCOPE.workspace_id,
            "policy_version": policy,
            "authorization_ref": "a1",
        }

    def dispatch(self, claimed, auth=None):
        return self.outbox.dispatch_claimed(
            claimed["idempotency_key"],
            worker_id=WORKER,
            authorize=lambda _: self.auth(claimed) if auth is None else auth,
            adapter=self.adapter,
            now=NOW + timedelta(seconds=1),
        )

    def fault(self, *, after, fail_at=1):
        proxy = CommitFault(self.raw, after=after, fail_at=fail_at)
        self.outbox.db = self.store.db = proxy
        return proxy

    def check_uncertain_fault(self, fn, *, after, fail_at=1):
        proxy = self.fault(after=after, fail_at=fail_at)
        with self.assertRaisesRegex(
            OSError, "G34_IMPLICIT_COMMIT_ACK_UNKNOWN"
        ) as caught:
            fn()
        self.assertEqual(proxy.commits, fail_at)
        self.assertEqual(proxy.rollbacks, 0)
        self.assertEqual(proxy.closes, 1)
        self.assertIsNone(self.store.db)
        self.assertIsNone(self.outbox.db)
        self.assertEqual(self.store.storage_health()["state"], "failed")
        with self.assertRaises(StorageUnavailableError):
            self.store.require_healthy()
        with self.assertRaises(StorageUnavailableError):
            self.outbox.enqueue(
                intent_ref="denied", action="synthetic", payload={},
                aggregate_key="denied", policy_version="p1",
                authorization_ref="a1", created_at=NOW,
                valid_until=NOW + timedelta(minutes=5),
            )
        self.assertTrue(any(
            "COMMIT_OUTCOME_UNCERTAIN" in note
            for note in getattr(caught.exception, "__notes__", [])
        ))
        return proxy

    def disk_outbox(self):
        store = SQLiteChatStore(self.path)
        outbox = ExecutionOutbox(store, SCOPE)
        return store, outbox

    def test_01_normal_denied_authority_never_reaches_adapter(self):
        claimed = self.claim()
        result = self.dispatch(claimed, auth=self.auth(claimed, allowed=False))
        self.assertEqual(result["state"], "REVOKED")
        self.assertEqual(self.adapter.lookups, 0)

    def test_02_normal_valid_authority_still_needs_witness(self):
        claimed = self.claim()
        result = self.dispatch(claimed)
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(self.adapter.lookups, 0)

    def test_03_implicit_block_precommit_fault_leaves_claimed(self):
        claimed = self.claim()
        self.check_uncertain_fault(
            lambda: self.dispatch(claimed, auth=self.auth(claimed, allowed=False)),
            after=False,
        )
        store, outbox = self.disk_outbox()
        try:
            self.assertEqual(outbox.get(claimed["idempotency_key"])["state"], "CLAIMED")
        finally:
            store.close()
        print("G34_BLOCK_PRECOMMIT_GREEN=DENIAL_NOT_PERSISTED_STORE_QUARANTINED")

    def test_04_implicit_block_postcommit_fault_persists_revoked(self):
        claimed = self.claim()
        self.check_uncertain_fault(
            lambda: self.dispatch(claimed, auth=self.auth(claimed, allowed=False)),
            after=True,
        )
        store, outbox = self.disk_outbox()
        try:
            self.assertEqual(outbox.get(claimed["idempotency_key"])["state"], "REVOKED")
        finally:
            store.close()
        print("G34_BLOCK_POSTCOMMIT_RED=REVOKED_PERSISTED_DESPITE_EXCEPTION")

    def test_05_witness_reservation_precommit_fault_keeps_claimed(self):
        claimed = self.claim()
        self.check_uncertain_fault(lambda: self.dispatch(claimed), after=False)
        store, outbox = self.disk_outbox()
        try:
            self.assertEqual(outbox.get(claimed["idempotency_key"])["state"], "CLAIMED")
        finally:
            store.close()
        self.assertEqual(self.adapter.lookups, 0)

    def test_06_witness_reservation_postcommit_fault_persists_uncertain(self):
        claimed = self.claim()
        self.check_uncertain_fault(lambda: self.dispatch(claimed), after=True)
        store, outbox = self.disk_outbox()
        try:
            record = outbox.get(claimed["idempotency_key"])
            self.assertEqual(record["state"], "UNCERTAIN")
            self.assertEqual(record["last_error"], "FIRST_ATTEMPT_WITNESS_PENDING")
        finally:
            store.close()
        self.assertEqual(self.adapter.lookups, 0)
        print("G34_PRE_WITNESS_POSTCOMMIT_RED=UNCERTAIN_PERSISTED_ACK_UNKNOWN")

    def test_07_second_witness_transition_precommit_retains_pending_marker(self):
        claimed = self.claim()
        self.check_uncertain_fault(lambda: self.dispatch(claimed), after=False, fail_at=2)
        store, outbox = self.disk_outbox()
        try:
            record = outbox.get(claimed["idempotency_key"])
            self.assertEqual(record["state"], "UNCERTAIN")
            self.assertEqual(record["last_error"], "FIRST_ATTEMPT_WITNESS_PENDING")
        finally:
            store.close()
        self.assertEqual(self.adapter.lookups, 0)

    def test_08_second_witness_transition_postcommit_updates_no_send_marker(self):
        claimed = self.claim()
        self.check_uncertain_fault(lambda: self.dispatch(claimed), after=True, fail_at=2)
        store, outbox = self.disk_outbox()
        try:
            record = outbox.get(claimed["idempotency_key"])
            self.assertEqual(record["state"], "UNCERTAIN")
            self.assertEqual(record["last_error"], "FIRST_ATTEMPT_WITNESS_UNVERIFIED_NO_SEND")
        finally:
            store.close()
        self.assertEqual(self.adapter.lookups, 0)
        print("G34_NO_SEND_POSTCOMMIT_RED=FINAL_UNCERTAIN_PERSISTED_ACK_UNKNOWN")

    def test_09_no_auto_resend_after_postcommit_reopen(self):
        claimed = self.claim()
        self.check_uncertain_fault(lambda: self.dispatch(claimed), after=True)
        store, outbox = self.disk_outbox()
        try:
            self.assertIsNone(outbox.claim_next(WORKER, now=NOW + timedelta(minutes=2)))
            self.assertEqual(outbox.get(claimed["idempotency_key"])["state"], "UNCERTAIN")
            self.assertEqual(self.adapter.lookups, 0)
        finally:
            store.close()
        print("G34_POSTCOMMIT_REOPEN_GREEN=UNCERTAIN_NOT_RECLAIMED")

    def test_10_schema_partial_ddl_error_rolls_back_all_action_tables(self):
        with tempfile.TemporaryDirectory(prefix="aion-g34-schema-") as path:
            dbpath = Path(path) / "schema.sqlite3"
            store = SQLiteChatStore(dbpath)
            try:
                real = store.db
                proxy = CommitFault(real, ddl_fault="CREATE TABLE IF NOT EXISTS action_effects")
                store.db = proxy
                with self.assertRaisesRegex(RuntimeError, "G34_SCHEMA_DDL_INJECTED_FAILURE"):
                    ExecutionOutbox(store, SCOPE)
                self.assertEqual(proxy.rollbacks, 1)
                self.assertEqual(proxy.commits, 0)
                self.assertIs(store.db, proxy)
                store.db = real
                names = [r[0] for r in real.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name LIKE 'action_%'"
                ).fetchall()]
                self.assertEqual(names, [])
                print("G34_ATOMIC_DDL_GREEN=NO_PARTIAL_ACTION_SCHEMA_AFTER_ERROR")
            finally:
                store.close()

    def test_11_schema_postcommit_ack_loss_is_quarantined(self):
        with tempfile.TemporaryDirectory(prefix="aion-g34-schema-") as path:
            dbpath = Path(path) / "schema.sqlite3"
            store = SQLiteChatStore(dbpath)
            try:
                proxy = CommitFault(store.db, after=True)
                store.db = proxy
                with self.assertRaisesRegex(OSError, "G34_IMPLICIT_COMMIT_ACK_UNKNOWN"):
                    ExecutionOutbox(store, SCOPE)
                self.assertEqual(proxy.rollbacks, 0)
                self.assertIsNone(store.db)
                raw = sqlite3.connect(dbpath)
                try:
                    count = raw.execute(
                        "SELECT COUNT(*) FROM sqlite_master "
                        "WHERE type='table' AND name LIKE 'action_%'"
                    ).fetchone()[0]
                    self.assertEqual(count, 3)
                finally:
                    raw.close()
                print("G34_SCHEMA_POSTCOMMIT_RED=TABLES_EXIST_ACK_UNKNOWN")
            finally:
                store.close()

    def test_12_schema_precommit_ack_loss_leaves_no_action_tables(self):
        with tempfile.TemporaryDirectory(prefix="aion-g34-schema-") as path:
            dbpath = Path(path) / "schema.sqlite3"
            store = SQLiteChatStore(dbpath)
            try:
                proxy = CommitFault(store.db, after=False)
                store.db = proxy
                with self.assertRaisesRegex(OSError, "G34_IMPLICIT_COMMIT_ACK_UNKNOWN"):
                    ExecutionOutbox(store, SCOPE)
                self.assertEqual(proxy.rollbacks, 0)
                self.assertIsNone(store.db)
                raw = sqlite3.connect(dbpath)
                try:
                    count = raw.execute(
                        "SELECT COUNT(*) FROM sqlite_master "
                        "WHERE type='table' AND name LIKE 'action_%'"
                    ).fetchone()[0]
                    self.assertEqual(count, 0)
                finally:
                    raw.close()
            finally:
                store.close()

    def test_13_implicit_write_failure_rollback_error_stays_quarantined(self):
        claimed = self.claim()
        proxy = self.fault(after=False)
        original_execute = proxy.execute
        def fail_update(sql, *args, **kwargs):
            if "SET state=?,lease_owner=" in sql:
                raise RuntimeError("G34_PRIMARY_UPDATE_ERROR")
            return original_execute(sql, *args, **kwargs)
        proxy.execute = fail_update
        def failed_rollback():
            raise OSError("G34_SECONDARY_ROLLBACK_ERROR")
        proxy.rollback = failed_rollback
        with self.assertRaisesRegex(RuntimeError, "G34_PRIMARY_UPDATE_ERROR") as caught:
            self.dispatch(claimed, auth=self.auth(claimed, allowed=False))
        self.assertIsInstance(caught.exception.__cause__, OSError)
        self.assertIsNone(self.store.db)
        self.assertIsNone(self.outbox.db)
        self.assertEqual(self.adapter.lookups, 0)

    def test_14_schema_normal_creation_idempotent(self):
        existing = self.outbox.list()
        self.assertEqual(existing, [])
        again = ExecutionOutbox(self.store, SCOPE)
        self.assertEqual(again.list(), [])
        self.assertFalse(self.store.db.in_transaction)

    def test_15_implicit_denial_is_scoped_and_durable(self):
        claimed = self.claim()
        self.dispatch(claimed, auth=self.auth(claimed, policy="new-policy"))
        store, outbox = self.disk_outbox()
        try:
            row = outbox.get(claimed["idempotency_key"])
            self.assertEqual(row["state"], "BLOCKED_REAPPROVAL")
            self.assertEqual(row["last_error"], "POLICY_VERSION_CHANGED")
        finally:
            store.close()

    def test_16_no_provider_effects_in_all_default_boundaries(self):
        claimed = self.claim()
        self.dispatch(claimed)
        self.assertEqual(self.adapter.lookups, 0)
        self.assertEqual(self.outbox.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
