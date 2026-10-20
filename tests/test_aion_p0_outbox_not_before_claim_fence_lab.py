"""P0 LAB: an Outbox intent cannot be claimed before its creation timestamp.

Tests use actual ExecutionOutbox + SQLiteChatStore and a disposable database.
The timestamp is caller-provided, NOT an external time authority. Even passing
all tests cannot approve first effect, HUMAN_OWNER, receipt or H0 rollback.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

T0 = datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc)
SCOPE = Scope("not-before-owner", "not-before-tenant", "not-before-space")


class RealOutboxNotBeforeClaimTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-p0-not-before-")
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteChatStore(Path(self.tmp.name) / "execution.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(self.store, SCOPE)

    def enqueue(self, ref="future", start=T0 + timedelta(minutes=1),
                end=T0 + timedelta(minutes=4)):
        return self.outbox.enqueue(
            intent_ref=ref, action="synthetic-no-provider",
            payload={"intent": ref}, aggregate_key=ref,
            policy_version="lab", authorization_ref="non-authoritative-lab",
            created_at=start, valid_until=end,
        )

    def assert_pending(self, key):
        row = self.outbox.get(key)
        self.assertEqual(row["state"], "PENDING")
        self.assertEqual(row["attempts"], 0)
        self.assertEqual(row["lease_owner"], "")
        self.assertEqual(row["lease_until"], "")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_01_future_created_pending_is_not_claimable(self):
        key = self.enqueue()["idempotency_key"]
        self.assertIsNone(self.outbox.claim_next("lab", now=T0))
        self.assert_pending(key)

    def test_02_exact_creation_instant_is_admissible_for_staging(self):
        key = self.enqueue()["idempotency_key"]
        claim = self.outbox.claim_next("lab", now=T0 + timedelta(minutes=1))
        self.assertEqual(claim["idempotency_key"], key)
        self.assertEqual(claim["state"], "CLAIMED")
        self.assertEqual(claim["attempts"], 1)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_03_future_created_retry_does_not_bypass_gate(self):
        key = self.enqueue()["idempotency_key"]
        with self.outbox.db:
            self.outbox.db.execute(
                "UPDATE action_outbox SET state='RETRY' WHERE idempotency_key=?",
                (key,),
            )
        self.assertIsNone(self.outbox.claim_next("lab", now=T0))
        row = self.outbox.get(key)
        self.assertEqual(row["state"], "RETRY")
        self.assertEqual(row["attempts"], 0)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_04_mature_intent_claims_while_future_one_waits(self):
        future = self.enqueue("future")
        mature = self.enqueue("mature", start=T0 - timedelta(seconds=30),
                              end=T0 + timedelta(minutes=4))
        claim = self.outbox.claim_next("lab", now=T0)
        self.assertEqual(claim["idempotency_key"], mature["idempotency_key"])
        self.assert_pending(future["idempotency_key"])
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_05_future_intent_admitted_at_start_but_denied_after_expiry(self):
        key = self.enqueue()["idempotency_key"]
        self.assertIsNone(self.outbox.claim_next("lab", now=T0))
        self.assertIsNone(self.outbox.claim_next(
            "lab", now=T0 + timedelta(minutes=4)))
        self.assert_pending(key)
        claimed = self.outbox.claim_next("lab", now=T0 + timedelta(minutes=2))
        self.assertEqual(claimed["idempotency_key"], key)
        self.assertEqual(claimed["state"], "CLAIMED")
        self.assertEqual(self.outbox.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
