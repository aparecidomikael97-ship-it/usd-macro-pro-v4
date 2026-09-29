import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from atlasquant_aion_background_executor import (
    executor_snapshot,
    load_executor_receipts,
)
from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_intelligence.evidence import digest
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_core_voice_automation import stage_schedule
from atlasquant_aion_global_worker import (
    GLOBAL_WORKER_NAMESPACE,
    SERVICE_PRINCIPAL,
    _claim_state,
    _persist_runtime_checkpoint_cas,
    _release_state,
    _runtime_id,
    attach_global_worker_state,
    global_worker_integrity,
    global_worker_snapshot,
    load_global_worker_state,
    run_global_worker_once,
    stage_arm_global_worker,
    stage_kill_global_worker,
    stage_pause_global_worker,
)
from atlasquant_aion_global_worker_arming import (
    CONFIRMATION_PHRASE,
    approve_global_worker_arming_plan,
    prepare_global_worker_arming_plan,
)
from atlasquant_aion_memory import (
    RuntimeConfig,
    checkpoint_integrity_report,
    checkpoint_source_digest,
    ensure_operating_checkpoint,
)


CREATED = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)
TICK = datetime(2026, 9, 28, 13, 0, tzinfo=timezone.utc)


def _access(username="mikael", fingerprint="global-worker-admin-fingerprint-1234567890"):
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


def _config():
    return RuntimeConfig(
        token="test-token",
        repo="owner/repo",
        branch="atlasquant-runtime",
    )


