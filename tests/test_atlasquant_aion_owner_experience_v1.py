from datetime import datetime
import unittest

from atlasquant_aion_owner_experience_v1 import (
    command_plan,
    continuity_handoff,
    interaction_mode_plan,
    meeting_transition,
    owner_binding,
    owner_experience_policy,
    owner_greeting_plan,
    voice_capability_plan,
)


class AionOwnerExperienceV1Tests(unittest.TestCase):
    def access(self, **changes):
        session = {
            "username": "mikael",
            "role": "ADMIN",
            "permissions": ["app:read", "aion:admin", "aion:checkpoint"],
            "credential_fingerprint": "test-fingerprint",
        }
        session.update(changes.pop("session", {}))
        value = {
            "allowed": True,
            "mode": "AUTHENTICATED",
            "role": "ADMIN",
            "session": session,
        }
        value.update(changes)
        return value

    def assertion(self, **changes):
        value = {
            "verified": True,
            "principal": "HUMAN_OWNER",
            "subject": "mikael",
            "issuer": "owner-auth-test",
        }
        value.update(changes)
        return value

    def test_owner_binding_is_injected_and_fail_closed(self):
        good = owner_binding(self.access(), self.assertion())
        self.assertTrue(good["bound"])
        self.assertEqual(good["principal"], "HUMAN_OWNER")
        self.assertFalse(good["grants_authority"])

        self.assertFalse(
            owner_binding(self.access(), self.assertion(verified=False))["bound"]
        )
        self.assertFalse(
            owner_binding(self.access(), self.assertion(subject="other"))["bound"]
        )
        self.assertFalse(
            owner_binding(self.access(role="USER"), self.assertion())["bound"]
        )

    def test_greeting_is_prepared_but_not_spoken(self):
        result = owner_greeting_plan(
            self.access(),
            self.assertion(),
            now=datetime(2026, 10, 8, 9, 0),
            timezone_name="America/Cuiaba",
            display_name="Mikael",
        )
        self.assertEqual(result["state"], "READY")
        self.assertIn("Mikael", result["text"])
        self.assertFalse(result["spoken"])
        self.assertFalse(result["executes_action"])

    def test_voice_plan_never_starts_capture(self):
        ready = voice_capability_plan(
            device="desktop",
            microphone_permission=True,
            continuous_recognition_available=True,
            hotword_runtime_available=True,
            tts_ready=True,
            app_active=True,
        )
        self.assertTrue(ready["hotword_ready"])
        self.assertFalse(ready["microphone_opened"])
        self.assertFalse(ready["listener_started"])
        self.assertFalse(ready["provider_called"])

    def test_internal_navigation_commands_are_plans_only(self):
        cases = (
            ("AION, abre a aba Trader", "trader"),
            ("AION entra no AtlasQuant", "central"),
            ("AION, abre Negócios", "negocios"),
            ("AION, abre Investimentos", "investimentos"),
        )
        for message, target in cases:
            with self.subTest(message=message):
                plan = command_plan(message, device="mobile", owner_bound=True)
                self.assertEqual(plan["state"], "PLANNED")
                self.assertEqual(plan["kind"], "ATLASQUANT_NAVIGATION")
                self.assertEqual(plan["target"], target)
                self.assertFalse(plan["physical_execution"])

    def test_external_app_commands_require_local_agent(self):
        cases = (
            ("AION, abre o ChatGPT", "chatgpt"),
            ("AION, abre WhatsApp", "whatsapp"),
            ("AION, abre Spotify e toca sertanejo", "spotify"),
        )
        for message, target in cases:
            with self.subTest(message=message):
                desktop = command_plan(
                    message,
                    device="desktop",
                    owner_bound=True,
                )
                self.assertEqual(desktop["target"], target)
                self.assertEqual(
                    desktop["adapter_required"],
                    "SECURE_LOCAL_AGENT",
                )
                self.assertTrue(desktop["device_supported"])
                self.assertTrue(desktop["requires_explicit_approval"])
                self.assertFalse(desktop["physical_execution"])

    def test_commands_require_owner_binding(self):
        blocked = command_plan(
            "AION, abre o ChatGPT",
            device="desktop",
            owner_bound=False,
        )
        self.assertEqual(blocked["state"], "BLOCKED")

    def test_teaching_mode_contract(self):
        plan = interaction_mode_plan(
            "teaching",
            topic="Negócios B2B e CRM",
        )
        self.assertEqual(plan["voice_style"], "CALM_PATIENT")
        self.assertTrue(plan["slides"])
        self.assertTrue(plan["drawings"])
        self.assertTrue(plan["exercises"])

    def test_meeting_mode_pause_and_resume(self):
        plan = interaction_mode_plan("meeting", sector="clínica")
        self.assertTrue(plan["pause_for_questions"])
        self.assertTrue(plan["resume_to_prior_slide"])

        start = meeting_transition("IDLE", "START", slide=4)
        self.assertEqual(start["meeting_state"], "PRESENTING")
        pause = meeting_transition("PRESENTING", "QUESTION", slide=4)
        self.assertEqual(pause["meeting_state"], "PAUSED_FOR_QA")
        self.assertEqual(pause["return_slide"], 4)
        answered = meeting_transition("PAUSED_FOR_QA", "ANSWERED", slide=4)
        self.assertEqual(answered["meeting_state"], "RESUME_PENDING")
        resumed = meeting_transition("RESUME_PENDING", "RESUME", slide=4)
        self.assertEqual(resumed["meeting_state"], "PRESENTING")

    def test_invalid_meeting_transition_is_blocked(self):
        result = meeting_transition("IDLE", "RESUME", slide=2)
        self.assertEqual(result["state"], "BLOCKED")

    def test_cross_device_handoff_transfers_context_not_authentication(self):
        handoff = continuity_handoff(
            source_device="desktop",
            target_device="mobile",
            owner_subject="mikael",
            conversation_id="conv-1",
            last_turn_id="turn-9",
            context={"mode": "TEACHING", "topic": "CRM", "slide": 7},
        )
        self.assertEqual(handoff["state"], "HANDOFF_READY")
        self.assertFalse(handoff["authentication_transferred"])
        self.assertFalse(handoff["session_token_transferred"])
        self.assertFalse(handoff["secrets_transferred"])
        self.assertTrue(handoff["requires_target_reauthentication"])

    def test_policy_has_no_physical_or_production_authority(self):
        policy = owner_experience_policy()
        self.assertFalse(policy["owner_identity_inferred"])
        self.assertFalse(policy["automatic_app_launch"])
        self.assertFalse(policy["automatic_navigation"])
        self.assertFalse(policy["microphone_started"])
        self.assertFalse(policy["continuous_listener_started"])
        self.assertFalse(policy["worker_armed"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["core_checkpoint_write"])
        self.assertFalse(policy["external_action_executed"])


if __name__ == "__main__":
    unittest.main()
