"""A335 LAB: local Outbox terminal rows are NOT independent producer proof.

Every effect is synthetic. SyntheticFirstAttemptOutboxLab and explicit SQLite
fixture rows are confined to temporary test stores; no provider/network runs.
Neither a local CONFIRMED row nor FAILED proves COMMITTED_EFFECT/NO_EFFECT_FENCED.
"""
import tempfile
import unittest
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

import test_atlasquant_aion_execution_saga as fixture_module


class A335SagaUntrustedTerminalTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.ExecutionSagaTests()
        self.fixture.setUp()

    def test_forged_forward_confirmed_cannot_debit_authority_or_complete_saga(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, budget, saga = self.fixture._components(raw)
            try:
                self.fixture._create(saga)
                self.fixture._enqueue_forward(saga)
                result = self.fixture._dispatch_claimed(
                    outbox, budget, fixture_module.FakeAdapter(), offset=1
                )
                self.fixture._test_only_seed_hypothetical_confirmed(
                    outbox, result, when=fixture_module.NOW + timedelta(seconds=1)
                )
                before = deepcopy(saga.get("saga-1"))
                spent_before = budget.snapshot(
                    "saga-1", now=fixture_module.NOW + timedelta(seconds=2)
                )["transaction_effects"]
                with self.assertRaisesRegex(
                    PermissionError, "INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED"
                ):
                    saga.sync_forward_outcome(
                        "saga-1", "one",
                        now=fixture_module.NOW + timedelta(seconds=2),
                    )
                self.assertEqual(saga.get("saga-1"), before)
                self.assertEqual(
                    budget.snapshot("saga-1", now=fixture_module.NOW + timedelta(seconds=2))["transaction_effects"],
                    spent_before,
                )
                self.assertEqual(saga.integrity_report("saga-1")["state"], "MATCH")
            finally:
                store.close()

    def test_forged_forward_failed_requires_independent_no_effect_fence(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, budget, saga = self.fixture._components(raw)
            try:
                self.fixture._create(saga)
                self.fixture._enqueue_forward(saga)
                key = saga.get("saga-1")["steps"][0]["outbox_key"]
                with outbox.db:
                    cursor = outbox.db.execute(
                        """UPDATE action_outbox SET state='FAILED',last_error='LOCAL_CLAIM'
                           WHERE idempotency_key=? AND state='PENDING'""",
                        (key,),
                    )
                    self.assertEqual(cursor.rowcount, 1)
                before = deepcopy(saga.get("saga-1"))
                with self.assertRaisesRegex(
                    PermissionError, "INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED"
                ):
                    saga.sync_forward_outcome("saga-1", "one", now=fixture_module.NOW)
                self.assertEqual(saga.get("saga-1"), before)
                self.assertEqual(
                    budget.snapshot("saga-1", now=fixture_module.NOW)["transaction_effects"], 0
                )
            finally:
                store.close()

    def _compensation_view(self, saga):
        view = deepcopy(saga.get("saga-1"))
        view["steps"][0]["compensation_outbox_key"] = "fake-compensation-key"
        return view

    def test_forged_compensation_confirmed_cannot_record_budget_effect(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, budget, saga = self.fixture._components(raw)
            try:
                self.fixture._create(saga)
                view = self._compensation_view(saga)
                fake_out = {
                    "state": "CONFIRMED",
                    "effect_ref": "LOCAL-COMPENSATION-CLAIM",
                    "decision": {"transaction_id": "fake"},
                    "idempotency_key": "fake-compensation-key",
                    "confirmed_at": fixture_module.NOW.isoformat(),
                }
                with patch.object(saga, "get", return_value=view), patch.object(
                    outbox, "get", return_value=fake_out
                ), patch.object(
                    budget, "record_confirmed",
                    side_effect=AssertionError("A335_LEDGER_MUST_NOT_BE_WRITTEN"),
                ) as record:
                    with self.assertRaisesRegex(
                        PermissionError, "INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED"
                    ):
                        saga.sync_compensation_outcome(
                            "saga-1", "one", now=fixture_module.NOW
                        )
                    record.assert_not_called()
            finally:
                store.close()

    def test_forged_compensation_failed_cannot_claim_terminal_no_effect(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, budget, saga = self.fixture._components(raw)
            try:
                self.fixture._create(saga)
                view = self._compensation_view(saga)
                with patch.object(saga, "get", return_value=view), patch.object(
                    outbox, "get", return_value={
                        "state": "FAILED", "last_error": "LOCAL_NO_EFFECT_CLAIM"
                    },
                ):
                    with self.assertRaisesRegex(
                        PermissionError, "INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED"
                    ):
                        saga.sync_compensation_outcome(
                            "saga-1", "one", now=fixture_module.NOW
                        )
            finally:
                store.close()

    def test_forward_pending_remains_only_enqueued_not_effect_confirmed(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, budget, saga = self.fixture._components(raw)
            try:
                self.fixture._create(saga)
                self.fixture._enqueue_forward(saga)
                result = saga.sync_forward_outcome(
                    "saga-1", "one", now=fixture_module.NOW
                )
                self.assertEqual(result["step_state"], "ENQUEUED")
                self.assertEqual(result["state"], "RUNNING")
                self.assertEqual(
                    budget.snapshot("saga-1", now=fixture_module.NOW)["transaction_effects"], 0
                )
            finally:
                store.close()

    def test_compensation_uncertain_stays_reconciliation_required(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, budget, saga = self.fixture._components(raw)
            try:
                self.fixture._create(saga)
                view = self._compensation_view(saga)
                with patch.object(saga, "get", return_value=view), patch.object(
                    outbox, "get", return_value={"state": "UNCERTAIN"}
                ):
                    result = saga.sync_compensation_outcome(
                        "saga-1", "one", now=fixture_module.NOW
                    )
                self.assertEqual(result["state"], "RECONCILIATION_REQUIRED")
                self.assertEqual(result["step_state"], "UNCERTAIN")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
