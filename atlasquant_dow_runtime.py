"""Build observational Dow context from AtlasQuant's existing timeframe caches.

No provider calls are added. Only closed/validated bars already present in the
scanner and research cache are used. The output is research/context only.
"""
from __future__ import annotations
from typing import Any,Mapping
import pandas as pd

from atlasquant_dow_context import dow_context
from atlasquant_m15_derived_timeframes import derive_from_m15
from atlasquant_research_timeframes import build_research_timeframe_cache
from market_map_core_v10 import normalize_ohlc

SCHEMA="ATLASQUANT_DOW_RUNTIME_V1"

def _swing_trend(frame:Any,*,lookback:int=80)->str:
    d=normalize_ohlc(frame)
    if len(d)<8:return "UNKNOWN"
    d=d.tail(max(8,int(lookback))).reset_index(drop=True)
    highs=[];lows=[]
    for i in range(2,len(d)-2):
        h=float(d.loc[i,"high"]);l=float(d.loc[i,"low"])
        if h>=float(d.loc[i-2:i+2,"high"].max()):highs.append(h)
        if l<=float(d.loc[i-2:i+2,"low"].min()):lows.append(l)
    if len(highs)<2 or len(lows)<2:return "UNKNOWN"
    eps=max(abs(highs[-1]),abs(lows[-1]),1.0)*1e-10
    dh=highs[-1]-highs[-2];dl=lows[-1]-lows[-2]
    if dh>eps and dl>eps:return "BULLISH"
    if dh<-eps and dl<-eps:return "BEARISH"
    return "MIXED"

def build_dow_runtime_context(scanner:Mapping[str,Any]|None,daily_cache:Mapping[str,Any]|None,
                              *,now:Any=None)->dict[str,Any]:
    research=build_research_timeframe_cache(scanner,daily_cache,now=now)
    scanner_rows=dict((scanner or {}).get("resultados",{}) or {}) if isinstance(scanner,Mapping) else {}
    pairs={}
    for pair,cache in dict(research.get("pairs",{}) or {}).items():
        raw=dict(scanner_rows.get(pair,{}) or {})
        tech=dict(raw.get("tecnico",{}) or {})
        m15=list(dict(tech.get("cache_v110",{}) or {}).get("m15",[]) or [])
        try:
            h1=derive_from_m15(m15,"1h",now_utc=now)
            h4=derive_from_m15(m15,"4h",now_utc=now)
        except Exception:
            h1=pd.DataFrame();h4=pd.DataFrame()
        d1=cache.get("D1",[]);w1=cache.get("W1",[])
        trends={"W1":_swing_trend(w1,lookback=52),"D1":_swing_trend(d1,lookback=80),
                "H4":_swing_trend(h4,lookback=80),"H1":_swing_trend(h1,lookback=80)}
        ctx=dow_context(weekly=trends["W1"],daily=trends["D1"],h4=trends["H4"],h1=trends["H1"])
        ctx["timeframe_provenance"]={
            "W1":"DERIVED_FROM_COMPLETED_D1",
            "D1":"COMPLETED_PROVIDER_D1",
            "H4":"DERIVED_FROM_EXACT_CLOSED_M15",
            "H1":"DERIVED_FROM_EXACT_CLOSED_M15",
        }
        ctx["bars"]={"W1":len(cache.get("W1",[])),"D1":len(cache.get("D1",[])),
                     "H4":len(h4),"H1":len(h1)}
        ctx["provider_calls_added"]=False
        pairs[pair]=ctx
    return {"schema":SCHEMA,"generated_at":research.get("generated_at",""),"pairs":pairs,
            "safety":{"research_only":True,"provider_calls_added":False,
                      "ranking_weight_change":False,"gate_change":False,
                      "real_orders_enabled":False}}

def attach_dow_to_packs(packs:list[Mapping[str,Any]]|None,runtime:Mapping[str,Any]|None)->list[dict[str,Any]]:
    contexts=dict((runtime or {}).get("pairs",{}) or {}) if isinstance(runtime,Mapping) else {}
    out=[]
    for raw in packs or []:
        row=dict(raw);pair=str(row.get("pair") or "").upper()
        ctx=dict(contexts.get(pair,{}) or {})
        if ctx:
            row["dow_context"]=ctx
        out.append(row)
    return out
