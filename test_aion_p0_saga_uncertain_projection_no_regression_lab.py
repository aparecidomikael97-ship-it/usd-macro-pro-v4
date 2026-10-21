"""AION P0/H0 RED->GREEN: never downgrade Saga uncertainty via local Outbox rollback.

These tests use the *real* Saga coordinator and Outbox, and a temporary
SQLite database. First-dispatch is denied by the production NO-PRODUCER gate.
The staged UNCERTAIN state is a test fixture, not evidence of external effect.
No adapter sends, no worker, and no compensating activity are permitted.
"""
from __future__ import annotations

from datetime import timedelta
import tempfile
import unittest

import test_atlasquant_aion_execution_saga as saga_fixtures

NOW = saga_fixtures.NOW


class SagaUncertainProjectionRegressionLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fx = saga_fixtures.ExecutionSagaTests()
        self.fx.setUp()
        self.store, self.outbox, self.budget, self.saga = self.fx._components(self.tmp.name)
        self.addCleanup(self.store.close)
        self.fx._create(self.saga)
        self.fx._enqueue_forward(self.saga)
        self.adapter = saga_fixtures.FakeAdapter("lose-after-effect")
        observed = self.fx._dispatch_claimed(
            self.outbox, self.budget, self.adapter, offset=1,
        )
        self.key = observed["idempotency_key"]
        self.assertEqual(observed["state"], "UNCERTAIN")
        self.assertEqual(self.adapter.send_calls, 0)
        once = self.saga.sync_forward_outcome(
            "saga-1", "one", now=NOW + timedelta(seconds=2),
        )
        self.assertEqual(once["state"], "RECONCILIATION_REQUIRED")
        self.assertEqual(once["step_state"], "UNCERTAIN")
        self.assertEqual(self.outbox.effect_count(), 0)

    def _attempt_projection_rollback(self, unsafe_state: str):
        # This local-only mutation represents a historical file/row rollback.
        # It cannot prove external no-effect, and cannot be used as a receipt.
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state=?,lease_owner='',lease_until='',"
                "dispatch_started_at='',sent_at='',confirmed_at='',effect_ref='' "
                "WHERE idempotency_key=?",
                (unsafe_state, self.key),
            )
        before_saga = self.saga.get("saga-1")
        before_outbox = self.outbox.get(self.key)
        before_budget = self.budget.snapshot(
            "saga-1", now=NOW + timedelta(seconds=3),
        )
        with self.assertRaisesRegex(
            PermissionError, "SAGA_UNCERTAIN_HISTORY_REGRESSION_NO_EXTERNAL_FENCE",
        ):
            self.saga.sync_forward_outcome(
                "saga-1", "one", now=NOW + timedelta(seconds=3),
            )
        self.assertEqual(self.saga.get("saga-1"), before_saga)
        self.assertEqual(self.outbox.get(self.key), before_outbox)
        self.assertEqual(self.budget.snapshot(
            "saga-1", now=NOW + timedelta(seconds=3),
        ), before_budget)
        self.assertEqual(before_saga["state"], "RECONCILIATION_REQUIRED")
        self.assertEqual(before_saga["steps"][0]["state"], "UNCERTAIN")
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertEqual(self.adapter.send_calls, 0)
        with self.assertRaisesRegex(ValueError, "state does not allow"):
            self.fx._enqueue_forward(self.saga, offset=4)

    def test_01_uncertain_saga_cannot_downgrade_to_pending_projection(self):
        self._attempt_projection_rollback("PENDING")

    def test_02_uncertain_saga_cannot_downgrade_to_retry_projection(self):
        self._attempt_projection_rollback("RETRY")

    def test_03_uncertain_saga_cannot_downgrade_to_claimed_projection(self):
        self._attempt_projection_rollback("CLAIMED")

    def test_04_repeated_uncertain_observation_stays_blocked_not_resendable(self):
        before = self.saga.get("saga-1")
        again = self.saga.sync_forward_outcome(
            "saga-1", "one", now=NOW + timedelta(seconds=3),
        )
        self.assertEqual(again["state"], "RECONCILIATION_REQUIRED")
        self.assertEqual(again["step_state"], "UNCERTAIN")
        self.assertEqual(self.saga.get("saga-1")["state"], before["state"])
        self.assertEqual(self.outbox.get(self.key)["state"], "UNCERTAIN")
        self.assertIsNone(self.outbox.claim_next(
            "worker-2", now=NOW + timedelta(seconds=4),
        ))
        self.assertEqual(self.adapter.send_calls, 0)
        self.assertEqual(self.outbox.effect_count(), 0)


