"""G61: preserve genuine serializer errors and quarantine failed rollback.

Disposable synthetic SQLite only. The tests are committed BEFORE engine edits.
No external provider, Worker, SEND, customer data, secrets or financial action.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from atlasquant_aion_execution_outbox import ExecutionOutbox
from test_g31_transaction_quarantine_lab import FaultDB

NOW=datetime(2026,10,25,22,tzinfo=timezone.utc)
SCOPE=Scope("g61-owner","g61-tenant","g61-workspace")
EVENT="g61-disposable-event"

class BadString:
    def __str__(self):
        raise ValueError("G61_ORIGINAL_CUSTOM_SERIALIZATION_FAILURE")

class G61ErrorClassificationAndRollback(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="g61-local-")
        self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/"local.sqlite3"
        self.store=SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.box=ExecutionOutbox(self.store,SCOPE)
        self.real=self.store.db

    def stage(self, *, intent="intent-A",event=EVENT,extra=None):
        data={"amount_minor":18}
        if event:
            data["business_event_id"]=event
        if extra:
            data.update(extra)
        return self.box.enqueue(
            intent_ref=intent,action="synthetic_no_external_action",
            payload=data,aggregate_key="g61-aggregate",policy_version="p1",
            authorization_ref="synthetic-auth",created_at=NOW,
            valid_until=NOW+timedelta(minutes=5),
            semantic_event_id_lab=event or "",
        )

    def table_count(self,db=None):
        db=db or self.real
        return tuple(db.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]
                     for table in ("action_decisions","action_outbox",
                                   "semantic_reservations_lab","action_effects"))

    def poison_old_history(self):
        self.stage()
        row=self.real.execute("SELECT decision_id,data FROM action_decisions").fetchone()
        malformed='{"extraneous_aux":1e999,'+row["data"][1:]
        self.real.execute(
            "UPDATE action_decisions SET data=? WHERE decision_id=?",
            (malformed,row["decision_id"]))
        self.real.commit()
        return self.table_count()

    def trigger_historical(self):
        return self.stage(intent="intent-B",event="g61-independent-event")

    def separate_disk_count(self):
        fresh=SQLiteChatStore(self.path)
        try:
            return self.table_count(fresh.db)
        finally:
            fresh.close()

    def test_01_custom_object_valueerror_preserves_original_exception(self):
        with self.assertRaisesRegex(
                ValueError,"G61_ORIGINAL_CUSTOM_SERIALIZATION_FAILURE"):
            self.stage(extra={"opaque":BadString()})
        self.assertEqual(self.table_count(),(0,0,0,0))
        self.assertFalse(self.real.in_transaction)
        self.assertEqual(self.store.storage_health()["state"],"healthy")
        print("G61_ORIGINAL_ERROR_GREEN=NOT_MISLABELED_NONFINITE")

    def test_02_custom_object_nested_without_event_preserves_original(self):
        with self.assertRaisesRegex(
                ValueError,"G61_ORIGINAL_CUSTOM_SERIALIZATION_FAILURE"):
            self.stage(event=None,extra={"list":[{"opaque":BadString()}]})
        self.assertEqual(self.table_count(),(0,0,0,0))
        self.assertFalse(self.real.in_transaction)

    def test_03_true_nan_still_raises_specific_g60_before_begin(self):
        with self.assertRaisesRegex(ValueError,"G60_NONFINITE_PAYLOAD_DENY"):
            self.stage(extra={"score":float("nan")})
        self.assertEqual(self.table_count(),(0,0,0,0))
        self.assertFalse(self.real.in_transaction)
        print("G61_TRUE_NAN_GREEN=PROPER_CLASSIFICATION")

    def test_04_nested_infinity_tuple_still_raises_specific_g60(self):
        with self.assertRaisesRegex(ValueError,"G60_NONFINITE_PAYLOAD_DENY"):
            self.stage(extra={"score":({"value":float("inf")},)})
        self.assertEqual(self.table_count(),(0,0,0,0))

    def test_05_historical_overflow_then_failed_rollback_quarantines(self):
        baseline=self.poison_old_history()
        proxy=FaultDB(self.real,trigger="G61_NO_INTERCEPT",rollback_fails=True)
        self.box.db=proxy
        with self.assertRaisesRegex(
                RuntimeError,"G58_HISTORICAL_JSON_UNTRUSTED_DENY") as info:
            self.trigger_historical()
        self.assertEqual(proxy.rollbacks,1)
        self.assertIsInstance(info.exception.__cause__,OSError)
        self.assertIn("G31_SECONDARY_ROLLBACK_FAILURE",
                      str(info.exception.__cause__))
        self.assertTrue(any("ROLLBACK_FAILED_STORE_QUARANTINED" in note
                            for note in getattr(info.exception,"__notes__",[])))
        self.assertIsNone(self.store.db)
        self.assertIsNone(self.box.db)
        self.assertEqual(self.store.storage_health()["state"],"failed")
        self.assertEqual(self.separate_disk_count(),baseline)
        print("G61_OVERFLOW_ROLLBACK_GREEN=PRIMARY_AND_QUARANTINE")

    def test_06_historical_overflow_healthy_rollback_denies_no_repair(self):
        baseline=self.poison_old_history()
        proxy=FaultDB(self.real,trigger="G61_NO_INTERCEPT",rollback_fails=False)
        self.box.db=proxy
        with self.assertRaisesRegex(
                RuntimeError,"G58_HISTORICAL_JSON_UNTRUSTED_DENY"):
            self.trigger_historical()
        self.assertEqual(proxy.rollbacks,1)
        self.assertIs(self.store.db,self.real)
        self.assertFalse(self.real.in_transaction)
        self.assertEqual(self.table_count(),baseline)
        self.assertEqual(self.store.storage_health()["state"],"healthy")
        print("G61_HEALTHY_ROLLBACK_GREEN=NO_AUTOMATIC_REPAIR")

    def test_07_after_failed_rollback_no_new_enqueue_or_automatic_retry(self):
        self.poison_old_history()
        self.box.db=FaultDB(self.real,trigger="G61_NO_INTERCEPT",rollback_fails=True)
        with self.assertRaises(RuntimeError):
            self.trigger_historical()
        for _ in range(2):
            with self.assertRaises(StorageUnavailableError):
                self.trigger_historical()
        self.assertEqual(self.store.storage_health()["state"],"failed")
        self.assertEqual(self.separate_disk_count(),(1,1,1,0))
        print("G61_QUARANTINE_GREEN=NO_NEW_STAGING_OR_RETRY")

    def test_08_unaffected_tenant_can_still_stage_in_healthy_store(self):
        other=ExecutionOutbox(self.store,Scope("foreign-owner","foreign-tenant","space"))
        result=other.enqueue(
            intent_ref="foreign-request",action="synthetic_no_external_action",
            payload={"amount_minor":27},aggregate_key="foreign-aggregate",
            policy_version="p1",authorization_ref="foreign-fake",
            created_at=NOW,valid_until=NOW+timedelta(minutes=5))
        self.assertEqual(result["enqueue_state"],"ENQUEUED")
        self.assertEqual(self.table_count(),(1,1,0,0))

    def test_09_string_literals_nan_infinity_remain_regular_values(self):
        data=self.stage(extra={"text_nan":"NaN","text_inf":"Infinity"})
        self.assertEqual(data["enqueue_state"],"ENQUEUED")
        again=self.stage(extra={"text_nan":"NaN","text_inf":"Infinity"})
        self.assertEqual(again["enqueue_state"],"IDEMPOTENT")
        self.assertEqual(self.table_count(),(1,1,1,0))

if __name__=="__main__":
    unittest.main()
