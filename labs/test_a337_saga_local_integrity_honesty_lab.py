"""A337 LAB: local Saga event hashes are not independent antirollback proof.

Every case mutates only test-owned temporary SQLite. No provider, network,
signed producer receipt, independent witness, owner ceremony, or real effect.
"""
from contextlib import contextmanager
from tempfile import TemporaryDirectory
import unittest

import test_atlasquant_aion_execution_saga as fixtures


SAGA_ID = "saga-1"


class A337SagaLocalChainHonestyTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ExecutionSagaTests()
        self.fixture.setUp()

    @contextmanager
    def lab(self):
        with TemporaryDirectory() as directory:
            store, outbox, budget, saga = self.fixture._components(directory)
            try:
                self.fixture._create(saga)
                yield store, outbox, budget, saga
            finally:
                store.close()

    def _report_readonly(self, saga):
        changes = saga.db.total_changes
        report = saga.integrity_report(SAGA_ID)
        self.assertEqual(saga.db.total_changes, changes)
        return report

    def test_01_deleted_entire_chain_is_mismatch_not_vacuous_match(self):
        with self.lab() as (store, _outbox, _budget, saga):
            self.assertEqual(saga.integrity_report(SAGA_ID)["state"], "MATCH")
            with store.db:
                store.db.execute(
                    "DELETE FROM aion_execution_saga_events WHERE saga_id=?",
                    (SAGA_ID,),
                )
            report = self._report_readonly(saga)
            self.assertEqual(report["state"], "MISMATCH")
            self.assertIn("EVENT_CHAIN_EMPTY", report["blockers"])
            self.assertEqual(report["events"], 0)
            self.assertIs(report["independent_witness_verified"], False)

    def test_02_truncated_running_tail_cannot_be_reported_intact(self):
        with self.lab() as (store, _outbox, _budget, saga):
            self.fixture._enqueue_forward(saga)
            self.assertEqual(saga.integrity_report(SAGA_ID)["state"], "MATCH")
            with store.db:
                store.db.execute(
                    "DELETE FROM aion_execution_saga_events WHERE saga_id=? AND sequence=2",
                    (SAGA_ID,),
                )
            self.assertEqual(saga.get(SAGA_ID)["state"], "RUNNING")
            report = self._report_readonly(saga)
            self.assertEqual(report["state"], "MISMATCH")
            self.assertIn("LATEST_EVENT_STATE_MISMATCH", report["blockers"])
            self.assertIs(report["authorizes_execution"], False)

    def test_03_direct_state_rewrite_must_mismatch_latest_local_event(self):
        with self.lab() as (store, _outbox, _budget, saga):
            with store.db:
                store.db.execute(
                    "UPDATE aion_execution_sagas SET state='COMPLETED' WHERE saga_id=?",
                    (SAGA_ID,),
                )
            report = self._report_readonly(saga)
            self.assertEqual(report["state"], "MISMATCH")
            self.assertIn("LATEST_EVENT_STATE_MISMATCH", report["blockers"])
            self.assertIs(report["producer_effect_verified"], False)

    def test_04_missing_genesis_event_is_explicitly_reported(self):
        with self.lab() as (store, _outbox, _budget, saga):
            self.fixture._enqueue_forward(saga)
            with store.db:
                store.db.execute(
                    "DELETE FROM aion_execution_saga_events WHERE saga_id=? AND sequence=1",
                    (SAGA_ID,),
                )
            report = self._report_readonly(saga)
            self.assertEqual(report["state"], "MISMATCH")
            self.assertIn("GENESIS_EVENT_MISSING", report["blockers"])

    def test_05_intact_genesis_is_local_consistency_only(self):
        with self.lab() as (_store, _outbox, _budget, saga):
            report = self._report_readonly(saga)
            self.assertEqual(report["state"], "MATCH")
            self.assertEqual(report["events"], 1)
            self.assertEqual(report["proof_scope"], "LOCAL_SQLITE_CHAIN_ONLY")
            self.assertIs(report["independent_witness_verified"], False)
            self.assertIs(report["producer_effect_verified"], False)
            self.assertIs(report["authorizes_execution"], False)
            self.assertIs(report["executes_action"], False)

    def test_06_intact_running_chain_still_has_no_external_witness(self):
        with self.lab() as (_store, _outbox, budget, saga):
            self.fixture._enqueue_forward(saga)
            report = self._report_readonly(saga)
            self.assertEqual(report["state"], "MATCH")
            self.assertEqual(report["events"], 2)
            self.assertEqual(report["proof_scope"], "LOCAL_SQLITE_CHAIN_ONLY")
            self.assertIs(report["independent_witness_verified"], False)
            self.assertIs(report["authorizes_execution"], False)
            self.assertEqual(
                budget.snapshot(SAGA_ID, now=fixtures.NOW)["transaction_effects"], 0,
            )


if __name__ == "__main__":
    unittest.main()