class SagaMissingProducerProjectionRegressionLAB(unittest.TestCase):
    """A real BLOCKED_PRODUCER incident cannot become a new local claim."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fx = saga_fixtures.ExecutionSagaTests()
        self.fx.setUp()
        self.store, self.outbox, self.budget, self.saga = self.fx._components(self.tmp.name)
        self.addCleanup(self.store.close)
        self.fx._create(self.saga)
        self.fx._enqueue_forward(self.saga)
        self.key = self.saga.get("saga-1")["steps"][0]["outbox_key"]
        self.adapter = saga_fixtures.FakeAdapter()
        claimed = self.outbox.claim_next(
            "worker-1", now=NOW + timedelta(seconds=1),
        )
        self.assertEqual(claimed["idempotency_key"], self.key)
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$",
        ):
            self.outbox.dispatch_claimed(
                self.key, worker_id="worker-1",
                authorize=saga_fixtures.policy(self.fx.scope),
                adapter=self.adapter,
                cumulative_authority_guard=lambda d: self.budget.guard(
                    d, now=NOW + timedelta(seconds=1),
                ),
                now=NOW + timedelta(seconds=1),
            )
        self.assertEqual(self.outbox.get(self.key)["state"], "BLOCKED_PRODUCER")
        self.assertEqual(self.adapter.send_calls, 0)
        synced = self.saga.sync_forward_outcome(
            "saga-1", "one", now=NOW + timedelta(seconds=2),
        )
        self.assertEqual(synced["state"], "PRODUCER_ENROLLMENT_REQUIRED")
        self.assertEqual(synced["step_state"], "BLOCKED_PRODUCER")

    def _verify_no_revival(self, earlier_state):
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state=?,lease_owner='',lease_until='',"
                "dispatch_started_at='',sent_at='',confirmed_at='',effect_ref='' "
                "WHERE idempotency_key=?",
                (earlier_state, self.key),
            )
        before = self.saga.get("saga-1")
        budget_before = self.budget.snapshot(
            "saga-1", now=NOW + timedelta(seconds=3),
        )
        with self.assertRaisesRegex(
            PermissionError, "SAGA_UNCERTAIN_HISTORY_REGRESSION_NO_EXTERNAL_FENCE",
        ):
            self.saga.sync_forward_outcome(
                "saga-1", "one", now=NOW + timedelta(seconds=3),
            )
        self.assertEqual(self.saga.get("saga-1"), before)
        self.assertEqual(self.budget.snapshot(
            "saga-1", now=NOW + timedelta(seconds=3),
        ), budget_before)
        self.assertEqual(self.saga.get("saga-1")["state"], "PRODUCER_ENROLLMENT_REQUIRED")
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertEqual(self.adapter.send_calls, 0)
        with self.assertRaisesRegex(ValueError, "state does not allow"):
            self.fx._enqueue_forward(self.saga, offset=4)

    def test_05_blocked_producer_cannot_downgrade_to_pending(self):
        self._verify_no_revival("PENDING")

    def test_06_blocked_producer_cannot_downgrade_to_retry(self):
        self._verify_no_revival("RETRY")

    def test_07_blocked_producer_cannot_downgrade_to_claimed(self):
        self._verify_no_revival("CLAIMED")


if __name__ == "__main__":
    unittest.main()
