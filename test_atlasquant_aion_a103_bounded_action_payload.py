"""A103 LAB: bounded, UTF-8-safe JSON staging before digest and SQLite mutation.

Synthetic inputs only. No live Worker, account, provider, secrets or outbound effects.
A regression test must fail against A100/A96 code before the bounded gate is added.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_action_payload_gate import clean_action_payload
from atlasquant_aion_cumulative_authority_budget import CumulativeAuthorityBudget
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_execution_saga import ExecutionSagaCoordinator


NOW = datetime(2026, 10, 15, 16, tzinfo=timezone.utc)
INVALID = "ACTION_PAYLOAD_NOT_CANONICAL_JSON"


class A103BoundedActionPayloadTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = SQLiteChatStore(Path(tmp.name) / "a103.sqlite3")
        self.addCleanup(self.store.close)
        scope = Scope("A103_OWNER", "A103_TENANT", "A103_WORKSPACE")
        self.outbox = ExecutionOutbox(self.store, scope)
        budget = CumulativeAuthorityBudget(
            self.store, scope,
            authority_budget_ref="A103_BUDGET", policy_version="A103_POLICY",
        )
        self.saga = ExecutionSagaCoordinator(
            self.store, scope, outbox=self.outbox, authority_budget=budget,
        )

    def enqueue(self, payload, intent_ref="A103_INTENT"):
        return self.outbox.enqueue(
            intent_ref=intent_ref, action="send_email",
            payload=payload, aggregate_key="A103_AGG",
            policy_version="A103_POLICY", authorization_ref="A103_APPROVAL",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        )

    def create_saga(self, forward, undo=None):
        return self.saga.create(
            saga_id="A103_SAGA",
            steps=[dict(
                step_key="A103_STEP", action="LOCAL_ONLY", payload=forward,
                capability_class="LOW_RISK", risk_points=1, reversible=True,
                compensation_action="LOCAL_UNDO",
                compensation_payload={} if undo is None else undo,
                compensation_risk_points=1,
            )], created_at=NOW,
        )

    def assert_no_staging(self):
        for table in ("action_outbox", "action_decisions",
                      "aion_execution_sagas", "aion_execution_saga_steps"):
            self.assertEqual(
                self.store.db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0],
                0, table,
            )

    def test_01_outbox_rejects_oversized_single_string_before_sql(self):
        with self.assertRaisesRegex(ValueError, INVALID):
            self.enqueue({"message": "A" * 100_000})
        self.assert_no_staging()

    def test_02_outbox_rejects_oversized_list_node_count_before_sql(self):
        with self.assertRaisesRegex(ValueError, INVALID):
            self.enqueue({"items": list(range(5_000))})
        self.assert_no_staging()

    def test_03_saga_forward_rejects_oversized_object_before_sql(self):
        with self.assertRaisesRegex(ValueError, INVALID):
            self.create_saga({"items": {"field_%04d" % i: i for i in range(5_000)}})
        self.assert_no_staging()

    def test_04_saga_compensation_rejects_oversized_payload_before_sql(self):
        with self.assertRaisesRegex(ValueError, INVALID):
            self.create_saga({"operation": "manual"}, {"items": list(range(5_000))})
        self.assert_no_staging()

    def test_05_outbox_rejects_cumulative_bytes_before_sql(self):
        with self.assertRaisesRegex(ValueError, INVALID):
            self.enqueue({"parts": ["B" * 60_000 for _ in range(5)]})
        self.assert_no_staging()

    def test_06_outbox_rejects_invalid_utf8_surrogate_before_digest(self):
        with self.assertRaisesRegex(ValueError, INVALID):
            self.enqueue({"note": "\ud800"})
        self.assert_no_staging()

    def test_07_normal_bounded_json_preserves_idempotency_and_saga(self):
        valid = {"message": "C" * 2000, "items": [{"n": i} for i in range(15)],
                 "approved_ref": "A103_SYNTHETIC_POINTER"}
        self.assertEqual(clean_action_payload(valid), valid)
        one = self.enqueue(valid)
        two = self.enqueue(valid)
        self.assertEqual(one["enqueue_state"], "ENQUEUED")
        self.assertEqual(two["enqueue_state"], "IDEMPOTENT")
        self.assertEqual(one["idempotency_key"], two["idempotency_key"])
        self.assertEqual(
            self.create_saga(valid, {"undo": "manual"})["create_state"], "CREATED",
        )


if __name__ == "__main__":
    unittest.main()
