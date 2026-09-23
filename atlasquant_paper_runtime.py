"""P0 Paper 24/7 state/recovery contract. No broker/live execution."""
from __future__ import annotations
from datetime import datetime,timezone
from typing import Any,Mapping,Sequence
import hashlib,json,math
from atlasquant_instrument_registry import normalize_fx_symbol
from atlasquant_paper_authorization_bridge import paper_request_id_for_authorization
from atlasquant_paper_state_audit import audit_paper_state

ACTIVE={"WAIT_ENTRY","OPEN","MANAGING"}

def _utc(value:datetime|None)->datetime:
    d=value or datetime.now(timezone.utc)
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)

def _positive(v:Any)->bool:
    try:return math.isfinite(float(v)) and float(v)>0
    except Exception:return False

def _symbol(v:Any)->str|None:
    try:return normalize_fx_symbol(str(v))
    except Exception:return None

def paper_state_snapshot(trades:Sequence[Mapping[str,Any]]|None, *, created_at:Any=None)->dict[str,Any]:
    rows=[dict(x) for x in (trades or [])]
    active=[r for r in rows if str(r.get("status","")).upper() in ACTIVE]
    payload={"active":active,"active_count":len(active),"created_at":str(created_at or datetime.now(timezone.utc).isoformat()),"environment":"PAPER","real_orders_enabled":False}
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),default=str)
    payload["checksum"]=hashlib.sha256(raw.encode()).hexdigest()
    return payload

def _entry_auth_ok(row:Mapping[str,Any],auth:Mapping[str,Any]|None,current:datetime)->bool:
    a=dict(auth or {})
    if a.get("approved") is not True or str(a.get("risk_gate","")).upper()!="APPROVED": return False
    if a.get("real_orders_enabled") is not False: return False
    if str(a.get("risk_auth_id",""))!=str(row.get("risk_auth_id","")): return False
    if str(a.get("opportunity_id",""))!=str(row.get("opportunity_id","")): return False
    if str(a.get("strategy_version",""))!=str(row.get("strategy_version","")): return False
    if _symbol(a.get("pair")) is None or _symbol(a.get("pair"))!=_symbol(row.get("pair")): return False
    if paper_request_id_for_authorization(a)!=str(row.get("paper_request_id","")): return False
    direction=str(a.get("direction","")).upper()
    if direction not in {"BUY","LONG","COMPRA","SELL","SHORT","VENDA"} or not _positive(a.get("stop_price")): return False
    try:
        exp=datetime.fromisoformat(str(a.get("expires_at")).replace("Z","+00:00"))
        exp=exp.replace(tzinfo=timezone.utc) if exp.tzinfo is None else exp.astimezone(timezone.utc)
        return current<exp
    except Exception:
        return False

def _market_index(current_market:Mapping[str,Any]|None)->tuple[dict[str,Any],list[str]]:
    out={};reasons=[]
    for key,value in dict(current_market or {}).items():
        sym=_symbol(key)
        if sym is None:
            reasons.append(f"MARKET_PAIR_INVALID:{key}");continue
        if sym in out:
            reasons.append(f"MARKET_PAIR_DUPLICATE:{sym}");continue
        out[sym]=value
    return out,reasons

def recover_paper_state(snapshot:Mapping[str,Any]|None, *, current_market:Mapping[str,Any]|None=None,
                        current_authorizations:Mapping[str,Mapping[str,Any]]|None=None,
                        now:datetime|None=None)->dict[str,Any]:
    s=dict(snapshot or {}); reasons=[]; current=_utc(now)
    if s.get("environment")!="PAPER": reasons.append("ENVIRONMENT_INVALID")
    if s.get("real_orders_enabled") is not False: reasons.append("LIVE_FLAG_INVALID")
    expected=s.get("checksum")
    tmp={k:v for k,v in s.items() if k!="checksum"}
    raw=json.dumps(tmp,sort_keys=True,separators=(",",":"),default=str)
    if not expected or hashlib.sha256(raw.encode()).hexdigest()!=expected: reasons.append("CHECKSUM_INVALID")
    active=[dict(x) for x in (s.get("active",[]) or [])]
    if not reasons:
        state_audit=audit_paper_state(active)
        if not state_audit["ok"]: reasons.extend(f"STATE:{x}" for x in state_audit["reasons"])
    market,market_reasons=_market_index(current_market)
    if market_reasons: reasons.extend(market_reasons)
    recovered=[]
    if not reasons:
        auths=dict(current_authorizations or {});seen=set()
        for r in active:
            pair=str(r.get("pair",""));sym=_symbol(pair);rid=str(r.get("paper_request_id","")).strip()
            if not rid or rid in seen:
                reasons.append("PAPER_REQUEST_ID_MISSING_OR_DUPLICATE");continue
            seen.add(rid);status=str(r.get("status","")).upper()
            market_ready=False
            if sym not in market:
                r["recovery_state"]="AWAITING_MARKET_RECONCILIATION"
            else:
                m=market[sym]
                if isinstance(m,Mapping) and m.get("fresh") is True and m.get("valid") is True and _positive(m.get("price")):
                    market_ready=True;r["reconciled_price"]=float(m.get("price"))
                else:
                    r["recovery_state"]="AWAITING_VALID_MARKET_DATA"
            if market_ready:
                if status=="WAIT_ENTRY":
                    aid=str(r.get("risk_auth_id","")).strip()
                    if not aid or not _entry_auth_ok(r,auths.get(aid),current):
                        r["recovery_state"]="REAUTHORIZATION_REQUIRED";r["entry_authorized"]=False
                    else:
                        r["recovery_state"]="RECOVERED";r["entry_authorized"]=True
                else:
                    r["recovery_state"]="RECOVERED";r["management_only"]=True
            recovered.append(r)
    if reasons: recovered=[]
    return {"ok":not reasons,"reasons":list(dict.fromkeys(reasons)),"trades":recovered,
            "environment":"PAPER","real_orders_enabled":False}
