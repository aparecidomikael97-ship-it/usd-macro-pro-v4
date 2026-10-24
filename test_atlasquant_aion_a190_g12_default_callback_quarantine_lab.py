"""A190 G12: default quarantine for caller-injected synthetic Outbox callbacks.

All adapters here are objects in a temporary Python process. Nothing is sent.
The explicit unsafe LAB opt-in is NOT an authentication or production gate.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox


NOW = datetime(2026, 10, 23, 16, 0, tzinfo=timezone.utc)


class TrapAdapter:
    """Even attribute lookup of a hostile adapter must not occur by default."""

    def __init__(self):
        self.touches = 0

    @property
    def send(self):
        self.touches += 1
        raise AssertionError("unsafe adapter.send attribute lookup")

    @property
    def reconcile(self):
        self.touches += 1
        raise AssertionError("unsafe adapter.reconcile attribute lookup")


class MemoryOnlyAdapter:
    def __init__(self):
        self.send_calls = 0
        self.reconcile_calls = 0

    def send(self, _decision, key):
        self.send_calls += 1
        return {
            "accepted": True,
            "confirmed": True,
            "effect_ref": "LAB-ONLY-" + key[:24].upper(),
        }

    def reconcile(self, key, _decision):
        self.reconcile_calls += 1
        return {
            "found": True,
            "confirmed": True,
            "effect_ref": "LAB-ONLY-" + key[:24].upper(),
        }


class G12DefaultCallbackQuarantineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-g12-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "outbox.sqlite3"
        self.scope = Scope("synthetic-owner", "synthetic-tenant", "synthetic-workspace")
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)

    def outbox(self, *, unsafe=False, guard=None, evidence=None):
        return ExecutionOutbox(
            self.store, self.scope,
            first_attempt_guard=guard,
            evidence_verifier=evidence,
            unsafe_allow_synthetic_lab_callbacks=unsafe,
        )

    def enqueue(self, outbox, ref="same-original", aggregate="aggregate-one"):
        return outbox.enqueue(
            intent_ref=ref, action="synthetic-only",
            payload={"kind": "fixed-synthetic-business-intent"},
            aggregate_key=aggregate, policy_version="LAB-POLICY",
            authorization_ref="LAB-AUTH", created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )

    def policy(self, decision):
        return {
            "allowed": True,
            "actor_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "policy_version": decision["policy_version"],
            "authorization_ref": decision["authorization_ref"],
            "reauthenticated": True,
        }

    def dispatch(self, outbox, key, adapter, worker="worker-one"):
        claimed = outbox.claim_next(worker, now=NOW, lease_seconds=60)
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["idempotency_key"], key)
        return outbox.dispatch_claimed(
            key, worker_id=worker, authorize=self.policy,
            adapter=adapter, now=NOW + timedelta(seconds=1),
        )

    def test_01_true_callbacks_default_never_touch_adapter_property(self):
        outbox = self.outbox(guard=lambda _: True, evidence=lambda *_: True)
        item = self.enqueue(outbox)
        trap = TrapAdapter()
        result = self.dispatch(outbox, item["idempotency_key"], trap)
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(result["dispatch_state"], "UNCERTAIN_PRE_DISPATCH_RESERVATION_REQUIRED")
        self.assertEqual(result["last_error"], "FIRST_ATTEMPT_WITNESS_UNVERIFIED_NO_SEND")
        self.assertEqual(trap.touches, 0)
        self.assertEqual(outbox.effect_count(), 0)
        print("G12_DEFAULT_TRUE_CALLBACKS=NO_SEND_NO_ADAPTER_LOOKUP")

    def test_02_true_callbacks_default_never_confirm_on_reconcile(self):
        outbox = self.outbox(guard=lambda _: True, evidence=lambda *_: True)
        item = self.enqueue(outbox)
        adapter = MemoryOnlyAdapter()
        self.dispatch(outbox, item["idempotency_key"], adapter)
        self.assertEqual(adapter.send_calls, 0)
        followup = outbox.reconcile(
            item["idempotency_key"], adapter=TrapAdapter(),
            authorize=self.policy, now=NOW + timedelta(seconds=2),
        )
        self.assertEqual(followup["state"], "UNCERTAIN")
        self.assertEqual(followup["reconcile_state"], "EXTERNAL_TRUST_NOT_CONFIGURED")
        self.assertEqual(outbox.effect_count(), 0)
        print("G12_DEFAULT_RECONCILE=NO_CONFIRM_NO_ADAPTER_LOOKUP")

    def test_03_after_reopen_new_true_callbacks_cannot_confirm(self):
        outbox = self.outbox(guard=lambda _: True, evidence=lambda *_: True)
        item = self.enqueue(outbox)
        self.dispatch(outbox, item["idempotency_key"], TrapAdapter())
        self.store.close()
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        reopened = self.outbox(guard=lambda _: True, evidence=lambda *_: True)
        trap = TrapAdapter()
        state = reopened.reconcile(
            item["idempotency_key"], adapter=trap,
            authorize=self.policy, now=NOW + timedelta(seconds=5),
        )
        self.assertEqual(state["state"], "UNCERTAIN")
        self.assertEqual(trap.touches, 0)
        self.assertEqual(reopened.effect_count(), 0)
        print("G12_REOPEN_TRUE_CALLBACK=STILL_UNCERTAIN_ZERO_EFFECT")

    def test_04_neither_string_nor_integer_opt_in_allowed(self):
        for bad in ("True", 1, None, [], {"unsafe": True}):
            with self.subTest(value=repr(bad)):
                with self.assertRaisesRegex(TypeError, "must be bool"):
                    ExecutionOutbox(
                        self.store, self.scope,
                        first_attempt_guard=lambda _: True,
                        unsafe_allow_synthetic_lab_callbacks=bad,
                    )
        print("G12_UNSAFE_LAB_OPT_IN=STRICT_BOOL_ONLY")

    def test_05_explicit_lab_opt_in_still_simulates_without_real_provider(self):
        outbox = self.outbox(
            unsafe=True, guard=lambda _: True, evidence=lambda *_: True,
        )
        item = self.enqueue(outbox)
        adapter = MemoryOnlyAdapter()
        result = self.dispatch(outbox, item["idempotency_key"], adapter)
        self.assertEqual(result["state"], "CONFIRMED")
        self.assertEqual(adapter.send_calls, 1)
        self.assertEqual(outbox.effect_count(), 1)
        print("G12_EXPLICIT_UNSAFE_LAB_ONLY=MEMORY_EFFECT_NOT_AUTHORITY_RED")

    def test_06_explicit_lab_opt_in_without_witness_stays_closed(self):
        outbox = self.outbox(unsafe=True, evidence=lambda *_: True)
        item = self.enqueue(outbox)
        trap = TrapAdapter()
        result = self.dispatch(outbox, item["idempotency_key"], trap)
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(trap.touches, 0)
        print("G12_LAB_WITHOUT_WITNESS=UNCERTAIN_NO_SEND")

    def test_07_separate_relabelled_claims_still_no_send_by_default(self):
        outbox = self.outbox(guard=lambda _: True, evidence=lambda *_: True)
        a = self.enqueue(outbox, ref="original-event", aggregate="first-aggregate")
        b = self.enqueue(outbox, ref="relabelled-event", aggregate="second-aggregate")
        self.assertNotEqual(a["idempotency_key"], b["idempotency_key"])
        trap = TrapAdapter()
        first = self.dispatch(outbox, a["idempotency_key"], trap, worker="worker-a")
        second = self.dispatch(outbox, b["idempotency_key"], trap, worker="worker-b")
        self.assertEqual(first["state"], "UNCERTAIN")
        self.assertEqual(second["state"], "UNCERTAIN")
        self.assertEqual(trap.touches, 0)
        print("G12_TWO_DIFFERENT_REFS_DEFAULT=ZERO_ADAPTER_ACCESS")

    def test_08_uncertain_is_not_reopened_as_retry_after_lease_expiry(self):
        outbox = self.outbox(guard=lambda _: True)
        item = self.enqueue(outbox)
        self.dispatch(outbox, item["idempotency_key"], TrapAdapter())
        released = outbox.release_expired_claims(now=NOW + timedelta(minutes=2))
        self.assertEqual(released, 0)
        self.assertIsNone(outbox.claim_next("worker-two", now=NOW + timedelta(minutes=2)))
        self.assertEqual(outbox.get(item["idempotency_key"])["state"], "UNCERTAIN")
        print("G12_DEFAULT_UNCERTAIN=ZERO_AUTO_RESEND")

    def test_09_lab_missing_send_after_reservation_stays_uncertain(self):
        outbox = self.outbox(unsafe=True, guard=lambda _: True)
        item = self.enqueue(outbox)
        result = self.dispatch(outbox, item["idempotency_key"], object())
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(result["last_error"], "ADAPTER_SEND_MISSING_NO_SEND")
        self.assertEqual(result["dispatch_state"], "UNCERTAIN_RECONCILE_REQUIRED")
        print("G12_LAB_MISSING_ADAPTER=UNCERTAIN_NO_SEND")


if __name__ == "__main__":
    unittest.main()
