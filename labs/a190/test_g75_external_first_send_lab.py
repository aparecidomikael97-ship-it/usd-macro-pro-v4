"""G75 LAB containment tests; synthetic inputs and forbidden network only."""
import os
import socket
import unittest
from unittest.mock import Mock, patch

from atlasquant_aion_provider import execute_openai_answer, provider_configuration_status
from atlasquant_neural_tts import generate_neural_speech, NeuralVoiceConfig
from atlasquant_external_first_send_gate import (
    G75_EXTERNAL_FIRST_SEND_AUTHORITY_UNAVAILABLE as REASON,
    require_external_first_send_authority,
)


def config():
    return {
        "AION_MODEL_PROVIDER": "openai", "OPENAI_API_KEY": "FAKE_G75_ONLY",
        "AION_OPENAI_FAST_MODEL": "synthetic-fast",
        "AION_OPENAI_REASONING_MODEL": "synthetic-reasoning",
        "AION_OPENAI_INPUT_USD_PER_MTOK": "1",
        "AION_OPENAI_OUTPUT_USD_PER_MTOK": "1",
        "AION_OPENAI_MAX_OUTPUT_TOKENS": "100",
    }


class G75ExternalFirstSendLab(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        # A transport regression must never reach any real HTTP or socket.
        for target in ("requests.sessions.Session.request", "requests.post",
                       "socket.socket.connect", "socket.create_connection"):
            guard = patch(target, side_effect=AssertionError("G75_FORBIDDEN_NETWORK"))
            guard.start()
            self.addCleanup(guard.stop)

    def ask(self, **overrides):
        args = dict(lane="EXTERNAL_FAST", budget={"allow_paid": True,
                    "monthly_limit_usd": 10}, external_feature_enabled=True,
                    request_approved=True, values=config())
        args.update(overrides)
        return execute_openai_answer("synthetic public question", **args)

    def assert_blocked(self, result):
        self.assertEqual(result, {"schema": "ATLASQUANT_AION_PROVIDER_V1",
            "state": "BLOCKED_FIRST_SEND_AUTHORITY_UNAVAILABLE",
            "called": False, "reason": REASON})
        self.assertNotIn("FAKE_G75_ONLY", str(result))
        self.assertNotIn("synthetic public question", str(result))

    def test_fake_transport_and_explicit_approval_are_not_authority(self):
        transport = Mock()
        self.assert_blocked(self.ask(session=transport))
        transport.post.assert_not_called()

    def test_crafted_session_and_callback_are_not_authority(self):
        class Crafted:
            reserved = True
            first_send_authorized = True
            def __bool__(self):
                raise AssertionError("session must not even be evaluated")
            def reserve(self):
                raise AssertionError("caller callback is not custody")
            def post(self, *args, **kwargs):
                raise AssertionError("caller transport reached")
        self.assert_blocked(self.ask(session=Crafted()))

    def test_ready_config_does_not_authorize_transport(self):
        self.assertTrue(provider_configuration_status(config())["ready"])
        self.assert_blocked(self.ask())

    def test_repeated_calls_never_send(self):
        for _ in range(5):
            self.assert_blocked(self.ask())
            with self.assertRaisesRegex(RuntimeError, "^" + REASON + "$"):
                generate_neural_speech("synthetic public audio", api_key="FAKE_G75_ONLY")

    def test_no_environment_or_config_bypass(self):
        supplied = config()
        supplied.update(G75_EXTERNAL_FIRST_SEND_AUTHORITY="approved",
                        G75_EXTERNAL_FIRST_SEND_BYPASS="true")
        with patch.dict(os.environ, supplied):
            self.assert_blocked(self.ask(values=supplied))
            with self.assertRaisesRegex(RuntimeError, "^" + REASON + "$"):
                require_external_first_send_authority()

    def test_missing_text_config_preserves_legacy_gate(self):
        self.assertEqual(self.ask(values={})["state"], "BLOCKED_PROVIDER_CONFIG")

    def test_offline_text_preserves_legacy_gate(self):
        supplied = config()
        supplied["AION_MODEL_PROVIDER"] = "offline"
        self.assertEqual(self.ask(values=supplied)["state"], "BLOCKED_PROVIDER_CONFIG")

    def test_no_session_still_blocks(self):
        self.assert_blocked(self.ask(session=None))

    def test_legacy_approval_feature_budget_and_privacy_precede_gate(self):
        for args, state in (({"request_approved": False}, "BLOCKED_APPROVAL"),
                            ({"external_feature_enabled": False}, "BLOCKED_FEATURE_FLAG"),
                            ({"budget": {"allow_paid": False}}, "BLOCKED_BUDGET")):
            with self.subTest(state=state):
                self.assertEqual(self.ask(**args)["state"], state)
        result = execute_openai_answer("minha senha ? 123", lane="EXTERNAL_FAST",
            budget=None, external_feature_enabled=True, request_approved=True,
            values=config())
        self.assertEqual(result["state"], "BLOCKED_PRIVACY")

    def test_tts_fake_post_and_explicit_config_never_send(self):
        with patch("atlasquant_neural_tts.requests.post") as post:
            with self.assertRaisesRegex(RuntimeError, "^" + REASON + "$") as ctx:
                generate_neural_speech("synthetic public audio",
                    api_key="FAKE_G75_ONLY", config=NeuralVoiceConfig())
            post.assert_not_called()
        self.assertNotIn("FAKE_G75_ONLY", str(ctx.exception))
        self.assertNotIn("synthetic public audio", str(ctx.exception))

    def test_tts_missing_key_preserves_legacy_gate(self):
        with self.assertRaises(RuntimeError) as ctx:
            generate_neural_speech("synthetic public audio", api_key="")
        self.assertNotEqual(str(ctx.exception), REASON)

    def test_tts_invalid_config_and_transcript_preserve_validation(self):
        with self.assertRaises(ValueError):
            generate_neural_speech("synthetic", api_key="FAKE_G75_ONLY",
                config=NeuralVoiceConfig(endpoint="https://invalid.example"))
        with self.assertRaises(ValueError):
            generate_neural_speech("", api_key="FAKE_G75_ONLY")


if __name__ == "__main__":
    unittest.main()
