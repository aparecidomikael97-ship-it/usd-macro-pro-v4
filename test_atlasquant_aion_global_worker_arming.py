import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atlasquant_aion_global_worker import (
    GLOBAL_WORKER_NAMESPACE,
    load_global_worker_state,
    stage_arm_global_worker,
)
from atlasquant_aion_global_worker_arming import (
    APPROVAL_SCHEMA,
    CONFIRMATION_PHRASE,
    PLAN_SCHEMA,
    approval_integrity,
    approve_global_worker_arming_plan,
    plan_integrity,
    prepare_global_worker_arming_plan,
    validate_global_worker_arming_approval,
)
from atlasquant_aion_memory import checkpoint_source_digest


NOW = datetime(2026, 9, 28, 14, 0, tzinfo=timezone.utc)


def _access(username="mikael", fingerprint="arming-admin-fingerprint-1234567890"):
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


class GlobalWorkerArmingCeremonyTests(unittest.TestCase):
    def setUp(self):
        self.access = _access()
        self.checkpoint = {
            "schema": "ATLASQUANT_AION_MEMORY_V1",
            "checkpoint_version": 18,
            "operating": {
                "task_digest": "arming-source",
                "dirty": False,
            },
        }

    def plan(self, *, checkpoint=None, max_jobs=5, lease_seconds=600, ttl=900):
        result = prepare_global_worker_arming_plan(
            self.access,
            self.checkpoint if checkpoint is None else checkpoint,
            max_jobs=max_jobs,
            lease_seconds=lease_seconds,
            approval_ttl_seconds=ttl,
            now=NOW,
        )
        self.assertEqual(result["status"], "PLAN_READY")
        return result["plan"]

    def approval(self, *, checkpoint=None, max_jobs=5, lease_seconds=600, ttl=900):
        plan = self.plan(
            checkpoint=checkpoint,
            max_jobs=max_jobs,
            lease_seconds=lease_seconds,
            ttl=ttl,
        )
        approved = approve_global_worker_arming_plan(
            self.access,
            plan,
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=NOW,
        )
        self.assertEqual(approved["status"], "APPROVED_FOR_STAGING")
        return approved["approval"]

    def test_plan_is_read_only_scope_bound_and_hashed(self):
        before = deepcopy(self.checkpoint)
        result = prepare_global_worker_arming_plan(
            self.access,
            self.checkpoint,
            max_jobs=5,
            lease_seconds=600,
            approval_ttl_seconds=900,
            now=NOW,
        )
        self.assertEqual(result["status"], "PLAN_READY")
        self.assertEqual(self.checkpoint, before)
        self.assertFalse(result["checkpoint_modified"])
        self.assertFalse(result["runtime_modified"])
        self.assertFalse(result["feature_flag_modified"])
        self.assertFalse(result["worker_armed"])
        plan = result["plan"]
        self.assertEqual(plan["schema"], PLAN_SCHEMA)
        self.assertEqual(plan_integrity(plan)["state"], "MATCH")
        self.assertEqual(
            plan["source_checkpoint_digest"],
            checkpoint_source_digest(self.checkpoint),
        )
        self.assertEqual(plan["required_readiness_stage"], "READY_FOR_ADMIN_ARMING")
        self.assertFalse(plan["readiness_verified_by_plan"])
        self.assertTrue(plan["activation_flag_required"])
        self.assertFalse(plan["activation_flag_changed_by_ceremony"])

    def test_plan_budgets_are_explicit_and_external_budgets_zero(self):
        plan = self.plan(max_jobs=4, lease_seconds=600)
        budgets = plan["budgets"]
        self.assertEqual(budgets["max_jobs_per_tick"], 4)
        self.assertEqual(budgets["max_runtime_checkpoint_writes_per_tick"], 2)
        assumptions = plan["schedule_assumptions"]
        self.assertEqual(assumptions["existing_pulses_per_hour"], 2)
        self.assertEqual(assumptions["estimated_scheduled_ticks_per_utc_day"], 48)
        self.assertFalse(assumptions["hard_daily_limit_claimed"])
        for key in (
            "provider_calls_per_tick",
            "paid_service_calls_per_tick",
            "publications_per_tick",
            "payments_per_tick",
            "deploys_per_tick",
            "merges_per_tick",
            "subprocess_calls_per_tick",
            "market_orders_per_tick",
        ):
            self.assertEqual(budgets[key], 0)
        self.assertFalse(budgets["real_trading_enabled"])

    def test_wrong_phrase_does_not_create_approval(self):
        plan = self.plan()
        result = approve_global_worker_arming_plan(
            self.access,
            plan,
            confirmation=True,
            confirmation_phrase="ARMAR",
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "CONFIRMATION_PHRASE_MISMATCH")
        self.assertFalse(result["runtime_modified"])
        self.assertFalse(result["worker_armed"])

    def test_confirmation_boolean_is_required(self):
        plan = self.plan()
        result = approve_global_worker_arming_plan(
            self.access,
            plan,
            confirmation=False,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "EXPLICIT_CONFIRMATION_REQUIRED")

    def test_tampered_plan_cannot_be_approved(self):
        plan = self.plan()
        plan["lease_seconds"] = 1200
        self.assertEqual(plan_integrity(plan)["state"], "MISMATCH")
        result = approve_global_worker_arming_plan(
            self.access,
            plan,
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "ARMING_PLAN_INTEGRITY_MISMATCH")

    def test_expired_plan_cannot_be_approved(self):
        plan = self.plan(ttl=300)
        result = approve_global_worker_arming_plan(
            self.access,
            plan,
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=NOW + timedelta(seconds=301),
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "ARMING_PLAN_EXPIRED")

    def test_other_admin_cannot_approve_plan(self):
        plan = self.plan()
        result = approve_global_worker_arming_plan(
            _access(
                username="other-admin",
                fingerprint="other-arming-fingerprint-99999999",
            ),
            plan,
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            result["reason"],
            {"ARMING_PLAN_ACTOR_MISMATCH", "ARMING_PLAN_SCOPE_MISMATCH"},
        )

    def test_approval_ticket_is_integrity_protected_and_short_lived(self):
        approval = self.approval(ttl=900)
        self.assertEqual(approval["schema"], APPROVAL_SCHEMA)
        self.assertEqual(approval_integrity(approval)["state"], "MATCH")
        expires = datetime.fromisoformat(approval["expires_at"])
        issued = datetime.fromisoformat(approval["issued_at"])
        self.assertEqual(int((expires - issued).total_seconds()), 900)
        self.assertFalse(approval["runtime_modified"])
        self.assertFalse(approval["feature_flag_modified"])
        self.assertFalse(approval["worker_armed"])

    def test_stage_arm_without_ticket_is_blocked(self):
        result = stage_arm_global_worker(
            self.access,
            self.checkpoint,
            confirmation=True,
            max_jobs=5,
            lease_seconds=600,
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "ARMING_APPROVAL_INTEGRITY_MISMATCH",
        )
        self.assertNotIn(GLOBAL_WORKER_NAMESPACE, result["checkpoint"])

    def test_stage_arm_with_valid_ticket_records_plan_approval_and_budgets(self):
        approval = self.approval(max_jobs=5, lease_seconds=600)
        result = stage_arm_global_worker(
            self.access,
            self.checkpoint,
            confirmation=True,
            arming_approval=approval,
            max_jobs=5,
            lease_seconds=600,
            now=NOW,
        )
        self.assertEqual(result["status"], "STAGED_ARMED")
        self.assertTrue(result["requires_checkpoint_save"])
        self.assertFalse(result["external_persisted"])
        state, status = load_global_worker_state(result["checkpoint"])
        self.assertEqual(status["state"], "CONNECTED")
        self.assertEqual(state["state"], "ARMED")
        self.assertEqual(
            state["arming_plan_digest"],
            approval["plan_digest"],
        )
        self.assertEqual(
            state["arming_approval_digest"],
            approval["approval_digest"],
        )
        self.assertEqual(
            state["resource_budgets"]["max_jobs_per_tick"],
            5,
        )
        self.assertEqual(
            state["resource_budgets"]["market_orders_per_tick"],
            0,
        )
        self.assertFalse(state["resource_budgets"]["real_trading_enabled"])

    def test_ticket_is_bound_to_exact_checkpoint_digest(self):
        approval = self.approval()
        changed = deepcopy(self.checkpoint)
        changed["new_field"] = "changed"
        validation = validate_global_worker_arming_approval(
            self.access,
            changed,
            approval,
            max_jobs=5,
            lease_seconds=600,
            now=NOW,
        )
        self.assertEqual(validation["state"], "BLOCKED")
        self.assertEqual(
            validation["reason"],
            "ARMING_APPROVAL_CHECKPOINT_CHANGED",
        )

    def test_ticket_is_bound_to_exact_job_budget_and_lease(self):
        approval = self.approval(max_jobs=5, lease_seconds=600)
        wrong_jobs = validate_global_worker_arming_approval(
            self.access,
            self.checkpoint,
            approval,
            max_jobs=4,
            lease_seconds=600,
            now=NOW,
        )
        self.assertEqual(
            wrong_jobs["reason"],
            "ARMING_APPROVAL_JOB_BUDGET_MISMATCH",
        )
        wrong_lease = validate_global_worker_arming_approval(
            self.access,
            self.checkpoint,
            approval,
            max_jobs=5,
            lease_seconds=900,
            now=NOW,
        )
        self.assertEqual(
            wrong_lease["reason"],
            "ARMING_APPROVAL_LEASE_MISMATCH",
        )

    def test_expired_ticket_cannot_stage_arm(self):
        approval = self.approval(ttl=300)
        result = stage_arm_global_worker(
            self.access,
            self.checkpoint,
            confirmation=True,
            arming_approval=approval,
            max_jobs=5,
            lease_seconds=600,
            now=NOW + timedelta(seconds=301),
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "ARMING_APPROVAL_EXPIRED")

    def test_ticket_replay_fails_after_first_staging_changes_checkpoint(self):
        approval = self.approval()
        first = stage_arm_global_worker(
            self.access,
            self.checkpoint,
            confirmation=True,
            arming_approval=approval,
            max_jobs=5,
            lease_seconds=600,
            now=NOW,
        )
        self.assertEqual(first["status"], "STAGED_ARMED")
        replay = stage_arm_global_worker(
            self.access,
            first["checkpoint"],
            confirmation=True,
            arming_approval=approval,
            max_jobs=5,
            lease_seconds=600,
            now=NOW + timedelta(seconds=1),
        )
        self.assertEqual(replay["status"], "BLOCKED")
        self.assertEqual(
            replay["reason"],
            "ARMING_APPROVAL_CHECKPOINT_CHANGED",
        )

    def test_ui_has_three_step_ceremony_and_no_direct_arm_button(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Cerimônia de Arming", source)
        self.assertIn("Gerar plano de Arming", source)
        self.assertIn("Criar autorização temporária", source)
        self.assertIn("Preparar ARMED (staged, sem salvar)", source)
        self.assertIn("ARMAR WORKER GLOBAL", source)
        self.assertNotIn('"🌐 Armar Global (staged)"', source)

    def test_ceremony_module_has_no_runtime_write_or_feature_flag_mutation(self):
        source = Path(
            "atlasquant_aion_global_worker_arming.py"
        ).read_text(encoding="utf-8")
        for banned in (
            "requests.put(",
            "requests.post(",
            "requests.patch(",
            "requests.delete(",
            "save_runtime_checkpoint(",
            "_persist_runtime_checkpoint_cas(",
            "run_global_worker_once(",
            "subprocess.",
            "os.system(",
        ):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
