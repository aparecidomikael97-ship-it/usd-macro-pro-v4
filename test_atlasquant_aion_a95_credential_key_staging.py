"""A95 LAB — reject recognizable credential headers/keys before local SQL staging.

Synthetic strings only. No actual key, provider request, Worker, or external effect.
The historical test suites remain unchanged.
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


NOW = datetime(2026, 10, 15, 13, tzinfo=timezone.utc)
DENIED = "REDACTED_PAYLOAD_NOT_STAGEABLE"


class A95CredentialKeyStagingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = SQLiteChatStore(Path(temp.name) / "a95.sqlite3")
        self.addCleanup(self.store.close)
        self.scope = Scope("A95_OWNER", "A95_TENANT", "A95_WORKSPACE")
        self.outbox = ExecutionOutbox(self.store, self.scope)
        budget = CumulativeAuthorityBudget(
            self.store, self.scope,
            authority_budget_ref="A95_BUDGET",
            policy_version="A95_POLICY",
        )
        self.saga = ExecutionSagaCoordinator(
            self.store, self.scope, outbox=self.outbox, authority_budget=budget,
        )

    def send_intent(self, payload, *, intent_ref="A95_INTENT"):
        return self.outbox.enqueue(
            intent_ref=intent_ref, action="send_email",
            payload=payload, aggregate_key="A95_AGG",
            policy_version="A95_POLICY", authorization_ref="A95_APPROVAL",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        )

    def create_saga(self, payload, compensation=None):
        return self.saga.create(
            saga_id="A95_SAGA",
            steps=[dict(
                step_key="A95_STEP", action="A95_LOCAL_ONLY",
                payload=payload, capability_class="LOW_RISK",
                risk_points=1, reversible=True,
                compensation_action="A95_LOCAL_UNDO",
                compensation_payload=compensation if compensation is not None else {},
                compensation_risk_points=1,
            )], created_at=NOW,
        )

    def assert_no_rows(self):
        for table in ("action_outbox", "action_decisions",
                      "aion_execution_sagas", "aion_execution_saga_steps"):
            with self.subTest(table=table):
                value = self.store.db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
                self.assertEqual(value, 0, table)

    def test_01_outbox_header_authorization_basic_denied(self):
        for index, payload in enumerate((
            {"authorization": "Basic A95_FAKE_ONLY"},
            {"Authorization": "Basic A95_FAKE_ONLY"},
            {"headers": {"ACCESS_TOKEN": "A95_FAKE_ONLY"}},
            {"headers": {"X-Api-Key": "A95_FAKE_ONLY"}},
        )):
            with self.subTest(case=str(list(payload.keys()))):
                with self.assertRaisesRegex(ValueError, DENIED):
                    self.send_intent(payload, intent_ref=f"A95_HEADER_{index}")
                self.assert_no_rows()

    def test_02_outbox_nested_aliases_and_camel_case_denied(self):
        for index, name in enumerate(("refreshToken", "client-secret", "private_key",
                     "session_token", "Set-Cookie", "x_api_key")):
            with self.subTest(key=name):
                with self.assertRaisesRegex(ValueError, DENIED):
                    self.send_intent({"meta": [{"headers": {name: "A95_FAKE_ONLY"}}]}, intent_ref=f"A95_ALIAS_{index}")
                self.assert_no_rows()

    def test_03_saga_forward_credential_denied_without_sql_rows(self):
        with self.assertRaisesRegex(ValueError, DENIED):
            self.create_saga({"headers": {"Authorization": "Basic A95_FAKE_ONLY"}})
        self.assert_no_rows()

    def test_04_saga_compensation_credential_denied_without_sql_rows(self):
        with self.assertRaisesRegex(ValueError, DENIED):
            self.create_saga({"operation": "note"}, {"auth": {"clientSecret": "A95_FAKE_ONLY"}})
        self.assert_no_rows()

    def test_05_legitimate_fields_are_not_swept_by_partial_key_match(self):
        benign = {"authorization_ref": "A95_APPROVAL", "token_count": 2,
                  "auth_mode": "manual", "headers": {"Content-Type": "application/json"}}
        self.assertEqual(clean_action_payload(benign), benign)
        result = self.send_intent(benign)
        self.assertEqual(result["enqueue_state"], "ENQUEUED")
        saga = self.create_saga(benign, {"audit_event": "review"})
        self.assertEqual(saga["create_state"], "CREATED")

    def test_06_existing_redaction_stays_denied(self):
        with self.assertRaisesRegex(ValueError, DENIED):
            self.send_intent({"api_key": "A95_FAKE_ONLY"})
        self.assert_no_rows()


if __name__ == "__main__":
    unittest.main()
