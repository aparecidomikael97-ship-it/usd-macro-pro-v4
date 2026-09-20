"""AtlasQuant four-layer market context.

Research/presentation layer only:
- Macro
- Geopolitics
- Micro/Fundamentals
- Technical/Flow

It consumes state already computed by AtlasQuant. It never fetches providers,
changes Score Mestre, changes gates/weights, promotes setups, or sends orders.
Missing evidence is shown as UNAVAILABLE instead of being silently converted to
neutral confidence.
"""
from __future__ import annotations

from html import escape
import math
import re
import unicodedata
from typing import Any, Mapping, Sequence

import streamlit as st

from atlasquant_layer_consensus import build_layer_consensus
from atlasquant_macro_engine import build_structured_macro

SCHEMA="ATLASQUANT_MARKET_LAYERS_V1"
LAYER_ORDER=("macro","geopolitics","micro","technical_flow")
RESEARCH_WEIGHTS={
    "macro":0.35,
    "geopolitics":0.15,
    "micro":0.20,
    "technical_flow":0.30,
}

RISK_SENSITIVITY={
    "USD":0.35,
    "JPY":0.85,
    "CHF":0.80,
    "EUR":-0.20,
    "GBP":-0.20,
    "CAD":-0.55,
    "AUD":-0.75,
    "NZD":-0.75,
}

GEO_RISK_OFF=(
    "war","conflict","attack","missile","invasion","escalat","sanction",
    "embargo","blockade","geopolitical tension","trade war","export ban",
    "political crisis","state of emergency","military strike","hostilities",
)
GEO_RISK_ON=(
    "ceasefire","peace deal","peace talks","de-escal","truce",
    "sanctions relief","diplomatic agreement","diplomatic breakthrough",
)
GEO_CONTEXT=(
    "geopolit","sanction","tariff","trade restriction","export control",
    "election uncertainty","political uncertainty","government crisis",
)


def _finite(value:Any,default:float=0.0)->float:
    try:
        x=float(value)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _clip(value:Any,lo:float=-100.0,hi:float=100.0)->float:
    return max(lo,min(hi,_finite(value)))


def _norm(value:object)->str:
    raw=unicodedata.normalize("NFKD",str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()


def _pair(value:object)->tuple[str,str]:
    raw=str(value or "").upper().replace("-","/").strip()
    if "/" not in raw:
        return "",""
    base,quote=raw.split("/",1)
    return base.strip(),quote.strip()


def _direction(balance:float,deadband:float=12.0)->str:
    x=_finite(balance)
    if x>=deadband:
        return "COMPRA"
    if x<=-deadband:
        return "VENDA"
    return "NEUTRO"


def _layer(
    layer_id:str,
    label:str,
    *,
    available:bool,
    balance:float=0.0,
    quality:float=0.0,
    reasons:Sequence[object]|None=None,
    risks:Sequence[object]|None=None,
    detail:str="",
)->dict[str,Any]:
    ok=bool(available)
    bal=_clip(balance) if ok else 0.0
    qual=max(0.0,min(100.0,_finite(quality))) if ok else 0.0
    return {
        "id":layer_id,
        "label":label,
        "available":ok,
        "balance":round(bal,1),
        "direction":_direction(bal) if ok else "INDISPONÍVEL",
        "quality":round(qual,1),
        "reasons":[str(x) for x in list(reasons or []) if str(x).strip()][:8],
        "risks":[str(x) for x in list(risks or []) if str(x).strip()][:8],
        "detail":str(detail or ""),
        "probability":False,
        "decision_effect":False,
    }


def macro_layer(
    pack:Mapping[str,Any]|None,
    *,
    macro_context:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    p=dict(pack or {})
    m=dict(macro_context or {})
    pair=str(p.get("pair") or "—")
    base,quote=_pair(pair)
    if not base or not quote:
        return _layer("macro","Macro",available=False,detail="Par inválido ou ausente.")

    diff=_finite(p.get("macro_diff",p.get("strength_diff",0)))
    data=p.get("data_ready")
    data_score=_finite((data or {}).get("score",0)) if isinstance(data,Mapping) else _finite(p.get("data_score",0))
    pair_quality=max(_finite(p.get("quality",0)),data_score,_finite(m.get("usd_quality",0)))

    engine=build_structured_macro(
        pair,
        m,
        legacy_balance=_clip(diff*4.0),
        legacy_quality=pair_quality,
    )
    reasons=list(engine.get("reasons",[]) or [])
    risks=list(engine.get("risks",[]) or [])

    if not reasons:
        if abs(diff)>0.01:
            stronger=base if diff>0 else quote
            weaker=quote if diff>0 else base
            reasons.append(f"{stronger} está {abs(diff):.1f} pts acima de {weaker} na força macro relativa.")
        else:
            reasons.append("Diferença macro relativa sem vantagem clara no estado atual.")

    fed=dict(m.get("fed",{}) or {})
    fed_tone=str(fed.get("tom",m.get("fed_tone","")) or "").strip()
    fed_strength=_finite(fed.get("forca",m.get("fed_strength",0)))
    if "USD" in {base,quote} and fed_tone and not any("fed" in _norm(x) for x in reasons):
        reasons.append(f"Fed: {fed_tone} · intensidade {fed_strength:+.2f}.")

    event=m.get("event")
    if isinstance(event,Mapping) and event.get("disponivel") and not any("proximo evento" in _norm(x) for x in risks):
        name=str(event.get("evento") or "evento macro")
        impact=str(event.get("impacto") or "")
        risks.append(f"Próximo evento: {name}{' · '+impact if impact else ''}.")

    out=_layer(
        "macro","Macro",
        available=bool(engine.get("available",False)),
        balance=_finite(engine.get("balance",0)),
        quality=_finite(engine.get("quality",0)),
        reasons=reasons,
        risks=risks,
        detail=(
            f"Motor macro {engine.get('mode','insufficient')} · cobertura "
            f"{_finite(engine.get('coverage',0)):.0f}% · juros, inflação, emprego, "
            "crescimento/atividade, expectativas/surpresas e bancos centrais. Não é probabilidade."
        ),
    )
    out["engine_mode"]=str(engine.get("mode") or "insufficient")
    out["coverage"]=round(_finite(engine.get("coverage",0)),1)
    out["macro_conflict"]=bool(engine.get("macro_conflict",False))
    out["groups"]=list(engine.get("groups",[]) or [])
    return out

def _geo_article_score(article:Mapping[str,Any])->tuple[float,list[str]]:
    title=_norm(article.get("title",""))
    if not title:
        return 0.0,[]
    off=sum(1 for term in GEO_RISK_OFF if term in title)
    on=sum(1 for term in GEO_RISK_ON if term in title)
    context=sum(1 for term in GEO_CONTEXT if term in title)
    if not (off or on or context):
        return 0.0,[]
    raw=float(off-on)
    if raw==0 and context:
        raw=0.35
    rec=max(0.15,min(1.0,_finite(article.get("recency_factor",1.0),1.0)))
    source=max(0.50,min(1.35,_finite(article.get("source_factor",1.0),1.0)))
    independent=max(0.30,min(1.0,_finite(article.get("independence_factor",1.0),1.0)))
    score=max(-2.0,min(2.0,raw))*rec*source*independent
    tags=[]
    if off:
        tags.append("risk-off/escalada")
    if on:
        tags.append("descompressão/peace")
    if context:
        tags.append("política/comércio")
    return score,tags


def geopolitical_layer(
    pair:object,
    news_state:Mapping[str,Any]|None,
)->dict[str,Any]:
    base,quote=_pair(pair)
    state=dict(news_state or {})