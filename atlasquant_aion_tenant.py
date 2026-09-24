"""AION tenant-isolation contracts for future subscriber assistants.

This module prepares a safe boundary between the official ADMIN AION and future
per-subscriber "Meu AION" assistants.

Security principles:
- ADMIN canonical/project memory is never exposed to subscriber tenants;
- each authenticated credential receives an opaque, credential-bound namespace;
- password/credential rotation changes the namespace by design to prevent stale
  memory from silently following a replaced credential;
- personal AION eligibility requires a confirmed AION_PERSONAL entitlement;
- login role alone never grants a personal assistant;
- no provider calls, billing, publishing, account mutation or real trading occur here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import hashlib
import re

from atlasquant_access_control import normalize_role, normalize_username
from atlasquant_aion_entitlements import entitlement_effective, normalize_entitlements

SCHEMA="ATLASQUANT_AION_TENANT_V1"
PERSONAL_SCOPE="AION_PERSONAL"
ALLOWED_ROLES=frozenset({"USER","SALES"})
TENANT_DOMAINS=("central","trading","academy","support","account")
ADMIN_ONLY_DOMAINS=frozenset({
    "secretary","studio","business","laboratory","development","promotions","admin",
})
TENANT_ACTIONS=frozenset({
    "read_market",
    "explain_indicator",
    "explain_platform",
    "academy_help",
    "support_help",
    "read_own_account",
    "save_own_preferences",
})
FORBIDDEN_ACTIONS=frozenset({
    "read_admin_memory",
    "read_other_tenant",
    "manage_users",
    "approve_cost",
    "publish_social",
    "publish_marketplace",
    "activate_promotion",
    "activate_entitlement",
    "charge_customer",
    "deploy_production",
    "merge_main",
    "read_secret",
    "write_secret",
    "real_trade",
})
_SAFE_ID_RE=re.compile(r"^[a-f0-9]{32}$")


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def _session(access:Mapping[str,Any]|None)->dict[str,Any]:
    if not isinstance(access,Mapping):
        return {}
    raw=access.get("session")
    if isinstance(raw,Mapping):
        return dict(raw)
    # Some tests/callers may pass an already-authenticated session object.
    if access.get("username") and access.get("role"):
        return dict(access)
    return {}


def authenticated_subject(access:Mapping[str,Any]|None)->dict[str,str]:
    session=_session(access)
    username=normalize_username(session.get("username"))
    role=normalize_role(session.get("role"))
    fingerprint=str(session.get("credential_fingerprint") or "").strip().lower()
    if not username or role not in ALLOWED_ROLES:
        return {}
    if not re.fullmatch(r"[a-f0-9]{24,128}",fingerprint):
        return {}
    return {
        "username":username,
        "role":role,
        "credential_fingerprint":fingerprint,
    }


def tenant_namespace(access:Mapping[str,Any]|None)->dict[str,Any]:
    subject=authenticated_subject(access)
    if not subject:
        return {
            "schema":SCHEMA,
            "ready":False,
            "tenant_id":"",
            "namespace":"",
            "reason":"AUTHENTICATED_USER_OR_SALES_SESSION_REQUIRED",
        }
    raw=(
        "atlasquant-aion-tenant-v1|"
        +subject["username"]+"|"
        +subject["credential_fingerprint"]
    ).encode("utf-8")
    tenant_id=hashlib.sha256(raw).hexdigest()[:32]
    return {
        "schema":SCHEMA,
        "ready":True,
        "tenant_id":tenant_id,
        "namespace":f"tenant/{tenant_id}",
        "reason":"OK",
        "role":subject["role"],
        "username":subject["username"],
        "credential_bound":True,
    }


def tenant_runtime_path(access:Mapping[str,Any]|None)->str:
    ns=tenant_namespace(access)
    if not ns["ready"] or not _SAFE_ID_RE.fullmatch(str(ns["tenant_id"])):
        return ""
    return f"dados/aion/tenants/{ns['tenant_id']}/checkpoint.json"


def matching_personal_entitlements(
    access:Mapping[str,Any]|None,
    entitlements:Sequence[Mapping[str,Any]]|None,
)->list[dict[str,Any]]:
    subject=authenticated_subject(access)
    if not subject:
        return []
    rows=normalize_entitlements(entitlements)
    return [
        row for row in rows
        if str(row.get("subject_ref") or "").strip().casefold()==subject["username"].casefold()
        and str(row.get("scope") or "").strip().upper()==PERSONAL_SCOPE
    ]


def personal_aion_eligibility(
    access:Mapping[str,Any]|None,
    entitlements:Sequence[Mapping[str,Any]]|None,
    *,
    now:datetime|None=None,
)->dict[str,Any]:
    ns=tenant_namespace(access)
    if not ns["ready"]:
        return {
            "schema":SCHEMA,
            "eligible":False,
            "reason":ns["reason"],
            "tenant_id":"",
            "effective_entitlement_ids":[],
            "admin_memory_access":False,
            "other_tenant_access":False,
        }
    matches=matching_personal_entitlements(access,entitlements)
    effective=[]
    for row in matches:
        result=entitlement_effective(row,now=now)
        if result["effective"]:
            effective.append(str(row.get("entitlement_id") or ""))
    eligible=bool(effective)
    return {
        "schema":SCHEMA,
        "eligible":eligible,
        "reason":"CONFIRMED_AION_PERSONAL_ENTITLEMENT" if eligible else "AION_PERSONAL_ENTITLEMENT_REQUIRED",
        "tenant_id":ns["tenant_id"],
        "namespace":ns["namespace"],
        "runtime_path":tenant_runtime_path(access),
        "effective_entitlement_ids":effective,
        "admin_memory_access":False,
        "other_tenant_access":False,
        "provider_enabled":False,
        "real_trading_enabled":False,
    }


def tenant_domain_allowed(domain:Any)->bool:
    raw=str(domain or "").strip().casefold()
    return raw in TENANT_DOMAINS


def tenant_action_decision(
    action:Any,
    access:Mapping[str,Any]|None,
    entitlements:Sequence[Mapping[str,Any]]|None,
    *,
    now:datetime|None=None,
)->dict[str,Any]:
    key=str(action or "").strip().casefold()
    eligibility=personal_aion_eligibility(access,entitlements,now=now)
    if not eligibility["eligible"]:
        return {
            "schema":SCHEMA,
            "allowed":False,
            "action":key,
            "reason":eligibility["reason"],
            "executes_external_action":False,
        }
    if key in FORBIDDEN_ACTIONS:
        return {
            "schema":SCHEMA,
            "allowed":False,
            "action":key,
            "reason":"ACTION_RESERVED_OR_FORBIDDEN",
            "executes_external_action":False,
        }
    if key not in TENANT_ACTIONS:
        return {
            "schema":SCHEMA,
            "allowed":False,
            "action":key,
            "reason":"UNKNOWN_TENANT_ACTION",
            "executes_external_action":False,
        }
    return {
        "schema":SCHEMA,
        "allowed":True,
        "action":key,
        "reason":"LOCAL_TENANT_ACTION_ALLOWED",
        "executes_external_action":False,
    }


def tenant_memory_seed(access:Mapping[str,Any]|None)->dict[str,Any]:
    ns=tenant_namespace(access)
    if not ns["ready"]:
        raise ValueError("authenticated tenant session required")
    return {
        "schema":SCHEMA,
        "tenant_id":ns["tenant_id"],
        "namespace":ns["namespace"],
        "created_at":_now(),
        "updated_at":_now(),
        "profile":{
            "display_name":"",
            "experience_level":"",
            "preferences":{},
        },
        "conversation_notes":[],
        "academy_progress":{},
        "watchlist":[],
        "truth_policy":"never_invent",
        "privacy":{
            "admin_memory_inherited":False,
            "project_docs_inherited":False,
            "other_tenant_memory_visible":False,
            "credential_bound_namespace":True,
        },
        "permissions":{
            "domains":list(TENANT_DOMAINS),
            "actions":sorted(TENANT_ACTIONS),
            "external_publish":False,
            "billing":False,
            "admin":False,
            "real_trading":False,
        },
    }


def sanitize_tenant_memory(raw:Mapping[str,Any]|None, access:Mapping[str,Any]|None)->dict[str,Any]:
    seed=tenant_memory_seed(access)
    data=dict(raw or {})
    if str(data.get("tenant_id") or "") != seed["tenant_id"]:
        return seed

    profile=data.get("profile") if isinstance(data.get("profile"),Mapping) else {}
    preferences=profile.get("preferences") if isinstance(profile.get("preferences"),Mapping) else {}
    safe_preferences={}
    for key,value in list(preferences.items())[:50]:
        k=str(key or "").strip()[:64]
        if not k:
            continue
        if isinstance(value,(str,int,float,bool)) or value is None:
            safe_preferences[k]=value

    notes=[]
    for row in list(data.get("conversation_notes") or [])[:200]:
        if not isinstance(row,Mapping):
            continue
        text=" ".join(str(row.get("text") or "").replace("\x00","").split())[:1000]
        if text:
            notes.append({
                "text":text,
                "created_at":str(row.get("created_at") or "")[:80],
                "truth_state":str(row.get("truth_state") or "UNKNOWN").upper()
                if str(row.get("truth_state") or "").upper() in {"CONFIRMED","INFERENCE","HYPOTHESIS","UNKNOWN"}
                else "UNKNOWN",
            })

    academy=data.get("academy_progress") if isinstance(data.get("academy_progress"),Mapping) else {}
    watchlist=[]
    for item in list(data.get("watchlist") or [])[:100]:
        symbol="".join(ch for ch in str(item or "").upper() if ch.isalnum() or ch in "._-/")[:24]
        if symbol and symbol not in watchlist:
            watchlist.append(symbol)

    seed["profile"]={
        "display_name":" ".join(str(profile.get("display_name") or "").split())[:80],
        "experience_level":" ".join(str(profile.get("experience_level") or "").split())[:40],
        "preferences":safe_preferences,
    }
    seed["conversation_notes"]=notes
    seed["academy_progress"]={
        str(k)[:80]:v for k,v in list(academy.items())[:200]
        if isinstance(v,(str,int,float,bool)) or v is None
    }
    seed["watchlist"]=watchlist
    seed["updated_at"]=_now()
    return seed


def cross_tenant_access_allowed(
    requester_access:Mapping[str,Any]|None,
    target_tenant_id:Any,
)->bool:
    ns=tenant_namespace(requester_access)
    return bool(
        ns["ready"]
        and str(target_tenant_id or "")==str(ns["tenant_id"])
    )


def tenant_prompt_contract(access:Mapping[str,Any]|None)->dict[str,Any]:
    ns=tenant_namespace(access)
    if not ns["ready"]:
        return {
            "schema":SCHEMA,
            "ready":False,
            "system_rules":[],
        }
    return {
        "schema":SCHEMA,
        "ready":True,
        "tenant_id":ns["tenant_id"],
        "system_rules":[
            "Nunca inventar fatos, integrações, resultados ou estados.",
            "Usar somente memória do próprio tenant e contexto explicitamente fornecido à sessão.",
            "Nunca expor memória canônica do AION ADMIN, documentos privados do projeto ou dados de outro tenant.",
            "Nunca executar publicação, cobrança, administração de contas, deploy ou trading real.",
            "Dados de mercado só podem ser chamados de atuais quando houver fonte fresca confirmada.",
        ],
        "admin_memory_access":False,
        "other_tenant_access":False,
        "external_provider_enabled_by_default":False,
        "real_trading_enabled":False,
    }


__all__=[
    "SCHEMA","PERSONAL_SCOPE","TENANT_DOMAINS","TENANT_ACTIONS","FORBIDDEN_ACTIONS",
    "authenticated_subject","tenant_namespace","tenant_runtime_path",
    "matching_personal_entitlements","personal_aion_eligibility",
    "tenant_domain_allowed","tenant_action_decision","tenant_memory_seed",
    "sanitize_tenant_memory","cross_tenant_access_allowed","tenant_prompt_contract",
]
