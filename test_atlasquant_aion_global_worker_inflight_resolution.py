import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atlasquant_aion_background_executor import _execute_due_local_work_authorized
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
    CONFIRMATION_PHRASE as ARMING_PHRASE,
    approve_global_worker_arming_plan,
    prepare_global_worker_arming_plan,
)
from atlasquant_aion_global_worker_inflight_resolution import (
    CONFIRMATION_PHRASE,
    stage_resolved_inflight_clear,
)


BASE = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)
TICK = datetime(2026, 9, 28, 13, 0, tzinfo=timezone.utc)
AFTER_EXPIRY = TICK + timedelta(seconds=601)


def _access(username="mikael", fingerprint="inflight-resolution-admin-1234567890"):
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "role": "ADMIN",
        "session": {
            "username": username,
            "role": "ADMIN",
            "credential_fingerprint": fingerprint,
            "permissions": ["app:read", "admin:read", "aion:admin"],
        },
    }


class GlobalInflightResolutionTests(unittest.TestCase):
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
            confirmation_phrase=ARMING_PHRASE,
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
            title="Resolution safe task",
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

    def claim(self, checkpoint, *, runtime_id="gha-resolution"):
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

    def runtime(self, checkpoint, *, sha="sha-resolution"):
        return {
            "status": "CONFIRMED",
            "checkpoint": checkpoint,
            "sha": sha,
        }

    def test_confirmation_is_required_before_any_staging(self):
        claimed, _ = self.claim(self.arm({}))
        result = stage_resolved_inflight_clear(
            self.access,
            self.runtime(claimed),
            confirmation=False,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=AFTER_EXPIRY,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["requires_checkpoint_save"])
        state, _ = load_global_worker_state(result["checkpoint"])
        self.assertTrue(state["inflight_tick"])

    def test_exact_phrase_is_required(self):
        claimed, _ = self.claim(self.arm({}))
        result = stage_resolved_inflight_clear(
            self.access,
            self.runtime(claimed),
            confirmation=True,
            confirmation_phrase="limpar",
            now=AFTER_EXPIRY,
        )
        self.assertEqual(result["reason"], "EXACT_CONFIRMATION_PHRASE_REQUIRED")
        self.assertFalse(result["requires_checkpoint_save"])

    def test_active_lease_cannot_be_cleared(self):
        claimed, _ = self.claim(self.arm({}))
        result = stage_resolved_inflight_clear(
            self.access,
            self.runtime(claimed),
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=TICK + timedelta(seconds=30),
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "EXPIRED_OWNED_LEASE_REQUIRED")
        self.assertFalse(result["requires_checkpoint_save"])

    def test_empty_batch_can_stage_clear_after_lease_expiry(self):
        claimed, intent = self.claim(self.arm({}))
        self.assertEqual(intent["count"], 0)
        result = stage_resolved_inflight_clear(
            self.access,
            self.runtime(claimed, sha="sha-empty"),
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=AFTER_EXPIRY,
        )
        self.assertEqual(result["status"], "STAGED_CLEAR_READY")
        self.assertEqual(result["assessment_status"], "EMPTY_BATCH_READY_FOR_HUMAN_CLEAR")
        self.assertEqual(result["expected_sha"], "sha-empty")
        self.assertTrue(result["requires_checkpoint_save"])
        self.assertTrue(result["conditional_write_required"])
        self.assertFalse(result["external_persisted"])
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertFalse(result["automatic_clear_executed"])
        state, _ = load_global_worker_state(result["checkpoint"])
        self.assertEqual(state["inflight_tick"], {})
        self.assertEqual(state["lease"]["owner"], "")
        self.assertEqual(state["state"], "ARMED")

    def test_terminal_evidence_can_stage_clear_after_expiry(self):
        claimed, _ = self.claim(self.due_checkpoint())
        executed = _execute_due_local_work_authorized(
            self.access,
            claimed,
            authorization_mode="GLOBAL_WORKER",
            authorization_digest="resolution-auth",
            execution_principal="aion-global-worker:gha-resolution",
            capability_allowlist=("ADMINISTRATION",),
            max_jobs=5,
            now=TICK,
        )
        result = stage_resolved_inflight_clear(
            self.access,
            self.runtime(executed["checkpoint"]),
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=AFTER_EXPIRY,
        )
        self.assertEqual(result["status"], "STAGED_CLEAR_READY")
        self.assertEqual(
            result["assessment_status"],
            "TERMINAL_EVIDENCE_READY_FOR_HUMAN_CLEAR",
        )
        self.assertEqual(result["resolved_work_intent_count"], 1)
        self.assertTrue(result["resolution_digest"])
        self.assertFalse(result["runtime_modified"])

    def test_ambiguous_execution_cannot_be_cleared_by_safe_ceremony(self):
        claimed, _ = self.claim(self.due_checkpoint())
        result = stage_resolved_inflight_clear(
            self.access,
            self.runtime(claimed),
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=AFTER_EXPIRY,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "INFLIGHT_RECONCILIATION_NOT_CLEARABLE")
        self.assertEqual(
            result["assessment_status"],
            "AMBIGUOUS_EXECUTION_REVIEW_REQUIRED",
        )
        self.assertFalse(result["requires_checkpoint_save"])
        self.assertFalse(result["automatic_retry_allowed"])

    def test_other_admin_scope_cannot_stage_clear(self):
        claimed, _ = self.claim(self.arm({}))
        other = _access(
            username="other",
            fingerprint="other-resolution-admin-999999999",
        )
        result = stage_resolved_inflight_clear(
            other,
            self.runtime(claimed),
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=AFTER_EXPIRY,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "GLOBAL_WORKER_CONTEXT_MISMATCH")
        self.assertFalse(result["requires_checkpoint_save"])


    def test_resolution_module_has_no_persistence_or_execution_apis(self):
        source = Path(
            "atlasquant_aion_global_worker_inflight_resolution.py"
        ).read_text(encoding="utf-8")
        for banned in (
            "requests.put(",
            "requests.post(",
            "save_runtime_checkpoint(",
            "_persist_runtime_checkpoint_cas(",
            "run_global_worker_once(",
            "_execute_due_local_work_authorized(",
            "activate_global_worker_feature_flag(",
            "workflow_dispatch",
            "subprocess.",
            "os.system(",
            "real_trade(",
        ):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
