"""V16-A.21 -- adversarial RED acceptance contracts on the REAL Outbox module.

This file is intentionally expected to FAIL on the A.20 candidate: an
adapter-supplied confirmed=True/effect_ref is not independent producer proof.
The provider is not invoked. No trusted positive receipt verifier exists.

Keep RED in this LAB Draft until an independently pinned producer trust root,
causal receipt and external witness are implemented and independently tested.
These 3 tests are NOT the previously authored A.12+A.16 original 37+8.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox


NOW = datetime(2026, 10, 13, 13, 0, tzinfo=timezone.utc)


def fixture_authority(scope):
    """Synthetic authorization ONLY; it confers zero productive authority."""
    def check(_decision):
        return {
            "allowed": True,
            "actor_id": scope.owner_id,
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "policy_version": "policy-v1",
            "authorization_ref": "approval-fixture-only",
        }
    return check


class ClaimsConfirmedWithoutProducer:
    def __init__(self):
        self.calls = 0
        self.real_effects = 0

    def send(self, _decision, _key):
        self.calls += 1
        # Deliberately fabricates claims, never calls a producer.
        return {
            "accepted": True,
            "confirmed": True,
            "effect_ref": "CALLER-FORGED-POSITIVE",
        }


class ClaimsReconciledWithoutProducer:
    def __init__(self):
        self.send_calls = 0
        self.reconcile_calls = 0
        self.real_effects = 0

    def send(self, _decision, _key):
        self.send_calls += 1
        return {
            "accepted": True,
            "confirmed": False,
            "effect_ref": "UNVERIFIED-SEND-REF",
        }

    def reconcile(self, _key, _decision):
        self.reconcile_calls += 1
        # Deliberately forges a positive receipt instead of citing any issuer.
        return {
            "found": True,
            "confirmed": True,
            "effect_ref": "CALLER-FORGED-RECONCILE-POSITIVE",
        }


class RejectsWithoutProducer:
    def __init__(self):
        self.calls = 0

    def send(self, _decision, _key):
        self.calls += 1
        return {"accepted": False, "retryable": True, "reason": "fixture negative"}


class AionUntrustedPositiveAdmissionRedTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.store = SQLiteChatStore(Path(self.root.name) / "chat.sqlite3")
        self.scope = Scope("fixture-owner", "tenant-a", "workspace-a")
        self.outbox = ExecutionOutbox(self.store, self.scope)
        self.item = self.outbox.enqueue(
            intent_ref="intent-false-positive-A21",
            action="send_email",
            payload={"fixture": "no producer exists"},
            aggregate_key="client-false-positive-A21",
            policy_version="policy-v1",
            authorization_ref="approval-fixture-only",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )
        self.key = self.item["idempotency_key"]
        self.outbox.claim_next("worker-fixture", now=NOW, lease_seconds=60)

    def tearDown(self):
        self.store.close()
        self.root.cleanup()

    def _dispatch(self, adapter):
        return self.outbox.dispatch_claimed(
            self.key,
            worker_id="worker-fixture",
            authorize=fixture_authority(self.scope),
            adapter=adapter,
            now=NOW + timedelta(seconds=1),
        )

    def test_unverified_positive_from_send_must_not_record_real_effect(self):
        """EXPECTED RED: caller can currently forge CONFIRMED and effect ledger."""
        adapter = ClaimsConfirmedWithoutProducer()
        result = self._dispatch(adapter)
        self.assertEqual(adapter.calls, 1)
        self.assertEqual(adapter.real_effects, 0)
        self.assertIn(
            result["state"], ("UNCERTAIN", "SENT"),
            "an adapter-supplied bool must not be admitted as producer proof",
        )
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_unverified_positive_from_reconcile_must_not_record_real_effect(self):
        """EXPECTED RED: caller can currently forge the reconciling receipt."""
        adapter = ClaimsReconciledWithoutProducer()
        sent = self._dispatch(adapter)
        self.assertEqual(sent["state"], "SENT")
        reconciled = self.outbox.reconcile(
            self.key,
            adapter=adapter,
            authorize=fixture_authority(self.scope),
            now=NOW + timedelta(seconds=2),
        )
        self.assertEqual(adapter.send_calls, 1)
        self.assertEqual(adapter.reconcile_calls, 1)
        self.assertEqual(adapter.real_effects, 0)
        self.assertIn(
            reconciled["state"], ("SENT", "UNCERTAIN"),
            "a self-attested reconciliation must not prove a real effect",
        )
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_existing_unverified_negative_remains_quarantined(self):
        """EXPECTED GREEN control: A.20 does not trust negative adapter claims."""
        adapter = RejectsWithoutProducer()
        result = self._dispatch(adapter)
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(result["dispatch_state"], "UNCERTAIN_PROOF_REQUIRED")
        self.assertEqual(adapter.calls, 1)
        self.assertEqual(self.outbox.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
