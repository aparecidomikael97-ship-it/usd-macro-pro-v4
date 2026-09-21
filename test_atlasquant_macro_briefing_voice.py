import unittest

from atlasquant_macro_briefing_voice import (
    DEFAULT_VOICE_STYLE,
    VoiceRequest,
    generate_voice_audio,
)
from atlasquant_voice_profile import VOICE_PROFILE_ID


class MacroBriefingVoiceTests(unittest.TestCase):
    def test_default_voice_identity_is_fixed_atlasquant_profile(self):
        self.assertEqual(DEFAULT_VOICE_STYLE,VOICE_PROFILE_ID)
        self.assertEqual(VoiceRequest("Texto.").validated().voice,VOICE_PROFILE_ID)

    def test_voice_requires_explicit_provider(self):
        with self.assertRaisesRegex(RuntimeError,"provedor TTS"):
            generate_voice_audio(VoiceRequest("Briefing validado."))

    def test_voice_passes_exact_transcript_and_fixed_identity_to_provider(self):
        seen={}
        def provider(text,voice):
            seen["text"]=text
            seen["voice"]=voice
            return b"audio"
        audio=generate_voice_audio(VoiceRequest("Texto exato."),provider)
        self.assertEqual(audio,b"audio")
        self.assertEqual(seen,{"text":"Texto exato.","voice":VOICE_PROFILE_ID})

    def test_voice_rejects_empty_transcript(self):
        with self.assertRaisesRegex(ValueError,"vazio"):
            generate_voice_audio(VoiceRequest("   "),lambda *_:b"audio")

    def test_voice_rejects_fake_cosmetic_styles(self):
        for fake in ("normal","clear","fancy","deep","crisp","delicate"):
            with self.subTest(fake=fake):
                with self.assertRaisesRegex(ValueError,"identidade de voz"):
                    VoiceRequest("Texto.",fake).validated()


if __name__=="__main__":
    unittest.main()
