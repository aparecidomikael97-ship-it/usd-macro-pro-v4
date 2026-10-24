"""A190 G29 — static Codex findings -> REAL ExecutionOutbox RED/guard tests.

Only SQLiteChatStore and ExecutionOutbox.enqueue/get/list; no dispatch,
synthetic test actors only, no Worker, no provider, no external side effects.
RED denotes observed ambiguity, not confirmed unauthorized external effects.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.privacy import redact
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from g13_signed_semantic_outbox_bridge_lab import semantic_operation_digest

NOW = datetime(2026, 10, 24, 16, 0, tzinfo=timezone.utc)
SCOPE = Scope("g29-synthetic-owner", "g29-synthetic-tenant", "g29-synthetic-workspace")
DEFAULT_PAYLOAD = {"invoice": "synthetic-42", "amount_minor": 1000}


class G29RealOutboxSemanticAuthRed(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-g29-red-")
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteChatStore(Path(self.tmp.name) / "staging.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(self.store, SCOPE)

    def stage(self, **changes):
        options = {
            "intent_ref": "g29-intent-1",
            "action": "synthetic_no_provider",
            "payload": DEFAULT_PAYLOAD,
            "aggregate_key": "g29-invoice-group",
            "policy_version": "policy-v1",
            "authorization_ref": "auth-v1",
            "created_at": NOW,
            "valid_until": NOW + timedelta(minutes=5),
        }
        options.update(changes)
        return self.outbox.enqueue(**options)

    def assert_replay_retains(self, expected_field, *, changed):
        first = self.stage()
        again = self.stage(**changed)
        self.assertEqual(again["enqueue_state"], "IDEMPOTENT")
        self.assertEqual(first["idempotency_key"], again["idempotency_key"])
        self.assertEqual(again["decision"][expected_field], first["decision"][expected_field])
        self.assertEqual(len(self.outbox.list()), 1)
        self.assertFalse(again["executes_action"])
        return first, again

    def test_01_identical_replay_is_idempotent(self):
        self.assert_replay_retains("authorization_ref", changed={})

    def test_02_policy_change_does_not_update_staged_decision_red(self):
        a, b = self.assert_replay_retains(
            "policy_version", changed={"policy_version": "policy-v2"}
        )
        self.assertEqual(b["decision"]["policy_version"], "policy-v1")
        print("G29_POLICY_REPLAY_RED=CHANGED_POLICY_RETURNS_OLD_DECISION")

    def test_03_authorization_change_does_not_update_decision_red(self):
        _, b = self.assert_replay_retains(
            "authorization_ref", changed={"authorization_ref": "auth-v2"}
        )
        self.assertEqual(b["decision"]["authorization_ref"], "auth-v1")
        print("G29_AUTH_REPLAY_RED=CHANGED_AUTH_REF_RETURNS_OLD_DECISION")

    def test_04_shorter_validity_does_not_replace_old_expiry_red(self):
        first, b = self.assert_replay_retains(
            "valid_until", changed={"valid_until": NOW + timedelta(minutes=1)}
        )
        self.assertEqual(first["decision"]["valid_until"], b["decision"]["valid_until"])
        print("G29_EXPIRY_REPLAY_RED=SHORTER_VALIDITY_RETURNS_OLD_EXPIRY")

    def test_05_new_reauth_requirement_does_not_replace_old_decision_red(self):
        first, b = self.assert_replay_retains(
            "requires_reauth",
            changed={"requires_reauth": True, "reauth_ref": "new-synthetic-reauth"},
        )
        self.assertFalse(first["decision"]["requires_reauth"])
        self.assertFalse(b["decision"]["requires_reauth"])
        print("G29_REAUTH_REPLAY_RED=NEW_REAUTH_REQUIREMENT_RETURNS_OLD_DECISION")

    def test_06_changed_reauth_reference_does_not_replace_old_decision_red(self):
        first = self.stage(requires_reauth=True, reauth_ref="reauth-v1")
        second = self.stage(requires_reauth=True, reauth_ref="reauth-v2")
        self.assertEqual(second["enqueue_state"], "IDEMPOTENT")
        self.assertEqual(second["decision"]["reauth_ref"], "reauth-v1")
        self.assertEqual(first["idempotency_key"], second["idempotency_key"])
        print("G29_REAUTH_REF_REPLAY_RED=CHANGED_REAUTH_REFERENCE_IGNORED")

    def test_07_created_time_change_does_not_replace_old_decision(self):
        a, b = self.assert_replay_retains(
            "created_at",
            changed={
                "created_at": NOW + timedelta(seconds=30),
                "valid_until": NOW + timedelta(minutes=5),
            },
        )
        self.assertEqual(a["decision"]["created_at"], b["decision"]["created_at"])

    def test_08_new_intent_alias_same_operation_creates_second_row_red(self):
        a = self.stage()
        b = self.stage(intent_ref="g29-intent-2")
        self.assertNotEqual(a["idempotency_key"], b["idempotency_key"])
        self.assertEqual(len(self.outbox.list()), 2)
        print("G29_CALLER_ALIAS_RED=SAME_OPERATION_NEW_REF_TWO_RESERVATIONS")

    def test_09_new_intent_ref_new_policy_creates_second_row(self):
        a = self.stage()
        b = self.stage(intent_ref="g29-intent-2", policy_version="policy-v2")
        self.assertNotEqual(a["idempotency_key"], b["idempotency_key"])
        self.assertEqual(len(self.outbox.list()), 2)

    def test_10_same_intent_ref_real_amount_change_denies_collision(self):
        self.stage()
        with self.assertRaisesRegex(ValueError, "idempotency collision"):
            self.stage(payload={"invoice": "synthetic-42", "amount_minor": 2000})
        self.assertEqual(len(self.outbox.list()), 1)

    def test_11_same_intent_ref_different_action_denies_collision(self):
        self.stage()
        with self.assertRaisesRegex(ValueError, "idempotency collision"):
            self.stage(action="different_synthetic_action")
        self.assertEqual(len(self.outbox.list()), 1)

    def test_12_redacted_credential_values_produce_same_key_red(self):
        a = self.stage(payload={"invoice": "synthetic-42", "token": "synthetic-A"})
        b = self.stage(payload={"invoice": "synthetic-42", "token": "synthetic-B"})
        self.assertEqual(a["idempotency_key"], b["idempotency_key"])
        self.assertEqual(b["enqueue_state"], "IDEMPOTENT")
        self.assertEqual(b["decision"]["payload"]["token"], "[REDACTED]")
        print("G29_REDACTION_ALIAS_RED=DIFFERENT_CREDENTIAL_VALUES_SAME_IDEMPOTENCY_KEY")

    def test_13_redacted_string_secret_values_collide(self):
        a = self.stage(payload={"note": "api_key=syntheticAAA"})
        b = self.stage(payload={"note": "api_key=syntheticBBB"})
        self.assertEqual(a["idempotency_key"], b["idempotency_key"])
        self.assertEqual(b["enqueue_state"], "IDEMPOTENT")

    def test_14_nested_redacted_values_collapse_digest(self):
        a = self.stage(payload={"nested": {"secret": "alpha"}})
        b = self.stage(payload={"nested": {"secret": "bravo"}})
        self.assertEqual(a["idempotency_key"], b["idempotency_key"])
        self.assertEqual(b["enqueue_state"], "IDEMPOTENT")

    def test_15_g13_semantic_digest_redaction_collision_red(self):
        payload_a = {"invoice": "synthetic-42", "token": "synthetic-A"}
        payload_b = {"invoice": "synthetic-42", "token": "synthetic-B"}
        self.assertNotEqual(payload_a, payload_b)
        self.assertEqual(redact(payload_a), redact(payload_b))
        key_a = semantic_operation_digest(
            SCOPE, business_event_id="synthetic-biz-42",
            action="synthetic_no_provider", aggregate_key="g29-invoice-group",
            payload=payload_a,
        )
        key_b = semantic_operation_digest(
            SCOPE, business_event_id="synthetic-biz-42",
            action="synthetic_no_provider", aggregate_key="g29-invoice-group",
            payload=payload_b,
        )
        self.assertEqual(key_a, key_b)
        print("G29_G13_DIGEST_REDACTION_RED=SAME_SIGNABLE_DIGEST_DIFFERENT_ORIGINAL_PAYLOAD")

    def test_16_no_redaction_different_business_amounts_have_different_semantic_digest(self):
        a = semantic_operation_digest(
            SCOPE, business_event_id="synthetic-biz-42",
            action="synthetic_no_provider", aggregate_key="g29-invoice-group",
            payload={"amount_minor": 1000},
        )
        b = semantic_operation_digest(
            SCOPE, business_event_id="synthetic-biz-42",
            action="synthetic_no_provider", aggregate_key="g29-invoice-group",
            payload={"amount_minor": 2000},
        )
        self.assertNotEqual(a, b)

    def test_17_transaction_binding_differences_deny_intent_collision(self):
        args = dict(
            transaction_id="synthetic-txn-42",
            authority_budget_ref="synthetic-budget-42",
            risk_points=1, capability_class="SYNTHETIC",
        )
        self.stage(**args)
        with self.assertRaisesRegex(ValueError, "idempotency collision"):
            self.stage(**{**args, "risk_points": 2})
        self.assertEqual(len(self.outbox.list()), 1)

    def test_18_default_injected_true_callback_is_quarantined(self):
        outbox = ExecutionOutbox(
            self.store, SCOPE,
            evidence_verifier=lambda *_: True,
            first_attempt_guard=lambda _: True,
        )
        self.assertFalse(outbox._reserved_first_attempt({"synthetic": True}))
        self.assertFalse(outbox._verified_evidence("EFFECT_CONFIRMED", {}, {}))

    def test_19_separate_workspace_has_separate_local_idempotency_namespace(self):
        a = self.stage()
        other_scope = Scope(SCOPE.owner_id, SCOPE.tenant_id, "other-synthetic-workspace")
        other = ExecutionOutbox(self.store, other_scope)
        b = other.enqueue(
            intent_ref="g29-intent-1", action="synthetic_no_provider",
            payload=DEFAULT_PAYLOAD, aggregate_key="g29-invoice-group",
            policy_version="policy-v1", authorization_ref="auth-v1",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        )
        self.assertNotEqual(a["idempotency_key"], b["idempotency_key"])
        self.assertEqual(len(self.outbox.list()), 1)
        self.assertEqual(len(other.list()), 1)

    def test_20_no_real_effects_created_by_staging_matrix(self):
        self.stage()
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertTrue(all(not r["executes_action"] for r in self.outbox.list()))


if __name__ == "__main__":
    unittest.main()
