"""A114 LAB: local Saga projection/plan mismatch cannot be treated as authentic.

This tests ONLY synthetic SQLite tampering; no producer, Worker or external send.
It does not provide independent F1/T1, H0 or F2 evidence.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import test_atlasquant_aion_execution_saga as old


class A114SagaProjectionIntegrityTests(TestCase):
    def setUp(self):
        self.fixture = old.ExecutionSagaTests(methodName="test_event_chain_detects_tamper")
        self.fixture.setUp()
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store, self.outbox, self.budget, self.saga = self.fixture._components(
            self.tmp.name
        )
        self.addCleanup(self.store.close)
        self.saga_id = "saga-1"
        self.fixture._create(self.saga)
        self.assertEqual(self.saga.integrity_report(self.saga_id)["state"], "MATCH")

    def unchanged_counts(self):
        return (
            self.saga.db.execute(
                "SELECT COUNT(*) FROM aion_execution_saga_events WHERE saga_id=?",
                (self.saga_id,)
            ).fetchone()[0],
            self.saga.db.execute(
                "SELECT COUNT(*) FROM action_outbox"
            ).fetchone()[0],
            self.outbox.effect_count(),
        )

    def stage_first(self):
        result = self.fixture._enqueue_forward(self.saga)
        self.assertEqual(result["state"], "ENQUEUED")
        self.assertEqual(self.saga.integrity_report(self.saga_id)["state"], "MATCH")
        return result

    def test_01_pending_step_with_bound_outbox_key_must_break_integrity(self):
        first = self.stage_first()
        first_key = first["outbox"]["idempotency_key"]
        with self.saga.db:
            self.saga.db.execute(
                "UPDATE aion_execution_saga_steps SET state='PENDING' "
                "WHERE saga_id=? AND step_key='one'",
                (self.saga_id,)
            )
        self.assertEqual(
            self.saga.get(self.saga_id)["steps"][0]["outbox_key"], first_key
        )
        before = self.unchanged_counts()
        report = self.saga.integrity_report(self.saga_id)
        self.assertEqual(report["state"], "MISMATCH")
        self.assertIn("PENDING_STEP_HAS_OUTBOX_BINDING", report["blockers"])
        with self.assertRaisesRegex(PermissionError, "SAGA_LOCAL_INTEGRITY_MISMATCH"):
            self.fixture._enqueue_forward(self.saga)
        self.assertEqual(self.unchanged_counts(), before)

    def test_02_enqueued_step_without_outbox_binding_must_break_integrity(self):
        self.stage_first()
        with self.saga.db:
            self.saga.db.execute(
                "UPDATE aion_execution_saga_steps SET outbox_key='' "
                "WHERE saga_id=? AND step_key='one'",
                (self.saga_id,)
            )
        report = self.saga.integrity_report(self.saga_id)
        self.assertEqual(report["state"], "MISMATCH")
        self.assertIn("ENQUEUED_STEP_WITHOUT_OUTBOX_BINDING", report["blockers"])

    def test_03_existing_idempotent_create_denied_if_event_chain_deleted(self):
        with self.saga.db:
            self.saga.db.execute(
                "DELETE FROM aion_execution_saga_events WHERE saga_id=?",
                (self.saga_id,)
            )
        before = self.unchanged_counts()
        with self.assertRaisesRegex(PermissionError, "SAGA_LOCAL_INTEGRITY_MISMATCH"):
            self.fixture._create(self.saga)
        self.assertEqual(self.unchanged_counts(), before)

    def test_04_existing_idempotent_create_denied_if_state_forged(self):
        with self.saga.db:
            self.saga.db.execute(
                "UPDATE aion_execution_sagas SET state='COMPLETED' WHERE saga_id=?",
                (self.saga_id,)
            )
        before = self.unchanged_counts()
        with self.assertRaisesRegex(PermissionError, "SAGA_LOCAL_INTEGRITY_MISMATCH"):
            self.fixture._create(self.saga)
        self.assertEqual(self.unchanged_counts(), before)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_05_existing_intact_saga_is_still_idempotent(self):
        original = self.saga.get(self.saga_id)
        before = self.unchanged_counts()
        returned = self.fixture._create(self.saga)
        self.assertEqual(returned["create_state"], "IDEMPOTENT")
        self.assertEqual(returned["saga_id"], original["saga_id"])
        self.assertEqual(self.unchanged_counts(), before)

    def test_06_clean_first_stage_preserves_integrity_and_is_inert(self):
        before = self.unchanged_counts()
        first = self.stage_first()
        self.assertEqual(first["outbox"]["state"], "PENDING")
        self.assertIs(first["executes_action"], False)
        self.assertEqual(self.saga.integrity_report(self.saga_id)["state"], "MATCH")
        self.assertEqual(self.outbox.effect_count(), 0)
        after = self.unchanged_counts()
        self.assertEqual(after[0], before[0] + 1)
        self.assertEqual(after[1], before[1] + 1)


if __name__ == "__main__":
    import unittest
    unittest.main()
