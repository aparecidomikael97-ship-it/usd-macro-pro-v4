"""A89: synthetic-only checks of action payload serialization and identity.

Tests are restricted to local SQLite LAB fixtures. They must never call
Worker, real provider, signer, external API or credential storage.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_cumulative_authority_budget import CumulativeAuthorityBudget
from atlasquant_aion_execution_saga import ExecutionSagaCoordinator


NOW = datetime(2026, 10, 15, 10, 0, tzinfo=timezone.utc)
INVALID = "ACTION_PAYLOAD_NOT_CANONICAL_JSON"
REDACTED = "REDACTED_PAYLOAD_NOT_STAGEABLE"


class A89PayloadCanonicalGateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = SQLiteChatStore(Path(temp.name) / "a89.sqlite3")
        self.addCleanup(self.store.close)
        self.scope = Scope("A89_OWNER", "A89_TENANT", "A89_WORKSPACE")
        self.outbox = ExecutionOutbox(self.store, self.scope)
        budget = CumulativeAuthorityBudget(
            self.store, self.scope,
            authority_budget_ref="A89_BUDGET",
            policy_version="A89_POLICY",
        )
        self.saga = ExecutionSagaCoordinator(
            self.store, self.scope, outbox=self.outbox, authority_budget=budget,
        )

    def send_intent(self, payload):
        return self.outbox.enqueue(
            intent_ref="A89_INTENT", action="send_email",
            payload=payload, aggregate_key="A89_AGG",
            policy_version="A89_POLICY", authorization_ref="A89_LOCAL_APPROVAL",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        )

    def step(self, payload, compensation=None):
        return dict(
            step_key="A89_STEP", action="A89_LOCAL_ONLY",
            payload=payload, capability_class="LOW_RISK",
            risk_points=1, reversible=True,
            compensation_action="A89_LOCAL_UNDO",
            compensation_payload=compensation if compensation is not None else {},
            compensation_risk_points=1,
        )

    def create_saga(self, payload, compensation=None):
        return self.saga.create(
            saga_id="A89_SAGA",
            steps=[self.step(payload, compensation)],
            created_at=NOW,
        )

    def no_rows(self):
        for table in ("action_outbox", "action_decisions",
                      "aion_execution_sagas", "aion_execution_saga_steps"):
            n = self.store.db.execute("SELECT count(*) FROM " + table).fetchone()[0]
            self.assertEqual(n, 0, table)

    def test_01_outbox_nested_tuple_cannot_store_unredacted_secret(self):
        # Privacy.redact does not traverse tuples and json.dumps(default=str)
        # used to serialize the tuple representation to a persisted SQL string.
        with self.assertRaisesRegex(ValueError, INVALID):
            self.send_intent({"metadata": ({"api_key": "A89-FAKE-NOT-A-SECRET"},)})
        self.no_rows()

    def test_02_outbox_object_stringification_cannot_collide_with_real_string(self):
        # Decimal("2.50") was stringified to "2.50", same as a real JSON str.
        with self.assertRaisesRegex(ValueError, INVALID):
            self.send_intent({"amount": Decimal("2.50")})
        self.no_rows()
        valid = self.send_intent({"amount": "2.50"})
        self.assertEqual(valid["enqueue_state"], "ENQUEUED")

    def test_03_outbox_nonfinite_and_nonstring_keys_are_blocked(self):
        for payload in ({"score": float("nan")},
                        {"score": [float("inf")]},
                        {1: "numeric-key"}):
            with self.subTest(payload_type=type(next(iter(payload.values()))).__name__):
                with self.assertRaisesRegex(ValueError, INVALID):
                    self.send_intent(payload)
                self.no_rows()

    def test_04_saga_redacted_forward_payload_cannot_collide(self):
        with self.assertRaisesRegex(ValueError, REDACTED):
            self.create_saga({"api_key": "A89-FAKE-FORWARD"})
        self.no_rows()

    def test_05_saga_redacted_compensation_payload_cannot_collide(self):
        with self.assertRaisesRegex(ValueError, REDACTED):
            self.create_saga(
                {"topic": "notice"},
                {"auth": {"token": "A89-FAKE-UNDO"}},
            )
        self.no_rows()

    def test_06_saga_tuple_hidden_secret_cannot_be_persisted(self):
        with self.assertRaisesRegex(ValueError, INVALID):
            self.create_saga(
                {"metadata": ({"credential": "A89-FAKE-NOT-A-SECRET"},)}
            )
        self.no_rows()

    def test_07_saga_nonfinite_and_decimal_compensation_are_blocked(self):
        for forward, undo in (({"qty": float("-inf")}, {}),
                              ({"qty": 1}, {"cost": Decimal("3")})):
            with self.assertRaisesRegex(ValueError, INVALID):
                self.create_saga(forward, undo)
            self.no_rows()

    def test_08_normal_json_actions_keep_idempotency_and_plan_integrity(self):
        intent = {"to": "sample@example.invalid",
                  "features": [True, None, 3, {"ratio": 1.25}]}
        first = self.send_intent(intent)
        same = self.send_intent(intent)
        self.assertEqual(first["idempotency_key"], same["idempotency_key"])
        self.assertEqual(same["enqueue_state"], "IDEMPOTENT")
        saga = self.create_saga(
            {"value": {"array": [1, 2.5, False, None]}},
            {"retry": False},
        )
        self.assertEqual(saga["create_state"], "CREATED")
        self.assertEqual(self.saga.integrity_report("A89_SAGA")["state"], "MATCH")

    def test_09_cyclic_and_non_json_types_must_fail_before_write(self):
        cyc = []
        cyc.append(cyc)
        for payload in ({"items": cyc}, {"items": b"binary"}, {"set": {1, 2}}):
            with self.assertRaisesRegex(ValueError, INVALID):
                self.send_intent(payload)
            self.no_rows()


if __name__ == "__main__":
    unittest.main()
