"""P0 Paper active-state invariant audit. Pure validation; no execution."""
from __future__ import annotations
from typing import Any,Mapping,Sequence
import math

VALID_STATUS={"WAIT_ENTRY","OPEN","MANAGING","CLOSED","INVALIDATED"}
ACTIVE={"WAIT_ENTRY","OPEN","MANAGING"}

def _positive(v:Any)->bool:
    try:return math.isfinite(float(v)) and float(v)>0
    except Exception:return False

def audit_paper_state(rows:Sequence[Mapping[str,Any]]|None)->dict[str,Any]:
    data=[dict(x) for x in (rows or [])];reasons=[];seen_req=set();seen_opp=set();seen_entry=set();active=0
    for i,r in enumerate(data):
        p=f"ROW_{i}"
        if str(r.get("environment","")).upper()!="PAPER": reasons.append(f"{p}:ENVIRONMENT_INVALID")
        if r.get("real_orders_enabled") is not False: reasons.append(f"{p}:LIVE_FLAG_INVALID")
        status=str(r.get("status","")).upper()
        if status not in VALID_STATUS: reasons.append(f"{p}:STATUS_INVALID");continue
        rid=str(r.get("paper_request_id","")).strip();oid=str(r.get("opportunity_id","")).strip()
        if not rid: reasons.append(f"{p}:PAPER_REQUEST_ID_MISSING")
        elif rid in seen_req: reasons.append(f"DUPLICATE_PAPER_REQUEST_ID:{rid}")
        else: seen_req.add(rid)
        if not oid: reasons.append(f"{p}:OPPORTUNITY_ID_MISSING")
        elif oid in seen_opp and status in ACTIVE: reasons.append(f"DUPLICATE_ACTIVE_OPPORTUNITY_ID:{oid}")
        elif status in ACTIVE: seen_opp.add(oid)
        if status in ACTIVE: active+=1
        if status=="WAIT_ENTRY":
            if not str(r.get("risk_auth_id","")).strip(): reasons.append(f"{p}:RISK_AUTH_ID_MISSING")
            if r.get("entry_event_id") or r.get("entry_price") is not None or r.get("opened_at"):
                reasons.append(f"{p}:WAIT_ENTRY_HAS_FILL_EVIDENCE")
        if status in {"OPEN","MANAGING"}:
            eid=str(r.get("entry_event_id","")).strip()
            if not eid: reasons.append(f"{p}:ENTRY_EVENT_ID_MISSING")
            elif eid in seen_entry: reasons.append(f"DUPLICATE_ENTRY_EVENT_ID:{eid}")
            else: seen_entry.add(eid)
            if not _positive(r.get("entry_price")): reasons.append(f"{p}:ENTRY_PRICE_INVALID")
            if not _positive(r.get("stop_price")): reasons.append(f"{p}:STOP_PRICE_INVALID")
            if not str(r.get("opened_at","")).strip(): reasons.append(f"{p}:OPENED_AT_MISSING")
            direction=str(r.get("direction","")).upper()
            if direction not in {"BUY","LONG","COMPRA","SELL","SHORT","VENDA"}: reasons.append(f"{p}:DIRECTION_INVALID")
            if status=="OPEN" and _positive(r.get("entry_price")) and _positive(r.get("stop_price")):
                entry=float(r["entry_price"]);stop=float(r["stop_price"])
                if direction in {"BUY","LONG","COMPRA"} and not stop<entry: reasons.append(f"{p}:INITIAL_STOP_GEOMETRY_INVALID")
                if direction in {"SELL","SHORT","VENDA"} and not stop>entry: reasons.append(f"{p}:INITIAL_STOP_GEOMETRY_INVALID")
    reasons=list(dict.fromkeys(reasons));ok=not reasons
    return {"ok":ok,"state":"NORMAL" if ok else "PROTECTED","reasons":reasons,"rows":len(data),"active_count":active,
            "new_entries_allowed":ok,"management_allowed":True,"management_mode":"NORMAL" if ok else "SAFE_ONLY",
            "real_orders_enabled":False}
