"""G19: real AION ExecutionOutbox / SQLiteChatStore, offline adversarial tests.

These tests DO NOT call dispatch_claimed or any provider adapter. They show
the limits of local-only journal custody; NOT a proof of P0 closure.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox


NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
SCOPE = Scope("g19-owner", "g19-tenant", "g19-workspace")


def enqueue(outbox, intent_ref="g19-semantic-1"):
    return outbox.enqueue(
        intent_ref=intent_ref,
        action="synthetic_no_send",
        payload={"synthetic": "only", "value": 42},
        aggregate_key="g19-aggregate",
        policy_version="g19-policy",
        authorization_ref="g19-local-placeholder",
        created_at=NOW,
        valid_until=NOW + timedelta(minutes=5),
    )


class G19RealOutboxOfflineIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-g19-real-offline-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "aion.sqlite3"

    def test_01_default_outbox_stages_without_adapter(self):
        store = SQLiteChatStore(self.path)
        try:
            outbox = ExecutionOutbox(store, SCOPE)
            row = enqueue(outbox)
            self.assertEqual(row["state"], "PENDING")
            self.assertFalse(row["executes_action"])
            self.assertEqual(outbox.list()[0]["idempotency_key"], row["idempotency_key"])
        finally:
            store.close()

    def test_02_same_intent_ref_idempotent_in_same_local_history(self):
        store = SQLiteChatStore(self.path)
        try:
            outbox = ExecutionOutbox(store, SCOPE)
            first = enqueue(outbox)
            second = enqueue(outbox)
            self.assertEqual(first["idempotency_key"], second["idempotency_key"])
            self.assertEqual(second["enqueue_state"], "IDEMPOTENT")
            self.assertEqual(len(outbox.list()), 1)
        finally:
            store.close()

    def test_03_local_rollback_recreates_deleted_decision_red(self):
        """RED: no independent witness, so restoring an old local DB forgets a decision."""
        store = SQLiteChatStore(self.path)
        store.close()
        old = Path(self.tmp.name) / "old.sqlite3"
        shutil.copyfile(self.path, old)
        store = SQLiteChatStore(self.path)
        try:
            first = enqueue(ExecutionOutbox(store, SCOPE))
            self.assertEqual(first["enqueue_state"], "ENQUEUED")
        finally:
            store.close()
        shutil.copyfile(old, self.path)
        restored = SQLiteChatStore(self.path)
        try:
            outbox = ExecutionOutbox(restored, SCOPE)
            self.assertEqual(outbox.list(), [])
            second = enqueue(outbox)
            self.assertEqual(second["enqueue_state"], "ENQUEUED")
            self.assertEqual(first["idempotency_key"], second["idempotency_key"])
            print("G19_REAL_OUTBOX_ROLLBACK_RED=OLD_DB_FORGETS_PRIOR_ENQUEUE")
        finally:
            restored.close()

    def test_04_same_semantic_payload_new_intent_ref_creates_distinct_key_red(self):
        """RED: intent_ref is caller supplied, not a trusted semantic identity."""
        store = SQLiteChatStore(self.path)
        try:
            outbox = ExecutionOutbox(store, SCOPE)
            first = enqueue(outbox, "g19-request-1")
            second = enqueue(outbox, "g19-request-2")
            self.assertNotEqual(first["idempotency_key"], second["idempotency_key"])
            self.assertEqual(len(outbox.list()), 2)
            print("G19_REAL_OUTBOX_SEMANTIC_ALIAS_RED=TWO_REQUEST_REFS_TWO_KEYS")
        finally:
            store.close()

    def test_05_default_guard_quarantined_no_provider(self):
        store = SQLiteChatStore(self.path)
        try:
            outbox = ExecutionOutbox(
                store, SCOPE,
                first_attempt_guard=lambda intent: True,
                evidence_verifier=lambda kind, intent, result: True,
            )
            self.assertFalse(outbox._reserved_first_attempt({"idempotency_key": "fake"}))
            self.assertFalse(outbox._verified_evidence("EFFECT_CONFIRMED", {}, {}))
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
