"""G63 LAB RED-first: fail closed on cyclic confirmation results and
volatile custom payload serialization before any local ledger commit.

ALL tests are disposable SQLite with synthetic data; no external provider,
no Worker, SEND, customer secrets, funds or production authority.
"""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json,tempfile,unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore,StorageUnavailableError
from test_g31_transaction_quarantine_lab import FaultDB
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW=datetime(2026,10,25,23,tzinfo=timezone.utc)
SCOPE=Scope("g63-owner","g63-tenant","g63-space")
EVENT="g63-synthetic-event"
REF="g63-synthetic-receipt"

class ChangesBetweenSerializations:
    def __init__(self, first,second,db=None):
        self.calls=0
        self.first=first
        self.second=second
        self.db=db
        self.second_observation=None
    def __str__(self):
        self.calls+=1
        if self.calls>=2:
            if self.db is not None:
                self.second_observation=(
                    self.db.in_transaction,
                    self.db.execute("SELECT COUNT(*) FROM semantic_reservations_lab").fetchone()[0]
                )
            return self.second
        return self.first

class G63ConfirmCyclesAndStablePayload(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(prefix="a190-g63-")
        self.addCleanup(t.cleanup)
        self.path=Path(t.name)/"local-only.sqlite3"
        self.store=SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.db=self.store.db
        self.box=ExecutionOutbox(self.store,SCOPE)

    def table_counts(self):
        return tuple(self.db.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]
                     for table in ("action_decisions","action_outbox",
                                   "semantic_reservations_lab","action_effects"))

    def stage(self, *, intent="request-A", event=EVENT, extra=None):
        payload={"business_event_id":event,"amount_minor":63}
        if extra:
            payload.update(extra)
        return self.box.enqueue(
            intent_ref=intent,action="synthetic-no-network",
            payload=payload,aggregate_key="synthetic-order",
            policy_version="p1",authorization_ref="synthetic-only",
            created_at=NOW,valid_until=NOW+timedelta(minutes=5),
            semantic_event_id_lab=event,
        )

    def prepare_uncertain(self):
        key=self.stage()["idempotency_key"]
        self.db.execute("UPDATE action_outbox SET state='UNCERTAIN' WHERE idempotency_key=?",(key,))
        self.db.commit()
        return key

    def confirm(self,key,result):
        return self.box._confirm(key,effect_ref=REF,
                                 confirmed_at=NOW+timedelta(minutes=1),
                                 result=result)

    def assert_unchanged_confirmation_denial(self,key,do):
        before=self.table_counts()
        raw=self.db.execute(
            "SELECT state,data,confirmed_at,effect_ref FROM action_outbox WHERE idempotency_key=?",
            (key,)).fetchone()
        old=tuple(raw)
        with self.assertRaisesRegex(ValueError,"G63_CYCLIC_RESULT_DENY"):
            do()
        self.assertEqual(self.table_counts(),before)
        self.assertEqual(tuple(self.db.execute(
            "SELECT state,data,confirmed_at,effect_ref FROM action_outbox WHERE idempotency_key=?",
            (key,)).fetchone()),old)
        self.assertFalse(self.db.in_transaction)
        self.assertEqual(self.store.storage_health()["state"],"healthy")

    def test_01_confirm_self_referential_dict_denied_before_begin(self):
        key=self.prepare_uncertain()
        cyclic={}
        cyclic["again"]=cyclic
        self.assert_unchanged_confirmation_denial(key,lambda:self.confirm(key,{"loop":cyclic}))
        print("G63_CONFIRM_DICT_CYCLE_GREEN=NO_LEDGER_WRITE")

    def test_02_confirm_tuple_list_cycle_denied(self):
        key=self.prepare_uncertain()
        values=[]
        wrapped=(values,)
        values.append(wrapped)
        self.assert_unchanged_confirmation_denial(key,lambda:self.confirm(key,{"nested":wrapped}))
        print("G63_CONFIRM_TUPLE_CYCLE_GREEN=NO_RECURSION")

    def test_03_confirm_cycle_beneath_redacted_key_denied(self):
        key=self.prepare_uncertain()
        hidden={}
        hidden["self"]=hidden
        self.assert_unchanged_confirmation_denial(key,lambda:self.confirm(key,{"password":hidden}))

    def test_04_confirm_healthy_result_with_tuple_redacts_fake_secret(self):
        key=self.prepare_uncertain()
        fake="G63_FAKE_SECRET_NOT_A_CREDENTIAL"
        result=self.confirm(key,{"items":({"password":fake},)})
        self.assertEqual(result["state"],"CONFIRMED")
        ledger=json.loads(self.db.execute(
            "SELECT data FROM action_effects WHERE idempotency_key=?",(key,)).fetchone()[0])
        self.assertEqual(ledger["items"],[{"password":"[REDACTED]"}])
        self.assertNotIn(fake,json.dumps(ledger))
        self.assertEqual(self.table_counts(),(1,1,1,1))
        print("G63_CONFIRM_CLEAN_GREEN=SYNTHETIC_LEDGER_ONLY")

    def test_05_confirmation_shared_acyclic_result_allowed(self):
        key=self.prepare_uncertain()
        shared={"numbers":[1,2,3]}
        result=self.confirm(key,{"a":shared,"b":shared})
        self.assertEqual(result["state"],"CONFIRMED")
        self.assertEqual(self.table_counts(),(1,1,1,1))

    def assert_drift_denial(self,volatile,code):
        before=self.table_counts()
        with self.assertRaisesRegex(RuntimeError,code):
            self.stage(extra={"opaque":volatile})
        self.assertGreaterEqual(volatile.calls,2)
        self.assertEqual(volatile.second_observation,(True,1))
        self.assertEqual(self.table_counts(),before)
        self.assertFalse(self.db.in_transaction)
        self.assertEqual(self.store.storage_health()["state"],"healthy")

    def test_06_volatile_custom_string_mismatch_denied(self):
        volatile=ChangesBetweenSerializations("synthetic-first","synthetic-second",self.db)
        self.assert_drift_denial(volatile,"G63_STAGED_PAYLOAD_DRIFT_DENY")
        print("G63_VOLATILE_DIGEST_GREEN=NO_MISMATCH_PERSISTED")

    def test_07_volatile_string_secret_after_redact_denied(self):
        volatile=ChangesBetweenSerializations(
            "synthetic-first","sk-G63SYNTHETIC1234567890",self.db)
        self.assert_drift_denial(volatile,"G63_STAGED_PAYLOAD_PRIVACY_DENY")
        print("G63_VOLATILE_SECRET_GREEN=NO_FAKE_TOKEN_PERSISTED")

    def test_08_volatile_string_bearer_after_redact_denied(self):
        volatile=ChangesBetweenSerializations(
            "synthetic-first","Bearer G63FAKETOKEN1234",self.db)
        self.assert_drift_denial(volatile,"G63_STAGED_PAYLOAD_PRIVACY_DENY")

    def test_09_stable_custom_object_keeps_synthetic_replay(self):
        a=ChangesBetweenSerializations("stable-synthetic","stable-synthetic",self.db)
        first=self.stage(extra={"opaque":a})
        self.assertEqual(first["enqueue_state"],"ENQUEUED")
        self.assertEqual(self.table_counts(),(1,1,1,0))
        row=self.db.execute("SELECT data FROM action_decisions").fetchone()[0]
        doc=json.loads(row)
        self.assertEqual(doc["payload"]["opaque"],"stable-synthetic")
        second=self.stage(extra={"opaque":"stable-synthetic"})
        self.assertEqual(second["enqueue_state"],"IDEMPOTENT")
        self.assertEqual(self.table_counts(),(1,1,1,0))
        print("G63_STABLE_OBJECT_GREEN=LEGITIMATE_REPLAY")

    def test_11_stable_custom_secret_rejected_even_if_digest_matches(self):
        secret="sk-G63SYNTHETICSTABLE123456"
        volatile=ChangesBetweenSerializations(secret,secret,self.db)
        self.assert_drift_denial(volatile,"G63_STAGED_PAYLOAD_PRIVACY_DENY")
        print("G63_STABLE_SECRET_GREEN=REDACTION_AFTER_ENCODING")

    def test_12_drift_plus_failed_rollback_preserves_primary_and_quarantines(self):
        volatile=ChangesBetweenSerializations("first-safe","second-safe",self.db)
        original=self.db
        fault=FaultDB(original,trigger="G63_NO_INTERCEPT",rollback_fails=True)
        self.box.db=fault
        with self.assertRaisesRegex(
            RuntimeError,"G63_STAGED_PAYLOAD_DRIFT_DENY") as caught:
            self.stage(extra={"unstable":volatile})
        self.assertEqual(volatile.second_observation,(True,1))
        self.assertEqual(fault.rollbacks,1)
        self.assertIsInstance(caught.exception.__cause__,OSError)
        self.assertIn("G31_SECONDARY_ROLLBACK_FAILURE",str(caught.exception.__cause__))
        self.assertIsNone(self.box.db)
        self.assertIsNone(self.store.db)
        self.assertEqual(self.store.storage_health()["state"],"failed")
        with self.assertRaises(StorageUnavailableError):
            self.stage(intent="request-B",event="another-event")
        disk=SQLiteChatStore(self.path)
        try:
            self.assertEqual(tuple(disk.db.execute(
                "SELECT COUNT(*) FROM "+table).fetchone()[0]
                for table in ("action_decisions","action_outbox",
                              "semantic_reservations_lab","action_effects")),(0,0,0,0))
        finally:
            disk.close()
        print("G63_DRIFT_QUARANTINE_GREEN=PRIMARY_NO_RETRY")

    def test_13_confirm_list_self_cycle_denied(self):
        key=self.prepare_uncertain()
        values=[]
        values.append(values)
        self.assert_unchanged_confirmation_denial(
            key,lambda:self.confirm(key,{"values":values}))
        print("G63_CONFIRM_LIST_CYCLE_GREEN=NO_LEDGER_WRITE")

    def test_10_same_declared_event_with_different_request_still_denied(self):
        self.stage()
        with self.assertRaisesRegex(ValueError,"semantic business event collision"):
            self.stage(intent="request-B")
        self.assertEqual(self.table_counts(),(1,1,1,0))

if __name__=="__main__":
    unittest.main()
