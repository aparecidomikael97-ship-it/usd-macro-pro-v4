"""A206 RED-first: a late SEND outcome must not erase newer CONFIRMED.

Real SQLite WAL and independent per-thread connections. While synthetic
adapter.send is blocked, an independent reconciler confirms a fake
effect_ref. A late timeout or accepted-unconfirmed SEND result must
not roll CONFIRMED backward to UNCERTAIN/SENT.

All adapters and effects are synthetic. No network, Worker or provider.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock
import tempfile
import unittest

from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from labs import test_a202_outbox_dispatch_atomic_cas as a202

NOW=a202.NOW
WORKER=a202.WORKER
SCOPE=a202.SCOPE


class DelayedSend:
    def __init__(self,mode):
        self.mode=mode
        self.entered=Event()
        self.release=Event()
        self.lock=Lock()
        self.send_calls=0
        self.effects=[]
        self.effect_ref="SYNTHETIC-A206-EFFECT"

    def send(self,decision,key):
        with self.lock:
            self.send_calls+=1
            self.effects.append((key,decision["intent_ref"],self.effect_ref))
        self.entered.set()
        if not self.release.wait(timeout=25):
            raise AssertionError("test must unblock delayed adapter")
        if self.mode=="lost-ack":
            raise TimeoutError("synthetic ACK lost after one fake effect")
        if self.mode=="sent":
            return {
                "accepted":True,
                "confirmed":False,
                "effect_ref":self.effect_ref,
            }
        raise AssertionError("unknown synthetic mode")

    def reconcile(self,key,decision):
        if not self.entered.is_set():
            raise AssertionError("reconcile must run after fake SEND effect")
        return {
            "found":True,
            "confirmed":True,
            "effect_ref":self.effect_ref,
        }


class A206DelayedSendOutcomeDoesNotEraseConfirmedTests(unittest.TestCase):
    def run_late_outcome(self,mode):
        helper=a202.A202SameLeaseOwnerDispatchRaceTests()
        with tempfile.TemporaryDirectory() as root:
            path,store,outbox,key=helper.seed_claim(root)
            adapter=DelayedSend(mode)

            def worker():
                local=SQLiteChatStore(path)
                try:
                    scoped=ExecutionOutbox(local,SCOPE)
                    return scoped.dispatch_claimed(
                        key,worker_id=WORKER,
                        authorize=helper.authorize,
                        adapter=adapter,now=NOW,
                    )
                finally:
                    local.close()

            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pending=pool.submit(worker)
                    self.assertTrue(adapter.entered.wait(timeout=20))
                    try:
                        # The worker persisted UNCERTAIN BEFORE adapter.send,
                        # so a different SQLite connection can reconcile it.
                        self.assertEqual(outbox.get(key)["state"],"UNCERTAIN")
                        fresh=outbox.reconcile(
                            key,adapter=adapter,
                            authorize=helper.authorize,now=NOW,
                        )
                        self.assertEqual(fresh["state"],"UNCERTAIN")
                        self.assertEqual(outbox.effect_count(),0)
                    finally:
                        adapter.release.set()
                    stale=pending.result(timeout=25)

                self.assertEqual(adapter.send_calls,1)
                self.assertEqual(len(adapter.effects),1)
                self.assertEqual(
                    outbox.get(key)["state"],"UNCERTAIN",
                    "A213_RED_LATE_SEND_OVERWROTE_QUARANTINED_POSITIVE",
                )
                self.assertEqual(outbox.effect_count(),0)
                self.assertEqual(stale["state"],"UNCERTAIN")
                self.assertEqual(
                    stale["dispatch_state"],"NOT_DISPATCHED_STATE_CHANGED",
                )
                self.assertIsNone(outbox.claim_next("worker-again",now=NOW))
            finally:
                store.close()

    def test_01_late_send_timeout_cannot_erase_confirmed_effect(self):
        self.run_late_outcome("lost-ack")

    def test_02_late_accepted_unconfirmed_cannot_erase_confirmed_effect(self):
        self.run_late_outcome("sent")

    def test_03_timeout_without_concurrent_confirmation_remains_uncertain(self):
        helper=a202.A202SameLeaseOwnerDispatchRaceTests()
        with tempfile.TemporaryDirectory() as root:
            _,store,outbox,key=helper.seed_claim(root)
            adapter=DelayedSend("lost-ack")
            adapter.release.set()
            try:
                result=outbox.dispatch_claimed(
                    key,worker_id=WORKER,
                    authorize=helper.authorize,adapter=adapter,now=NOW,
                )
                self.assertEqual(result["state"],"UNCERTAIN")
                self.assertEqual(result["dispatch_state"],"UNCERTAIN_RECONCILE_REQUIRED")
                self.assertEqual(adapter.send_calls,1)
                self.assertIsNone(outbox.claim_next("worker-again",now=NOW))
            finally:
                store.close()

    def test_04_sent_without_concurrent_confirmation_remains_sent(self):
        helper=a202.A202SameLeaseOwnerDispatchRaceTests()
        with tempfile.TemporaryDirectory() as root:
            _,store,outbox,key=helper.seed_claim(root)
            adapter=DelayedSend("sent")
            adapter.release.set()
            try:
                result=outbox.dispatch_claimed(
                    key,worker_id=WORKER,
                    authorize=helper.authorize,adapter=adapter,now=NOW,
                )
                self.assertEqual(result["state"],"SENT")
                self.assertEqual(result["dispatch_state"],"SENT_RECONCILE_REQUIRED")
                self.assertEqual(adapter.send_calls,1)
                self.assertIsNone(outbox.claim_next("worker-again",now=NOW))
            finally:
                store.close()


if __name__=="__main__":
    unittest.main()
