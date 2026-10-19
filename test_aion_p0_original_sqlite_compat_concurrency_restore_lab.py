"""AION P0 original SQLite compatibility, concurrent claim and rollback audit.

Tests execute REAL A118 SQLiteChatStore/ExecutionOutbox methods in temp folders.
No provider, adapter, network, owner credential, Worker, send or merge.
Two intentionally reproduced limitations are not counted as fixed:
  1. A single SQLite connection is bound to its constructing thread;
  2. Outbox claim nested under an existing transaction is explicitly denied.
And restore_from_backup validates SQLite integrity, NOT an independent action
high-water mark: restoring an old *valid* DB loses later UNCERTAIN evidence.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 19, 20, 0, tzinfo=timezone.utc)
SCOPE = Scope("p0-sqlite-owner", "p0-sqlite-tenant", "p0-sqlite-workspace")


class P0OriginalSQLiteCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aion-p0-sqlite-compat-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "original.sqlite3"
        store, outbox = self.open_store()
        self.key = outbox.enqueue(
            intent_ref="p0-first-original-intent",
            action="synthetic_no_provider",
            payload={"purpose": "compatibility-proof"},
            aggregate_key="p0-aggregate",
            policy_version="fixture-only-policy",
            authorization_ref="fixture-only-approval",
            valid_until=NOW + timedelta(minutes=5),
            created_at=NOW,
        )["idempotency_key"]
        store.close()

    def open_store(self, scope=SCOPE):
        store = SQLiteChatStore(self.path)
        return store, ExecutionOutbox(store, scope)

    def test_01_original_two_independent_connections_claim_only_once(self):
        barrier = threading.Barrier(2)
        def competitor(label):
            store, outbox = self.open_store()
            try:
                barrier.wait(timeout=10)
                claim = outbox.claim_next(label, now=NOW + timedelta(seconds=1), lease_seconds=60)
                return None if claim is None else (claim["idempotency_key"], claim["state"], claim["lease_owner"])
            finally:
                store.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(competitor, "worker-" + str(i)) for i in range(2)]
            results = [future.result(timeout=20) for future in futures]
        winners = [r for r in results if r is not None]
        self.assertEqual(len(winners), 1, results)
        self.assertEqual(winners[0][0], self.key)
        self.assertEqual(winners[0][1], "CLAIMED")
        store, outbox = self.open_store()
        self.assertEqual(outbox.get(self.key)["attempts"], 1)
        store.close()

    def test_02_expired_pre_dispatch_lease_reclaims_once_only(self):
        store, outbox = self.open_store()
        row = outbox.claim_next("worker-a", now=NOW + timedelta(seconds=1), lease_seconds=30)
        self.assertEqual(row["state"], "CLAIMED")
        store.close()
        reopened, after = self.open_store()
        count = after.release_expired_claims(now=NOW + timedelta(seconds=33))
        self.assertEqual(count, 1)
        self.assertEqual(after.release_expired_claims(now=NOW + timedelta(seconds=33)), 0)
        self.assertEqual(after.get(self.key)["state"], "RETRY")
        reopened.close()

    def test_03_cross_thread_reusing_sqlite_handle_is_rejected(self):
        store, outbox = self.open_store()
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                result = pool.submit(lambda: outbox.get(self.key))
                with self.assertRaisesRegex(RuntimeError, "OUTBOX_SQLITE_CONNECTION_THREAD_MISMATCH"):
                    result.result(timeout=10)
            self.assertEqual(outbox.get(self.key)["state"], "PENDING")
        finally:
            store.close()

    def test_04_nested_transaction_claim_raises_sqlite_operational_error(self):
        store, outbox = self.open_store()
        try:
            store.db.execute("BEGIN IMMEDIATE")
            with self.assertRaisesRegex(RuntimeError, "OUTBOX_NESTED_TRANSACTION_UNSUPPORTED"):
                outbox.claim_next("worker-a", now=NOW + timedelta(seconds=1))
            # The caller transaction remains open and is still owned by the
            # caller; this LAB updates its expected diagnostic only.
            self.assertTrue(store.db.in_transaction)
            store.db.rollback()
            self.assertEqual(outbox.get(self.key)["state"], "PENDING")
            self.assertEqual(outbox.get(self.key)["attempts"], 0)
        finally:
            if store.db.in_transaction:
                store.db.rollback()
            store.close()

    def test_05_backup_to_is_valid_sqlite_but_not_an_action_highwater(self):
        store, outbox = self.open_store()
        backup = Path(self.temp.name) / "original-before-attempt.sqlite3"
        try:
            report = store.backup_to(backup)
            self.assertEqual(report["state"], "BACKUP_VERIFIED")
            self.assertEqual(outbox.get(self.key)["state"], "PENDING")
            self.assertTrue(backup.is_file())
        finally:
            store.close()

    def test_06_real_restore_api_erases_later_uncertain_state_without_witness(self):
        backup = Path(self.temp.name) / "valid-older-backup.sqlite3"
        first, original = self.open_store()
        first.backup_to(backup)
        first.close()

        later, outbox = self.open_store()
        row = outbox.claim_next("worker-before-restore", now=NOW + timedelta(seconds=1))
        self.assertEqual(row["state"], "CLAIMED")
        # Direct fixture-only write: no actual send (A118 keeps provider gate).
        with outbox.db:
            changed = outbox.db.execute(
                "UPDATE action_outbox SET state='UNCERTAIN',dispatch_started_at=?"
                " WHERE idempotency_key=?",
                (NOW.isoformat(), self.key),
            )
            self.assertEqual(changed.rowcount, 1)
        self.assertEqual(outbox.get(self.key)["state"], "UNCERTAIN")
        later.close()

        restored = SQLiteChatStore.restore_from_backup(backup, self.path)
        self.assertEqual(restored["state"], "RESTORE_VERIFIED")
        check, post = self.open_store()
        self.assertEqual(post.get(self.key)["state"], "PENDING")
        re_lease = post.claim_next("worker-after-restore", now=NOW + timedelta(seconds=2))
        self.assertIsNotNone(re_lease)
        self.assertEqual(re_lease["state"], "CLAIMED")
        # Real A118 dispatch is still denied separately; this test does not
        # show a production duplicate effect or bypass of the hard stop.
        check.close()

    def test_07_pending_in_one_scope_not_claimed_from_foreign_scope(self):
        stranger = Scope("p0-sqlite-other", "p0-sqlite-tenant", "p0-sqlite-workspace")
        store, other = self.open_store(stranger)
        try:
            self.assertIsNone(other.claim_next("foreign-worker", now=NOW + timedelta(seconds=1)))
            with self.assertRaises(LookupError):
                other.get(self.key)
        finally:
            store.close()
        first, original = self.open_store()
        self.assertEqual(original.get(self.key)["state"], "PENDING")
        first.close()

    def test_08_stale_lease_with_possible_effect_marker_cannot_recycle(self):
        store, outbox = self.open_store()
        claim = outbox.claim_next("worker-with-marker", now=NOW + timedelta(seconds=1), lease_seconds=30)
        self.assertEqual(claim["state"], "CLAIMED")
        with outbox.db:
            outbox.db.execute(
                "UPDATE action_outbox SET dispatch_started_at=? WHERE idempotency_key=?",
                (NOW.isoformat(), self.key),
            )
        store.close()
        reopened, after = self.open_store()
        self.assertEqual(after.release_expired_claims(now=NOW + timedelta(minutes=2)), 0)
        self.assertIsNone(after.claim_next("another", now=NOW + timedelta(minutes=2)))
        self.assertEqual(after.get(self.key)["state"], "CLAIMED")
        reopened.close()


if __name__ == "__main__":
    unittest.main()
