"""P0 Paper entry activator. Converts WAIT_ENTRY to OPEN only with fresh evidence.

Pure state transition: no broker calls, no live execution.
"""
from __future__ import annotations
from datetime import datetime,timezone
from typing import Any,Mapping
import hashlib,math
from atlasquant_instrument_registry import normalize_fx_symbol

def _utc(value:datetime|None)->datetime:
    d=value or datetime.now(timezone.utc)
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)

def _positive(v:Any)->bool:
    try: return math.isfinite(float(v)) and float(v)>0
    except Exception: return False

def _pair(v:Any)->str|None:
    try:
        s=normalize_fx_symbol(str(v));return f"{s[:3]}/{s[3:]}"
    except Exception:return None

def activate_paper_entry(waiting_trade:Mapping[str,Any],auth:Mapping[str,Any],market:Mapping[str,Any],
                         *,system_state:str="NORMAL",now:datetime|None=None)->dict[str,Any]:
    t=dict(waiting_trade or {});a=dict(auth or {});m=dict(market or {});reasons=[];current=_utc(now)
    status=str(t.get("status","")).upper()
    if status in {"OPEN","MANAGING"} and str(t.get("entry_event_id","")).strip():
        return {"state":"ALREADY_OPEN","opened":False,"trade":t,"reasons":["IDEMPOTENCY_GUARD"],"real_orders_enabled":False}
    if status!="WAIT_ENTRY": reasons.append("TRADE_NOT_WAIT_ENTRY")
    if str(t.get("environment","")).upper()!="PAPER": reasons.append("TRADE_ENVIRONMENT_INVALID")
    if t.get("real_orders_enabled") is not False: reasons.append("TRADE_LIVE_FLAG_INVALID")
    if str(system_state).upper()!="NORMAL": reasons.append("SYSTEM_HEALTH_NOT_NORMAL")
    for key,code in (("risk_auth_id","RISK_AUTH_ID_MISMATCH"),("opportunity_id","OPPORTUNITY_MISMATCH"),("strategy_version","STRATEGY_MISMATCH")):
        if not str(t.get(key,"")).strip() or str(t.get(key))!=str(a.get(key)): reasons.append(code)
    tp=_pair(t.get("pair"));ap=_pair(a.get("pair"))
    if tp is None or ap is None: reasons.append("PAIR_INVALID")
    elif tp!=ap: reasons.append("PAIR_MISMATCH")
    if a.get("approved") is not True or str(a.get("risk_gate","")).upper()!="APPROVED": reasons.append("RISK_NOT_APPROVED")
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
    rid=str(t.get("paper_request_id","")).strip()
    if not rid:
        return {"state":"REJECTED","opened":False,"trade":t,"reasons":["PAPER_REQUEST_ID_MISSING"],"real_orders_enabled":False}
    seed=f"{rid}|{a.get('risk_auth_id')}|ENTRY"
    out=dict(t)
    out.update({"status":"OPEN","entry_price":float(price),"stop_price":float(stop),"direction":direction,"opened_at":current.isoformat(),
                "entry_event_id":"PENTRY-"+hashlib.sha256(seed.encode()).hexdigest()[:20],
                "entry_authorized":True,"environment":"PAPER","real_orders_enabled":False})
    return {"state":"OPENED","opened":True,"trade":out,"reasons":[],"real_orders_enabled":False}
