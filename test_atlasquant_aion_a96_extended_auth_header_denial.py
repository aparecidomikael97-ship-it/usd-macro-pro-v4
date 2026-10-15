"""A96 LAB: standard credential HTTP header aliases must fail before SQLite writes.

Inert synthetic strings only, no Worker, provider, account, key, or external SEND.
This is regression coverage for the A95 bounded alias gate, not universal DLP.
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


NOW = datetime(2026, 10, 15, 14, tzinfo=timezone.utc)
DENIED = "REDACTED_PAYLOAD_NOT_STAGEABLE"


class A96ExtendedAuthorizationHeaderTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = SQLiteChatStore(Path(tmp.name) / "a96.sqlite3")
        self.addCleanup(self.store.close)
        scope = Scope("A96_OWNER", "A96_TENANT", "A96_WORKSPACE")
        self.outbox = ExecutionOutbox(self.store, scope)
        budget = CumulativeAuthorityBudget(
            self.store, scope,
            authority_budget_ref="A96_BUDGET", policy_version="A96_POLICY",
        )
        self.saga = ExecutionSagaCoordinator(
            self.store, scope, outbox=self.outbox, authority_budget=budget,
        )

    def enqueue(self, payload, intent_ref="A96_INTENT"):
        return self.outbox.enqueue(
            intent_ref=intent_ref, action="send_email",
            payload=payload, aggregate_key="A96_AGG",
            policy_version="A96_POLICY", authorization_ref="A96_APPROVAL",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        )

    def saga_create(self, forward, undo=None):
        return self.saga.create(
            saga_id="A96_SAGA",
            steps=[dict(
                step_key="A96_STEP", action="LOCAL_ONLY", payload=forward,
                capability_class="LOW_RISK", risk_points=1, reversible=True,
                compensation_action="LOCAL_UNDO",
                compensation_payload=undo if undo is not None else {},
                compensation_risk_points=1,
            )], created_at=NOW,
        )

    def no_sql_rows(self):
        for table in ("action_outbox", "action_decisions",
                      "aion_execution_sagas", "aion_execution_saga_steps"):
            self.assertEqual(self.store.db.execute(
                "SELECT COUNT(*) FROM " + table
            ).fetchone()[0], 0, table)

    def test_01_outbox_five_credential_aliases_denied_pre_sql(self):
        names = (
            "Proxy-Authorization",
            "X-Auth-Token",
            "X-Amz-Security-Token",
            "X-Goog-Api-Key",
            "aws_secret_access_key",
        )
        for index, field in enumerate(names):
            with self.subTest(field=field):
                payload = {"headers": {field: "A96_FAKE_ONLY"}}
                with self.assertRaisesRegex(ValueError, DENIED):
                    self.enqueue(payload, intent_ref=f"A96_{index}")
                self.no_sql_rows()

    def test_02_saga_forward_proxy_authorization_denied_pre_sql(self):
        with self.assertRaisesRegex(ValueError, DENIED):
            self.saga_create({"headers": {"Proxy-Authorization": "A96_FAKE_ONLY"}})
        self.no_sql_rows()

    def test_03_saga_compensation_x_auth_token_denied_pre_sql(self):
        with self.assertRaisesRegex(ValueError, DENIED):
            self.saga_create({"event": "local"}, {
                "headers": {"X-Auth-Token": "A96_FAKE_ONLY"},
            })
        self.no_sql_rows()

    def test_04_nested_case_and_unicode_compatibility_denied(self):
        with self.assertRaisesRegex(ValueError, DENIED):
            self.enqueue({"steps": [{"headers": {
                "Ｘ－Ａｕｔｈ－Ｔｏｋｅｎ": "A96_FAKE_ONLY",
            }}]})
        self.no_sql_rows()

    def test_05_benign_references_and_non_secret_headers_continue(self):
        payload = {
            "proxy_authorization_ref": "A96_OWNER_APPROVAL",
            "x_auth_token_ref": "A96_NOTE",
            "aws_secret_access_key_ref": "A96_POINTER",
            "headers": {"Content-Type": "application/json"},
        }
        self.assertEqual(clean_action_payload(payload), payload)
        self.assertEqual(self.enqueue(payload)["enqueue_state"], "ENQUEUED")
        self.assertEqual(
            self.saga_create(payload, {"audit_event": "review"})["create_state"],
            "CREATED",
        )

    def test_06_preexisting_a95_denials_still_hold(self):
        for field in ("Authorization", "Access-Token", "X-Api-Key"):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, DENIED):
                    clean_action_payload({field: "A96_FAKE_ONLY"})


if __name__ == "__main__":
    unittest.main()