class AionGlobalDurableWorkerTests(unittest.TestCase):
    def setUp(self):
        self.access = _access()
        self.context = authenticated_context(self.access, Domain.ADMIN)

    def schedule(
        self,
        *,
        capability="ADMINISTRATION",
        prompt="estado do sistema",
        title="Global safe task",
        checkpoint=None,
    ):
        result = stage_schedule(
            checkpoint or {},
            self.context,
            title=title,
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

    def approval(self, checkpoint, *, max_jobs=5, lease_seconds=600, now=CREATED):
        plan = prepare_global_worker_arming_plan(
            self.access,
            checkpoint,
            max_jobs=max_jobs,
            lease_seconds=lease_seconds,
            approval_ttl_seconds=900,
            now=now,
        )
        self.assertEqual(plan["status"], "PLAN_READY")
        approved = approve_global_worker_arming_plan(
            self.access,
            plan["plan"],
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=now,
        )
        self.assertEqual(approved["status"], "APPROVED_FOR_STAGING")
        return approved["approval"]

    def armed_checkpoint(self, *, capability="ADMINISTRATION", prompt="estado do sistema"):
        scheduled = self.schedule(capability=capability, prompt=prompt)
        result = stage_arm_global_worker(
            self.access,
            scheduled,
            confirmation=True,
            arming_approval=self.approval(scheduled),
            max_jobs=5,
            lease_seconds=600,
            now=CREATED,
        )
        return result["checkpoint"]

    def fake_persist(self, captures):
        def _persist(checkpoint, config, *, expected_sha, operation, timeout=15.0):
            captures.append({
                "checkpoint": deepcopy(checkpoint),
                "expected_sha": expected_sha,
                "operation": operation,
            })
            return {
                "status": "CONFIRMED",
                "saved": True,
                "verified": True,
                "sha": "sha-" + str(len(captures)),
                "checkpoint": deepcopy(checkpoint),
                "integrity": checkpoint_integrity_report(checkpoint),
            }
        return _persist

    def test_global_arming_requires_explicit_confirmation(self):
        result = stage_arm_global_worker(
            self.access,
            {},
            confirmation=False,
            now=CREATED,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertNotIn(GLOBAL_WORKER_NAMESPACE, result["checkpoint"])

    def test_staged_arm_binds_exact_admin_scope_without_persisting(self):
        checkpoint = {}
        result = stage_arm_global_worker(
            self.access,
            checkpoint,
            confirmation=True,
            arming_approval=self.approval(
                checkpoint,
                max_jobs=4,
                lease_seconds=600,
            ),
            max_jobs=4,
            lease_seconds=600,
            now=CREATED,
        )
        self.assertEqual(result["status"], "STAGED_ARMED")
        self.assertTrue(result["requires_checkpoint_save"])
        self.assertFalse(result["external_persisted"])
        state, status = load_global_worker_state(result["checkpoint"])
        self.assertEqual(status["state"], "CONNECTED")
        self.assertEqual(state["state"], "ARMED")
        self.assertFalse(state["kill_switch"])
        self.assertEqual(state["max_jobs"], 4)
        self.assertEqual(state["lease_seconds"], 600)
        snap = global_worker_snapshot(self.access, result["checkpoint"], now=CREATED)
        self.assertTrue(snap["delegated_scope_matches"])
        self.assertFalse(snap["automatic_external_business_actions"])
        self.assertFalse(snap["real_trading_enabled"])

    def test_other_admin_context_cannot_read_global_control_details(self):
        checkpoint = self.armed_checkpoint()
        other = _access(
            username="other-admin",
            fingerprint="other-global-worker-fingerprint-999999",
        )
        snapshot = global_worker_snapshot(other, checkpoint, now=CREATED)
        self.assertEqual(snapshot["status"], "CONTEXT_ISOLATED")
        self.assertEqual(snapshot["state"], "UNKNOWN")
        self.assertEqual(snapshot["delegated_actor"], "")
        self.assertEqual(snapshot["lease_owner"], "")
        self.assertEqual(snapshot["stats"], {})
        self.assertEqual(snapshot["allowed_capabilities"], [])

    def test_feature_flag_off_makes_zero_network_calls(self):
        with patch("atlasquant_aion_global_worker.load_runtime_checkpoint") as load:
            result = run_global_worker_once(
                config=_config(),
                runtime_id="gha-1-1",
                feature_enabled=False,
                now=TICK,
            )
        load.assert_not_called()
        self.assertEqual(result["status"], "FEATURE_DISABLED")
        self.assertFalse(result["network_called"])
        self.assertEqual(result["processed"], 0)

    def test_loop_governor_block_stops_before_global_lease_write_and_executor(self):
        checkpoint = self.armed_checkpoint()
        blocked = {
            "state": "BLOCK",
            "blockers": ["RESOURCE_BUDGET"],
            "grants_permission": False,
            "executes_action": False,
            "starts_worker": False,
        }
        with patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
            return_value={
                "status": "CONFIRMED",
                "checkpoint": checkpoint,
                "sha": "sha-0",
                "integrity": checkpoint_integrity_report(checkpoint),
            },
        ), patch(
            "atlasquant_aion_global_worker.govern_due_batch",
            return_value=blocked,
        ) as governor, patch(
            "atlasquant_aion_global_worker._persist_runtime_checkpoint_cas"
        ) as persist, patch(
            "atlasquant_aion_global_worker._execute_due_local_work_authorized"
        ) as executor:
            result = run_global_worker_once(
                config=_config(),
                runtime_id="gha-governor-block",
                feature_enabled=True,
                now=TICK,
            )

        governor.assert_called_once()
        persist.assert_not_called()
        executor.assert_not_called()
        self.assertEqual(result["status"], "LOOP_GOVERNOR_BLOCKED")
        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["loop_governor"]["blockers"], ["RESOURCE_BUDGET"])
        self.assertFalse(result["runtime_write_attempted"])
        self.assertTrue(result["network_called"])
        self.assertFalse(result["external_action_executed"])

    def test_global_tick_claims_fence_executes_and_persists_receipt(self):
        checkpoint = self.armed_checkpoint()
        captures = []
        with patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
            return_value={
                "status": "CONFIRMED",
                "checkpoint": checkpoint,
                "sha": "sha-0",
                "integrity": checkpoint_integrity_report(checkpoint),
            },
        ), patch(
            "atlasquant_aion_global_worker._persist_runtime_checkpoint_cas",
            side_effect=self.fake_persist(captures),
        ):
            result = run_global_worker_once(
                config=_config(),
                runtime_id="gha-100-1",
                feature_enabled=True,
                now=TICK,
            )

        self.assertEqual(result["status"], "CONFIRMED")
        self.assertEqual(result["authorization_mode"], "GLOBAL_WORKER")
        self.assertEqual(result["service_principal"], SERVICE_PRINCIPAL)
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["loop_governor"]["state"], "WITHIN_LIMITS")
        self.assertEqual(result["loop_governor"]["selected_count"], 1)
        self.assertFalse(result["loop_governor"]["grants_permission"])
        self.assertFalse(result["loop_governor"]["executes_action"])
        self.assertEqual(result["fencing_token"], 1)
        self.assertTrue(result["automatic_runtime_checkpoint_persistence"])
        self.assertFalse(result["automatic_external_business_actions"])
        self.assertFalse(result["provider_called"])
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["payment_executed"])
        self.assertFalse(result["publication_executed"])
        self.assertFalse(result["deploy_executed"])
        self.assertFalse(result["merge_executed"])
        self.assertFalse(result["real_trading_enabled"])
        self.assertEqual(len(captures), 2)
        self.assertEqual(captures[0]["expected_sha"], "sha-0")
        self.assertEqual(captures[1]["expected_sha"], "sha-1")

        final_checkpoint = captures[-1]["checkpoint"]
        receipts, _ = load_executor_receipts(self.context, final_checkpoint)
        self.assertEqual(len(receipts), 1)
        receipt = receipts[0]
        self.assertEqual(receipt["authorization_mode"], "GLOBAL_WORKER")
        self.assertEqual(receipt["human_principal"], "")
        self.assertEqual(receipt["delegated_actor"], "mikael")
        self.assertTrue(receipt["execution_principal"].startswith(SERVICE_PRINCIPAL + ":"))
        self.assertFalse(receipt["external_action_executed"])
        state, _ = load_global_worker_state(final_checkpoint)
        self.assertEqual(state["lease"]["owner"], "")
        self.assertEqual(state["fencing_counter"], 1)
        self.assertEqual(state["stats"]["ticks"], 1)
        self.assertEqual(state["stats"]["processed"], 1)

        executor = executor_snapshot(self.access, final_checkpoint, now=TICK)
        self.assertTrue(executor["global_worker_execution_observed"])
        self.assertFalse(executor["manual_invocation_only"])
        self.assertFalse(executor["autonomous_worker_connected"])

    def test_active_global_lease_blocks_other_runtime_without_write(self):
        checkpoint = self.armed_checkpoint()
        state, _ = load_global_worker_state(checkpoint)
        claimed, lease = _claim_state(state, runtime_id="gha-a", now=TICK)
        self.assertEqual(lease["state"], "CLAIMED")
        with_lease = attach_global_worker_state(checkpoint, claimed)
        with patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
            return_value={
                "status": "CONFIRMED",
                "checkpoint": with_lease,
                "sha": "sha-lease",
            },
        ), patch(
            "atlasquant_aion_global_worker._persist_runtime_checkpoint_cas"
        ) as persist:
            result = run_global_worker_once(
                config=_config(),
                runtime_id="gha-b",
                feature_enabled=True,
                now=TICK + timedelta(seconds=30),
            )
        persist.assert_not_called()
        self.assertEqual(result["status"], "INFLIGHT_RECONCILIATION_REQUIRED")
        self.assertEqual(result["inflight_owner"], "gha-a")
        self.assertTrue(result["reconciliation_required"])
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertEqual(result["processed"], 0)

    def test_release_requires_same_owner_token_and_fencing_token(self):
        checkpoint = self.armed_checkpoint()
        state, _ = load_global_worker_state(checkpoint)
        claimed, lease = _claim_state(state, runtime_id="gha-a", now=TICK)
        batch = {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "blocked": 0,
        }
        released = _release_state(
            claimed,
            runtime_id="gha-a",
            expected_lease_token=lease["token"],
            expected_fencing_token=lease["fencing_token"],
            now=TICK,
            batch=batch,
            final_status="OK",
        )
        self.assertEqual(released["lease"]["owner"], "")

        with self.assertRaisesRegex(ValueError, "GLOBAL_LEASE_TOKEN_MISMATCH"):
            _release_state(
                claimed,
                runtime_id="gha-a",
                expected_lease_token="wrong-token",
                expected_fencing_token=lease["fencing_token"],
                now=TICK,
                batch=batch,
                final_status="OK",
            )
        with self.assertRaisesRegex(ValueError, "GLOBAL_FENCING_TOKEN_MISMATCH"):
            _release_state(
                claimed,
                runtime_id="gha-a",
                expected_lease_token=lease["token"],
                expected_fencing_token=lease["fencing_token"] + 1,
                now=TICK,
                batch=batch,
                final_status="OK",
            )

    def test_global_runtime_id_fails_closed_for_ambiguous_values(self):
        self.assertEqual(_runtime_id(""), "")
        self.assertEqual(_runtime_id("   "), "")
        self.assertEqual(_runtime_id(True), "")
        self.assertEqual(_runtime_id("x" * 161), "")
        self.assertEqual(_runtime_id("gha-valid-1"), "gha-valid-1")

        with patch("atlasquant_aion_global_worker.load_runtime_checkpoint") as load:
            result = run_global_worker_once(
                config=_config(),
                runtime_id=True,
                feature_enabled=True,
                now=TICK,
            )
        load.assert_not_called()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "GLOBAL_RUNTIME_ID_REQUIRED")

    def test_release_fence_failure_blocks_final_persistence(self):
        checkpoint = self.armed_checkpoint()
        captures = []

        def tampering_executor(*args, **kwargs):
            staged = deepcopy(args[1])
            state, _ = load_global_worker_state(staged)
            state["lease"]["token"] = "tampered-token"
            state["inflight_tick"]["lease_token"] = "tampered-token"
            state["inflight_tick"]["intent_id"] = digest({
                "owner": state["inflight_tick"]["owner"],
                "lease_token": "tampered-token",
                "fencing_token": state["inflight_tick"]["fencing_token"],
                "claimed_at": state["inflight_tick"]["claimed_at"],
                "work_intent_digest": state["inflight_tick"].get("work_intent_digest", ""),
            })
            state["digest"] = global_worker_integrity(state)["expected"]
            return {
                "status": "COMPLETED",
                "checkpoint": attach_global_worker_state(staged, state),
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "blocked": 0,
            }

        with patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
            return_value={"status": "CONFIRMED", "checkpoint": checkpoint, "sha": "sha-0"},
        ), patch(
            "atlasquant_aion_global_worker._persist_runtime_checkpoint_cas",
            side_effect=self.fake_persist(captures),
        ) as persist, patch(
            "atlasquant_aion_global_worker._execute_due_local_work_authorized",
            side_effect=tampering_executor,
        ):
            result = run_global_worker_once(
                config=_config(),
                runtime_id="gha-fence-test",
                feature_enabled=True,
                now=TICK,
            )

        self.assertEqual(result["status"], "FENCE_RELEASE_FAILED")
        self.assertEqual(result["reason"], "GLOBAL_LEASE_TOKEN_MISMATCH")
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertEqual(persist.call_count, 1)

    def test_claim_persists_inflight_guard_and_release_clears_it(self):
        checkpoint = self.armed_checkpoint()
        state, _ = load_global_worker_state(checkpoint)
        claimed, lease = _claim_state(state, runtime_id="gha-inflight", now=TICK)
        self.assertTrue(claimed["inflight_tick"])
        self.assertEqual(claimed["inflight_tick"]["owner"], "gha-inflight")
        self.assertEqual(claimed["inflight_tick"]["lease_token"], lease["token"])
        self.assertEqual(claimed["inflight_tick"]["fencing_token"], lease["fencing_token"])

        released = _release_state(
            claimed,
            runtime_id="gha-inflight",
            expected_lease_token=lease["token"],
            expected_fencing_token=lease["fencing_token"],
            now=TICK,
            batch={"processed":0,"succeeded":0,"failed":0,"blocked":0},
            final_status="NO_DUE_WORK",
        )
        self.assertEqual(released["inflight_tick"], {})
        self.assertEqual(released["lease"]["owner"], "")

    def test_global_claim_persists_bounded_safe_work_intent(self):
        checkpoint = self.armed_checkpoint()
        captures = []
        with patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
            return_value={
                "status": "CONFIRMED",
                "checkpoint": checkpoint,
                "sha": "sha-0",
            },
        ), patch(
            "atlasquant_aion_global_worker._persist_runtime_checkpoint_cas",
            side_effect=self.fake_persist(captures),
        ):
            result = run_global_worker_once(
                config=_config(),
                runtime_id="gha-intent",
                feature_enabled=True,
                now=TICK,
            )

        self.assertEqual(result["status"], "CONFIRMED")
        self.assertEqual(result["work_intent_count"], 1)
        self.assertTrue(result["work_intent_digest"])
        claimed, _ = load_global_worker_state(captures[0]["checkpoint"])
        inflight = claimed["inflight_tick"]
        self.assertEqual(inflight["work_intent_count"], 1)
        self.assertEqual(len(inflight["work_occurrences"]), 1)
        row = inflight["work_occurrences"][0]
        self.assertTrue(row["schedule_id"])
        self.assertEqual(len(row["occurrence_key"]), 64)
        self.assertTrue(row["due_at"])
        self.assertEqual(row["capability"], "ADMINISTRATION")
        self.assertNotIn("prompt", row)
        self.assertNotIn("title", row)

    def test_unresolved_inflight_reports_exact_safe_work_manifest(self):
        checkpoint = self.armed_checkpoint()
        state, _ = load_global_worker_state(checkpoint)
        from atlasquant_aion_core_voice_automation import CheckpointAutomationAdapter
        from atlasquant_aion_background_executor import _occurrence_key
        snapshot = CheckpointAutomationAdapter(self.context, checkpoint).snapshot(TICK)
        due = [x for x in snapshot["schedules"] if x.get("due") is True]
        self.assertEqual(len(due), 1)
        row = due[0]
        work = {
            "as_of": TICK.isoformat(),
            "count": 1,
            "occurrences": [{
                "schedule_id": row["schedule_id"],
                "occurrence_key": _occurrence_key(
                    self.context,
                    row,
                    row["due_at"],
                ),
                "due_at": row["due_at"],
                "capability": row["capability"],
            }],
        }
        work["digest"] = digest({
            "as_of": work["as_of"],
            "count": work["count"],
            "occurrences": work["occurrences"],
        })
        claimed, _ = _claim_state(
            state,
            runtime_id="gha-crashed-intent",
            now=TICK,
            work_intent=work,
        )
        persisted_claim = attach_global_worker_state(checkpoint, claimed)

        with patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
            return_value={
                "status": "CONFIRMED",
                "checkpoint": persisted_claim,
                "sha": "sha-claim",
            },
        ), patch(
            "atlasquant_aion_global_worker._execute_due_local_work_authorized"
        ) as executor:
            result = run_global_worker_once(
                config=_config(),
                runtime_id="gha-next",
                feature_enabled=True,
                now=TICK + timedelta(seconds=601),
            )

        executor.assert_not_called()
        self.assertEqual(result["status"], "INFLIGHT_RECONCILIATION_REQUIRED")
        self.assertEqual(result["inflight_work_intent_count"], 1)
        self.assertEqual(
            result["inflight_work_intent_digest"],
            work["digest"],
        )
        self.assertEqual(
            result["inflight_work_occurrences"][0]["occurrence_key"],
            work["occurrences"][0]["occurrence_key"],
        )
        self.assertNotIn("prompt", result["inflight_work_occurrences"][0])
        self.assertNotIn("title", result["inflight_work_occurrences"][0])

    def test_unresolved_inflight_tick_blocks_reexecution_before_executor(self):
        checkpoint = self.armed_checkpoint()
        state, _ = load_global_worker_state(checkpoint)
        claimed, lease = _claim_state(state, runtime_id="gha-crashed", now=TICK)
        persisted_claim = attach_global_worker_state(checkpoint, claimed)

        with patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
            return_value={
                "status":"CONFIRMED",
                "checkpoint":persisted_claim,
                "sha":"sha-claim",
            },
        ), patch(
            "atlasquant_aion_global_worker._persist_runtime_checkpoint_cas"
        ) as persist, patch(
            "atlasquant_aion_global_worker._execute_due_local_work_authorized"
        ) as executor:
            result = run_global_worker_once(
                config=_config(),
                runtime_id="gha-next",
                feature_enabled=True,
                now=TICK + timedelta(seconds=601),
            )

        persist.assert_not_called()
        executor.assert_not_called()
        self.assertEqual(result["status"], "INFLIGHT_RECONCILIATION_REQUIRED")
        self.assertTrue(result["reconciliation_required"])
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertEqual(result["inflight_owner"], "gha-crashed")
        self.assertEqual(result["inflight_fencing_token"], lease["fencing_token"])

    def test_successful_global_tick_clears_inflight_guard_in_final_checkpoint(self):
        checkpoint = self.armed_checkpoint()
        captures=[]
        with patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
            return_value={"status":"CONFIRMED","checkpoint":checkpoint,"sha":"sha-0"},
        ), patch(
            "atlasquant_aion_global_worker._persist_runtime_checkpoint_cas",
            side_effect=self.fake_persist(captures),
        ):
            result = run_global_worker_once(
                config=_config(),
                runtime_id="gha-success",
                feature_enabled=True,
                now=TICK,
            )

        self.assertEqual(result["status"], "CONFIRMED")
        self.assertEqual(len(captures), 2)
        claimed_state, _ = load_global_worker_state(captures[0]["checkpoint"])
        final_state, _ = load_global_worker_state(captures[1]["checkpoint"])
        self.assertTrue(claimed_state["inflight_tick"])
        self.assertEqual(final_state["inflight_tick"], {})

    def test_expired_lease_reclaims_with_monotonic_fencing_token(self):
        checkpoint = self.armed_checkpoint()
        state, _ = load_global_worker_state(checkpoint)
        first, lease1 = _claim_state(state, runtime_id="gha-a", now=TICK)
        second, lease2 = _claim_state(
            first,
            runtime_id="gha-b",
            now=TICK + timedelta(seconds=601),
        )
        self.assertEqual(lease1["fencing_token"], 1)
        self.assertEqual(lease2["fencing_token"], 2)
        self.assertTrue(lease2["reclaimed"])
        self.assertEqual(second["fencing_counter"], 2)
        self.assertEqual(second["stats"]["crash_recoveries"], 1)


    def test_global_cas_unverified_write_returns_reconciliation_receipt(self):
        checkpoint = ensure_operating_checkpoint(self.armed_checkpoint())
        put = MagicMock()
        put.status_code = 200
        put.raise_for_status.return_value = None
        put.json.return_value = {"content": {"sha": "sha-new"}}
        with patch(
            "atlasquant_aion_global_worker.github_put",
            return_value=put,
        ) as put_call, patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
            return_value={"status": "ERROR", "checkpoint": None, "sha": ""},
        ):
            result = _persist_runtime_checkpoint_cas(
                checkpoint,
                _config(),
                expected_sha="sha-old",
                operation="claim global lease",
            )

        self.assertEqual(result["status"], "UNVERIFIED")
        self.assertFalse(result["saved"])
        self.assertFalse(result["verified"])
        self.assertTrue(result["reconciliation_required"])
        self.assertFalse(result["write_receipt"]["automatic_retry"])
        self.assertTrue(result["write_receipt"]["write_accepted"])
        self.assertEqual(result["write_receipt"]["write_sha"], "sha-new")
        self.assertEqual(result["write_receipt"]["expected_sha"], "sha-old")
        put_call.assert_called_once()

    def test_global_cas_transport_exception_is_ambiguous_and_never_retryable(self):
        checkpoint = ensure_operating_checkpoint(self.armed_checkpoint())
        with patch(
            "atlasquant_aion_global_worker.github_put",
            side_effect=TimeoutError("synthetic timeout"),
        ) as put_call:
            result = _persist_runtime_checkpoint_cas(
                checkpoint,
                _config(),
                expected_sha="sha-old",
                operation="persist global worker tick",
            )

        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["write_outcome"], "UNKNOWN")
        self.assertTrue(result["reconciliation_required"])
        self.assertFalse(result["write_receipt"]["automatic_retry"])
        self.assertIsNone(result["write_receipt"]["write_accepted"])
        put_call.assert_called_once()

    def test_unverified_lease_claim_blocks_executor_and_surfaces_no_retry(self):
        checkpoint = self.armed_checkpoint()
        with patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
            return_value={
                "status": "CONFIRMED",
                "checkpoint": checkpoint,
                "sha": "sha-0",
            },
        ), patch(
            "atlasquant_aion_global_worker._persist_runtime_checkpoint_cas",
            return_value={
                "status": "UNVERIFIED",
                "saved": False,
                "verified": False,
                "reconciliation_required": True,
                "write_receipt": {"automatic_retry": False},
            },
        ), patch(
            "atlasquant_aion_global_worker._execute_due_local_work_authorized"
        ) as executor:
            result = run_global_worker_once(
                config=_config(),
                runtime_id="gha-unverified",
                feature_enabled=True,
                now=TICK,
            )

        executor.assert_not_called()
        self.assertEqual(result["status"], "LEASE_CLAIM_UNVERIFIED")
        self.assertTrue(result["reconciliation_required"])
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertEqual(result["processed"], 0)

    def test_claim_cas_conflict_blocks_executor(self):
        checkpoint = self.armed_checkpoint()
        with patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
            return_value={
                "status": "CONFIRMED",
                "checkpoint": checkpoint,
                "sha": "sha-0",
            },
        ), patch(
            "atlasquant_aion_global_worker._persist_runtime_checkpoint_cas",
            return_value={
                "status": "CONFLICT",
                "saved": False,
                "verified": False,
            },
        ), patch(
            "atlasquant_aion_global_worker._execute_due_local_work_authorized"
        ) as executor:
            result = run_global_worker_once(
                config=_config(),
                runtime_id="gha-conflict",
                feature_enabled=True,
                now=TICK,
            )
        executor.assert_not_called()
        self.assertEqual(result["status"], "LEASE_CLAIM_CONFLICT")
        self.assertEqual(result["processed"], 0)

    def test_global_allowlist_blocks_voice_schedule_before_provider(self):
        checkpoint = self.armed_checkpoint(
            capability="VOICE",
            prompt="voz preparar resumo",
        )
        captures = []
        with patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
            return_value={"status": "CONFIRMED", "checkpoint": checkpoint, "sha": "sha-0"},
        ), patch(
            "atlasquant_aion_global_worker._persist_runtime_checkpoint_cas",
            side_effect=self.fake_persist(captures),
        ):
            result = run_global_worker_once(
                config=_config(),
                runtime_id="gha-voice",
                feature_enabled=True,
                now=TICK,
            )
        self.assertEqual(result["status"], "CONFIRMED")
        self.assertEqual(result["blocked"], 1)
        final = captures[-1]["checkpoint"]
        receipts, _ = load_executor_receipts(self.context, final)
        self.assertEqual(receipts[0]["state"], "BLOCKED")
        self.assertEqual(
            receipts[0]["reason"],
            "CAPABILITY_NOT_BACKGROUND_ALLOWLISTED",
        )
        self.assertFalse(receipts[0]["provider_called"])

    def test_sensitive_publication_is_blocked_in_global_mode(self):
        checkpoint = self.armed_checkpoint(
            capability="CONTENT",
            prompt="publique este conteúdo agora",
        )
        captures = []
        with patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
            return_value={"status": "CONFIRMED", "checkpoint": checkpoint, "sha": "sha-0"},
        ), patch(
            "atlasquant_aion_global_worker._persist_runtime_checkpoint_cas",
            side_effect=self.fake_persist(captures),
        ):
            result = run_global_worker_once(
                config=_config(),
                runtime_id="gha-content",
                feature_enabled=True,
                now=TICK,
            )
        self.assertEqual(result["blocked"], 1)
        receipts, _ = load_executor_receipts(
            self.context,
            captures[-1]["checkpoint"],
        )
        self.assertIn(
            "SENSITIVE_INTENT_REQUIRES_INTERACTIVE_APPROVAL",
            receipts[0]["reason"],
        )
        self.assertFalse(receipts[0]["external_action_executed"])

    def test_staged_pause_and_kill_require_checkpoint_save(self):
        armed = self.armed_checkpoint()
        paused = stage_pause_global_worker(
            self.access,
            armed,
            confirmation=True,
        )
        self.assertEqual(paused["status"], "STAGED_PAUSED")
        self.assertTrue(paused["requires_checkpoint_save"])
        state, _ = load_global_worker_state(paused["checkpoint"])
        self.assertEqual(state["state"], "PAUSED")

        killed = stage_kill_global_worker(
            self.access,
            armed,
            confirmation=True,
        )
        self.assertEqual(killed["status"], "STAGED_KILLED")
        self.assertTrue(killed["requires_checkpoint_save"])
        state, _ = load_global_worker_state(killed["checkpoint"])
        self.assertEqual(state["state"], "KILLED")
        self.assertTrue(state["kill_switch"])

    def test_persisted_kill_switch_prevents_claim_and_execution(self):
        checkpoint = stage_kill_global_worker(
            self.access,
            self.armed_checkpoint(),
            confirmation=True,
        )["checkpoint"]
        with patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
            return_value={"status": "CONFIRMED", "checkpoint": checkpoint, "sha": "sha-kill"},
        ), patch(
            "atlasquant_aion_global_worker._persist_runtime_checkpoint_cas"
        ) as persist:
            result = run_global_worker_once(
                config=_config(),
                runtime_id="gha-kill",
                feature_enabled=True,
                now=TICK,
            )
        persist.assert_not_called()
        self.assertEqual(result["status"], "KILLED")
        self.assertEqual(result["processed"], 0)

    def test_global_state_tamper_fails_master_integrity(self):
        checkpoint = self.armed_checkpoint()
        raw = checkpoint[GLOBAL_WORKER_NAMESPACE]
        self.assertEqual(global_worker_integrity(raw)["state"], "MATCH")
        tampered = deepcopy(checkpoint)
        tampered[GLOBAL_WORKER_NAMESPACE]["max_jobs"] = 19
        self.assertEqual(
            global_worker_integrity(tampered[GLOBAL_WORKER_NAMESPACE])["state"],
            "MISMATCH",
        )
        report = checkpoint_integrity_report(tampered)
        self.assertEqual(report["state"], "MISMATCH")
        self.assertIn("aion_global_worker", report["mismatches"])

    def test_global_namespace_survives_normalization_and_conflict_digest(self):
        base = ensure_operating_checkpoint(self.schedule())
        before = checkpoint_source_digest(base)
        armed = stage_arm_global_worker(
            self.access,
            base,
            confirmation=True,
            arming_approval=self.approval(
                base,
                max_jobs=5,
                lease_seconds=600,
            ),
            lease_seconds=600,
            now=CREATED,
        )["checkpoint"]
        normalized = ensure_operating_checkpoint(armed)
        self.assertIn(GLOBAL_WORKER_NAMESPACE, normalized)
        self.assertNotEqual(before, checkpoint_source_digest(normalized))

    def test_existing_autopilot_pulse_is_reused_without_new_cron(self):
        workflow = Path(".github/workflows/autopilot-v107.yml").read_text(
            encoding="utf-8"
        )
        self.assertEqual(workflow.count("cron:"), 1)
        self.assertIn('cron: "7,37 * * * *"', workflow)
        self.assertIn("AION Global Worker tick", workflow)
        self.assertIn(
            "vars.ATLASQUANT_AION_GLOBAL_WORKER_ENABLED == '1'",
            workflow,
        )
        self.assertIn("python atlasquant_aion_global_worker.py --tick", workflow)

    def test_admin_ui_stages_global_control_but_does_not_auto_save(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Worker Global/Durable V1 · control plane", source)
        self.assertIn("Cerimônia de Arming", source)
        self.assertIn("Gerar plano de Arming", source)
        self.assertIn("Criar autorização temporária", source)
        self.assertIn("Preparar ARMED (staged, sem salvar)", source)
        self.assertNotIn('"🌐 Armar Global (staged)"', source)
        self.assertIn("Pausar Global (staged)", source)
        self.assertIn("Kill Global (staged)", source)
        self.assertIn("NÃO foi salvo no runtime", source)
        self.assertIn("Salvar Checkpoint Mestre", source)

    def test_global_worker_has_no_physical_or_business_action_apis(self):
        source = Path("atlasquant_aion_global_worker.py").read_text(
            encoding="utf-8"
        )
        for banned in (
            "import subprocess",
            "from subprocess",
            "subprocess.",
            "os.system(",
            "generate_neural_speech(",
            "publish_social(",
            "publish_marketplace(",
            "charge_customer(",
            "deploy_production(",
            "merge_main(",
            "real_trade(",
        ):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
