"""A190 G6 LAB — real ExecutionOutbox callback trust-boundary negative controls.

No operational adapter, provider request, network access, credentials, true
HUMAN_OWNER or independent signer. A test adapter only counts in-memory calls.
Test success on caller-controlled true callbacks is a RED finding, not approval.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from test_atlasquant_aion_a190_g3_first_intent_contract_lab import (
    event, signed_query, synthetic_keys_and_pins, verifier_for,
)


NOW = datetime(2026, 10, 23, 13, 0, tzinfo=timezone.utc)


class MemoryOnlyAdapter:
    """A deterministic recording fake; absolutely no outgoing effects."""

    def __init__(self):
        self.send_calls = []
        self.reconcile_calls = []

    def send(self, decision, key):
        self.send_calls.append((decision["intent_ref"], key))
        return {
            "accepted": True, "confirmed": True,
            "effect_ref": "LAB-ONLY-" + key[:20].upper(),
        }

    def reconcile(self, key, _decision):
        self.reconcile_calls.append(key)
        return {
            "found": True, "confirmed": True,
            "effect_ref": "LAB-ONLY-" + key[:20].upper(),
        }


class A190G6RealOutboxCallbackBoundaryLabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="a190-g6-outbox-")
        self.addCleanup(self.tmp.cleanup)
        self.scope = Scope(
            owner_id="synthetic-owner", tenant_id="synthetic-tenant",
            workspace_id="synthetic-workspace",
        )
        self.store = SQLiteChatStore(Path(self.tmp.name) / "outbox.sqlite")
        self.addCleanup(self.store.close)
        self.adapter = MemoryOnlyAdapter()

    def _outbox(self, *, guard=None, evidence=None):
        return ExecutionOutbox(
            self.store, self.scope, first_attempt_guard=guard,
            evidence_verifier=evidence,
        )

    def _enqueue(self, outbox, *, ref="claimed-original-e1", aggregate="same-operation"):
        return outbox.enqueue(
            intent_ref=ref,
            action="no-real-send",
            payload={"synthetic_event": "exact-same-business-intent"},
            aggregate_key=aggregate,
            policy_version="LAB-POLICY",
            authorization_ref="SYNTHETIC-OWNER-AUTH",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )

    def _policy(self, decision):
        return {
            "allowed": True,
            "actor_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "policy_version": decision["policy_version"],
            "authorization_ref": decision["authorization_ref"],
            "reauthenticated": True,
            "reauth_ref": decision.get("reauth_ref", ""),
        }

    def _claim_and_dispatch(self, outbox, key, worker="synthetic-worker"):
        claimed = outbox.claim_next(worker, now=NOW, lease_seconds=60)
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["idempotency_key"], key)
        return outbox.dispatch_claimed(
            key, worker_id=worker, authorize=self._policy,
            adapter=self.adapter, now=NOW + timedelta(seconds=1),
        )

    def test_missing_first_attempt_guard_never_crosses_send_boundary(self):
        outbox = self._outbox(evidence=lambda *_args: True)
        item = self._enqueue(outbox)
        result = self._claim_and_dispatch(outbox, item["idempotency_key"])
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(
            result["dispatch_state"], "UNCERTAIN_PRE_DISPATCH_RESERVATION_REQUIRED",
        )
        self.assertEqual(len(self.adapter.send_calls), 0)
        self.assertEqual(outbox.effect_count(), 0)
        print("A190_G6_NO_FIRST_ATTEMPT_GUARD=REAL_OUTBOX_NO_SEND")

    def test_synthetic_signed_a183_lab_verified_never_grants_send_flag(self):
        private, pins = synthetic_keys_and_pins(41)
        attested = verifier_for(pins).admit(
            "RESERVATION", event("unrelated-fixture-event"),
            signed_query(private, pins, sequence=1),
        )
        self.assertIsNotNone(attested)
        self.assertTrue(attested["lab_verified"])
        self.assertFalse(attested["permits_send"])
        outbox = self._outbox(
            guard=lambda _intent: attested["permits_send"],
            evidence=lambda *_args: True,
        )
        item = self._enqueue(outbox)
        result = self._claim_and_dispatch(outbox, item["idempotency_key"])
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(len(self.adapter.send_calls), 0)
        print("A190_G6_A183_SIGNED_FIXTURE_PERMITS_SEND_FALSE=REAL_OUTBOX_NO_SEND")

    def test_truthy_caller_callbacks_fake_authority_and_confirm_effect_red(self):
        outbox = self._outbox(
            guard=lambda _intent: True,
            evidence=lambda *_args: True,
        )
        item = self._enqueue(outbox)
        result = self._claim_and_dispatch(outbox, item["idempotency_key"])
        self.assertEqual(result["state"], "CONFIRMED")
        self.assertEqual(result["dispatch_state"], "CONFIRMED")
        self.assertEqual(len(self.adapter.send_calls), 1)
        self.assertEqual(outbox.effect_count(), 1)
        print("A190_G6_CALLER_TRUE_GUARD_AND_RECEIPT=IN_MEMORY_SEND_CONFIRMED_RED")

    def test_true_guard_can_call_adapter_without_any_evidence_verifier_red(self):
        outbox = self._outbox(guard=lambda _intent: True)
        item = self._enqueue(outbox)
        result = self._claim_and_dispatch(outbox, item["idempotency_key"])
        self.assertEqual(result["state"], "SENT")
        self.assertEqual(result["dispatch_state"], "SENT_RECONCILE_REQUIRED")
        self.assertEqual(len(self.adapter.send_calls), 1)
        self.assertEqual(outbox.effect_count(), 0)
        print("A190_G6_CALLER_TRUE_GUARD_WITHOUT_RECEIPT=ADAPTER_CROSSED_RED")

    def test_guard_timeout_keeps_uncertain_and_never_calls_adapter(self):
        def timed_out(_intent):
            raise TimeoutError("unavailable independent witness fixture")
        outbox = self._outbox(guard=timed_out, evidence=lambda *_args: True)
        item = self._enqueue(outbox)
        result = self._claim_and_dispatch(outbox, item["idempotency_key"])
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(len(self.adapter.send_calls), 0)
        self.assertEqual(outbox.effect_count(), 0)
        print("A190_G6_FIRST_ATTEMPT_WITNESS_TIMEOUT=UNCERTAIN_NO_SEND")

    def test_replacing_verifier_after_send_can_confirm_self_attested_receipt_red(self):
        old = self._outbox(guard=lambda _intent: True)
        item = self._enqueue(old)
        result = self._claim_and_dispatch(old, item["idempotency_key"])
        self.assertEqual(result["state"], "SENT")
        self.assertEqual(len(self.adapter.send_calls), 1)
        self.assertEqual(old.effect_count(), 0)

        # Construct another in-process Outbox against the SAME real store,
        # replacing the missing provenance verifier by a trivial true callback.
        replaced = self._outbox(evidence=lambda *_args: True)
        after = replaced.reconcile(
            item["idempotency_key"],
            adapter=self.adapter,
            authorize=self._policy,
            now=NOW + timedelta(seconds=2),
        )
        self.assertEqual(after["state"], "CONFIRMED")
        self.assertEqual(after["reconcile_state"], "CONFIRMED")
        self.assertEqual(replaced.effect_count(), 1)
        self.assertEqual(len(self.adapter.send_calls), 1)
        print("A190_G6_VERIFIER_REPLACED_AFTER_SEND=FORGED_LOCAL_CONFIRMATION_RED")

    def test_two_relabelled_refs_same_business_intent_cross_two_send_calls_red(self):
        outbox = self._outbox(
            guard=lambda _intent: True, evidence=lambda *_args: True,
        )
        first = self._enqueue(outbox, ref="claimed-original-e1")
        second = self._enqueue(outbox, ref="attacker-relabelled-e2")
        self.assertNotEqual(first["idempotency_key"], second["idempotency_key"])
        self.assertEqual(first["decision"]["payload_digest"], second["decision"]["payload_digest"])
        first_result = self._claim_and_dispatch(
            outbox, first["idempotency_key"], worker="first-worker",
        )
        self.assertEqual(first_result["state"], "CONFIRMED")
        second_result = self._claim_and_dispatch(
            outbox, second["idempotency_key"], worker="second-worker",
        )
        self.assertEqual(second_result["state"], "CONFIRMED")
        self.assertEqual(len(self.adapter.send_calls), 2)
        self.assertEqual(outbox.effect_count(), 2)
        print("A190_G6_DIFFERENT_INTENT_REFS_SAME_SEMANTIC_EVENT=TWO_MEMORY_SENDS_RED")

    def test_miswired_lab_verified_flag_on_unrelated_signed_event_crosses_guard_red(self):
        private, pins = synthetic_keys_and_pins(41)
        attested = verifier_for(pins).admit(
            "RESERVATION", event("completely-unrelated-fixture-id"),
            signed_query(private, pins, sequence=1),
        )
        self.assertIsNotNone(attested)
        self.assertFalse(attested["permits_send"])
        # The host could incorrectly treat an authentic fixture's syntactic
        # 'lab_verified' as actual dispatch authority. There is NO event binding
        # between this A183 response and the following Outbox decision.
        miswired = self._outbox(
            guard=lambda _intent: attested["lab_verified"],
            evidence=lambda *_args: True,
        )
        item = self._enqueue(miswired, ref="different-unsignable-event")
        result = self._claim_and_dispatch(miswired, item["idempotency_key"])
        self.assertEqual(result["state"], "CONFIRMED")
        self.assertEqual(len(self.adapter.send_calls), 1)
        print("A190_G6_A183_LAB_VERIFIED_MISWIRED_AS_AUTHORITY=SEND_BYPASS_RED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
