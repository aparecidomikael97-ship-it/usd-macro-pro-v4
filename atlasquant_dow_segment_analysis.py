"""Dow Theory research segmentation for Backtest/Paper evidence.

Descriptive cohort analysis only. Never ranks strategies for deployment, never
changes Quality Score/Gate/Risk and never enables real orders.
"""
from __future__ import annotations
from collections import defaultdict
from typing import Any,Mapping,Sequence
import math

SCHEMA="ATLASQUANT_DOW_SEGMENT_ANALYSIS_V1"
DIMENSIONS=("pair","strategy","timeframe","session")

def _finite(v:Any)->float|None:
    try:
        x=float(v);return x if math.isfinite(x) else None
    except Exception:return None

def _key(row:Mapping[str,Any],dim:str)->str:
    raw=str(row.get(dim) or "UNKNOWN").strip().upper()
    return raw or "UNKNOWN"

def _stats(rows:Sequence[Mapping[str,Any]])->dict[str,Any]:
    vals=[x for x in (_finite(r.get("net_r")) for r in rows) if x is not None]
    n=len(vals)
    return {
        "resolved":n,
        "wins":sum(x>0 for x in vals),
        "losses":sum(x<0 for x in vals),
        "breakeven":sum(x==0 for x in vals),
        "net_r":round(sum(vals),4) if vals else 0.0,
        "expectancy_r":round(sum(vals)/n,4) if n else None,
    }

def segment_dow_evidence(rows:Sequence[Mapping[str,Any]]|None,*,dimension:str,min_per_cohort:int=20)->dict[str,Any]:
    dim=str(dimension or "").strip().lower()
    if dim not in DIMENSIONS:raise ValueError("Unsupported Dow segmentation dimension")
    grouped=defaultdict(list)
    for raw in rows or []:
        row=dict(raw)
        if _finite(row.get("net_r")) is None:continue
        grouped[_key(row,dim)].append(row)
    segments=[]
    threshold=max(1,int(min_per_cohort))
    for name,data in sorted(grouped.items()):
        aligned=[r for r in data if bool(r.get("dow_aligned",False))]
        other=[r for r in data if not bool(r.get("dow_aligned",False))]
        a,b=_stats(aligned),_stats(other)
        enough=a["resolved"]>=threshold and b["resolved"]>=threshold
        delta=None
        if enough:delta=round(float(a["expectancy_r"])-float(b["expectancy_r"]),4)
        segments.append({
            dim:name,"aligned":a,"not_aligned":b,"sample_sufficient":enough,
            "observed_expectancy_delta_r":delta,
            "deployment_conclusion_allowed":False,
            "ranking_weight_change_allowed":False,
            "gate_change_allowed":False,
        })
    return {
        "schema":SCHEMA,"dimension":dim,"min_per_cohort":threshold,"segments":segments,
        "research_only":True,"multiple_testing_warning":True,
        "deployment_conclusion_allowed":False,"ranking_weight_change_allowed":False,
        "gate_change_allowed":False,"real_orders_enabled":False,
    }

def dow_research_report(rows:Sequence[Mapping[str,Any]]|None,*,min_per_cohort:int=20)->dict[str,Any]:
    data=[dict(x) for x in (rows or [])]
    return {
        "schema":SCHEMA,
        "sample_rows":len(data),
        "by_dimension":{d:segment_dow_evidence(data,dimension=d,min_per_cohort=min_per_cohort) for d in DIMENSIONS},
        "interpretation":"Resultados observacionais por segmento; exigem validação fora da amostra/walk-forward e Paper antes de qualquer mudança de modelo.",
        "research_only":True,"automatic_model_selection":False,
        "quality_score_change_allowed":False,"gate_change_allowed":False,
        "real_orders_enabled":False,
    }
