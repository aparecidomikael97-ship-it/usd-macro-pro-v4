"""A113 LAB: expired claims with possible-effect evidence must not re-enter RETRY.

All evidence is synthetic local SQLite adversarial data, NOT a producer receipt.
No adapter, Worker, network, external effect, or actual message is used.
These tests deliberately fail on the A112 pre-patch Outbox implementation.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)


class A113ExpiredClaimEvidenceQuarantine(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SQLiteChatStore(Path(self.temp.name) / "a113.sqlite3")
        self.addCleanup(self.store.close)
        self.scope = Scope("A113_OWNER", "A113_TENANT", "A113_WORKSPACE")
        self.outbox = ExecutionOutbox(self.store, self.scope)
        self.item = self.enqueue("a113-main", "a113-aggregate")
        self.key = self.item["idempotency_key"]
        got = self.outbox.claim_next(
            "a113-worker-one", now=NOW + timedelta(seconds=1), lease_seconds=5
        )
        self.assertIsNotNone(got)
        self.assertEqual(got["state"], "CLAIMED")
        self.expired = NOW + timedelta(seconds=7)

    def enqueue(self, ref, aggregate):
        return self.outbox.enqueue(
            intent_ref=ref, action="synthetic_staged_action",
            payload={"origin": "A113_SYNTHETIC"}, aggregate_key=aggregate,
            policy_version="a113-policy", authorization_ref="a113-local-only",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        )

    def mark(self, **fields):
        self.assertTrue(fields)
        assert all(k in {
            "state", "dispatch_started_at", "sent_at", "confirmed_at", "effect_ref"
        } for k in fields)
        sql = ", ".join(k + "=?" for k in fields)
        with self.outbox.db:
            self.outbox.db.execute(
                "UPDATE action_outbox SET " + sql + " WHERE idempotency_key=?",
                (*fields.values(), self.key),
            )

    def forged_effect(self):
        # Local attacker-controlled row. This is explicitly not proof of any send.
        with self.outbox.db:
            self.outbox.db.execute(
                """INSERT INTO action_effects (
                    idempotency_key,owner,tenant,workspace,effect_ref,confirmed_at,data
                ) VALUES (?,?,?,?,?,?,?)""",
                (self.key, self.scope.owner_id, self.scope.tenant_id,
                 self.scope.workspace_id, "LOCAL_FAKE_EFFECT", NOW.isoformat(), "{}"),
            )

    def assert_quarantined(self, state):
        original = self.outbox.get(self.key)
        self.assertEqual(original["state"], state)
        self.assertEqual(self.outbox.release_expired_claims(now=self.expired), 0)
        self.assertEqual(self.outbox.get(self.key), original)
        self.assertIsNone(self.outbox.claim_next("a113-worker-two", now=self.expired))
        self.assertEqual(self.outbox.get(self.key), original)

    def test_01_expired_claim_with_dispatch_started_is_not_retried(self):
        self.mark(dispatch_started_at=NOW.isoformat())
        self.assert_quarantined("CLAIMED")

    def test_02_expired_claim_with_effect_ledger_row_is_not_retried(self):
        self.forged_effect()
        self.assert_quarantined("CLAIMED")
        self.assertEqual(self.outbox.effect_count(), 1)

    def test_03_retry_state_with_dispatch_started_is_not_reclaimed(self):
        self.mark(state="RETRY", dispatch_started_at=NOW.isoformat())
        original = self.outbox.get(self.key)
        self.assertIsNone(self.outbox.claim_next("a113-worker-two", now=self.expired))
        self.assertEqual(self.outbox.get(self.key), original)

    def test_04_pending_with_effect_ledger_row_is_not_claimed(self):
        self.mark(state="PENDING")
        self.forged_effect()
        original = self.outbox.get(self.key)
        self.assertIsNone(self.outbox.claim_next("a113-worker-two", now=self.expired))
        self.assertEqual(self.outbox.get(self.key), original)

    def test_05_clean_expired_claim_can_be_released_and_reclaimed(self):
        self.assertEqual(self.outbox.release_expired_claims(now=self.expired), 1)
        self.assertEqual(self.outbox.get(self.key)["state"], "RETRY")
        claimed = self.outbox.claim_next("a113-worker-two", now=self.expired)
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["idempotency_key"], self.key)
        self.assertEqual(claimed["state"], "CLAIMED")
        self.assertEqual(claimed["attempts"], 2)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_06_poisoned_aggregate_does_not_stop_unrelated_clean_first_intent(self):
        self.mark(dispatch_started_at=NOW.isoformat())
        other = self.enqueue("a113-other", "a113-independent-aggregate")
        claimed = self.outbox.claim_next("a113-worker-two", now=self.expired)
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["idempotency_key"], other["idempotency_key"])
        self.assertEqual(self.outbox.get(self.key)["state"], "CLAIMED")
        self.assertEqual(self.outbox.get(self.key)["attempts"], 1)

    def test_07_expired_claim_with_sent_metadata_is_not_retried(self):
        self.mark(sent_at=NOW.isoformat(), effect_ref="FAKE_LOCAL_REF")
        self.assert_quarantined("CLAIMED")


if __name__ == "__main__":
    unittest.main()
