"""G30 real SQLite transaction rollback fault injection: isolated LAB only."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile,unittest
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
NOW=datetime(2026,10,24,16,tzinfo=timezone.utc)
SCOPE=Scope("g30-fault-owner","g30-fault-tenant","g30-fault-workspace")
class FaultingConnection:
    def __init__(self,db,fail):
        self.db=db
        self.fail=fail
        self.rollbacks=0
    def execute(self,sql,*args,**kw):
        if "INSERT INTO action_decisions" in sql:
            raise RuntimeError("G30_ORIGINAL_WRITE_ERROR")
        return self.db.execute(sql,*args,**kw)
    def rollback(self):
        self.rollbacks+=1
        if self.fail:raise OSError("G30_SYNTHETIC_ROLLBACK_ERROR")
        return self.db.rollback()
    def __getattr__(self,key):return getattr(self.db,key)
class G30FaultInjection(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="g30-sql-fault-")
        self.addCleanup(tmp.cleanup)
        self.store=SQLiteChatStore(Path(tmp.name)/"real.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox=ExecutionOutbox(self.store,SCOPE)
        self.db=self.outbox.db
        self.addCleanup(lambda:setattr(self.outbox,"db",self.db))
    def stage(self):
        return self.outbox.enqueue(intent_ref="g30-sql-fault",
          action="synthetic",payload={"amount_minor":1000},
          aggregate_key="aggregate",policy_version="p1",authorization_ref="a1",
          created_at=NOW,valid_until=NOW+timedelta(minutes=5))
    def test_01_successful_rollback_preserves_original_error(self):
        proxy=FaultingConnection(self.db,False)
        self.outbox.db=proxy
        with self.assertRaisesRegex(RuntimeError,"G30_ORIGINAL_WRITE_ERROR"):
            self.stage()
        self.assertEqual(proxy.rollbacks,1)
        self.assertFalse(self.db.in_transaction)
        self.assertEqual(len(self.outbox.list()),0)
    def test_02_failed_rollback_masks_original_and_leaves_transaction_open_red(self):
        proxy=FaultingConnection(self.db,True)
        self.outbox.db=proxy
        try:
            with self.assertRaisesRegex(OSError,"G30_SYNTHETIC_ROLLBACK_ERROR") as caught:
                self.stage()
            self.assertIsInstance(caught.exception.__context__,RuntimeError)
            self.assertTrue(self.db.in_transaction)
            print("G30_SQLITE_ROLLBACK_MASK_RED=ORIGINAL_FAILURE_OBSCURED_TRANSACTION_OPEN")
        finally:
            self.db.rollback()
        self.assertFalse(self.db.in_transaction)
if __name__=="__main__":unittest.main()
