"""AION P0 defence in depth: expired authorization must not be locally claimed.

RED on the inherited ExecutionOutbox.claim_next (expiry checked only later in
dispatch_claimed). These are authentic Outbox + SQLiteChatStore tests, but
the SQLite DB, policy claims and all action identifiers are disposable fixtures.
PASS is ONLY local expiry-fence evidence, never a witness against rollback,
a trusted clock, a signed owner approval or authorization to send.
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
SCOPE = Scope("claim-expiry-lab-owner", "claim-expiry-lab-tenant", "claim-expiry-lab-space")


class P0OutboxExpiredAuthorityClaimLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-p0-expired-claim-lab-")
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteChatStore(Path(self.tmp.name) / "claims.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(self.store, SCOPE)

    def enqueue(self, ref="expired-one", *, ttl_seconds=60, aggregate=None):
        return self.outbox.enqueue(
            intent_ref=ref, action="synthetic-no-provider",
            payload={"synthetic": True}, aggregate_key=aggregate or ref,
            policy_version="lab", authorization_ref="local-test-only",
            created_at=T0, valid_until=T0 + timedelta(seconds=ttl_seconds),
        )

    def assert_untouched(self, key, state):
        row = self.outbox.get(key)
        self.assertEqual(row["state"], state)
        self.assertEqual(row["attempts"], 0)
        self.assertEqual(row["lease_owner"], "")
        self.assertEqual(row["lease_until"], "")
        self.assertEqual(row["dispatch_started_at"], "")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_01_expired_pending_cannot_claim(self):
        key = self.enqueue()["idempotency_key"]
        self.assertIsNone(self.outbox.claim_next("local-lab", now=T0 + timedelta(seconds=61)))
        self.assert_untouched(key, "PENDING")

    def test_02_exact_expiration_boundary_cannot_claim(self):
        key = self.enqueue()["idempotency_key"]
        self.assertIsNone(self.outbox.claim_next("local-lab", now=T0 + timedelta(seconds=60)))
        self.assert_untouched(key, "PENDING")

    def test_03_expired_retry_cannot_reclaim(self):
        key = self.enqueue()["idempotency_key"]
        with self.outbox.db:
            self.outbox.db.execute("UPDATE action_outbox SET state='RETRY' WHERE idempotency_key=?", (key,))
        self.assertIsNone(self.outbox.claim_next("local-lab", now=T0 + timedelta(minutes=2)))
        self.assert_untouched(key, "RETRY")

    def test_04_unexpired_other_aggregate_can_still_claim(self):
        expired = self.enqueue(ref="old", ttl_seconds=10)
        active = self.enqueue(ref="active", ttl_seconds=180)
        claimed = self.outbox.claim_next("local-lab", now=T0 + timedelta(seconds=30))
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["idempotency_key"], active["idempotency_key"])
        self.assertEqual(claimed["state"], "CLAIMED")
        self.assert_untouched(expired["idempotency_key"], "PENDING")

    def test_05_live_claim_stays_possible_for_local_staging_only(self):
        row = self.enqueue(ttl_seconds=60)
        claimed = self.outbox.claim_next("local-lab", now=T0 + timedelta(seconds=59))
        self.assertEqual(claimed["idempotency_key"], row["idempotency_key"])
        self.assertEqual(claimed["attempts"], 1)
        self.assertEqual(claimed["state"], "CLAIMED")
        self.assertEqual(self.outbox.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
