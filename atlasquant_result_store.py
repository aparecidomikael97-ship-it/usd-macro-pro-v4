"""Immutable-style P0 Result Store records for AtlasQuant evidence lineage."""
from __future__ import annotations
from datetime import datetime,timezone
from typing import Any,Mapping
import hashlib,json,math

ENVIRONMENTS={"BACKTEST","PAPER","LIVE"}

def _iso(v:Any)->str:
    if not v: return datetime.now(timezone.utc).isoformat()
    d=datetime.fromisoformat(str(v).replace("Z","+00:00"))
    d=d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    return d.isoformat()

def decision_record(*,opportunity_id:str,environment:str,pair:str,direction:str,strategy_version:str,
                    score_version:str,risk_version:str,quality_score:float,confidence:float,
                    gates:Mapping[str,Any],risk_decision:Mapping[str,Any],timestamp:Any=None)->dict[str,Any]:
    env=str(environment).upper()
    if env not in ENVIRONMENTS: raise ValueError("invalid environment")
    if not opportunity_id or not strategy_version or not score_version or not risk_version: raise ValueError("lineage incomplete")
    payload={"opportunity_id":opportunity_id,"environment":env,"pair":pair,"direction":direction,
             "strategy_version":strategy_version,"score_version":score_version,"risk_version":risk_version,
             "quality_score":float(quality_score),"confidence":float(confidence),"gates":dict(gates or {}),
             "risk_decision":dict(risk_decision or {}),"timestamp":_iso(timestamp)}
    canonical=json.dumps(payload,sort_keys=True,separators=(",",":"),default=str)
    payload["record_id"]="DEC-"+hashlib.sha256(canonical.encode()).hexdigest()[:24]
    payload["record_type"]="DECISION"; payload["immutable_evidence"]=True
    return payload

def attach_result(decision:Mapping[str,Any],*,outcome:str,realized_r:float,mae_r:float|None=None,
                  mfe_r:float|None=None,spread_cost_r:float=0,slippage_cost_r:float=0,closed_at:Any=None)->dict[str,Any]:
    d=dict(decision)
    if d.get("record_type")!="DECISION": raise ValueError("result requires decision record")
    vals=[realized_r,spread_cost_r,slippage_cost_r]
    if not all(math.isfinite(float(x)) for x in vals): raise ValueError("non-finite result")
    net=float(realized_r)-float(spread_cost_r)-float(slippage_cost_r)
    return {**d,"record_type":"RESULT","decision_record_id":d["record_id"],"outcome":str(outcome).upper(),
            "realized_r":float(realized_r),"spread_cost_r":float(spread_cost_r),"slippage_cost_r":float(slippage_cost_r),
            "net_r":net,"mae_r":mae_r,"mfe_r":mfe_r,"closed_at":_iso(closed_at)}

def rejected_record(**kwargs)->dict[str,Any]:
    row=decision_record(**kwargs)
    row["record_type"]="REJECTED_OPPORTUNITY"
    return row
