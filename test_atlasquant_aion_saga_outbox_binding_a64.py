"""A64 LAB: Saga steps must not consume another Outbox decision."""
import json
import tempfile
import unittest
from datetime import timedelta

import test_atlasquant_aion_execution_saga as fx


class A64SagaOutboxBindingTests(unittest.TestCase):
    def setUp(self):
        self.f = fx.ExecutionSagaTests()
        self.f.setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store, self.outbox, self.budget, self.saga = self.f._components(self.tmp.name)
        # LIFO cleanup: close SQLite/WAL handles BEFORE removing temp folder (Windows).
        self.addCleanup(self.store.close)
        for sid in ("saga-1", "saga-2"):
            self.f._create(self.saga, saga_id=sid)
        self.one = self.f._enqueue_forward(self.saga, saga_id="saga-1")["outbox"]
        self.two = self.f._enqueue_forward(self.saga, saga_id="saga-2")["outbox"]

    def snapshot(self):
        s = self.saga.get("saga-1")
        return (s["state"], [(r["state"], r["effect_ref"], r["last_error"]) for r in s["steps"]],
                self.saga.integrity_report("saga-1")["events"], self.outbox.effect_count())

    def redirect(self, key):
        with self.saga.db:
            self.saga.db.execute(
                "UPDATE aion_execution_saga_steps SET outbox_key=? WHERE saga_id='saga-1' AND step_key='one'",
                (key,),
            )
        self.assertEqual(self.saga.integrity_report("saga-1")["state"], "MATCH")

    def deny(self):
        before = self.snapshot()
        with self.assertRaisesRegex(PermissionError, "SAGA_OUTBOX_BINDING_MISMATCH"):
            self.saga.sync_forward_outcome("saga-1", "one", now=fx.NOW)
        self.assertEqual(self.snapshot(), before)

    def test_01_other_saga_pending_cannot_be_consumed(self):
        self.redirect(self.two["idempotency_key"])
        self.deny()

    def test_02_other_saga_uncertain_cannot_set_reconciliation(self):
        key = self.two["idempotency_key"]
        with self.saga.db:
            self.saga.db.execute(
                "UPDATE action_outbox SET state='UNCERTAIN' WHERE idempotency_key=?", (key,))
        self.redirect(key)
        self.deny()

    def test_03_standalone_note_cannot_be_a_saga_intent(self):
        out = self.outbox.enqueue(
            intent_ref="a64-unrelated", action="create_crm_note",
            payload={"client":"c1", "note":"prepared"},
            aggregate_key="a64-other", policy_version="policy-v1",
            authorization_ref="approval-forward", created_at=fx.NOW,
            valid_until=fx.NOW + timedelta(minutes=5))
        self.redirect(out["idempotency_key"])
        self.deny()

    def test_04_locally_forged_decision_action_must_be_denied(self):
        d = self.outbox.get(self.one["idempotency_key"])
        forged = dict(d["decision"])
        forged["action"] = "A64_WRONG_ACTION"
        with self.saga.db:
            self.saga.db.execute("UPDATE action_decisions SET data=? WHERE decision_id=?",
                                 (json.dumps(forged, sort_keys=True), d["decision_id"]))
        self.deny()

    def test_05_legitimate_pending_still_returns_inert_diagnostic(self):
        out = self.saga.sync_forward_outcome("saga-1", "one", now=fx.NOW)
        self.assertEqual(out["state"], "RUNNING")
        self.assertFalse(out["executes_action"])
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_06_forged_confirmed_stays_producer_denied(self):
        key = self.one["idempotency_key"]
        with self.saga.db:
            self.saga.db.execute("UPDATE action_outbox SET state='CONFIRMED' WHERE idempotency_key=?", (key,))
        before = self.snapshot()
        with self.assertRaisesRegex(PermissionError, "INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED"):
            self.saga.sync_forward_outcome("saga-1", "one", now=fx.NOW)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
