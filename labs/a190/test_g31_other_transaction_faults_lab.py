"""G31: other transactional paths and stale-claim rollback quarantine."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile,unittest
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore,StorageUnavailableError
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW=datetime(2026,10,24,16,tzinfo=timezone.utc)
SCOPE=Scope("g31-other-owner","g31-other-tenant","g31-other-workspace")

class ZeroCursor:
    rowcount=0

class FailingDB:
    def __init__(self,real,match,*,zero=False,rollback_fails=True):
        self.real=real
        self.match=match
        self.zero=zero
        self.rollback_fails=rollback_fails
        self.calls=0
    def execute(self,sql,*args,**kwargs):
        if self.match in sql:
            self.calls+=1
            if self.zero:return ZeroCursor()
            raise RuntimeError("G31_PRIMARY_OTHER_TRANSACTION_ERROR")
        return self.real.execute(sql,*args,**kwargs)
    def rollback(self):
        if self.rollback_fails:raise OSError("G31_OTHER_ROLLBACK_FAILURE")
        return self.real.rollback()
    def __getattr__(self,name):return getattr(self.real,name)

class G31OtherTransactions(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="g31-other-")
        self.addCleanup(tmp.cleanup)
        self.store=SQLiteChatStore(Path(tmp.name)/"real.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox=ExecutionOutbox(self.store,SCOPE)
        self.real=self.store.db
        self.addCleanup(lambda:setattr(self.outbox,"db",self.real) if self.store.db is self.real else None)
    def stage(self):
        return self.outbox.enqueue(intent_ref="g31-test",action="synthetic_no_send",
            payload={"amount_minor":2000},aggregate_key="g31-aggregate",
            policy_version="p1",authorization_ref="a1",
            created_at=NOW,valid_until=NOW+timedelta(minutes=5))
    def fault(self,match,*,zero=False,rollback_fails=True):
        proxy=FailingDB(self.real,match,zero=zero,rollback_fails=rollback_fails)
        self.outbox.db=proxy
        return proxy
    def denied(self,fn):
        with self.assertRaisesRegex(RuntimeError,"G31_PRIMARY_OTHER_TRANSACTION_ERROR") as caught:fn()
        self.assertIsInstance(caught.exception.__cause__,OSError)
        self.assertIsNone(self.store.db)
        self.assertIsNone(self.outbox.db)
        with self.assertRaises(StorageUnavailableError):self.store.require_healthy()

    def test_01_claim_release_error_quarantines(self):
        self.stage()
        self.fault("SET state='RETRY'")
        self.denied(lambda:self.outbox.release_expired_claims(now=NOW))

    def test_02_claim_lease_update_error_quarantines(self):
        self.stage()
        self.fault("SET state='CLAIMED'")
        self.denied(lambda:self.outbox.claim_next("g31-worker",now=NOW))

    def test_03_confirm_effect_insert_error_quarantines(self):
        item=self.stage()
        # G53: exercise the effect INSERT failure from a valid synthetic
        # recovery phase instead of a now-prohibited PENDING confirmation.
        self.real.execute(
            "UPDATE action_outbox SET state='UNCERTAIN' "
            "WHERE idempotency_key=?", (item["idempotency_key"],))
        self.real.commit()
        self.fault("INSERT INTO action_effects")
        self.denied(lambda:self.outbox._confirm(item["idempotency_key"],
            effect_ref="synthetic-ref",confirmed_at=NOW))
        print("G31_CONFIRM_PATH_GREEN=PRIMARY_ERROR_QUARANTINED")

    def test_04_stale_claim_rollback_failure_quarantines(self):
        self.stage()
        proxy=self.fault("SET state='CLAIMED'",zero=True)
        with self.assertRaisesRegex(StorageUnavailableError,"OUTBOX_CLAIM_ROLLBACK_UNCERTAIN_NO_RETRY"):
            self.outbox.claim_next("g31-worker",now=NOW)
        self.assertEqual(proxy.calls,1)
        self.assertIsNone(self.store.db)
        self.assertIsNone(self.outbox.db)
        print("G31_STALE_CLAIM_GREEN=FAILED_ROLLBACK_NO_RETRY")

    def test_05_stale_claim_successful_rollback_returns_none(self):
        self.stage()
        proxy=self.fault("SET state='CLAIMED'",zero=True,rollback_fails=False)
        self.assertIsNone(self.outbox.claim_next("g31-worker",now=NOW))
        self.assertEqual(proxy.calls,1)
        self.assertIs(self.store.db,self.real)
        self.assertFalse(self.real.in_transaction)
        self.assertEqual(self.outbox.list()[0]["state"],"PENDING")

    def test_06_claim_error_successful_rollback_preserves_state(self):
        self.stage()
        self.fault("SET state='CLAIMED'",rollback_fails=False)
        with self.assertRaisesRegex(RuntimeError,"G31_PRIMARY_OTHER_TRANSACTION_ERROR"):
            self.outbox.claim_next("g31-worker",now=NOW)
        self.assertIs(self.store.db,self.real)
        self.assertFalse(self.real.in_transaction)
        self.assertEqual(self.outbox.list()[0]["state"],"PENDING")

    def test_07_no_automatic_repair_after_quarantine(self):
        self.stage()
        self.fault("SET state='RETRY'")
        with self.assertRaises(RuntimeError):
            self.outbox.release_expired_claims(now=NOW)
        self.assertIsNone(self.store.db)
        with self.assertRaises(StorageUnavailableError):
            ExecutionOutbox(self.store,SCOPE)

    def test_08_new_store_reopen_does_not_prove_prior_transaction(self):
        self.stage()
        self.fault("SET state='RETRY'")
        with self.assertRaises(RuntimeError):
            self.outbox.release_expired_claims(now=NOW)
        new_store=SQLiteChatStore(self.store.path)
        try:
            fresh=ExecutionOutbox(new_store,SCOPE)
            self.assertEqual(len(fresh.list()),1)
            self.assertEqual(fresh.effect_count(),0)
            # A new local SQLite handle cannot prove external attempt status.
            self.assertFalse(fresh.list()[0]["executes_action"])
            print("G31_REOPEN_LIMIT=LOCAL_DB_NOT_EXTERNAL_FRESHNESS_PROOF")
        finally:
            new_store.close()

if __name__=="__main__":unittest.main()
