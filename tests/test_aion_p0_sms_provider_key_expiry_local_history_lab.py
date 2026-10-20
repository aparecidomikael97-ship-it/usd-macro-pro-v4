"""AION P0 LAB — time-shifted SMS key expiry vs local Outbox history.

A documented 30-day OneSignal Create idempotency window does NOT mean 30-day
external-effect certainty. This suite exercises ACTUAL AION Outbox SQLite
durability and admissions, but uses NO API calls or authentic producer receipt.

Green tests intentionally distinguish:
(a) a preserved local SQLite record (local negative guarantees), from
(b) a deleted/rolled-back SQLite history (an OPEN external proof gap).
They NEVER authorize retry, provider enrollment, deployment or P0 closure.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
import test_atlasquant_aion_execution_outbox as fixture

NOW=fixture.NOW

class _NoDescriptorAdapter:
    def __init__(self):
        self.reads=0
    @property
    def send(self):
        self.reads+=1
        raise AssertionError("PROVIDER_BARRIER_VIOLATED")
    @property
    def reconcile(self):
        self.reads+=1
        raise AssertionError("PROVIDER_BARRIER_VIOLATED")

class ExpiredProviderKeyLocalOutboxFenceLAB(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"aion_local_only.sqlite3"
        self.scope=Scope("owner-test", "tenant-test","space-test")
        self.store=SQLiteChatStore(self.path)
        self.addCleanup(self._close_if_open)
        self.outbox=ExecutionOutbox(self.store,self.scope)

    def _close_if_open(self):
        if self.store is not None:
            self.store.close()
            self.store=None

    def restart(self):
        self._close_if_open()
        self.store=SQLiteChatStore(self.path)
        self.outbox=ExecutionOutbox(self.store,self.scope)

    def create(self, *,intent="notification-unique-123",payload=None,
               date=NOW,scope=None,aggregate="client-1", action="send_sms"):
        box=self.outbox if scope is None else ExecutionOutbox(self.store,scope)
        return box.enqueue(
            intent_ref=intent,action=action,
            payload=payload if payload is not None else
                {"to":"FAKE_TEST_RECIPIENT", "body":"FAKE_TEST_BODY"},
            aggregate_key=aggregate,policy_version="policy-v1",
            authorization_ref="LAB_APPROVAL_NOT_REAL",
            created_at=date, valid_until=date+timedelta(minutes=5),
        )

    def verify_quarantined(self,key,*,future):
        row=self.outbox.get(key)
        self.assertEqual(row["state"],"UNCERTAIN")
        self.assertEqual(self.outbox.release_expired_claims(now=future),0)
        self.assertIsNone(self.outbox.claim_next(
            "future-local-claim",now=future))
        self.assertEqual(self.outbox.get(key)["state"],"UNCERTAIN")
        self.assertEqual(self.outbox.effect_count(),0)

    def test_01_existing_key_persists_after_restart_and_30_days(self):
        item=self.create()
        self.restart()
        replay=self.create(date=NOW+timedelta(days=30))
        self.assertEqual(replay["enqueue_state"],"IDEMPOTENT")
        self.assertEqual(replay["idempotency_key"],item["idempotency_key"])
        self.assertEqual(len(self.outbox.list()),1)
        self.assertEqual(self.outbox.effect_count(),0)

    def test_02_same_intent_still_idempotent_after_31_365_and_730_days(self):
        item=self.create()
        for days in (31,365,730):
            with self.subTest(days=days):
                self.restart()
                replay=self.create(date=NOW+timedelta(days=days))
                self.assertEqual(replay["enqueue_state"],"IDEMPOTENT")
                self.assertEqual(replay["idempotency_key"],item["idempotency_key"])
                self.assertEqual(len(self.outbox.list()),1)

    def test_03_payload_collision_denied_after_31_days_and_restart(self):
        self.create()
        self.restart()
        with self.assertRaisesRegex(ValueError,"idempotency collision"):
            self.create(date=NOW+timedelta(days=31),
                        payload={"to":"FAKE_OTHER_RECIPIENT","body":"FAKE_CHANGED"})
        self.assertEqual(len(self.outbox.list()),1)
        self.assertEqual(self.outbox.effect_count(),0)

    def test_04_action_collision_denied_even_after_365_days(self):
        self.create()
        self.restart()
        with self.assertRaisesRegex(ValueError,"idempotency collision"):
            self.create(action="send_whatsapp",date=NOW+timedelta(days=365))
        self.assertEqual(len(self.outbox.list()),1)

    def test_05_aggregate_collision_denied_after_31_days(self):
        self.create()
        self.restart()
        with self.assertRaisesRegex(ValueError,"idempotency collision"):
            self.create(aggregate="other-aggregate",
                        date=NOW+timedelta(days=31))
        self.assertEqual(len(self.outbox.list()),1)

    def test_06_uncertain_row_still_never_retry_claim_after_31_days(self):
        item=self.create()
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='UNCERTAIN' "
                "WHERE idempotency_key=?", (item["idempotency_key"],))
        self.restart()
        self.verify_quarantined(item["idempotency_key"],
                                future=NOW+timedelta(days=31))

    def test_07_uncertain_row_still_never_retry_claim_after_730_days(self):
        item=self.create()
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='UNCERTAIN' "
                "WHERE idempotency_key=?", (item["idempotency_key"],))
        self.restart()
        self.verify_quarantined(item["idempotency_key"],
                                future=NOW+timedelta(days=730))

    def test_08_repeated_enqueue_cannot_turn_uncertain_into_pending(self):
        item=self.create()
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='UNCERTAIN' "
                "WHERE idempotency_key=?", (item["idempotency_key"],))
        self.restart()
        replay=self.create(date=NOW+timedelta(days=365))
        self.assertEqual(replay["enqueue_state"],"IDEMPOTENT")
        self.assertEqual(replay["state"],"UNCERTAIN")
        self.verify_quarantined(item["idempotency_key"],
                                future=NOW+timedelta(days=365))

    def test_09_future_no_effect_callback_cannot_reconcile_unknown(self):
        item=self.create()
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='UNCERTAIN' "
                "WHERE idempotency_key=?", (item["idempotency_key"],))
        self.restart()
        adapter=_NoDescriptorAdapter()
        with self.assertRaisesRegex(
            PermissionError,"^INDEPENDENT_PRODUCER_NOT_ENROLLED$"):
            self.outbox.reconcile(
                item["idempotency_key"],adapter=adapter,
                authorize=lambda decision: {
                    "allowed":True,"authoritative_absence":True},
                now=NOW+timedelta(days=31))
        self.assertEqual(adapter.reads,0)
        self.verify_quarantined(item["idempotency_key"],
                                future=NOW+timedelta(days=31))

    def test_10_new_aggregate_intent_does_not_release_prior_ordinal(self):
        item=self.create()
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='UNCERTAIN' "
                "WHERE idempotency_key=?", (item["idempotency_key"],))
        followup=self.create(
            intent="notification-unique-456",date=NOW+timedelta(days=31))
        self.assertEqual(followup["decision"]["aggregate_seq"],2)
        self.assertIsNone(self.outbox.claim_next(
            "local-only",now=NOW+timedelta(days=31)))
        self.assertEqual(self.outbox.get(item["idempotency_key"])["state"],
                         "UNCERTAIN")
        self.assertEqual(self.outbox.effect_count(),0)

    def test_11_open_gap_lost_sqlite_history_reopens_same_logical_intent(self):
        # This is a *known danger demonstration*, not a success criterion
        # for production. Local-only idempotency cannot survive missing DB.
        first=self.create()
        self._close_if_open()
        lost=Path(self.temp.name)/"isolated_blank_db_after_loss.sqlite3"
        empty=SQLiteChatStore(lost)
        try:
            copied=ExecutionOutbox(empty,self.scope)
            date=NOW+timedelta(days=31)
            reused=copied.enqueue(
                intent_ref="notification-unique-123",action="send_sms",
                payload={"to":"FAKE_TEST_RECIPIENT","body":"FAKE_TEST_BODY"},
                aggregate_key="client-1",policy_version="policy-v1",
                authorization_ref="LAB_APPROVAL_NOT_REAL",
                created_at=date,valid_until=date+timedelta(minutes=5))
            self.assertEqual(first["idempotency_key"],
                             reused["idempotency_key"])
            self.assertEqual(reused["enqueue_state"],"ENQUEUED")
            self.assertEqual(reused["state"],"PENDING")
            self.assertEqual(copied.effect_count(),0)
        finally:
            empty.close()
        # Consequence: without an independent durable provider witness,
        # the local record cannot prove a prior send did or did not occur.

    def test_12_local_expiry_policy_does_not_create_independent_receipt(self):
        self.create()
        self.restart()
        self.assertEqual(self.outbox.effect_count(),0)
        self.assertEqual(self.store.db.execute(
            "SELECT count(*) FROM action_effects").fetchone()[0],0)


if __name__=="__main__":
    unittest.main()
