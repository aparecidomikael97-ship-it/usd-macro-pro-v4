"""Build Dow context from AtlasQuant point-in-time timeframe caches.

Research/observational only. Uses only closed candles already available in the
scanner/research cache. Missing data remains UNKNOWN and never grants execution.
"""
from __future__ import annotations
from typing import Any,Mapping
import pandas as pd

from ict_structure_v111 import _frame,_pivot_points,_bias_before
from atlasquant_dow_context import dow_context

SCHEMA="ATLASQUANT_DOW_CACHE_BUILDER_V1"

def _mapping(v:Any)->dict[str,Any]:
    return dict(v) if isinstance(v,Mapping) else {}

def _records_frame(records:Any)->pd.DataFrame:
    if not isinstance(records,list):return pd.DataFrame()
    return _frame(pd.DataFrame(records))

def structural_trend(records:Any,*,min_bars:int=12)->str:
    d=_records_frame(records)
    if len(d)<max(6,int(min_bars)):return "UNKNOWN"
    highs,lows=_pivot_points(d)
    if len(highs)<2 or len(lows)<2:return "UNKNOWN"
    return _bias_before(highs,lows,len(d)-1)

def dow_context_from_caches(pair:str,scanner:Mapping[str,Any]|None,research_cache:Mapping[str,Any]|None)->dict[str,Any]:
    symbol=str(pair or "").upper()
    sp=_mapping(_mapping(scanner).get("resultados")).get(symbol,{})
    sp=_mapping(sp);tec=_mapping(sp.get("tecnico"));native=_mapping(tec.get("cache_v110"))
    rp=_mapping(_mapping(research_cache).get("pairs")).get(symbol,{})
    rp=_mapping(rp)
    trends={
        "W1":structural_trend(rp.get("W1"),min_bars=12),
        "D1":structural_trend(rp.get("D1"),min_bars=20),
        "H4":structural_trend(native.get("h4"),min_bars=20),
        "H1":structural_trend(native.get("h1"),min_bars=20),
    }
    ctx=dow_context(weekly=trends["W1"],daily=trends["D1"],h4=trends["H4"],h1=trends["H1"])
    ctx["builder_schema"]=SCHEMA
    ctx["pair"]=symbol
    ctx["timeframe_trends"]=trends
    ctx["provenance"]={
        "W1":str(_mapping(rp.get("provenance")).get("W1") or "MISSING"),
        "D1":str(_mapping(rp.get("provenance")).get("D1") or "MISSING"),
        "H4":"SCANNER_NATIVE_OR_VALIDATED_CACHE" if native.get("h4") else "MISSING",
        "H1":"SCANNER_NATIVE_OR_VALIDATED_CACHE" if native.get("h1") else "MISSING",
    }
    ctx["research_only"]=True
    ctx["execution_authorized"]=False
    ctx["real_orders_enabled"]=False
    return ctx

def build_dow_context_map(scanner:Mapping[str,Any]|None,research_cache:Mapping[str,Any]|None)->dict[str,Any]:
    scanner_pairs=set(_mapping(_mapping(scanner).get("resultados")))
    research_pairs=set(_mapping(_mapping(research_cache).get("pairs")))
    pairs=sorted(scanner_pairs|research_pairs)
    rows={p:dow_context_from_caches(p,scanner,research_cache) for p in pairs}
    return {
        "schema":SCHEMA,"pairs":rows,
        "safety":{"research_only":True,"changes_quality_score":False,"changes_ranking":False,
                  "changes_gate":False,"real_orders_enabled":False},
    }
