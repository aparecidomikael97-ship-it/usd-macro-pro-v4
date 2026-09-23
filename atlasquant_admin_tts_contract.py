"""Provider-neutral TTS contract for the original AtlasQuant Admin voice.

No provider credentials or network calls live here. Production adapters must
honor this contract and return audio without changing trading state.
"""
from __future__ import annotations
from typing import Any,Mapping
import hashlib

VOICE_CONTRACT_VERSION="AION_ADMIN_TTS_V1"

def build_admin_tts_request(text:str,*,mode:str="SYSTEM_UPDATE")->dict[str,Any]:
    clean=" ".join(str(text or "").strip().split())
    if not clean: raise ValueError("voice text required")
    if len(clean)>6000: raise ValueError("voice text too long")
    m=str(mode or "SYSTEM_UPDATE").upper()
    if m not in {"NORMAL","SYSTEM_UPDATE","IMPORTANT_ALERT","EDUCATIONAL"}: raise ValueError("invalid voice mode")
    request_id="TTS-"+hashlib.sha256(f"{VOICE_CONTRACT_VERSION}|{m}|{clean}".encode("utf-8")).hexdigest()[:24]
    return {
        "schema":VOICE_CONTRACT_VERSION,
        "request_id":request_id,
        "profile_id":"AION_VOICE_PT_BR_V1",
        "language":"pt-BR",
        "text":clean,
        "mode":m,
        "style":{
            "identity":"ORIGINAL_AION_ATLAS_CODE",
            "presentation":"masculina",
            "delivery":"calma, sofisticada, comunicativa, objetiva e levemente futurista",
            "pronunciation":"Português natural do Brasil",
            "pace":"moderado",
            "alert_behavior":"mais firme e curto, sem alarmismo",
        },
        "imitate_person_or_character":False,
        "voice_can_authorize_orders":False,
        "real_orders_enabled":False,
    }

def validate_admin_tts_response(request:Mapping[str,Any],response:Mapping[str,Any])->dict[str,Any]:
    req=dict(request or {});res=dict(response or {});reasons=[]
    if req.get("schema")!=VOICE_CONTRACT_VERSION:reasons.append("REQUEST_SCHEMA_INVALID")
    if str(res.get("request_id",""))!=str(req.get("request_id","")):reasons.append("REQUEST_ID_MISMATCH")
    if str(res.get("language",""))!="pt-BR":reasons.append("LANGUAGE_INVALID")
    if not str(res.get("audio_ref","")).strip():reasons.append("AUDIO_REF_MISSING")
    if res.get("imitated_person_or_character") is not False:reasons.append("VOICE_IDENTITY_INVALID")
    return {"ok":not reasons,"reasons":reasons,"request_id":req.get("request_id"),
            "voice_can_authorize_orders":False,"real_orders_enabled":False}
