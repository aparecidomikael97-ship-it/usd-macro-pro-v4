"""P0 immutable evidence records. Record builders only; persistence is separate."""
from __future__ import annotations
from datetime import datetime,timezone
from typing import Any,Mapping
import hashlib,json,math
from atlasquant_instrument_registry import normalize_fx_symbol
ENVIRONMENTS={"BACKTEST","PAPER","LIVE"}; SCHEMA_VERSION="AQ_RESULT_V1"
def _iso(v:Any)->str:
 if not v:return datetime.now(timezone.utc).isoformat()
 d=datetime.fromisoformat(str(v).replace("Z","+00:00")); d=d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc); return d.isoformat()
def _score(v:Any,name:str)->float:
 x=float(v)
 if not math.isfinite(x) or not 0<=x<=100: raise ValueError(f"{name} outside 0..100")
 return x
def _hash(prefix:str,payload:Mapping[str,Any])->str:
 raw=json.dumps(dict(payload),sort_keys=True,separators=(",",":"),default=str); return prefix+hashlib.sha256(raw.encode()).hexdigest()[:24]
def decision_record(*,opportunity_id:str,environment:str,pair:str,direction:str,strategy_version:str,score_version:str,risk_version:str,quality_score:float,confidence:float,gates:Mapping[str,Any],risk_decision:Mapping[str,Any],timestamp:Any=None)->dict[str,Any]:
 env=str(environment).upper()
 if env not in ENVIRONMENTS: raise ValueError("invalid environment")
 if not opportunity_id or not strategy_version or not score_version or not risk_version: raise ValueError("lineage incomplete")
 symbol=normalize_fx_symbol(pair); side=str(direction).upper()
 if side not in {"BUY","LONG","COMPRA","SELL","SHORT","VENDA"}: raise ValueError("invalid direction")
 payload={"schema_version":SCHEMA_VERSION,"opportunity_id":opportunity_id,"environment":env,"pair":f"{symbol[:3]}/{symbol[3:]}","direction":side,"strategy_version":strategy_version,"score_version":score_version,"risk_version":risk_version,"quality_score":_score(quality_score,"quality_score"),"confidence":_score(confidence,"confidence"),"gates":dict(gates or {}),"risk_decision":dict(risk_decision or {}),"timestamp":_iso(timestamp),"record_type":"DECISION","immutable_evidence":True}
 payload["record_id"]=_hash("DEC-",payload); return payload
def attach_result(decision:Mapping[str,Any],*,outcome:str,realized_r:float,mae_r:float|None=None,mfe_r:float|None=None,spread_cost_r:float=0,slippage_cost_r:float=0,closed_at:Any=None)->dict[str,Any]:
 d=dict(decision)
 if d.get("record_type")!="DECISION": raise ValueError("result requires decision record")
 vals=[realized_r,spread_cost_r,slippage_cost_r]+([mae_r] if mae_r is not None else [])+([mfe_r] if mfe_r is not None else [])
 if not all(math.isfinite(float(x)) for x in vals): raise ValueError("non-finite result")
 base={k:v for k,v in d.items() if k!="record_id"}; base.update({"record_type":"RESULT","decision_record_id":d["record_id"],"outcome":str(outcome).upper(),"realized_r":float(realized_r),"spread_cost_r":float(spread_cost_r),"slippage_cost_r":float(slippage_cost_r),"net_r":float(realized_r)-float(spread_cost_r)-float(slippage_cost_r),"mae_r":mae_r,"mfe_r":mfe_r,"closed_at":_iso(closed_at)})
 base["record_id"]=_hash("RES-",base); return base
def rejected_record(**kwargs)->dict[str,Any]:
 d=decision_record(**kwargs); base={k:v for k,v in d.items() if k!="record_id"}; base["record_type"]="REJECTED_OPPORTUNITY"; base["record_id"]=_hash("REJ-",base); return base
