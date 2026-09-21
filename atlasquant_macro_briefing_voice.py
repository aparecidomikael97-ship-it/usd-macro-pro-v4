"""Safe fixed-identity TTS contract for AtlasQuant Macro Briefing.

This compatibility adapter never selects between cosmetic voice styles. The
only accepted identity is the official AtlasQuant neural profile.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from atlasquant_voice_profile import VOICE_PROFILE_ID

AudioProvider = Callable[[str, str], bytes]
DEFAULT_VOICE_STYLE=VOICE_PROFILE_ID


@dataclass(frozen=True)
class VoiceRequest:
    transcript:str
    voice:str=DEFAULT_VOICE_STYLE

    def validated(self)->"VoiceRequest":
        text=str(self.transcript or "").strip()
        if not text:
            raise ValueError("speech_text vazio")
        if len(text)>4096:
            raise ValueError("speech_text excede o limite seguro")
        identity=str(self.voice or DEFAULT_VOICE_STYLE).strip()
        if identity!=VOICE_PROFILE_ID:
            raise ValueError("identidade de voz não permitida")
        return VoiceRequest(text,VOICE_PROFILE_ID)


def generate_voice_audio(
    request:VoiceRequest,
    provider:AudioProvider|None=None,
)->bytes:
    """Generate audio only with the fixed AtlasQuant identity."""
    req=request.validated()
    if provider is None:
        raise RuntimeError("provedor TTS não configurado")
    audio=provider(req.transcript,req.voice)
    if not isinstance(audio,(bytes,bytearray)) or not audio:
        raise RuntimeError("provedor TTS não retornou áudio válido")
    return bytes(audio)


__all__=[
    "AudioProvider","DEFAULT_VOICE_STYLE","VoiceRequest","generate_voice_audio",
]
