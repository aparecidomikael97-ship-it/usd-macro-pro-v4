"""Shared AtlasQuant voice profile.

This module defines the presentation-only voice preference used by browser/device
speech and by the optional external TTS request contract. It does not call a TTS
provider, fetch market data, change trading state, or execute orders.
"""
from __future__ import annotations

from typing import Any

SCHEMA="ATLASQUANT_VOICE_PROFILE_V1"
VOICE_PROFILE_ID="atlasquant_ptbr_neural_male_deep_v1"

_VOICE_PROFILE={
    "schema":SCHEMA,
    "id":VOICE_PROFILE_ID,
    "label":"AtlasQuant · masculina/grave",
    "language":"pt-BR",
    "external_style":"deep",
    "rate":0.93,
    "pitch":0.88,
    "volume":1.0,
    "quality_terms":["natural","neural","premium","enhanced"],
    "preferred_terms":["antonio","antônio","fabio","fábio","daniel","ricardo","thiago","male","masculino"],
    "fallback_terms":[],
    "strict_fixed_voice":True,
    "allow_generic_device_fallback":False,
    "fallback_behavior":"text_only",
    "automatic_playback":False,
    "provider_required":False,
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
        and p["external_style"]=="deep"
        and 0.80 <= float(p["pitch"]) < 1.0
        and 0.85 <= float(p["rate"]) <= 1.0
        and p["strict_fixed_voice"] is True
        and p["allow_generic_device_fallback"] is False
        and p["fallback_behavior"]=="text_only"
        and p["automatic_playback"] is False
        and p["trading_side_effects"] is False
    )


__all__=["SCHEMA","VOICE_PROFILE_ID","voice_profile","voice_profile_ready"]
