import unittest

from atlasquant_macro_briefing_voice import VoiceRequest, generate_voice_audio


class MacroBriefingVoiceTests(unittest.TestCase):
    def test_voice_requires_explicit_provider(self):
        with self.assertRaisesRegex(RuntimeError, "provedor TTS"):
            generate_voice_audio(VoiceRequest("Briefing validado."))

    def test_voice_passes_exact_transcript_to_provider(self):
        seen = {}

        def provider(text, voice):
            seen["text"] = text
            seen["voice"] = voice
            return b"audio"

        audio = generate_voice_audio(VoiceRequest("Texto exato.", "deep"), provider)
        self.assertEqual(audio, b"audio")
        self.assertEqual(seen, {"text": "Texto exato.", "voice": "deep"})

    def test_voice_rejects_empty_transcript(self):
        with self.assertRaisesRegex(ValueError, "vazio"):
            generate_voice_audio(VoiceRequest("   "), lambda *_: b"audio")

    def test_voice_rejects_unknown_voice(self):
        with self.assertRaisesRegex(ValueError, "não permitida"):
            generate_voice_audio(VoiceRequest("Texto.", "inventada"), lambda *_: b"audio")


if __name__ == "__main__":
    unittest.main()
