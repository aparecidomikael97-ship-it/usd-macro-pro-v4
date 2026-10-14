"""A60 adversarial LAB: local Saga plan/event integrity before any staging.

Tests use an ephemeral SQLite store only. A local hash is not producer or
HUMAN_OWNER proof; this suite never enables outbox dispatch or real actions.
"""
import tempfile
import unittest

from test_atlasquant_aion_execution_saga import ExecutionSagaTests, NOW


class A60SagaPreEnqueueIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ExecutionSagaTests()
        self.fixture.setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store, self.outbox, self.budget, self.saga = (
            self.fixture._components(self.tmp.name)
        )
        self.created = self.fixture._create(self.saga)
        self.assertEqual(self.saga.integrity_report("saga-1")["state"], "MATCH")

    def _outbox_rows(self):
        return self.outbox.db.execute(
            "SELECT COUNT(*) FROM action_outbox"
        ).fetchone()[0]

    def _assert_not_enqueued(self):
        count_before = self._outbox_rows()
        with self.assertRaisesRegex(
            PermissionError, "SAGA_LOCAL_INTEGRITY_MISMATCH"
        ):
            self.fixture._enqueue_forward(self.saga)
        self.assertEqual(self._outbox_rows(), count_before)
        self.assertEqual(self.saga.get("saga-1")["state"], "PLANNED")

    def test_01_local_forged_step_action_must_not_enqueue(self):
        with self.saga.db:
            self.saga.db.execute(
                """UPDATE aion_execution_saga_steps SET action=?
                   WHERE saga_id=? AND step_key=?""",
                ("different_action_claim", "saga-1", "one"),
            )
        report = self.saga.integrity_report("saga-1")
        self.assertEqual(report["state"], "MISMATCH")
        self.assertIn("PLAN_DIGEST_MISMATCH", report["blockers"])
        self._assert_not_enqueued()

    def test_02_genesis_deleted_must_not_enqueue(self):
        with self.saga.db:
            self.saga.db.execute(
                "DELETE FROM aion_execution_saga_events WHERE saga_id=?",
                ("saga-1",),
            )
        report = self.saga.integrity_report("saga-1")
        self.assertEqual(report["state"], "MISMATCH")
        self.assertIn("EVENT_CHAIN_EMPTY", report["blockers"])
        self._assert_not_enqueued()

    def test_03_locally_rewritten_saga_state_without_event_must_not_enqueue(self):
        with self.saga.db:
            self.saga.db.execute(
                "UPDATE aion_execution_sagas SET state='RUNNING' WHERE saga_id=?",
                ("saga-1",),
            )
        report = self.saga.integrity_report("saga-1")
        self.assertEqual(report["state"], "MISMATCH")
        self.assertIn("LATEST_EVENT_STATE_MISMATCH", report["blockers"])
        self._assert_not_enqueued()

    def test_04_intact_plan_can_stage_first_step_but_not_execute_effect(self):
        self.assertEqual(self._outbox_rows(), 0)
        item = self.fixture._enqueue_forward(self.saga)
        self.assertEqual(item["state"], "ENQUEUED")
        self.assertFalse(item["executes_action"])
        self.assertEqual(self._outbox_rows(), 1)
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertEqual(self.saga.integrity_report("saga-1")["state"], "MATCH")


if __name__ == "__main__":
    unittest.main()
