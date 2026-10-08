import copy
import unittest

from atlasquant_aion_owner_experience_v1 import (
    SCHEMA as OWNER_EXPERIENCE_SCHEMA,
    command_plan,
)
from atlasquant_aion_secure_local_agent_v1 import (
    APP_REGISTRY,
    build_local_action_request,
    evaluate_dispatch_readiness,
    local_app_registry,
    secure_local_agent_policy,
    verify_local_action_request,
)


BINDING_DIGEST = "sha256:" + ("a" * 64)
ISSUED = "2026-10-08T09:50:00+00:00"
EXPIRES = "2026-10-08T09:50:30+00:00"
CURRENT = "2026-10-08T09:50:10+00:00"


class AionSecureLocalAgentV1Tests(unittest.TestCase):
    def owner_plan(self, message, *, device="desktop"):
        return command_plan(message, device=device, owner_bound=True)

    def request(self, message="AION, abre o ChatGPT", **changes):
        plan = changes.pop("owner_plan", self.owner_plan(message))
        values = {
            "command_text": message,
            "owner_subject": "mikael",
            "owner_binding_digest": BINDING_DIGEST,
            "command_id": "cmd-owner-1",
            "command_nonce": "nonce-owner-1",
            "device_id": "windows-owner-desktop-1",
            "platform": "WINDOWS",
            "issued_at": ISSUED,
            "expires_at": EXPIRES,
        }
        values.update(changes)
        return build_local_action_request(plan, **values)

    def host_attestation(self, request, **changes):
        value = {
            "verified": True,
            "source": "TRUSTED_OWNER_DESKTOP_HOST",
            "mechanism": "WINDOWS_HELLO",
            "fresh_owner_command": True,
            "generic_chat_acknowledgement": False,
            "owner_subject": request["owner_subject"],
            "owner_binding_digest": request["owner_binding_digest"],
            "request_digest": request["request_digest"],
            "command_nonce_digest": request["command_nonce_digest"],
            "cryptographic_verification_performed": True,
        }
        value.update(changes)
        return value

    def replay_attestation(self, request, **changes):
        value = {
            "verified": True,
            "request_digest": request["request_digest"],
            "command_nonce_digest": request["command_nonce_digest"],
            "fresh": True,
            "single_use_claimed": True,
            "durable_replay_rejection": True,
        }
        value.update(changes)
        return value

    def test_registry_contains_only_logical_allowlisted_apps(self):
        registry = local_app_registry()
        self.assertEqual(set(registry["apps"]), {"chatgpt", "whatsapp", "spotify"})
        self.assertEqual(set(registry["apps"]), set(APP_REGISTRY))
        for app in registry["apps"].values():
            self.assertFalse(app["physical_binding_included"])
            self.assertFalse(app["executable_path_included"])
            self.assertFalse(app["launch_command_included"])
            self.assertFalse(app["url_handler_included"])
        self.assertFalse(registry["physical_binding_included"])
        self.assertFalse(registry["executes_action"])

    def test_owner_commands_become_bounded_logical_requests(self):
        cases = (
            ("AION, abre o ChatGPT", "chatgpt", "CHATGPT"),
            ("AION, abre WhatsApp", "whatsapp", "WHATSAPP"),
            ("AION, abre Spotify", "spotify", "SPOTIFY"),
        )
        for index, (message, target, logical_id) in enumerate(cases, start=1):
            with self.subTest(message=message):
                request = self.request(
                    message,
                    command_id=f"cmd-{index}",
                    command_nonce=f"nonce-{index}",
                )
                self.assertEqual(request["state"], "REQUEST_READY")
                self.assertEqual(request["target"], target)
                self.assertEqual(request["actions"][0]["action"], "OPEN_APP")
                self.assertEqual(
                    request["actions"][0]["logical_app_id"],
                    logical_id,
                )
                self.assertTrue(request["requires_trusted_host_authorization"])
                self.assertTrue(request["requires_replay_guard"])
                self.assertTrue(request["requires_single_use_nonce"])
                self.assertFalse(request["physical_binding_included"])
                self.assertFalse(request["executable_path_included"])
                self.assertFalse(request["launch_command_included"])
                self.assertFalse(request["dispatch_ready"])
                self.assertFalse(request["physical_execution_performed"])

    def test_spotify_media_playback_is_data_not_command_line(self):
        request = self.request(
            "AION, abre Spotify e toca sertanejo",
            command_id="cmd-spotify",
            command_nonce="nonce-spotify",
        )
        self.assertEqual(request["state"], "REQUEST_READY")
        self.assertEqual(
            [item["action"] for item in request["actions"]],
            ["OPEN_APP", "MEDIA_PLAYBACK"],
        )
        self.assertEqual(
            request["actions"][1]["parameters"]["query"],
            "sertanejo",
        )
        self.assertNotIn("command", request["actions"][1])
        self.assertNotIn("path", request["actions"][1])
        self.assertFalse(request["execution_command_generated"])

    def test_mobile_external_app_plan_is_blocked(self):
        plan = self.owner_plan("AION, abre o ChatGPT", device="mobile")
        self.assertFalse(plan["device_supported"])
        request = self.request(
            "AION, abre o ChatGPT",
            owner_plan=plan,
        )
        self.assertEqual(request["state"], "BLOCKED")
        self.assertIn("DESKTOP_DEVICE_REQUIRED", request["blockers"])
        self.assertFalse(request["dispatch_ready"])

    def test_arbitrary_app_is_not_allowlisted(self):
        plan = {
            "schema": OWNER_EXPERIENCE_SCHEMA,
            "state": "PLANNED",
            "kind": "LOCAL_APPLICATION",
            "target": "calculator",
            "adapter_required": "SECURE_LOCAL_AGENT",
            "requires_explicit_approval": True,
            "device_supported": True,
            "physical_execution": False,
            "executes_action": False,
        }
        request = self.request(
            "AION, abre Calculator",
            owner_plan=plan,
        )
        self.assertEqual(request["state"], "BLOCKED")
        self.assertIn("APP_NOT_ALLOWLISTED", request["blockers"])

    def test_shell_or_url_material_is_rejected(self):
        cases = (
            "AION, abre o ChatGPT && powershell whoami",
            "AION, abre o ChatGPT; cmd.exe /c calc",
            "AION, abre o ChatGPT https://example.com",
        )
        for index, message in enumerate(cases):
            with self.subTest(message=message):
                request = self.request(
                    message,
                    command_id=f"cmd-shell-{index}",
                    command_nonce=f"nonce-shell-{index}",
                )
                self.assertEqual(request["state"], "BLOCKED")
                self.assertIn(
                    "COMMAND_CONTAINS_FORBIDDEN_MATERIAL",
                    request["blockers"],
                )
                self.assertEqual(request["actions"], [])

    def test_planned_target_must_match_one_command_target(self):
        chatgpt_plan = self.owner_plan("AION, abre o ChatGPT")
        mismatched = self.request(
            "AION, abre WhatsApp",
            owner_plan=chatgpt_plan,
        )
        self.assertEqual(mismatched["state"], "BLOCKED")
        self.assertIn(
            "PLANNED_TARGET_NOT_PRESENT_IN_COMMAND",
            mismatched["blockers"],
        )

        ambiguous_plan = self.owner_plan("AION, abre o ChatGPT e WhatsApp")
        ambiguous = self.request(
            "AION, abre o ChatGPT e WhatsApp",
            owner_plan=ambiguous_plan,
        )
        self.assertEqual(ambiguous["state"], "BLOCKED")
        self.assertIn("COMMAND_TARGET_AMBIGUOUS", ambiguous["blockers"])

    def test_request_digest_and_freshness_fail_closed(self):
        request = self.request()
        current = verify_local_action_request(request, now=CURRENT)
        self.assertTrue(current["current"])

        tampered = copy.deepcopy(request)
        tampered["actions"][0]["logical_app_id"] = "OTHER"
        invalid = verify_local_action_request(tampered, now=CURRENT)
        self.assertFalse(invalid["current"])
        self.assertIn("REQUEST_DIGEST_MISMATCH", invalid["blockers"])

        expired = verify_local_action_request(
            request,
            now="2026-10-08T09:51:31+00:00",
        )
        self.assertFalse(expired["current"])
        self.assertIn("ACTION_REQUEST_EXPIRED", expired["blockers"])

    def test_action_window_is_short_and_timezone_aware(self):
        too_long = self.request(
            expires_at="2026-10-08T09:52:00+00:00",
        )
        self.assertEqual(too_long["state"], "BLOCKED")
        self.assertIn("ACTION_WINDOW_INVALID", too_long["blockers"])

        naive = self.request(
            issued_at="2026-10-08T09:50:00",
        )
        self.assertEqual(naive["state"], "BLOCKED")
        self.assertIn("ACTION_WINDOW_INVALID", naive["blockers"])

    def test_dispatch_readiness_requires_host_crypto_and_replay_guard(self):
        request = self.request()
        ready = evaluate_dispatch_readiness(
            request,
            trusted_host_authorization=self.host_attestation(request),
            replay_guard_attestation=self.replay_attestation(request),
            now=CURRENT,
        )
        self.assertEqual(ready["state"], "DISPATCH_READY")
        self.assertTrue(ready["dispatch_ready"])
        self.assertTrue(ready["adapter_must_reverify_before_execution"])
        self.assertFalse(ready["physical_binding_included"])
        self.assertFalse(ready["execution_command_generated"])
        self.assertFalse(ready["execution_command_executed"])
        self.assertFalse(ready["subprocess_called"])
        self.assertFalse(ready["physical_execution_performed"])
        self.assertFalse(ready["external_action_executed"])
        self.assertFalse(ready["executes_action"])

    def test_generic_chat_or_replayed_nonce_never_reaches_dispatch_ready(self):
        request = self.request()

        generic = evaluate_dispatch_readiness(
            request,
            trusted_host_authorization=self.host_attestation(
                request,
                generic_chat_acknowledgement=True,
            ),
            replay_guard_attestation=self.replay_attestation(request),
            now=CURRENT,
        )
        self.assertFalse(generic["dispatch_ready"])
        self.assertIn(
            "GENERIC_CHAT_ACKNOWLEDGEMENT_FORBIDDEN",
            generic["blockers"],
        )

        replayed = evaluate_dispatch_readiness(
            request,
            trusted_host_authorization=self.host_attestation(request),
            replay_guard_attestation=self.replay_attestation(
                request,
                fresh=False,
                single_use_claimed=False,
            ),
            now=CURRENT,
        )
        self.assertFalse(replayed["dispatch_ready"])
        self.assertIn("NONCE_NOT_FRESH", replayed["blockers"])
        self.assertIn(
            "NONCE_SINGLE_USE_CLAIM_REQUIRED",
            replayed["blockers"],
        )

    def test_policy_forbids_high_risk_desktop_authority(self):
        policy = secure_local_agent_policy()
        self.assertTrue(policy["fresh_owner_command_can_supply_explicit_intent"])
        self.assertTrue(policy["trusted_host_attestation_required"])
        self.assertTrue(policy["cryptographic_owner_verification_required"])
        self.assertTrue(policy["durable_single_use_replay_guard_required"])
        self.assertTrue(policy["signed_local_adapter_required"])
        for key in (
            "arbitrary_app_launch",
            "arbitrary_executable_path",
            "shell_execution",
            "command_line_execution",
            "file_mutation",
            "system_settings_mutation",
            "credential_access",
            "send_message",
            "send_email",
            "purchase_or_payment",
            "trading_order",
            "browser_autofill",
            "microphone_started",
            "hotword_listener_started",
            "network_called",
            "worker_armed",
            "deploy_executed",
            "core_checkpoint_write",
            "physical_execution_performed",
            "external_action_executed",
            "executes_action",
        ):
            self.assertFalse(policy[key], key)


if __name__ == "__main__":
    unittest.main()
