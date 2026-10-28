"""A204 RED-first: a stale 'authoritative_absence' must not undo CONFIRMED.

No external provider. Two SQLite WAL connections in separate threads; a
barrier-like pair of Events forces a late fake absence reply to arrive after
a fresh confirmation for the very same original intent.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import tempfile
import unittest

from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from labs import test_a202_outbox_dispatch_atomic_cas as a202

SCOPE=a202.SCOPE
NOW=a202.NOW
WORKER=a202.WORKER


class SyntheticEffectAdapter:
    def __init__(self, mode="uncertain"):
        self.mode=mode
        self.effects=[]
        self.send_calls=0
        self.effect_ref="SYNTHETIC-RECEIPT-1"

    def send(self, decision, key):
        self.send_calls+=1
        self.effects.append((key,self.effect_ref))
        if self.mode=="uncertain":
            raise TimeoutError("synthetic ACK lost after effect, no network")
        return {
            "accepted":True,
            "confirmed":False,
            "effect_ref":self.effect_ref,
        }


class A204StaleAbsenceVersusConfirmedTests(unittest.TestCase):
    def setup_case(self,root,mode):
        helper=a202.A202SameLeaseOwnerDispatchRaceTests()
        path,store,outbox,key=helper.seed_claim(root)
        adapter=SyntheticEffectAdapter(mode)
        dispatched=outbox.dispatch_claimed(
            key,worker_id=WORKER,authorize=helper.authorize,
            adapter=adapter,now=NOW,
        )
        expected="UNCERTAIN" if mode=="uncertain" else "SENT"
        self.assertEqual(dispatched["state"],expected)
        self.assertEqual(adapter.send_calls,1)
        self.assertEqual(len(adapter.effects),1)
        return path,store,outbox,key,helper,adapter,expected

    def prove_no_stale_retry(self,mode):
        with tempfile.TemporaryDirectory() as raw:
            path,store,outbox,key,helper,adapter,prior=self.setup_case(raw,mode)
            inside_old_reconcile=Event()
            release_old_reconcile=Event()

            class LateAbsence:
                def reconcile(self,_key,_decision):
                    inside_old_reconcile.set()
                    if not release_old_reconcile.wait(timeout=20):
                        raise AssertionError("late absence test failed to synchronize")
                    return {"found":False,"authoritative_absence":True}

            class FreshReceipt:
                def reconcile(self,_key,_decision):
                    return {
                        "found":True,
                        "confirmed":True,
                        "effect_ref":adapter.effect_ref,
                    }

            def stale_worker():
                local=SQLiteChatStore(path)
                try:
                    local_outbox=ExecutionOutbox(local,SCOPE)
                    return local_outbox.reconcile(
                        key,adapter=LateAbsence(),
                        authorize=helper.authorize,now=NOW,
                    )
                finally:
                    local.close()

            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pending=pool.submit(stale_worker)
                    self.assertTrue(inside_old_reconcile.wait(timeout=20))
                    try:
                        newer=outbox.reconcile(
                            key,adapter=FreshReceipt(),
                            authorize=helper.authorize,now=NOW,
                        )
                        self.assertEqual(newer["state"],"CONFIRMED")
                        self.assertEqual(outbox.effect_count(),1)
                    finally:
                        release_old_reconcile.set()
                    stale=pending.result(timeout=25)

                after=outbox.get(key)
                self.assertEqual(
                    after["state"],"CONFIRMED",
                    "A204_STALE_ABSENCE_REOPENED_CONFIRMED_INTENT_RED",
                )
                self.assertEqual(stale["state"],"CONFIRMED")
                self.assertEqual(
                    stale["reconcile_state"],
                    "NOT_RECONCILED_STATE_CHANGED",
                )
                self.assertEqual(outbox.effect_count(),1)
                self.assertEqual(adapter.send_calls,1)
                self.assertIsNone(
                    outbox.claim_next("new-worker",now=NOW),
                    "stale absence made a confirmed action retryable",
                )
            finally:
                store.close()

    def test_01_late_absence_cannot_reopen_confirmed_uncertain_intent(self):
        self.prove_no_stale_retry("uncertain")

    def test_02_late_absence_cannot_reopen_confirmed_sent_intent(self):
        self.prove_no_stale_retry("sent")

    def test_03_current_unverified_absence_cannot_reopen_uncertain(self):
        # A205 changed the staging contract: adapter boolean claims are not
        # independently authenticated provider NO_EFFECT_FENCED witnesses.
        # Original RETRY expectation remains in prior A204 Git history.
        with tempfile.TemporaryDirectory() as raw:
            path,store,outbox,key,helper,adapter,_=self.setup_case(raw,"uncertain")
            class CurrentAbsence:
                def reconcile(self,_key,_decision):
                    return {"found":False,"authoritative_absence":True}
            try:
                out=outbox.reconcile(
                    key,adapter=CurrentAbsence(),
                    authorize=helper.authorize,now=NOW,
                )
                self.assertEqual(out["state"],"UNCERTAIN")
                self.assertEqual(out["reconcile_state"],"ABSENCE_UNVERIFIED_HARD_NO_GO")
                self.assertIsNone(outbox.claim_next("other-worker",now=NOW))
                self.assertEqual(adapter.send_calls,1)
            finally:
                store.close()



if __name__=="__main__":
    unittest.main()
