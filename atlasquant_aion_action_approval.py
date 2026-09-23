"""AION explicit-approval envelope for external write actions.

Approval authorizes only the exact immutable payload for a short period. It
does not execute the provider action and never grants trading or money powers.
"""
from __future__ import annotations
from typing import Any,Mapping
from datetime import datetime,timezone,timedelta
import hashlib,json

SCHEMA="AION_ACTION_APPROVAL_V1"
DEFAULT_TTL_SECONDS=300

def _utc(value:datetime|None)->datetime:
    d=value or datetime.now(timezone.utc)
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)

def _payload_hash(provider:str,action_class:str,payload:Mapping[str,Any])->str:
    stable={
        "provider":str(provider or "").strip().lower(),
        "action_class":str(action_class or "").strip().upper(),
        "payload":dict(payload or {}),
    }
    raw=json.dumps(stable,sort_keys=True,separators=(",",":"),ensure_ascii=False,default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def build_pending_action(*,provider:str,action_class:str,payload:Mapping[str,Any],
                         now:datetime|None=None,ttl_seconds:int=DEFAULT_TTL_SECONDS)->dict[str,Any]:
    p=str(provider or "").strip().lower()
    a=str(action_class or "").strip().upper()
    if not p or not a or a=="READ":
        raise ValueError("pending approval requires external write-like action")
    try:
        ttl=int(ttl_seconds)
    except Exception as exc:
        raise ValueError("invalid ttl") from exc
    if ttl<30 or ttl>1800:
        raise ValueError("ttl out of range")
    current=_utc(now)
    digest=_payload_hash(p,a,payload)
    action_id="AION-ACT-"+hashlib.sha256(f"{digest}|{current.isoformat()}".encode("utf-8")).hexdigest()[:24]
    return {
        "schema":SCHEMA,
        "action_id":action_id,
        "provider":p,
        "action_class":a,
        "payload":dict(payload or {}),
        "payload_hash":digest,
        "state":"PENDING_APPROVAL",
        "created_at":current.isoformat(),
        "expires_at":(current+timedelta(seconds=ttl)).isoformat(),
        "approved":False,
        "approved_by":None,
        "approved_at":None,
        "executed":False,
        "real_orders_enabled":False,
        "voice_can_authorize_orders":False,
    }

def approve_pending_action(action:Mapping[str,Any],*,approved_by:str,now:datetime|None=None)->dict[str,Any]:
    out=dict(action or {})
    if out.get("schema")!=SCHEMA or out.get("state")!="PENDING_APPROVAL":
        raise ValueError("action not pending")
    who=" ".join(str(approved_by or "").strip().split())
    if not who:
        raise ValueError("approver required")
    current=_utc(now)
    try:
        expiry=datetime.fromisoformat(str(out.get("expires_at","")).replace("Z","+00:00"))
        if expiry.tzinfo is None:
            expiry=expiry.replace(tzinfo=timezone.utc)
        expiry=expiry.astimezone(timezone.utc)
    except Exception as exc:
        raise ValueError("invalid expiry") from exc
    if current>=expiry:
        raise ValueError("approval expired")
    expected=_payload_hash(out.get("provider",""),out.get("action_class",""),dict(out.get("payload",{}) or {}))
    if expected!=str(out.get("payload_hash","")):
        raise ValueError("payload changed")
    out.update({
        "state":"APPROVED_FOR_ADAPTER",
        "approved":True,
        "approved_by":who,
        "approved_at":current.isoformat(),
        "real_orders_enabled":False,
        "voice_can_authorize_orders":False,
    })
    return out

def validate_adapter_execution(action:Mapping[str,Any],*,provider:str,payload:Mapping[str,Any],
                               now:datetime|None=None)->dict[str,Any]:
    row=dict(action or {});reasons=[]
    current=_utc(now)
    if row.get("schema")!=SCHEMA:reasons.append("SCHEMA_INVALID")
    if row.get("state")!="APPROVED_FOR_ADAPTER" or row.get("approved") is not True:
        reasons.append("APPROVAL_MISSING")
    if str(row.get("provider",""))!=str(provider or "").strip().lower():
        reasons.append("PROVIDER_MISMATCH")
    expected=_payload_hash(provider,row.get("action_class",""),payload)
    if expected!=str(row.get("payload_hash","")):reasons.append("PAYLOAD_MISMATCH")
    try:
        expiry=datetime.fromisoformat(str(row.get("expires_at","")).replace("Z","+00:00"))
        if expiry.tzinfo is None:expiry=expiry.replace(tzinfo=timezone.utc)
        if current>=expiry.astimezone(timezone.utc):reasons.append("APPROVAL_EXPIRED")
    except Exception:
        reasons.append("EXPIRY_INVALID")
    if row.get("executed") is True:reasons.append("ALREADY_EXECUTED")
    return {
        "allowed":not reasons,
        "reasons":reasons,
        "action_id":row.get("action_id"),
        "real_orders_enabled":False,
        "voice_can_authorize_orders":False,
    }
