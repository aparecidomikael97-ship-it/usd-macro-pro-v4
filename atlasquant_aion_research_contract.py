"""AION web-research response contract.

The actual internet provider is injected by an adapter. This module validates
that time-sensitive answers carry traceable sources instead of pretending a
search happened.
"""
from __future__ import annotations
from typing import Any,Mapping,Sequence
from datetime import datetime,timezone
from urllib.parse import urlparse

SCHEMA="AION_WEB_RESEARCH_V1"

def _valid_url(value:Any)->bool:
    try:
        p=urlparse(str(value or "").strip())
        return p.scheme in {"http","https"} and bool(p.netloc)
    except Exception:
        return False

def validate_research_response(raw:Mapping[str,Any]|None)->dict[str,Any]:
    src=dict(raw or {})
    answer=" ".join(str(src.get("answer") or "").strip().split())
    reasons=[]
    if not answer:
        reasons.append("ANSWER_MISSING")
    sources=[]
    for item in list(src.get("sources",[]) or [])[:20]:
        row=dict(item or {})
        title=" ".join(str(row.get("title") or "").strip().split())
        url=str(row.get("url") or "").strip()
        if not title or not _valid_url(url):
            continue
        sources.append({
            "title":title[:300],
            "url":url,
            "publisher":" ".join(str(row.get("publisher") or "").strip().split())[:200],
            "published_at":str(row.get("published_at") or "").strip()[:80],
        })
    if not sources:
        reasons.append("SOURCES_MISSING")
    researched_at=str(src.get("researched_at") or "").strip()
    if not researched_at:
        researched_at=datetime.now(timezone.utc).isoformat()
    return {
        "schema":SCHEMA,
        "ok":not reasons,
        "answer":answer,
        "sources":sources,
        "researched_at":researched_at,
        "reasons":reasons,
        "citations_required":True,
        "real_orders_enabled":False,
        "voice_can_authorize_orders":False,
    }

def research_unavailable_message()->dict[str,Any]:
    return {
        "schema":SCHEMA,
        "ok":False,
        "answer":"Eu preciso pesquisar isso para responder com informação atual, mas o adaptador de internet do AION ainda não está conectado neste ambiente.",
        "sources":[],
        "researched_at":None,
        "reasons":["RESEARCH_ADAPTER_UNAVAILABLE"],
        "citations_required":True,
        "real_orders_enabled":False,
        "voice_can_authorize_orders":False,
    }
