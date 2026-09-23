"""P0 Paper entry activator. Converts WAIT_ENTRY to OPEN only with fresh evidence.

Pure state transition: no broker calls, no live execution.
"""
from __future__ import annotations
from datetime import datetime,timezone
from typing import Any,Mapping
import hashlib,math
from atlasquant_instrument_registry import normalize_fx_symbol
from atlasquant_paper_authorization_bridge import paper_request_id_for_authorization

def _utc(value:datetime|None)->datetime:
    d=value or datetime.now(timezone.utc)
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)

def _positive(v:Any)->bool:
    try:return math.isfinite(float(v)) and float(v)>0
    except Exception:return False

def _pair(v:Any)->str|None:
    try:
        s=normalize_fx_symbol(str(v));return f"{s[:3]}/{s[3:]}"
    except Exception:return None

def _entry_event_id(request_id:str,risk_auth_id:str)->str:
    seed=f"{request_id}|{risk_auth_id}|ENTRY"
    return "PENTRY-"+hashlib.sha256(seed.encode()).hexdigest()[:20]

def _static_identity_reasons(t:Mapping[str,Any],a:Mapping[str,Any])->list[str]:
    reasons=[]
    if str(t.get("environment","")).upper()!="PAPER": reasons.append("TRADE_ENVIRONMENT_INVALID")
    if t.get("real_orders_enabled") is not False: reasons.append("TRADE_LIVE_FLAG_INVALID")
    for key,code in (("risk_auth_id","RISK_AUTH_ID_MISMATCH"),("opportunity_id","OPPORTUNITY_MISMATCH"),("strategy_version","STRATEGY_MISMATCH")):
        if not str(t.get(key,"")).strip() or str(t.get(key))!=str(a.get(key)): reasons.append(code)
    tp=_pair(t.get("pair"));ap=_pair(a.get("pair"))
    if tp is None or ap is None: reasons.append("PAIR_INVALID")
    elif tp!=ap: reasons.append("PAIR_MISMATCH")
    rid=str(t.get("paper_request_id","")).strip()
    if not rid: reasons.append("PAPER_REQUEST_ID_MISSING")
    else:
        expected=paper_request_id_for_authorization(a)
        if not expected or rid!=expected: reasons.append("PAPER_REQUEST_ID_AUTH_MISMATCH")
    return list(dict.fromkeys(reasons))

def activate_paper_entry(waiting_trade:Mapping[str,Any],auth:Mapping[str,Any],market:Mapping[str,Any],
                         *,system_state:str="NORMAL",now:datetime|None=None)->dict[str,Any]:
    t=dict(waiting_trade or {});a=dict(auth or {});m=dict(market or {});current=_utc(now)
    status=str(t.get("status","")).upper()
    static=_static_identity_reasons(t,a)
    rid=str(t.get("paper_request_id","")).strip(); aid=str(a.get("risk_auth_id","")).strip()
    expected_event=_entry_event_id(rid,aid) if rid and aid else None
    if status in {"OPEN","MANAGING"}:
        reasons=list(static)
        if str(t.get("entry_event_id","")).strip()!=str(expected_event or ""): reasons.append("ENTRY_EVENT_ID_INVALID")
        if not _positive(t.get("entry_price")): reasons.append("ENTRY_PRICE_INVALID")
        if not _positive(t.get("stop_price")): reasons.append("STRUCTURAL_STOP_PRICE_INVALID")
        if reasons:
            return {"state":"REJECTED","opened":False,"trade":t,"reasons":list(dict.fromkeys(reasons)),"real_orders_enabled":False}
        return {"state":"ALREADY_OPEN","opened":False,"trade":t,"reasons":["IDEMPOTENCY_GUARD"],"real_orders_enabled":False}

    reasons=list(static)
    if status!="WAIT_ENTRY": reasons.append("TRADE_NOT_WAIT_ENTRY")
    if str(system_state).upper()!="NORMAL": reasons.append("SYSTEM_HEALTH_NOT_NORMAL")
    if a.get("approved") is not True or str(a.get("risk_gate","")).upper()!="APPROVED": reasons.append("RISK_NOT_APPROVED")
    if a.get("fail_closed") is not True: reasons.append("RISK_AUTH_CONTRACT_INVALID")
    if not _positive(a.get("max_authorized_risk")): reasons.append("AUTHORIZED_RISK_INVALID")
    if not _positive(a.get("max_authorized_exposure")): reasons.append("AUTHORIZED_EXPOSURE_INVALID")
    if a.get("real_orders_enabled") is not False: reasons.append("AUTH_LIVE_FLAG_INVALID")
    try:
        exp=datetime.fromisoformat(str(a.get("expires_at")).replace("Z","+00:00"))
        exp=exp.replace(tzinfo=timezone.utc) if exp.tzinfo is None else exp.astimezone(timezone.utc)
        if current>=exp: reasons.append("RISK_AUTH_EXPIRED")
    except Exception: reasons.append("RISK_AUTH_EXPIRY_INVALID")
    if m.get("fresh") is not True: reasons.append("MARKET_DATA_STALE")
    if m.get("valid") is not True: reasons.append("MARKET_DATA_INVALID")
    price=m.get("price")
    if not _positive(price): reasons.append("ENTRY_PRICE_INVALID")
    direction=str(a.get("direction","")).upper()
    stop=a.get("stop_price")
    if direction not in {"BUY","LONG","COMPRA","SELL","SHORT","VENDA"}: reasons.append("DIRECTION_INVALID")
    if not _positive(stop): reasons.append("STRUCTURAL_STOP_PRICE_INVALID")
    if _positive(price) and _positive(stop):
        if direction in {"BUY","LONG","COMPRA"} and not float(stop)<float(price): reasons.append("STOP_GEOMETRY_INVALID")
        if direction in {"SELL","SHORT","VENDA"} and not float(stop)>float(price): reasons.append("STOP_GEOMETRY_INVALID")
    if reasons:
        return {"state":"REJECTED","opened":False,"trade":t,"reasons":list(dict.fromkeys(reasons)),"real_orders_enabled":False}
    out=dict(t)
    out.update({"status":"OPEN","entry_price":float(price),"stop_price":float(stop),"direction":direction,"opened_at":current.isoformat(),
                "entry_event_id":expected_event,"entry_authorized":True,"environment":"PAPER","real_orders_enabled":False})
    return {"state":"OPENED","opened":True,"trade":out,"reasons":[],"real_orders_enabled":False}
