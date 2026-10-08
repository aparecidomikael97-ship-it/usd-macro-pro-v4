import copy
import unittest

from atlasquant_aion_secure_desktop_runtime_blueprint_v1 import (
    AGENT_MODEL,
    INSTALLED_ATTESTATION_SCHEMA,
    REQUIRED_COMPONENTS,
    build_desktop_runtime_plan,
    desktop_runtime_blueprint,
    evaluate_installed_runtime_attestation,
    pc_implementation_sequence,
    secure_desktop_runtime_policy,
    verify_desktop_runtime_plan,
)


def sha(char):
    return "sha256:" + (char * 64)


class AionSecureDesktopRuntimeBlueprintV1Tests(unittest.TestCase):
    def plan_input(self, **changes):
        value = {
            "platform": "WINDOWS",
            "agent_model": "PER_USER_DESKTOP_AGENT",
            "runtime_identity": "CURRENT_USER",
            "startup_mode": "USER_LOGIN",
            "bridge_strategy": "LOOPBACK_BRIDGE",
            "internal_ipc": "WINDOWS_NAMED_PIPE",
            "protocol_version": "1",
            "update_mode": "SIGNED_MANUAL_UPDATE",
            "local_secret_storage": "WINDOWS_DPAPI_CURRENT_USER",
            "owner_verification_mechanisms": ["WINDOWS_HELLO", "FIDO2"],
            "components": list(REQUIRED_COMPONENTS),
            "bridge_local_only": True,
            "bridge_origin_or_signed_envelope_validation": True,
            "exact_protocol_version_required": True,
            "internal_ipc_acl_current_user_only": True,
            "signed_binary_required": True,
            "code_signing_chain_verification_required": True,
            "binary_digest_verification_required": True,
            "fresh_owner_verification_required": True,
            "durable_single_use_replay_registry_required": True,
            "logical_app_allowlist_only": True,
            "postcondition_observer_required": True,
            "append_only_audit_journal_required": True,
            "audit_receipt_contract_required": True,
            "update_signature_verification_required": True,
            "kill_switch_required": True,
            "uninstall_path_required": True,
            "rollback_plan_required": True,
            "crash_recovery_plan_required": True,
            "least_privilege_required": True,
            "remote_listener_enabled": False,
            "lan_listener_enabled": False,
            "runs_as_system": False,
            "runtime_elevation_required": False,
            "arbitrary_executable_paths_allowed": False,
            "shell_execution_allowed": False,
            "command_line_execution_allowed": False,
            "credential_export_allowed": False,
            "raw_process_output_export_allowed": False,
            "automatic_unknown_retry_allowed": False,
            "automatic_unknown_reconciliation_allowed": False,
            "loopback_bind_only": True,
            "strict_origin_allowlist_required": True,
            "signed_envelope_required": False,
        }
        value.update(changes)
        return value

    def ready_plan(self):
        plan = build_desktop_runtime_plan(self.plan_input())
        self.assertEqual(plan["state"], "READY_FOR_PC_IMPLEMENTATION")
        self.assertEqual(plan["blockers"], [])
        return plan

    def installed_attestation(self, plan, **changes):
        value = {
            "schema": INSTALLED_ATTESTATION_SCHEMA,
            "verified": True,
            "plan_digest": plan["plan_digest"],
            "platform": "WINDOWS",
            "agent_model": "PER_USER_DESKTOP_AGENT",
            "runtime_identity": "CURRENT_USER",
            "bridge_strategy": plan["bridge_strategy"],
            "protocol_version": "1",
            "binary_digest": sha("a"),
            "evidence_bundle_digest": sha("b"),
            "attestor_identity": "atlasquant-pc-runtime-auditor",
            "attestor_signature_verified": True,
            "code_signature_verified": True,
            "publisher_identity": "AtlasQuant Owner Runtime",
            "runs_as_system": False,
            "runtime_elevated": False,
            "remote_listener_present": False,
            "lan_listener_present": False,
            "local_channel_access_control_verified": True,
            "loopback_only_verified": True,
            "strict_origin_allowlist_verified": True,
            "owner_verification_bridge_verified": True,
            "durable_replay_registry_verified": True,
            "single_use_nonce_rejection_verified": True,
            "allowlist_resolver_verified": True,
            "arbitrary_path_launch_possible": False,
            "shell_execution_possible": False,
            "append_only_audit_journal_verified": True,
            "receipt_pipeline_verified": True,
            "kill_switch_verified": True,
            "uninstall_path_verified": True,
            "rollback_path_verified": True,
            "signed_update_verification_verified": True,
        }
        value.update(changes)
        return value

    def test_blueprint_prefers_per_user_windows_agent(self):
        blueprint = desktop_runtime_blueprint()
        self.assertEqual(blueprint["platform"], "WINDOWS")
        self.assertEqual(blueprint["agent_model"], AGENT_MODEL)
        self.assertEqual(blueprint["runtime_identity"], "CURRENT_USER")
        self.assertFalse(blueprint["runs_as_system"])
        self.assertFalse(blueprint["requires_runtime_elevation"])
        self.assertFalse(blueprint["remote_listener_allowed"])
        self.assertFalse(blueprint["lan_listener_allowed"])
        self.assertFalse(blueprint["physical_install_started"])
        self.assertFalse(blueprint["runtime_process_started"])
        self.assertFalse(blueprint["executes_action"])

    def test_secure_plan_is_ready_for_pc_implementation_only(self):
        plan = self.ready_plan()
        verified = verify_desktop_runtime_plan(plan)
        self.assertTrue(verified["valid"])
        self.assertFalse(plan["physical_install_started"])
        self.assertFalse(plan["runtime_process_started"])
        self.assertFalse(plan["startup_entry_created"])
        self.assertFalse(plan["ipc_endpoint_created"])
        self.assertFalse(plan["application_launched"])
        self.assertFalse(plan["network_called"])
        self.assertFalse(plan["deploy_executed"])
        self.assertFalse(plan["core_checkpoint_write"])
        self.assertFalse(plan["executes_action"])

    def test_system_or_elevated_runtime_is_blocked(self):
        system_plan = build_desktop_runtime_plan(
            self.plan_input(
                runtime_identity="SYSTEM",
                runs_as_system=True,
            )
        )
        self.assertEqual(system_plan["state"], "BLOCKED")
        self.assertIn(
            "CURRENT_USER_RUNTIME_REQUIRED",
            system_plan["blockers"],
        )
        self.assertIn(
            "FORBIDDEN_CONTROL_ENABLED_OR_UNSET:runs_as_system",
            system_plan["blockers"],
        )

        elevated = build_desktop_runtime_plan(
            self.plan_input(runtime_elevation_required=True)
        )
        self.assertEqual(elevated["state"], "BLOCKED")
        self.assertIn(
            "FORBIDDEN_CONTROL_ENABLED_OR_UNSET:runtime_elevation_required",
            elevated["blockers"],
        )

    def test_remote_or_lan_listener_is_blocked(self):
        plan = build_desktop_runtime_plan(
            self.plan_input(
                remote_listener_enabled=True,
                lan_listener_enabled=True,
            )
        )
        self.assertEqual(plan["state"], "BLOCKED")
        self.assertIn(
            "FORBIDDEN_CONTROL_ENABLED_OR_UNSET:remote_listener_enabled",
            plan["blockers"],
        )
        self.assertIn(
            "FORBIDDEN_CONTROL_ENABLED_OR_UNSET:lan_listener_enabled",
            plan["blockers"],
        )

    def test_missing_security_component_blocks_plan(self):
        components = [
            item for item in REQUIRED_COMPONENTS
            if item != "REPLAY_REGISTRY"
        ]
        plan = build_desktop_runtime_plan(
            self.plan_input(components=components)
        )
        self.assertEqual(plan["state"], "BLOCKED")
        self.assertIn(
            "REQUIRED_COMPONENT_MISSING:REPLAY_REGISTRY",
            plan["blockers"],
        )

    def test_shell_and_arbitrary_path_authority_are_blocked(self):
        plan = build_desktop_runtime_plan(
            self.plan_input(
                arbitrary_executable_paths_allowed=True,
                shell_execution_allowed=True,
                command_line_execution_allowed=True,
            )
        )
        self.assertEqual(plan["state"], "BLOCKED")
        self.assertIn(
            "FORBIDDEN_CONTROL_ENABLED_OR_UNSET:arbitrary_executable_paths_allowed",
            plan["blockers"],
        )
        self.assertIn(
            "FORBIDDEN_CONTROL_ENABLED_OR_UNSET:shell_execution_allowed",
            plan["blockers"],
        )
        self.assertIn(
            "FORBIDDEN_CONTROL_ENABLED_OR_UNSET:command_line_execution_allowed",
            plan["blockers"],
        )

    def test_plan_digest_detects_tampering(self):
        plan = self.ready_plan()
        tampered = copy.deepcopy(plan)
        tampered["bridge_strategy"] = "NATIVE_SHELL_IPC"
        verified = verify_desktop_runtime_plan(tampered)
        self.assertFalse(verified["valid"])
        self.assertIn("PLAN_DIGEST_MISMATCH", verified["blockers"])

    def test_pc_sequence_is_ordered_and_generates_no_commands(self):
        sequence = pc_implementation_sequence(self.ready_plan())
        self.assertEqual(
            sequence["state"],
            "PC_IMPLEMENTATION_SEQUENCE_READY",
        )
        self.assertTrue(sequence["requires_pc"])
        self.assertEqual(len(sequence["steps"]), 10)
        self.assertEqual(
            [step["order"] for step in sequence["steps"]],
            list(range(1, 11)),
        )
        self.assertTrue(
            all(step["requires_pc"] for step in sequence["steps"])
        )
        self.assertFalse(sequence["commands_generated"])
        self.assertFalse(sequence["installer_generated"])
        self.assertFalse(sequence["physical_install_started"])
        self.assertFalse(sequence["executes_action"])

    def test_future_installed_runtime_attestation_can_be_validated(self):
        plan = self.ready_plan()
        result = evaluate_installed_runtime_attestation(
            plan,
            self.installed_attestation(plan),
        )
        self.assertTrue(result["valid"])
        self.assertEqual(
            result["state"],
            "INSTALLED_RUNTIME_ATTESTATION_VALID",
        )
        self.assertEqual(result["binary_digest"], sha("a"))
        self.assertEqual(result["evidence_bundle_digest"], sha("b"))
        self.assertFalse(result["evidence_gathered_by_this_module"])
        self.assertFalse(result["installation_performed_by_this_module"])
        self.assertFalse(result["runtime_started_by_this_module"])
        self.assertFalse(result["external_action_executed_by_this_module"])
        self.assertFalse(result["executes_action"])

    def test_unsigned_or_remote_installed_runtime_fails_closed(self):
        plan = self.ready_plan()
        result = evaluate_installed_runtime_attestation(
            plan,
            self.installed_attestation(
                plan,
                code_signature_verified=False,
                attestor_signature_verified=False,
                remote_listener_present=True,
                runs_as_system=True,
            ),
        )
        self.assertFalse(result["valid"])
        self.assertIn(
            "INSTALLED_CODE_SIGNATURE_NOT_VERIFIED",
            result["blockers"],
        )
        self.assertIn(
            "INSTALLED_ATTESTOR_SIGNATURE_NOT_VERIFIED",
            result["blockers"],
        )
        self.assertIn(
            "INSTALLED_REMOTE_LISTENER_FORBIDDEN",
            result["blockers"],
        )
        self.assertIn(
            "INSTALLED_SYSTEM_RUNTIME_FORBIDDEN",
            result["blockers"],
        )

    def test_loopback_bridge_requires_local_and_origin_controls(self):
        plan = build_desktop_runtime_plan(
            self.plan_input(
                loopback_bind_only=False,
                strict_origin_allowlist_required=False,
            )
        )
        self.assertEqual(plan["state"], "BLOCKED")
        self.assertIn(
            "LOOPBACK_BIND_ONLY_REQUIRED",
            plan["blockers"],
        )
        self.assertIn(
            "STRICT_ORIGIN_ALLOWLIST_REQUIRED",
            plan["blockers"],
        )

    def test_runtime_policy_preserves_least_privilege(self):
        policy = secure_desktop_runtime_policy()
        self.assertTrue(policy["per_user_agent_required"])
        self.assertFalse(policy["system_service_v1"])
        self.assertFalse(policy["runtime_elevation"])
        self.assertFalse(policy["remote_listener"])
        self.assertFalse(policy["lan_listener"])
        self.assertTrue(policy["local_bridge_security_required"])
        self.assertTrue(policy["code_signing_required"])
        self.assertTrue(
            policy["durable_single_use_replay_registry_required"]
        )
        self.assertTrue(policy["logical_app_allowlist_only"])
        self.assertFalse(policy["arbitrary_executable_paths"])
        self.assertFalse(policy["shell_execution"])
        self.assertFalse(policy["command_line_execution"])
        self.assertTrue(policy["append_only_audit_journal_required"])
        self.assertTrue(policy["outcome_receipt_required"])
        self.assertFalse(policy["automatic_unknown_retry"])
        self.assertTrue(policy["kill_switch_required"])
        self.assertTrue(policy["uninstall_required"])
        self.assertTrue(policy["rollback_required"])
        self.assertFalse(policy["physical_install_started"])
        self.assertFalse(policy["runtime_started"])
        self.assertFalse(policy["application_launched"])
        self.assertFalse(policy["network_called"])
        self.assertFalse(policy["worker_armed"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["core_checkpoint_write"])
        self.assertFalse(policy["executes_action"])


if __name__ == "__main__":
    unittest.main()
