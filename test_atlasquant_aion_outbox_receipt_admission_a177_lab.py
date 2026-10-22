"""A177 LAB RED/GREEN: never treat adapter strings as authenticated receipts.

All effects and verifier stubs are synthetic; no network, real providers,
customer effects, credentials or payment paths are involved.
"""
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from test_atlasquant_aion_execution_outbox import (FakeIdempotentAdapter, NOW, policy,
    synthetic_lab_first_attempt_reservation)


class A177ReceiptAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SQLiteChatStore(Path(self.temp.name) / "outbox.sqlite3")
        self.addCleanup(self.store.close)
        self.scope = Scope("ownerlab", "tenantlab", "workspacelab")

    def make_claim(self, *, evidence_verifier=None):
        options = {"first_attempt_guard": synthetic_lab_first_attempt_reservation}
        options.update({} if evidence_verifier is None else {
            "evidence_verifier": evidence_verifier})
        outbox = ExecutionOutbox(self.store, self.scope, **options)
        item = outbox.enqueue(
            intent_ref="event-one", action="send_email",
            payload={"to":"lab.invalid","body":"synthetic"},
            aggregate_key="customer-one", policy_version="policy-v1",
            authorization_ref="approval-1", created_at=NOW,
            valid_until=NOW+timedelta(minutes=5))
        self.assertEqual(outbox.claim_next("worker1", now=NOW, lease_seconds=60)["idempotency_key"],
                         item["idempotency_key"])
        return outbox, item["idempotency_key"]

    def dispatch(self, outbox, key, adapter):
        return outbox.dispatch_claimed(
            key, worker_id="worker1", authorize=policy(self.scope),
            adapter=adapter, now=NOW+timedelta(seconds=1))

    def test_01_false_definitive_rejection_after_effect_must_be_uncertain(self):
        class LyingReject:
            def __init__(self):
                self.effects = []
                self.calls = 0
            def send(self, decision, key):
                self.calls += 1
                self.effects.append(key)
                return {"accepted":False, "retryable":False,
                        "reason":"fake definitive rejection"}
        outbox, key = self.make_claim()
        adapter = LyingReject()
        result = self.dispatch(outbox, key, adapter)
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(result["dispatch_state"], "UNCERTAIN_RECONCILE_REQUIRED")
        self.assertEqual(len(adapter.effects), 1)
        self.assertIsNone(outbox.claim_next("worker2",now=NOW+timedelta(seconds=2)))
        print("A177_FAKE_DEFINITIVE_REJECTION=UNCERTAIN_NO_RETRY")

    def test_02_unverified_positive_send_receipt_does_not_enter_ledger(self):
        outbox, key = self.make_claim()
        fake = FakeIdempotentAdapter("confirmed")
        result = self.dispatch(outbox, key, fake)
        self.assertEqual(result["state"], "SENT")
        self.assertEqual(result["dispatch_state"], "SENT_RECONCILE_REQUIRED")
        self.assertEqual(outbox.effect_count(), 0)
        self.assertEqual(fake.send_calls, 1)
        print("A177_UNVERIFIED_POSITIVE_SEND=NO_LEDGER")

    def test_03_unverified_positive_reconcile_does_not_confirm(self):
        outbox, key = self.make_claim()
        adapter = FakeIdempotentAdapter("lose-after-effect")
        self.assertEqual(self.dispatch(outbox,key,adapter)["state"],"UNCERTAIN")
        out = outbox.reconcile(key,adapter=adapter,authorize=policy(self.scope),
                               now=NOW+timedelta(seconds=2))
        self.assertEqual(out["state"],"UNCERTAIN")
        self.assertEqual(out["reconcile_state"],"STILL_UNCERTAIN")
        self.assertEqual(outbox.effect_count(),0)
        self.assertEqual(adapter.send_calls,1)
        print("A177_UNVERIFIED_POSITIVE_RECONCILE=NO_LEDGER")

    def test_04_synthetic_lab_verifier_allows_confirm_without_resend(self):
        # Test-only evidence acceptance, not a trusted external verification.
        calls = []
        def synthetic(kind, intent, result):
            calls.append(kind)
            return kind == "EFFECT_CONFIRMED" and result.get("confirmed") is True
        outbox,key = self.make_claim(evidence_verifier=synthetic)
        adapter=FakeIdempotentAdapter("lose-after-effect")
        self.assertEqual(self.dispatch(outbox,key,adapter)["state"],"UNCERTAIN")
        self.assertEqual(outbox.reconcile(key,adapter=adapter,
                          authorize=policy(self.scope),
                          now=NOW+timedelta(seconds=2))["state"],"CONFIRMED")
        self.assertEqual(outbox.effect_count(),1)
        self.assertEqual(adapter.send_calls,1)
        self.assertIn("EFFECT_CONFIRMED",calls)
        print("A177_TEST_ONLY_RECEIPT=CONFIRMED_SYNTHETIC")

    def test_05_test_only_effect_zero_proof_never_grants_retry(self):
        def synthetic(kind,intent,result):
            return kind == "EFFECT_ZERO" and result.get("retryable") is False
        outbox,key = self.make_claim(evidence_verifier=synthetic)
        class Reject:
            def send(self, decision, key):
                return {"accepted":False, "retryable":False}
        out = self.dispatch(outbox,key,Reject())
        self.assertEqual(out["state"],"FAILED")
        self.assertIsNone(outbox.claim_next("worker2",now=NOW+timedelta(seconds=2)))
        print("A177_SYNTHETIC_EFFECT_ZERO=TERMINAL_NO_RETRY")

    def test_06_throwing_verifier_fails_closed(self):
        def broken(*args):
            raise RuntimeError("verifier unavailable")
        outbox,key=self.make_claim(evidence_verifier=broken)
        out=self.dispatch(outbox,key,FakeIdempotentAdapter("confirmed"))
        self.assertEqual(out["state"],"SENT")
        self.assertEqual(outbox.effect_count(),0)
        print("A177_VERIFIER_UNAVAILABLE=NO_CONFIRMATION")

    def test_07_adapter_cannot_override_evidence_verifier(self):
        def deny(*args):
            return False
        outbox,key=self.make_claim(evidence_verifier=deny)
        result=self.dispatch(outbox,key,FakeIdempotentAdapter("confirmed"))
        self.assertEqual(result["state"],"SENT")
        self.assertEqual(outbox.effect_count(),0)


if __name__=="__main__":
    unittest.main()
