"""AION promotions and entitlement-preflight contracts.

Pure/offline administrative planning. Codes may be created and approved, but no
subscription/account entitlement is granted unless a future provider/registry
connector returns concrete confirmation evidence.

Security:
- public promo codes are generated with the secrets module;
- checkpoints store only SHA-256 code digests + last4, never the full code;
- activating a promotion is guarded behind feature flag + ADMIN approval;
- "ACTIVE" is reserved for confirmed provider evidence;
- redemptions never create AtlasQuant users or extend access by themselves.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import hashlib
import json
import secrets
import string

from atlasquant_aion_core import guardian_decision, is_admin

SCHEMA="ATLASQUANT_AION_PROMOTIONS_V1"
MAX_CAMPAIGNS=200
MAX_REDEMPTIONS=2000
BENEFIT_TYPES=("TRIAL_DAYS","PERCENT_OFF","FIXED_DISCOUNT")
STATUSES=("DRAFT","APPROVED","PROVIDER_READY","ACTIVE","DISABLED","EXPIRED")
ALPHABET="ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def _text(value:Any,limit:int)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _num(value:Any)->float:
    try:
        return max(0.0,float(value or 0))
    except Exception:
        return 0.0


def _int(value:Any,default:int=0)->int:
    try:
        return max(0,int(value))
    except Exception:
        return default


def _parse_iso(value:Any)->datetime|None:
    text=str(value or "").strip()
    if not text:
        return None
    try:
        dt=datetime.fromisoformat(text.replace("Z","+00:00"))
        if dt.tzinfo is None:
            dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def code_digest(code:Any)->str:
    normalized="".join(str(code or "").strip().upper().split())
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_promo_code(prefix:Any="AQ", length:int=10)->str:
    prefix_clean="".join(ch for ch in str(prefix or "AQ").upper() if ch in string.ascii_uppercase+string.digits)[:8]
    prefix_clean=prefix_clean or "AQ"
    size=max(6,min(24,int(length)))
    token="".join(secrets.choice(ALPHABET) for _ in range(size))
    return f"{prefix_clean}-{token}"


def _campaign_id(name:str,created_at:str)->str:
    raw=f"{name}|{created_at}".encode("utf-8")
    return "PROMO-"+hashlib.sha256(raw).hexdigest()[:12].upper()


def _benefit_payload(kind:Any,value:Any)->dict[str,Any]:
    benefit=str(kind or "TRIAL_DAYS").strip().upper()
    if benefit not in BENEFIT_TYPES:
        benefit="TRIAL_DAYS"
    if benefit=="TRIAL_DAYS":
        val=max(1,min(365,_int(value,7)))
    elif benefit=="PERCENT_OFF":
        val=max(1.0,min(100.0,_num(value)))
    else:
        val=round(_num(value),2)
    return {"type":benefit,"value":val}


def new_campaign(
    name:Any,
    *,
    benefit_type:Any="TRIAL_DAYS",
    benefit_value:Any=7,
    max_uses:Any=100,
    starts_at:Any="",
    expires_at:Any="",
    source:Any="ADMIN",
    created_at:str|None=None,
)->tuple[dict[str,Any],str]:
    """Create a campaign and return (record, one-time plaintext public code)."""
    name_clean=_text(name,220)
    if not name_clean:
        raise ValueError("campaign name required")
    uses=max(1,min(1_000_000,_int(max_uses,100)))
    created=str(created_at or _now())
    code=generate_promo_code("AQ",10)
    digest=code_digest(code)
    starts=_parse_iso(starts_at)
    expires=_parse_iso(expires_at)
    if starts and expires and expires<=starts:
        raise ValueError("campaign expiry must be after start")
    benefit=_benefit_payload(benefit_type,benefit_value)
    campaign={
        "schema":SCHEMA,
        "campaign_id":_campaign_id(name_clean,created),
        "name":name_clean,
        "benefit":benefit,
        "code":{
            "sha256":digest,
            "last4":code[-4:],
            "plaintext_stored":False,
        },
        "limits":{
            "max_uses":uses,
            "confirmed_uses":0,
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
        "provider_activation":{
            "confirmed":False,
            "provider":"",
            "external_id":"",
            "confirmed_at":"",
        },
        "source":_text(source,100) or "ADMIN",
        "created_at":created,
        "updated_at":created,
    }
    return campaign,code


def normalize_campaign(raw:Mapping[str,Any])->dict[str,Any]:
    if not isinstance(raw,Mapping):
        raise ValueError("invalid campaign")
    name=_text(raw.get("name"),220)
    if not name:
        raise ValueError("campaign name required")
    created=str(raw.get("created_at") or _now())
    benefit=raw.get("benefit") if isinstance(raw.get("benefit"),Mapping) else {}
    code=raw.get("code") if isinstance(raw.get("code"),Mapping) else {}
    limits=raw.get("limits") if isinstance(raw.get("limits"),Mapping) else {}
    window=raw.get("window") if isinstance(raw.get("window"),Mapping) else {}
    approval=raw.get("approval") if isinstance(raw.get("approval"),Mapping) else {}
    activation=raw.get("provider_activation") if isinstance(raw.get("provider_activation"),Mapping) else {}

    digest=str(code.get("sha256") or "").strip().lower()
    if digest and (len(digest)!=64 or any(ch not in string.hexdigits.lower() for ch in digest)):
        digest=""
    status=str(raw.get("status") or "DRAFT").strip().upper()
    if status not in STATUSES:
        status="DRAFT"
    campaign={
        "schema":SCHEMA,
        "campaign_id":_text(raw.get("campaign_id"),64) or _campaign_id(name,created),
        "name":name,
        "benefit":_benefit_payload(benefit.get("type"),benefit.get("value")),
        "code":{
            "sha256":digest,
            "last4":_text(code.get("last4"),4),
            "plaintext_stored":False,
        },
        "limits":{
            "max_uses":max(1,min(1_000_000,_int(limits.get("max_uses"),100))),
            "confirmed_uses":max(0,_int(limits.get("confirmed_uses"),0)),
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
        "provider_activation":{
            "confirmed":bool(activation.get("confirmed",False)),
            "provider":_text(activation.get("provider"),120),
            "external_id":_text(activation.get("external_id"),220),
            "confirmed_at":_text(activation.get("confirmed_at"),80),
        },
        "source":_text(raw.get("source"),100) or "ADMIN",
        "created_at":created,
        "updated_at":str(raw.get("updated_at") or created),
    }
    if campaign["limits"]["confirmed_uses"]>campaign["limits"]["max_uses"]:
        campaign["limits"]["confirmed_uses"]=campaign["limits"]["max_uses"]
    # ACTIVE is a provider-confirmed state, not an admin-local declaration.
    if campaign["status"]=="ACTIVE" and not (
        campaign["provider_activation"]["confirmed"]
        and campaign["provider_activation"]["provider"]
        and campaign["provider_activation"]["external_id"]
    ):
        campaign["status"]="APPROVED" if campaign["approval"]["approved"] else "DRAFT"
    return campaign


def normalize_campaigns(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[:MAX_CAMPAIGNS*2]:
        try:
            item=normalize_campaign(raw)
        except Exception:
            continue
        cid=item["campaign_id"]
        if cid in seen:
            continue
        seen.add(cid)
        out.append(item)
        if len(out)>=MAX_CAMPAIGNS:
            break
    return out


def upsert_campaign(
    rows:Sequence[Mapping[str,Any]]|None,
    campaign:Mapping[str,Any],
)->list[dict[str,Any]]:
    campaigns=normalize_campaigns(rows)
    item=normalize_campaign(campaign)
    for idx,current in enumerate(campaigns):
        if current["campaign_id"]==item["campaign_id"]:
            campaigns[idx]=item
            return campaigns
    if len(campaigns)>=MAX_CAMPAIGNS:
        raise ValueError("promotion capacity reached")
    campaigns.append(item)
    return campaigns


def approve_campaign(
    campaign:Mapping[str,Any],
    access:Mapping[str,Any]|None,
)->dict[str,Any]:
    if not is_admin(access):
        raise PermissionError("ADMIN required")
    item=normalize_campaign(campaign)
    if not item["code"]["sha256"]:
        raise ValueError("campaign has no code digest")
    item["approval"]={
        "approved":True,
        "approved_by":_text((access or {}).get("username"),80) or "ADMIN",
        "approved_at":_now(),
    }
    item["status"]="APPROVED"
    item["updated_at"]=_now()
    return item


def activation_preflight(
    campaign:Mapping[str,Any],
    access:Mapping[str,Any]|None,
    *,
    feature_flags:Mapping[str,Any]|None=None,
    approved:bool=False,
)->dict[str,Any]:
    item=normalize_campaign(campaign)
    guardian=guardian_decision(
        "activate_promotion",
        access,
        approved=approved,
        feature_flags=feature_flags,
    )
    campaign_approved=bool(item["approval"]["approved"])
    allowed=bool(campaign_approved and guardian["allowed"])
    if not campaign_approved:
        reason="Campanha ainda não foi aprovada pelo administrador."
    else:
        reason=guardian["reason"]
    return {
        "schema":SCHEMA,
        "campaign_id":item["campaign_id"],
        "allowed":allowed,
        "campaign_approved":campaign_approved,
        "guardian":guardian,
        "reason":reason,
        "executes_activation":False,
    }


def mark_active_from_provider_evidence(
    campaign:Mapping[str,Any],
    evidence:Mapping[str,Any],
)->dict[str,Any]:
    item=normalize_campaign(campaign)
    data=dict(evidence or {})
    provider=_text(data.get("provider"),120)
    external_id=_text(data.get("external_id"),220)
    confirmed=bool(data.get("confirmed",False))
    if not confirmed or not provider or not external_id:
        raise ValueError("confirmed provider activation evidence required")
    if not item["approval"]["approved"]:
        raise ValueError("campaign must be approved first")
    item["provider_activation"]={
        "confirmed":True,
        "provider":provider,
        "external_id":external_id,
        "confirmed_at":_text(data.get("confirmed_at"),80) or _now(),
    }
    item["status"]="ACTIVE"
    item["updated_at"]=_now()
    return item


def campaign_availability(
    campaign:Mapping[str,Any],
    *,
    code:Any,
    now:datetime|None=None,
)->dict[str,Any]:
    item=normalize_campaign(campaign)
    current=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    starts=_parse_iso(item["window"]["starts_at"])
    expires=_parse_iso(item["window"]["expires_at"])
    digest=code_digest(code)
    code_match=bool(digest and item["code"]["sha256"] and secrets.compare_digest(digest,item["code"]["sha256"]))
    reasons=[]
    if item["status"]!="ACTIVE":
        reasons.append("CAMPAIGN_NOT_ACTIVE")
    if not code_match:
        reasons.append("CODE_INVALID")
    if starts and current<starts:
        reasons.append("NOT_STARTED")
    if expires and current>=expires:
        reasons.append("EXPIRED")
    if item["limits"]["confirmed_uses"]>=item["limits"]["max_uses"]:
        reasons.append("MAX_USES_REACHED")
    return {
        "schema":SCHEMA,
        "campaign_id":item["campaign_id"],
        "available":not reasons,
        "reasons":reasons,
        "benefit":deepcopy(item["benefit"]),
        "executes_entitlement":False,
    }


def new_redemption_request(
    campaign:Mapping[str,Any],
    *,
    username:Any,
    code:Any,
    now:datetime|None=None,
)->dict[str,Any]:
    item=normalize_campaign(campaign)
    user=_text(username,64).lower()
    if not user:
        raise ValueError("username required")
    availability=campaign_availability(item,code=code,now=now)
    raw=f"{item['campaign_id']}|{user}|{_now()}".encode("utf-8")
    return {
        "schema":SCHEMA,
        "redemption_id":"REDEEM-"+hashlib.sha256(raw).hexdigest()[:14].upper(),
        "campaign_id":item["campaign_id"],
        "username":user,
        "available_preflight":availability["available"],
        "preflight_reasons":availability["reasons"],
        "benefit":deepcopy(item["benefit"]),
        "entitlement":{
            "granted":False,
            "provider":"",
            "external_id":"",
            "confirmed_at":"",
        },
        "created_at":_now(),
    }


def confirm_redemption_from_provider(
    request:Mapping[str,Any],
    evidence:Mapping[str,Any],
)->dict[str,Any]:
    row=deepcopy(dict(request or {}))
    data=dict(evidence or {})
    if not row.get("available_preflight"):
        raise ValueError("redemption preflight not available")
    provider=_text(data.get("provider"),120)
    external_id=_text(data.get("external_id"),220)
    confirmed=bool(data.get("confirmed",False))
    if not confirmed or not provider or not external_id:
        raise ValueError("confirmed entitlement evidence required")
    row["entitlement"]={
        "granted":True,
        "provider":provider,
        "external_id":external_id,
        "confirmed_at":_text(data.get("confirmed_at"),80) or _now(),
    }
    return row


def promotion_digest(
    campaigns:Sequence[Mapping[str,Any]]|None,
    redemptions:Sequence[Mapping[str,Any]]|None=None,
)->str:
    payload={
        "campaigns":normalize_campaigns(campaigns),
        "redemptions":[dict(x) for x in list(redemptions or [])[:MAX_REDEMPTIONS] if isinstance(x,Mapping)],
    }
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def promotions_summary(
    campaigns:Sequence[Mapping[str,Any]]|None,
    redemptions:Sequence[Mapping[str,Any]]|None=None,
)->dict[str,Any]:
    rows=normalize_campaigns(campaigns)
    reds=[dict(x) for x in list(redemptions or [])[:MAX_REDEMPTIONS] if isinstance(x,Mapping)]
    by_status={status:0 for status in STATUSES}
    for item in rows:
        by_status[item["status"]]+=1
    confirmed_redemptions=sum(
        1 for row in reds
        if bool((row.get("entitlement") or {}).get("granted",False))
    )
    return {
        "schema":SCHEMA,
        "campaigns":len(rows),
        "active":by_status["ACTIVE"],
        "approved":by_status["APPROVED"],
        "confirmed_redemptions":confirmed_redemptions,
        "by_status":by_status,
    }


__all__=[
    "SCHEMA","BENEFIT_TYPES","STATUSES","generate_promo_code","code_digest",
    "new_campaign","normalize_campaign","normalize_campaigns","upsert_campaign",
    "approve_campaign","activation_preflight","mark_active_from_provider_evidence",
    "campaign_availability","new_redemption_request","confirm_redemption_from_provider",
    "promotion_digest","promotions_summary",
]
