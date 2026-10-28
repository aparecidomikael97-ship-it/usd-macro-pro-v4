"""A205 RED-first: untrusted adapter claims cannot authorize real-world re-SEND.

Actual ExecutionOutbox + SQLite WAL. All effects simulated in Python.
Two dangerous claims under test:
  * late/false authoritative_absence=True despite an earlier effect
  * accepted=False,retryable=True despite having caused an effect
The adapter deliberately lies, so neither flag proves NO_EFFECT_FENCED.
"""
import tempfile
import unittest

from atlasquant_aion_execution_outbox import ExecutionOutbox
from labs import test_a202_outbox_dispatch_atomic_cas as a202

NOW=a202.NOW
WORKER=a202.WORKER
SCOPE=a202.SCOPE

class MisleadingEffectAdapter:
    def __init__(self, mode):
        self.mode=mode
        self.effects=[]
        self.send_calls=0
        self.reconcile_calls=0

    def send(self, decision, key):
        self.send_calls+=1
        self.effects.append((key,decision["intent_ref"]))
        if self.mode=="lost-ack":
            raise TimeoutError("synthetic lost ACK after effect")
        if self.mode=="retryable-reject":
            return {"accepted":False,"retryable":True,
                    "reason":"synthetic provider says retry"}
        if self.mode=="reject-with-effect":
            return {"accepted":False,"retryable":False,
                    "reason":"synthetic provider says rejected"}
        return {
            "accepted":True,"confirmed":True,
            "effect_ref":"synthetic-effect-"+str(len(self.effects)),
        }

    def reconcile(self, key, decision):
        self.reconcile_calls+=1
        # An arbitrary callback's assertion is NOT an independent proof!
        return {"found":False,"authoritative_absence":True}


class A205UntrustedAdapterCannotCauseAutoResend(unittest.TestCase):
    def fixture(self,root):
        helper=a202.A202SameLeaseOwnerDispatchRaceTests()
        path,store,outbox,key=helper.seed_claim(root)
        return store,outbox,key,helper

    def test_01_false_authoritative_absence_cannot_reopen_uncertain_effect(self):
        with tempfile.TemporaryDirectory() as root:
            store,outbox,key,helper=self.fixture(root)
            try:
                adapter=MisleadingEffectAdapter("lost-ack")
                first=outbox.dispatch_claimed(
                    key,worker_id=WORKER,authorize=helper.authorize,
                    adapter=adapter,now=NOW,
                )
                self.assertEqual(first["state"],"UNCERTAIN")
                self.assertEqual(adapter.send_calls,1)
                self.assertEqual(len(adapter.effects),1)
                reply=outbox.reconcile(
                    key,adapter=adapter,authorize=helper.authorize,now=NOW,
                )
                self.assertEqual(
                    reply["state"],"UNCERTAIN",
                    "A205_RED_UNVERIFIED_ABSENCE_REOPENED_UNCERTAIN_SEND",
                )
                self.assertEqual(
                    reply["reconcile_state"],"ABSENCE_UNVERIFIED_HARD_NO_GO",
                )
                self.assertIsNone(outbox.claim_next("worker-again",now=NOW))
                self.assertEqual(adapter.send_calls,1)
                self.assertEqual(len(adapter.effects),1)
            finally:
                store.close()

    def test_02_retryable_rejection_after_synthetic_effect_never_requeues(self):
        with tempfile.TemporaryDirectory() as root:
            store,outbox,key,helper=self.fixture(root)
            try:
                adapter=MisleadingEffectAdapter("retryable-reject")
                result=outbox.dispatch_claimed(
                    key,worker_id=WORKER,authorize=helper.authorize,
                    adapter=adapter,now=NOW,
                )
                self.assertEqual(
                    result["state"],"UNCERTAIN",
                    "A205_RED_UNTRUSTED_RETRYABLE_REJECTION_REQUEUED_EFFECT",
                )
                self.assertEqual(result["dispatch_state"],"UNCERTAIN_RECONCILE_REQUIRED")
                self.assertEqual(adapter.send_calls,1)
                self.assertEqual(len(adapter.effects),1)
                self.assertIsNone(outbox.claim_next("worker-again",now=NOW))
                self.assertEqual(len(adapter.effects),1)
            finally:
                store.close()

    def test_03_nonretryable_rejection_after_synthetic_effect_not_proof_of_absence(self):
        with tempfile.TemporaryDirectory() as root:
            store,outbox,key,helper=self.fixture(root)
            try:
                adapter=MisleadingEffectAdapter("reject-with-effect")
                result=outbox.dispatch_claimed(
                    key,worker_id=WORKER,authorize=helper.authorize,
                    adapter=adapter,now=NOW,
                )
                # Never call it a verified absent effect based on fake adapter.
                self.assertEqual(result["state"],"UNCERTAIN")
                self.assertEqual(result["dispatch_state"],"UNCERTAIN_RECONCILE_REQUIRED")
                self.assertIsNone(outbox.claim_next("worker-again",now=NOW))
                self.assertEqual(adapter.send_calls,1)
            finally:
                store.close()

    def test_04_self_asserted_positive_is_quarantined_without_effect_ledger(self):
        with tempfile.TemporaryDirectory() as root:
            store,outbox,key,helper=self.fixture(root)
            try:
                adapter=MisleadingEffectAdapter("confirmed")
                result=outbox.dispatch_claimed(
                    key,worker_id=WORKER,authorize=helper.authorize,
                    adapter=adapter,now=NOW,
                )
                self.assertEqual(result["state"],"UNCERTAIN")
                self.assertEqual(outbox.effect_count(),0)
                self.assertEqual(adapter.send_calls,1)
            finally:
                store.close()

    def test_05_unverified_absence_from_sent_stays_sent(self):
        with tempfile.TemporaryDirectory() as root:
            store,outbox,key,helper=self.fixture(root)
            try:
                class SentAdapter(MisleadingEffectAdapter):
                    def send(self,decision,key):
                        self.send_calls+=1
                        self.effects.append((key,decision["intent_ref"]))
                        return {"accepted":True,"confirmed":False,
                                "effect_ref":"synthetic-pending"}
                adapter=SentAdapter("sent")
                result=outbox.dispatch_claimed(
                    key,worker_id=WORKER,authorize=helper.authorize,
                    adapter=adapter,now=NOW,
                )
                self.assertEqual(result["state"],"SENT")
                recon=outbox.reconcile(
                    key,adapter=adapter,authorize=helper.authorize,now=NOW,
                )
                self.assertEqual(recon["state"],"SENT")
                self.assertEqual(recon["reconcile_state"],"ABSENCE_UNVERIFIED_HARD_NO_GO")
                self.assertIsNone(outbox.claim_next("worker-again",now=NOW))
                self.assertEqual(adapter.send_calls,1)
            finally:
                store.close()


if __name__=="__main__":
    unittest.main()
