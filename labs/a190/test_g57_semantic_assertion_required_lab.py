"""G57 LAB: explicit business event IDs require asserted semantic reservation.

Disposable SQLite; no provider, send, customer, Worker or external identity.
The RED file is committed before the candidate motor change.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026,10,25,20,tzinfo=timezone.utc)
SCOPE = Scope("g57-owner","g57-tenant","g57-workspace")
EVENT = "g57-synthetic-business-event"


class G57RequiredSemanticAssertion(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="a190-g57-")
        self.addCleanup(tmp.cleanup)
        self.store=SQLiteChatStore(Path(tmp.name)/"test.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox=ExecutionOutbox(self.store,SCOPE)

    def stage(self,intent="request-A",*,event=EVENT,semantic=None,outbox=None):
        options=dict(
            intent_ref=intent,action="synthetic_no_network",
            payload={"business_event_id":event,"amount_minor":100},
            aggregate_key="g57-synthetic-aggregate",policy_version="p1",
            authorization_ref="g57-local-auth",created_at=NOW,
            valid_until=NOW+timedelta(minutes=5))
        if semantic is not None:
            options["semantic_event_id_lab"]=semantic
        return (outbox or self.outbox).enqueue(**options)

    def rows(self):
        return self.store.db.execute(
            "SELECT idempotency_key FROM action_outbox ORDER BY idempotency_key"
        ).fetchall()

    def locks(self):
        return self.store.db.execute(
            "SELECT business_event_id,idempotency_key FROM semantic_reservations_lab"
        ).fetchall()

    def test_01_business_event_without_semantic_token_denied(self):
        with self.assertRaisesRegex(ValueError,"G57_SEMANTIC_ASSERTION_REQUIRED"):
            self.stage()
        self.assertEqual(len(self.rows()),0)
        self.assertEqual(len(self.locks()),0)
        print("G57_MISSING_ASSERTION_GREEN=NO_ADMISSION")

    def test_02_second_request_alias_cannot_omit_semantic_token(self):
        first=self.stage(semantic=EVENT)
        with self.assertRaisesRegex(ValueError,"G57_SEMANTIC_ASSERTION_REQUIRED"):
            self.stage(intent="request-B")
        self.assertEqual(len(self.rows()),1)
        self.assertEqual(len(self.locks()),1)
        self.assertEqual(self.locks()[0]["idempotency_key"],first["idempotency_key"])
        print("G57_ALIAS_OMISSION_GREEN=ONE_LOCAL_RESERVATION")

    def test_03_other_workspace_cannot_omit_assertion_for_same_event(self):
        first=self.stage(semantic=EVENT)
        scoped=ExecutionOutbox(self.store,Scope(SCOPE.owner_id,SCOPE.tenant_id,"other-workspace"))
        with self.assertRaisesRegex(ValueError,"G57_SEMANTIC_ASSERTION_REQUIRED"):
            self.stage(intent="request-B",outbox=scoped)
        self.assertEqual(len(self.rows()),1)
        self.assertEqual(len(self.locks()),1)
        self.assertEqual(self.locks()[0]["idempotency_key"],first["idempotency_key"])

    def test_04_valid_assertion_remains_idempotent_and_atomic(self):
        a=self.stage(semantic=EVENT)
        b=self.stage(semantic=EVENT)
        self.assertEqual(a["idempotency_key"],b["idempotency_key"])
        self.assertEqual(b["enqueue_state"],"IDEMPOTENT")
        self.assertEqual(len(self.rows()),1)
        self.assertEqual(len(self.locks()),1)
        print("G57_VALID_EVENT_GREEN=LEGITIMATE_REPLAY")

    def test_05_explicit_semantic_assertion_blocks_request_alias(self):
        self.stage(semantic=EVENT)
        with self.assertRaisesRegex(ValueError,"semantic business event collision"):
            self.stage(intent="request-B",semantic=EVENT)
        self.assertEqual(len(self.rows()),1)
        self.assertEqual(len(self.locks()),1)

    def test_06_missing_or_invalid_event_value_cannot_bypass_guard(self):
        for event in ("",None,False,0):
            with self.subTest(event=event):
                with self.assertRaisesRegex(ValueError,"G57_SEMANTIC_ASSERTION_REQUIRED"):
                    self.stage(event=event)
        self.assertEqual(len(self.rows()),0)
        self.assertEqual(len(self.locks()),0)

    def test_07_payload_without_business_id_keeps_legacy_local_staging(self):
        def stage(intent):
            return self.outbox.enqueue(
                intent_ref=intent,action="synthetic_no_network",
                payload={"invoice":"local-unidentified", "amount_minor":100},
                aggregate_key="g57-other-aggregate",policy_version="p1",
                authorization_ref="g57-local-auth",created_at=NOW,
                valid_until=NOW+timedelta(minutes=5))
        one=stage("legacy-request-A")
        two=stage("legacy-request-A")
        self.assertEqual(two["enqueue_state"],"IDEMPOTENT")
        self.assertEqual(one["idempotency_key"],two["idempotency_key"])
        self.assertEqual(len(self.locks()),0)
        self.assertEqual(len(self.rows()),1)
        print("G57_NO_EVENT_GREEN=NO_UNSUPPORTED_GLOBAL_DEDUP_CLAIM")

    def test_08_mismatched_semantic_binding_still_denied(self):
        with self.assertRaisesRegex(ValueError,"semantic event binding mismatch"):
            self.stage(semantic="different-synthetic-id")
        self.assertEqual(len(self.rows()),0)
        self.assertEqual(len(self.locks()),0)

    def test_09_two_distinct_declared_ids_cannot_prove_real_world_unicity(self):
        self.stage(semantic=EVENT)
        self.stage(intent="request-B",event="fabricated-other-id",
                   semantic="fabricated-other-id")
        self.assertEqual(len(self.rows()),2)
        self.assertEqual(len(self.locks()),2)
        print("G57_EXTERNAL_IDENTITY_LIMIT=DIFFERENT_DECLARATIONS_NOT_PROOF")

if __name__ == "__main__":
    unittest.main()
