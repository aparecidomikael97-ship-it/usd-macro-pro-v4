"""A213: real SQLite Outbox, fake adapters, zero actual side effects.

The unmodified historical A207 RED fixture is separately re-run by CI.
A213 tests focus on the new durable quarantine, concurrency and bypass denial.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import tempfile
import unittest

from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from labs.a259_synthetic_outbox_fixture import SyntheticFirstAttemptOutboxLab
from labs import test_a202_outbox_dispatch_atomic_cas as a202

NOW = a202.NOW
WORKER = a202.WORKER
SCOPE = a202.SCOPE


class UntrustedPositive:
    def __init__(self, send_mode="positive", reconcile_mode="positive"):
        self.send_mode = send_mode
        self.reconcile_mode = reconcile_mode
        self.send_calls = 0
        self.reconcile_calls = 0
        self.actual_effects = []  # Intentionally NEVER create an effect.

    def send(self, decision, key):
        self.send_calls += 1
        if self.send_mode == "lost-ack":
            raise TimeoutError("synthetic lost acknowledgement")
        if self.send_mode == "rejected-positive":
            return {"accepted": False, "confirmed": True, "retryable": True}
        if self.send_mode == "pending":
            return {"accepted": True, "confirmed": False, "effect_ref": "pending-only"}
        if self.send_mode == "positive-no-ref":
            return {"accepted": True, "confirmed": True}
        return {
            "accepted": True, "confirmed": True,
            "effect_ref": "NO-ACTUAL-EFFECT-A213",
            "receipt": {"fake": True, "independently_verified": True},
            "external_signature_verified": True,
        }

    def reconcile(self, key, decision):
        self.reconcile_calls += 1
        if self.reconcile_mode == "absence":
            return {"found": False, "authoritative_absence": True}
        if self.reconcile_mode == "positive-no-ref":
            return {"found": True, "confirmed": True}
        return {
            "found": True, "confirmed": True,
            "effect_ref": "NO-ACTUAL-EFFECT-A213",
            "independently_verified": True,
        }


class A213OutboxPositiveHardNoGoTests(unittest.TestCase):
    def setUp(self):
        self.helper = a202.A202SameLeaseOwnerDispatchRaceTests()

    def case(self, root, adapter, *, worker=WORKER):
        path, store, outbox, key = self.helper.seed_claim(root)
        first = outbox.dispatch_claimed(
            key, worker_id=worker, authorize=self.helper.authorize,
            adapter=adapter, now=NOW,
        )
        return path, store, outbox, key, first

    def test_01_positive_send_stays_uncertain_with_no_effect_ledger(self):
        with tempfile.TemporaryDirectory() as root:
            adapter = UntrustedPositive()
            _, store, outbox, key, result = self.case(root, adapter)
            try:
                self.assertEqual(result["state"], "UNCERTAIN")
                self.assertEqual(
                    result["dispatch_state"], "UNTRUSTED_POSITIVE_RECONCILE_REQUIRED",
                )
                self.assertEqual(
                    result["last_error"],
                    "UNTRUSTED_SEND_POSITIVE_NO_EXTERNAL_RECEIPT",
                )
                self.assertEqual(result["effect_ref"], "")
                self.assertEqual(outbox.effect_count(), 0)
                self.assertEqual(adapter.actual_effects, [])
                self.assertIsNone(outbox.claim_next("worker-again", now=NOW))
            finally:
                store.close()

    def test_02_missing_effect_ref_does_not_produce_confirmation(self):
        with tempfile.TemporaryDirectory() as root:
            adapter = UntrustedPositive("positive-no-ref")
            _, store, outbox, key, result = self.case(root, adapter)
            try:
                self.assertEqual(result["state"], "UNCERTAIN")
                self.assertEqual(outbox.effect_count(), 0)
                self.assertEqual(adapter.send_calls, 1)
            finally:
                store.close()

    def test_03_self_claimed_independent_receipt_flag_is_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            adapter = UntrustedPositive()
            _, store, outbox, key, result = self.case(root, adapter)
            try:
                self.assertEqual(result["state"], "UNCERTAIN")
                self.assertEqual(result["effect_ref"], "")
                self.assertEqual(outbox.effect_count(), 0)
            finally:
                store.close()

    def test_04_repeated_dispatch_cannot_send_twice(self):
        with tempfile.TemporaryDirectory() as root:
            adapter = UntrustedPositive()
            _, store, outbox, key, result = self.case(root, adapter)
            try:
                with self.assertRaisesRegex(ValueError, "must be CLAIMED"):
                    outbox.dispatch_claimed(
                        key, worker_id=WORKER, authorize=self.helper.authorize,
                        adapter=adapter, now=NOW,
                    )
                self.assertEqual(adapter.send_calls, 1)
                self.assertIsNone(outbox.claim_next("again", now=NOW))
            finally:
                store.close()

    def test_05_positive_reconcile_from_sent_keeps_sent(self):
        with tempfile.TemporaryDirectory() as root:
            adapter = UntrustedPositive("pending")
            _, store, outbox, key, first = self.case(root, adapter)
            try:
                self.assertEqual(first["state"], "SENT")
                out = outbox.reconcile(
                    key, adapter=adapter, authorize=self.helper.authorize, now=NOW,
                )
                self.assertEqual(out["state"], "SENT")
                self.assertEqual(out["reconcile_state"], "UNTRUSTED_POSITIVE_HARD_NO_GO")
                self.assertEqual(outbox.effect_count(), 0)
                self.assertIsNone(outbox.claim_next("again", now=NOW))
            finally:
                store.close()

    def test_06_positive_reconcile_after_lost_ack_keeps_uncertain(self):
        with tempfile.TemporaryDirectory() as root:
            adapter = UntrustedPositive("lost-ack")
            _, store, outbox, key, first = self.case(root, adapter)
            try:
                self.assertEqual(first["state"], "UNCERTAIN")
                out = outbox.reconcile(
                    key, adapter=adapter, authorize=self.helper.authorize, now=NOW,
                )
                self.assertEqual(out["state"], "UNCERTAIN")
                self.assertEqual(out["reconcile_state"], "UNTRUSTED_POSITIVE_HARD_NO_GO")
                self.assertEqual(outbox.effect_count(), 0)
                self.assertEqual(adapter.send_calls, 1)
            finally:
                store.close()

    def test_07_missing_reconcile_effect_ref_still_no_confirmation(self):
        with tempfile.TemporaryDirectory() as root:
            adapter = UntrustedPositive("pending", "positive-no-ref")
            _, store, outbox, key, _ = self.case(root, adapter)
            try:
                out = outbox.reconcile(
                    key, adapter=adapter, authorize=self.helper.authorize, now=NOW,
                )
                self.assertEqual(out["state"], "SENT")
                self.assertEqual(outbox.effect_count(), 0)
            finally:
                store.close()

    def test_08_direct_private_confirm_entrypoint_denied(self):
        with tempfile.TemporaryDirectory() as root:
            _, store, outbox, key = self.helper.seed_claim(root)
            try:
                with self.assertRaisesRegex(PermissionError, "INDEPENDENT_EFFECT_RECEIPT_REQUIRED"):
                    outbox._confirm(
                        key, effect_ref="FAKE", confirmed_at=NOW,
                        result={"confirmed": True},
                    )
                self.assertEqual(outbox.effect_count(), 0)
                self.assertEqual(outbox.get(key)["state"], "CLAIMED")
            finally:
                store.close()

    def test_09_repeat_reconcile_never_confirms(self):
        with tempfile.TemporaryDirectory() as root:
            adapter = UntrustedPositive("pending")
            _, store, outbox, key, _ = self.case(root, adapter)
            try:
                for _ in range(3):
                    out = outbox.reconcile(
                        key, adapter=adapter, authorize=self.helper.authorize, now=NOW,
                    )
                    self.assertEqual(out["state"], "SENT")
                    self.assertEqual(outbox.effect_count(), 0)
                self.assertEqual(adapter.reconcile_calls, 3)
            finally:
                store.close()

    def test_10_stale_positive_reconcile_cannot_overwrite_newer_marker(self):
        with tempfile.TemporaryDirectory() as root:
            adapter = UntrustedPositive("pending")
            path, store, outbox, key, _ = self.case(root, adapter)
            entered, released = Event(), Event()

            class StalePositive:
                def reconcile(self, key, decision):
                    entered.set()
                    if not released.wait(timeout=20):
                        raise AssertionError("synchronization failure")
                    return {"found": True, "confirmed": True, "effect_ref": "FAKE"}

            def old_reader():
                local_store = SQLiteChatStore(path)
                try:
                    return SyntheticFirstAttemptOutboxLab(local_store, SCOPE).reconcile(
                        key, adapter=StalePositive(),
                        authorize=self.helper.authorize, now=NOW,
                    )
                finally:
                    local_store.close()

            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(old_reader)
                    self.assertTrue(entered.wait(timeout=20))
                    try:
                        newer = outbox.reconcile(
                            key, adapter=adapter, authorize=self.helper.authorize,
                            now=NOW,
                        )
                        self.assertEqual(
                            newer["reconcile_state"], "UNTRUSTED_POSITIVE_HARD_NO_GO",
                        )
                    finally:
                        released.set()
                    stale = future.result(timeout=25)
                self.assertEqual(stale["state"], "SENT")
                self.assertEqual(
                    stale["reconcile_state"], "NOT_RECONCILED_STATE_CHANGED",
                )
                self.assertEqual(outbox.effect_count(), 0)
            finally:
                store.close()

    def test_11_rejected_positive_claim_does_not_requeue(self):
        with tempfile.TemporaryDirectory() as root:
            adapter = UntrustedPositive("rejected-positive")
            _, store, outbox, key, result = self.case(root, adapter)
            try:
                self.assertEqual(result["state"], "UNCERTAIN")
                self.assertEqual(
                    result["dispatch_state"], "UNCERTAIN_RECONCILE_REQUIRED",
                )
                self.assertEqual(outbox.effect_count(), 0)
                self.assertIsNone(outbox.claim_next("again", now=NOW))
            finally:
                store.close()

    def test_12_fake_absence_cannot_reenable_after_positive(self):
        with tempfile.TemporaryDirectory() as root:
            adapter = UntrustedPositive("positive", "absence")
            _, store, outbox, key, first = self.case(root, adapter)
            try:
                self.assertEqual(first["state"], "UNCERTAIN")
                out = outbox.reconcile(
                    key, adapter=adapter, authorize=self.helper.authorize, now=NOW,
                )
                self.assertEqual(out["state"], "UNCERTAIN")
                self.assertEqual(out["reconcile_state"], "ABSENCE_UNVERIFIED_HARD_NO_GO")
                self.assertIsNone(outbox.claim_next("again", now=NOW))
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
