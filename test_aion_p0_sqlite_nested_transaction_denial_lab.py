"""AION P0 original Outbox SQLite nested-transaction boundary, RED->GREEN LAB.

The original claim_next calls release_expired_claims, which issues BEGIN
IMMEDIATE. Calling either inside a caller-owned SQLite transaction currently
raises a generic sqlite3.OperationalError. This suite demands an EXPLICIT
non-retryable denial and tests that the caller still owns the transaction.
No producer, adapter, network, real send or owner enrollment.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 19, 20, 30, tzinfo=timezone.utc)
SCOPE = Scope("p0-tx-owner", "p0-tx-tenant", "p0-tx-workspace")
DENIAL = "OUTBOX_NESTED_TRANSACTION_UNSUPPORTED"


class P0NestedTransactionSafeDenialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="p0-sqlite-nested-")
        self.addCleanup(self.temp.cleanup)
        self.store = SQLiteChatStore(Path(self.temp.name) / "outbox.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(self.store, SCOPE)
        self.key = self.outbox.enqueue(
            intent_ref="one-test-intent",
            action="synthetic_no_provider",
            payload={"sample": "only fixture"},
            aggregate_key="nested-transaction",
            policy_version="lab-v1",
            authorization_ref="lab-authorization",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )["idempotency_key"]
        with self.store.db:
            self.store.db.execute(
                "CREATE TABLE IF NOT EXISTS p0_nested_sentinel(id TEXT PRIMARY KEY)"
            )

    def start_caller_transaction(self):
        self.store.db.execute("BEGIN IMMEDIATE")
        self.store.db.execute(
            "INSERT INTO p0_nested_sentinel(id) VALUES (?)", ("caller-uncommitted",)
        )

    def assert_outer_preserved(self):
        self.assertTrue(self.store.db.in_transaction,
                        "the caller owns transaction; no implicit rollback or commit")
        count = self.store.db.execute(
            "SELECT COUNT(*) FROM p0_nested_sentinel WHERE id='caller-uncommitted'"
        ).fetchone()[0]
        self.assertEqual(count, 1)
        out = self.outbox.get(self.key)
        self.assertEqual((out["state"], out["attempts"]), ("PENDING", 0))

    def test_01_release_expired_claims_reports_explicit_denial_and_preserves_parent(self):
        self.start_caller_transaction()
        try:
            with self.assertRaisesRegex(RuntimeError, DENIAL):
                self.outbox.release_expired_claims(now=NOW + timedelta(seconds=4))
            self.assert_outer_preserved()
        finally:
            self.store.db.rollback()

    def test_02_claim_next_reports_explicit_denial_and_preserves_parent(self):
        self.start_caller_transaction()
        try:
            with self.assertRaisesRegex(RuntimeError, DENIAL):
                self.outbox.claim_next("worker-a", now=NOW + timedelta(seconds=4))
            self.assert_outer_preserved()
        finally:
            self.store.db.rollback()

    def test_03_savepoint_ownership_survives_denied_claim(self):
        self.store.db.execute("SAVEPOINT caller_savepoint")
        try:
            self.store.db.execute(
                "INSERT INTO p0_nested_sentinel(id) VALUES ('caller-savepoint-row')"
            )
            with self.assertRaisesRegex(RuntimeError, DENIAL):
                self.outbox.claim_next("worker-a", now=NOW + timedelta(seconds=1))
            self.assertTrue(self.store.db.in_transaction)
            self.assertEqual(self.store.db.execute(
                "SELECT count(*) FROM p0_nested_sentinel"
            ).fetchone()[0], 1)
            self.store.db.execute("ROLLBACK TO SAVEPOINT caller_savepoint")
            self.store.db.execute("RELEASE SAVEPOINT caller_savepoint")
        finally:
            if self.store.db.in_transaction:
                self.store.db.rollback()
        self.assertEqual(self.store.db.execute(
            "SELECT count(*) FROM p0_nested_sentinel"
        ).fetchone()[0], 0)

    def test_04_caller_can_commit_its_own_work_after_denial(self):
        self.start_caller_transaction()
        try:
            with self.assertRaisesRegex(RuntimeError, DENIAL):
                self.outbox.release_expired_claims(now=NOW)
            self.assert_outer_preserved()
            self.store.db.commit()
        finally:
            if self.store.db.in_transaction:
                self.store.db.rollback()
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM p0_nested_sentinel WHERE id='caller-uncommitted'"
        ).fetchone()[0], 1)
        self.assertEqual(self.outbox.get(self.key)["state"], "PENDING")

    def test_05_denial_preserves_existing_claim_lease_and_marker(self):
        before = self.outbox.claim_next(
            "first-worker", now=NOW + timedelta(seconds=1), lease_seconds=20
        )
        self.assertEqual(before["state"], "CLAIMED")
        self.store.db.execute("BEGIN IMMEDIATE")
        try:
            with self.assertRaisesRegex(RuntimeError, DENIAL):
                self.outbox.release_expired_claims(now=NOW + timedelta(minutes=2))
            self.assertTrue(self.store.db.in_transaction)
            self.assertEqual(self.outbox.get(self.key), before)
        finally:
            self.store.db.rollback()

    def test_06_ordinary_claim_from_fresh_transaction_still_succeeds_once(self):
        claimed = self.outbox.claim_next(
            "one-worker", now=NOW + timedelta(seconds=1), lease_seconds=20
        )
        self.assertEqual(claimed["state"], "CLAIMED")
        self.assertEqual(claimed["attempts"], 1)
        self.assertIsNone(self.outbox.claim_next(
            "two-worker", now=NOW + timedelta(seconds=2)
        ))
        self.assertEqual(self.outbox.get(self.key)["attempts"], 1)

    def test_07_outer_saga_style_enqueue_still_uses_existing_savepoint(self):
        self.store.db.execute("BEGIN IMMEDIATE")
        try:
            staged = self.outbox.enqueue(
                intent_ref="nested-extra",
                action="synthetic_only",
                payload={"local": True},
                aggregate_key="another-aggregate",
                policy_version="lab-v1",
                authorization_ref="lab-authorization",
                created_at=NOW,
                valid_until=NOW + timedelta(minutes=3),
            )
            self.assertEqual(staged["enqueue_state"], "ENQUEUED")
            self.assertTrue(self.store.db.in_transaction)
        finally:
            self.store.db.rollback()
        self.assertEqual(len(self.outbox.list()), 1)


if __name__ == "__main__":
    unittest.main()
