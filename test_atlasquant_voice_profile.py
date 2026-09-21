import unittest

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


if __name__=="__main__":
    unittest.main()
