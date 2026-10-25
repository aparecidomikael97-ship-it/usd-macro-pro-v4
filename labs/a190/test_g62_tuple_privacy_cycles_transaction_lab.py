"""G62 RED-first: tuple privacy, cyclic payloads and post-reservation rollback.

Disposable synthetic SQLite only. No network/Worker, real secrets, money or SEND.
All sensitive-looking strings are deliberate fake markers, not credentials.
"""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.privacy import redact
from aion_chat.store import SQLiteChatStore,StorageUnavailableError
from atlasquant_aion_execution_outbox import ExecutionOutbox
from test_g31_transaction_quarantine_lab import FaultDB

NOW=datetime(2026,10,25,23,tzinfo=timezone.utc)
SCOPE=Scope("g62-owner","g62-tenant","g62-space")
E="g62-synthetic-event"

class FailsOnSecondString:
    def __init__(self, db=None):
        self.calls=0
        self.db=db
        self.observed_reservation=None
    def __str__(self):
        self.calls+=1
        if self.calls >= 2:
            # At the second conversion the reservation must ALREADY be
            # visible in the same uncommitted SQLite transaction; otherwise
            # the test would not prove post-reservation rollback integrity.
            if self.db is not None:
                self.observed_reservation=(
                    self.db.in_transaction,
                    self.db.execute(
                        "SELECT COUNT(*) FROM semantic_reservations_lab"
                    ).fetchone()[0],
                )
            raise ValueError("G62_SERIALIZATION_AFTER_RESERVATION")
        return "synthetic-first-string"

