"""The second concrete billable OpenAI API path must fail before POST."""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch
import unittest

import requests
import atlasquant_neural_tts as neural


class PaidTTSProductionNoGoTests(unittest.TestCase):
    def protected(self,*,text="Texto público sintético",
                  api_key="fake-test-only-no-credentials",config=None):
        with patch("requests.post",
                   side_effect=AssertionError("NEVER DO REAL TTS POST")), \
             patch.object(requests.sessions.Session,"send",
                          side_effect=AssertionError("NEVER SEND HTTP")):
            return neural.generate_neural_speech(
                text,api_key=api_key,config=config,
            )

    def test_ready_text_fake_key_still_stopped_before_openai_speech_api(self):
        with self.assertRaisesRegex(RuntimeError,"bloqueada"):
            self.protected()

    def test_high_perceived_owner_approval_cannot_unlock_tts(self):
        with patch.dict("os.environ",{
            "AION_OWNER_VERIFIED":"true",
            "AION_PAID_TTS_ENABLED":"true",
            "AION_MODEL_DISPATCH_HARD_DENY":"false",
            "AION_VOICE_AUTOPLAY":"true",
        }):
            with self.assertRaisesRegex(RuntimeError,"bloqueada"):
                self.protected()

    def test_tts_reasoning_model_cannot_bypass(self):
        cfg=neural.NeuralVoiceConfig(model="other-costing-model")
        with self.assertRaisesRegex(RuntimeError,"bloqueada"):
            self.protected(config=cfg)

    def test_custom_voice_key_does_not_bypass(self):
        cfg=neural.NeuralVoiceConfig(voice="voice_dummy")
        with self.assertRaisesRegex(RuntimeError,"bloqueada"):
            self.protected(config=cfg)

    def test_direct_endpoint_injection_stays_blocked_as_invalid(self):
        cfg=neural.NeuralVoiceConfig(endpoint="https://other.invalid/")
        with self.assertRaises(ValueError):
            self.protected(config=cfg)

    def test_no_secret_keeps_existing_configuration_error(self):
        with self.assertRaisesRegex(RuntimeError,"não configurado"):
            self.protected(api_key="")

    def test_invalid_empty_text_stops_before_network(self):
        with self.assertRaises(ValueError):
            self.protected(text="")

    def test_overlong_text_stops_before_network(self):
        with self.assertRaises(ValueError):
            self.protected(text="A"*4097)

    def test_invalid_speech_config_stops_before_network(self):
        cfg=neural.NeuralVoiceConfig(provider="external-provider")
        with self.assertRaises(ValueError):
            self.protected(config=cfg)

    def test_tts_source_lock_literal_true_above_actual_billable_post(self):
        root=Path(__file__).resolve().parents[1]
        tree=ast.parse((root/"atlasquant_neural_tts.py").read_text("utf-8"))
        assignments=[
            n for n in tree.body if isinstance(n,ast.Assign)
            and any(isinstance(t,ast.Name)
                    and t.id=="_PAID_TTS_DISPATCH_HARD_DENY"
                    for t in n.targets)
        ]
        self.assertEqual(len(assignments),1)
        self.assertIs(assignments[0].value.value,True)
        fn=next(n for n in tree.body
                if isinstance(n,ast.FunctionDef)
                and n.name=="generate_neural_speech")
        guard=next(n for n in ast.walk(fn)
                   if isinstance(n,ast.If)
                   and isinstance(n.test,ast.Compare)
                   and isinstance(n.test.left,ast.Name)
                   and n.test.left.id=="_PAID_TTS_DISPATCH_HARD_DENY")
        posts=[
            n for n in ast.walk(fn)
            if isinstance(n,ast.Call)
            and isinstance(n.func,ast.Attribute)
            and n.func.attr=="post"
        ]
        self.assertEqual(len(posts),1)
        self.assertLess(guard.lineno,posts[0].lineno)
        self.assertIsInstance(guard.body[0],ast.Raise)
        self.assertNotIn(
            "_PAID_TTS_DISPATCH_HARD_DENY",neural.__all__,
        )

    def test_voice_metadata_and_transcript_cache_remain_offline(self):
        identity=neural.neural_voice_identity()
        self.assertFalse(identity["automatic_playback"])
        self.assertFalse(identity["trading_side_effects"])
        self.assertFalse(identity["browser_speech_fallback"])
        digest=neural.transcript_cache_key("Mensagem educacional")
        self.assertEqual(len(digest),64)


if __name__=="__main__":
    unittest.main()
