"""RED-FIRST LAB: Saga must not restage a pre-existing first Outbox attempt.

Genuine SQLiteChatStore, CumulativeAuthorityBudget, ExecutionOutbox and
ExecutionSagaCoordinator share one disposable SQLite connection. A first
intent exists in Outbox but the Saga's forward step is still PENDING, as can
happen after local corruption, divergent recovery, or a non-atomic legacy
stage. Outbox.enqueue deliberately returns IDEMPOTENT for the same key;
the Saga must NOT silently turn that into a new ENQUEUED admission.

No external adapter, worker, provider call, owner proof or real effect.
This is a LOCAL fail-closed regression, not an exactly-once guarantee.
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

NOW = datetime(2026, 10, 21, 17, 0, tzinfo=timezone.utc)
SCOPE = Scope("first-owner", "first-tenant", "first-workspace")
BLOCK = "SAGA_FIRST_INTENT_REENTRY_REQUIRES_RECONCILIATION"


class SagaExistingFirstIntentFenceLab(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aion-saga-existing-first-intent-")
        self.addCleanup(tmp.cleanup)
        self.store = SQLiteChatStore(Path(tmp.name) / "first.sqlite3")
        self.addCleanup(self.store.close)
        self.db = self.store.db
        self.box = ExecutionOutbox(self.store,SCOPE)
        self.budget = CumulativeAuthorityBudget(
            self.store,SCOPE,authority_budget_ref="budget-local",
            policy_version="policy-local",
        )
        self.saga = ExecutionSagaCoordinator(
            self.store,SCOPE,outbox=self.box,authority_budget=self.budget,
        )
        self.saga.create(saga_id="saga-first",created_at=NOW,steps=[{
            "step_key":"first",
            "action":"stage_lab_note",
            "payload":{"stage":"first","test_only":True},
            "capability_class":"LOW_RISK",
            "risk_points":1,
            "reversible":False,
            "compensation_payload":{},
        }])

    def stage_saga(self, **kwargs):
        return self.saga.enqueue_next(
            "saga-first",
            authorization_ref=kwargs.get("authorization_ref","lab-not-auth"),
            valid_until=NOW+timedelta(minutes=5),
            created_at=NOW,
        )

    def seed_same_first_intent(self):
        return self.box.enqueue(
            intent_ref="saga-first:first:forward",
            action="stage_lab_note",
            payload={"stage":"first","test_only":True},
            aggregate_key="saga:saga-first:forward",
            policy_version="policy-local",
            authorization_ref="lab-not-auth",
            valid_until=NOW+timedelta(minutes=5),
            created_at=NOW,
            transaction_id="saga-first",
            authority_budget_ref="budget-local",
            risk_points=1,
            capability_class="LOW_RISK",
        )

    def set_first_state(self,state):
        first=self.seed_same_first_intent()
        kwargs={"CLAIMED":("state='CLAIMED', attempts=1,lease_owner='old-worker',"
                           "lease_until='2026-10-21T17:00:20+00:00'"),
                "RETRY":("state='RETRY',attempts=1"),
                "UNCERTAIN":("state='UNCERTAIN',attempts=1,"
                             "dispatch_started_at='2026-10-21T17:00:01+00:00'"),
                "SENT":("state='SENT',attempts=1,"
                        "dispatch_started_at='2026-10-21T17:00:01+00:00',"
                        "sent_at='2026-10-21T17:00:02+00:00'"),
                "CONFIRMED":("state='CONFIRMED',attempts=1,"
                             "dispatch_started_at='2026-10-21T17:00:01+00:00',"
                             "sent_at='2026-10-21T17:00:02+00:00',"
                             "confirmed_at='2026-10-21T17:00:03+00:00',"
                             "effect_ref='unverified-local-ref'"),
                "REVOKED":("state='REVOKED',last_error='local-revocation'"),
                "BLOCKED_PRODUCER":("state='BLOCKED_PRODUCER',"
                                    "last_error='producer-not-enrolled'"),
                "BLOCKED_REAPPROVAL":("state='BLOCKED_REAPPROVAL',"
                                      "last_error='authorization-uncertain'"),
                "FAILED":("state='FAILED',last_error='unverified-local-no-effect'"),
                "PENDING":"state='PENDING'"}
        if state not in kwargs:
            raise AssertionError("unknown lab state")
        with self.db:
            self.db.execute(
                "UPDATE action_outbox SET "+kwargs[state]+
                " WHERE idempotency_key=?",
                (first["idempotency_key"],),
            )
        self.assertEqual(self.box.get(first["idempotency_key"])["state"],state)
        self.assertEqual(self.box.get(first["idempotency_key"])["local_integrity"],"MATCH")
        return first

    def assert_fails_closed(self,state):
        first=self.set_first_state(state)
        before=tuple(self.db.iterdump())
        report_before=self.saga.integrity_report("saga-first")
        self.assertEqual(report_before["state"],"MATCH")
        with self.assertRaisesRegex(PermissionError,BLOCK):
            self.stage_saga()
        self.assertEqual(tuple(self.db.iterdump()),before)
        after=self.saga.get("saga-first")
        self.assertEqual(after["state"],"PLANNED")
        self.assertEqual(after["steps"][0]["state"],"PENDING")
        self.assertEqual(after["steps"][0]["outbox_key"],"")
        self.assertEqual(self.saga.integrity_report("saga-first"),report_before)
        item=self.box.get(first["idempotency_key"])
        self.assertEqual(item["state"],state)
        self.assertEqual(item["local_integrity"],"MATCH")
        self.assertEqual(self.box.effect_count(),0)

    def test_01_healthy_first_time_stage_remains_allowed_locally(self):
        out=self.stage_saga()
        self.assertEqual(out["state"],"ENQUEUED")
        self.assertEqual(out["outbox"]["enqueue_state"],"ENQUEUED")
        self.assertEqual(out["outbox"]["state"],"PENDING")
        self.assertEqual(out["outbox"]["local_integrity"],"MATCH")
        self.assertEqual(self.saga.get("saga-first")["state"],"RUNNING")
        self.assertEqual(self.saga.integrity_report("saga-first")["state"],"MATCH")
        self.assertFalse(out["executes_action"])
        self.assertEqual(self.box.effect_count(),0)

    def test_02_existing_clean_pending_intent_denied(self):
        self.assert_fails_closed("PENDING")

    def test_03_existing_retry_intent_denied(self):
        self.assert_fails_closed("RETRY")

    def test_04_existing_claimed_intent_denied(self):
        self.assert_fails_closed("CLAIMED")

    def test_05_existing_uncertain_first_attempt_denied(self):
        self.assert_fails_closed("UNCERTAIN")

    def test_06_existing_sent_first_attempt_denied(self):
        self.assert_fails_closed("SENT")

    def test_07_existing_local_confirmed_first_attempt_denied(self):
        self.assert_fails_closed("CONFIRMED")

    def test_08_existing_local_revocation_denied(self):
        self.assert_fails_closed("REVOKED")

    def test_09_existing_producer_block_denied(self):
        self.assert_fails_closed("BLOCKED_PRODUCER")

    def test_10_existing_reapproval_block_denied(self):
        self.assert_fails_closed("BLOCKED_REAPPROVAL")

    def test_11_existing_local_failed_without_provider_fence_denied(self):
        self.assert_fails_closed("FAILED")

    def test_12_direct_outbox_idempotent_lookup_remains_read_only(self):
        first=self.seed_same_first_intent()
        before=tuple(self.db.iterdump())
        found=self.seed_same_first_intent()
        self.assertEqual(found["enqueue_state"],"IDEMPOTENT")
        self.assertEqual(found["idempotency_key"],first["idempotency_key"])
        self.assertEqual(found["local_integrity"],"MATCH")
        self.assertEqual(before,tuple(self.db.iterdump()))
        self.assertEqual(self.box.effect_count(),0)

    def test_13_duplicate_with_changed_authorization_must_not_stage(self):
        self.seed_same_first_intent()
        before=tuple(self.db.iterdump())
        with self.assertRaisesRegex(PermissionError,BLOCK):
            self.stage_saga(authorization_ref="another-local-ref")
        self.assertEqual(before,tuple(self.db.iterdump()))
        self.assertEqual(self.saga.get("saga-first")["state"],"PLANNED")

    def test_14_first_stage_second_call_does_not_create_second_intent(self):
        first=self.stage_saga()
        before=tuple(self.db.iterdump())
        with self.assertRaises((ValueError,PermissionError,LookupError)):
            self.stage_saga()
        self.assertEqual(tuple(self.db.iterdump()),before)
        self.assertEqual(len(self.box.list()),1)
        self.assertEqual(self.box.effect_count(),0)


if __name__=="__main__":
    unittest.main()
