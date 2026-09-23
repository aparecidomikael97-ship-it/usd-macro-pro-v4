"""P0 Paper 24/7 state/recovery contract. No broker/live execution."""
from __future__ import annotations
from datetime import datetime,timezone
from typing import Any,Mapping,Sequence
import hashlib,json

ACTIVE={"WAIT_ENTRY","OPEN","MANAGING"}

def paper_state_snapshot(trades:Sequence[Mapping[str,Any]]|None, *, created_at:Any=None)->dict[str,Any]:
    rows=[dict(x) for x in (trades or [])]
    active=[r for r in rows if str(r.get("status","")).upper() in ACTIVE]
    payload={"active":active,"active_count":len(active),"created_at":str(created_at or datetime.now(timezone.utc).isoformat()),"environment":"PAPER","real_orders_enabled":False}
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),default=str)
    payload["checksum"]=hashlib.sha256(raw.encode()).hexdigest()
    return payload

def recover_paper_state(snapshot:Mapping[str,Any]|None, *, current_market:Mapping[str,Any]|None=None)->dict[str,Any]:
    s=dict(snapshot or {}); reasons=[]
    if s.get("environment")!="PAPER": reasons.append("ENVIRONMENT_INVALID")
    if s.get("real_orders_enabled") is not False: reasons.append("LIVE_FLAG_INVALID")
    expected=s.get("checksum")
    tmp={k:v for k,v in s.items() if k!="checksum"}
    raw=json.dumps(tmp,sort_keys=True,separators=(",",":"),default=str)
    if not expected or hashlib.sha256(raw.encode()).hexdigest()!=expected: reasons.append("CHECKSUM_INVALID")
    recovered=[]
    if not reasons:
        market=dict(current_market or {})
        seen=set()
        for row in s.get("active",[]) or []:
            r=dict(row); pair=str(r.get("pair","")); rid=str(r.get("paper_request_id","")).strip()
            if not rid or rid in seen:
                reasons.append("PAPER_REQUEST_ID_MISSING_OR_DUPLICATE"); continue
            seen.add(rid)
            if pair not in market:
                r["recovery_state"]="AWAITING_MARKET_RECONCILIATION"
            else:
                m=market[pair]
                if isinstance(m,Mapping):
                    if m.get("fresh") is not True or m.get("valid") is not True:
                        r["recovery_state"]="AWAITING_VALID_MARKET_DATA"
                    else:
                        r["recovery_state"]="RECOVERED"; r["reconciled_price"]=m.get("price")
                else:
                    r["recovery_state"]="AWAITING_VALID_MARKET_DATA"
            recovered.append(r)
    if reasons: recovered=[]
    return {"ok":not reasons,"reasons":reasons,"trades":recovered,"environment":"PAPER","real_orders_enabled":False}
