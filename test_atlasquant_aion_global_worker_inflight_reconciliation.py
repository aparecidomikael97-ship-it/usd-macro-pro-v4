import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from atlasquant_aion_background_executor import (
    _bundle_digest as _executor_bundle_digest,
    _execute_due_local_work_authorized,
)
from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_core_voice_automation import stage_schedule
from atlasquant_aion_global_worker import (
    _claim_state,
    _global_work_intent,
    attach_global_worker_state,
    load_global_worker_state,
    stage_arm_global_worker,
)
from atlasquant_aion_global_worker_arming import (
    CONFIRMATION_PHRASE,
    approve_global_worker_arming_plan,
    prepare_global_worker_arming_plan,
)
from atlasquant_aion_global_worker_inflight_reconciliation import (
    assess_global_inflight_reconciliation,
)


BASE = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)
TICK = datetime(2026, 9, 28, 13, 0, tzinfo=timezone.utc)


def _access():
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "role": "ADMIN",
        "session": {
            "username": "mikael",
            "role": "ADMIN",
            "credential_fingerprint": "inflight-reconcile-admin-1234567890",
            "permissions": ["app:read", "admin:read", "aion:admin"],
        },
    }


class GlobalInflightReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.access = _access()
        self.context = authenticated_context(self.access, Domain.ADMIN)

    def arm(self, checkpoint):
        plan = prepare_global_worker_arming_plan(
            self.access,
            checkpoint,
            max_jobs=5,
            lease_seconds=600,
            approval_ttl_seconds=900,
            now=BASE,
        )
        approval = approve_global_worker_arming_plan(
            self.access,
            plan["plan"],
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=BASE,
        )["approval"]
        return stage_arm_global_worker(
            self.access,
            checkpoint,
            confirmation=True,
            arming_approval=approval,
            max_jobs=5,
            lease_seconds=600,
            now=BASE,
        )["checkpoint"]

    def due_checkpoint(self):
        scheduled = stage_schedule(
            {},
            self.context,
            title="Reconcile safe task",
            prompt="estado do sistema",
            capability="ADMINISTRATION",
            cadence="DAILY",
            timezone_name="America/Cuiaba",
            hour=8,
            minute=0,
            confirmation=True,
            now=BASE,
        )["checkpoint"]
        return self.arm(scheduled)

    def claimed(self, checkpoint, *, runtime_id="gha-reconcile"):
        state, _ = load_global_worker_state(checkpoint)
        intent = _global_work_intent(
            self.context,
            checkpoint,
            max_jobs=state["max_jobs"],
            now=TICK,
        )
        claimed, _ = _claim_state(
            state,
            runtime_id=runtime_id,
            now=TICK,
            work_intent=intent,
        )
        return attach_global_worker_state(checkpoint, claimed), intent

    def runtime(self, checkpoint):
        return {
            "status": "CONFIRMED",
            "checkpoint": checkpoint,
            "sha": "runtime-sha-reconcile",
        }

    def test_no_inflight_needs_no_reconciliation(self):
        result = assess_global_inflight_reconciliation(
            self.runtime(self.due_checkpoint()),
            now=TICK,
        )
        self.assertEqual(result["status"], "NO_INFLIGHT")
        self.assertFalse(result["reconciliation_required"])
        self.assertFalse(result["human_review_required"])
        self.assertFalse(result["executes_action"])

    def test_empty_batch_is_prepared_for_human_clear_without_auto_mutation(self):
        checkpoint = self.arm({})
        claimed, intent = self.claimed(checkpoint)
        self.assertEqual(intent["count"], 0)
        result = assess_global_inflight_reconciliation(
            self.runtime(claimed),
            now=TICK + timedelta(minutes=20),
        )
        self.assertEqual(result["status"], "EMPTY_BATCH_READY_FOR_HUMAN_CLEAR")
        self.assertEqual(result["work_intent_count"], 0)
        self.assertEqual(result["suggested_resolution"], "CLEAR_INFLIGHT_NO_WORK")
        self.assertFalse(result["automatic_clear_allowed"])
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertTrue(result["human_review_required"])
        self.assertFalse(result["runtime_modified"])

    def test_missing_receipt_is_reported_as_ambiguous_not_retried(self):
        checkpoint, intent = self.claimed(self.due_checkpoint())
        self.assertEqual(intent["count"], 1)
        result = assess_global_inflight_reconciliation(
            self.runtime(checkpoint),
            now=TICK + timedelta(minutes=20),
        )
        self.assertEqual(result["status"], "AMBIGUOUS_EXECUTION_REVIEW_REQUIRED")
        self.assertEqual(result["no_terminal_evidence"], 1)
        self.assertEqual(result["terminal_proven"], 0)
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertEqual(len(result["occurrences"]), 1)
        self.assertNotIn("prompt", result["occurrences"][0])
        self.assertNotIn("title", result["occurrences"][0])

    def test_persisted_terminal_receipt_is_bound_to_inflight_occurrence(self):
        checkpoint, intent = self.claimed(self.due_checkpoint())
        executed = _execute_due_local_work_authorized(
            self.access,
            checkpoint,
            authorization_mode="GLOBAL_WORKER",
            authorization_digest="reconcile-auth",
            execution_principal="aion-global-worker:gha-reconcile",
            capability_allowlist=("ADMINISTRATION",),
            max_jobs=5,
            now=TICK,
        )
        result = assess_global_inflight_reconciliation(
            self.runtime(executed["checkpoint"]),
            now=TICK + timedelta(minutes=20),
        )
        self.assertEqual(
            result["status"],
            "TERMINAL_EVIDENCE_READY_FOR_HUMAN_CLEAR",
        )
        self.assertEqual(result["terminal_proven"], 1)
        self.assertEqual(result["no_terminal_evidence"], 0)
        self.assertEqual(
            result["occurrences"][0]["occurrence_key"],
            intent["occurrences"][0]["occurrence_key"],
        )
        self.assertTrue(result["occurrences"][0]["latest_receipt_id"])
        self.assertFalse(result["automatic_clear_allowed"])

    def test_unsafe_or_malformed_receipt_evidence_blocks_reconciliation(self):
        checkpoint, _ = self.claimed(self.due_checkpoint())
        executed = _execute_due_local_work_authorized(
            self.access,
            checkpoint,
            authorization_mode="GLOBAL_WORKER",
            authorization_digest="reconcile-auth",
            execution_principal="aion-global-worker:gha-reconcile",
            capability_allowlist=("ADMINISTRATION",),
            max_jobs=5,
            now=TICK,
        )
        tampered = deepcopy(executed["checkpoint"])
        raw = tampered["aion_core_executor_v1"]
        raw["receipts"][0]["external_action_executed"] = True
        raw["digest"] = _executor_bundle_digest(raw)

        result = assess_global_inflight_reconciliation(
            self.runtime(tampered),
            now=TICK + timedelta(minutes=20),
        )
        self.assertEqual(result["status"], "BLOCKED_UNSAFE_EVIDENCE")
        self.assertTrue(result["unsafe_evidence"])
        self.assertEqual(result["suggested_resolution"], "PRESERVE_AND_ESCALATE")
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertFalse(result["executes_action"])


if __name__ == "__main__":
    unittest.main()
