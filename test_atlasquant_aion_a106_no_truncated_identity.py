"""A106 LAB: reject overlong opaque identifiers instead of aliasing by truncation.

Synthetic IDs only. No Worker activation, adapter, provider or outbound effect.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_cumulative_authority_budget import CumulativeAuthorityBudget
from atlasquant_aion_execution_outbox import ExecutionOutbox, _token as outbox_token
from atlasquant_aion_execution_saga import ExecutionSagaCoordinator, _token as saga_token

NOW = datetime(2026, 10, 15, 16, 0, tzinfo=timezone.utc)

class A106NoTruncatedIdentityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = SQLiteChatStore(Path(temp.name) / "a106.sqlite3")
        self.addCleanup(self.store.close)
        scope = Scope("A106_OWNER", "A106_TENANT", "A106_WORKSPACE")
        self.outbox = ExecutionOutbox(self.store, scope)
        budget = CumulativeAuthorityBudget(
            self.store, scope,
            authority_budget_ref="A106_BUDGET", policy_version="A106_POLICY",
        )
        self.saga = ExecutionSagaCoordinator(
            self.store, scope, outbox=self.outbox, authority_budget=budget,
        )

    def enqueue(self, **updates):
        args = {
            "intent_ref": "A106_INTENT", "action": "LOCAL_STAGE",
            "payload": {"note": "synthetic"}, "aggregate_key": "A106_AGG",
            "policy_version": "A106_POLICY", "authorization_ref": "A106_APPROVAL",
            "created_at": NOW, "valid_until": NOW + timedelta(minutes=5),
        }
        args.update(updates)
        return self.outbox.enqueue(**args)

    def create_saga(self, **updates):
        step = {
            "step_key": "A106_STEP", "action": "LOCAL_STAGE",
            "payload": {"note": "synthetic"}, "capability_class": "LOW_RISK",
            "risk_points": 1, "reversible": False,
        }
        args = {"saga_id": "A106_SAGA", "steps": [step], "created_at": NOW}
        args.update(updates)
        return self.saga.create(**args)

    def assert_no_sql_rows(self):
        for table in (
            "action_decisions", "action_outbox",
            "aion_execution_sagas", "aion_execution_saga_steps",
        ):
            count = self.store.db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
            self.assertEqual(count, 0, table)

    def test_01_outbox_token_rejects_129_chars(self):
        with self.assertRaisesRegex(ValueError, "invalid intent_ref"):
            outbox_token("I" * 128 + "A", "intent_ref")

    def test_02_outbox_token_respects_custom_limit(self):
        with self.assertRaisesRegex(ValueError, "invalid effect_ref"):
            outbox_token("E" * 17, "effect_ref", 16)

    def test_03_saga_token_rejects_129_chars(self):
        with self.assertRaisesRegex(ValueError, "invalid saga_id"):
            saga_token("S" * 128 + "A", "saga_id")

    def test_04_distinct_long_intents_cannot_collapse(self):
        for suffix in ("A", "B"):
            with self.assertRaisesRegex(ValueError, "invalid intent_ref"):
                self.enqueue(intent_ref="I" * 128 + suffix)
        self.assert_no_sql_rows()

    def test_05_overlong_approval_rejected_before_sql(self):
        with self.assertRaisesRegex(ValueError, "invalid authorization_ref"):
            self.enqueue(authorization_ref="R" * 128 + "DIFFERENT")
        self.assert_no_sql_rows()

    def test_06_overlong_saga_rejected_before_sql(self):
        with self.assertRaisesRegex(ValueError, "invalid saga_id"):
            self.create_saga(saga_id="S" * 128 + "DIFFERENT")
        self.assert_no_sql_rows()

    def test_07_overlong_step_rejected_before_sql(self):
        step = {
            "step_key": "T" * 129, "action": "LOCAL_STAGE", "payload": {},
            "capability_class": "LOW_RISK", "risk_points": 1,
            "reversible": False,
        }
        with self.assertRaisesRegex(ValueError, "invalid step_key"):
            self.create_saga(steps=[step])
        self.assert_no_sql_rows()

    def test_08_exact_128_char_ids_idempotent(self):
        exact = "V" * 128
        self.assertEqual(outbox_token(exact, "intent_ref"), exact)
        self.assertEqual(saga_token(exact, "saga_id"), exact)
        first = self.enqueue(intent_ref=exact)
        second = self.enqueue(intent_ref=exact)
        self.assertEqual(first["enqueue_state"], "ENQUEUED")
        self.assertEqual(second["enqueue_state"], "IDEMPOTENT")
        self.assertEqual(first["idempotency_key"], second["idempotency_key"])
        self.assertEqual(self.create_saga(saga_id=exact)["create_state"], "CREATED")

    def test_09_trailing_spaces_preserve_128_char_id(self):
        value = "V" * 128 + "   "
        self.assertEqual(outbox_token(value, "intent_ref"), "V" * 128)
        self.assertEqual(saga_token(value, "saga_id"), "V" * 128)

if __name__ == "__main__":
    unittest.main()
