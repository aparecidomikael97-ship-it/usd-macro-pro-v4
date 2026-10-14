"""A63 LAB: reject stale Saga/Outbox snapshots before outcome mutation.

The Outbox is read before Saga's SQLite write lock. Tests interleave a local
SQLite write between the initial read and BEGIN IMMEDIATE. They do not call
provider adapters, enroll an independent producer or assert physical HUMAN_OWNER.
"""
import tempfile
import unittest
from unittest.mock import patch

import test_atlasquant_aion_execution_saga as historic


class A63SagaOutboxSnapshotRaceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = historic.ExecutionSagaTests()
        self.fixture.setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store, self.outbox, self.budget, self.saga = self.fixture._components(self.tmp.name)
        self.fixture._create(self.saga)
        self.staged = self.fixture._enqueue_forward(self.saga)
        self.key = self.staged["outbox"]["idempotency_key"]
        self.assertEqual(self.saga.integrity_report("saga-1")["state"], "MATCH")

    def snapshot(self):
        saga = self.saga.get("saga-1")
        return (
            saga["state"],
            tuple((row["step_key"], row["state"], row["effect_ref"], row["last_error"])
                  for row in saga["steps"]),
            self.saga.integrity_report("saga-1")["events"],
            self.outbox.effect_count(),
        )

    def interleave(self, alteration, *, min_reads=2):
        original_get = self.outbox.get
        called = [0]

        def read_then_change(key):
            result = original_get(key)
            called[0] += 1
            if called[0] == 1:
                self.assertEqual(key, self.key)
                alteration()
            return result

        with patch.object(self.outbox, "get", side_effect=read_then_change):
            with self.assertRaisesRegex(PermissionError, "SAGA_.*SNAPSHOT_STALE"):
                self.saga.sync_forward_outcome("saga-1", "one", now=historic.NOW)
        # A stale Saga snapshot is denied before a second Outbox fetch;
        # Outbox mutations still must trigger their own locked re-read.
        self.assertGreaterEqual(called[0], min_reads, "Insufficient reads for denial path")

    def test_01_pending_to_uncertain_cannot_be_overwritten_by_stale_read(self):
        before = self.snapshot()
        def change():
            with self.saga.db:
                self.saga.db.execute(
                    "UPDATE action_outbox SET state='UNCERTAIN' WHERE idempotency_key=?",
                    (self.key,),
                )
        self.interleave(change)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.outbox.get(self.key)["state"], "UNCERTAIN")

    def test_02_pending_to_revoked_cannot_be_overwritten_by_stale_read(self):
        before = self.snapshot()
        def change():
            with self.saga.db:
                self.saga.db.execute(
                    "UPDATE action_outbox SET state='REVOKED' WHERE idempotency_key=?",
                    (self.key,),
                )
        self.interleave(change)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.outbox.get(self.key)["state"], "REVOKED")

    def test_03_saga_metadata_changed_after_snapshot_is_rejected(self):
        before = self.snapshot()
        initial_updated = self.saga.get("saga-1")["updated_at"]
        def change():
            with self.saga.db:
                self.saga.db.execute(
                    "UPDATE aion_execution_sagas SET updated_at=? WHERE saga_id=?",
                    ("2026-10-14T23:11:59Z", "saga-1"),
                )
        self.interleave(change, min_reads=1)
        self.assertNotEqual(self.saga.get("saga-1")["updated_at"], initial_updated)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.saga.integrity_report("saga-1")["state"], "MATCH")

    def test_04_unchanged_pending_outbox_preserves_safe_diagnostic_path(self):
        report = self.saga.sync_forward_outcome("saga-1", "one", now=historic.NOW)
        self.assertEqual(report["state"], "RUNNING")
        self.assertFalse(report["executes_action"])
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertEqual(self.saga.integrity_report("saga-1")["state"], "MATCH")

    def test_05_forged_confirmed_still_rejected_before_any_effect(self):
        with self.saga.db:
            self.saga.db.execute(
                "UPDATE action_outbox SET state='CONFIRMED',effect_ref='A63_FAKE' WHERE idempotency_key=?",
                (self.key,),
            )
        before = self.snapshot()
        with self.assertRaisesRegex(PermissionError, "INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED"):
            self.saga.sync_forward_outcome("saga-1", "one", now=historic.NOW)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
