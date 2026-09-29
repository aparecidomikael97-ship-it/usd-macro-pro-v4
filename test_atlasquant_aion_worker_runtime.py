import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from atlasquant_aion_background_executor import load_executor_receipts
from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_core_voice_automation import stage_schedule
from atlasquant_aion_memory import (
    checkpoint_integrity_report,
    checkpoint_source_digest,
    ensure_operating_checkpoint,
)
from atlasquant_aion_worker_runtime import (
    WORKER_NAMESPACE,
    arm_worker,
    kill_worker,
    load_worker_state,
    pause_worker,
    worker_integrity,
    worker_snapshot,
    worker_tick,
)


CREATED = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)
TICK = datetime(2026, 9, 28, 13, 0, tzinfo=timezone.utc)


def _access(username="mikael", fingerprint="worker-runtime-admin"):
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "role": "ADMIN",
        "session": {
            "username": username,
            "role": "ADMIN",
            "credential_fingerprint": fingerprint,
            "permissions": ["app:read", "admin:read", "aion:admin"],
            "authenticated_at": 10,
            "last_seen": 10,
        },
    }


def _schedule(access, checkpoint=None, capability="ADMINISTRATION", prompt="estado do sistema"):
    context = authenticated_context(access, Domain.ADMIN)
    result = stage_schedule(
        checkpoint or {},
        context,
        title="Worker local seguro",
        prompt=prompt,
        capability=capability,
        cadence="DAILY",
        timezone_name="America/Cuiaba",
        hour=8,
        minute=0,
        confirmation=True,
        now=CREATED,
    )
    return result["checkpoint"]


class AionWorkerRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.access = _access()
        self.context = authenticated_context(self.access, Domain.ADMIN)
        self.runtime_a = "runtime-a"
        self.runtime_b = "runtime-b"

    def arm(self, checkpoint=None, runtime_id=None, now=CREATED):
        return arm_worker(
            self.access,
            checkpoint or {},
            runtime_id=runtime_id or self.runtime_a,
            confirmation=True,
            interval_seconds=60,
            lease_seconds=150,
            now=now,
        )

    def armed_due_checkpoint(self):
        scheduled = _schedule(self.access)
        return self.arm(scheduled)["checkpoint"]

    def test_worker_requires_explicit_admin_arming(self):
        result = arm_worker(
            self.access,
            {},
            runtime_id=self.runtime_a,
            confirmation=False,
            now=CREATED,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["worker_armed"])
        self.assertNotIn(WORKER_NAMESPACE, result["checkpoint"])

    def test_arm_is_session_scoped_not_24x7_or_multi_instance_claim(self):
        result = self.arm({})
        worker = result["worker"]
        self.assertEqual(worker["state"], "ARMED")
        self.assertFalse(worker["kill_switch"])
        self.assertTrue(result["worker_armed"])
        self.assertEqual(result["autonomy_scope"], "ACTIVE_STREAMLIT_SESSION")
        self.assertFalse(result["multi_instance_safe"])
        self.assertEqual(result["concurrency_scope"], "CALLER_CHECKPOINT_ONLY")
        self.assertFalse(result["lease_external_persistence"])
        self.assertFalse(result["continuous_24x7_confirmed"])
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["real_trading_enabled"])

    def test_arm_worker_does_not_depend_on_tick_batch_size_variable(self):
        result = self.arm({})
        self.assertEqual(result["status"], "ARMED")
        self.assertTrue(result["worker_armed"])
        self.assertFalse(result["multi_instance_safe"])
        self.assertEqual(result["concurrency_scope"], "CALLER_CHECKPOINT_ONLY")
        self.assertFalse(result["lease_external_persistence"])

    def test_worker_rejects_empty_or_non_string_runtime_id_before_execution(self):
        armed = self.arm({})["checkpoint"]
        for runtime_id in ("", "   ", None, True, 123, "x" * 161):
            with self.subTest(runtime_id=runtime_id):
                with self.assertRaises(ValueError):
                    worker_tick(
                        self.access,
                        armed,
                        runtime_id=runtime_id,
                        now=TICK,
                    )

    def test_armed_worker_executes_due_local_work_without_external_authority(self):
        checkpoint = self.armed_due_checkpoint()
        result = worker_tick(
            self.access,
            checkpoint,
            runtime_id=self.runtime_a,
            system_context={},
            voice_status={},
            max_jobs=5,
            now=TICK,
        )
        self.assertEqual(result["status"], "TICK_COMPLETED")
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["succeeded"], 1)
        self.assertTrue(result["session_autonomy"])
        self.assertFalse(result["multi_instance_safe"])
        self.assertFalse(result["continuous_24x7_confirmed"])
        self.assertFalse(result["provider_called"])
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["real_trading_enabled"])
        receipts, _ = load_executor_receipts(
            self.context,
            result["checkpoint"],
        )
        self.assertEqual(len(receipts), 1)
        receipt = receipts[0]
        self.assertEqual(receipt["state"], "SUCCEEDED")
        self.assertEqual(receipt["authorization_mode"], "ARMED_WORKER")
        self.assertEqual(receipt["human_confirmation_digest"], "")
        self.assertTrue(receipt["authorization_digest"])
        self.assertFalse(receipt["execution_authorized"])

    def test_executor_snapshot_reports_observed_armed_worker_mode_truthfully(self):
        from atlasquant_aion_background_executor import executor_snapshot

        result = worker_tick(
            self.access,
            self.armed_due_checkpoint(),
            runtime_id=self.runtime_a,
            now=TICK,
        )
        snapshot = executor_snapshot(
            self.access,
            result["checkpoint"],
            now=TICK,
        )
        self.assertIn("ARMED_WORKER", snapshot["authorization_modes_observed"])
        self.assertTrue(snapshot["armed_worker_execution_observed"])
        self.assertFalse(snapshot["manual_invocation_only"])
        self.assertTrue(snapshot["manual_run_available"])
        self.assertFalse(snapshot["autonomous_worker_connected"])

    def test_same_occurrence_remains_idempotent_under_worker_ticks(self):
        first = worker_tick(
            self.access,
            self.armed_due_checkpoint(),
            runtime_id=self.runtime_a,
            now=TICK,
        )
        second = worker_tick(
            self.access,
            first["checkpoint"],
            runtime_id=self.runtime_a,
            now=TICK + timedelta(seconds=60),
        )
        self.assertEqual(second["processed"], 0)
        receipts, _ = load_executor_receipts(
            self.context,
            second["checkpoint"],
        )
        self.assertEqual(len(receipts), 1)
        state, _ = load_worker_state(self.context, second["checkpoint"])
        self.assertEqual(state["stats"]["ticks"], 2)

    def test_active_lease_blocks_second_runtime(self):
        first = worker_tick(
            self.access,
            self.armed_due_checkpoint(),
            runtime_id=self.runtime_a,
            now=TICK,
        )
        second = worker_tick(
            self.access,
            first["checkpoint"],
            runtime_id=self.runtime_b,
            now=TICK + timedelta(seconds=30),
        )
        self.assertEqual(second["status"], "LEASE_HELD")
        self.assertEqual(second["processed"], 0)
        self.assertEqual(second["lease"]["owner"], self.runtime_a)

    def test_expired_lease_is_reclaimed_as_crash_recovery(self):
        first = worker_tick(
            self.access,
            self.armed_due_checkpoint(),
            runtime_id=self.runtime_a,
            now=TICK,
        )
        reclaimed = worker_tick(
            self.access,
            first["checkpoint"],
            runtime_id=self.runtime_b,
            now=TICK + timedelta(seconds=151),
        )
        self.assertEqual(reclaimed["status"], "TICK_COMPLETED")
        self.assertTrue(reclaimed["lease"]["reclaimed"])
        state, _ = load_worker_state(self.context, reclaimed["checkpoint"])
        self.assertEqual(state["lease"]["owner"], self.runtime_b)
        self.assertEqual(state["stats"]["lease_reclaims"], 1)
        self.assertEqual(state["stats"]["crash_recoveries"], 1)

    def test_pause_releases_lease_and_stops_ticks(self):
        first = worker_tick(
            self.access,
            self.armed_due_checkpoint(),
            runtime_id=self.runtime_a,
            now=TICK,
        )
        paused = pause_worker(
            self.access,
            first["checkpoint"],
            confirmation=True,
            now=TICK + timedelta(seconds=5),
        )
        state, _ = load_worker_state(self.context, paused["checkpoint"])
        self.assertEqual(state["state"], "PAUSED")
        self.assertEqual(state["lease"]["owner"], "")
        tick = worker_tick(
            self.access,
            paused["checkpoint"],
            runtime_id=self.runtime_a,
            now=TICK + timedelta(seconds=60),
        )
        self.assertEqual(tick["status"], "PAUSED")
        self.assertEqual(tick["processed"], 0)

    def test_kill_switch_stops_ticks_until_explicit_rearm(self):
        armed = self.armed_due_checkpoint()
        killed = kill_worker(
            self.access,
            armed,
            confirmation=True,
            now=TICK,
        )
        state, _ = load_worker_state(self.context, killed["checkpoint"])
        self.assertEqual(state["state"], "KILLED")
        self.assertTrue(state["kill_switch"])
        tick = worker_tick(
            self.access,
            killed["checkpoint"],
            runtime_id=self.runtime_a,
            now=TICK + timedelta(seconds=60),
        )
        self.assertEqual(tick["status"], "KILLED")
        rearmed = arm_worker(
            self.access,
            killed["checkpoint"],
            runtime_id=self.runtime_a,
            confirmation=True,
            interval_seconds=60,
            lease_seconds=150,
            now=TICK + timedelta(seconds=61),
        )
        self.assertEqual(rearmed["status"], "ARMED")
        self.assertFalse(rearmed["worker"]["kill_switch"])

    def test_failed_local_handler_populates_retry_queue(self):
        checkpoint = self.armed_due_checkpoint()
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            side_effect=RuntimeError("private failure detail"),
        ):
            result = worker_tick(
                self.access,
                checkpoint,
                runtime_id=self.runtime_a,
                now=TICK,
            )
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["retry_queue_count"], 1)
        state, _ = load_worker_state(self.context, result["checkpoint"])
        self.assertEqual(len(state["retry_queue"]), 1)
        queued = state["retry_queue"][0]
        self.assertEqual(queued["attempt"], 1)
        self.assertEqual(queued["state"], "WAITING_BACKOFF")
        self.assertTrue(queued["retry_after"])

    def test_retry_queue_clears_after_successful_retry(self):
        checkpoint = self.armed_due_checkpoint()
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            side_effect=RuntimeError("boom"),
        ):
            first = worker_tick(
                self.access,
                checkpoint,
                runtime_id=self.runtime_a,
                now=TICK,
            )
        second = worker_tick(
            self.access,
            first["checkpoint"],
            runtime_id=self.runtime_a,
            now=TICK + timedelta(seconds=61),
        )
        self.assertEqual(second["succeeded"], 1)
        self.assertEqual(second["retry_queue_count"], 0)
        state, _ = load_worker_state(self.context, second["checkpoint"])
        self.assertEqual(state["retry_queue"], [])

    def test_worker_state_tamper_fails_master_integrity(self):
        armed = self.arm({})["checkpoint"]
        raw = armed[WORKER_NAMESPACE]
        self.assertEqual(worker_integrity(raw)["state"], "MATCH")
        tampered = deepcopy(armed)
        tampered[WORKER_NAMESPACE]["kill_switch"] = True
        self.assertEqual(
            worker_integrity(tampered[WORKER_NAMESPACE])["state"],
            "MISMATCH",
        )
        report = checkpoint_integrity_report(tampered)
        self.assertEqual(report["state"], "MISMATCH")
        self.assertIn("aion_core_worker", report["mismatches"])

    def test_worker_namespace_survives_checkpoint_normalization_and_digest(self):
        base = ensure_operating_checkpoint(_schedule(self.access))
        before = checkpoint_source_digest(base)
        armed = self.arm(base)["checkpoint"]
        normalized = ensure_operating_checkpoint(armed)
        self.assertIn(WORKER_NAMESPACE, normalized)
        self.assertNotEqual(before, checkpoint_source_digest(normalized))

    def test_cross_actor_worker_state_is_isolated(self):
        armed = self.arm({})["checkpoint"]
        other_access = _access(username="outro", fingerprint="other-worker")
        other_context = authenticated_context(other_access, Domain.ADMIN)
        state, status = load_worker_state(other_context, armed)
        self.assertEqual(status["state"], "CONTEXT_ISOLATED")
        self.assertEqual(state["state"], "DISABLED")

    def test_worker_snapshot_never_claims_global_or_24x7_safety(self):
        armed = self.arm({})["checkpoint"]
        snap = worker_snapshot(
            self.access,
            armed,
            runtime_id=self.runtime_a,
            now=TICK,
        )
        self.assertEqual(snap["state"], "ARMED")
        self.assertTrue(snap["session_autonomy"])
        self.assertFalse(snap["multi_instance_safe"])
        self.assertEqual(snap["concurrency_scope"], "CALLER_CHECKPOINT_ONLY")
        self.assertFalse(snap["lease_external_persistence"])
        self.assertFalse(snap["continuous_24x7_confirmed"])
        self.assertEqual(snap["physical_action_adapter"], "UNAVAILABLE")
        self.assertFalse(snap["provider_calls_allowed"])
        self.assertFalse(snap["publication_allowed"])
        self.assertFalse(snap["payment_allowed"])
        self.assertFalse(snap["deploy_allowed"])
        self.assertFalse(snap["real_trading_enabled"])

    def test_ui_contains_fragment_arming_pause_and_kill_switch(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Worker Runtime V1 · autonomia da sessão", source)
        self.assertIn("Armar Worker", source)
        self.assertIn("Pausar Worker", source)
        self.assertIn("Kill switch", source)
        self.assertIn("@st.fragment(run_every=", source)
        self.assertIn("worker_tick(", source)
        self.assertIn("Multi-instância global: NÃO confirmada", source)

    def test_worker_module_has_no_network_subprocess_or_external_persistence(self):
        source = Path("atlasquant_aion_worker_runtime.py").read_text(
            encoding="utf-8"
        )
        for banned in (
            "import requests",
            "requests.",
            "subprocess",
            "urlopen(",
            "save_runtime_checkpoint(",
            "generate_neural_speech(",
            "publish_social(",
            "real_trade(",
        ):
            self.assertNotIn(banned, source)


    def test_worker_consults_loop_governor_before_due_execution(self):
        result = worker_tick(
            self.access,
            self.armed_due_checkpoint(),
            runtime_id=self.runtime_a,
            now=TICK,
        )
        self.assertEqual(result["loop_governor"]["state"], "WITHIN_LIMITS")
        self.assertFalse(result["loop_governor"]["grants_permission"])
        self.assertFalse(result["loop_governor"]["executes_action"])
        self.assertEqual(result["loop_governor"]["selected_count"], 1)

    def test_loop_governor_block_stops_before_lease_and_executor(self):
        checkpoint = self.armed_due_checkpoint()
        blocked = {
            "state": "BLOCK",
            "blockers": ["RESOURCE_BUDGET"],
            "grants_permission": False,
            "executes_action": False,
            "starts_worker": False,
        }
        with patch(
            "atlasquant_aion_worker_runtime.govern_due_batch",
            return_value=blocked,
        ), patch(
            "atlasquant_aion_worker_runtime._execute_due_local_work_authorized"
        ) as executor:
            result = worker_tick(
                self.access,
                checkpoint,
                runtime_id=self.runtime_a,
                now=TICK,
            )
        executor.assert_not_called()
        self.assertEqual(result["status"], "LOOP_GOVERNOR_BLOCKED")
        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["lease"]["state"], "NOT_CLAIMED")
        self.assertEqual(result["loop_governor"]["blockers"], ["RESOURCE_BUDGET"])
        self.assertEqual(result["checkpoint"], checkpoint)

    def test_no_due_work_does_not_need_governor_permission(self):
        armed = self.arm({})["checkpoint"]
        result = worker_tick(
            self.access,
            armed,
            runtime_id=self.runtime_a,
            now=TICK,
        )
        self.assertEqual(result["loop_governor"]["state"], "NOT_REQUIRED")
        self.assertFalse(result["loop_governor"]["grants_permission"])


    def test_worker_returns_non_authoritative_action_receipts(self):
        result = worker_tick(
            self.access,
            self.armed_due_checkpoint(),
            runtime_id=self.runtime_a,
            now=TICK,
        )
        self.assertEqual(len(result["action_receipts"]), 1)
        self.assertFalse(result["action_receipts_are_authority"])
        self.assertEqual(result["action_receipts"][0]["authorization"], "NONE")

    def test_invalid_worker_batch_size_fails_before_governor(self):
        for value in ("5", True, 0, 21):
            with self.assertRaises(ValueError):
                worker_tick(
                    self.access,
                    self.armed_due_checkpoint(),
                    runtime_id=self.runtime_a,
                    max_jobs=value,
                    now=TICK,
                )


if __name__ == "__main__":
    unittest.main()
