"""AION provider-neutral runtime gateway.

The AtlasQuant app can point AION at administrator-controlled backend services
for general AI and current web research without hard-coding a vendor.

Secrets remain in environment/secrets and are only attached to outbound HTTP
headers. They are never returned in AION context or UI.
"""
from __future__ import annotations
from typing import Any,Callable,Mapping
from urllib.parse import urlparse
import os

DEFAULT_TIMEOUT_SECONDS=20.0

def _setting(name:str,default:str="",env:Mapping[str,Any]|None=None)->str:
    source=dict(env or os.environ)
    return str(source.get(name,default) or "").strip()

def _valid_backend_url(url:str,environment:str)->bool:
    try:
        p=urlparse(str(url or "").strip())
    except Exception:
        return False
    if not p.netloc:
        return False
    if p.scheme=="https":
        return True
    if p.scheme=="http" and environment!="PRODUCTION" and p.hostname in {"localhost","127.0.0.1","::1"}:
        return True
    return False

def runtime_gateway_status(env:Mapping[str,Any]|None=None)->dict[str,Any]:
    environment=_setting("ATLASQUANT_ENV","DEV",env).upper() or "DEV"
    general=_setting("AION_GENERAL_AI_URL","",env)
    research=_setting("AION_WEB_RESEARCH_URL","",env)
    return {
        "environment":environment,
        "general_ai_configured":bool(general and _valid_backend_url(general,environment)),
        "web_research_configured":bool(research and _valid_backend_url(research,environment)),
        "general_ai_url_valid":bool(not general or _valid_backend_url(general,environment)),
        "web_research_url_valid":bool(not research or _valid_backend_url(research,environment)),
        "credentials_exposed":False,
        "real_orders_enabled":False,
        "voice_can_authorize_orders":False,
    }

def _timeout(env:Mapping[str,Any]|None=None)->float:
    raw=_setting("AION_GATEWAY_TIMEOUT_SECONDS",str(DEFAULT_TIMEOUT_SECONDS),env)
    try:
        value=float(raw)
    except Exception:
        return DEFAULT_TIMEOUT_SECONDS
    if not (1.0<=value<=60.0):
        return DEFAULT_TIMEOUT_SECONDS
    return value

def _post_json(url:str,payload:Mapping[str,Any],*,token:str,timeout:float,
               request_post:Callable[...,Any]|None=None)->dict[str,Any]:
    if request_post is None:
        import requests
        request_post=requests.post
    headers={"Accept":"application/json","Content-Type":"application/json"}
    if token:
        headers["Authorization"]="Bearer "+token
    response=request_post(url,json=dict(payload),headers=headers,timeout=timeout)
    status=int(getattr(response,"status_code",0) or 0)
    if status<200 or status>=300:
        raise RuntimeError("AION_BACKEND_HTTP_"+str(status))
    data=response.json()
    if not isinstance(data,Mapping):
        raise RuntimeError("AION_BACKEND_RESPONSE_INVALID")
    return dict(data)

def build_runtime_adapters(*,env:Mapping[str,Any]|None=None,
                           request_post:Callable[...,Any]|None=None)->dict[str,Any]:
    source=dict(env or os.environ)
    environment=_setting("ATLASQUANT_ENV","DEV",source).upper() or "DEV"
    general_url=_setting("AION_GENERAL_AI_URL","",source)
    research_url=_setting("AION_WEB_RESEARCH_URL","",source)
    token=_setting("AION_RUNTIME_TOKEN","",source)
    timeout=_timeout(source)

    general_ok=bool(general_url and _valid_backend_url(general_url,environment))
    research_ok=bool(research_url and _valid_backend_url(research_url,environment))

    def general_ai_adapter(*,question:str,memory:list|None=None,**_:Any)->dict[str,Any]:
        if not general_ok:
            raise RuntimeError("AION_GENERAL_AI_NOT_CONFIGURED")
        return _post_json(
            general_url,
            {"question":str(question or ""),"memory":list(memory or []),"language":"pt-BR","assistant":"AION"},
            token=token,timeout=timeout,request_post=request_post,
        )

    def web_research_adapter(*,question:str,memory:list|None=None,**_:Any)->dict[str,Any]:
        if not research_ok:
            raise RuntimeError("AION_WEB_RESEARCH_NOT_CONFIGURED")
        return _post_json(
            research_url,
            {"question":str(question or ""),"memory":list(memory or []),"language":"pt-BR","assistant":"AION","require_sources":True},
            token=token,timeout=timeout,request_post=request_post,
        )

    return {
        "status":{
            "environment":environment,
            "general_ai_configured":general_ok,
            "web_research_configured":research_ok,
            "credentials_exposed":False,
        },
        "general_ai_adapter":general_ai_adapter if general_ok else None,
        "web_research_adapter":web_research_adapter if research_ok else None,
        "real_orders_enabled":False,
        "voice_can_authorize_orders":False,
    }
