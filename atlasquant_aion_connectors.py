"""AION external platform connector contract.

Provider-neutral registry for integrations such as YouTube and Spotify.
Connections are user-authorized, scoped, auditable and fail closed.

This module does not contain credentials or make network calls.
"""
from __future__ import annotations
from typing import Any,Mapping

CONNECTOR_SCHEMA="AION_CONNECTORS_V1"

CONNECTORS={
    "youtube":{
        "display_name":"YouTube",
        "status":"PLANNED",
        "auth":"OAUTH",
        "read_capabilities":["SEARCH","VIDEO_METADATA","CHANNEL_METADATA","PLAYLIST_METADATA"],
        "write_capabilities":["PLAYLIST_WRITE","UPLOAD_OR_PUBLISH_WHEN_PROVIDER_ADAPTER_SUPPORTS"],
        "requires_confirmation_for_writes":True,
    },
    "spotify":{
        "display_name":"Spotify",
        "status":"PLANNED",
        "auth":"OAUTH",
        "read_capabilities":["SEARCH","LIBRARY_READ","PLAYLIST_READ","PLAYBACK_STATE_WHEN_SUPPORTED"],
        "write_capabilities":["PLAYLIST_WRITE","LIBRARY_WRITE","PLAYBACK_CONTROL_WHEN_SUPPORTED"],
        "requires_confirmation_for_writes":True,
    },
    "google_calendar":{
        "display_name":"Google Calendar",
        "status":"PLANNED",
        "auth":"OAUTH",
        "read_capabilities":["EVENT_READ"],
        "write_capabilities":["EVENT_CREATE","EVENT_UPDATE","EVENT_DELETE"],
        "requires_confirmation_for_writes":True,
    },
    "gmail":{
        "display_name":"Gmail",
        "status":"PLANNED",
        "auth":"OAUTH",
        "read_capabilities":["MAIL_READ","THREAD_READ"],
        "write_capabilities":["DRAFT_CREATE","MAIL_SEND","ARCHIVE_OR_LABEL"],
        "requires_confirmation_for_writes":True,
    },
    "google_drive":{
        "display_name":"Google Drive",
        "status":"PLANNED",
        "auth":"OAUTH",
        "read_capabilities":["FILE_SEARCH","FILE_READ"],
        "write_capabilities":["FILE_CREATE","FILE_UPDATE"],
        "requires_confirmation_for_writes":True,
    },
}

SENSITIVE_ACTION_CLASSES={"WRITE","PUBLISH","SEND","DELETE","MONEY","TRADING","SECURITY","ACCOUNT_CHANGE"}

def aion_connector_registry()->dict[str,Any]:
    return {
        "schema":CONNECTOR_SCHEMA,
        "assistant_name":"AION",
        "connections_are_user_authorized":True,
        "credentials_stored_in_prompt_or_model_context":False,
        "least_privilege_scopes":True,
        "audit_required":True,
        "connectors":{k:{**v,
            "read_capabilities":list(v["read_capabilities"]),
            "write_capabilities":list(v["write_capabilities"]),
        } for k,v in CONNECTORS.items()},
        "real_orders_enabled":False,
        "voice_can_authorize_orders":False,
    }

def connector_action_policy(provider:str,action_class:str,*,connected:bool)->dict[str,Any]:
    p=str(provider or "").strip().lower();a=str(action_class or "").strip().upper()
    if p not in CONNECTORS:
        return {"allowed":False,"reason":"CONNECTOR_UNKNOWN","confirmation_required":False}
    if not connected:
        return {"allowed":False,"reason":"CONNECTOR_NOT_CONNECTED","confirmation_required":False}
    confirmation=a in SENSITIVE_ACTION_CLASSES or a!="READ"
    if a in {"MONEY","TRADING"}:
        return {"allowed":False,"reason":"ACTION_CLASS_BLOCKED","confirmation_required":True,
                "real_orders_enabled":False,"voice_can_authorize_orders":False}
    return {
        "allowed":True,
        "reason":"CONFIRMATION_REQUIRED" if confirmation else "READ_ALLOWED",
        "confirmation_required":confirmation,
        "real_orders_enabled":False,
        "voice_can_authorize_orders":False,
    }

def sanitize_connector_context(raw:Mapping[str,Any]|None)->dict[str,Any]:
    """Remove credential-like fields before context can reach AION."""
    source=dict(raw or {})
    blocked={"access_token","refresh_token","client_secret","password","api_key","authorization","cookie","cookies"}
    clean={}
    for k,v in source.items():
        if str(k).strip().lower() in blocked:
            continue
        clean[k]=v
    return clean
