"""A62 LAB: untrusted SQLite Saga outcomes must not promote state.

Only ephemeral SQLite / actual Saga+Outbox code. Does not simulate a genuine
HUMAN_OWNER presence, independent producer receipts or a trusted witness.
No network and no external actions.
"""
import tempfile
import unittest
from datetime import timedelta

import test_atlasquant_aion_execution_saga as historic


class A62UntrustedSagaOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.f = historic.ExecutionSagaTests()
        self.f.setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store, self.outbox, self.budget, self.saga = self.f._components(self.tmp.name)
        self.f._create(self.saga)
        self.first = self.f._enqueue_forward(self.saga)
        self.assertEqual(self.saga.integrity_report("saga-1")["state"], "MATCH")

    def _state(self):
        saga = self.saga.get("saga-1")
        return {
            "saga_state": saga["state"],
            "steps": [(s["step_key"], s["state"], s["outbox_key"],
                       s["compensation_outbox_key"], s["effect_ref"])
                      for s in saga["steps"]],
            "events": self.saga.integrity_report("saga-1")["events"],
            "outbox_count": self.outbox.db.execute(
                "SELECT count(*) FROM action_outbox"
            ).fetchone()[0],
            "budget_effects": self.outbox.effect_count(),
        }

    def _expect_denial_without_mutation(self, method, match):
        before = self._state()
        with self.assertRaisesRegex(PermissionError, match):
            method()
        self.assertEqual(self._state(), before)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_01_changed_forward_plan_must_not_append_outcome(self):
        with self.saga.db:
            self.saga.db.execute(
                """UPDATE aion_execution_saga_steps SET action=?
                   WHERE saga_id=? AND step_key=?""",
                ("forged_action_after_staging", "saga-1", "one"),
            )
        self.assertIn("PLAN_DIGEST_MISMATCH",
                      self.saga.integrity_report("saga-1")["blockers"])
        self._expect_denial_without_mutation(
            lambda: self.saga.sync_forward_outcome("saga-1", "one", now=historic.NOW),
            "SAGA_LOCAL_INTEGRITY_MISMATCH",
        )

    def test_02_missing_genesis_must_not_append_forward_outcome(self):
        with self.saga.db:
            self.saga.db.execute(
                "DELETE FROM aion_execution_saga_events WHERE saga_id=?",
                ("saga-1",),
            )
        self.assertEqual(self.saga.integrity_report("saga-1")["state"], "MISMATCH")
        self._expect_denial_without_mutation(
            lambda: self.saga.sync_forward_outcome("saga-1", "one", now=historic.NOW),
            "SAGA_LOCAL_INTEGRITY_MISMATCH",
        )

    def _forge_local_compensation_binding(self, outbox_state):
        # A standalone inert note is NOT a compensation or producer receipt.
        row = self.outbox.enqueue(
            intent_ref="a62-fake-local-compensation",
            action="never_dispatch_local_test",
            payload={"fake": True},
            aggregate_key="a62-local",
            policy_version="policy-v1",
            authorization_ref="self-asserted-local",
            created_at=historic.NOW,
            valid_until=historic.NOW + timedelta(minutes=5),
        )
        with self.saga.db:
            self.saga.db.execute(
                """UPDATE aion_execution_saga_steps
                   SET state='COMPENSATION_ENQUEUED',compensation_outbox_key=?
                   WHERE saga_id=? AND step_key=?""",
                (row["idempotency_key"], "saga-1", "one"),
            )
            self.saga.db.execute(
                "UPDATE action_outbox SET state=? WHERE idempotency_key=?",
                (outbox_state, row["idempotency_key"]),
            )
        self.assertEqual(self.outbox.effect_count(), 0)
        return row

    def test_03_forged_compensation_revoked_must_not_escalate_saga_state(self):
        self._forge_local_compensation_binding("REVOKED")
        self._expect_denial_without_mutation(
            lambda: self.saga.sync_compensation_outcome("saga-1", "one", now=historic.NOW),
            "INDEPENDENT_PRODUCER_COMPENSATION_NOT_ENROLLED",
        )

    def test_04_forged_compensation_uncertain_must_not_promote_state(self):
        self._forge_local_compensation_binding("UNCERTAIN")
        self._expect_denial_without_mutation(
            lambda: self.saga.sync_compensation_outcome("saga-1", "one", now=historic.NOW),
            "INDEPENDENT_PRODUCER_COMPENSATION_NOT_ENROLLED",
        )

    def test_05_forward_blocked_producer_remains_inert_diagnostic(self):
        with self.saga.db:
            self.saga.db.execute(
                """UPDATE action_outbox SET state='BLOCKED_PRODUCER',
                   last_error='INDEPENDENT_PRODUCER_NOT_ENROLLED'
                   WHERE idempotency_key=?""",
                (self.first["outbox"]["idempotency_key"],),
            )
        report = self.saga.sync_forward_outcome("saga-1", "one", now=historic.NOW)
        self.assertEqual(report["state"], "PRODUCER_ENROLLMENT_REQUIRED")
        self.assertFalse(report["executes_action"])
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertEqual(self.saga.integrity_report("saga-1")["state"], "MATCH")

    def test_06_forged_forward_confirmed_remains_producer_denied(self):
        with self.saga.db:
            self.saga.db.execute(
                "UPDATE action_outbox SET state='CONFIRMED',effect_ref=? WHERE idempotency_key=?",
                ("A62_FAKE_LOCAL_EFFECT", self.first["outbox"]["idempotency_key"]),
            )
        self._expect_denial_without_mutation(
            lambda: self.saga.sync_forward_outcome("saga-1", "one", now=historic.NOW),
            "INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED",
        )


if __name__ == "__main__":
    unittest.main()
