"""AION P0 LAB: Saga direct SQLite connection may not cross its owner's thread.

REAL A118 ExecutionSagaCoordinator with the already-guarded LAB SQLite store/
Outbox. Before a fix, Saga .db is accessed directly and sqlite3 raises
ProgrammingError. These immutable contracts require owner-thread denial BEFORE
any DB read/write, budget guard, transaction manipulation or effect ledger.
No provider, network, Worker, credentials or real effects.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from aion_chat.store import StorageUnavailableError, HEALTHY
import test_atlasquant_aion_execution_saga as historical

NOW = historical.NOW

DENIAL = "SQLITE_STORE_CONNECTION_THREAD_MISMATCH"


class P0SagaSQLiteOwnerThreadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="p0-saga-sqlite-owner-")
        self.addCleanup(self.temp.cleanup)
        self.fixture = historical.ExecutionSagaTests()
        self.fixture.setUp()
        self.store, self.outbox, self.budget, self.saga = self.fixture._components(self.temp.name)
        self.addCleanup(self.store.close)  # close before removing folder on Windows
        self.fixture._create(self.saga, saga_id="saga-lab")

    def snapshot(self):
        return (
            self.saga.get("saga-lab"),
            self.saga.integrity_report("saga-lab"),
            self.outbox.effect_count(),
            self.store.storage_health(deep=True)["state"],
        )

    def reject_foreign(self, call):
        before = self.snapshot()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.assertRaisesRegex(StorageUnavailableError, DENIAL):
                pool.submit(call).result(timeout=15)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.store.storage_health(deep=True)["state"], HEALTHY)

    def test_01_get_fails_before_direct_db_use(self):
        self.reject_foreign(lambda: self.saga.get("saga-lab"))

    def test_02_create_fails_before_read_or_mutation(self):
        self.reject_foreign(lambda: self.saga.create(
            saga_id="new-saga", steps=self.fixture._steps(), created_at=NOW
        ))

    def test_03_enqueue_next_fails_before_begin_immediate(self):
        self.reject_foreign(lambda: self.saga.enqueue_next(
            "saga-lab", authorization_ref="lab-authority",
            valid_until=NOW + timedelta(minutes=4), created_at=NOW
        ))

    def test_04_integrity_report_fails_before_event_chain_read(self):
        self.reject_foreign(lambda: self.saga.integrity_report("saga-lab"))

    def test_05_sync_forward_fails_before_outbox_read(self):
        self.reject_foreign(lambda: self.saga.sync_forward_outcome("saga-lab", "one", now=NOW))

    def test_06_prepare_compensation_denied_without_touching_sqlite(self):
        self.reject_foreign(lambda: self.saga.prepare_compensation(
            "saga-lab", explicit_human_approval=True,
            approval_ref="fixture-approval", reauth_ref="fixture-reauth", now=NOW
        ))

    def test_07_enqueue_compensation_denied_before_db(self):
        self.reject_foreign(lambda: self.saga.enqueue_next_compensation(
            "saga-lab", valid_until=NOW + timedelta(minutes=4), created_at=NOW
        ))

    def test_08_sync_compensation_denied_before_db(self):
        self.reject_foreign(lambda: self.saga.sync_compensation_outcome(
            "saga-lab", "one", now=NOW
        ))

    def test_09_authority_guard_denied_before_budget_on_foreign_thread(self):
        self.reject_foreign(lambda: self.saga.authority_guard({}, now=NOW))

    def test_10_wrong_thread_denial_preserves_outer_transaction_and_rows(self):
        self.store.db.execute(
            "CREATE TABLE IF NOT EXISTS p0_saga_thread_sentinel(note TEXT PRIMARY KEY)"
        )
        self.store.db.execute("BEGIN IMMEDIATE")
        try:
            self.store.db.execute(
                "INSERT INTO p0_saga_thread_sentinel(note) VALUES ('uncommitted')")
            with ThreadPoolExecutor(max_workers=1) as pool:
                with self.assertRaisesRegex(StorageUnavailableError, DENIAL):
                    pool.submit(lambda: self.saga.enqueue_next(
                        "saga-lab", authorization_ref="lab-authority",
                        valid_until=NOW + timedelta(minutes=4), created_at=NOW
                    )).result(timeout=15)
            self.assertTrue(self.store.db.in_transaction)
            self.assertEqual(self.store.db.execute(
                "SELECT COUNT(*) FROM p0_saga_thread_sentinel"
            ).fetchone()[0], 1)
            self.assertEqual(self.saga.get("saga-lab")["state"], "PLANNED")
        finally:
            self.store.db.rollback()
        self.assertEqual(self.store.storage_health(deep=True)["state"], HEALTHY)

    def test_11_new_store_outbox_budget_saga_within_other_thread_works(self):
        # A fresh SQLite connection constructed in its *own* worker thread is
        # permitted; reusing this thread's connection is what must be denied.
        def other_thread():
            store, outbox, budget, saga = self.fixture._components(self.temp.name)
            try:
                return saga.get("saga-lab")["state"], saga.integrity_report("saga-lab")["state"]
            finally:
                store.close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(other_thread).result(timeout=20)
        self.assertEqual(result, ("PLANNED", "MATCH"))

    def test_12_owner_thread_still_stages_once_with_original_no_provider_guard(self):
        staged = self.fixture._enqueue_forward(self.saga, saga_id="saga-lab")
        self.assertEqual(staged["state"], "ENQUEUED")
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertFalse(staged["executes_action"])
        self.assertEqual(self.saga.integrity_report("saga-lab")["state"], "MATCH")


if __name__ == "__main__":
    unittest.main()
