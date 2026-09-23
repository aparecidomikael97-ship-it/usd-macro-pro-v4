"""AtlasQuant Admin Voice identity contract.

Original PT-BR voice identity. This module stores product metadata only; it
does not clone or imitate any actor/person and performs no TTS network calls.
"""
from __future__ import annotations

ADMIN_VOICE_PROFILE={
    "profile_id":"ATLAS_VOICE_PT_BR_V1",
    "display_name":"AtlasQuant Admin",
    "language":"pt-BR",
    "voice_identity":"ORIGINAL_ATLASQUANT",
    "gender_presentation":"MASCULINE",
    "tone":["CALMO","SOFISTICADO","COMUNICATIVO","OBJETIVO","LEVEMENTE_FUTURISTA"],
    "modes":{
        "NORMAL":"amigável, natural e informativo",
        "SYSTEM_UPDATE":"objetivo e executivo",
        "IMPORTANT_ALERT":"mais firme, curto e sem alarmismo",
        "EDUCATIONAL":"didático e simples",
    },
    "imitates_public_figure_or_character":False,
    "real_orders_enabled":False,
    "voice_can_authorize_orders":False,
}

def admin_voice_profile()->dict:
    return {**ADMIN_VOICE_PROFILE,"tone":list(ADMIN_VOICE_PROFILE["tone"]),"modes":dict(ADMIN_VOICE_PROFILE["modes"])}
