"""Execution-readiness matrix for AtlasQuant multi-timeframe Paper research.

This module never enables a timeframe by data availability alone. Exact OHLC,
direction/context, filters and a timeframe-specific trigger contract are all
required. Unsupported timeframes remain research-only/fail-closed.
"""
from __future__ import annotations

from typing import Any, Mapping

SUPPORTED_TIMEFRAMES=("M15","M30","H1","H4","D1","W1")
RESEARCH_CACHE_PATH="dados/atlasquant_research_timeframes_v1.json"

CONTEXT_REQUIREMENTS={
    "M15":("H1","H4"),
    "M30":("H1","H4"),
    "H1":("H4","D1"),
    "H4":("D1","W1"),
    "D1":("W1",),
    "W1":("W1",),
}

# Paper execution is deliberately narrower than Backtest research.
# New timeframes must receive an explicit trigger/filter/context contract first.
PAPER_GATE_SUPPORTED={"M15","H1"}


def _mapping(v:Any)->dict[str,Any]:
    return dict(v) if isinstance(v,Mapping) else {}


def _scanner_pair(scanner:Mapping[str,Any]|None,pair:str)->dict[str,Any]:
    rows=_mapping(_mapping(scanner).get("resultados"))
    return _mapping(rows.get(str(pair or "").upper()))


def _research_pair(cache:Mapping[str,Any]|None,pair:str)->dict[str,Any]:
    rows=_mapping(_mapping(cache).get("pairs"))
    return _mapping(rows.get(str(pair or "").upper()))


def _bars_available(scanner_pair:Mapping[str,Any],research_pair:Mapping[str,Any],tf:str)->bool:
    tec=_mapping(scanner_pair.get("tecnico"))
    native=_mapping(tec.get("cache_v110"))
    if tf in {"M15","H1","H4"}:
        return bool(list(native.get(tf.lower(),[]) or []))
    return bool(list(research_pair.get(tf,[]) or []))


def execution_readiness_for_pair(
    pair:str,
    scanner:Mapping[str,Any]|None,
    research_cache:Mapping[str,Any]|None,
)->dict[str,Any]:
    sp=_scanner_pair(scanner,pair)
    rp=_research_pair(research_cache,pair)
    rows={}
    for tf in SUPPORTED_TIMEFRAMES:
        exact_data=_bars_available(sp,rp,tf)
        gate_supported=tf in PAPER_GATE_SUPPORTED
        reasons=[]
        if not exact_data:
            reasons.append("SEM_CANDLES_EXATOS")
        if not gate_supported:
            reasons.append("CONTRATO_DE_GATILHO_AINDA_NAO_IMPLEMENTADO")
        rows[tf]={
            "timeframe":tf,
            "required_context":list(CONTEXT_REQUIREMENTS[tf]),
            "exact_execution_data":bool(exact_data),
            "decision_gate_supported":bool(gate_supported),
            "can_execute_paper":bool(exact_data and gate_supported),
            "state":"READY" if exact_data and gate_supported else "RESEARCH_ONLY",
            "reasons":reasons,
            "real_orders_enabled":False,
        }
    return {
        "pair":str(pair or "").upper(),
        "timeframes":rows,
        "safety":{
            "alignment_required":True,
            "direction_required":True,
            "filters_required":True,
            "trigger_required":True,
            "lower_timeframe_substitution":False,
            "real_orders_enabled":False,
        },
    }


def execution_readiness_summary(
    scanner:Mapping[str,Any]|None,
    research_cache:Mapping[str,Any]|None,
)->dict[str,Any]:
    pairs=sorted(set(_mapping(_mapping(scanner).get("resultados"))) | set(_mapping(_mapping(research_cache).get("pairs"))))
    by_pair={pair:execution_readiness_for_pair(pair,scanner,research_cache) for pair in pairs}
    counts={tf:{"pairs_with_exact_data":0,"pairs_paper_ready":0} for tf in SUPPORTED_TIMEFRAMES}
    for pack in by_pair.values():
        for tf,row in pack["timeframes"].items():
            counts[tf]["pairs_with_exact_data"]+=int(bool(row["exact_execution_data"]))
            counts[tf]["pairs_paper_ready"]+=int(bool(row["can_execute_paper"]))
    return {
        "supported_timeframes":list(SUPPORTED_TIMEFRAMES),
        "paper_gate_supported":sorted(PAPER_GATE_SUPPORTED,key=SUPPORTED_TIMEFRAMES.index),
        "by_timeframe":counts,
        "by_pair":by_pair,
        "safety":{
            "research_only_for_unsupported_timeframes":True,
            "alignment_required":True,
            "lower_timeframe_substitution":False,
            "automatic_execution":False,
            "real_orders_enabled":False,
        },
    }


__all__=[
    "SUPPORTED_TIMEFRAMES","RESEARCH_CACHE_PATH","CONTEXT_REQUIREMENTS",
    "PAPER_GATE_SUPPORTED","execution_readiness_for_pair","execution_readiness_summary",
]
