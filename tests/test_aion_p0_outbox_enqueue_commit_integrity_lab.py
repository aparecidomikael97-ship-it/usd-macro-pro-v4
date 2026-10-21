"""RED-FIRST AION P0: enqueue must not commit an invalid post-insert Outbox row.

Actual SQLiteChatStore / ExecutionOutbox / ExecutionSagaCoordinator. SQLite
AFTER INSERT triggers are deliberately installed in a disposable LAB database.
There is no adapter, producer, Worker, HTTP, real execution, or deployment.
This is a partial local-DB corruption threat model, not external provenance.
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

NOW = datetime(2026, 10, 21, 16, 45, tzinfo=timezone.utc)
SCOPE = Scope("owner-stage-lab", "tenant-stage-lab", "workspace-stage-lab")
REASON = "OUTBOX_ENQUEUE_LOCAL_INTEGRITY_MISMATCH"


class OutboxEnqueueAtomicIntegrityLab(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(prefix="aion-outbox-atomic-integrity-")
        self.addCleanup(t.cleanup)
        self.store = SQLiteChatStore(Path(t.name) / "outbox.sqlite3")
        self.addCleanup(self.store.close)
        self.db = self.store.db
        self.box = ExecutionOutbox(self.store, SCOPE)

    def _enqueue(self, label="one"):
        return self.box.enqueue(
            intent_ref="intent-"+label,
            action="stage_lab_note",
            payload={"label":label, "test_only":True},
            aggregate_key="agg-"+label,
            policy_version="lab-policy",
            authorization_ref="not-owner-signature",
            created_at=NOW,
            valid_until=NOW+timedelta(minutes=5),
        )

    def _trigger(self, sql):
        self.db.executescript(
            "CREATE TRIGGER aion_lab_post_enqueue_corruption "
            "AFTER INSERT ON action_outbox BEGIN " + sql + "; END;"
        )

    def _tamper_data(self, expression):
        self._trigger(
            "UPDATE action_decisions SET data="+expression+
            " WHERE decision_id=NEW.decision_id"
        )

    def _assert_rollback(self, before):
        self.assertEqual(tuple(self.db.iterdump()),before)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM action_decisions").fetchone()[0],0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM action_outbox").fetchone()[0],0)
        self.assertEqual(self.box.effect_count(),0)

    def _expect_reject(self):
        before=tuple(self.db.iterdump())
        with self.assertRaisesRegex(PermissionError,REASON):
            self._enqueue()
        self._assert_rollback(before)

    def test_01_normal_standalone_enqueue_is_preserved(self):
        obj=self._enqueue()
        self.assertEqual(obj["enqueue_state"],"ENQUEUED")
        self.assertEqual(obj["state"],"PENDING")
        self.assertEqual(obj["local_integrity"],"MATCH")
        self.assertEqual(obj["attempts"],0)
        self.assertEqual(len(self.box.list()),1)
        self.assertEqual(self.box.effect_count(),0)

    def test_02_forged_authority_after_insert_cannot_commit(self):
        self._tamper_data("replace(data,'\"grants_authority\":false','\"grants_authority\":true')")
        self._expect_reject()

    def test_03_invalid_json_after_insert_cannot_commit(self):
        self._tamper_data("'{'")
        self._expect_reject()

    def test_04_corrupt_authorization_column_cannot_commit(self):
        self._trigger(
            "UPDATE action_decisions SET authorization_ref='attacker-approval' "
            "WHERE decision_id=NEW.decision_id"
        )
        self._expect_reject()

    def test_05_corrupt_deadline_column_cannot_commit(self):
        self._trigger(
            "UPDATE action_decisions SET valid_until='2099-01-01T00:00:00+00:00' "
            "WHERE decision_id=NEW.decision_id"
        )
        self._expect_reject()

    def test_06_forged_confirmed_outbox_state_cannot_commit(self):
        self._trigger(
            "UPDATE action_outbox SET state='CONFIRMED',"
            "confirmed_at='2026-10-21T16:45:01+00:00',effect_ref='forged-effect' "
            "WHERE idempotency_key=NEW.idempotency_key"
        )
        self._expect_reject()

    def test_07_changed_attempts_before_first_claim_cannot_commit(self):
        self._trigger(
            "UPDATE action_outbox SET attempts=7 "
            "WHERE idempotency_key=NEW.idempotency_key"
        )
        self._expect_reject()

    def test_08_forged_pre_dispatch_claim_lease_cannot_commit(self):
        self._trigger(
            "UPDATE action_outbox SET state='CLAIMED',lease_owner='foreign-worker',"
            "lease_until='2026-10-21T16:46:00+00:00' "
            "WHERE idempotency_key=NEW.idempotency_key"
        )
        self._expect_reject()

    def test_09_forged_dispatch_marker_cannot_commit(self):
        self._trigger(
            "UPDATE action_outbox SET dispatch_started_at='2026-10-21T16:45:01+00:00' "
            "WHERE idempotency_key=NEW.idempotency_key"
        )
        self._expect_reject()

    def test_10_fake_local_effect_ledger_cannot_commit(self):
        self._trigger(
            "INSERT INTO action_effects("
            "idempotency_key,owner,tenant,workspace,effect_ref,confirmed_at,data"
            ") VALUES (NEW.idempotency_key,NEW.owner,NEW.tenant,NEW.workspace,"
            "'forged-effect','2026-10-21T16:45:01+00:00','{}')"
        )
        self._expect_reject()

    def _make_saga(self):
        budget=CumulativeAuthorityBudget(
            self.store,SCOPE,authority_budget_ref="lab-budget",
            policy_version="lab-policy",
        )
        saga=ExecutionSagaCoordinator(self.store,SCOPE,outbox=self.box,authority_budget=budget)
        saga.create(saga_id="saga-stage",created_at=NOW,steps=[{
            "step_key":"one",
            "action":"stage_lab_note",
            "payload":{"label":"saga-note","test_only":True},
            "capability_class":"LOW_RISK",
            "risk_points":1,
            "reversible":False,
            "compensation_payload":{},
        }])
        return saga

    def _saga_stage(self,saga):
        return saga.enqueue_next(
            "saga-stage",
            authorization_ref="not-owner-signature",
            created_at=NOW,
            valid_until=NOW+timedelta(minutes=5),
        )

    def test_11_saga_nested_enqueue_must_rollback_everything_when_decision_tampered(self):
        saga=self._make_saga()
        self._tamper_data("replace(data,'\"grants_authority\":false','\"grants_authority\":true')")
        before=tuple(self.db.iterdump())
        with self.assertRaisesRegex(PermissionError,REASON):
            self._saga_stage(saga)
        self._assert_rollback(before)
        self.assertEqual(saga.get("saga-stage")["state"],"PLANNED")
        self.assertEqual(saga.get("saga-stage")["steps"][0]["state"],"PENDING")
        self.assertEqual(saga.integrity_report("saga-stage")["state"],"MATCH")

    def test_12_saga_nested_enqueue_must_reject_forged_outbox_state(self):
        saga=self._make_saga()
        self._trigger(
            "UPDATE action_outbox SET state='CONFIRMED',effect_ref='forged' "
            "WHERE idempotency_key=NEW.idempotency_key"
        )
        before=tuple(self.db.iterdump())
        with self.assertRaisesRegex(PermissionError,REASON):
            self._saga_stage(saga)
        self._assert_rollback(before)
        self.assertEqual(saga.get("saga-stage")["state"],"PLANNED")
        self.assertEqual(saga.integrity_report("saga-stage")["state"],"MATCH")

    def test_13_healthy_saga_staging_remains_atomic_and_has_no_effect(self):
        saga=self._make_saga()
        out=self._saga_stage(saga)
        self.assertEqual(out["state"],"ENQUEUED")
        self.assertEqual(out["outbox"]["state"],"PENDING")
        self.assertEqual(out["outbox"]["local_integrity"],"MATCH")
        self.assertEqual(saga.get("saga-stage")["state"],"RUNNING")
        self.assertEqual(saga.integrity_report("saga-stage")["state"],"MATCH")
        self.assertEqual(self.box.effect_count(),0)

    def test_14_nested_caller_savepoint_preserved_on_invalid_enqueue(self):
        self.db.execute("CREATE TABLE lab_parent_marker (value TEXT)")
        self._tamper_data("replace(data,'\"grants_authority\":false','\"grants_authority\":true')")
        self.db.execute("BEGIN IMMEDIATE")
        self.db.execute("INSERT INTO lab_parent_marker VALUES ('parent')")
        try:
            with self.assertRaisesRegex(PermissionError,REASON):
                self._enqueue()
            self.assertTrue(self.db.in_transaction)
            self.assertEqual(self.db.execute("SELECT COUNT(*) FROM lab_parent_marker").fetchone()[0],1)
            self.assertEqual(self.db.execute("SELECT COUNT(*) FROM action_outbox").fetchone()[0],0)
            self.assertEqual(self.db.execute("SELECT COUNT(*) FROM action_decisions").fetchone()[0],0)
        finally:
            self.db.rollback()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM lab_parent_marker").fetchone()[0],0)

    def test_15_no_external_provider_invoked_during_lab_scenarios(self):
        healthy=self._enqueue()
        self.assertFalse(healthy["executes_action"])
        self.assertEqual(self.box.effect_count(),0)
        self.assertEqual(healthy["local_integrity"],"MATCH")


if __name__=="__main__":
    unittest.main()
