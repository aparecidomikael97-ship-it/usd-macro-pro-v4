"""AION Sovereignty & Resilience Core.

Deterministic contracts for authority, delegated agents, watchdogs, circuit
breakers, resource budgets and safe-mode posture.

This module does NOT execute tools, kill processes, disable security products,
change credentials, deploy, publish, charge money or enable real trading.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

from atlasquant_aion_fortress import source_authority

SCHEMA="ATLASQUANT_AION_RESILIENCE_V1"

PRINCIPALS=(
    "SYSTEM_POLICY","ADMIN","AION_CORE","AGENT","EXTERNAL_AI","TOOL","WORKSPACE","UNKNOWN"
)
CAPABILITIES=(
    "READ_CONTEXT","SEARCH","DRAFT","TEST_SANDBOX","WRITE_CHECKPOINT",
    "WRITE_CODE_SANDBOX","PUBLISH_EXTERNAL","MERGE_MAIN","DEPLOY_PRODUCTION",
    "WRITE_SECRET","CHARGE_CUSTOMER","REAL_TRADING","CHANGE_POLICY",
    "EXPAND_PERMISSIONS","DISABLE_SECURITY",
)
NON_DELEGABLE=frozenset({
    "REAL_TRADING","WRITE_SECRET","CHARGE_CUSTOMER","MERGE_MAIN",
    "DEPLOY_PRODUCTION","CHANGE_POLICY","EXPAND_PERMISSIONS","DISABLE_SECURITY",
})
CIRCUIT_STATES=("CLOSED","OPEN","HALF_OPEN")
WATCHDOG_STATES=("HEALTHY","DEGRADED","ISOLATE_RECOMMENDED")
SAFE_MODES=("NORMAL","DEGRADED_READ_ONLY","EMERGENCY_STOP_RECOMMENDED")


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value:Any,limit:int=1000)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _upper(value:Any,limit:int=100)->str:
    return _clean(value,limit).upper()


def _finite(value:Any,default:float=0.0)->float:
    try:
        x=float(value)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _int(value:Any,default:int=0,minimum:int=0,maximum:int=1_000_000)->int:
    try:
        x=int(value)
    except Exception:
        x=int(default)
    return max(minimum,min(maximum,x))


def _refs(values:Sequence[Any]|None,limit:int=80)->list[str]:
    out=[]
    for raw in list(values or [])[:limit*2]:
        text=_clean(raw,240)
        if text and text not in out:
            out.append(text)
        if len(out)>=limit:
            break
    return out


def _caps(values:Sequence[Any]|None)->list[str]:
    out=[]
    for raw in list(values or [])[:100]:
        cap=_upper(raw,80)
        if cap in CAPABILITIES and cap not in out:
            out.append(cap)
    return out


def _digest(value:Any,length:int=24)->str:
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:length]


def principal_authority(
    principal_kind:Any,
    *,
    authenticated_admin:bool=False,
    signed_system_policy:bool=False,
)->dict[str,Any]:
    kind=_upper(principal_kind,80)
    if kind not in PRINCIPALS:
        kind="UNKNOWN"
    if kind=="AION_CORE":
        return {
            "schema":SCHEMA,
            "principal_kind":kind,
            "root_authority":False,
            "may_orchestrate_delegated_agents":True,
            "may_expand_own_permissions":False,
            "may_change_policy":False,
            "reason":"AION_CORE pode orquestrar apenas dentro das permissões herdadas e do Guardian.",
        }
    if kind=="AGENT":
        return {
            "schema":SCHEMA,
            "principal_kind":kind,
            "root_authority":False,
            "may_orchestrate_delegated_agents":False,
            "may_expand_own_permissions":False,
            "may_change_policy":False,
            "reason":"Agente só atua por delegação explícita e limitada.",
        }
    if kind=="EXTERNAL_AI":
        return {
            "schema":SCHEMA,
            "principal_kind":kind,
            "root_authority":False,
            "may_orchestrate_delegated_agents":False,
            "may_expand_own_permissions":False,
            "may_change_policy":False,
            "reason":"IA externa é conteúdo/worker delegado, nunca autoridade raiz.",
        }
    base=source_authority(
        "ADMIN" if kind=="ADMIN" else "SYSTEM_POLICY" if kind=="SYSTEM_POLICY" else "UNKNOWN",
        authenticated_admin=authenticated_admin,
        signed_system_policy=signed_system_policy,
    )
    return {
        "schema":SCHEMA,
        "principal_kind":kind,
        "root_authority":bool(base.get("can_issue_action",False)),
        "may_orchestrate_delegated_agents":kind in {"ADMIN","SYSTEM_POLICY"} and bool(base.get("can_issue_action",False)),
        "may_expand_own_permissions":False,
        "may_change_policy":bool(kind=="SYSTEM_POLICY" and signed_system_policy),
        "reason":str(base.get("reason") or ""),
    }


def new_delegation(
    *,
    issuer_kind:Any,
    subject_kind:Any,
    subject_ref:Any,
    workspace_id:Any,
    requested_capabilities:Sequence[Any]|None,
    issuer_capabilities:Sequence[Any]|None,
    authenticated_admin:bool=False,
    signed_system_policy:bool=False,
    scope:Any="",
    evidence_refs:Sequence[Any]|None=None,
    created_at:str|None=None,
)->dict[str,Any]:
    issuer=_upper(issuer_kind,80)
    subject=_upper(subject_kind,80)
    if issuer not in PRINCIPALS or subject not in PRINCIPALS:
        raise ValueError("invalid delegation principal")
    authority=principal_authority(
        issuer,
        authenticated_admin=authenticated_admin,
        signed_system_policy=signed_system_policy,
    )
    parent=set(_caps(issuer_capabilities))
    requested=_caps(requested_capabilities)
    scope_text=_clean(scope,1000)
    refs=_refs(evidence_refs)
    blockers=[]
    if issuer not in {"ADMIN","SYSTEM_POLICY","AION_CORE"}:
        blockers.append("ISSUER_CANNOT_DELEGATE")
    if issuer in {"ADMIN","SYSTEM_POLICY"} and not authority["root_authority"]:
        blockers.append("ISSUER_NOT_AUTHENTICATED")
    if issuer=="AION_CORE" and not parent:
        blockers.append("AION_PARENT_CAPABILITIES_MISSING")
    if not scope_text:
        blockers.append("SCOPE_MISSING")
    if not refs:
        blockers.append("EVIDENCE_MISSING")

    granted=[]
    for cap in requested:
        if cap in NON_DELEGABLE:
            blockers.append(f"NON_DELEGABLE:{cap}")
            continue
        if issuer=="AION_CORE" and cap not in parent:
            blockers.append(f"CAPABILITY_NOT_IN_PARENT:{cap}")
            continue
        if issuer in {"ADMIN","SYSTEM_POLICY"} and parent and cap not in parent:
            blockers.append(f"CAPABILITY_NOT_IN_PARENT:{cap}")
            continue
        granted.append(cap)

    payload={
        "issuer_kind":issuer,
        "subject_kind":subject,
        "subject_ref":_clean(subject_ref,160),
        "workspace_id":_clean(workspace_id,120).lower(),
        "requested_capabilities":requested,
        "granted_capabilities":granted,
        "scope":scope_text,
        "evidence_refs":refs,
        "created_at":str(created_at or _now()),
    }
    return {
        "schema":SCHEMA,
        "delegation_id":"DEL-"+_digest(payload,16).upper(),
        **payload,
        "state":"BLOCKED" if blockers else "ACTIVE",
        "blockers":list(dict.fromkeys(blockers)),
        "root_authority_granted":False,
        "may_expand_permissions":False,
        "may_change_policy":False,
        "direct_real_trading":False,
        "executes_action":False,
    }


def agent_firewall(
    *,
    source_kind:Any,
    requested_capability:Any,
    workspace_id:Any,
    delegation:Mapping[str,Any]|None=None,
    authenticated_admin:bool=False,
    signed_system_policy:bool=False,
)->dict[str,Any]:
    kind=_upper(source_kind,80)
    cap=_upper(requested_capability,80)
    workspace=_clean(workspace_id,120).lower()
    blockers=[]
    root=principal_authority(
        kind,
        authenticated_admin=authenticated_admin,
        signed_system_policy=signed_system_policy,
    )

    if cap not in CAPABILITIES:
        blockers.append("UNKNOWN_CAPABILITY")
    if cap in NON_DELEGABLE and kind not in {"ADMIN","SYSTEM_POLICY"}:
        blockers.append("SENSITIVE_CAPABILITY_NOT_DELEGABLE")

    delegated=False
    if kind in {"AGENT","EXTERNAL_AI","AION_CORE"}:
        d=dict(delegation or {})
        delegated=bool(
            d.get("state")=="ACTIVE"
            and cap in list(d.get("granted_capabilities") or [])
            and str(d.get("workspace_id") or "").lower()==workspace
        )
        if not delegated:
            blockers.append("VALID_DELEGATION_REQUIRED")

    if kind=="EXTERNAL_AI":
        # External models may produce delegated content, never directly control tools.
        blockers.append("EXTERNAL_AI_DIRECT_TOOL_CONTROL_BLOCKED")

    if kind in {"ADMIN","SYSTEM_POLICY"} and not root["root_authority"]:
        blockers.append("ROOT_AUTHENTICATION_REQUIRED")

    state="BLOCK" if blockers else "PASS_TO_GUARDIAN"
    return {
        "schema":SCHEMA,
        "state":state,
        "source_kind":kind,
        "requested_capability":cap,
        "workspace_id":workspace,
        "delegated":delegated,
        "blockers":list(dict.fromkeys(blockers)),
        "must_still_pass_guardian":True,
        "must_still_pass_proof_of_safety":cap not in {"READ_CONTEXT","SEARCH"},
        "tool_called":False,
        "permission_expanded":False,
        "real_trading_enabled":False,
    }


def circuit_breaker(
    component:Any,
    *,
    previous_state:Any="CLOSED",
    consecutive_failures:Any=0,
    error_rate_pct:Any=0,
    critical_signal:bool=False,
    recovery_probe_passed:bool=False,
)->dict[str,Any]:
    name=_clean(component,160)
    prev=_upper(previous_state,40)
    if prev not in CIRCUIT_STATES:
        prev="CLOSED"
    failures=_int(consecutive_failures,0,0,10000)
    error_rate=max(0.0,min(100.0,_finite(error_rate_pct,0.0)))
    reasons=[]

    if critical_signal:
        state="OPEN"
        reasons.append("CRITICAL_SIGNAL")
    elif failures>=3:
        state="OPEN"
        reasons.append("CONSECUTIVE_FAILURE_LIMIT")
    elif error_rate>=50.0:
        state="OPEN"
        reasons.append("ERROR_RATE_LIMIT")
    elif prev=="OPEN" and recovery_probe_passed:
        state="HALF_OPEN"
        reasons.append("RECOVERY_PROBE_PASSED")
    elif prev=="HALF_OPEN" and recovery_probe_passed and failures==0 and error_rate<10:
        state="CLOSED"
        reasons.append("RECOVERY_CONFIRMED")
    elif prev in {"OPEN","HALF_OPEN"}:
        state=prev
        reasons.append("CIRCUIT_REMAINS_RESTRICTED")
    else:
        state="CLOSED"

    return {
        "schema":SCHEMA,
        "component":name,
        "state":state,
        "consecutive_failures":failures,
        "error_rate_pct":round(error_rate,2),
        "reasons":reasons,
        "sensitive_calls_allowed":state=="CLOSED",
        "automatic_restart":False,
        "automatic_destructive_action":False,
        "executes_action":False,
    }


def watchdog(
    component:Any,
    *,
    heartbeat_age_seconds:Any,
    stale_after_seconds:Any=300,
    repeated_action_count:Any=0,
    loop_limit:Any=5,
    unhandled_error_count:Any=0,
    error_limit:Any=3,
)->dict[str,Any]:
    age=max(0.0,_finite(heartbeat_age_seconds,1e9))
    stale=max(1.0,_finite(stale_after_seconds,300))
    repeated=_int(repeated_action_count,0,0,100000)
    loop_max=max(1,_int(loop_limit,5,1,100000))
    errors=_int(unhandled_error_count,0,0,100000)
    error_max=max(1,_int(error_limit,3,1,100000))
    signals=[]
    if age>stale:
        signals.append("HEARTBEAT_STALE")
    if repeated>=loop_max:
        signals.append("LOOP_SUSPECTED")
    if errors>=error_max:
        signals.append("ERROR_LIMIT_REACHED")
    if "LOOP_SUSPECTED" in signals or "ERROR_LIMIT_REACHED" in signals:
        state="ISOLATE_RECOMMENDED"
    elif signals:
        state="DEGRADED"
    else:
        state="HEALTHY"
    return {
        "schema":SCHEMA,
        "component":_clean(component,160),
        "state":state,
        "signals":signals,
        "heartbeat_age_seconds":round(age,2),
        "repeated_action_count":repeated,
        "unhandled_error_count":errors,
        "recommended_action":(
            "ISOLATE_AND_REVIEW" if state=="ISOLATE_RECOMMENDED"
            else "READ_ONLY_DIAGNOSTIC" if state=="DEGRADED"
            else "NONE"
        ),
        "automatic_kill":False,
        "automatic_delete":False,
        "executes_action":False,
    }


def resource_governor(
    component:Any,
    *,
    call_limit:Any=100,
    calls_used:Any=0,
    token_limit:Any=100000,
    tokens_used:Any=0,
    wall_seconds_limit:Any=300,
    wall_seconds_used:Any=0,
    memory_mb_limit:Any=1024,
    memory_mb_used:Any=0,
)->dict[str,Any]:
    pairs={
        "calls":(_finite(calls_used,0),max(1.0,_finite(call_limit,100))),
        "tokens":(_finite(tokens_used,0),max(1.0,_finite(token_limit,100000))),
        "wall_seconds":(_finite(wall_seconds_used,0),max(1.0,_finite(wall_seconds_limit,300))),
        "memory_mb":(_finite(memory_mb_used,0),max(1.0,_finite(memory_mb_limit,1024))),
    }
    ratios={k:max(0.0,v[0])/v[1] for k,v in pairs.items()}
    max_ratio=max(ratios.values()) if ratios else 0.0
    if max_ratio>=1.0:
        state="CIRCUIT_BREAK"
    elif max_ratio>=0.8:
        state="THROTTLE"
    else:
        state="WITHIN_BUDGET"
    return {
        "schema":SCHEMA,
        "component":_clean(component,160),
        "state":state,
        "usage_pct":{k:round(v*100,2) for k,v in ratios.items()},
        "max_usage_pct":round(max_ratio*100,2),
        "allow_new_sensitive_work":state=="WITHIN_BUDGET",
        "automatic_paid_upgrade":False,
        "automatic_permission_expansion":False,
        "executes_action":False,
    }


def safe_mode_posture(
    *,
    authority_integrity_ok:bool=True,
    policy_integrity_ok:bool=True,
    secret_exposure:bool=False,
    open_circuits:Any=0,
    isolate_recommendations:Any=0,
)->dict[str,Any]:
    circuits=_int(open_circuits,0,0,100000)
    isolates=_int(isolate_recommendations,0,0,100000)
    reasons=[]
    if not authority_integrity_ok:
        reasons.append("AUTHORITY_INTEGRITY_FAILED")
    if not policy_integrity_ok:
        reasons.append("POLICY_INTEGRITY_FAILED")
    if secret_exposure:
        reasons.append("SECRET_EXPOSURE")
    if circuits:
        reasons.append("OPEN_CIRCUITS")
    if isolates:
        reasons.append("ISOLATION_RECOMMENDED")

    if (
        not authority_integrity_ok
        or not policy_integrity_ok
        or secret_exposure
    ):
        mode="EMERGENCY_STOP_RECOMMENDED"
    elif circuits or isolates:
        mode="DEGRADED_READ_ONLY"
    else:
        mode="NORMAL"

    return {
        "schema":SCHEMA,
        "mode":mode,
        "reasons":reasons,
        "read_allowed":True,
        "diagnostics_allowed":True,
        "sensitive_tools_allowed":mode=="NORMAL",
        "external_side_effects_allowed":False,
        "real_trading_enabled":False,
        "automatic_destructive_action":False,
        "requires_independent_controller_for_kill_switch":True,
        "executes_action":False,
    }


def normalize_delegations(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[-500:]:
        if not isinstance(raw,Mapping):
            continue
        did=_clean(raw.get("delegation_id"),120)
        if not did or did in seen:
            continue
        caps=[x for x in _caps(raw.get("granted_capabilities") if isinstance(raw.get("granted_capabilities"),(list,tuple)) else []) if x not in NON_DELEGABLE]
        state="ACTIVE" if str(raw.get("state") or "").upper()=="ACTIVE" and caps else "BLOCKED"
        item={
            "schema":SCHEMA,
            "delegation_id":did,
            "issuer_kind":_upper(raw.get("issuer_kind"),80),
            "subject_kind":_upper(raw.get("subject_kind"),80),
            "subject_ref":_clean(raw.get("subject_ref"),160),
            "workspace_id":_clean(raw.get("workspace_id"),120).lower(),
            "requested_capabilities":_caps(raw.get("requested_capabilities") if isinstance(raw.get("requested_capabilities"),(list,tuple)) else []),
            "granted_capabilities":caps,
            "scope":_clean(raw.get("scope"),1000),
            "evidence_refs":_refs(raw.get("evidence_refs") if isinstance(raw.get("evidence_refs"),(list,tuple)) else []),
            "created_at":_clean(raw.get("created_at"),80),
            "state":state,
            "blockers":_refs(raw.get("blockers") if isinstance(raw.get("blockers"),(list,tuple)) else []),
            "root_authority_granted":False,
            "may_expand_permissions":False,
            "may_change_policy":False,
            "direct_real_trading":False,
            "executes_action":False,
        }
        seen.add(did)
        out.append(item)
    return out


def default_resilience()->dict[str,Any]:
    delegations=[]
    return {
        "schema":SCHEMA,
        "delegations":delegations,
        "watchdogs":[],
        "circuit_breakers":[],
        "resource_governors":[],
        "safe_mode":safe_mode_posture(),
        "digest":resilience_digest(delegations,[],[],[]),
        "external_ai_root_authority":False,
        "automatic_destructive_action":False,
        "real_trading_enabled":False,
    }


def normalize_resilience(raw:Mapping[str,Any]|None)->dict[str,Any]:
    item=dict(raw or {})
    delegations=normalize_delegations(item.get("delegations") if isinstance(item.get("delegations"),(list,tuple)) else [])
    watchdogs=[dict(x) for x in list(item.get("watchdogs") or [])[:500] if isinstance(x,Mapping)]
    breakers=[dict(x) for x in list(item.get("circuit_breakers") or [])[:500] if isinstance(x,Mapping)]
    governors=[dict(x) for x in list(item.get("resource_governors") or [])[:500] if isinstance(x,Mapping)]
    open_circuits=sum(1 for x in breakers if str(x.get("state") or "").upper()=="OPEN")
    isolates=sum(1 for x in watchdogs if str(x.get("state") or "").upper()=="ISOLATE_RECOMMENDED")
    safe=safe_mode_posture(
        authority_integrity_ok=not bool(item.get("authority_integrity_failed",False)),
        policy_integrity_ok=not bool(item.get("policy_integrity_failed",False)),
        secret_exposure=bool(item.get("secret_exposure",False)),
        open_circuits=open_circuits,
        isolate_recommendations=isolates,
    )
    return {
        "schema":SCHEMA,
        "delegations":delegations,
        "watchdogs":watchdogs,
        "circuit_breakers":breakers,
        "resource_governors":governors,
        "safe_mode":safe,
        "digest":resilience_digest(delegations,watchdogs,breakers,governors),
        "external_ai_root_authority":False,
        "automatic_destructive_action":False,
        "real_trading_enabled":False,
    }


def resilience_digest(
    delegations:Sequence[Mapping[str,Any]]|None,
    watchdogs:Sequence[Mapping[str,Any]]|None,
    breakers:Sequence[Mapping[str,Any]]|None,
    governors:Sequence[Mapping[str,Any]]|None,
)->str:
    return _digest({
        "delegations":normalize_delegations(delegations),
        "watchdogs":[dict(x) for x in list(watchdogs or []) if isinstance(x,Mapping)],
        "circuit_breakers":[dict(x) for x in list(breakers or []) if isinstance(x,Mapping)],
        "resource_governors":[dict(x) for x in list(governors or []) if isinstance(x,Mapping)],
    })


def resilience_summary(raw:Mapping[str,Any]|None)->dict[str,Any]:
    state=normalize_resilience(raw)
    return {
        "schema":SCHEMA,
        "delegations":len(state["delegations"]),
        "active_delegations":sum(1 for x in state["delegations"] if x["state"]=="ACTIVE"),
        "open_circuits":sum(1 for x in state["circuit_breakers"] if str(x.get("state") or "").upper()=="OPEN"),
        "isolate_recommendations":sum(1 for x in state["watchdogs"] if str(x.get("state") or "").upper()=="ISOLATE_RECOMMENDED"),
        "safe_mode":state["safe_mode"]["mode"],
        "external_ai_root_authority":False,
        "real_trading_enabled":False,
        "digest":state["digest"],
    }


__all__=[
    "SCHEMA","PRINCIPALS","CAPABILITIES","NON_DELEGABLE","CIRCUIT_STATES",
    "WATCHDOG_STATES","SAFE_MODES","principal_authority","new_delegation",
    "agent_firewall","circuit_breaker","watchdog","resource_governor",
    "safe_mode_posture","normalize_delegations","default_resilience",
    "normalize_resilience","resilience_digest","resilience_summary",
]
