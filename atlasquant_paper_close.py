"""P0 Paper close finalizer: idempotent, evidence-linked, never broker/live."""
from __future__ import annotations
from datetime import datetime,timezone
from typing import Any,Mapping,Sequence
import math
from atlasquant_result_store import attach_result
from atlasquant_evidence_ledger import append_evidence

CLOSABLE={"OPEN","MANAGING"}
OUTCOMES={"WIN","LOSS","BREAKEVEN"}

def _finite(v:Any)->float|None:
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:
        return None

def _utc_iso(v:Any)->str|None:
    try:
        if isinstance(v,datetime): d=v
        else: d=datetime.fromisoformat(str(v).replace("Z","+00:00"))
        d=d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
        return d.isoformat()
    except Exception:
        return None

def _norm_pair(v:Any)->str:
    return str(v or "").replace("-","/").replace("_","/").upper().strip()

def close_paper_trade(trade:Mapping[str,Any],decision:Mapping[str,Any],existing_results:Sequence[Mapping[str,Any]]|None=None,
                      *,realized_r:float,spread_cost_r:float=0,slippage_cost_r:float=0,
                      mae_r:float|None=None,mfe_r:float|None=None,outcome:str|None=None,closed_at:Any=None)->dict[str,Any]:
    t=dict(trade or {}); d=dict(decision or {}); existing=[dict(x) for x in (existing_results or [])]; reasons=[]
    if str(t.get("environment","")).upper()!="PAPER": reasons.append("TRADE_ENVIRONMENT_INVALID")
    if t.get("real_orders_enabled") is not False: reasons.append("TRADE_LIVE_FLAG_INVALID")
    if str(t.get("status","")).upper() not in CLOSABLE: reasons.append("TRADE_NOT_CLOSABLE")
    if str(d.get("environment","")).upper()!="PAPER" or d.get("record_type")!="DECISION": reasons.append("DECISION_INVALID")
    if d.get("immutable_evidence") is not True: reasons.append("DECISION_NOT_IMMUTABLE")
    for key,code in (("opportunity_id","OPPORTUNITY_MISMATCH"),("strategy_version","STRATEGY_MISMATCH")):
        if str(t.get(key,""))!=str(d.get(key,"")): reasons.append(code)
    if _norm_pair(t.get("pair"))!=_norm_pair(d.get("pair")): reasons.append("PAIR_MISMATCH")
    if not str(t.get("paper_request_id","")).strip() or str(t.get("paper_request_id"))!=str(d.get("paper_request_id")):
        reasons.append("PAPER_REQUEST_ID_MISMATCH")
    rid=str(d.get("record_id","")).strip()
    if not rid: reasons.append("DECISION_RECORD_ID_MISSING")
    same=[r for r in existing if str(r.get("decision_record_id",""))==rid or (str(t.get("paper_request_id","")).strip() and str(r.get("paper_request_id",""))==str(t.get("paper_request_id")))]
    if len(same)>1:
        return {"state":"RECOVERY_REQUIRED","closed":False,"reasons":["DUPLICATE_CLOSE_EVIDENCE"],"real_orders_enabled":False}
    if len(same)==1:
        return {"state":"ALREADY_CLOSED","closed":False,"existing_result":same[0],"reasons":["IDEMPOTENCY_GUARD"],"real_orders_enabled":False}
    rr=_finite(realized_r); sc=_finite(spread_cost_r); sl=_finite(slippage_cost_r)
    if rr is None: reasons.append("REALIZED_R_INVALID")
    if sc is None or sc<0: reasons.append("SPREAD_COST_INVALID")
    if sl is None or sl<0: reasons.append("SLIPPAGE_COST_INVALID")
    if mae_r is not None and _finite(mae_r) is None: reasons.append("MAE_INVALID")
    if mfe_r is not None and _finite(mfe_r) is None: reasons.append("MFE_INVALID")
    close_iso=_utc_iso(closed_at or datetime.now(timezone.utc))
    decision_iso=_utc_iso(d.get("timestamp"))
    if close_iso is None: reasons.append("CLOSED_AT_INVALID")
    elif decision_iso is not None and close_iso<decision_iso: reasons.append("CLOSED_BEFORE_DECISION")
    net=None if None in (rr,sc,sl) else rr-sc-sl
    inferred="BREAKEVEN" if net is not None and abs(net)<1e-12 else ("WIN" if net is not None and net>0 else "LOSS")
    requested=str(outcome).upper() if outcome is not None else inferred
    if requested not in OUTCOMES: reasons.append("OUTCOME_INVALID")
    elif net is not None and requested!=inferred: reasons.append("OUTCOME_NET_R_MISMATCH")
    if reasons:
        return {"state":"REJECTED","closed":False,"reasons":reasons,"real_orders_enabled":False}
    result=attach_result(d,outcome=requested,realized_r=rr,spread_cost_r=sc,slippage_cost_r=sl,mae_r=mae_r,mfe_r=mfe_r,closed_at=close_iso)
    result["paper_request_id"]=t["paper_request_id"]; result["risk_auth_id"]=t.get("risk_auth_id"); result["status"]="CLOSED"
    result["real_orders_enabled"]=False
    return {"state":"CLOSED","closed":True,"result":result,"reasons":[],"real_orders_enabled":False}


def close_and_append_paper_result(trade:Mapping[str,Any],decision:Mapping[str,Any],evidence_ledger:Sequence[Mapping[str,Any]]|None,
                                  *,realized_r:float,spread_cost_r:float=0,slippage_cost_r:float=0,
                                  mae_r:float|None=None,mfe_r:float|None=None,outcome:str|None=None,closed_at:Any=None)->dict[str,Any]:
    """Finalize one Paper trade and atomically validate its append contract."""
    ledger=[dict(x) for x in (evidence_ledger or [])]
    rid=str(decision.get("record_id","")).strip()
    parents=[x for x in ledger if str(x.get("record_id","")).strip()==rid and str(x.get("record_type","")).upper()=="DECISION"]
    if len(parents)!=1:
        return {"state":"REJECTED","closed":False,"appended":False,"ledger":ledger,
                "reasons":["DECISION_NOT_PERSISTED_UNIQUELY"],"real_orders_enabled":False}
    finalized=close_paper_trade(trade,decision,[x for x in ledger if str(x.get("record_type","")).upper()=="RESULT"],
                                realized_r=realized_r,spread_cost_r=spread_cost_r,slippage_cost_r=slippage_cost_r,
                                mae_r=mae_r,mfe_r=mfe_r,outcome=outcome,closed_at=closed_at)
    if not finalized.get("closed"):
        return {**finalized,"appended":False,"ledger":ledger}
    app=append_evidence(ledger,finalized["result"])
    if not app.get("appended"):
        return {"state":app["state"],"closed":True,"appended":False,"result":finalized["result"],
                "ledger":ledger,"reasons":app["reasons"],"real_orders_enabled":False}
    return {"state":"CLOSED_AND_APPENDED","closed":True,"appended":True,"result":finalized["result"],
            "ledger":app["ledger"],"reasons":[],"real_orders_enabled":False}
