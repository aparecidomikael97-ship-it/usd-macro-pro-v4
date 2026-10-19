"""P0 LAB: CAS, expired-lease, local FIFO and Saga retry/sequence recovery.

These are independent, no-provider regressions for invariants related to
32 still RED canonical Outbox/Saga errors. NOT a substitute for the original
test methods, independent receipts, external authority or Quality rebaseline.
No network access, Worker, provider adapter, synthetic verification override,
real dispatch or actual compensation is involved.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_saga_sequence_policy import (
    select_forward_step, select_compensation_step,
)
import test_atlasquant_aion_execution_saga as fx

NOW = fx.NOW


class OutboxCASRetryLocalLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "ledger.sqlite3"
        self.scope = Scope("cas-owner", "cas-tenant", "cas-workspace")
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(self.store, self.scope)

    def enqueue(self, reference="intent-1", aggregate="aggregate-1"):
        return self.outbox.enqueue(
            intent_ref=reference, action="stage_no_effect",
            payload={"fixture": True, "ref": reference},
            aggregate_key=aggregate, policy_version="policy-local",
            authorization_ref="approval-local-not-rooted",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        )

    def claim(self, worker="lab-claim", lease_seconds=10):
        return self.outbox.claim_next(
            worker, now=NOW + timedelta(seconds=1), lease_seconds=lease_seconds
        )

    def test_01_concurrent_independent_handles_only_one_claims(self):
        staged = self.enqueue()
        # Independent handles exercise SQLite BEGIN IMMEDIATE concurrency; no
        # Worker process, provider or adapter is ever constructed.
        self.store.close()
        def contender(n):
            local = SQLiteChatStore(self.path)
            try:
                return ExecutionOutbox(local, self.scope).claim_next(
                    "racer-" + str(n), now=NOW + timedelta(seconds=1),
                    lease_seconds=60,
                )
            finally:
                local.close()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(contender, range(8)))
        wins = [r for r in results if r is not None]
        self.assertEqual(len(wins), 1)
        self.assertEqual(wins[0]["idempotency_key"], staged["idempotency_key"])
        self.assertEqual(wins[0]["attempts"], 1)
        readback = SQLiteChatStore(self.path)
        try:
            check = ExecutionOutbox(readback, self.scope)
            self.assertEqual(check.effect_count(), 0)
            self.assertEqual(check.get(staged["idempotency_key"])["state"], "CLAIMED")
        finally:
            readback.close()

    def test_02_pre_effect_expired_claim_recycles_to_retry_only(self):
        staged = self.enqueue()
        before = self.claim(lease_seconds=3)
        self.assertEqual(before["attempts"], 1)
        released = self.outbox.release_expired_claims(now=NOW+timedelta(seconds=6))
        self.assertEqual(released, 1)
        retry = self.outbox.get(staged["idempotency_key"])
        self.assertEqual(retry["state"], "RETRY")
        self.assertEqual(retry["last_error"], "CLAIM_LEASE_EXPIRED_BEFORE_DISPATCH")
        reacquired = self.outbox.claim_next("new-local-claim",
            now=NOW+timedelta(seconds=7), lease_seconds=60)
        self.assertEqual(reacquired["idempotency_key"], staged["idempotency_key"])
        self.assertEqual(reacquired["attempts"], 2)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_03_expired_claim_with_fake_effect_row_never_retries(self):
        staged = self.enqueue()
        key = staged["idempotency_key"]
        self.claim(lease_seconds=3)
        with self.store.db:
            self.store.db.execute(
                """INSERT INTO action_effects(
                    idempotency_key,owner,tenant,workspace,effect_ref,
                    confirmed_at,data
                ) VALUES (?,?,?,?,?,?,?)""",
                (key, self.scope.owner_id, self.scope.tenant_id,
                 self.scope.workspace_id, "LOCAL-FORGED-NOT-TRUSTED",
                 NOW.isoformat(), "{}"))
        self.assertEqual(self.outbox.release_expired_claims(
            now=NOW+timedelta(seconds=6)), 0)
        self.assertEqual(self.outbox.get(key)["state"], "CLAIMED")
        self.assertEqual(self.outbox.get(key)["attempts"], 1)
        self.assertIsNone(self.outbox.claim_next(
            "not-allowed", now=NOW+timedelta(seconds=7)))
        self.assertEqual(self.outbox.effect_count(), 1)
        # This is a forged local row; never claim a real effect was sent.

    def test_04_expired_claim_with_dispatch_marker_never_retries(self):
        staged = self.enqueue()
        key = staged["idempotency_key"]
        self.claim(lease_seconds=3)
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET dispatch_started_at=? "
                "WHERE idempotency_key=?", (NOW.isoformat(),key))
        self.assertEqual(self.outbox.release_expired_claims(
            now=NOW+timedelta(seconds=6)), 0)
        self.assertEqual(self.outbox.get(key)["state"], "CLAIMED")
        self.assertIsNone(self.outbox.claim_next(
            "not-allowed", now=NOW+timedelta(seconds=7)))
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_05_stale_claim_lease_cannot_revoke_peer_claim(self):
        staged = self.enqueue()
        key=staged["idempotency_key"]
        expected = self.claim()
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET lease_until=? WHERE idempotency_key=?",
                ((NOW+timedelta(seconds=60)).isoformat(),key))
        with self.assertRaisesRegex(
            RuntimeError, "stale outbox state/lease"
        ):
            self.outbox._set_blocked(
                key, "REVOKED", "local fake late revocation", expected=expected)
        row=self.outbox.get(key)
        self.assertEqual(row["state"], "CLAIMED")
        self.assertEqual(row["lease_owner"], "lab-claim")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_06_deleted_predecessor_never_releases_aggregate_seq_two(self):
        first=self.enqueue("intent-1")
        second=self.enqueue("intent-2")
        self.assertEqual(self.outbox.get(second["idempotency_key"])["aggregate_seq"],2)
        # Adversarial SQLite-only deletion of old outbox row; no provider
        # proof or actual terminal receipt is ever implied.
        with self.store.db:
            self.store.db.execute("DELETE FROM action_outbox WHERE idempotency_key=?",
                                  (first["idempotency_key"],))
        self.assertIsNone(self.claim())
        self.assertEqual(self.outbox.get(second["idempotency_key"])["state"],"PENDING")
        self.assertEqual(self.outbox.effect_count(),0)

    def test_07_ambiguous_state_is_not_claimable_even_with_expired_lease(self):
        staged = self.enqueue()
        key=staged["idempotency_key"]
        self.claim(lease_seconds=3)
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='UNCERTAIN' "
                "WHERE idempotency_key=?", (key,))
        self.assertEqual(self.outbox.release_expired_claims(
            now=NOW+timedelta(seconds=6)),0)
        self.assertIsNone(self.outbox.claim_next("new-worker",
            now=NOW+timedelta(seconds=7)))
        self.assertEqual(self.outbox.get(key)["state"],"UNCERTAIN")
        self.assertEqual(self.outbox.effect_count(),0)


class SagaPureStateRecoveryLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fixture = fx.ExecutionSagaTests()
        self.fixture.setUp()
        self.store,self.outbox,self.budget,self.saga=self.fixture._components(
            self.tmp.name)
        self.addCleanup(self.store.close)
        self.fixture._create(self.saga)

    def stage(self, offset=0):
        return self.fixture._enqueue_forward(self.saga, offset=offset)

    def test_08_pure_selector_checks_order_not_producer_authority(self):
        rows=[
            {"ordinal":1,"state":"PENDING"},
            {"ordinal":2,"state":"PENDING"},
            {"ordinal":3,"state":"PENDING"},
        ]
        self.assertEqual(select_forward_step("PLANNED",rows),0)
        rows[0]["state"]="ENQUEUED"
        with self.assertRaisesRegex(ValueError,"previous saga step"):
            select_forward_step("RUNNING",rows)
        rows[0]["state"]="UNCERTAIN"
        with self.assertRaisesRegex(ValueError,"previous saga step"):
            select_forward_step("RUNNING",rows)
        rows[0]["state"]="CONFIRMED"
        self.assertEqual(select_forward_step("RUNNING",rows),1)
        # A selector accepting a synthetic CONFIRMED is not effect proof:
        # coordinator must keep its separate independent-receipt hardstop.

    def test_09_compensation_selector_reverse_order_only(self):
        rows=[
            {"ordinal":1,"state":"COMPENSATION_PENDING"},
            {"ordinal":2,"state":"COMPENSATION_PENDING"},
            {"ordinal":3,"state":"COMPENSATION_PENDING"},
        ]
        self.assertEqual(select_compensation_step("COMPENSATING",rows),2)
        rows[2]["state"]="COMPENSATION_ENQUEUED"
        with self.assertRaisesRegex(ValueError, "previous compensation"):
            select_compensation_step("COMPENSATING",rows)
        rows[2]["state"]="COMPENSATED"
        self.assertEqual(select_compensation_step("COMPENSATING",rows),1)
        with self.assertRaisesRegex(ValueError,"not in compensation mode"):
            select_compensation_step("RUNNING",rows)

    def test_10_locally_uncertain_forward_freezes_next_stage(self):
        staged=self.stage()
        key=staged["outbox"]["idempotency_key"]
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='UNCERTAIN',"
                "last_error='SYNTHETIC_AMBIGUOUS_NO_PRODUCER' "
                "WHERE idempotency_key=?", (key,))
        result=self.saga.sync_forward_outcome("saga-1","one",
            now=NOW+timedelta(seconds=1))
        self.assertEqual(result["state"],"RECONCILIATION_REQUIRED")
        self.assertFalse(result["executes_action"])
        with self.assertRaises(ValueError):
            self.stage(offset=2)
        self.assertEqual(len(self.outbox.list()),1)
        self.assertEqual(self.outbox.effect_count(),0)

    def test_11_forged_local_confirmed_cannot_stage_next_step(self):
        staged=self.stage()
        key=staged["outbox"]["idempotency_key"]
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='CONFIRMED',"
                "effect_ref='LOCAL-FORGED' WHERE idempotency_key=?", (key,))
            self.store.db.execute(
                "UPDATE aion_execution_saga_steps SET state='CONFIRMED' "
                "WHERE saga_id='saga-1' AND step_key='one'")
        with self.assertRaisesRegex(
            PermissionError,"INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED"
        ):
            self.stage(offset=2)
        self.assertEqual(len(self.outbox.list()),1)
        self.assertEqual(self.outbox.effect_count(),0)

    def test_12_untrusted_rollback_both_saga_and_outbox(self):
        # Fail during the event write, after Outbox enqueue and Saga step
        # update, to verify whole transaction restoration.
        with self.store.db:
            self.store.db.execute("""
                CREATE TRIGGER lab_denied_event
                BEFORE INSERT ON aion_execution_saga_events
                BEGIN SELECT RAISE(ABORT,'lab event rollback'); END;
            """)
        with self.assertRaisesRegex(sqlite3.IntegrityError,"lab event rollback"):
            self.stage()
        self.assertEqual(self.saga.get("saga-1")["state"],"PLANNED")
        self.assertEqual(self.saga.get("saga-1")["steps"][0]["state"],"PENDING")
        self.assertEqual(len(self.outbox.list()),0)
        self.assertEqual(self.outbox.effect_count(),0)


if __name__ == "__main__":
    unittest.main()
