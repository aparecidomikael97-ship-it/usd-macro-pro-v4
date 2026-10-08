import unittest

from atlasquant_aion_voice_hotword_runtime_v1 import (
    ACTIVATION_SCHEMA,
    detect_voice_activation,
    route_voice_command,
    voice_continuity_handoff,
    voice_hotword_runtime_plan,
    voice_privacy_policy,
    voice_response_plan,
    voice_state_transition,
)


OWNER_BINDING = "sha256:" + ("a" * 64)
NOW = "2026-10-08T14:00:00+00:00"


class AionVoiceHotwordRuntimeV1Tests(unittest.TestCase):
    def ready_plan(self, **changes):
        kwargs = {
            "device": "DESKTOP",
            "owner_binding_digest": OWNER_BINDING,
            "microphone_permission": True,
            "continuous_recognition_available": True,
            "hotword_runtime_available": True,
            "tts_ready": True,
            "app_active": True,
            "privacy_indicator_available": True,
            "push_to_talk_available": True,
            "background_listening_authorized": False,
        }
        kwargs.update(changes)
        return voice_hotword_runtime_plan(**kwargs)

    def hotword_activation(self, text="AION, abre o ChatGPT"):
        return detect_voice_activation(text, mode="HOTWORD")

    def test_ready_plan_starts_nothing(self):
        plan = self.ready_plan()
        self.assertEqual(plan["state"], "READY")
        self.assertTrue(plan["hotword_ready"])
        self.assertTrue(plan["push_to_talk_ready"])
        self.assertTrue(plan["text_fallback"])
        self.assertFalse(plan["hotword_is_authentication"])
        self.assertFalse(plan["wake_word_grants_authority"])
        self.assertFalse(plan["background_listening_supported_v1"])
        self.assertFalse(plan["raw_audio_persistence_allowed"])
        self.assertFalse(plan["raw_transcript_persistence_allowed"])
        self.assertFalse(plan["microphone_opened"])
        self.assertFalse(plan["listener_started"])
        self.assertFalse(plan["provider_called"])
        self.assertFalse(plan["audio_playback_started"])
        self.assertFalse(plan["background_worker_started"])
        self.assertFalse(plan["external_action_executed"])
        self.assertFalse(plan["executes_action"])

    def test_microphone_permission_and_privacy_indicator_are_required(self):
        no_mic = self.ready_plan(microphone_permission=False)
        self.assertEqual(no_mic["state"], "BLOCKED")
        self.assertIn(
            "MICROPHONE_PERMISSION_REQUIRED",
            no_mic["blockers"],
        )

        no_indicator = self.ready_plan(privacy_indicator_available=False)
        self.assertEqual(no_indicator["state"], "BLOCKED")
        self.assertIn(
            "VISIBLE_PRIVACY_INDICATOR_REQUIRED",
            no_indicator["blockers"],
        )

    def test_hotword_requires_exact_leading_aion(self):
        exact = detect_voice_activation(
            "AION, abre o ChatGPT",
            mode="HOTWORD",
        )
        self.assertTrue(exact["activation_detected"])
        self.assertTrue(exact["wake_word_detected"])
        self.assertFalse(exact["activation_phrase_is_authentication"])
        self.assertFalse(exact["grants_owner_authority"])

        middle = detect_voice_activation(
            "abre o AION agora",
            mode="HOTWORD",
        )
        self.assertFalse(middle["activation_detected"])

        false_prefix = detect_voice_activation(
            "AIONIC abre o ChatGPT",
            mode="HOTWORD",
        )
        self.assertFalse(false_prefix["activation_detected"])
        self.assertTrue(false_prefix["false_hotword_prefix_detected"])

    def test_push_to_talk_is_explicit_and_does_not_require_hotword(self):
        ignored = detect_voice_activation(
            "abre o ChatGPT",
            mode="PUSH_TO_TALK",
            explicit_gesture=False,
        )
        self.assertFalse(ignored["activation_detected"])

        activated = detect_voice_activation(
            "abre o ChatGPT",
            mode="PUSH_TO_TALK",
            explicit_gesture=True,
        )
        self.assertTrue(activated["activation_detected"])
        self.assertFalse(activated["grants_owner_authority"])

    def test_state_machine_happy_path_never_opens_microphone_itself(self):
        state = "DISARMED"
        for event, expected in (
            ("ENABLE", "ARMED"),
            ("START_LISTENING", "LISTENING_FOR_WAKE_WORD"),
            ("WAKE_DETECTED", "CAPTURING_COMMAND"),
            ("TRANSCRIPT_READY", "COMMAND_READY"),
            ("RESPONSE_READY", "RESPONDING"),
            ("RESPONSE_DONE", "ARMED"),
        ):
            result = voice_state_transition(
                state,
                event,
                microphone_permission=True,
                app_active=True,
            )
            self.assertEqual(result["state"], "TRANSITIONED")
            self.assertEqual(result["to_state"], expected)
            self.assertFalse(result["microphone_opened_by_this_module"])
            self.assertFalse(result["listener_started_by_this_module"])
            self.assertFalse(result["raw_audio_recorded"])
            self.assertFalse(result["external_action_executed"])
            state = expected

    def test_permission_revocation_and_app_inactive_fail_closed(self):
        revoked = voice_state_transition(
            "LISTENING_FOR_WAKE_WORD",
            "MIC_PERMISSION_REVOKED",
            microphone_permission=False,
            app_active=True,
        )
        self.assertEqual(revoked["to_state"], "BLOCKED_PERMISSION")
        self.assertFalse(revoked["microphone_should_be_active"])

        inactive = voice_state_transition(
            "LISTENING_FOR_WAKE_WORD",
            "APP_INACTIVE",
            microphone_permission=True,
            app_active=False,
        )
        self.assertEqual(inactive["to_state"], "SUSPENDED_APP_INACTIVE")
        self.assertFalse(inactive["microphone_should_be_active"])

        blocked_ptt = voice_state_transition(
            "ARMED",
            "PUSH_TO_TALK",
            microphone_permission=True,
            app_active=False,
        )
        self.assertEqual(blocked_ptt["state"], "BLOCKED")
        self.assertIn("APP_ACTIVE_REQUIRED", blocked_ptt["blockers"])

    def test_privacy_pause_stops_active_listening_state(self):
        paused = voice_state_transition(
            "LISTENING_FOR_WAKE_WORD",
            "PRIVACY_PAUSE",
            microphone_permission=True,
            app_active=True,
        )
        self.assertEqual(paused["to_state"], "PAUSED_PRIVACY")
        self.assertFalse(paused["microphone_should_be_active"])

        blocked = voice_state_transition(
            "PAUSED_PRIVACY",
            "START_LISTENING",
            microphone_permission=True,
            app_active=True,
            privacy_pause=True,
        )
        self.assertEqual(blocked["state"], "BLOCKED")

    def test_voice_route_requires_owner_binding_even_after_hotword(self):
        activation = self.hotword_activation()
        route = route_voice_command(
            "AION, abre o ChatGPT",
            activation=activation,
            device="DESKTOP",
            owner_bound=False,
            owner_binding_digest=OWNER_BINDING,
            session_id="voice-session-1",
            activation_id="activation-1",
            captured_at=NOW,
        )
        self.assertEqual(route["state"], "BLOCKED")
        self.assertIn(
            "HUMAN_OWNER_BINDING_REQUIRED",
            route["blockers"],
        )
        self.assertFalse(route["physical_execution"])
        self.assertFalse(route["external_action_executed"])
        self.assertFalse(route["raw_transcript_returned"])
        self.assertFalse(route["raw_transcript_persisted"])

    def test_external_app_voice_route_goes_to_secure_local_agent_only(self):
        activation = self.hotword_activation()
        route = route_voice_command(
            "AION, abre o ChatGPT",
            activation=activation,
            device="DESKTOP",
            owner_bound=True,
            owner_binding_digest=OWNER_BINDING,
            session_id="voice-session-1",
            activation_id="activation-1",
            captured_at=NOW,
        )
        self.assertEqual(route["state"], "ROUTE_READY")
        self.assertEqual(route["route_kind"], "LOCAL_APPLICATION")
        self.assertEqual(route["target"], "chatgpt")
        self.assertEqual(route["adapter_required"], "SECURE_LOCAL_AGENT")
        self.assertTrue(route["owner_plan_requires_explicit_approval"])
        self.assertFalse(route["physical_execution"])
        self.assertFalse(route["wake_word_grants_authority"])
        self.assertFalse(route["provider_called"])
        self.assertFalse(route["external_action_executed"])
        self.assertFalse(route["executes_action"])

    def test_internal_navigation_voice_route_stays_non_executing(self):
        activation = self.hotword_activation("AION, abre a aba Trader")
        route = route_voice_command(
            "AION, abre a aba Trader",
            activation=activation,
            device="DESKTOP",
            owner_bound=True,
            owner_binding_digest=OWNER_BINDING,
            session_id="voice-session-2",
            activation_id="activation-2",
            captured_at=NOW,
        )
        self.assertEqual(route["route_kind"], "ATLASQUANT_NAVIGATION")
        self.assertEqual(route["target"], "trader")
        self.assertEqual(
            route["adapter_required"],
            "TRUSTED_HOST_NAVIGATION",
        )
        self.assertFalse(route["physical_execution"])
        self.assertFalse(route["external_action_executed"])

    def test_unmatched_voice_text_routes_to_aion_conversation(self):
        activation = self.hotword_activation(
            "AION, me explique inflação"
        )
        route = route_voice_command(
            "AION, me explique inflação",
            activation=activation,
            device="MOBILE",
            owner_bound=True,
            owner_binding_digest=OWNER_BINDING,
            session_id="voice-session-3",
            activation_id="activation-3",
            captured_at=NOW,
        )
        self.assertEqual(route["state"], "ROUTE_READY")
        self.assertEqual(route["route_kind"], "AION_CONVERSATION")
        self.assertEqual(route["target"], "aion")
        self.assertEqual(route["adapter_required"], "AION_CHAT_RUNTIME")
        self.assertFalse(route["physical_execution"])

    def test_sensitive_credential_like_speech_is_blocked(self):
        activation = self.hotword_activation(
            "AION, minha senha é alguma coisa"
        )
        route = route_voice_command(
            "AION, minha senha é alguma coisa",
            activation=activation,
            device="DESKTOP",
            owner_bound=True,
            owner_binding_digest=OWNER_BINDING,
            session_id="voice-session-4",
            activation_id="activation-4",
            captured_at=NOW,
        )
        self.assertEqual(route["state"], "BLOCKED")
        self.assertIn(
            "SENSITIVE_CREDENTIAL_LIKE_SPEECH_BLOCKED",
            route["blockers"],
        )

    def test_high_risk_voice_action_requires_separate_ceremony(self):
        activation = self.hotword_activation(
            "AION, faz pix para o João"
        )
        route = route_voice_command(
            "AION, faz pix para o João",
            activation=activation,
            device="DESKTOP",
            owner_bound=True,
            owner_binding_digest=OWNER_BINDING,
            session_id="voice-session-5",
            activation_id="activation-5",
            captured_at=NOW,
        )
        self.assertEqual(route["state"], "BLOCKED")
        self.assertIn(
            "HIGH_RISK_VOICE_ACTION_REQUIRES_SEPARATE_CEREMONY",
            route["blockers"],
        )

    def test_response_plan_keeps_text_fallback_and_no_generic_tts(self):
        response = voice_response_plan(
            "Pronto. Posso continuar.",
            voice_session_active=True,
            tts_ready=True,
            user_requested_audio=True,
        )
        self.assertEqual(response["state"], "READY")
        self.assertTrue(response["text_response_available"])
        self.assertTrue(response["text_fallback"])
        self.assertFalse(response["generic_device_tts_fallback_allowed"])
        self.assertFalse(response["provider_called"])
        self.assertFalse(response["audio_generated"])
        self.assertFalse(response["audio_playback_started"])
        self.assertFalse(response["automatic_generic_speech_started"])

    def test_voice_handoff_transfers_no_audio_transcript_or_auth(self):
        handoff = voice_continuity_handoff(
            session_id="voice-session-6",
            source_device="MOBILE",
            target_device="DESKTOP",
            last_route_digest="sha256:" + ("b" * 64),
            runtime_state="ARMED",
        )
        self.assertEqual(handoff["state"], "READY")
        self.assertFalse(handoff["raw_audio_transferred"])
        self.assertFalse(handoff["raw_transcript_transferred"])
        self.assertFalse(handoff["microphone_state_transferred"])
        self.assertFalse(handoff["authentication_transferred"])
        self.assertFalse(handoff["owner_authority_transferred"])
        self.assertTrue(handoff["target_device_must_reauthenticate"])
        self.assertTrue(
            handoff["target_device_must_request_microphone_permission"]
        )
        self.assertFalse(handoff["listener_started"])
        self.assertFalse(handoff["executes_action"])

    def test_privacy_policy_is_fail_closed(self):
        policy = voice_privacy_policy()
        self.assertFalse(policy["hotword_is_authentication"])
        self.assertFalse(policy["wake_word_grants_authority"])
        self.assertTrue(policy["microphone_permission_required"])
        self.assertTrue(policy["visible_privacy_indicator_required"])
        self.assertTrue(policy["one_tap_privacy_pause_required"])
        self.assertTrue(policy["app_active_required_for_hotword_v1"])
        self.assertFalse(policy["background_listening_supported_v1"])
        self.assertTrue(policy["push_to_talk_supported"])
        self.assertTrue(policy["exact_leading_hotword_required"])
        self.assertFalse(policy["fuzzy_hotword_activation_allowed"])
        self.assertFalse(policy["raw_audio_persistence_allowed"])
        self.assertFalse(policy["raw_transcript_persistence_allowed"])
        self.assertFalse(policy["generic_device_tts_fallback_allowed"])
        self.assertTrue(policy["text_fallback_required"])
        self.assertTrue(policy["credential_like_voice_commands_blocked"])
        self.assertTrue(
            policy["high_risk_voice_actions_require_separate_ceremony"]
        )
        self.assertFalse(policy["trading_order_authority"])
        self.assertFalse(policy["payment_authority"])
        self.assertFalse(policy["file_delete_authority"])
        self.assertFalse(policy["software_install_authority"])
        self.assertFalse(policy["local_app_physical_execution"])
        self.assertFalse(policy["microphone_opened"])
        self.assertFalse(policy["hotword_listener_started"])
        self.assertFalse(policy["asr_provider_called"])
        self.assertFalse(policy["tts_provider_called"])
        self.assertFalse(policy["audio_playback_started"])
        self.assertFalse(policy["background_worker_started"])
        self.assertFalse(policy["network_called"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["core_checkpoint_write"])
        self.assertFalse(policy["executes_action"])


if __name__ == "__main__":
    unittest.main()
