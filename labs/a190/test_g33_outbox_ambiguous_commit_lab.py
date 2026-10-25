"""A190 G33: REAL ExecutionOutbox pre/post-COMMIT lost acknowledgement LAB.

A post-COMMIT error must not be treated as proof of no durable intent.
All references and effects are synthetic; no actual provider, send or Worker.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 24, 16, tzinfo=timezone.utc)
SCOPE = Scope("g33-outbox-owner", "g33-outbox-tenant", "g33-outbox-workspace")
WORKER = "g33-synthetic-worker"


class AmbiguousCommit:
    def __init__(self, real, *, after, fail_at=1):
        self.real = real
        self.after = after
        self.fail_at = fail_at
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0

    def commit(self):
        self.commits += 1
        if self.commits != self.fail_at:
            return self.real.commit()
        if self.after:
            self.real.commit()
        raise OSError("G33_OUTBOX_COMMIT_ACK_UNKNOWN")

    def rollback(self):
        self.rollbacks += 1
        return self.real.rollback()

    def close(self):
        self.closes += 1
        return self.real.close()

    def __getattr__(self, name):
        return getattr(self.real, name)


class TrapAdapter:
    def __init__(self):
        self.lookups = 0

    @property
    def send(self):
        self.lookups += 1
        raise AssertionError("G33_FORBIDDEN_PROVIDER_SEND_LOOKUP")


class G33OutboxCommitAmbiguity(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aion-g33-outbox-")
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "outbox.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(self.store, SCOPE)
        self.original = self.store.db
        self.addCleanup(self.restore_if_healthy)
        self.trap = TrapAdapter()

    def restore_if_healthy(self):
        if self.store.db is not None:
            self.store.db = self.original
            self.outbox.db = self.original

    def stage(self, intent="intent-1"):
        return self.outbox.enqueue(
            intent_ref=intent, action="synthetic_no_effect",
            payload={"amount_minor": 1000},
            aggregate_key="synthetic-biz-42",
            policy_version="synthetic-policy-1",
            authorization_ref="synthetic-auth-1",
            created_at=NOW, valid_until=NOW + timedelta(minutes=10),
        )

    def fault(self, *, after, fail_at=1):
        proxy = AmbiguousCommit(self.original, after=after, fail_at=fail_at)
        self.store.db = proxy
        self.outbox.db = proxy
        return proxy

    def run_failure(self, fn, *, after, fail_at=1):
        proxy = self.fault(after=after, fail_at=fail_at)
        with self.assertRaisesRegex(
            OSError, "G33_OUTBOX_COMMIT_ACK_UNKNOWN"
        ) as caught:
            fn()
        self.assertEqual(proxy.commits, fail_at)
        self.assertEqual(proxy.rollbacks, 0)
        self.assertEqual(proxy.closes, 1)
        self.assertIsNone(self.outbox.db)
        self.assertIsNone(self.store.db)
        self.assertEqual(self.store.storage_health()["state"], "failed")
        self.assertTrue(any(
            "COMMIT_OUTCOME_UNCERTAIN" in note
            for note in getattr(caught.exception, "__notes__", [])
        ))
        with self.assertRaises(StorageUnavailableError):
            self.stage("another-intent")
        with self.assertRaises(StorageUnavailableError):
            ExecutionOutbox(self.store, SCOPE)
        return caught.exception

    @contextmanager
    def reopened(self):
        store = SQLiteChatStore(self.path)
        try:
            yield store, ExecutionOutbox(store, SCOPE)
        finally:
            store.close()

    def test_01_enqueue_precommit_error_makes_no_row(self):
        self.run_failure(lambda: self.stage(), after=False)
        with self.reopened() as (_, outbox):
            self.assertEqual(len(outbox.list()), 0)
        print("G33_OUTBOX_PRECOMMIT_GREEN=ERROR_QUARANTINED_NO_AUTO_RETRY")

    def test_02_enqueue_postcommit_error_retains_row(self):
        self.run_failure(lambda: self.stage(), after=True)
        with self.reopened() as (_, outbox):
            self.assertEqual(len(outbox.list()), 1)
            self.assertEqual(outbox.list()[0]["state"], "PENDING")
        print("G33_OUTBOX_POSTCOMMIT_RED=RESERVATION_PERSISTED_ERROR_RETURNED")

    def test_03_duplicate_enqueue_commit_ack_unknown_quarantined(self):
        self.stage()
        self.run_failure(lambda: self.stage(), after=True)
        with self.reopened() as (_, outbox):
            self.assertEqual(len(outbox.list()), 1)

    def test_04_claim_precommit_error_preserves_pending(self):
        self.stage()
        self.run_failure(
            lambda: self.outbox.claim_next(WORKER, now=NOW, lease_seconds=60),
            after=False, fail_at=2,
        )
        with self.reopened() as (_, outbox):
            self.assertEqual(outbox.list()[0]["state"], "PENDING")

    def test_05_claim_postcommit_error_persists_claimed(self):
        self.stage()
        self.run_failure(
            lambda: self.outbox.claim_next(WORKER, now=NOW, lease_seconds=60),
            after=True, fail_at=2,
        )
        with self.reopened() as (_, outbox):
            self.assertEqual(outbox.list()[0]["state"], "CLAIMED")
        print("G33_CLAIM_POSTCOMMIT_RED=CLAIMED_ROW_PERSISTED_ACK_UNKNOWN")

    def test_06_release_precommit_error_keeps_claimed(self):
        self.stage()
        self.outbox.claim_next(WORKER, now=NOW, lease_seconds=60)
        self.run_failure(
            lambda: self.outbox.release_expired_claims(now=NOW + timedelta(minutes=2)),
            after=False,
        )
        with self.reopened() as (_, outbox):
            self.assertEqual(outbox.list()[0]["state"], "CLAIMED")

    def test_07_release_postcommit_error_releases_claim(self):
        self.stage()
        self.outbox.claim_next(WORKER, now=NOW, lease_seconds=60)
        self.run_failure(
            lambda: self.outbox.release_expired_claims(now=NOW + timedelta(minutes=2)),
            after=True,
        )
        with self.reopened() as (_, outbox):
            self.assertEqual(outbox.list()[0]["state"], "RETRY")
        print("G33_RELEASE_POSTCOMMIT_RED=RETRY_STATE_PERSISTED_UNKNOWN_ACK")

    def stage_uncertain_receipt_fixture(self):
        # G53: a synthetic receipt test must first cross into a locally
        # reconcilable phase, not directly confirm a PENDING intent.
        key = self.stage()["idempotency_key"]
        self.original.execute(
            "UPDATE action_outbox SET state='UNCERTAIN' "
            "WHERE idempotency_key=?", (key,))
        self.original.commit()
        return key

    def test_08_internal_confirm_precommit_error_has_no_effect_row(self):
        key = self.stage_uncertain_receipt_fixture()
        self.run_failure(
            lambda: self.outbox._confirm(
                key, effect_ref="synthetic-effect", confirmed_at=NOW
            ),
            after=False,
        )
        with self.reopened() as (_, outbox):
            self.assertEqual(outbox.effect_count(), 0)
            self.assertEqual(outbox.get(key)["state"], "UNCERTAIN")

    def test_09_internal_confirm_postcommit_error_has_effect_row(self):
        # Direct call to internal routine is only a laboratory fixture.
        # It does NOT represent an independently authenticated receipt.
        key = self.stage_uncertain_receipt_fixture()
        self.run_failure(
            lambda: self.outbox._confirm(
                key, effect_ref="synthetic-effect", confirmed_at=NOW
            ),
            after=True,
        )
        with self.reopened() as (_, outbox):
            self.assertEqual(outbox.effect_count(), 1)
            self.assertEqual(outbox.get(key)["state"], "CONFIRMED")
        print("G33_CONFIRM_POSTCOMMIT_RED=LOCAL_EFFECT_ROW_PERSISTED_ERROR_RETURNED")

    def test_10_postcommit_enqueue_then_default_dispatch_never_sends(self):
        self.run_failure(lambda: self.stage(), after=True)
        with self.reopened() as (_, outbox):
            row = outbox.claim_next(WORKER, now=NOW, lease_seconds=60)
            decision = row["decision"]
            result = outbox.dispatch_claimed(
                row["idempotency_key"], worker_id=WORKER,
                authorize=lambda _: {
                    "allowed": True,
                    "actor_id": SCOPE.owner_id,
                    "policy_version": decision["policy_version"],
                    "authorization_ref": decision["authorization_ref"],
                },
                adapter=self.trap, now=NOW + timedelta(seconds=1),
            )
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(self.trap.lookups, 0)
            self.assertEqual(outbox.effect_count(), 0)
        print("G33_POSTCOMMIT_REOPEN_GREEN=DEFAULT_WITNESS_DENIES_SEND")

    def test_11_unquarantined_explicit_reopen_not_global_freshness(self):
        self.run_failure(lambda: self.stage(), after=True)
        with self.reopened() as (store, outbox):
            self.assertEqual(store.require_healthy()["state"], "healthy")
            self.assertEqual(len(outbox.list()), 1)
            # This fresh local connection does not certify independent custody.
            self.assertFalse(outbox.list()[0]["executes_action"])

    def test_12_both_commit_failure_orders_keep_original_exception(self):
        for after in (False, True):
            with self.subTest(after=after):
                with tempfile.TemporaryDirectory(prefix="g33-dual-") as folder:
                    store = SQLiteChatStore(Path(folder) / "fresh.sqlite3")
                    try:
                        outbox = ExecutionOutbox(store, SCOPE)
                        raw = store.db
                        proxy = AmbiguousCommit(raw, after=after)
                        store.db = proxy
                        outbox.db = proxy
                        with self.assertRaisesRegex(
                            OSError, "G33_OUTBOX_COMMIT_ACK_UNKNOWN"
                        ) as captured:
                            outbox.enqueue(
                                intent_ref="fresh", action="synthetic_no_effect",
                                payload={"a": 1}, aggregate_key="fresh-aggregate",
                                policy_version="p1", authorization_ref="a1",
                                created_at=NOW,
                                valid_until=NOW + timedelta(minutes=5),
                            )
                        self.assertIsNone(outbox.db)
                        self.assertIsNone(store.db)
                        self.assertIsNone(captured.exception.__cause__)
                    finally:
                        store.close()


if __name__ == "__main__":
    unittest.main()
