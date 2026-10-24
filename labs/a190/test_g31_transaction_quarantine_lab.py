"""G31 candidate: preserve primary error and permanently quarantine uncertain SQLite."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026,10,24,16,tzinfo=timezone.utc)
SCOPE = Scope("g31-owner","g31-tenant","g31-workspace")

class FaultDB:
    def __init__(self, db, *, trigger, rollback_fails=True, kind=RuntimeError):
        self.db=db
        self.trigger=trigger
        self.rollback_fails=rollback_fails
        self.kind=kind
        self.rollbacks=0
    def execute(self,sql,*args,**kwargs):
        if self.trigger in sql:
            raise self.kind("G31_PRIMARY_SYNTHETIC_WRITE_FAILURE")
        return self.db.execute(sql,*args,**kwargs)
    def rollback(self):
        self.rollbacks+=1
        if self.rollback_fails:
            raise OSError("G31_SECONDARY_ROLLBACK_FAILURE")
        return self.db.rollback()
    def __getattr__(self,name):return getattr(self.db,name)

class G31QuarantineEnqueue(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="g31-quarantine-")
        self.addCleanup(tmp.cleanup)
        self.store=SQLiteChatStore(Path(tmp.name)/"real.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox=ExecutionOutbox(self.store,SCOPE)
        self.real=self.store.db
        def conditional_restore():
            if self.store.db is self.real:
                self.outbox.db=self.real
        self.addCleanup(conditional_restore)

    def stage(self, **kw):
        opts=dict(intent_ref="g31-intent",action="synthetic_no_send",
                  payload={"amount_minor":1000},aggregate_key="g31-aggregate",
                  policy_version="p1",authorization_ref="a1",
                  created_at=NOW,valid_until=NOW+timedelta(minutes=5))
        opts.update(kw)
        return self.outbox.enqueue(**opts)

    def inject(self, trigger="INSERT INTO action_decisions", rollback_fails=True,
               kind=RuntimeError):
        proxy=FaultDB(self.real,trigger=trigger,
                      rollback_fails=rollback_fails,kind=kind)
        self.outbox.db=proxy
        return proxy

    def assert_quarantined(self):
        self.assertIsNone(self.store.db)
        self.assertIsNone(self.outbox.db)
        self.assertEqual(self.store.storage_health()["state"],"failed")
        with self.assertRaises(StorageUnavailableError):
            self.store.require_healthy()

    def test_01_normal_staging_without_fault(self):
        result=self.stage()
        self.assertEqual(result["enqueue_state"],"ENQUEUED")
        self.assertEqual(self.outbox.effect_count(),0)

    def test_02_successful_rollback_retains_primary_and_connection(self):
        proxy=self.inject(rollback_fails=False)
        with self.assertRaisesRegex(RuntimeError,"G31_PRIMARY_SYNTHETIC_WRITE_FAILURE"):
            self.stage()
        self.assertEqual(proxy.rollbacks,1)
        self.assertIs(self.store.db,self.real)
        self.assertFalse(self.real.in_transaction)
        self.assertEqual(len(self.outbox.list()),0)

    def test_03_rollback_failure_preserves_primary_and_chains_secondary(self):
        proxy=self.inject()
        with self.assertRaisesRegex(RuntimeError,"G31_PRIMARY_SYNTHETIC_WRITE_FAILURE") as result:
            self.stage()
        self.assertEqual(proxy.rollbacks,1)
        self.assertIsInstance(result.exception.__cause__,OSError)
        self.assertIn("G31_SECONDARY_ROLLBACK_FAILURE",str(result.exception.__cause__))
        self.assert_quarantined()
        print("G31_PRIMARY_EXCEPTION_GREEN=ORIGINAL_RETAINED_ROLLBACK_AS_CAUSE")

    def test_04_failed_rollback_blocks_new_enqueue(self):
        self.inject()
        with self.assertRaises(RuntimeError):self.stage()
        with self.assertRaises(StorageUnavailableError):self.stage()
        self.assert_quarantined()
        print("G31_QUARANTINE_GREEN=NO_NEW_STAGING_AFTER_FAILED_ROLLBACK")

    def test_05_health_check_does_not_reopen_detached_store(self):
        self.inject()
        with self.assertRaises(RuntimeError):self.stage()
        first=self.store.storage_health(deep=True)
        second=self.store.storage_health(deep=False)
        self.assertEqual(first["state"],"failed")
        self.assertEqual(second["state"],"failed")
        self.assertIsNone(self.store.db)

    def test_06_new_outbox_using_quarantined_store_denied(self):
        self.inject()
        with self.assertRaises(RuntimeError):self.stage()
        with self.assertRaises(StorageUnavailableError):
            ExecutionOutbox(self.store,SCOPE)

    def test_07_no_silent_auto_retry_even_with_same_intent(self):
        self.inject()
        with self.assertRaises(RuntimeError):self.stage()
        for _ in range(2):
            with self.assertRaises(StorageUnavailableError):
                self.stage()
        self.assert_quarantined()

    def test_08_primary_sqlite_exception_type_is_not_replaced(self):
        self.inject(kind=sqlite3.DatabaseError)
        with self.assertRaisesRegex(sqlite3.DatabaseError,"G31_PRIMARY_SYNTHETIC_WRITE_FAILURE") as result:
            self.stage()
        self.assertIsInstance(result.exception.__cause__,OSError)
        self.assert_quarantined()

    def test_09_conflicting_replay_with_failed_rollback_preserves_valueerror(self):
        self.stage()
        proxy=self.inject(trigger="NO_INTERCEPT",rollback_fails=True)
        with self.assertRaisesRegex(ValueError,"intent_ref idempotency collision") as result:
            self.stage(payload={"amount_minor":2000})
        self.assertEqual(proxy.rollbacks,1)
        self.assertIsInstance(result.exception.__cause__,OSError)
        self.assert_quarantined()

    def test_10_successful_rollback_can_continue_staging_explicitly(self):
        self.inject(rollback_fails=False)
        with self.assertRaises(RuntimeError):self.stage()
        self.outbox.db=self.real
        staged=self.stage()
        self.assertEqual(staged["enqueue_state"],"ENQUEUED")
        self.assertEqual(self.outbox.effect_count(),0)

if __name__=="__main__":unittest.main()
