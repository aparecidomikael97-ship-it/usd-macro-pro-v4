"""G58 historic missing semantic reservation must deny a new event alias.

Synthetic disposable SQLite, no network, provider, worker, payment or customer.
Tests committed before the candidate engine change for actual RED/GREEN.
"""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW=datetime(2026,10,25,21,tzinfo=timezone.utc)
SCOPE=Scope("g58-owner","g58-tenant","g58-workspace")
EVENT="g58-synthetic-obligation"


class G58HistoricalSemanticCustody(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(prefix="g58-lab-")
        self.addCleanup(t.cleanup)
        self.store=SQLiteChatStore(Path(t.name)/"only-synthetic.sqlite3")
        self.addCleanup(self.store.close)
        self.base=ExecutionOutbox(self.store,SCOPE)

    def stage(self,intent="request-A",event=EVENT,outbox=None,include_event=True):
        payload={"amount_minor":10}
        if include_event:
            payload["business_event_id"]=event
        return (outbox or self.base).enqueue(
            intent_ref=intent,action="synthetic_no_provider",
            payload=payload,aggregate_key="g58-synthetic-aggregate",
            policy_version="p1",authorization_ref="g58-fake",
            created_at=NOW,valid_until=NOW+timedelta(minutes=5),
            semantic_event_id_lab=event if include_event else "",
        )

    def locks(self):
        return self.store.db.execute(
            "SELECT tenant,business_event_id,idempotency_key FROM semantic_reservations_lab "
            "ORDER BY tenant,business_event_id").fetchall()

    def count(self):
        return self.store.db.execute("SELECT COUNT(*) FROM action_outbox").fetchone()[0]

    def delete_lock(self,event=EVENT):
        self.store.db.execute(
            "DELETE FROM semantic_reservations_lab WHERE tenant=? AND business_event_id=?",
            (SCOPE.tenant_id,event))
        self.store.db.commit()

    def assert_fail_closed(self,run,expected="G58_HISTORICAL_SEMANTIC_CUSTODY_DENY"):
        n=self.count()
        m=len(self.locks())
        with self.assertRaisesRegex(RuntimeError,expected):
            run()
        self.assertEqual(self.count(),n)
        self.assertEqual(len(self.locks()),m)
        self.assertFalse(self.store.db.in_transaction)

    def test_01_first_declared_event_stages_normally(self):
        first=self.stage()
        self.assertEqual(first["enqueue_state"],"ENQUEUED")
        self.assertEqual(self.count(),1)
        self.assertEqual(len(self.locks()),1)

    def test_02_old_missing_lock_denies_different_request_same_event(self):
        self.stage()
        self.delete_lock()
        self.assert_fail_closed(lambda:self.stage(intent="request-B"))
        self.assertEqual(self.count(),1)
        self.assertEqual(len(self.locks()),0)
        print("G58_MISSING_LOCK_GREEN=NO_SECOND_INTENT")

    def test_03_old_missing_lock_denies_other_workspace_same_tenant(self):
        self.stage()
        self.delete_lock()
        other=ExecutionOutbox(self.store,Scope("other-owner",SCOPE.tenant_id,"other-space"))
        self.assert_fail_closed(lambda:self.stage(intent="request-B",outbox=other))
        self.assertEqual(len(other.list()),0)
        print("G58_CROSS_SCOPE_GREEN=ONE_TENANT_ONE_ASSERTED_EVENT")

    def test_04_missing_lock_original_same_request_denies_replay(self):
        self.stage()
        self.delete_lock()
        self.assert_fail_closed(lambda:self.stage(),expected="semantic lock missing for existing intent")
        self.assertEqual(self.count(),1)

    def test_05_different_declared_event_remains_independent(self):
        self.stage()
        self.delete_lock()
        second=self.stage(intent="request-B",event="unrelated-synthetic-event")
        self.assertEqual(second["enqueue_state"],"ENQUEUED")
        self.assertEqual(self.count(),2)
        self.assertEqual(len(self.locks()),1)

    def test_06_identical_event_in_other_tenant_remains_allowed(self):
        self.stage()
        self.delete_lock()
        other=ExecutionOutbox(self.store,Scope(SCOPE.owner_id,"another-tenant","second"))
        second=self.stage(intent="request-B",outbox=other)
        self.assertEqual(second["enqueue_state"],"ENQUEUED")
        self.assertEqual(self.count(),2)
        self.assertEqual(len(self.locks()),1)

    def test_07_missing_event_payload_legacy_staging_unchanged(self):
        self.stage()
        self.delete_lock()
        new=self.stage(intent="no-event",include_event=False)
        self.assertEqual(new["enqueue_state"],"ENQUEUED")
        self.assertEqual(self.count(),2)
        self.assertEqual(len(self.locks()),0)

    def test_08_malformed_historical_decision_fails_closed(self):
        self.stage()
        self.delete_lock()
        self.store.db.execute(
            "UPDATE action_decisions SET data='not-json' WHERE tenant=?",
            (SCOPE.tenant_id,))
        self.store.db.commit()
        self.assert_fail_closed(
            lambda:self.stage(intent="request-B"),
            expected="G58_HISTORICAL_JSON_UNTRUSTED_DENY")
        print("G58_BAD_HISTORICAL_JSON_GREEN=NO_SILENT_SKIP")

    def test_09_duplicate_key_historical_json_fails_closed(self):
        self.stage()
        self.delete_lock()
        row=self.store.db.execute("SELECT data FROM action_decisions").fetchone()[0]
        doc='{"payload":{"business_event_id":"fake-other"} ,'+row[1:]
        self.store.db.execute("UPDATE action_decisions SET data=?",(doc,))
        self.store.db.commit()
        self.assert_fail_closed(
            lambda:self.stage(intent="request-B"),
            expected="G58_HISTORICAL_JSON_UNTRUSTED_DENY")

    def test_10_historical_revoked_row_still_blocks_alias(self):
        self.stage()
        self.delete_lock()
        self.store.db.execute("UPDATE action_outbox SET state='REVOKED'")
        self.store.db.commit()
        self.assert_fail_closed(lambda:self.stage(intent="request-B"))
        self.assertEqual(self.count(),1)

    def test_11_explicit_different_asserted_ids_do_not_prove_same_real_event(self):
        self.stage()
        other=self.stage(intent="request-B",event="invented-different-event")
        self.assertEqual(other["enqueue_state"],"ENQUEUED")
        self.assertEqual(self.count(),2)
        print("G58_EXTERNAL_IDENTITY_RED=TWO_DECLARED_IDS_NOT_VERIFIED_REAL_IDENTITY")


if __name__=="__main__":
    unittest.main()
