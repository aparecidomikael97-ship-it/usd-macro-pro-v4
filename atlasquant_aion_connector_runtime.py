"""AION external-platform runtime gateway.

A single administrator-controlled backend may broker OAuth sessions and provider
APIs for YouTube, Spotify and future connectors. The AtlasQuant model context
never receives provider access tokens.

READ actions may run when the provider is connected. WRITE-like actions require
an unexpired exact approval envelope from atlasquant_aion_action_approval.
"""
from __future__ import annotations
from typing import Any,Callable,Mapping
from urllib.parse import urlparse
import os

from atlasquant_aion_action_approval import validate_adapter_execution
from atlasquant_aion_connectors import sanitize_connector_context

BLOCKED_ACTIONS={"MONEY","TRADING","SECURITY"}
WRITE_LIKE={"WRITE","PUBLISH","SEND","DELETE","ACCOUNT_CHANGE"}

def _setting(name:str,default:str="",env:Mapping[str,Any]|None=None)->str:
    src=dict(env or os.environ)
    return str(src.get(name,default) or "").strip()

def _valid_url(url:str,environment:str)->bool:
    try:
        p=urlparse(str(url or "").strip())
    except Exception:
        return False
    if not p.netloc:
        return False
    if p.scheme=="https":
        return True
    return p.scheme=="http" and environment!="PRODUCTION" and p.hostname in {"localhost","127.0.0.1","::1"}

def connector_runtime_status(env:Mapping[str,Any]|None=None)->dict[str,Any]:
    environment=_setting("ATLASQUANT_ENV","DEV",env).upper() or "DEV"
    url=_setting("AION_CONNECTOR_GATEWAY_URL","",env)
    return {
        "environment":environment,
        "gateway_configured":bool(url and _valid_url(url,environment)),
        "gateway_url_valid":bool(not url or _valid_url(url,environment)),
        "credentials_exposed":False,
        "real_orders_enabled":False,
        "voice_can_authorize_orders":False,
    }

def build_connector_adapter(*,env:Mapping[str,Any]|None=None,
                            request_post:Callable[...,Any]|None=None)->Callable[...,dict[str,Any]]|None:
    src=dict(env or os.environ)
    environment=_setting("ATLASQUANT_ENV","DEV",src).upper() or "DEV"
    url=_setting("AION_CONNECTOR_GATEWAY_URL","",src)
    token=_setting("AION_CONNECTOR_GATEWAY_TOKEN","",src)
    if not url or not _valid_url(url,environment):
        return None
    try:
        timeout=float(_setting("AION_CONNECTOR_TIMEOUT_SECONDS","20",src))
    except Exception:
        timeout=20.0
    if not 1.0<=timeout<=60.0:
        timeout=20.0

    def adapter(*,provider:str,action_class:str,payload:Mapping[str,Any],
                approved_action:Mapping[str,Any]|None=None,**_:Any)->dict[str,Any]:
        p=str(provider or "").strip().lower()
        action=str(action_class or "").strip().upper()
        body=dict(payload or {})
        if not p:
            raise ValueError("provider required")
        if action in BLOCKED_ACTIONS:
            raise PermissionError("AION_CONNECTOR_ACTION_BLOCKED")
        if action not in {"READ",*WRITE_LIKE}:
            raise ValueError("unsupported action class")

        approval_id=None
        if action in WRITE_LIKE:
            validation=validate_adapter_execution(
                dict(approved_action or {}),
                provider=p,
                payload=body,
            )
            if not validation.get("allowed"):
                raise PermissionError("AION_CONNECTOR_APPROVAL_REQUIRED")
            approval_id=validation.get("action_id")

        if request_post is None:
            import requests
            post=requests.post
        else:
            post=request_post

        headers={"Accept":"application/json","Content-Type":"application/json"}
        if token:
            headers["Authorization"]="Bearer "+token
        response=post(
            url,
            json={
                "assistant":"AION",
                "language":"pt-BR",
                "provider":p,
                "action_class":action,
                "payload":body,
                "approval_id":approval_id,
            },
            headers=headers,
            timeout=timeout,
        )
        status=int(getattr(response,"status_code",0) or 0)
        if status<200 or status>=300:
            raise RuntimeError("AION_CONNECTOR_HTTP_"+str(status))
        data=response.json()
        if not isinstance(data,Mapping):
            raise RuntimeError("AION_CONNECTOR_RESPONSE_INVALID")
        out=sanitize_connector_context(dict(data))
        out.update({
            "provider":p,
            "action_class":action,
            "real_orders_enabled":False,
            "voice_can_authorize_orders":False,
        })
        return out

    return adapter
