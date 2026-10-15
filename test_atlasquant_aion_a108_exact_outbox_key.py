"""A108 LAB: exact SHA256 idempotency keys at every Outbox entry point.

All cases are in-memory/synthetic SQLite only. No producer, Worker, transport,
external messages, credentials, costs, or activation.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 15, 17, 0, tzinfo=timezone.utc)

class NoAdapter:
    @property
    def send(self):
        raise AssertionError("adapter.send must not be inspected")
    @property
    def reconcile(self):
        raise AssertionError("adapter.reconcile must not be inspected")

class A108ExactOutboxKeyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteChatStore(Path(self.tmp.name) / "a108.sqlite3")
        self.addCleanup(self.store.close)
        self.scope = Scope("A108_OWNER", "A108_TENANT", "A108_WORKSPACE")
        self.outbox = ExecutionOutbox(self.store, self.scope)
        self.intent = self.outbox.enqueue(
            intent_ref="A108_INTENT", action="LOCAL_STAGE", payload={"note": "synthetic"},
            aggregate_key="A108_AGG", policy_version="A108_POLICY",
            authorization_ref="A108_APPROVAL",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        )
        self.key = self.intent["idempotency_key"]
        self.assertEqual(len(self.key), 64)

    def authorization(self, decision):
        return {
            "allowed": True,
            "actor_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "policy_version": decision["policy_version"],
            "authorization_ref": decision["authorization_ref"],
        }

    def claim(self):
        result = self.outbox.claim_next(
            "A108_WORKER", now=NOW + timedelta(seconds=1), lease_seconds=60
        )
        self.assertEqual(result["idempotency_key"], self.key)
        return result

    def synthetic_uncertain(self):
        with self.outbox.db:
            self.outbox.db.execute(
                """UPDATE action_outbox SET state='UNCERTAIN'
                   WHERE idempotency_key=?""", (self.key,)
            )
        self.assertEqual(self.outbox.get(self.key)["state"], "UNCERTAIN")

    def test_01_get_rejects_valid_key_with_appended_suffix(self):
        with self.assertRaisesRegex(ValueError, "invalid idempotency_key"):
            self.outbox.get(self.key + "X")
        self.assertEqual(self.outbox.get(self.key)["state"], "PENDING")

    def test_02_get_rejects_valid_key_with_trailing_space(self):
        with self.assertRaisesRegex(ValueError, "invalid idempotency_key"):
            self.outbox.get(self.key + " ")

    def test_03_get_rejects_valid_key_with_leading_space(self):
        with self.assertRaisesRegex(ValueError, "invalid idempotency_key"):
            self.outbox.get(" " + self.key)

    def test_04_dispatch_rejects_suffix_before_state_change(self):
        self.claim()
        with self.assertRaisesRegex(ValueError, "invalid idempotency_key"):
            self.outbox.dispatch_claimed(
                self.key + "X", worker_id="A108_WORKER",
                authorize=self.authorization, adapter=NoAdapter(),
                now=NOW + timedelta(seconds=2),
            )
        self.assertEqual(self.outbox.get(self.key)["state"], "CLAIMED")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_05_reconcile_rejects_suffix_before_adapter_lookup(self):
        self.synthetic_uncertain()
        with self.assertRaisesRegex(ValueError, "invalid idempotency_key"):
            self.outbox.reconcile(
                self.key + "X", adapter=NoAdapter(), authorize=self.authorization,
                now=NOW + timedelta(seconds=2),
            )
        self.assertEqual(self.outbox.get(self.key)["state"], "UNCERTAIN")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_06_get_rejects_non_hex_key_of_exact_length(self):
        with self.assertRaisesRegex(ValueError, "invalid idempotency_key"):
            self.outbox.get("g" + self.key[1:])

    def test_07_get_rejects_uppercase_key(self):
        with self.assertRaisesRegex(ValueError, "invalid idempotency_key"):
            self.outbox.get(self.key.upper())

    def test_08_exact_key_get_remains_available(self):
        row = self.outbox.get(self.key)
        self.assertEqual(row["idempotency_key"], self.key)
        self.assertEqual(row["state"], "PENDING")

    def test_09_exact_key_dispatch_remains_hard_denied(self):
        self.claim()
        with self.assertRaisesRegex(
            PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED"
        ):
            self.outbox.dispatch_claimed(
                self.key, worker_id="A108_WORKER",
                authorize=self.authorization, adapter=NoAdapter(),
                now=NOW + timedelta(seconds=2),
            )
        self.assertEqual(self.outbox.get(self.key)["state"], "BLOCKED_PRODUCER")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_10_exact_key_reconcile_remains_hard_denied(self):
        self.synthetic_uncertain()
        with self.assertRaisesRegex(
            PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED"
        ):
            self.outbox.reconcile(
                self.key, adapter=NoAdapter(),
                authorize=self.authorization, now=NOW + timedelta(seconds=2),
            )
        self.assertEqual(self.outbox.get(self.key)["state"], "UNCERTAIN")
        self.assertEqual(self.outbox.effect_count(), 0)

if __name__ == "__main__":
    unittest.main()
