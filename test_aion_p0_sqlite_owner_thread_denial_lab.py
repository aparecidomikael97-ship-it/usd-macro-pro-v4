"""P0 LAB: Outbox methods must deny cross-thread reuse before touching SQLite.

The baseline SQLite connection uses sqlite3 default check_same_thread=True.
An imported, reused Outbox object must fail with an explicit non-operational
contract, NOT the driver exception (and never change SQLite health/state).

All tests use temp SQLite only. No producer, credential, external effects,
network, Worker, or privileged write. This suite is RED before LAB guard.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 19, 21, 0, tzinfo=timezone.utc)
SCOPE = Scope("owner-t", "tenant-t", "workspace-t")
DENIAL = "OUTBOX_SQLITE_CONNECTION_THREAD_MISMATCH"


class P0OwnerThreadDenialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="p0-cross-thread-")
        self.addCleanup(self.temp.cleanup)
        self.store = SQLiteChatStore(Path(self.temp.name) / "outbox.sqlite3")
        self.addCleanup(self.store.close)  # LIFO: close SQLite before removal on Windows
        self.outbox = ExecutionOutbox(self.store, SCOPE)
        self.key = self.outbox.enqueue(
            intent_ref="cross-thread-fixture",
            action="synthetic_no_provider",
            payload={"test": "cross-thread"},
            aggregate_key="thread-isolation-test",
            policy_version="fixture-v1",
            authorization_ref="fixture-approval",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )["idempotency_key"]

    def _run_foreign(self, callback):
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.assertRaisesRegex(RuntimeError, DENIAL):
                pool.submit(callback).result(timeout=12)
        self.assertEqual(self.outbox.get(self.key)["state"], "PENDING")
        self.assertEqual(self.outbox.get(self.key)["attempts"], 0)
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertEqual(self.store.storage_health(deep=True)["state"], "healthy")

    def test_01_get_cross_thread_explicit_denial(self):
        self._run_foreign(lambda: self.outbox.get(self.key))

    def test_02_list_cross_thread_explicit_denial(self):
        self._run_foreign(lambda: self.outbox.list())

    def test_03_effect_count_cross_thread_explicit_denial(self):
        self._run_foreign(lambda: self.outbox.effect_count())

    def test_04_enqueue_cross_thread_explicit_denial_before_store_health(self):
        self._run_foreign(lambda: self.outbox.enqueue(
            intent_ref="another-intent",
            action="synthetic_no_provider",
            payload={"safe": True},
            aggregate_key="another-aggregate",
            policy_version="fixture-v1",
            authorization_ref="fixture-approval",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        ))
        self.assertEqual(len(self.outbox.list()), 1)

    def test_05_release_expired_claims_cross_thread_explicit_denial(self):
        self._run_foreign(lambda: self.outbox.release_expired_claims(now=NOW))

    def test_06_claim_next_cross_thread_explicit_denial(self):
        self._run_foreign(lambda: self.outbox.claim_next(
            "foreign-worker", now=NOW + timedelta(seconds=1)
        ))

    def test_07_dispatch_cross_thread_denied_before_callbacks_or_adapter(self):
        class Trap:
            @property
            def send(self):
                raise AssertionError("never inspect adapter on wrong thread")
        self._run_foreign(lambda: self.outbox.dispatch_claimed(
            self.key, worker_id="foreign-worker",
            authorize=lambda _: (_ for _ in ()).throw(AssertionError("never call auth")),
            adapter=Trap(), now=NOW,
        ))

    def test_08_reconcile_cross_thread_denied_before_adapter(self):
        class Trap:
            @property
            def reconcile(self):
                raise AssertionError("never inspect reconciliation adapter")
        self._run_foreign(lambda: self.outbox.reconcile(
            self.key, adapter=Trap(),
            authorize=lambda _: (_ for _ in ()).throw(AssertionError("no auth")),
            now=NOW,
        ))

    def test_09_cross_thread_denial_does_not_rollback_parent_transaction(self):
        self.store.db.execute("CREATE TABLE IF NOT EXISTS owner_thread_sentinel(id TEXT)")
        self.store.db.execute("BEGIN IMMEDIATE")
        try:
            self.store.db.execute("INSERT INTO owner_thread_sentinel VALUES ('caller')")
            with ThreadPoolExecutor(max_workers=1) as pool:
                with self.assertRaisesRegex(RuntimeError, DENIAL):
                    pool.submit(lambda: self.outbox.release_expired_claims(now=NOW)).result(timeout=12)
            self.assertTrue(self.store.db.in_transaction)
            self.assertEqual(self.store.db.execute(
                "SELECT count(*) FROM owner_thread_sentinel"
            ).fetchone()[0], 1)
            self.assertEqual(self.outbox.get(self.key)["state"], "PENDING")
        finally:
            self.store.db.rollback()

    def test_10_same_thread_behavior_still_claims_once(self):
        out = self.outbox.claim_next("first", now=NOW + timedelta(seconds=1), lease_seconds=30)
        self.assertEqual((out["state"], out["attempts"]), ("CLAIMED", 1))
        self.assertIsNone(self.outbox.claim_next("second", now=NOW + timedelta(seconds=2)))
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_11_independent_connection_in_each_thread_remains_usable(self):
        path = self.store.path
        def local_reader():
            store = SQLiteChatStore(path)
            try:
                obj = ExecutionOutbox(store, SCOPE)
                return obj.get(self.key)["state"]
            finally:
                store.close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            self.assertEqual(pool.submit(local_reader).result(timeout=12), "PENDING")

    def test_12_explicit_denial_does_not_poison_another_healthy_connection(self):
        self._run_foreign(lambda: self.outbox.list())
        with ThreadPoolExecutor(max_workers=1) as pool:
            def other():
                store = SQLiteChatStore(self.store.path)
                try:
                    return ExecutionOutbox(store, SCOPE).get(self.key)["state"]
                finally:
                    store.close()
            self.assertEqual(pool.submit(other).result(timeout=12), "PENDING")


if __name__ == "__main__":
    unittest.main()