class G62TuplePrivacyCycleRecovery(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(prefix="a190-g62-only-")
        self.addCleanup(t.cleanup)
        self.path=Path(t.name)/"no-provider.sqlite3"
        self.store=SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.box=ExecutionOutbox(self.store,SCOPE)
        self.real=self.store.db

    def stage(self,extra=None,request="req-A",event=E):
        payload={"amount_minor":62}
        if event is not None:
            payload["business_event_id"]=event
        if extra:
            payload.update(extra)
        return self.box.enqueue(
            intent_ref=request,action="synthetic_no_external_adapter",
            payload=payload,aggregate_key="g62-group",policy_version="p1",
            authorization_ref="synthetic-auth",
            created_at=NOW,valid_until=NOW+timedelta(minutes=5),
            semantic_event_id_lab=event or "")

    def dbcounts(self,db=None):
        db=self.real if db is None else db
        return tuple(db.execute("SELECT COUNT(*) FROM "+name).fetchone()[0]
                     for name in ("action_decisions","action_outbox",
                                  "semantic_reservations_lab","action_effects"))

    def cold_counts(self):
        other=SQLiteChatStore(self.path)
        try:
            return self.dbcounts(other.db)
        finally:
            other.close()

    def decision(self):
        return json.loads(self.real.execute("SELECT data FROM action_decisions").fetchone()["data"])

    def test_01_tuple_credentials_redacted_before_decision_persistence(self):
        marker="G62_FAKE_PASSWORD_MUST_NOT_PERSIST"
        got=self.stage({"attachments":({"password":marker,"nested":{"token":marker}},)})
        self.assertEqual(got["enqueue_state"],"ENQUEUED")
        raw=self.real.execute("SELECT data FROM action_decisions").fetchone()["data"]
        self.assertNotIn(marker,raw)
        payload=self.decision()["payload"]
        self.assertEqual(payload["attachments"],[{"password":"[REDACTED]",
                                                  "nested":{"token":"[REDACTED]"}}])
        self.assertEqual(self.dbcounts(),(1,1,1,0))
        print("G62_TUPLE_PRIVACY_GREEN=NO_RAW_MARKER")

    def test_02_deep_nested_tuple_strings_and_dict_redacted(self):
        fake="sk"+"-G62SYNTHETIC1234567890"
        extra={"outer":([({"secret":fake,"freeform":"Bearer G62FAKE12345"},)],)}
        safe=redact(extra)
        text=json.dumps(safe,default=str,sort_keys=True)
        self.assertNotIn(fake,text)
        self.assertNotIn("Bearer G62FAKE12345",text)
        self.stage(extra)
        raw=self.real.execute("SELECT data FROM action_decisions").fetchone()["data"]
        self.assertNotIn(fake,raw)
        self.assertNotIn("Bearer G62FAKE12345",raw)
        print("G62_DEEP_TUPLE_GREEN=PATTERNS_REDACTED")

    def test_03_tuple_and_equivalent_list_same_stable_idempotency(self):
        a=self.stage({"items":({"v":"normal"},)})
        b=self.stage({"items":[{"v":"normal"}]})
        self.assertEqual(a["idempotency_key"],b["idempotency_key"])
        self.assertEqual(b["enqueue_state"],"IDEMPOTENT")
        self.assertEqual(self.dbcounts(),(1,1,1,0))
        print("G62_JSON_SHAPE_GREEN=TUPLE_NORMALIZED")

    def test_04_tuple_list_cycle_denied_with_specific_failure(self):
        inner=[]
        outer=(inner,)
        inner.append(outer)
        with self.assertRaisesRegex(ValueError,"G62_CYCLIC_PAYLOAD_DENY"):
            self.stage({"loop":outer})
        self.assertEqual(self.dbcounts(),(0,0,0,0))
        self.assertFalse(self.real.in_transaction)
        print("G62_TUPLE_CYCLE_GREEN=NO_RECURSION")

    def test_05_dict_self_cycle_denied_before_redact(self):
        graph={}
        graph["self"]=graph
        with self.assertRaisesRegex(ValueError,"G62_CYCLIC_PAYLOAD_DENY"):
            self.stage({"graph":graph},event=None)
        self.assertEqual(self.dbcounts(),(0,0,0,0))
        self.assertFalse(self.real.in_transaction)

    def test_10_cycles_hidden_under_sensitive_key_still_fail_before_redact(self):
        circular={}
        circular["again"]=circular
        with self.assertRaisesRegex(ValueError,"G62_CYCLIC_PAYLOAD_DENY"):
            self.stage({"password":circular})
        self.assertEqual(self.dbcounts(),(0,0,0,0))
        self.assertFalse(self.real.in_transaction)
        print("G62_SENSITIVE_CYCLE_GREEN=DENY_BEFORE_REDACT")

    def test_06_repeated_shared_acyclic_containers_still_allowed(self):
        shared={"simple":[2,3]}
        got=self.stage({"first":shared,"second":shared})
        self.assertEqual(got["enqueue_state"],"ENQUEUED")
        self.assertEqual(self.decision()["payload"]["first"],{"simple":[2,3]})
        self.assertEqual(self.dbcounts(),(1,1,1,0))

    def test_07_second_serializer_failure_after_lock_rolls_back(self):
        obj=FailsOnSecondString(self.real)
        with self.assertRaisesRegex(ValueError,"G62_SERIALIZATION_AFTER_RESERVATION"):
            self.stage({"opaque":obj})
        self.assertGreaterEqual(obj.calls,2)
        self.assertEqual(obj.observed_reservation,(True,1))
        self.assertEqual(self.dbcounts(),(0,0,0,0))
        self.assertFalse(self.real.in_transaction)
        self.assertEqual(self.store.storage_health()["state"],"healthy")
        print("G62_POST_RESERVATION_GREEN=ROLLBACK_ALL_THREE_TABLES")

    def test_08_failed_rollback_after_reservation_quarantines_store(self):
        obj=FailsOnSecondString(self.real)
        injected=FaultDB(self.real,trigger="G62_NO_INTERCEPT",rollback_fails=True)
        self.box.db=injected
        with self.assertRaisesRegex(ValueError,"G62_SERIALIZATION_AFTER_RESERVATION") as info:
            self.stage({"opaque":obj})
        self.assertGreaterEqual(obj.calls,2)
        self.assertEqual(obj.observed_reservation,(True,1))
        self.assertEqual(injected.rollbacks,1)
        self.assertIsInstance(info.exception.__cause__,OSError)
        self.assertIn("G31_SECONDARY_ROLLBACK_FAILURE",str(info.exception.__cause__))
        self.assertIsNone(self.box.db)
        self.assertIsNone(self.store.db)
        self.assertEqual(self.store.storage_health()["state"],"failed")
        self.assertEqual(self.cold_counts(),(0,0,0,0))
        with self.assertRaises(StorageUnavailableError):
            self.stage(request="again",event="other-event")
        print("G62_QUARANTINE_GREEN=PRIMARY_ERROR_NO_AUTO_RETRY")

    def test_09_legitimate_simple_payload_same_intent_still_idempotent(self):
        first=self.stage({"details":{"amount":2,"label":"hello"}})
        second=self.stage({"details":{"amount":2,"label":"hello"}})
        self.assertEqual(first["idempotency_key"],second["idempotency_key"])
        self.assertEqual(second["enqueue_state"],"IDEMPOTENT")
        self.assertEqual(self.dbcounts(),(1,1,1,0))

if __name__=="__main__":
    unittest.main()
