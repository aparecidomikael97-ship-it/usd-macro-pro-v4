"""Join resolved Backtest/Paper outcomes to Dow observations by immutable identity.

No fuzzy/time-nearest matching: ambiguous or missing identities are excluded so
research cannot manufacture a Dow effect.
"""
from __future__ import annotations
from typing import Any,Mapping,Sequence

SCHEMA="ATLASQUANT_DOW_EVIDENCE_BRIDGE_V1"
IDS=("opportunity_id","paper_request_id","result_id")

def _identity(row:Mapping[str,Any])->tuple[str,str]|None:
    for k in IDS:
        v=str(row.get(k) or "").strip()
        if v:return k,v
    return None

def join_dow_outcomes(observations:Sequence[Mapping[str,Any]]|None,outcomes:Sequence[Mapping[str,Any]]|None)->dict[str,Any]:
    index={};ambiguous=set()
    for raw in outcomes or []:
        row=dict(raw);ident=_identity(row)
        if not ident:continue
        if ident in index:ambiguous.add(ident)
        else:index[ident]=row
    joined=[];missing=0;amb=0;no_identity=0
    for raw in observations or []:
        obs=dict(raw);ident=_identity(obs)
        if not ident:
            no_identity+=1;continue
        if ident in ambiguous:
            amb+=1;continue
        result=index.get(ident)
        if result is None:
            missing+=1;continue
        row=dict(obs)
        row["net_r"]=result.get("net_r")
        row["outcome"]=result.get("outcome","UNRESOLVED")
        row["result_id"]=str(result.get("result_id") or row.get("result_id") or "")
        row["evidence_join_key"]=f"{ident[0]}:{ident[1]}"
        joined.append(row)
    return {
        "schema":SCHEMA,"joined":joined,"joined_count":len(joined),
        "excluded_missing_outcome":missing,"excluded_ambiguous_identity":amb,
        "excluded_no_identity":no_identity,
        "fuzzy_matching":False,"research_only":True,"gate_change_allowed":False,
        "real_orders_enabled":False,
    }
