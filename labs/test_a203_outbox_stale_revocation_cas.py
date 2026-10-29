"""A203 RED-first proof: stale local auth denial must not rewrite a newer effect.

Uses actual SQLiteChatStore WAL, two connections in distinct threads,
the same claimed worker, and synthetic in-memory effects. No providers.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from labs.a259_synthetic_outbox_fixture import SyntheticFirstAttemptOutboxLab
# Import the module, not its TestCase class into this test module.
# unittest discovers imported TestCase classes and otherwise runs A202 twice.
from labs import test_a202_outbox_dispatch_atomic_cas as a202

FakeNonIdempotentEffect=a202.FakeNonIdempotentEffect
NOW=a202.NOW
SCOPE=a202.SCOPE
WORKER=a202.WORKER


class _EffectThenUnknown(FakeNonIdempotentEffect):
    def send(self, decision, key):
        super().send(decision, key)
        raise TimeoutError("synthetic ACK lost after local effect")


class A203StaleAuthorizationOutboxTests(unittest.TestCase):
    def fixture(self, root):
        helper = a202.A202SameLeaseOwnerDispatchRaceTests()
        return helper.seed_claim(root), helper

    def run_stale_revocation_case(self, adapter, expected_state):
        with tempfile.TemporaryDirectory() as tmp:
            (path,seed_store,outbox,key),helper=self.fixture(tmp)
            entered=Event()
            released=Event()
            try:
                def stale_auth(_decision):
                    entered.set()
                    if not released.wait(timeout=20):
                        raise AssertionError("test synchronization timeout")
                    return {
                        **helper.authorize(_decision),
                        "allowed": False,
                    }

                def old_decision_attempt():
                    separate_store=SQLiteChatStore(path)
                    try:
                        separate_outbox=SyntheticFirstAttemptOutboxLab(separate_store, SCOPE, first_attempt_guard=lambda _intent: True)
                        return separate_outbox.dispatch_claimed(
                            key,
                            worker_id=WORKER,
                            authorize=stale_auth,
                            adapter=adapter,
                            now=NOW,
                        )
                    finally:
                        separate_store.close()

                with ThreadPoolExecutor(max_workers=1) as pool:
                    pending=pool.submit(old_decision_attempt)
                    self.assertTrue(entered.wait(timeout=20))
                    try:
                        successful_or_uncertain=outbox.dispatch_claimed(
                            key,
                            worker_id=WORKER,
                            authorize=helper.authorize,
                            adapter=adapter,
                            now=NOW,
                        )
                        self.assertEqual(successful_or_uncertain["state"],expected_state)
                    finally:
                        released.set()
                    stale=pending.result(timeout=20)

                actual=outbox.get(key)
                self.assertEqual(len(adapter.effects),1)
                # The stale authorization must not overwrite a newer
                # CONFIRMED or UNCERTAIN effect boundary with REVOKED.
                self.assertEqual(
                    actual["state"],expected_state,
                    "A203_STALE_REVOCATION_OVERWROTE_EXTERNAL_EFFECT_STATE_RED",
                )
                self.assertEqual(stale["state"],expected_state)
                self.assertEqual(outbox.effect_count(),0)
                return actual
            finally:
                seed_store.close()

    def test_01_stale_revoke_cannot_overwrite_quarantined_positive(self):
        self.run_stale_revocation_case(
            FakeNonIdempotentEffect(),
            "UNCERTAIN",
        )

    def test_02_stale_revoke_cannot_mask_uncertain_effect(self):
        result=self.run_stale_revocation_case(
            _EffectThenUnknown(),
            "UNCERTAIN",
        )
        self.assertIn("SEND_RESULT_UNKNOWN",result["last_error"])

    def test_03_revocation_of_still_claimed_intent_still_blocks_without_send(self):
        with tempfile.TemporaryDirectory() as tmp:
            (_,store,outbox,key),helper=self.fixture(tmp)
            try:
                adapter=FakeNonIdempotentEffect()
                result=outbox.dispatch_claimed(
                    key,worker_id=WORKER,
                    authorize=lambda d:{**helper.authorize(d),"allowed":False},
                    adapter=adapter,now=NOW,
                )
                self.assertEqual(result["state"],"REVOKED")
                self.assertEqual(adapter.effects,[])
                self.assertEqual(outbox.get(key)["state"],"REVOKED")
            finally:
                store.close()


if __name__=="__main__":
    unittest.main()
