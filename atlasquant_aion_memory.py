"""AION bounded session-memory utilities.

Memory here is conversational working context only. It is intentionally bounded,
redacts obvious credential fields, and never becomes trading authority.
"""
from __future__ import annotations
from typing import Any,Mapping,Sequence
from datetime import datetime,timezone
import hashlib

SCHEMA="AION_SESSION_MEMORY_V1"
ALLOWED_ROLES={"user","assistant"}
SENSITIVE_KEYS={
    "access_token","refresh_token","client_secret","password","api_key",
    "authorization","cookie","cookies","secret","token",
}

def _utc_iso(now:datetime|None=None)->str:
    d=now or datetime.now(timezone.utc)
    if d.tzinfo is None:
        d=d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).isoformat()

def _clean_text(value:Any,limit:int=6000)->str:
    return " ".join(str(value or "").strip().split())[:limit]

def sanitize_metadata(raw:Mapping[str,Any]|None)->dict[str,Any]:
    source=dict(raw or {})
    out={}
    for key,value in source.items():
        k=str(key).strip()
        if k.lower() in SENSITIVE_KEYS:
            continue
        if isinstance(value,Mapping):
            out[k]=sanitize_metadata(value)
        elif isinstance(value,(str,int,float,bool)) or value is None:
            out[k]=value
        elif isinstance(value,Sequence) and not isinstance(value,(str,bytes,bytearray)):
            out[k]=[
                sanitize_metadata(x) if isinstance(x,Mapping)
                else x for x in list(value)[:25]
                if isinstance(x,(Mapping,str,int,float,bool)) or x is None
            ]
        else:
            out[k]=str(value)[:500]
    return out

def append_memory(messages:Sequence[Mapping[str,Any]]|None,*,role:str,text:str,
                  metadata:Mapping[str,Any]|None=None,now:datetime|None=None,
                  max_messages:int=24)->list[dict[str,Any]]:
    r=str(role or "").strip().lower()
    if r not in ALLOWED_ROLES:
        raise ValueError("invalid memory role")
    clean=_clean_text(text)
    if not clean:
        raise ValueError("memory text required")
    try:
        limit=int(max_messages)
    except Exception as exc:
        raise ValueError("invalid max_messages") from exc
    if limit<2 or limit>100:
        raise ValueError("max_messages out of range")
    stamp=_utc_iso(now)
    item_id="MEM-"+hashlib.sha256(f"{r}|{clean}|{stamp}".encode("utf-8")).hexdigest()[:20]
    row={
        "schema":SCHEMA,
        "message_id":item_id,
        "role":r,
        "text":clean,
        "created_at":stamp,
        "metadata":sanitize_metadata(metadata),
        "real_orders_enabled":False,
        "voice_can_authorize_orders":False,
    }
    existing=[]
    for raw in messages or []:
        m=dict(raw or {})
        if str(m.get("role","")).lower() in ALLOWED_ROLES and _clean_text(m.get("text")):
            existing.append(m)
    existing.append(row)
    return existing[-limit:]

def memory_context(messages:Sequence[Mapping[str,Any]]|None,*,max_chars:int=12000)->list[dict[str,str]]:
    try:
        char_limit=int(max_chars)
    except Exception as exc:
        raise ValueError("invalid max_chars") from exc
    if char_limit<100 or char_limit>50000:
        raise ValueError("max_chars out of range")
    selected=[]
    used=0
    for raw in reversed(list(messages or [])):
        m=dict(raw or {})
        role=str(m.get("role","")).lower()
        text=_clean_text(m.get("text"))
        if role not in ALLOWED_ROLES or not text:
            continue
        cost=len(text)
        if used+cost>char_limit:
            continue
        selected.append({"role":role,"content":text})
        used+=cost
    selected.reverse()
    return selected
