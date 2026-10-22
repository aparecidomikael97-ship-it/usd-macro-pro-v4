"""A176 LAB: prove provider/adapter assertions cannot release uncertain dispatch.

No real provider, Worker, network or customer side effects. This test must fail
against the A175 outbox's two unverified retry paths before the patch.
"""
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from test_atlasquant_aion_execution_outbox import FakeIdempotentAdapter, NOW, policy


class A176OutboxRetryGateTests(unittest.TestCase):
    def setUp(self):
        self.scope = Scope("owner-lab", "tenant-lab", "workspace-lab")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dbpath = Path(self.tmp.name) / "outbox.sqlite3"
        self.store = SQLiteChatStore(self.dbpath)
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(self.store, self.scope)
        self.item = self.outbox.enqueue(
            intent_ref="event-once", action="send_email",
            payload={"to":"example.invalid","template":"lab"},
            aggregate_key="client-once", policy_version="policy-v1",
            authorization_ref="approval-1", created_at=NOW,
            valid_until=NOW+timedelta(minutes=5))
        self.key = self.item["idempotency_key"]

    def _dispatch(self, adapter):
        item = self.outbox.claim_next("worker-lab", now=NOW, lease_seconds=60)
        self.assertEqual(item["idempotency_key"], self.key)
        return self.outbox.dispatch_claimed(
            self.key, worker_id="worker-lab", authorize=policy(self.scope),
            adapter=adapter, now=NOW+timedelta(seconds=1))

    def test_01_retryable_reply_after_provider_call_must_never_requeue(self):
        adapter = FakeIdempotentAdapter("retryable-reject")
        out = self._dispatch(adapter)
        self.assertEqual(adapter.send_calls, 1)
        self.assertEqual(out["state"], "UNCERTAIN")
        self.assertEqual(out["dispatch_state"], "UNCERTAIN_RECONCILE_REQUIRED")
        self.assertIsNone(self.outbox.claim_next("worker-other", now=NOW+timedelta(seconds=2)))
        print("A176_RETRYABLE_AFTER_SEND=QUARANTINED")

    def test_02_adapter_declared_absence_does_not_clear_uncertainty(self):
        adapter = FakeIdempotentAdapter("lose-before-effect")
        self.assertEqual(self._dispatch(adapter)["state"], "UNCERTAIN")
        out = self.outbox.reconcile(
            self.key, adapter=adapter, authorize=policy(self.scope),
            now=NOW+timedelta(seconds=2))
        self.assertEqual(out["state"], "UNCERTAIN")
        self.assertEqual(out["reconcile_state"], "STILL_UNCERTAIN")
        self.assertIsNone(self.outbox.claim_next("worker-other", now=NOW+timedelta(seconds=3)))
        self.assertEqual(adapter.send_calls, 1)
        print("A176_UNTRUSTED_ABSENCE=QUARANTINED")

    def test_03_lying_adapter_claims_retryable_after_real_local_effect(self):
        class Liar:
            def __init__(self):
                self.calls = 0
                self.effects = []
            def send(self, decision, key):
                self.calls += 1
                self.effects.append(key)
                return {"accepted":False, "retryable":True, "reason":"temporary"}
        adapter = Liar()
        self.assertEqual(self._dispatch(adapter)["state"], "UNCERTAIN")
        self.assertEqual(len(adapter.effects), 1)
        self.assertIsNone(self.outbox.claim_next("worker2", now=NOW+timedelta(seconds=2)))
        self.assertEqual(adapter.calls, 1)
        print("A176_LYING_RETRYABLE_ADAPTER=NO_AUTO_RESEND")

    def test_04_uncertain_state_blocks_after_new_store_instance(self):
        adapter = FakeIdempotentAdapter("lose-before-effect")
        self.assertEqual(self._dispatch(adapter)["state"], "UNCERTAIN")
        self.outbox.reconcile(self.key, adapter=adapter,
                              authorize=policy(self.scope), now=NOW+timedelta(seconds=2))
        self.store.close()
        reopened = SQLiteChatStore(self.dbpath)
        try:
            retry = ExecutionOutbox(reopened, self.scope)
            self.assertEqual(retry.get(self.key)["state"], "UNCERTAIN")
            self.assertIsNone(retry.claim_next("worker-after-restart",
                                              now=NOW+timedelta(seconds=4)))
        finally:
            reopened.close()
        print("A176_UNCERTAIN_RESTART=NO_AUTO_RESEND")

    def test_05_unverified_reconciliation_is_not_terminal_confirmation(self):
        adapter = FakeIdempotentAdapter("lose-after-effect")
        self.assertEqual(self._dispatch(adapter)["state"], "UNCERTAIN")
        final = self.outbox.reconcile(self.key, adapter=adapter,
                                       authorize=policy(self.scope),
                                       now=NOW+timedelta(seconds=2))
        self.assertEqual(final["state"], "UNCERTAIN")
        self.assertEqual(final["reconcile_state"], "STILL_UNCERTAIN")
        self.assertEqual(adapter.send_calls, 1)
        self.assertEqual(self.outbox.effect_count(), 0)
        print("A177_SIMULATED_FOUND_RECEIPT=DENIED_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
