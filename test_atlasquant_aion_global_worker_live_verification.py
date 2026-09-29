import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atlasquant_aion_background_executor import (
    _bundle_digest as _executor_bundle_digest,
    _execute_due_local_work_authorized,
)
from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_core_voice_automation import stage_schedule
from atlasquant_aion_global_worker import (
    GLOBAL_WORKER_NAMESPACE,
    _claim_state,
    _mutated,
    attach_global_worker_state,
    load_global_worker_state,
    stage_arm_global_worker,
)
from atlasquant_aion_global_worker_arming import (
    CONFIRMATION_PHRASE,
    approve_global_worker_arming_plan,
    prepare_global_worker_arming_plan,
)
from atlasquant_aion_global_worker_live_verification import (
    activation_boundary,
    verify_global_worker_live_activation,
)


BASE = datetime(2026, 9, 28, 14, 0, tzinfo=timezone.utc)
ACTIVATED = datetime(2026, 9, 28, 14, 10, tzinfo=timezone.utc)
TICK = datetime(2026, 9, 28, 14, 35, tzinfo=timezone.utc)


def _access(username="mikael", fingerprint="live-verification-admin-1234567890"):
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


def _flag(state="ENABLED", updated_at=ACTIVATED):
    return {
        "status": "CONFIRMED",
        "state": state,
        "variable_present": True,
        "updated_at": updated_at.isoformat(),
        "checked_at": (updated_at + timedelta(seconds=1)).isoformat(),
        "raw_value_exposed": False,
    }


def _activation_result(activated_at=ACTIVATED):
    return {
        "status": "ACTIVATED_PENDING_LIVE_EVIDENCE",
        "activated_at": activated_at.isoformat(),
        "live_heartbeat_confirmed": False,
        "live_receipt_confirmed": False,
    }


