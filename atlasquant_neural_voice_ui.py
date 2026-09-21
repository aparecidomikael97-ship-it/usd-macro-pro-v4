"""Streamlit UI for the fixed AtlasQuant neural voice.

The UI never falls back to browser/device speech. When the provider secret is
missing or generation fails, the original transcript remains available as text.
"""
from __future__ import annotations

from hashlib import sha256
import os
import re
from typing import Any

import streamlit as st

from atlasquant_neural_tts import (
    NeuralVoiceConfig,
    generate_neural_speech,
    neural_voice_identity,
    provider_configured,
    transcript_cache_key,
)
from atlasquant_voice_profile import VOICE_PROFILE_ID, voice_profile

SCHEMA="ATLASQUANT_NEURAL_VOICE_UI_V2"


def _setting(name:str,default:str="")->str:
    value=os.getenv(name)
    if value is not None and str(value).strip():
        return str(value).strip()
    try:
        value=st.secrets.get(name,default)
        return str(value or default).strip()
    except Exception:
        return str(default or "").strip()


def neural_voice_config()->NeuralVoiceConfig:
    profile=voice_profile()
    return NeuralVoiceConfig(
        provider="openai",
        model=_setting("ATLASQUANT_TTS_MODEL",str(profile.get("model") or "gpt-4o-mini-tts")),
        voice=_setting("ATLASQUANT_TTS_VOICE",str(profile.get("voice") or "cedar")),
        speed=float(_setting("ATLASQUANT_TTS_SPEED",str(profile.get("rate") or 0.96))),
    ).validated()


def neural_voice_status()->dict[str,Any]:
    key=_setting("OPENAI_API_KEY")
    cfg=neural_voice_config()
    identity=neural_voice_identity(cfg)
    return {
        "schema":SCHEMA,
        "profile_id":VOICE_PROFILE_ID,
        "configured":provider_configured(key),
        "provider":identity["provider"],
        "model":identity["model"],
        "voice":identity["voice"],
        "browser_speech_fallback":False,
        "device_voice_fallback":False,
        "automatic_playback":False,
        "ai_generated":True,
        "trading_side_effects":False,
    }


def _state_key(key:object)->str:
    safe=re.sub(r"[^a-zA-Z0-9_-]","_",str(key or "voice"))
    return f"aq_neural_audio_{safe}"


def render_neural_voice_player(
    text:object,
    *,
    key:str,
    button_label:str="🔊 Ouvir",
    show_identity:bool=True,
)->dict[str,Any]:
    transcript=str(text or "").strip()
    cfg=neural_voice_config()
    api_key=_setting("OPENAI_API_KEY")
    status=neural_voice_status()
    state_key=_state_key(key)

    if show_identity:
        st.caption(
            "🎙️ Voz oficial AtlasQuant · neural · portuguesa do Brasil · "
            "identidade fixa. Áudio gerado por IA."
        )

    if not transcript:
        st.info("Sem texto válido para narrar.")
        return {**status,"state":"NO_TRANSCRIPT","audio_ready":False}

    if not api_key:
        st.info(
            "A voz neural oficial ainda não está configurada neste ambiente. "
            "A voz genérica do Google foi desativada; o texto continua disponível."
        )
        return {**status,"state":"PROVIDER_NOT_CONFIGURED","audio_ready":False}

    try:
        digest=transcript_cache_key(transcript,cfg)
    except Exception as exc:
        st.warning(f"Texto não pôde ser preparado para voz: {exc}")
        return {**status,"state":"INVALID_TRANSCRIPT","audio_ready":False}

    current=st.session_state.get(state_key)
    audio=None
    if isinstance(current,dict) and current.get("digest")==digest:
        candidate=current.get("audio")
        if isinstance(candidate,(bytes,bytearray)) and candidate:
            audio=bytes(candidate)

    if st.button(button_label,key=f"{state_key}_generate",width="stretch"):
        try:
            with st.spinner("Gerando a voz AtlasQuant..."):
                audio=generate_neural_speech(
                    transcript,
                    api_key=api_key,
                    config=cfg,
                )
            st.session_state[state_key]={
                "digest":digest,
                "audio":audio,
                "profile_id":VOICE_PROFILE_ID,
            }
        except Exception as exc:
            st.session_state.pop(state_key,None)
            st.warning(
                "A voz neural não pôde ser gerada agora. "
                "O AtlasQuant não vai trocar para a voz do aparelho."
            )
            st.caption(f"Diagnóstico de voz: {type(exc).__name__}: {exc}")
            return {**status,"state":"PROVIDER_ERROR","audio_ready":False}

    if isinstance(audio,(bytes,bytearray)) and audio:
        st.audio(bytes(audio),format="audio/mp3")
        return {
            **status,
            "state":"AUDIO_READY",
            "audio_ready":True,
            "cache_digest":digest,
        }

    return {**status,"state":"READY_TO_GENERATE","audio_ready":False}


__all__=[
    "SCHEMA","neural_voice_config","neural_voice_status",
    "render_neural_voice_player",
]
