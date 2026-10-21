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

from test_atlasquant_aion_execution_saga import ExecutionSagaTests, FakeAdapter, NOW


class SagaUncertainProjectionRegressionLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fx = ExecutionSagaTests()
        self.fx.setUp()
        self.store, self.outbox, self.budget, self.saga = self.fx._components(self.tmp.name)
        self.addCleanup(self.store.close)
        self.fx._create(self.saga)
        self.fx._enqueue_forward(self.saga)
        self.adapter = FakeAdapter("lose-after-effect")
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


if __name__ == "__main__":
    unittest.main()