class GlobalWorkerLiveVerificationTests(unittest.TestCase):
    def setUp(self):
        self.access = _access()
        self.context = authenticated_context(self.access, Domain.ADMIN)

    def armed_checkpoint(self):
        checkpoint = {}
        plan = prepare_global_worker_arming_plan(
            self.access,
            checkpoint,
            max_jobs=5,
            lease_seconds=600,
            approval_ttl_seconds=900,
            now=BASE,
        )
        approved = approve_global_worker_arming_plan(
            self.access,
            plan["plan"],
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=BASE,
        )
        armed = stage_arm_global_worker(
            self.access,
            checkpoint,
            confirmation=True,
            arming_approval=approved["approval"],
            max_jobs=5,
            lease_seconds=600,
            now=BASE,
        )
        self.assertEqual(armed["status"], "STAGED_ARMED")
        return armed["checkpoint"]

    def runtime(self, checkpoint):
        return {
            "status": "CONFIRMED",
            "checkpoint": checkpoint,
            "sha": "runtime-sha-live-test",
        }

    def with_stats(
        self,
        checkpoint,
        *,
        heartbeat_at="",
        tick_at="",
        runtime_id="",
        ticks=0,
        lease=None,
    ):
        state, status = load_global_worker_state(checkpoint)
        self.assertEqual(status["state"], "CONNECTED")
        stats = deepcopy(state["stats"])
        stats["last_heartbeat_at"] = heartbeat_at
        stats["last_tick_at"] = tick_at
        stats["last_runtime_id"] = runtime_id
        stats["ticks"] = ticks
        changes = {"stats": stats}
        if lease is not None:
            changes["lease"] = lease
        mutated = _mutated(state, **changes)
        return attach_global_worker_state(checkpoint, mutated)

    def with_global_receipt(self, checkpoint, *, now=TICK):
        scheduled = stage_schedule(
            checkpoint,
            self.context,
            title="Live verification task",
            prompt="estado do sistema",
            capability="ADMINISTRATION",
            cadence="DAILY",
            timezone_name="America/Cuiaba",
            hour=10,
            minute=30,
            confirmation=True,
            now=BASE,
        )["checkpoint"]
        result = _execute_due_local_work_authorized(
            self.access,
            scheduled,
            authorization_mode="GLOBAL_WORKER",
            authorization_digest="live-verification-auth",
            execution_principal="aion-global-worker:gha-live-1",
            capability_allowlist=("ADMINISTRATION",),
            max_jobs=5,
            now=now,
        )
        self.assertEqual(result["processed"], 1)
        return result["checkpoint"]

    def test_activation_boundary_uses_later_trusted_timestamp(self):
        flag = _flag(updated_at=ACTIVATED + timedelta(seconds=5))
        result = activation_boundary(
            flag,
            _activation_result(activated_at=ACTIVATED),
        )
        self.assertEqual(result["state"], "READY")
        self.assertEqual(
            result["boundary"],
            (ACTIVATED + timedelta(seconds=5)).isoformat(),
        )

    def test_activation_boundary_requires_timestamp_evidence(self):
        result = activation_boundary(
            {"status": "CONFIRMED", "state": "ENABLED"},
            {"status": "ACTIVATED_PENDING_LIVE_EVIDENCE"},
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "ACTIVATION_TIMESTAMP_EVIDENCE_REQUIRED",
        )

    def test_flag_must_be_enabled(self):
        checkpoint = self.armed_checkpoint()
        report = verify_global_worker_live_activation(
            self.access,
            self.runtime(checkpoint),
            _flag(state="DISABLED"),
            activation_result=_activation_result(),
            now=TICK,
        )
        self.assertEqual(report["status"], "NOT_ENABLED")
        self.assertFalse(report["feature_flag_modified"])

    def test_awaiting_live_evidence_before_timeout(self):
        checkpoint = self.armed_checkpoint()
        report = verify_global_worker_live_activation(
            self.access,
            self.runtime(checkpoint),
            _flag(),
            activation_result=_activation_result(),
            now=ACTIVATED + timedelta(minutes=20),
        )
        self.assertEqual(report["status"], "AWAITING_LIVE_EVIDENCE")
        self.assertFalse(report["live_confirmed"])
        self.assertFalse(report["heartbeat_confirmed"])
        self.assertFalse(report["tick_confirmed"])

    def test_fresh_gha_heartbeat_without_completed_tick_is_not_full_live(self):
        checkpoint = self.with_stats(
            self.armed_checkpoint(),
            heartbeat_at=(ACTIVATED + timedelta(minutes=5)).isoformat(),
            tick_at="",
            runtime_id="gha-100-1",
            ticks=0,
        )
        report = verify_global_worker_live_activation(
            self.access,
            self.runtime(checkpoint),
            _flag(),
            activation_result=_activation_result(),
            now=ACTIVATED + timedelta(minutes=6),
        )
        self.assertEqual(
            report["status"],
            "LIVE_HEARTBEAT_CONFIRMED_AWAITING_TICK",
        )
        self.assertTrue(report["heartbeat_confirmed"])
        self.assertFalse(report["tick_confirmed"])
        self.assertFalse(report["live_confirmed"])

    def test_completed_tick_without_due_work_confirms_live_idle_runner(self):
        checkpoint = self.with_stats(
            self.armed_checkpoint(),
            heartbeat_at=TICK.isoformat(),
            tick_at=TICK.isoformat(),
            runtime_id="gha-200-1",
            ticks=1,
        )
        report = verify_global_worker_live_activation(
            self.access,
            self.runtime(checkpoint),
            _flag(),
            activation_result=_activation_result(),
            now=TICK + timedelta(seconds=10),
        )
        self.assertEqual(report["status"], "LIVE_CONFIRMED_IDLE")
        self.assertTrue(report["heartbeat_confirmed"])
        self.assertTrue(report["tick_confirmed"])
        self.assertTrue(report["live_confirmed"])
        self.assertFalse(report["work_receipt_confirmed"])

    def test_completed_tick_with_global_receipt_confirms_live_work(self):
        checkpoint = self.with_global_receipt(self.armed_checkpoint(), now=TICK)
        checkpoint = self.with_stats(
            checkpoint,
            heartbeat_at=TICK.isoformat(),
            tick_at=TICK.isoformat(),
            runtime_id="gha-300-1",
            ticks=1,
        )
        report = verify_global_worker_live_activation(
            self.access,
            self.runtime(checkpoint),
            _flag(),
            activation_result=_activation_result(),
            now=TICK + timedelta(seconds=10),
        )
        self.assertEqual(report["status"], "LIVE_CONFIRMED_WITH_WORK")
        self.assertTrue(report["live_confirmed"])
        self.assertTrue(report["work_receipt_confirmed"])
        self.assertEqual(report["global_receipts_after_activation"], 1)

    def test_unsafe_global_receipt_blocks_live_claim(self):
        checkpoint = self.with_global_receipt(self.armed_checkpoint(), now=TICK)
        executor = deepcopy(checkpoint["aion_core_executor_v1"])
        executor["receipts"][0]["external_action_executed"] = True
        executor["digest"] = _executor_bundle_digest(executor)
        checkpoint = deepcopy(checkpoint)
        checkpoint["aion_core_executor_v1"] = executor
        checkpoint = self.with_stats(
            checkpoint,
            heartbeat_at=TICK.isoformat(),
            tick_at=TICK.isoformat(),
            runtime_id="gha-400-1",
            ticks=1,
        )
        report = verify_global_worker_live_activation(
            self.access,
            self.runtime(checkpoint),
            _flag(),
            activation_result=_activation_result(),
            now=TICK + timedelta(seconds=10),
        )
        self.assertEqual(report["status"], "BLOCKED_UNSAFE_RECEIPT")
        self.assertEqual(report["unsafe_receipts_after_activation"], 1)
        self.assertFalse(report["live_confirmed"])

    def test_unresolved_inflight_blocks_live_before_stale_lease(self):
        checkpoint = self.armed_checkpoint()
        state, _ = load_global_worker_state(checkpoint)
        claimed, lease = _claim_state(
            state,
            runtime_id="gha-inflight-live",
            now=ACTIVATED + timedelta(minutes=5),
        )
        checkpoint = attach_global_worker_state(checkpoint, claimed)
        report = verify_global_worker_live_activation(
            self.access,
            self.runtime(checkpoint),
            _flag(),
            activation_result=_activation_result(),
            now=ACTIVATED + timedelta(minutes=6),
        )
        self.assertEqual(report["status"], "BLOCKED_INFLIGHT_RECONCILIATION")
        self.assertEqual(
            report["reason"],
            "GLOBAL_WORKER_INFLIGHT_TICK_REQUIRES_RECONCILIATION",
        )
        self.assertTrue(report["inflight_reconciliation_required"])
        self.assertEqual(report["inflight_owner"], "gha-inflight-live")
        self.assertEqual(report["inflight_fencing_token"], lease["fencing_token"])
        self.assertFalse(report["stale_lease"])
        self.assertFalse(report["live_confirmed"])
        self.assertNotIn(lease["token"], str(report))

    def test_stale_owned_lease_blocks_live_claim(self):
        checkpoint = self.with_stats(
            self.armed_checkpoint(),
            heartbeat_at=(ACTIVATED + timedelta(minutes=5)).isoformat(),
            tick_at="",
            runtime_id="gha-500-1",
            ticks=0,
            lease={
                "owner": "gha-500-1",
                "token": "lease-token",
                "fencing_token": 1,
                "acquired_at": ACTIVATED.isoformat(),
                "heartbeat_at": (ACTIVATED + timedelta(minutes=5)).isoformat(),
                "expires_at": (ACTIVATED + timedelta(minutes=6)).isoformat(),
            },
        )
        report = verify_global_worker_live_activation(
            self.access,
            self.runtime(checkpoint),
            _flag(),
            activation_result=_activation_result(),
            now=ACTIVATED + timedelta(minutes=7),
        )
        self.assertEqual(report["status"], "BLOCKED_STALE_LEASE")
        self.assertTrue(report["stale_lease"])
        self.assertFalse(report["live_confirmed"])

    def test_timeout_without_shared_heartbeat_is_explicit(self):
        checkpoint = self.armed_checkpoint()
        report = verify_global_worker_live_activation(
            self.access,
            self.runtime(checkpoint),
            _flag(),
            activation_result=_activation_result(),
            now=ACTIVATED + timedelta(seconds=4501),
        )
        self.assertEqual(report["status"], "LIVE_EVIDENCE_TIMEOUT")
        self.assertIn("NO_SHARED_HEARTBEAT", report["reason"])
        self.assertFalse(report["live_confirmed"])

    def test_other_admin_context_cannot_read_receipts(self):
        checkpoint = self.with_global_receipt(self.armed_checkpoint(), now=TICK)
        checkpoint = self.with_stats(
            checkpoint,
            heartbeat_at=TICK.isoformat(),
            tick_at=TICK.isoformat(),
            runtime_id="gha-600-1",
            ticks=1,
        )
        other = _access(
            username="other-admin",
            fingerprint="other-live-verification-999999",
        )
        report = verify_global_worker_live_activation(
            other,
            self.runtime(checkpoint),
            _flag(),
            activation_result=_activation_result(),
            now=TICK + timedelta(seconds=10),
        )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(
            report["reason"],
            "EXECUTOR_RECEIPT_CONTEXT_OR_INTEGRITY_INVALID",
        )

    def test_admin_ui_never_equates_enabled_with_live(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("ENABLED não significa LIVE", source)
        self.assertIn("Verificar Worker Global ao vivo", source)
        self.assertIn('"Live status"', source)
        self.assertIn('live_report.get("status")', source)
        self.assertIn("LIVE_EVIDENCE_TIMEOUT", source)
        self.assertIn("Worker Global LIVE confirmado por evidência compartilhada", source)

    def test_verifier_is_read_only_and_has_no_mutation_api(self):
        source = Path(
            "atlasquant_aion_global_worker_live_verification.py"
        ).read_text(encoding="utf-8")
        for banned in (
            "requests.put(",
            "requests.post(",
            "requests.patch(",
            "requests.delete(",
            "save_runtime_checkpoint(",
            "activate_global_worker_feature_flag(",
            "run_global_worker_once(",
            "worker_tick(",
            "subprocess.",
            "os.system(",
        ):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
