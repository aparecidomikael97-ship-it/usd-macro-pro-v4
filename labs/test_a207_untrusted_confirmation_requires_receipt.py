"""A207 RED-first: an adapter's positive assertion is NOT effect evidence.

No external provider, Worker, network, tokens or real SEND. These tests use
real SQLite via the A202 fixture and an injected adapter that never produces
any effect, but claims confirmed=True with an arbitrary effect_ref.

Expected before the fix: tests 01 and 02 fail RED. Do not "fix" them by
changing the fake to report a legitimate effect. A verified receipt must
come from an independent trust boundary, not another adapter flag.
"""
import tempfile
import unittest

from labs import test_a202_outbox_dispatch_atomic_cas as a202

NOW = a202.NOW
WORKER = a202.WORKER


class ForgedPositiveAdapter:
    def __init__(self, mode):
        self.mode = mode
        self.send_calls = 0
        self.reconcile_calls = 0
        self.actual_effects = []  # Intentionally NEVER written to.
        self.forged_ref = "UNTRUSTED-A207-NO-EFFECT"

    def send(self, decision, key):
        self.send_calls += 1
        if self.mode == "direct-false-confirmation":
            return {
                "accepted": True,
                "confirmed": True,
                "effect_ref": self.forged_ref,
            }
        return {
            "accepted": True,
            "confirmed": False,
            "effect_ref": "UNVERIFIED-PENDING-A207",
        }

    def reconcile(self, key, decision):
        self.reconcile_calls += 1
        return {
            "found": True,
            "confirmed": True,
            "effect_ref": self.forged_ref,
        }


class A207UntrustedPositiveConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.helper = a202.A202SameLeaseOwnerDispatchRaceTests()

    def test_01_direct_fake_positive_must_not_write_confirmed_ledger(self):
        with tempfile.TemporaryDirectory() as root:
            _, store, outbox, key = self.helper.seed_claim(root)
            adapter = ForgedPositiveAdapter("direct-false-confirmation")
            try:
                result = outbox.dispatch_claimed(
                    key, worker_id=WORKER,
                    authorize=self.helper.authorize,
                    adapter=adapter, now=NOW,
                )
                self.assertEqual(adapter.send_calls, 1)
                self.assertEqual(adapter.actual_effects, [])
                self.assertNotEqual(
                    result["state"], "CONFIRMED",
                    "A207_RED_ADAPTER_ASSERTION_FORGED_CONFIRMATION",
                )
                self.assertEqual(
                    outbox.effect_count(), 0,
                    "A207_RED_FABRICATED_EFFECT_REF_ENTERED_LEDGER",
                )
                self.assertIsNone(outbox.claim_next("worker-again", now=NOW))
            finally:
                store.close()

    def test_02_reconcile_fake_positive_must_not_write_confirmed_ledger(self):
        with tempfile.TemporaryDirectory() as root:
            _, store, outbox, key = self.helper.seed_claim(root)
            adapter = ForgedPositiveAdapter("sent-then-false-confirmation")
            try:
                sent = outbox.dispatch_claimed(
                    key, worker_id=WORKER,
                    authorize=self.helper.authorize,
                    adapter=adapter, now=NOW,
                )
                self.assertEqual(sent["state"], "SENT")
                self.assertEqual(outbox.effect_count(), 0)
                recon = outbox.reconcile(
                    key, adapter=adapter,
                    authorize=self.helper.authorize, now=NOW,
                )
                self.assertEqual(adapter.actual_effects, [])
                self.assertEqual(adapter.reconcile_calls, 1)
                self.assertNotEqual(
                    recon["state"], "CONFIRMED",
                    "A207_RED_RECONCILE_SELF_ATTESTED_FALSE_EFFECT",
                )
                self.assertEqual(
                    outbox.effect_count(), 0,
                    "A207_RED_RECONCILE_FORGED_LEDGER_ENTRY",
                )
                self.assertIsNone(outbox.claim_next("worker-again", now=NOW))
            finally:
                store.close()

    def test_03_control_unconfirmed_send_stays_sent_without_a_receipt(self):
        with tempfile.TemporaryDirectory() as root:
            _, store, outbox, key = self.helper.seed_claim(root)
            adapter = ForgedPositiveAdapter("sent-only")
            try:
                sent = outbox.dispatch_claimed(
                    key, worker_id=WORKER,
                    authorize=self.helper.authorize,
                    adapter=adapter, now=NOW,
                )
                self.assertEqual(sent["state"], "SENT")
                self.assertEqual(outbox.effect_count(), 0)
                self.assertEqual(adapter.actual_effects, [])
                self.assertIsNone(outbox.claim_next("worker-again", now=NOW))
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
