import unittest
from unittest.mock import Mock, patch

from atlasquant_neural_tts import (
    NeuralVoiceConfig,
    build_neural_speech_payload,
    parse_neural_speech_response,
    VOICE_INSTRUCTIONS,
    generate_neural_speech,
    neural_voice_identity,
    transcript_cache_key,
    validate_transcript,
)
from atlasquant_voice_profile import (
    VOICE_PROFILE_ID,
    voice_profile,
    voice_profile_ready,
)


class AtlasQuantVoiceProfileTests(unittest.TestCase):
    def test_profile_is_fixed_server_neural_ptbr_identity(self):
        p=voice_profile()
        self.assertEqual(p["id"],VOICE_PROFILE_ID)
        self.assertEqual(p["language"],"pt-BR")
        self.assertEqual(p["delivery_mode"],"server_neural_tts")
        self.assertEqual(p["provider"],"openai")
        self.assertEqual(p["model"],"gpt-4o-mini-tts")
        self.assertEqual(p["voice"],"cedar")
        self.assertIn("masculina",p["style"])
        self.assertIn("grave",p["style"])
        self.assertTrue(p["strict_fixed_voice"])
        self.assertTrue(p["provider_required"])
        self.assertFalse(p["allow_generic_device_fallback"])
        self.assertFalse(p["allow_browser_speech_synthesis"])
        self.assertEqual(p["fallback_behavior"],"text_only")
        self.assertTrue(p["ai_generated_disclosure_required"])
        self.assertTrue(voice_profile_ready())

    def test_profile_never_enables_automatic_audio_or_trading(self):
        p=voice_profile()
        self.assertFalse(p["automatic_playback"])
        self.assertFalse(p["trading_side_effects"])

    def test_profile_is_defensively_copied(self):
        a=voice_profile()
        b=voice_profile()
        a["quality_terms"].append("mutated")
        self.assertNotIn("mutated",b["quality_terms"])




class AtlasQuantNeuralTtsTests(unittest.TestCase):
    def setUp(self):
        for target in ("requests.sessions.Session.request", "requests.post",
                       "socket.socket.connect", "socket.create_connection"):
            guard=patch(target,side_effect=AssertionError("G76_FORBIDDEN_NETWORK"))
            mock=guard.start()
            self.addCleanup(guard.stop)
            self.addCleanup(mock.assert_not_called)

    def test_identity_never_allows_browser_or_device_fallback(self):
        identity=neural_voice_identity()
        self.assertEqual(identity["model"],"gpt-4o-mini-tts")
        self.assertEqual(identity["voice"],"cedar")
        self.assertTrue(identity["ai_generated"])
        self.assertFalse(identity["browser_speech_fallback"])
        self.assertFalse(identity["device_voice_fallback"])
        self.assertFalse(identity["automatic_playback"])
        self.assertFalse(identity["trading_side_effects"])

    def test_transcript_is_exact_and_cache_is_stable(self):
        text="EUR/USD em observação. Aguardar confirmação."
        self.assertEqual(validate_transcript(text),text)
        self.assertEqual(
            transcript_cache_key(text),
            transcript_cache_key(text),
        )
        self.assertNotEqual(
            transcript_cache_key(text),
            transcript_cache_key(text+" Novo dado."),
        )

    def test_generation_uses_fixed_neural_model_voice_and_ptbr_instructions(self):
        response=Mock()
        response.status_code=200
        response.content=b"MP3DATA"
        response.headers={"content-type":"audio/mpeg"}
        with self.assertRaisesRegex(RuntimeError,"^G75_EXTERNAL_FIRST_SEND_AUTHORITY_UNAVAILABLE$"):
            generate_neural_speech("Texto exato.",api_key="secret",config=NeuralVoiceConfig())
        audio=parse_neural_speech_response(response)
        self.assertEqual(audio,b"MP3DATA")
        payload=build_neural_speech_payload("Texto exato.",config=NeuralVoiceConfig())
        self.assertNotIn("secret",str(payload))
        self.assertEqual(payload["model"],"gpt-4o-mini-tts")
        self.assertEqual(payload["voice"],"cedar")
        self.assertEqual(payload["input"],"Texto exato.")
        self.assertEqual(payload["instructions"],VOICE_INSTRUCTIONS)
        self.assertEqual(payload["response_format"],"mp3")

    def test_missing_provider_never_generates_or_falls_back(self):
        with patch("atlasquant_neural_tts.requests.post") as post:
            with self.assertRaisesRegex(RuntimeError,"não configurado"):
                generate_neural_speech("Texto.",api_key="")
        post.assert_not_called()

    def test_provider_error_is_sanitized(self):
        response=Mock()
        response.status_code=401
        response.content=b'{"error":"sensitive provider detail"}'
        response.headers={"content-type":"application/json"}
        with self.assertRaisesRegex(RuntimeError,"^G75_EXTERNAL_FIRST_SEND_AUTHORITY_UNAVAILABLE$"):
            generate_neural_speech("Texto.",api_key="bad-secret")
        with self.assertRaisesRegex(RuntimeError,"HTTP 401") as ctx:
            parse_neural_speech_response(response)
        self.assertNotIn("sensitive provider detail",str(ctx.exception))
        self.assertNotIn("bad-secret",str(ctx.exception))

if __name__=="__main__":
    unittest.main()
