"""A107 LAB: exact-bound authority claims must not alias by truncation.

All inputs are synthetic. The public Outbox dispatch boundary remains
INDEPENDENT_PRODUCER_NOT_ENROLLED; no adapter or Worker is used.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 15, 16, 0, tzinfo=timezone.utc)


class A107BoundedAuthorizationClaimsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = SQLiteChatStore(Path(self.folder.name) / "a107.sqlite3")
        self.addCleanup(self.store.close)
        self.scope = Scope("A107_OWNER", "A107_TENANT", "A107_WORKSPACE")
        self.outbox = ExecutionOutbox(self.store, self.scope)

    def enqueue(self, **overrides):
        args = dict(
            intent_ref="A107_INTENT", action="LOCAL_STAGE",
            payload={"note": "synthetic"}, aggregate_key="A107_AGG",
            policy_version="A107_POLICY", authorization_ref="A107_AUTH",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        )
        args.update(overrides)
        return self.outbox.enqueue(**args)

    def evaluate(self, item, **overrides):
        decision = item["decision"]
        claim = dict(
            allowed=True, actor_id=self.scope.owner_id,
            tenant_id=self.scope.tenant_id, workspace_id=self.scope.workspace_id,
            policy_version=decision["policy_version"],
            authorization_ref=decision["authorization_ref"],
            reauthenticated=True, reauth_ref=decision["reauth_ref"],
        )
        claim.update(overrides)
        return self.outbox._authorization_gate(
            item, lambda _decision: claim, NOW + timedelta(seconds=1)
        )

    def assert_no_sql(self):
        for table in ("action_decisions", "action_outbox", "action_effects"):
            got = self.store.db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
            self.assertEqual(got, 0, table)

    def test_01_overlong_callback_approval_does_not_equal_staged_approval(self):
        old = "A" * 128
        item = self.enqueue(authorization_ref=old)
        allow, blocked, result = self.evaluate(item, authorization_ref=old + "X")
        self.assertFalse(allow)
        self.assertEqual(blocked, "BLOCKED_REAPPROVAL")
        self.assertEqual(result["reason"], "AUTHORIZATION_CHANGED")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_02_overlong_callback_policy_does_not_equal_staged_policy(self):
        old = "P" * 128
        item = self.enqueue(policy_version=old)
        allow, blocked, result = self.evaluate(item, policy_version=old + "X")
        self.assertFalse(allow)
        self.assertEqual(blocked, "BLOCKED_REAPPROVAL")
        self.assertEqual(result["reason"], "POLICY_VERSION_CHANGED")

    def test_03_overlong_callback_reauth_does_not_equal_staged_reauth(self):
        old = "R" * 160
        item = self.enqueue(requires_reauth=True, reauth_ref=old)
        allow, blocked, result = self.evaluate(item, reauth_ref=old + "X")
        self.assertFalse(allow)
        self.assertEqual(blocked, "BLOCKED_REAPPROVAL")
        self.assertEqual(result["reason"], "REAUTH_TRANSACTION_MISMATCH")

    def test_04_staging_reauth_ref_over_160_rejected_without_sql(self):
        with self.assertRaisesRegex(ValueError, "reauth_ref"):
            self.enqueue(requires_reauth=True, reauth_ref="R" * 160 + "X")
        self.assert_no_sql()

    def test_05_staging_transaction_ref_over_128_rejected_without_sql(self):
        with self.assertRaisesRegex(ValueError, "transaction_id"):
            self.enqueue(transaction_id="T" * 128 + "X",
                         authority_budget_ref="BUDGET", risk_points=1,
                         capability_class="LOW_RISK")
        self.assert_no_sql()

    def test_06_staging_budget_ref_over_128_rejected_without_sql(self):
        with self.assertRaisesRegex(ValueError, "authority_budget_ref"):
            self.enqueue(transaction_id="TXN",
                         authority_budget_ref="B" * 128 + "X",
                         risk_points=1, capability_class="LOW_RISK")
        self.assert_no_sql()

    def test_07_staging_capability_over_80_rejected_without_sql(self):
        with self.assertRaisesRegex(ValueError, "capability_class"):
            self.enqueue(transaction_id="TXN",
                         authority_budget_ref="BUDGET",
                         risk_points=1, capability_class="C" * 80 + "X")
        self.assert_no_sql()

    def test_08_normal_max_length_values_preserve_identity_and_gate(self):
        item = self.enqueue(
            policy_version="P" * 128, authorization_ref="A" * 128,
            requires_reauth=True, reauth_ref="R" * 160,
            transaction_id="T" * 128, authority_budget_ref="B" * 128,
            risk_points=1, capability_class="C" * 80,
        )
        allowed, decision, _ = self.evaluate(item)
        self.assertTrue(allowed)
        self.assertEqual(decision, "ALLOW")
        self.assertEqual(item["decision"]["transaction_id"], "T" * 128)
        self.assertEqual(item["decision"]["authority_budget_ref"], "B" * 128)
        self.assertEqual(item["decision"]["capability_class"], "C" * 80)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_09_normal_short_values_preserve_idempotency(self):
        first = self.enqueue()
        second = self.enqueue()
        self.assertEqual(first["enqueue_state"], "ENQUEUED")
        self.assertEqual(second["enqueue_state"], "IDEMPOTENT")
        self.assertEqual(first["idempotency_key"], second["idempotency_key"])
        allowed, decision, _ = self.evaluate(first)
        self.assertTrue(allowed)
        self.assertEqual(decision, "ALLOW")
        self.assertEqual(self.outbox.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
