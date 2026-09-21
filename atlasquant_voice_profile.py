"""Shared AtlasQuant voice profile.

This module defines the presentation-only voice preference used by browser/device
speech and by the optional external TTS request contract. It does not call a TTS
provider, fetch market data, change trading state, or execute orders.
"""
from __future__ import annotations

from typing import Any

SCHEMA="ATLASQUANT_VOICE_PROFILE_V2"
VOICE_PROFILE_ID="atlasquant_ptbr_fixed_neural_male_v2"

_VOICE_PROFILE={
    "schema":SCHEMA,
    "id":VOICE_PROFILE_ID,
    "label":"AtlasQuant · voz neural oficial",
    "language":"pt-BR",
    "delivery_mode":"server_neural_tts",
    "provider":"openai",
    "model":"gpt-4o-mini-tts",
    "voice":"cedar",
    "external_style":"fixed_neural",
    "style":"masculina, grave, natural e acolhedora",
    "rate":0.96,
    "pitch":None,
    "volume":1.0,
    "quality_terms":["natural","neural","fixed","server"],
    "preferred_terms":[],
    "fallback_terms":[],
    "strict_fixed_voice":True,
    "allow_generic_device_fallback":False,
    "allow_browser_speech_synthesis":False,
    "fallback_behavior":"text_only",
    "automatic_playback":False,
    "provider_required":True,
    "ai_generated_disclosure_required":True,
    "trading_side_effects":False,
}


def voice_profile()->dict[str,Any]:
    """Return a defensive copy of the approved AtlasQuant voice preference."""
    out=dict(_VOICE_PROFILE)
    for key in ("quality_terms","preferred_terms","fallback_terms"):
        out[key]=list(_VOICE_PROFILE[key])
    return out


def voice_profile_ready()->bool:
    p=voice_profile()
    return bool(
        p["id"]==VOICE_PROFILE_ID
        and p["language"]=="pt-BR"
        and p["delivery_mode"]=="server_neural_tts"
        and p["provider"]=="openai"
        and p["model"]=="gpt-4o-mini-tts"
        and bool(p["voice"])
        and p["strict_fixed_voice"] is True
        and p["provider_required"] is True
        and p["allow_generic_device_fallback"] is False
        and p["allow_browser_speech_synthesis"] is False
        and p["fallback_behavior"]=="text_only"
        and p["automatic_playback"] is False
        and p["ai_generated_disclosure_required"] is True
        and p["trading_side_effects"] is False
    )



__all__=["SCHEMA","VOICE_PROFILE_ID","voice_profile","voice_profile_ready"]
