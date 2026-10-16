"""A110: direct private block must never falsely terminate ambiguous effects.

In-memory/synthetic SQLite fixtures only. These are RED tests on A109 HEAD.
No provider, adapter, Worker, network, real send, or authority enrollment.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 16, 11, 15, tzinfo=timezone.utc)


class A110AmbiguousOutboxBlockDenialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteChatStore(Path(self.tmp.name) / "outbox-a110.sqlite3")
        self.addCleanup(self.store.close)
        self.scope = Scope("a110-owner", "a110-tenant", "a110-workspace")
        self.outbox = ExecutionOutbox(self.store, self.scope)
        row = self.outbox.enqueue(
            intent_ref="a110-intent-1",
            action="synthetic_stage_only",
            payload={"note": "test-only"},
            aggregate_key="a110-aggregate",
            policy_version="a110-policy",
            authorization_ref="a110-local-authorization",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )
        self.key = row["idempotency_key"]
        claimed = self.outbox.claim_next(
            "a110-worker", now=NOW + timedelta(seconds=1), lease_seconds=60
        )
        self.assertEqual(claimed["state"], "CLAIMED")

    def _synthetic_state(self, state):
        # TEST-ONLY direct SQLite setup, NOT a real dispatch or effect.
        with self.outbox.db:
            self.outbox.db.execute(
                "UPDATE action_outbox SET state=? WHERE idempotency_key=?",
                (state, self.key),
            )
        before = self.outbox.get(self.key)
        self.assertEqual(before["state"], state)
        return before

    def test_01_uncertain_cannot_be_revoked_by_private_local_state_transition(self):
        before = self._synthetic_state("UNCERTAIN")
        with self.assertRaisesRegex(
            PermissionError, "UNCERTAIN_EFFECT_STATE_CANNOT_BE_REVOKED"
        ):
            self.outbox._set_blocked(
                self.key, "REVOKED", "synthetic-local-revocation", expected=before
            )
        after = self.outbox.get(self.key)
        self.assertEqual(after, before)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_02_sent_cannot_be_reapproval_blocked_as_if_no_effect_occurred(self):
        before = self._synthetic_state("SENT")
        with self.assertRaisesRegex(
            PermissionError, "UNCERTAIN_EFFECT_STATE_CANNOT_BE_REVOKED"
        ):
            self.outbox._set_blocked(
                self.key, "BLOCKED_REAPPROVAL",
                "synthetic-local-reapproval", expected=before
            )
        after = self.outbox.get(self.key)
        self.assertEqual(after, before)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_03_claimed_with_effect_ledger_row_cannot_be_downgraded(self):
        # Locally forged row simulates evidence/state disagreement.
        before = self.outbox.get(self.key)
        with self.outbox.db:
            self.outbox.db.execute(
                """INSERT INTO action_effects(
                    idempotency_key,owner,tenant,workspace,effect_ref,confirmed_at,data
                   ) VALUES (?,?,?,?,?,?,?)""",
                (
                    self.key, self.scope.owner_id, self.scope.tenant_id,
                    self.scope.workspace_id, "A110_FAKE_LOCAL_EFFECT",
                    NOW.isoformat(), '{"synthetic":true}',
                ),
            )
        with self.assertRaisesRegex(
            RuntimeError, "stale outbox state/lease; blocked mutation rejected"
        ):
            self.outbox._set_blocked(
                self.key, "REVOKED", "synthetic-conflicting-effect-ledger",
                expected=before,
            )
        self.assertEqual(self.outbox.get(self.key), before)
        self.assertEqual(self.outbox.effect_count(), 1)

    def test_04_pre_dispatch_claimed_revocation_still_works_without_external_effect(self):
        before = self.outbox.get(self.key)
        result = self.outbox._set_blocked(
            self.key, "REVOKED", "synthetic-revocation-before-dispatch",
            expected=before,
        )
        self.assertEqual(result["state"], "REVOKED")
        self.assertEqual(result["last_error"], "synthetic-revocation-before-dispatch")
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertEqual(self.outbox.get(self.key)["attempts"], 1)


if __name__ == "__main__":
    unittest.main()
