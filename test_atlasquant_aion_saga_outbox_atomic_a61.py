"""A61 red-team: Saga forward staging and Outbox intent must commit atomically.

Fixtures use ephemeral SQLite, no independent producer or HUMAN_OWNER enrollment,
no network, no dispatch, no external action. Old tests remain untouched.
"""
import tempfile
import unittest
from datetime import timedelta
from unittest.mock import patch

import test_atlasquant_aion_execution_saga as historic


class A61SagaOutboxAtomicStagingTests(unittest.TestCase):
    def setUp(self):
        self.f = historic.ExecutionSagaTests()
        self.f.setUp()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store, self.outbox, self.budget, self.saga = self.f._components(self.temp.name)
        self.f._create(self.saga)

    def _snapshot(self):
        return {
            "decision_count": self.saga.db.execute(
                "SELECT count(*) FROM action_decisions"
            ).fetchone()[0],
            "outbox_count": self.saga.db.execute(
                "SELECT count(*) FROM action_outbox"
            ).fetchone()[0],
            "saga_state": self.saga.get("saga-1")["state"],
            "steps": [(r["step_key"], r["state"], r["outbox_key"])
                      for r in self.saga.get("saga-1")["steps"]],
            "events": self.saga.integrity_report("saga-1")["events"],
            "effect_count": self.outbox.effect_count(),
        }

    def _assert_unchanged_after_failure(self, before):
        self.assertEqual(self._snapshot(), before,
                         "Saga/Outbox partial local write survived failure")
        self.assertEqual(self.saga.integrity_report("saga-1")["state"], "MATCH")

    def test_01_event_append_failure_leaves_no_orphan_outbox_or_decision(self):
        before = self._snapshot()
        with patch.object(self.saga, "_append_event", side_effect=RuntimeError("A61_INJECT_EVENT")):
            with self.assertRaisesRegex(RuntimeError, "A61_INJECT_EVENT"):
                self.f._enqueue_forward(self.saga)
        self._assert_unchanged_after_failure(before)
        # Recovery is a fresh, inert staging attempt; never an adapter retry.
        out = self.f._enqueue_forward(self.saga)
        self.assertEqual(out["state"], "ENQUEUED")
        self.assertFalse(out["executes_action"])
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertEqual(self._snapshot()["outbox_count"], 1)

    def test_02_saga_projection_write_failure_leaves_no_orphan_outbox(self):
        self.saga.db.execute(
            """CREATE TRIGGER a61_inject_saga_update BEFORE UPDATE
               ON aion_execution_saga_steps
               BEGIN SELECT RAISE(ABORT, 'A61_INJECT_STEP_WRITE'); END"""
        )
        before = self._snapshot()
        with self.assertRaisesRegex(Exception, "A61_INJECT_STEP_WRITE"):
            self.f._enqueue_forward(self.saga)
        self._assert_unchanged_after_failure(before)

    def test_03_intact_forward_stages_one_local_intent_no_effect(self):
        before = self._snapshot()
        self.assertEqual(before["outbox_count"], 0)
        result = self.f._enqueue_forward(self.saga)
        self.assertFalse(result["executes_action"])
        self.assertEqual(self._snapshot()["outbox_count"], 1)
        self.assertEqual(self._snapshot()["decision_count"], 1)
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertEqual(self.saga.integrity_report("saga-1")["state"], "MATCH")

    def test_04_standalone_outbox_enqueue_remains_durable_and_idempotent(self):
        kwargs = {
            "intent_ref": "a61-standalone",
            "action": "record_internal_note",
            "payload": {"synthetic": True},
            "aggregate_key": "a61-local",
            "policy_version": "policy-v1",
            "authorization_ref": "approval-forward",
            "created_at": historic.NOW,
            "valid_until": historic.NOW + timedelta(minutes=5),
        }
        first = self.outbox.enqueue(**kwargs)
        second = self.outbox.enqueue(**kwargs)
        self.assertEqual(first["enqueue_state"], "ENQUEUED")
        self.assertEqual(second["enqueue_state"], "IDEMPOTENT")
        self.assertEqual(first["idempotency_key"], second["idempotency_key"])
        self.assertEqual(self._snapshot()["outbox_count"], 1)
        self.assertEqual(self.outbox.effect_count(), 0)


    def test_05_outer_transaction_rollback_cancels_nested_outbox_enqueue(self):
        kwargs = {
            "intent_ref": "a61-parent-rollback",
            "action": "record_internal_note",
            "payload": {"synthetic": True},
            "aggregate_key": "a61-parent-tx",
            "policy_version": "policy-v1",
            "authorization_ref": "approval-forward",
            "created_at": historic.NOW,
            "valid_until": historic.NOW + timedelta(minutes=5),
        }
        before = self._snapshot()
        self.saga.db.execute("BEGIN IMMEDIATE")
        try:
            staged = self.outbox.enqueue(**kwargs)
            self.assertEqual(staged["enqueue_state"], "ENQUEUED")
            self.assertTrue(self.saga.db.in_transaction)
            same = self.outbox.enqueue(**kwargs)
            self.assertEqual(same["enqueue_state"], "IDEMPOTENT")
        finally:
            self.saga.db.rollback()
        self._assert_unchanged_after_failure(before)

    def test_06_nested_enqueue_sql_failure_preserves_parent_transaction(self):
        self.saga.db.execute(
            """CREATE TRIGGER a61_inject_outbox_row BEFORE INSERT
               ON action_outbox BEGIN
               SELECT RAISE(ABORT, 'A61_INJECT_OUTBOX_WRITE');
               END"""
        )
        before = self._snapshot()
        self.saga.db.execute("BEGIN IMMEDIATE")
        try:
            with self.assertRaisesRegex(Exception, "A61_INJECT_OUTBOX_WRITE"):
                self.outbox.enqueue(
                    intent_ref="a61-nested-fail",
                    action="record_internal_note",
                    payload={"synthetic": True},
                    aggregate_key="a61-failed-tx",
                    policy_version="policy-v1",
                    authorization_ref="approval-forward",
                    created_at=historic.NOW,
                    valid_until=historic.NOW + timedelta(minutes=5),
                )
            # Failed SAVEPOINT must not abort the caller's outer transaction.
            self.assertTrue(self.saga.db.in_transaction)
            self.assertEqual(self._snapshot(), before)
        finally:
            self.saga.db.rollback()
        self._assert_unchanged_after_failure(before)


if __name__ == "__main__":
    unittest.main()
