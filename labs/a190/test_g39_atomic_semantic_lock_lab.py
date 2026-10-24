"""G39: opt-in tenant-wide atomic semantic reservation over REAL Outbox.

LAB-only candidate: callers still supply the business event ID, no independent
source authentication or external custodian. No Worker, provider, send.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW=datetime(2026,10,24,20,tzinfo=timezone.utc)
SCOPE=Scope("g39-owner","g39-tenant","g39-workspace")
EVENT="synthetic-obligation-42"

class G39AtomicSemanticReservation(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="g39-lock-")
        self.addCleanup(tmp.cleanup)
        self.store=SQLiteChatStore(Path(tmp.name)/"outbox.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox=ExecutionOutbox(self.store,SCOPE)

    def stage(self, *, outbox=None, intent="request-A", event=EVENT,
              amount=1000, strict=True):
        return (self.outbox if outbox is None else outbox).enqueue(
            intent_ref=intent,action="synthetic_no_provider",
            payload={"business_event_id":event,"amount_minor":amount},
            aggregate_key="synthetic-commercial-aggregate",
            policy_version="p1",authorization_ref="a1",
            created_at=NOW,valid_until=NOW+timedelta(minutes=5),
            semantic_event_id_lab=event if strict else "",
        )

    def locks(self):
        return self.store.db.execute(
            "SELECT owner,tenant,business_event_id,workspace,intent_ref,"
            "idempotency_key,payload_digest FROM semantic_reservations_lab"
        ).fetchall()

    def test_01_strict_first_reservation_atomic(self):
        item=self.stage()
        self.assertEqual(item["enqueue_state"],"ENQUEUED")
        self.assertEqual(item["state"],"PENDING")
        self.assertEqual(len(self.locks()),1)
        self.assertEqual(self.locks()[0]["idempotency_key"],item["idempotency_key"])
        self.assertEqual(len(self.outbox.list()),1)
        self.assertEqual(self.outbox.effect_count(),0)

    def test_02_same_request_strict_idempotent(self):
        a=self.stage()
        b=self.stage()
        self.assertEqual(b["enqueue_state"],"IDEMPOTENT")
        self.assertEqual(b["idempotency_key"],a["idempotency_key"])
        self.assertEqual(len(self.locks()),1)

    def test_03_request_alias_same_event_denied_before_second_outbox_row(self):
        a=self.stage()
        with self.assertRaisesRegex(ValueError,"semantic business event collision"):
            self.stage(intent="request-B")
        self.assertEqual(len(self.outbox.list()),1)
        self.assertEqual(len(self.locks()),1)
        self.assertEqual(self.locks()[0]["idempotency_key"],a["idempotency_key"])
        print("G39_ALIAS_GUARD_GREEN=SAME_EVENT_NEW_REQUEST_DENIED_ONE_ROW")

    def test_04_other_workspace_same_owner_tenant_event_denied(self):
        self.stage()
        foreign=ExecutionOutbox(self.store,Scope(SCOPE.owner_id,SCOPE.tenant_id,"other-workspace"))
        with self.assertRaisesRegex(ValueError,"semantic business event collision"):
            self.stage(outbox=foreign,intent="other-request")
        self.assertEqual(len(foreign.list()),0)
        self.assertEqual(len(self.outbox.list()),1)
        print("G39_TENANT_GLOBAL_GREEN=CROSS_WORKSPACE_SAME_EVENT_DENIED")

    def test_05_different_tenant_same_event_allowed_separate_boundary(self):
        self.stage()
        foreign=ExecutionOutbox(self.store,Scope(SCOPE.owner_id,"separate-tenant","new-workspace"))
        other=self.stage(outbox=foreign,intent="another-request")
        self.assertEqual(other["enqueue_state"],"ENQUEUED")
        self.assertEqual(len(self.locks()),2)
        self.assertEqual(len(foreign.list()),1)

    def test_06_different_owner_same_event_allowed(self):
        self.stage()
        foreign=ExecutionOutbox(self.store,Scope("other-owner",SCOPE.tenant_id,"separate-workspace"))
        other=self.stage(outbox=foreign,intent="other-intent")
        self.assertEqual(other["enqueue_state"],"ENQUEUED")
        self.assertEqual(len(self.locks()),2)

    def test_07_distinct_signed_event_ids_still_cannot_prove_business_truth_red(self):
        self.stage()
        self.stage(event="fabricated-identifier-for-same-obligation",intent="request-B")
        self.assertEqual(len(self.outbox.list()),2)
        self.assertEqual(len(self.locks()),2)
        print("G39_EVENT_ALIAS_RED=CALLER_INVENTED_DIFFERENT_EVENT_BYPASSES_SEMANTIC_LOCK")

    def test_08_semantic_binding_mismatch_denied(self):
        with self.assertRaisesRegex(ValueError,"semantic event binding mismatch"):
            self.outbox.enqueue(intent_ref="request-A",action="synthetic_no_provider",
                payload={"business_event_id":"a","amount_minor":1000},
                aggregate_key="synthetic-commercial-aggregate",
                policy_version="p1",authorization_ref="a1",
                created_at=NOW,valid_until=NOW+timedelta(minutes=5),
                semantic_event_id_lab="b")
        self.assertEqual(len(self.locks()),0)

    def test_09_conflicting_payload_denied(self):
        self.stage()
        with self.assertRaisesRegex(ValueError,"semantic business event collision"):
            self.stage(intent="request-B",amount=2000)
        self.assertEqual(len(self.outbox.list()),1)

    def test_10_late_strict_upgrade_of_legacy_intent_denied(self):
        self.stage(strict=False)
        with self.assertRaisesRegex(ValueError,"intent_ref idempotency collision"):
            self.stage(strict=True)
        self.assertEqual(len(self.outbox.list()),1)
        self.assertEqual(len(self.locks()),0)

    def test_11_legacy_outbox_can_still_stage_aliases_red(self):
        self.stage(strict=False)
        self.stage(strict=False,intent="request-B")
        self.assertEqual(len(self.outbox.list()),2)
        self.assertEqual(len(self.locks()),0)
        print("G39_LEGACY_PATH_RED=OPTIONAL_STRICT_MODE_NOT_GLOBAL_ENFORCEMENT")

    def test_12_failed_outbox_write_rolls_back_semantic_lock(self):
        original=self.outbox.db
        class Proxy:
            def execute(self,sql,*a,**kw):
                if "INSERT INTO action_decisions" in sql:
                    raise RuntimeError("G39_SYNTHETIC_INSERT_FAILURE")
                return original.execute(sql,*a,**kw)
            def __getattr__(self,field):return getattr(original,field)
        self.outbox.db=Proxy()
        try:
            with self.assertRaisesRegex(RuntimeError,"G39_SYNTHETIC_INSERT_FAILURE"):
                self.stage()
        finally:
            self.outbox.db=original
        self.assertFalse(original.in_transaction)
        self.assertEqual(len(self.locks()),0)
        self.assertEqual(len(self.outbox.list()),0)
        print("G39_ATOMIC_ROLLBACK_GREEN=NO_ORPHAN_SEMANTIC_LOCK")

    def test_13_reopen_store_keeps_semantic_lock_and_denies_alias(self):
        self.stage()
        path=self.store.path
        self.store.close()
        self.store=SQLiteChatStore(path)
        try:
            self.outbox=ExecutionOutbox(self.store,SCOPE)
            with self.assertRaisesRegex(ValueError,"semantic business event collision"):
                self.stage(intent="request-B")
            self.assertEqual(len(self.locks()),1)
        finally:
            self.store.close()

    def test_14_existing_same_request_without_event_replays_legacy(self):
        a=self.stage(strict=False)
        b=self.stage(strict=False)
        self.assertEqual(a["idempotency_key"],b["idempotency_key"])
        self.assertEqual(b["enqueue_state"],"IDEMPOTENT")

    def test_15_strict_lock_insert_under_same_transaction(self):
        self.stage()
        self.assertFalse(self.store.db.in_transaction)
        self.assertEqual(self.locks()[0]["business_event_id"],EVENT)
        self.assertEqual(self.outbox.list()[0]["decision"]["semantic_event_id_lab"],EVENT)

    def test_16_same_event_under_other_workspace_read_isolation(self):
        self.stage()
        scoped=ExecutionOutbox(self.store,Scope(SCOPE.owner_id,SCOPE.tenant_id,"another-workspace"))
        self.assertEqual(scoped.list(),[])
        with self.assertRaisesRegex(ValueError,"semantic business event collision"):
            self.stage(outbox=scoped,intent="another-intent")
        self.assertEqual(scoped.list(),[])

if __name__=="__main__":unittest.main()
