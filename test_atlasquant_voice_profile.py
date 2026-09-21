import unittest
from unittest.mock import Mock, patch

from atlasquant_neural_tts import (
    NeuralVoiceConfig,
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
        with patch("atlasquant_neural_tts.requests.post",return_value=response) as post:
            audio=generate_neural_speech(
                "Texto exato.",
                api_key="secret",
                config=NeuralVoiceConfig(),
            )
        self.assertEqual(audio,b"MP3DATA")
        kwargs=post.call_args.kwargs
        self.assertNotIn("secret",str(kwargs["json"]))
        self.assertEqual(kwargs["json"]["model"],"gpt-4o-mini-tts")
        self.assertEqual(kwargs["json"]["voice"],"cedar")
        self.assertEqual(kwargs["json"]["input"],"Texto exato.")
        self.assertEqual(kwargs["json"]["instructions"],VOICE_INSTRUCTIONS)
        self.assertEqual(kwargs["json"]["response_format"],"mp3")
        self.assertEqual(kwargs["headers"]["Authorization"],"Bearer secret")

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
        with patch("atlasquant_neural_tts.requests.post",return_value=response):
            with self.assertRaisesRegex(RuntimeError,"HTTP 401") as ctx:
                generate_neural_speech("Texto.",api_key="bad-secret")
        self.assertNotIn("sensitive provider detail",str(ctx.exception))
        self.assertNotIn("bad-secret",str(ctx.exception))

if __name__=="__main__":
    unittest.main()
