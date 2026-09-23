"""Dow Theory observational experiment for AtlasQuant.

Compares outcomes already produced by Backtest/Paper with the Dow context that
was known for that observation. It does not create trades, change ranking,
reweight Quality Score, or authorize execution.
"""
from __future__ import annotations
from typing import Any,Mapping,Sequence
import math

SCHEMA="ATLASQUANT_DOW_EXPERIMENT_V1"

def _finite(v:Any)->float|None:
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except Exception:return None

def dow_observation(opportunity:Mapping[str,Any],dow:Mapping[str,Any],outcome:Mapping[str,Any]|None=None)->dict[str,Any]:
    o=dict(opportunity or {});d=dict(dow or {});result=dict(outcome or {})
    return {
        "schema":SCHEMA,
        "pair":str(o.get("pair") or ""),
        "strategy":str(o.get("strategy",o.get("strategy_version","")) or ""),
        "observed_at":str(o.get("observed_at",o.get("timestamp","")) or ""),
        "dow_status":str(d.get("status","INSUFFICIENT_DATA")),
        "dow_primary":str(d.get("primary_trend","UNKNOWN")),
        "dow_secondary":str(d.get("secondary_trend","UNKNOWN")),
        "dow_aligned":bool(d.get("aligned",False)),
        "quality_score_original":_finite(o.get("quality_score",o.get("quality"))),
        "priority_original":_finite(o.get("priority")),
        "executed_original":bool(o.get("executed",False)),
        "net_r":_finite(result.get("net_r")),
        "outcome":str(result.get("outcome","UNRESOLVED")).upper(),
        "research_only":True,
        "changed_live_decision":False,
        "real_orders_enabled":False,
    }

def compare_dow_cohorts(rows:Sequence[Mapping[str,Any]]|None,*,min_resolved:int=20)->dict[str,Any]:
    data=[dict(x) for x in (rows or []) if _finite(dict(x).get("net_r")) is not None]
    aligned=[x for x in data if bool(x.get("dow_aligned",False))]
    not_aligned=[x for x in data if not bool(x.get("dow_aligned",False))]
    def stats(xs):
        vals=[float(x["net_r"]) for x in xs]
        return {"resolved":len(vals),"net_r":round(sum(vals),4) if vals else 0.0,
                "expectancy_r":round(sum(vals)/len(vals),4) if vals else None,
                "wins":sum(1 for x in vals if x>0),"losses":sum(1 for x in vals if x<0)}
    a,b=stats(aligned),stats(not_aligned);threshold=max(1,int(min_resolved))
    enough=a["resolved"]>=threshold and b["resolved"]>=threshold
    delta=None
    if enough and a["expectancy_r"] is not None and b["expectancy_r"] is not None:
        delta=round(a["expectancy_r"]-b["expectancy_r"],4)
    return {
        "schema":SCHEMA,"aligned":a,"not_aligned":b,"min_resolved_per_cohort":threshold,
        "sample_sufficient":enough,"observed_expectancy_delta_r":delta,
        "conclusion_allowed":enough,
        "ranking_weight_change_allowed":False,
        "live_gate_change_allowed":False,
        "real_orders_enabled":False,
        "interpretation":(
            "Amostra suficiente para análise descritiva; ainda exige walk-forward/Paper antes de qualquer peso."
            if enough else "Amostra insuficiente; não concluir que Dow melhora o operacional."
        ),
    }
