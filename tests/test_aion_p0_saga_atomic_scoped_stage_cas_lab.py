"""AION P0 LAB RED-first: Saga staging must CAS after Outbox enqueue.

A SQLite trigger simulates a mutation to the Saga projection occurring while
the first forward intent is staged. Normal Saga/Outbox share a single SQLite
transaction; no actual external worker, adapter, provider or effect executes.
Before patch, the stale step update silently reports success/commits in
several scenarios even when no row was updated or when a plan changed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_cumulative_authority_budget import CumulativeAuthorityBudget
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_execution_saga import ExecutionSagaCoordinator

NOW = datetime(2026,10,21,16,30,tzinfo=timezone.utc)
SCOPE = Scope("owner-a", "tenant-a", "workspace-a")


class AionSagaAtomicScopedStageCASLab(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(prefix="aion-saga-first-stage-cas-")
        self.addCleanup(t.cleanup)
        self.store=SQLiteChatStore(Path(t.name)/"staging.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox=ExecutionOutbox(self.store,SCOPE)
        self.budget=CumulativeAuthorityBudget(
            self.store,SCOPE,authority_budget_ref="budget-lab",
            policy_version="policy-lab",
        )
        self.saga=ExecutionSagaCoordinator(
            self.store,SCOPE,outbox=self.outbox,authority_budget=self.budget,
        )
        self.saga.create(saga_id="saga-a",created_at=NOW,steps=[{
            "step_key":"one","action":"save_lab_note",
            "payload":{"marker":"original","test_only":True},
            "capability_class":"LOW_RISK","risk_points":1,
            "reversible":False,"compensation_payload":{},
        }])

    def stage(self):
        return self.saga.enqueue_next(
            "saga-a",authorization_ref="lab-consent-not-authenticated",
            valid_until=NOW+timedelta(minutes=5),created_at=NOW,
        )

    def trigger(self, statement):
        self.store.db.executescript(
            "CREATE TRIGGER aion_lab_mutate_after_outbox "
            "AFTER INSERT ON action_outbox BEGIN "
            +statement+"; END;"
        )

    def assert_rolled_back(self):
        s=self.saga.get("saga-a")
        self.assertEqual(s["state"],"PLANNED")
        self.assertEqual(s["steps"][0]["step_key"],"one")
        self.assertEqual(s["steps"][0]["state"],"PENDING")
        self.assertEqual(s["steps"][0]["payload"]["marker"],"original")
        self.assertEqual(len(self.outbox.list()),0)
        self.assertEqual(self.outbox.effect_count(),0)
        integrity=self.saga.integrity_report("saga-a")
        self.assertEqual(integrity["state"],"MATCH")

    def test_01_normal_staging_keeps_atomic_saga_outbox_linkage(self):
        result=self.stage()
        self.assertEqual(result["state"],"ENQUEUED")
        self.assertFalse(result["executes_action"])
        self.assertEqual(self.saga.get("saga-a")["state"],"RUNNING")
        self.assertEqual(self.saga.get("saga-a")["steps"][0]["state"],"ENQUEUED")
        self.assertEqual(self.outbox.get(result["outbox"]["idempotency_key"])["state"],"PENDING")
        self.assertEqual(self.saga.integrity_report("saga-a")["state"],"MATCH")
        self.assertEqual(self.outbox.effect_count(),0)

    def test_02_step_key_changed_during_enqueue_must_abort_without_orphan_outbox(self):
        self.trigger("UPDATE aion_execution_saga_steps SET step_key='moved' "
                     "WHERE saga_id='saga-a' AND step_key='one'")
        with self.assertRaisesRegex(PermissionError,"SAGA_STAGE_SNAPSHOT_STALE"):
            self.stage()
        self.assert_rolled_back()

    def test_03_step_state_changed_during_enqueue_must_not_overwrite(self):
        self.trigger("UPDATE aion_execution_saga_steps SET state='BLOCKED_PRODUCER' "
                     "WHERE saga_id='saga-a' AND step_key='one'")
        with self.assertRaisesRegex(PermissionError,"SAGA_STAGE_SNAPSHOT_STALE"):
            self.stage()
        self.assert_rolled_back()

    def test_04_step_payload_changed_during_enqueue_must_abort(self):
        self.trigger("""UPDATE aion_execution_saga_steps
          SET payload='{"marker":"forged","test_only":true}'
          WHERE saga_id='saga-a' AND step_key='one'""")
        with self.assertRaisesRegex(PermissionError,"SAGA_STAGE_SNAPSHOT_STALE"):
            self.stage()
        self.assert_rolled_back()

    def test_05_parent_state_changed_during_enqueue_must_abort(self):
        self.trigger("UPDATE aion_execution_sagas SET state='COMPLETED' "
                     "WHERE saga_id='saga-a'")
        with self.assertRaisesRegex(PermissionError,"SAGA_STAGE_SNAPSHOT_STALE"):
            self.stage()
        self.assert_rolled_back()

    def test_06_parent_tenant_changed_during_enqueue_must_abort(self):
        self.trigger("UPDATE aion_execution_sagas SET tenant='tenant-other' "
                     "WHERE saga_id='saga-a'")
        with self.assertRaisesRegex(PermissionError,"SAGA_STAGE_SNAPSHOT_STALE"):
            self.stage()
        self.assert_rolled_back()

    def test_07_parent_policy_digest_changed_during_enqueue_must_abort(self):
        self.trigger("UPDATE aion_execution_sagas SET plan_digest='0000000000000000000000000000000000000000000000000000000000000000' "
                     "WHERE saga_id='saga-a'")
        with self.assertRaisesRegex(PermissionError,"SAGA_STAGE_SNAPSHOT_STALE"):
            self.stage()
        self.assert_rolled_back()

    def test_08_multiple_steps_allow_first_staging_only_without_provider(self):
        self.assertEqual(self.saga.integrity_report("saga-a")["state"],"MATCH")
        self.assertFalse(self.budget.guard.__name__ == "allow_unverified_external_sender")
        first=self.stage()
        self.assertEqual(self.outbox.effect_count(),0)
        self.assertFalse(first["executes_action"])
        self.assertEqual(len(self.outbox.list()),1)

    def test_09_actual_sql_error_rolls_back_both_tables(self):
        self.trigger("SELECT RAISE(ABORT,'lab-forced-fault')")
        with self.assertRaises(Exception):
            self.stage()
        self.assert_rolled_back()


if __name__=="__main__":
    unittest.main()
