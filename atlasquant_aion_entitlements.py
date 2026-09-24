"""AION subscription entitlement registry contracts.

Pure/offline administrative layer. It separates account roles, billing events,
promotions and commercial access rights so AtlasQuant never treats one as proof
of another.

Important:
- creating or approving an entitlement request does not modify the user registry;
- provider-confirmed lifecycle states require concrete external evidence;
- activation is double-locked by ADMIN approval + feature flag + explicit action approval;
- this module never charges, creates accounts, changes roles or enables real trading.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import hashlib
import json
import re

from atlasquant_aion_core import guardian_decision, is_admin

SCHEMA="ATLASQUANT_AION_ENTITLEMENTS_V1"
MAX_ENTITLEMENTS=2000
SOURCE_KINDS=("MANUAL_GRANT","BILLING","PROMOTION")
STATUSES=(
    "DRAFT",
    "APPROVED",
    "PROVIDER_READY",
    "ACTIVE_CONFIRMED",
    "SUSPENDED_CONFIRMED",
    "EXPIRED_CONFIRMED",
    "REVOKED_CONFIRMED",
)
CONFIRMED_STATUSES=frozenset({
    "ACTIVE_CONFIRMED",
    "SUSPENDED_CONFIRMED",
    "EXPIRED_CONFIRMED",
    "REVOKED_CONFIRMED",
})
_SCOPE_RE=re.compile(r"^[A-Z0-9][A-Z0-9._:-]{1,63}$")


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def _text(value:Any,limit:int)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _parse_iso(value:Any)->datetime|None:
    raw=str(value or "").strip()
    if not raw:
        return None
    try:
        dt=datetime.fromisoformat(raw.replace("Z","+00:00"))
        if dt.tzinfo is None:
            dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _scope(value:Any)->str:
    raw=_text(value,64).upper().replace(" ","_")
    return raw if _SCOPE_RE.fullmatch(raw) else ""


def _source_kind(value:Any)->str:
    raw=_text(value,40).upper()
    return raw if raw in SOURCE_KINDS else "MANUAL_GRANT"


def _entitlement_id(subject_ref:str,scope:str,created_at:str)->str:
    raw=f"{subject_ref}|{scope}|{created_at}".encode("utf-8")
    return "ENT-"+hashlib.sha256(raw).hexdigest()[:14].upper()


def new_entitlement_request(
    subject_ref:Any,
    *,
    scope:Any="APP_ACCESS",
    source_kind:Any="MANUAL_GRANT",
    source_ref:Any="",
    starts_at:Any="",
    expires_at:Any="",
    note:Any="",
    created_at:str|None=None,
)->dict[str,Any]:
    subject=_text(subject_ref,120)
    normalized_scope=_scope(scope)
    if not subject:
        raise ValueError("subject_ref required")
    if not normalized_scope:
        raise ValueError("valid scope required")
    starts=_parse_iso(starts_at)
    expires=_parse_iso(expires_at)
    if starts and expires and expires<=starts:
        raise ValueError("entitlement expiry must be after start")
    created=str(created_at or _now())
    return {
        "schema":SCHEMA,
        "entitlement_id":_entitlement_id(subject,normalized_scope,created),
        "subject_ref":subject,
        "scope":normalized_scope,
        "source":{
            "kind":_source_kind(source_kind),
            "ref":_text(source_ref,220),
        },
        "window":{
            "starts_at":starts.isoformat() if starts else "",
            "expires_at":expires.isoformat() if expires else "",
        },
        "status":"DRAFT",
        "approval":{
            "approved":False,
            "approved_by":"",
            "approved_at":"",
        },
        "provider_evidence":{
            "confirmed":False,
            "provider":"",
            "external_id":"",
            "event_id":"",
            "confirmed_at":"",
        },
        "note":_text(note,600),
        "created_at":created,
        "updated_at":created,
        "effects":{
            "account_registry_changed":False,
            "role_changed":False,
            "payment_executed":False,
            "trading_permission_changed":False,
        },
    }


def normalize_entitlement(raw:Mapping[str,Any])->dict[str,Any]:
    if not isinstance(raw,Mapping):
        raise ValueError("invalid entitlement")
    subject=_text(raw.get("subject_ref"),120)
    scope=_scope(raw.get("scope"))
    if not subject or not scope:
        raise ValueError("entitlement subject/scope required")
    created=str(raw.get("created_at") or _now())
    source=raw.get("source") if isinstance(raw.get("source"),Mapping) else {}
    window=raw.get("window") if isinstance(raw.get("window"),Mapping) else {}
    approval=raw.get("approval") if isinstance(raw.get("approval"),Mapping) else {}
    evidence=raw.get("provider_evidence") if isinstance(raw.get("provider_evidence"),Mapping) else {}
    status=_text(raw.get("status"),40).upper()
    if status not in STATUSES:
        status="DRAFT"

    item={
        "schema":SCHEMA,
        "entitlement_id":_text(raw.get("entitlement_id"),72) or _entitlement_id(subject,scope,created),
        "subject_ref":subject,
        "scope":scope,
        "source":{
            "kind":_source_kind(source.get("kind")),
            "ref":_text(source.get("ref"),220),
        },
        "window":{
            "starts_at":_text(window.get("starts_at"),80),
            "expires_at":_text(window.get("expires_at"),80),
        },
        "status":status,
        "approval":{
            "approved":bool(approval.get("approved",False)),
            "approved_by":_text(approval.get("approved_by"),80),
            "approved_at":_text(approval.get("approved_at"),80),
        },
        "provider_evidence":{
            "confirmed":bool(evidence.get("confirmed",False)),
            "provider":_text(evidence.get("provider"),120),
            "external_id":_text(evidence.get("external_id"),220),
            "event_id":_text(evidence.get("event_id"),220),
            "confirmed_at":_text(evidence.get("confirmed_at"),80),
        },
        "note":_text(raw.get("note"),600),
        "created_at":created,
        "updated_at":str(raw.get("updated_at") or created),
        "effects":{
            "account_registry_changed":False,
            "role_changed":False,
            "payment_executed":False,
            "trading_permission_changed":False,
        },
    }

    has_evidence=bool(
        item["provider_evidence"]["confirmed"]
        and item["provider_evidence"]["provider"]
        and item["provider_evidence"]["external_id"]
    )
    if item["status"] in CONFIRMED_STATUSES and not (
        item["approval"]["approved"] and has_evidence
    ):
        item["status"]="APPROVED" if item["approval"]["approved"] else "DRAFT"
    return item


def normalize_entitlements(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[:MAX_ENTITLEMENTS*2]:
        try:
            item=normalize_entitlement(raw)
        except Exception:
            continue
        eid=item["entitlement_id"]
        if eid in seen:
            continue
        seen.add(eid)
        out.append(item)
        if len(out)>=MAX_ENTITLEMENTS:
            break
    return out


def upsert_entitlement(
    rows:Sequence[Mapping[str,Any]]|None,
    entitlement:Mapping[str,Any],
)->list[dict[str,Any]]:
    items=normalize_entitlements(rows)
    item=normalize_entitlement(entitlement)
    for idx,current in enumerate(items):
        if current["entitlement_id"]==item["entitlement_id"]:
            items[idx]=item
            return items
    if len(items)>=MAX_ENTITLEMENTS:
        raise ValueError("entitlement capacity reached")
    items.append(item)
    return items


def approve_entitlement_request(
    entitlement:Mapping[str,Any],
    access:Mapping[str,Any]|None,
)->dict[str,Any]:
    if not is_admin(access):
        raise PermissionError("ADMIN required")
    item=normalize_entitlement(entitlement)
    item["approval"]={
        "approved":True,
        "approved_by":_text((access or {}).get("username"),80) or "ADMIN",
        "approved_at":_now(),
    }
    item["status"]="APPROVED"
    item["updated_at"]=_now()
    return item


def entitlement_activation_preflight(
    entitlement:Mapping[str,Any],
    access:Mapping[str,Any]|None,
    *,
    feature_flags:Mapping[str,Any]|None=None,
    approved:bool=False,
)->dict[str,Any]:
    item=normalize_entitlement(entitlement)
    guardian=guardian_decision(
        "activate_entitlement",
        access,
        approved=approved,
        feature_flags=feature_flags,
    )
    request_approved=bool(item["approval"]["approved"])
    allowed=bool(request_approved and guardian["allowed"])
    if not request_approved:
        reason="Solicitação de entitlement ainda não foi aprovada pelo administrador."
    else:
        reason=guardian["reason"]
    return {
        "schema":SCHEMA,
        "entitlement_id":item["entitlement_id"],
        "allowed":allowed,
        "request_approved":request_approved,
        "guardian":guardian,
        "reason":reason,
        "executes_entitlement":False,
        "changes_account_registry":False,
        "changes_role":False,
    }


def mark_entitlement_from_provider_evidence(
    entitlement:Mapping[str,Any],
    evidence:Mapping[str,Any],
    *,
    status:Any="ACTIVE_CONFIRMED",
)->dict[str,Any]:
    item=normalize_entitlement(entitlement)
    if not item["approval"]["approved"]:
        raise ValueError("entitlement request must be approved first")
    target=_text(status,40).upper()
    if target not in CONFIRMED_STATUSES:
        raise ValueError("confirmed lifecycle status required")
    data=dict(evidence or {})
    provider=_text(data.get("provider"),120)
    external_id=_text(data.get("external_id"),220)
    confirmed=bool(data.get("confirmed",False))
    if not confirmed or not provider or not external_id:
        raise ValueError("confirmed provider entitlement evidence required")
    item["provider_evidence"]={
        "confirmed":True,
        "provider":provider,
        "external_id":external_id,
        "event_id":_text(data.get("event_id"),220),
        "confirmed_at":_text(data.get("confirmed_at"),80) or _now(),
    }
    item["status"]=target
    item["updated_at"]=_now()
    return item


def entitlement_effective(
    entitlement:Mapping[str,Any],
    *,
    now:datetime|None=None,
)->dict[str,Any]:
    item=normalize_entitlement(entitlement)
    current=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    starts=_parse_iso(item["window"]["starts_at"])
    expires=_parse_iso(item["window"]["expires_at"])
    reasons=[]
    if item["status"]!="ACTIVE_CONFIRMED":
        reasons.append("NOT_ACTIVE_CONFIRMED")
    if not item["provider_evidence"]["confirmed"]:
        reasons.append("PROVIDER_EVIDENCE_MISSING")
    if starts and current<starts:
        reasons.append("NOT_STARTED")
    if expires and current>=expires:
        reasons.append("EXPIRED")
    return {
        "schema":SCHEMA,
        "entitlement_id":item["entitlement_id"],
        "subject_ref":item["subject_ref"],
        "scope":item["scope"],
        "effective":not reasons,
        "reasons":reasons,
        "changes_account_registry":False,
        "changes_role":False,
    }


def entitlement_digest(rows:Sequence[Mapping[str,Any]]|None)->str:
    payload=normalize_entitlements(rows)
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def entitlement_summary(rows:Sequence[Mapping[str,Any]]|None)->dict[str,Any]:
    items=normalize_entitlements(rows)
    by_status={status:0 for status in STATUSES}
    effective=0
    for item in items:
        by_status[item["status"]]+=1
        if entitlement_effective(item)["effective"]:
            effective+=1
    return {
        "schema":SCHEMA,
        "records":len(items),
        "approved":by_status["APPROVED"],
        "active_confirmed":by_status["ACTIVE_CONFIRMED"],
        "effective_now":effective,
        "by_status":by_status,
    }


__all__=[
    "SCHEMA","SOURCE_KINDS","STATUSES","CONFIRMED_STATUSES",
    "new_entitlement_request","normalize_entitlement","normalize_entitlements",
    "upsert_entitlement","approve_entitlement_request",
    "entitlement_activation_preflight","mark_entitlement_from_provider_evidence",
    "entitlement_effective","entitlement_digest","entitlement_summary",
]
