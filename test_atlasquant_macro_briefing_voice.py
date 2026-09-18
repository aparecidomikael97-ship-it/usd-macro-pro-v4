import pytest

from atlasquant_macro_briefing_voice import VoiceRequest, generate_voice_audio


def test_voice_requires_explicit_provider():
    with pytest.raises(RuntimeError, match="provedor TTS"):
        generate_voice_audio(VoiceRequest("Briefing validado."))


def test_voice_passes_exact_transcript_to_provider():
    seen = {}
    def provider(text, voice):
        seen["text"] = text
        seen["voice"] = voice
        return b"audio"

    audio = generate_voice_audio(VoiceRequest("Texto exato.", "deep"), provider)
    assert audio == b"audio"
    assert seen == {"text": "Texto exato.", "voice": "deep"}


def test_voice_rejects_empty_transcript():
    with pytest.raises(ValueError, match="vazio"):
        generate_voice_audio(VoiceRequest("   "), lambda *_: b"audio")


def test_voice_rejects_unknown_voice():
    with pytest.raises(ValueError, match="não permitida"):
        generate_voice_audio(VoiceRequest("Texto.", "inventada"), lambda *_: b"audio")
