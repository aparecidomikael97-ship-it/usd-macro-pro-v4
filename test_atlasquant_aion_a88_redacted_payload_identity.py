"""A88 LAB: redacted payloads must never silently define an action identity.

All checkpoints are synthetic local SQLite data; no Worker, provider, network,
secret account, or production action is enabled. The intended conservative
contract rejects values that privacy.redact would modify *before* staging.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.privacy import redact
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox


WHEN = datetime(2026, 10, 15, 4, 0, tzinfo=timezone.utc)
DENIAL = "REDACTED_PAYLOAD_NOT_STAGEABLE"


class A88RedactedPayloadIdentityTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = SQLiteChatStore(Path(self.folder.name) / "chat.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(
            self.store, Scope("owner-a88", "tenant-a88", "workspace-a88")
        )

    def enqueue(self, payload, *, ref="intent-1"):
        return self.outbox.enqueue(
            intent_ref=ref,
            action="send_email",
            payload=payload,
            aggregate_key="recipient-a88",
            policy_version="policy-v1",
            authorization_ref="human-approval-pending",
            created_at=WHEN,
            valid_until=WHEN + timedelta(minutes=5),
        )

    def assert_empty(self):
        self.assertEqual(self.outbox.list(), [])
        self.assertEqual(
            self.store.db.execute("SELECT count(*) FROM action_decisions").fetchone()[0], 0
        )
        self.assertEqual(
            self.store.db.execute("SELECT count(*) FROM action_outbox").fetchone()[0], 0
        )

    def test_01_two_distinct_api_keys_must_never_become_same_staged_intent(self):
        one = {"to": "sample@example.invalid", "api_key": "A88-demo-secret-one"}
        two = {"to": "sample@example.invalid", "api_key": "A88-demo-secret-two"}
        self.assertEqual(redact(one), redact(two))
        a, b = deepcopy(one), deepcopy(two)
        with self.assertRaisesRegex(ValueError, DENIAL):
            self.enqueue(one)
        with self.assertRaisesRegex(ValueError, DENIAL):
            self.enqueue(two)
        self.assertEqual((one, two), (a, b))
        self.assert_empty()

    def test_02_nested_secret_in_list_cannot_silently_change_digest(self):
        payload = {"to": "sample@example.invalid",
                   "data": [{"credential": "A88-demo-credential"}]}
        original = deepcopy(payload)
        self.assertNotEqual(redact(payload), payload)
        with self.assertRaisesRegex(ValueError, DENIAL):
            self.enqueue(payload)
        self.assertEqual(payload, original)
        self.assert_empty()

    def test_03_inline_secret_in_message_cannot_be_redacted_into_same_action(self):
        payload = {"message": "authorization=Bearer-A88-demonstration-only"}
        self.assertNotEqual(redact(payload), payload)
        with self.assertRaisesRegex(ValueError, DENIAL):
            self.enqueue(payload)
        self.assert_empty()

    def test_04_plain_payload_remains_transactionally_idempotent(self):
        payload = {"to": "sample@example.invalid", "template": "reminder"}
        a = self.enqueue(payload)
        b = self.enqueue(deepcopy(payload))
        self.assertEqual(a["enqueue_state"], "ENQUEUED")
        self.assertEqual(b["enqueue_state"], "IDEMPOTENT")
        self.assertEqual(a["idempotency_key"], b["idempotency_key"])
        self.assertEqual(len(self.outbox.list()), 1)

    def test_05_preexisting_plain_intent_preserved_on_redacted_attempt(self):
        base = {"to": "sample@example.invalid", "template": "reminder"}
        first = self.enqueue(base)
        with self.assertRaisesRegex(ValueError, DENIAL):
            self.enqueue({**base, "token": "A88-placeholder-not-real"})
        self.assertEqual(len(self.outbox.list()), 1)
        self.assertEqual(self.outbox.list()[0]["idempotency_key"], first["idempotency_key"])


if __name__ == "__main__":
    unittest.main()
