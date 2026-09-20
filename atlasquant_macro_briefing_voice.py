"""Safe, provider-agnostic TTS contract for AtlasQuant Macro Briefing.

The adapter never calls a network/provider by itself. It only validates a request
and accepts audio bytes returned by an explicitly configured external provider.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from atlasquant_voice_profile import voice_profile

AudioProvider = Callable[[str, str], bytes]
DEFAULT_VOICE_STYLE=str(voice_profile()["external_style"])


@dataclass(frozen=True)
class VoiceRequest:
    transcript: str
    voice: str = DEFAULT_VOICE_STYLE

    def validated(self) -> "VoiceRequest":
        text = str(self.transcript or "").strip()
        if not text:
            raise ValueError("speech_text vazio")
        if len(text) > 12000:
            raise ValueError("speech_text excede o limite seguro")
        voice = str(self.voice or DEFAULT_VOICE_STYLE).strip().lower()
        if voice not in {"normal", "clear", "fancy", "deep", "crisp", "delicate"}:
            raise ValueError("voz não permitida")
        return VoiceRequest(text, voice)


def generate_voice_audio(request: VoiceRequest, provider: AudioProvider | None = None) -> bytes:
    """Generate audio only after an explicit caller supplies a provider."""
    req = request.validated()
    if provider is None:
        raise RuntimeError("provedor TTS não configurado")
    audio = provider(req.transcript, req.voice)
    if not isinstance(audio, (bytes, bytearray)) or not audio:
        raise RuntimeError("provedor TTS não retornou áudio válido")
    return bytes(audio)

__all__=["AudioProvider","DEFAULT_VOICE_STYLE","VoiceRequest","generate_voice_audio"]
