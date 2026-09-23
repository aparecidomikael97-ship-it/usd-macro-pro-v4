"""P0 authoritative risk authorization contract. Broker-independent and fail-closed."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import uuid4
import math
from atlasquant_risk_guardian import RiskLimits,RiskState,evaluate_risk_guard
from atlasquant_instrument_registry import normalize_fx_symbol

@dataclass(frozen=True)
class RiskRequest:
    opportunity_id:str; pair:str; strategy_version:str
    requested_trade_risk:float; requested_exposure:float
    structural_stop_valid:bool; rr_after_costs:float|None
    spread_ok:bool; slippage_ok:bool; liquidity_ok:bool; volatility_ok:bool
    news_clear:bool; data_fresh:bool; opportunity_state:str
    cluster_limit_ok:bool=True; correlation_limit_ok:bool=True; portfolio_lock_ok:bool=True
    direction:str|None=None; entry_price:float|None=None; stop_price:float|None=None

def _finite_positive(v:Any)->bool:
    try:return math.isfinite(float(v)) and float(v)>0
    except Exception:return False

def _utc(value:datetime|None)->datetime:
    d=value or datetime.now(timezone.utc)
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)

def _pair(value:Any)->str|None:
    try:
        s=normalize_fx_symbol(str(value));return f"{s[:3]}/{s[3:]}"
    except Exception:return None

def _side(value:Any)->str|None:
    d=str(value or "").upper()
    if d in {"BUY","LONG","COMPRA"}:return "BUY"
    if d in {"SELL","SHORT","VENDA"}:return "SELL"
    return None

def _geometry_ok(side:str|None,entry:Any,stop:Any)->bool:
    if side is None or not (_finite_positive(entry) and _finite_positive(stop)):return False
    return float(stop)<float(entry) if side=="BUY" else float(stop)>float(entry)

def authorize_risk(req:RiskRequest, limits:RiskLimits, state:RiskState, *, min_rr:float=1.0,
                   now:datetime|None=None, ttl_minutes:int=5)->dict[str,Any]:
    reasons=[];pair=_pair(req.pair);side=_side(req.direction)
    if not str(req.opportunity_id).strip(): reasons.append("OPPORTUNITY_ID_MISSING")
    if not str(req.strategy_version).strip(): reasons.append("STRATEGY_VERSION_MISSING")
    if pair is None: reasons.append("PAIR_INVALID")
    if side is None: reasons.append("DIRECTION_INVALID")
    if not _finite_positive(req.entry_price): reasons.append("ENTRY_PRICE_INVALID")
    if not _finite_positive(req.stop_price): reasons.append("STOP_PRICE_INVALID")
    if req.structural_stop_valid is not True or not _geometry_ok(side,req.entry_price,req.stop_price):
        reasons.append("STRUCTURAL_STOP_INVALID")
    if not _finite_positive(min_rr): reasons.append("MIN_RR_INVALID")
    if req.rr_after_costs is None or not _finite_positive(req.rr_after_costs): reasons.append("RR_INVALID")
    elif _finite_positive(min_rr) and float(req.rr_after_costs)<float(min_rr): reasons.append("RR_INSUFFICIENT")
    if not _finite_positive(req.requested_trade_risk): reasons.append("TRADE_RISK_INVALID")
    if not _finite_positive(req.requested_exposure): reasons.append("EXPOSURE_INVALID")
    for ok,code in ((req.spread_ok,"SPREAD_TOO_HIGH"),(req.slippage_ok,"SLIPPAGE_GUARD"),
                    (req.liquidity_ok,"LIQUIDITY_GUARD"),(req.volatility_ok,"VOLATILITY_GUARD"),
                    (req.news_clear,"NEWS_LOCK"),(req.data_fresh,"DATA_STALE"),
                    (req.cluster_limit_ok,"RISK_CLUSTER_LIMIT"),(req.correlation_limit_ok,"CORRELATION_LIMIT"),
                    (req.portfolio_lock_ok,"PORTFOLIO_RISK_LOCK")):
        if ok is not True: reasons.append(code)
    if str(req.opportunity_state).upper()!="TRIGGERED": reasons.append("OPPORTUNITY_NOT_TRIGGERED")
    try:
        if isinstance(ttl_minutes,bool):raise ValueError
        ttl=int(ttl_minutes)
        if ttl<1 or ttl>60 or float(ttl_minutes)!=ttl:raise ValueError
    except Exception:
        ttl=0;reasons.append("AUTH_TTL_INVALID")
    try:
        guard=evaluate_risk_guard(limits,state,requested_trade_risk=req.requested_trade_risk,requested_exposure=req.requested_exposure)
        reasons.extend(f"GUARD:{x}" for x in guard.reasons)
    except Exception:
        reasons.append("RISK_ENGINE_ERROR")
    reasons=list(dict.fromkeys(reasons));approved=not reasons;current=_utc(now)
    return {"risk_gate":"APPROVED" if approved else "BLOCKED","approved":approved,"execution_grade":approved,
            "risk_auth_id":f"RISK-{uuid4().hex}" if approved else None,"issued_at":current.isoformat(),
            "expires_at":(current+timedelta(minutes=ttl)).isoformat() if approved else None,
            "opportunity_id":req.opportunity_id,"pair":pair or str(req.pair),"strategy_version":req.strategy_version,
            "direction":side,"entry_price":float(req.entry_price) if _finite_positive(req.entry_price) else req.entry_price,
            "stop_price":float(req.stop_price) if _finite_positive(req.stop_price) else req.stop_price,
            "max_authorized_risk":float(req.requested_trade_risk) if approved else 0.0,
            "max_authorized_exposure":float(req.requested_exposure) if approved else 0.0,
            "reasons":reasons,"real_orders_enabled":False,"fail_closed":True}
