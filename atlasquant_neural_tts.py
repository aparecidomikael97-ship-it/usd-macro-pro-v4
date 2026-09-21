"""AtlasQuant fixed neural voice service.

Server-side neural TTS only. Browser/device speech synthesis is intentionally
not used as fallback because device voices vary and can sound robotic.

The service never changes trading state. If neural TTS is unavailable, callers
must keep the transcript visible instead of switching to a generic device voice.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
from typing import Any

import requests

SCHEMA="ATLASQUANT_NEURAL_TTS_V2"
DEFAULT_PROVIDER="openai"
DEFAULT_MODEL="gpt-4o-mini-tts"
DEFAULT_VOICE="cedar"
DEFAULT_ENDPOINT="https://api.openai.com/v1/audio/speech"
MAX_INPUT_CHARS=4096

VOICE_INSTRUCTIONS=(
    "Fale em português brasileiro natural. Use voz masculina, adulta, grave e acolhedora. "
    "Soa como um analista humano experiente conversando com o usuário, sem voz de locutor, "
    "sem exagero comercial e sem tom robótico. Ritmo calmo, dicção clara, pequenas pausas "
    "naturais entre ideias e entonação discreta. Leia números, siglas financeiras e pares "
    "de moedas com clareza. Não acrescente nem remova conteúdo do texto."
)

_ALLOWED_BUILTIN_VOICES={
    "alloy","ash","ballad","coral","echo","fable","nova","onyx",
    "sage","shimmer","verse","marin","cedar",
}


@dataclass(frozen=True)
class NeuralVoiceConfig:
    provider:str=DEFAULT_PROVIDER
    model:str=DEFAULT_MODEL
    voice:str=DEFAULT_VOICE
    endpoint:str=DEFAULT_ENDPOINT
    response_format:str="mp3"
    speed:float=0.96

    def validated(self)->"NeuralVoiceConfig":
        provider=str(self.provider or "").strip().casefold()
        if provider!="openai":
            raise ValueError("provedor TTS não suportado")
        model=str(self.model or "").strip()
        if not model:
            raise ValueError("modelo TTS ausente")
        voice=str(self.voice or "").strip().casefold()
        if voice not in _ALLOWED_BUILTIN_VOICES and not voice.startswith("voice_"):
            raise ValueError("voz TTS não permitida")
        endpoint=str(self.endpoint or "").strip()
        if endpoint!=DEFAULT_ENDPOINT:
            raise ValueError("endpoint TTS não permitido")
        fmt=str(self.response_format or "mp3").strip().casefold()
        if fmt not in {"mp3","opus","aac","flac","wav","pcm"}:
            raise ValueError("formato de áudio não permitido")
        speed=float(self.speed)
        if not math.isfinite(speed) or not 0.25<=speed<=4.0:
            raise ValueError("velocidade TTS inválida")
        return NeuralVoiceConfig(
            provider=provider,
            model=model,
            voice=voice,
            endpoint=endpoint,
            response_format=fmt,
            speed=speed,
        )


def validate_transcript(text:Any)->str:
    transcript=str(text or "").strip()
    if not transcript:
        raise ValueError("texto da voz vazio")
    if len(transcript)>MAX_INPUT_CHARS:
        raise ValueError(
            f"texto da voz excede o limite seguro de {MAX_INPUT_CHARS} caracteres"
        )
    return transcript


def neural_voice_identity(config:NeuralVoiceConfig|None=None)->dict[str,Any]:
    cfg=(config or NeuralVoiceConfig()).validated()
    return {
        "schema":SCHEMA,
        "provider":cfg.provider,
        "model":cfg.model,
        "voice":cfg.voice,
        "language":"pt-BR",
        "identity":"AtlasQuant",
        "style":"masculina, grave, natural e acolhedora",
        "ai_generated":True,
        "browser_speech_fallback":False,
        "device_voice_fallback":False,
        "automatic_playback":False,
        "trading_side_effects":False,
    }


def transcript_cache_key(
    text:Any,
    config:NeuralVoiceConfig|None=None,
)->str:
    cfg=(config or NeuralVoiceConfig()).validated()
    transcript=validate_transcript(text)
    raw="|".join((
        SCHEMA,cfg.provider,cfg.model,cfg.voice,cfg.response_format,
        f"{cfg.speed:.3f}",VOICE_INSTRUCTIONS,transcript,
    ))
    return sha256(raw.encode("utf-8")).hexdigest()


def generate_neural_speech(
    text:Any,
    *,
    api_key:str,
    config:NeuralVoiceConfig|None=None,
    timeout:int=45,
)->bytes:
    """Generate exact-transcript audio using the fixed AtlasQuant identity."""
    cfg=(config or NeuralVoiceConfig()).validated()
    transcript=validate_transcript(text)
    secret=str(api_key or "").strip()
    if not secret:
        raise RuntimeError("provedor neural não configurado")

    response=requests.post(
        cfg.endpoint,
        headers={
            "Authorization":f"Bearer {secret}",
            "Content-Type":"application/json",
        },
        json={
            "model":cfg.model,
            "voice":cfg.voice,
            "input":transcript,
            "instructions":VOICE_INSTRUCTIONS,
            "response_format":cfg.response_format,
            "speed":cfg.speed,
        },
        timeout=max(5,int(timeout)),
    )
    if response.status_code!=200:
        # Deliberately do not surface provider response bodies; they can contain
        # operational/account details and are not useful to the end user.
        raise RuntimeError(f"falha do provedor neural (HTTP {response.status_code})")

    audio=bytes(response.content or b"")
    if not audio:
        raise RuntimeError("provedor neural retornou áudio vazio")
    content_type=str(response.headers.get("content-type","")).casefold()
    if content_type and not (
        content_type.startswith("audio/")
        or "octet-stream" in content_type
    ):
        raise RuntimeError("provedor neural retornou formato inesperado")
    return audio


def provider_configured(api_key:Any)->bool:
    return bool(str(api_key or "").strip())


__all__=[
    "SCHEMA","DEFAULT_PROVIDER","DEFAULT_MODEL","DEFAULT_VOICE",
    "DEFAULT_ENDPOINT","MAX_INPUT_CHARS","VOICE_INSTRUCTIONS",
    "NeuralVoiceConfig","validate_transcript","neural_voice_identity",
    "transcript_cache_key","generate_neural_speech","provider_configured",
]
