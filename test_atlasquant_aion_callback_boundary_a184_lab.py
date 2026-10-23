"""Synthetic callback fixtures only: data isolation is not external authority.

No network, provider, identity ceremony or genuine receipt is used here.
These regressions require fail-closed local handling of changed bindings and
independent copies across injected callback boundaries.
"""
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from test_atlasquant_aion_execution_outbox import NOW, policy


class CallbackBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.store = SQLiteChatStore(Path(self.root.name) / "chat.sqlite3")
        self.addCleanup(self.store.close)
        self.scope = Scope("synthetic-owner", "synthetic-tenant", "lab")
        self.original_payload = {"operation": {"target": "synthetic-original", "units": [1, 2]}}
        self.sent = []

    def claim(self, *, guard=lambda intent: True, verifier=lambda *args: True, budget=False):
        self.outbox = ExecutionOutbox(self.store, self.scope,
            first_attempt_guard=guard, evidence_verifier=verifier)
        extra = ({"transaction_id": "synthetic-tx", "authority_budget_ref": "synthetic-budget",
                  "risk_points": 1, "capability_class": "LAB"} if budget else {})
        row = self.outbox.enqueue(intent_ref="synthetic-intent", action="synthetic_action",
            payload=deepcopy(self.original_payload), aggregate_key="synthetic-aggregate",
            policy_version="policy-v1", authorization_ref="approval-1", created_at=NOW,
            valid_until=NOW + timedelta(minutes=5), **extra)
        self.key = row["idempotency_key"]
        self.outbox.claim_next("synthetic-worker", now=NOW, lease_seconds=60)

    def send(self, decision, key):
        self.sent.append(deepcopy(decision))
        return {"accepted": True, "confirmed": True, "effect_ref": "SYNTHETIC-EFFECT"}

    def dispatch(self, *, authorize=None, send=None, budget=None):
        return self.outbox.dispatch_claimed(self.key, worker_id="synthetic-worker",
            authorize=authorize or policy(self.scope), adapter=SimpleNamespace(send=send or self.send),
            cumulative_authority_guard=budget, now=NOW)

    def unchanged(self):
        self.assertEqual(self.outbox.get(self.key)["decision"]["payload"], self.original_payload)

    def test_authorizer_changed_nested_binding_denies_before_send(self):
        self.claim()
        def authorize(decision):
            decision["payload"]["operation"]["target"] = "synthetic-changed"
            return policy(self.scope)(decision)
        result = self.dispatch(authorize=authorize)
        self.assertEqual(result["state"], "REVOKED")
        self.assertEqual(self.sent, [])
        self.unchanged()

    def test_budget_changed_nested_binding_denies_before_send(self):
        self.claim(budget=True)
        def budget(decision):
            decision["payload"]["operation"]["units"].append(3)
            return {"allowed": True, "authority_budget_ref": "synthetic-budget",
                    "transaction_id": "synthetic-tx"}
        result = self.dispatch(budget=budget)
        self.assertEqual(result["state"], "BLOCKED_REAPPROVAL")
        self.assertEqual(self.sent, [])
        self.unchanged()

    def test_witness_changed_nested_binding_denies_and_stays_uncertain(self):
        def guard(intent):
            intent["decision"]["payload"]["operation"]["target"] = "synthetic-changed"
            return True
        self.claim(guard=guard)
        result = self.dispatch()
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(self.sent, [])
        self.assertIsNone(self.outbox.claim_next("other-worker", now=NOW + timedelta(minutes=2)))
        self.unchanged()

    def test_send_changed_nested_binding_never_confirms_or_retries(self):
        self.claim()
        def send(decision, key):
            decision["payload"]["operation"]["target"] = "synthetic-changed"
            return self.send(decision, key)
        result = self.dispatch(send=send)
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertEqual(self.outbox.release_expired_claims(now=NOW + timedelta(minutes=2)), 0)
        self.assertIsNone(self.outbox.claim_next("other-worker", now=NOW + timedelta(minutes=2)))
        self.unchanged()

    def test_verifier_changed_nested_intent_never_confirms(self):
        def verifier(kind, intent, result):
            intent["decision"]["payload"]["operation"]["units"].append(3)
            return True
        self.claim(verifier=verifier)
        result = self.dispatch()
        self.assertNotEqual(result["state"], "CONFIRMED")
        self.assertEqual(self.outbox.effect_count(), 0)
        self.unchanged()

    def test_verifier_changed_nested_result_never_confirms(self):
        def verifier(kind, intent, result):
            result["proof"]["binding"] = "synthetic-changed"
            return True
        self.claim(verifier=verifier)
        def send(decision, key):
            return dict(self.send(decision, key), proof={"binding": "synthetic-original"})
        result = self.dispatch(send=send)
        self.assertNotEqual(result["state"], "CONFIRMED")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_reconcile_changed_binding_never_confirms(self):
        self.claim()
        self.dispatch(send=lambda *args: {"accepted": True, "confirmed": False})
        def reconcile(key, decision):
            decision["payload"]["operation"]["target"] = "synthetic-changed"
            return {"found": True, "confirmed": True, "effect_ref": "SYNTHETIC-EFFECT"}
        result = self.outbox.reconcile(self.key, adapter=SimpleNamespace(reconcile=reconcile),
            authorize=policy(self.scope), now=NOW)
        self.assertNotEqual(result["state"], "CONFIRMED")
        self.assertEqual(self.outbox.effect_count(), 0)
        self.unchanged()

    def test_retained_authorizer_reference_cannot_change_later_send(self):
        retained = {}
        def authorize(decision):
            retained["decision"] = decision
            return policy(self.scope)(decision)
        def guard(intent):
            retained["decision"]["payload"]["operation"]["target"] = "synthetic-changed"
            return True
        self.claim(guard=guard)
        self.dispatch(authorize=authorize)
        self.assertEqual(self.sent[0]["payload"], self.original_payload)
        self.unchanged()

    def test_retained_witness_reference_cannot_change_verifier_binding(self):
        retained, verified = {}, []
        def guard(intent):
            retained["intent"] = intent
            return True
        def send(decision, key):
            retained["intent"]["decision"]["payload"]["operation"]["units"].append(3)
            return self.send(decision, key)
        def verifier(kind, intent, result):
            verified.append(deepcopy(intent["decision"]["payload"]))
            return True
        self.claim(guard=guard, verifier=verifier)
        self.dispatch(send=send)
        self.assertEqual(verified, [self.original_payload])
        self.unchanged()

    def test_retained_adapter_result_cannot_change_recorded_receipt(self):
        response = {"accepted": True, "confirmed": True, "effect_ref": "SYNTHETIC-EFFECT",
                    "proof": {"binding": "synthetic-original"}}
        def verifier(kind, intent, result):
            response["proof"]["binding"] = "synthetic-changed"
            return True
        self.claim(verifier=verifier)
        result = self.dispatch(send=lambda *args: response)
        self.assertEqual(result["state"], "CONFIRMED")
        stored = self.store.db.execute("SELECT data FROM action_effects WHERE idempotency_key=?",
                                       (self.key,)).fetchone()[0]
        self.assertEqual(json.loads(stored)["proof"]["binding"], "synthetic-original")


if __name__ == "__main__":
    unittest.main(verbosity=2)
