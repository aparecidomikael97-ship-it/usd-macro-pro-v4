"""P0 audit for persisted Paper RESULT evidence. Any ambiguity protects new entries."""
from __future__ import annotations
from typing import Any,Mapping,Sequence
import math

def _finite(v:Any)->float|None:
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:
        return None

def audit_paper_results(rows:Sequence[Mapping[str,Any]]|None)->dict[str,Any]:
    data=[dict(x) for x in (rows or [])]; reasons=[]; valid=[]
    seen_record={}; seen_decision={}; seen_request={}
    for i,r in enumerate(data):
        prefix=f"ROW_{i}"
        if str(r.get("environment","")).upper()!="PAPER":
            reasons.append(f"{prefix}:ENVIRONMENT_INVALID"); continue
        if str(r.get("record_type","")).upper()!="RESULT":
            reasons.append(f"{prefix}:RECORD_TYPE_INVALID"); continue
        if r.get("real_orders_enabled") is not False:
            reasons.append(f"{prefix}:LIVE_FLAG_INVALID")
        for key,code,seen in (("record_id","RECORD_ID",seen_record),("decision_record_id","DECISION_RECORD_ID",seen_decision),("paper_request_id","PAPER_REQUEST_ID",seen_request)):
            v=str(r.get(key,"")).strip()
            if not v: reasons.append(f"{prefix}:{code}_MISSING")
            else: seen[v]=seen.get(v,0)+1
        realized=_finite(r.get("realized_r")); spread=_finite(r.get("spread_cost_r")); slip=_finite(r.get("slippage_cost_r")); net=_finite(r.get("net_r"))
        if realized is None: reasons.append(f"{prefix}:REALIZED_R_INVALID")
        if spread is None or spread<0: reasons.append(f"{prefix}:SPREAD_COST_INVALID")
        if slip is None or slip<0: reasons.append(f"{prefix}:SLIPPAGE_COST_INVALID")
        if net is None: reasons.append(f"{prefix}:NET_R_INVALID")
        if None not in (realized,spread,slip,net) and abs(net-(realized-spread-slip))>1e-9:
            reasons.append(f"{prefix}:NET_R_ARITHMETIC_MISMATCH")
        if net is not None:
            expected="BREAKEVEN" if abs(net)<1e-12 else ("WIN" if net>0 else "LOSS")
            if str(r.get("outcome","")).upper()!=expected: reasons.append(f"{prefix}:OUTCOME_NET_R_MISMATCH")
        if str(r.get("status","CLOSED")).upper()!="CLOSED": reasons.append(f"{prefix}:STATUS_NOT_CLOSED")
        if not str(r.get("opportunity_id","")).strip() or not str(r.get("strategy_version","")).strip():
            reasons.append(f"{prefix}:LINEAGE_INCOMPLETE")
        valid.append(r)
    for label,seen in (("RECORD_ID",seen_record),("DECISION_RECORD_ID",seen_decision),("PAPER_REQUEST_ID",seen_request)):
        for value,count in seen.items():
            if count>1: reasons.append(f"DUPLICATE_{label}:{value}")
    reasons=list(dict.fromkeys(reasons)); ok=not reasons
    return {"ok":ok,"state":"NORMAL" if ok else "PROTECTED","new_entries_allowed":ok,
            "management_allowed":True,"management_mode":"NORMAL" if ok else "SAFE_ONLY",
            "result_count":len(data),"valid_result_rows":len(valid),"reasons":reasons,
            "real_orders_enabled":False}
