"""A241: Outbox direct sqlite handle must obey A240 pathname binding.

Staging-only synthetic tests; zero provider/network side effects.
"""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from atlasquant_aion_execution_outbox import ExecutionOutbox
from labs.a259_synthetic_outbox_fixture import SyntheticFirstAttemptOutboxLab


NOW = datetime(2026, 10, 29, 10, 0, tzinfo=timezone.utc)
SCOPE = Scope("owner-a241", "tenant-a241", "workspace-a241")
WORKER = "synthetic-worker"


class Adapter:
    def __init__(self, on_send=None):
        self.calls = 0
        self.on_send = on_send

    def send(self, decision, key):
        self.calls += 1
        if self.on_send:
            self.on_send()
        return {"accepted": True, "confirmed": False, "effect_ref": "synthetic-only"}


def _authorize(decision):
    return {
        "allowed": True,
        "actor_id": SCOPE.owner_id,
        "tenant_id": SCOPE.tenant_id,
        "workspace_id": SCOPE.workspace_id,
        "policy_version": decision["policy_version"],
        "authorization_ref": decision["authorization_ref"],
    }


def _fixture(root, claimed=False):
    path = Path(root) / "live.db"
    store = SQLiteChatStore(path)
    outbox = SyntheticFirstAttemptOutboxLab(store, SCOPE, first_attempt_guard=lambda _intent: True)
    item = outbox.enqueue(
        intent_ref="synthetic-intent", action="synthetic-only", payload={"offline": True},
        aggregate_key="target-a", policy_version="policy-a241",
        authorization_ref="synthetic-approval", created_at=NOW,
        valid_until=NOW + timedelta(minutes=5),
    )
    if claimed:
        outbox.claim_next(WORKER, now=NOW, lease_seconds=120)
    return path, store, outbox, item["idempotency_key"]


class A241OutboxStoreBindingTests(unittest.TestCase):
    def test_01_normal_outbox_operations_still_work(self):
        with TemporaryDirectory(prefix="a241-") as raw:
            path, store, outbox, key = _fixture(raw)
            try:
                self.assertEqual(outbox.get(key)["state"], "PENDING")
                self.assertEqual(len(outbox.list()), 1)
                self.assertEqual(outbox.effect_count(), 0)
            finally:
                store.close()

    def test_02_closed_store_denies_outbox_get(self):
        with TemporaryDirectory(prefix="a241-") as raw:
            path, store, outbox, key = _fixture(raw)
            store.close()
            with self.assertRaises(StorageUnavailableError):
                outbox.get(key)

    def test_03_closed_store_denies_expired_claim_release_before_begin(self):
        with TemporaryDirectory(prefix="a241-") as raw:
            path, store, outbox, key = _fixture(raw, claimed=True)
            store.close()
            with self.assertRaises(StorageUnavailableError):
                outbox.release_expired_claims(now=NOW + timedelta(minutes=10))

    def test_04_injected_path_mismatch_denies_reads_and_count(self):
        with TemporaryDirectory(prefix="a241-") as raw:
            path, store, outbox, key = _fixture(raw)
            try:
                with mock.patch.object(store, "_pathname_binding_reason",
                                       return_value="PATH_IDENTITY_CHANGED"):
                    with self.assertRaises(StorageUnavailableError):
                        outbox.list()
                    with self.assertRaises(StorageUnavailableError):
                        outbox.effect_count()
                self.assertEqual(store.storage_health()["state"], "failed")
            finally:
                store.close()

    def test_05_mismatch_before_dispatch_never_calls_adapter(self):
        with TemporaryDirectory(prefix="a241-") as raw:
            path, store, outbox, key = _fixture(raw, claimed=True)
            adapter = Adapter()
            try:
                with mock.patch.object(store, "_pathname_binding_reason",
                                       return_value="PATH_IDENTITY_CHANGED"):
                    with self.assertRaises(StorageUnavailableError):
                        outbox.dispatch_claimed(
                            key, worker_id=WORKER, authorize=_authorize,
                            adapter=adapter, now=NOW,
                        )
                self.assertEqual(adapter.calls, 0)
            finally:
                store.close()

    def test_06_identity_changes_during_authorization_no_send(self):
        with TemporaryDirectory(prefix="a241-") as raw:
            path, store, outbox, key = _fixture(raw, claimed=True)
            adapter = Adapter()
            def swapped_during_auth(decision):
                store._pathname_identity = (-1, -1)
                return _authorize(decision)
            try:
                with self.assertRaises(StorageUnavailableError):
                    outbox.dispatch_claimed(
                        key, worker_id=WORKER, authorize=swapped_during_auth,
                        adapter=adapter, now=NOW,
                    )
                self.assertEqual(adapter.calls, 0)
            finally:
                store.close()

    def test_07_swap_after_synthetic_send_preserves_uncertain_on_disk(self):
        with TemporaryDirectory(prefix="a241-") as raw:
            path, store, outbox, key = _fixture(raw, claimed=True)
            adapter = Adapter(on_send=lambda: setattr(store, "_pathname_identity", (-1, -1)))
            try:
                with self.assertRaises(StorageUnavailableError):
                    outbox.dispatch_claimed(
                        key, worker_id=WORKER, authorize=_authorize,
                        adapter=adapter, now=NOW,
                    )
                self.assertEqual(adapter.calls, 1)
            finally:
                store.close()
            reopened = SQLiteChatStore(path)
            try:
                fresh = SyntheticFirstAttemptOutboxLab(reopened, SCOPE, first_attempt_guard=lambda _intent: True)
                self.assertEqual(fresh.get(key)["state"], "UNCERTAIN")
                self.assertIsNone(fresh.claim_next("other-worker", now=NOW + timedelta(minutes=10)))
            finally:
                reopened.close()

    def test_08_real_path_replace_blocks_outbox_on_supporting_os(self):
        with TemporaryDirectory(prefix="a241-") as raw:
            path, store, outbox, key = _fixture(raw)
            replacement = Path(raw) / "replacement.db"
            with closing(sqlite3.connect(str(replacement))) as db:
                db.execute("CREATE TABLE unrelated (n INTEGER)")
                db.commit()
            try:
                try:
                    os.replace(replacement, path)
                except OSError as exc:
                    self.skipTest("OS forbids replacing active SQLite path: " + str(exc))
                with self.assertRaises(StorageUnavailableError):
                    outbox.get(key)
            finally:
                store.close()
