"""A206 RED-first: a delayed SEND callback must not downgrade a newer receipt.

Real SQLite WAL + two connections + deterministic Events.
The only effect and provider receipt are synthetic; no network, Worker or SEND.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import tempfile
import unittest

from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from labs import test_a202_outbox_dispatch_atomic_cas as a202

NOW = a202.NOW
WORKER = a202.WORKER
SCOPE = a202.SCOPE
EFFECT = "A206-SYNTHETIC-EFFECT-1"


class LateSendAdapter:
    def __init__(self, mode, entered, released):
        self.mode = mode
        self.entered = entered
        self.released = released
        self.calls = 0
        self.effects = []

    def send(self, decision, key):
        self.calls += 1
        self.effects.append((key, EFFECT))
        self.entered.set()
        if not self.released.wait(timeout=20):
            raise AssertionError("A206 adapter synchronization timeout")
        if self.mode == "timeout":
            raise TimeoutError("A206 synthetic ACK lost after effect")
        if self.mode == "pending":
            return {"accepted": True, "confirmed": False, "effect_ref": EFFECT}
        raise AssertionError("invalid synthetic mode")


class ConfirmedSyntheticReceipt:
    def reconcile(self, key, decision):
        return {"found": True, "confirmed": True, "effect_ref": EFFECT}


class A206LateSendReplyCannotDowngradeConfirmedTests(unittest.TestCase):
    def exercise(self, mode):
        with tempfile.TemporaryDirectory() as root:
            helper = a202.A202SameLeaseOwnerDispatchRaceTests()
            path, seed_store, outbox, key = helper.seed_claim(root)
            entered, released = Event(), Event()
            adapter = LateSendAdapter(mode, entered, released)

            def dispatch_in_separate_connection():
                store = SQLiteChatStore(path)
                try:
                    return ExecutionOutbox(store, SCOPE).dispatch_claimed(
                        key, worker_id=WORKER, authorize=helper.authorize,
                        adapter=adapter, now=NOW,
                    )
                finally:
                    store.close()

            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    delayed = pool.submit(dispatch_in_separate_connection)
                    self.assertTrue(entered.wait(timeout=20), "A206 SEND never reached fake adapter")
                    try:
                        self.assertEqual(outbox.get(key)["state"], "UNCERTAIN")
                        newer = outbox.reconcile(
                            key, adapter=ConfirmedSyntheticReceipt(),
                            authorize=helper.authorize, now=NOW,
                        )
                        self.assertEqual(newer["state"], "CONFIRMED")
                        self.assertEqual(outbox.effect_count(), 1)
                    finally:
                        released.set()
                    older = delayed.result(timeout=30)

                self.assertEqual(len(adapter.effects), 1)
                self.assertEqual(adapter.calls, 1)
                final = outbox.get(key)
                self.assertEqual(
                    final["state"], "CONFIRMED",
                    "A206_RED_STALE_SEND_REPLY_DOWNGRADED_NEWER_CONFIRMED",
                )
                self.assertEqual(older["state"], "CONFIRMED")
                self.assertEqual(final["effect_ref"], EFFECT)
                self.assertEqual(outbox.effect_count(), 1)
                self.assertIsNone(outbox.claim_next("a206-other-worker", now=NOW))
            finally:
                released.set()
                seed_store.close()

    def test_01_late_send_timeout_cannot_overwrite_confirmed(self):
        self.exercise("timeout")

    def test_02_late_send_pending_ack_cannot_overwrite_confirmed(self):
        self.exercise("pending")


if __name__ == "__main__":
    unittest.main()
