import unittest

from atlasquant_voice_profile import (
    VOICE_PROFILE_ID,
    voice_profile,
    voice_profile_ready,
)


class AtlasQuantVoiceProfileTests(unittest.TestCase):
    def test_profile_matches_approved_natural_deep_ptbr_direction(self):
        p=voice_profile()
        self.assertEqual(p["id"],VOICE_PROFILE_ID)
        self.assertEqual(p["language"],"pt-BR")
        self.assertEqual(p["external_style"],"deep")
        self.assertLess(float(p["pitch"]),1.0)
        self.assertGreaterEqual(float(p["rate"]),0.85)
        self.assertLessEqual(float(p["rate"]),1.0)
        self.assertIn("natural",p["quality_terms"])
        self.assertIn("neural",p["quality_terms"])
        self.assertTrue(p["preferred_terms"])
        self.assertTrue(voice_profile_ready())

    def test_profile_never_enables_automatic_audio_or_trading(self):
        p=voice_profile()
        self.assertFalse(p["automatic_playback"])
        self.assertFalse(p["trading_side_effects"])

    def test_profile_is_defensively_copied(self):
        a=voice_profile()
        b=voice_profile()
        a["preferred_terms"].append("mutated")
        self.assertNotIn("mutated",b["preferred_terms"])


if __name__=="__main__":
    unittest.main()
