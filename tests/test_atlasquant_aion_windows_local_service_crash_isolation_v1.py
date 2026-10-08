import base64
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_repository_mutation_local_runtime_hardening_v1 import (
    build_kill_switch_control_challenge,
    build_windows_owner_acl_attestation,
    resolve_windows_runtime_layout,
    verify_and_apply_signed_kill_switch_change,
)
from atlasquant_aion_repository_mutation_offline_runtime_v1 import (
    OfflineRuntimeError,
)
from atlasquant_aion_windows_local_service_crash_isolation_v1 import (
    HEALTH_PIPE_NAME,
    AtomicProcessLock,
    WindowsLocalServiceController,
    WindowsServiceRuntimeStore,
    build_windows_service_installation_blueprint,
    local_health_ipc_contract,
    windows_local_service_policy,
)


D = lambda c: "sha256:" + (c * 64)


class AionWindowsLocalServiceCrashIsolationV1Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "runtime.sqlite3"
        self.lock_path = self.root / "runtime.lock"
        self.store = WindowsServiceRuntimeStore(self.db)
        self.lock = AtomicProcessLock(self.lock_path)
        self.controller = WindowsLocalServiceController(
            store=self.store,
            lock=self.lock,
        )

        self.private_key = Ed25519PrivateKey.generate()
        raw_public = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.public_b64 = base64.b64encode(raw_public).decode("ascii")
        self.owner_binding = D("1")
        self.enrollment = self.store.enroll_owner_public_key_once(
            owner_subject="owner://mikael",
            owner_binding_digest=self.owner_binding,
            device_binding_digest=D("2"),
            public_key_b64=self.public_b64,
            enrollment_nonce_digest=D("3"),
            enrolled_at="2026-10-08T12:00:00+00:00",
            physical_owner_presence_verified=True,
            owner_only_acl_verified=True,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def start(self, instance_id="svc-instance-1", at="2026-10-08T12:01:00+00:00"):
        return self.controller.start_current_process(
            instance_id=instance_id,
            process_id=4242,
            process_start_digest=D("4"),
            owner_subject="owner://mikael",
            started_at=at,
        )

    def signed_open_kill_switch(
        self,
        *,
        action_id="svc-open-gate-1",
        nonce_digest=D("5"),
        issued_at="2026-10-08T12:01:05+00:00",
        expires_at="2026-10-08T12:02:00+00:00",
        now="2026-10-08T12:01:10+00:00",
    ):
        challenge = build_kill_switch_control_challenge(
            self.store,
            action_id=action_id,
            desired_enabled=False,
            reason="OWNER_REOPEN_AFTER_SERVICE_START",
            nonce_digest=nonce_digest,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        message = base64.b64decode(
            challenge["signature_message_b64"],
            validate=True,
        )
        signature = self.private_key.sign(message)
        return verify_and_apply_signed_kill_switch_change(
            self.store,
            challenge,
            signature_b64=base64.b64encode(signature).decode("ascii"),
            now=now,
        )

    def test_installation_blueprint_is_current_user_and_non_installing(self):
        layout = resolve_windows_runtime_layout(
            local_app_data=r"C:\Users\Mikael\AppData\Local",
            owner_subject="owner://mikael",
        )
        acl = build_windows_owner_acl_attestation(
            layout,
            owner_sid_digest=D("6"),
            acl_evidence_digest=D("7"),
            current_user_owner_match=True,
            owner_full_control_verified=True,
            inheritance_disabled_verified=True,
            broad_write_aces_absent=True,
            service_account_is_current_user=True,
        )
        plan = build_windows_service_installation_blueprint(
            layout,
            acl,
            package_digest=D("8"),
            code_signing_evidence_digest=D("9"),
            uninstall_plan_digest=D("a"),
            owner_key_enrollment_digest=self.enrollment["enrollment_digest"],
        )
        self.assertEqual(
            plan["state"],
            "WINDOWS_LOCAL_SERVICE_BLUEPRINT_READY",
            plan["blockers"],
        )
        self.assertEqual(plan["service_mode"], "CURRENT_USER_LOGON_AGENT")
        self.assertEqual(plan["process_identity"], "CURRENT_WINDOWS_USER")
        self.assertEqual(plan["startup_trigger"], "CURRENT_USER_LOGON")
        self.assertEqual(plan["health_transport"], "OWNER_ONLY_NAMED_PIPE")
        self.assertEqual(plan["health_pipe_name"], HEALTH_PIPE_NAME)
        self.assertFalse(plan["windows_service_installed"])
        self.assertFalse(plan["scheduled_task_installed"])
        self.assertFalse(plan["process_spawned"])
        self.assertFalse(plan["system_account_used"])
        self.assertFalse(plan["local_system_used"])
        self.assertFalse(plan["tcp_listener_enabled"])
        self.assertFalse(plan["http_listener_enabled"])
        self.assertFalse(plan["remote_control_enabled"])
        self.assertFalse(plan["firewall_rule_created"])
        self.assertFalse(plan["github_api_called"])
        self.assertFalse(plan["network_called"])

    def test_health_ipc_is_named_pipe_read_only_and_local_only(self):
        ipc = local_health_ipc_contract()
        self.assertEqual(ipc["transport"], "WINDOWS_NAMED_PIPE")
        self.assertEqual(ipc["pipe_name"], HEALTH_PIPE_NAME)
        self.assertEqual(
            ipc["allowed_operations"],
            ["GET_HEALTH", "GET_READINESS"],
        )
        self.assertTrue(ipc["owner_sid_acl_required"])
        self.assertTrue(ipc["current_user_only"])
        self.assertTrue(ipc["local_machine_only"])
        self.assertFalse(ipc["anonymous_access_allowed"])
        self.assertFalse(ipc["remote_pipe_access_allowed"])
        self.assertFalse(ipc["command_dispatch_allowed"])
        self.assertFalse(ipc["mutation_dispatch_allowed"])
        self.assertFalse(ipc["credential_exchange_allowed"])
        self.assertFalse(ipc["tcp_listener_enabled"])
        self.assertFalse(ipc["http_listener_enabled"])
        self.assertFalse(ipc["socket_opened_by_this_module"])
        self.assertFalse(ipc["pipe_opened_by_this_module"])

    def test_startup_forces_kill_switch_enabled_even_if_previously_open(self):
        self.store.set_kill_switch(
            enabled=False,
            reason="TEST_HARNESS_PREOPENED",
            updated_at="2026-10-08T12:00:30+00:00",
        )
        started = self.start()
        self.assertEqual(
            started["state"],
            "LOCAL_SERVICE_PROCESS_RUNNING_FAIL_CLOSED",
        )
        self.assertTrue(started["kill_switch"]["enabled"])
        self.assertEqual(
            started["kill_switch"]["reason"],
            "SERVICE_STARTUP_FAIL_CLOSED",
        )
        self.assertFalse(started["mutation_gate_open"])
        self.assertFalse(started["process_spawned_by_this_module"])
        self.assertFalse(started["windows_service_installed"])
        self.assertFalse(started["scheduled_task_installed"])
        self.assertFalse(started["github_api_called"])
        self.assertFalse(started["network_called"])
        self.assertTrue(self.lock_path.exists())

    def test_signed_owner_reopen_is_required_after_start_for_readiness(self):
        self.start()
        initial = self.controller.health_snapshot(
            instance_id="svc-instance-1",
            now="2026-10-08T12:01:05+00:00",
        )
        self.assertEqual(initial["state"], "HEALTHY")
        self.assertTrue(initial["process_healthy"])
        self.assertFalse(initial["mutation_runtime_ready"])
        self.assertTrue(initial["kill_switch_enabled"])

        opened = self.signed_open_kill_switch()
        self.assertFalse(opened["kill_switch_status"]["enabled"])

        ready = self.controller.health_snapshot(
            instance_id="svc-instance-1",
            now="2026-10-08T12:01:15+00:00",
        )
        self.assertTrue(ready["process_healthy"])
        self.assertTrue(ready["mutation_runtime_ready"])
        self.assertFalse(ready["kill_switch_enabled"])
        self.assertFalse(ready["tcp_listener_enabled"])
        self.assertFalse(ready["http_listener_enabled"])
        self.assertFalse(ready["network_called"])

    def test_atomic_process_lock_allows_exactly_one_concurrent_winner(self):
        lock_path = self.root / "race.lock"

        def acquire(index):
            lock = AtomicProcessLock(lock_path)
            try:
                row = lock.acquire(
                    instance_id=f"race-instance-{index}",
                    process_id=5000 + index,
                    process_start_digest=D("b"),
                    owner_subject="owner://mikael",
                    acquired_at="2026-10-08T12:00:00+00:00",
                )
                return ("SUCCESS", row)
            except OfflineRuntimeError as exc:
                return (exc.code, None)

        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(acquire, range(32)))

        successes = [row for code, row in results if code == "SUCCESS"]
        failures = [code for code, _ in results if code != "SUCCESS"]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 31)
        self.assertTrue(
            all(code == "PROCESS_SINGLETON_LOCK_ALREADY_HELD" for code in failures)
        )
        stored = AtomicProcessLock(lock_path).read()
        self.assertEqual(stored["lock_digest"], successes[0]["lock_digest"])

    def test_second_service_instance_is_blocked_by_singleton_lock(self):
        self.start()
        second = WindowsLocalServiceController(
            store=self.store,
            lock=AtomicProcessLock(self.lock_path),
        )
        with self.assertRaises(OfflineRuntimeError) as ctx:
            second.start_current_process(
                instance_id="svc-instance-2",
                process_id=4343,
                process_start_digest=D("c"),
                owner_subject="owner://mikael",
                started_at="2026-10-08T12:01:01+00:00",
            )
        self.assertEqual(
            ctx.exception.code,
            "PROCESS_SINGLETON_LOCK_ALREADY_HELD",
        )
        self.assertEqual(len(self.store.active_instances()), 1)

    def test_lock_metadata_tampering_is_detected(self):
        started = self.start()
        row = json.loads(self.lock_path.read_text(encoding="utf-8"))
        row["process_id"] = 9999
        self.lock_path.write_text(json.dumps(row), encoding="utf-8")
        with self.assertRaises(OfflineRuntimeError) as ctx:
            self.lock.read()
        self.assertEqual(ctx.exception.code, "PROCESS_LOCK_DIGEST_MISMATCH")
        self.assertTrue(started["kill_switch"]["enabled"])

    def test_heartbeat_becomes_stale_but_lock_is_not_auto_removed(self):
        self.start()
        current = self.controller.inspect_crash_candidate(
            instance_id="svc-instance-1",
            now="2026-10-08T12:01:20+00:00",
        )
        self.assertEqual(current["state"], "PROCESS_HEARTBEAT_CURRENT")
        self.assertFalse(current["heartbeat_stale"])
        self.assertTrue(self.lock_path.exists())

        stale = self.controller.inspect_crash_candidate(
            instance_id="svc-instance-1",
            now="2026-10-08T12:02:00+00:00",
        )
        self.assertEqual(
            stale["state"],
            "PROCESS_LIVENESS_ATTESTATION_REQUIRED",
        )
        self.assertTrue(stale["heartbeat_stale"])
        self.assertFalse(stale["process_not_running_verified"])
        self.assertFalse(stale["stale_lock_removed"])
        self.assertFalse(stale["automatic_lock_recovery_allowed"])
        self.assertTrue(stale["kill_switch"]["enabled"])
        self.assertTrue(self.lock_path.exists())
        instance = self.store.get_instance("svc-instance-1")
        self.assertEqual(instance["state"], "CRASH_RECOVERY_REQUIRED")

    def test_stale_lock_recovery_requires_dead_process_and_owner_session_evidence(self):
        self.start()
        stale = self.controller.inspect_crash_candidate(
            instance_id="svc-instance-1",
            now="2026-10-08T12:02:00+00:00",
        )

        with self.assertRaises(OfflineRuntimeError) as ctx:
            self.controller.recover_verified_dead_process(
                candidate=stale,
                recovery_id="recovery-1",
                process_not_running_evidence_digest=D("d"),
                owner_session_evidence_digest=D("e"),
                process_not_running_verified=False,
                owner_session_match_verified=True,
                recovered_at="2026-10-08T12:02:05+00:00",
            )
        self.assertEqual(
            ctx.exception.code,
            "PROCESS_NOT_RUNNING_VERIFICATION_REQUIRED",
        )
        self.assertTrue(self.lock_path.exists())

        recovered = self.controller.recover_verified_dead_process(
            candidate=stale,
            recovery_id="recovery-1",
            process_not_running_evidence_digest=D("d"),
            owner_session_evidence_digest=D("e"),
            process_not_running_verified=True,
            owner_session_match_verified=True,
            recovered_at="2026-10-08T12:02:05+00:00",
        )
        self.assertEqual(
            recovered["state"],
            "VERIFIED_DEAD_PROCESS_LOCK_RECOVERED",
        )
        self.assertTrue(recovered["stale_lock_removed"])
        self.assertFalse(self.lock_path.exists())
        self.assertTrue(recovered["kill_switch"]["enabled"])
        self.assertFalse(recovered["automatic_restart_authorized"])
        self.assertFalse(recovered["mutation_gate_open"])
        self.assertFalse(recovered["live_repository_mutation_authorized"])
        self.assertFalse(recovered["live_repository_mutation_performed"])
        instance = self.store.get_instance("svc-instance-1")
        self.assertEqual(instance["state"], "CRASHED_RECOVERED")

    def test_new_process_can_start_only_after_verified_stale_recovery(self):
        self.start()
        stale = self.controller.inspect_crash_candidate(
            instance_id="svc-instance-1",
            now="2026-10-08T12:02:00+00:00",
        )
        self.controller.recover_verified_dead_process(
            candidate=stale,
            recovery_id="recovery-2",
            process_not_running_evidence_digest=D("f"),
            owner_session_evidence_digest=D("a"),
            process_not_running_verified=True,
            owner_session_match_verified=True,
            recovered_at="2026-10-08T12:02:05+00:00",
        )
        second = self.controller.start_current_process(
            instance_id="svc-instance-2",
            process_id=5252,
            process_start_digest=D("c"),
            owner_subject="owner://mikael",
            started_at="2026-10-08T12:02:10+00:00",
        )
        self.assertEqual(
            second["state"],
            "LOCAL_SERVICE_PROCESS_RUNNING_FAIL_CLOSED",
        )
        self.assertTrue(second["kill_switch"]["enabled"])
        self.assertFalse(second["mutation_gate_open"])
        self.assertEqual(
            self.store.get_instance("svc-instance-2")["state"],
            "RUNNING",
        )

    def test_clean_shutdown_enables_kill_switch_and_releases_lock(self):
        self.start()
        self.signed_open_kill_switch()
        stopped = self.controller.clean_shutdown(
            instance_id="svc-instance-1",
            shutdown_at="2026-10-08T12:01:30+00:00",
        )
        self.assertEqual(
            stopped["state"],
            "LOCAL_SERVICE_PROCESS_STOPPED_CLEANLY",
        )
        self.assertTrue(stopped["kill_switch"]["enabled"])
        self.assertEqual(
            stopped["kill_switch"]["reason"],
            "SERVICE_SHUTDOWN_FAIL_CLOSED",
        )
        self.assertTrue(stopped["lock_released"])
        self.assertFalse(self.lock_path.exists())
        self.assertFalse(stopped["automatic_restart_authorized"])
        self.assertEqual(
            self.store.get_instance("svc-instance-1")["state"],
            "STOPPED",
        )

    def test_stale_heartbeat_health_is_degraded_and_never_mutation_ready(self):
        self.start()
        self.signed_open_kill_switch()
        health = self.controller.health_snapshot(
            instance_id="svc-instance-1",
            now="2026-10-08T12:02:00+00:00",
        )
        self.assertEqual(health["state"], "DEGRADED")
        self.assertIn("HEARTBEAT_STALE", health["blockers"])
        self.assertFalse(health["process_healthy"])
        self.assertFalse(health["mutation_runtime_ready"])

    def test_heartbeat_refresh_restores_process_health_not_authority(self):
        self.start()
        self.controller.heartbeat(
            instance_id="svc-instance-1",
            heartbeat_at="2026-10-08T12:01:20+00:00",
        )
        health = self.controller.health_snapshot(
            instance_id="svc-instance-1",
            now="2026-10-08T12:01:25+00:00",
        )
        self.assertTrue(health["process_healthy"])
        self.assertFalse(health["mutation_runtime_ready"])
        self.assertTrue(health["kill_switch_enabled"])

    def test_policy_remains_local_fail_closed_and_noninstalling(self):
        policy = windows_local_service_policy()
        self.assertEqual(policy["service_mode"], "CURRENT_USER_LOGON_AGENT")
        self.assertTrue(policy["current_user_only"])
        self.assertFalse(policy["system_account_allowed"])
        self.assertFalse(policy["local_system_allowed"])
        self.assertFalse(policy["runtime_admin_elevation_required"])
        self.assertTrue(policy["singleton_process_required"])
        self.assertTrue(policy["atomic_lock_file_implemented"])
        self.assertFalse(policy["lock_file_auto_deleted_when_stale"])
        self.assertTrue(
            policy["stale_lock_requires_process_liveness_attestation"]
        )
        self.assertTrue(policy["stale_lock_requires_owner_session_match"])
        self.assertTrue(policy["kill_switch_forced_enabled_on_startup"])
        self.assertTrue(policy["kill_switch_forced_enabled_on_shutdown"])
        self.assertTrue(policy["kill_switch_forced_enabled_on_crash_recovery"])
        self.assertTrue(policy["signed_owner_reopen_required_after_restart"])
        self.assertTrue(policy["heartbeat_implemented"])
        self.assertTrue(policy["health_is_read_only"])
        self.assertFalse(policy["tcp_listener_enabled"])
        self.assertFalse(policy["http_listener_enabled"])
        self.assertFalse(policy["remote_control_enabled"])
        self.assertFalse(policy["lan_control_enabled"])
        self.assertFalse(policy["anonymous_ipc_access_allowed"])
        self.assertFalse(policy["command_dispatch_over_health_ipc_allowed"])
        self.assertFalse(
            policy["repository_mutation_dispatch_over_health_ipc_allowed"]
        )
        self.assertFalse(policy["credential_exchange_over_health_ipc_allowed"])
        self.assertFalse(policy["windows_service_installed"])
        self.assertFalse(policy["scheduled_task_installed"])
        self.assertFalse(policy["process_spawned_by_this_module"])
        self.assertFalse(policy["real_windows_acl_modified_by_this_module"])
        self.assertFalse(policy["crash_recovery_is_automatic_retry"])
        self.assertFalse(policy["automatic_restart_authorized"])
        self.assertFalse(policy["automatic_retry_allowed"])
        self.assertFalse(policy["repository_mutation_replay_allowed"])
        self.assertFalse(policy["consumed_authorization_auto_released"])
        self.assertFalse(policy["owner_private_key_loaded"])
        self.assertFalse(policy["real_github_credentials_loaded"])
        self.assertFalse(policy["github_api_called"])
        self.assertFalse(policy["network_called"])
        self.assertFalse(policy["live_repository_mutation_authorized"])
        self.assertFalse(policy["live_repository_mutation_performed"])
        self.assertFalse(policy["production_repository_mutation_performed"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["worker_activated"])
        self.assertFalse(policy["provider_activated"])
        self.assertFalse(policy["production_persistence_activated"])


if __name__ == "__main__":
    unittest.main()
