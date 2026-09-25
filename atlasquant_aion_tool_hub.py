"""AION Tool Hub / MCP contracts.

Provider-neutral tool catalog and preflight planner. The Hub knows what a tool
is allowed to request, which workspace/connector owns it and whether an action
has side effects. It never calls the tool itself.

MCP/API/native connectors remain disabled until separately configured and
approved. Tool output is content, not authority.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

from atlasquant_aion_fortress import proof_of_safety, source_authority
from atlasquant_aion_portable import normalize_portable_core

SCHEMA="ATLASQUANT_AION_TOOL_HUB_V1"
TOOL_STATES=("LOCAL_READY","CONFIGURED","DISABLED","DEGRADED")
TOOL_KINDS=("READ","SEARCH","DRAFT","WRITE","PUBLISH","FINANCIAL","PRODUCTION","SECRETS")
_SAFE_ID=re.compile(r"^[a-z0-9][a-z0-9._-]{1,95}$")

DEFAULT_TOOLS=(
    {
        "tool_id":"aion.memory.search",
        "label":"Busca da memória auditável",
        "workspace_id":"central",
        "connector_id":"",
        "kind":"SEARCH",
        "guardian_action":"search",
        "state":"LOCAL_READY",
        "required_scopes":["memory:read"],
        "external_side_effects":False,
    },
    {
        "tool_id":"aion.checkpoint.inspect",
        "label":"Inspecionar Checkpoint Mestre",
        "workspace_id":"administration",
        "connector_id":"",
        "kind":"READ",
        "guardian_action":"read",
        "state":"LOCAL_READY",
        "required_scopes":["checkpoint:read"],
        "external_side_effects":False,
    },
    {
        "tool_id":"aion.checkpoint.prepare_save",
        "label":"Preparar salvamento do Checkpoint",
        "workspace_id":"administration",
        "connector_id":"",
        "kind":"WRITE",
        "guardian_action":"save_checkpoint",
        "state":"LOCAL_READY",
        "required_scopes":["checkpoint:write"],
        "external_side_effects":True,
    },
)


def _clean(value:Any,limit:int=500)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _safe_id(value:Any)->str:
    text=_clean(value,96).lower()
    if not _SAFE_ID.fullmatch(text):
        raise ValueError("invalid tool id")
    return text


def _digest(payload:Any)->str:
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:24]


def _unique(values:Sequence[Any]|None,limit:int=40)->list[str]:
    out=[]
    for raw in list(values or [])[:limit*2]:
        text=_clean(raw,120)
        if text and text not in out:
            out.append(text)
        if len(out)>=limit:
            break
    return out


def normalize_tool(raw:Mapping[str,Any])->dict[str,Any]:
    item=dict(raw or {})
    tool_id=_safe_id(item.get("tool_id"))
    workspace_id=_safe_id(item.get("workspace_id"))
    connector_raw=_clean(item.get("connector_id"),96).lower()
    connector_id=_safe_id(connector_raw) if connector_raw else ""
    kind=_clean(item.get("kind"),30).upper()
    if kind not in TOOL_KINDS:
        kind="READ"
    state=_clean(item.get("state"),30).upper()
    if state not in TOOL_STATES:
        state="DISABLED"
    action=_clean(item.get("guardian_action"),80).lower() or "read"
    return {
        "tool_id":tool_id,
        "label":_clean(item.get("label"),140) or tool_id,
        "workspace_id":workspace_id,
        "connector_id":connector_id,
        "kind":kind,
        "guardian_action":action,
        "state":state,
        "required_scopes":_unique(
            item.get("required_scopes")
            if isinstance(item.get("required_scopes"),(list,tuple))
            else []
        ),
        "external_side_effects":bool(item.get("external_side_effects",False)),
        "tool_output_is_authority":False,
        "may_expand_permissions":False,
        "auto_execute":False,
        "real_trading_enabled":False,
    }


def normalize_tools(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[:500]:
        if not isinstance(raw,Mapping):
            continue
        try:
            item=normalize_tool(raw)
        except Exception:
            continue
        if item["tool_id"] in seen:
            continue
        seen.add(item["tool_id"])
        out.append(item)
    return out


def default_tool_hub()->dict[str,Any]:
    tools=normalize_tools(DEFAULT_TOOLS)
    return {
        "schema":SCHEMA,
        "tools":tools,
        "digest":tool_hub_digest(tools),
        "protocols":["NATIVE","API","MCP","FILE","WEBHOOK"],
        "external_activation_automatic":False,
        "tool_output_is_authority":False,
        "auto_execute":False,
        "real_trading_enabled":False,
    }


def normalize_tool_hub(raw:Mapping[str,Any]|None)->dict[str,Any]:
    item=dict(raw or {})
    tools=normalize_tools(
        item.get("tools") if isinstance(item.get("tools"),(list,tuple)) else []
    )
    if not tools:
        tools=normalize_tools(DEFAULT_TOOLS)
    return {
        "schema":SCHEMA,
        "tools":tools,
        "digest":tool_hub_digest(tools),
        "protocols":["NATIVE","API","MCP","FILE","WEBHOOK"],
        "external_activation_automatic":False,
        "tool_output_is_authority":False,
        "auto_execute":False,
        "real_trading_enabled":False,
    }


def tool_hub_digest(rows:Sequence[Mapping[str,Any]]|None)->str:
    return _digest(normalize_tools(rows))


def _find_tool(tool_id:Any,hub:Mapping[str,Any]|None)->dict[str,Any]|None:
    target=_clean(tool_id,96).lower()
    state=normalize_tool_hub(hub)
    return next((x for x in state["tools"] if x["tool_id"]==target),None)


def _connector_readiness(
    connector_id:str,
    portable_core:Mapping[str,Any]|None,
)->dict[str,Any]:
    if not connector_id:
        return {"required":False,"configured":True,"activated":True,"reason":"LOCAL_TOOL"}
    core=normalize_portable_core(portable_core)
    connector=next(
        (x for x in core["connectors"] if x["connector_id"]==connector_id),
        None,
    )
    if not connector:
        return {
            "required":True,"configured":False,"activated":False,
            "reason":"CONNECTOR_NOT_REGISTERED",
        }
    return {
        "required":True,
        "configured":bool(connector.get("configuration_ready",False)),
        "activated":bool(connector.get("enabled",False) and connector.get("activation_approved",False)),
        "reason":"CONNECTOR_ACTIVE" if bool(connector.get("enabled",False)) else "CONNECTOR_NOT_ACTIVATED",
    }


def plan_tool_call(
    tool_id:Any,
    *,
    hub:Mapping[str,Any]|None,
    portable_core:Mapping[str,Any]|None,
    access:Mapping[str,Any]|None,
    source_kind:Any="ADMIN",
    authenticated_admin:bool=False,
    approved:bool=False,
    feature_flags:Mapping[str,Any]|None=None,
    scope:Any="",
    artifacts:Sequence[Any]|None=None,
    tests:Sequence[Mapping[str,Any]]|None=None,
    rollback_plan:Any="",
    uncertainty_pct:Any=100,
    impact:Any="MEDIUM",
    reversible:bool=False,
)->dict[str,Any]:
    """Create an execution preflight. No connector/tool is called."""
    tool=_find_tool(tool_id,hub)
    if tool is None:
        return {
            "schema":SCHEMA,"state":"BLOCK","reason":"TOOL_NOT_REGISTERED",
            "tool_id":_clean(tool_id,96),"executes_action":False,
            "real_trading_enabled":False,
        }
    authority=source_authority(source_kind,authenticated_admin=authenticated_admin)
    connector=_connector_readiness(tool["connector_id"],portable_core)
    safety=proof_of_safety(
        tool["guardian_action"],
        access,
        approved=approved,
        feature_flags=feature_flags,
        source_kind=source_kind,
        authenticated_admin=authenticated_admin,
        scope=scope,
        artifacts=artifacts,
        tests=tests,
        rollback_plan=rollback_plan,
        uncertainty_pct=uncertainty_pct,
        impact=impact,
        reversible=reversible,
        external_side_effects=tool["external_side_effects"],
    )
    blockers=[]
    if tool["state"]=="DISABLED":
        blockers.append("TOOL_DISABLED")
    if tool["connector_id"] and not connector["activated"]:
        blockers.append("CONNECTOR_NOT_ACTIVATED")
    if not authority["can_issue_action"]:
        blockers.append("SOURCE_HAS_NO_COMMAND_AUTHORITY")
    if safety.get("state")=="BLOCK":
        blockers.extend(str(x) for x in list(safety.get("blockers") or []))
    blockers=list(dict.fromkeys(blockers))
    state="BLOCK" if blockers else ("REVIEW" if safety.get("state")=="REVIEW" else "READY_FOR_EXECUTOR")
    return {
        "schema":SCHEMA,
        "state":state,
        "tool":tool,
        "connector":connector,
        "source_authority":authority,
        "proof_of_safety":safety,
        "blockers":blockers,
        "executes_action":False,
        "connector_called":False,
        "tool_called":False,
        "real_trading_enabled":False,
    }


def tool_hub_summary(
    hub:Mapping[str,Any]|None,
    portable_core:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    state=normalize_tool_hub(hub)
    core=normalize_portable_core(portable_core)
    tools=state["tools"]
    external=[x for x in tools if x["connector_id"]]
    return {
        "schema":SCHEMA,
        "tools":len(tools),
        "local_ready":sum(1 for x in tools if x["state"]=="LOCAL_READY" and not x["connector_id"]),
        "external_tools":len(external),
        "registered_connectors":len(core["connectors"]),
        "active_external_tools":0,
        "auto_execute":False,
        "real_trading_enabled":False,
        "digest":state["digest"],
    }


__all__=[
    "SCHEMA","TOOL_STATES","TOOL_KINDS","DEFAULT_TOOLS",
    "normalize_tool","normalize_tools","default_tool_hub","normalize_tool_hub",
    "tool_hub_digest","plan_tool_call","tool_hub_summary",
]
