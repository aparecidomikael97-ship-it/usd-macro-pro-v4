"""P0 authoritative risk authorization contract. Broker-independent and fail-closed."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Mapping
from uuid import uuid4
from atlasquant_risk_guardian import RiskLimits,RiskState,evaluate_risk_guard

@dataclass(frozen=True)
class RiskRequest:
    opportunity_id:str; pair:str; strategy_version:str
    requested_trade_risk:float; requested_exposure:float
    structural_stop_valid:bool; rr_after_costs:float|None
    spread_ok:bool; slippage_ok:bool; liquidity_ok:bool; volatility_ok:bool
    news_clear:bool; data_fresh:bool; opportunity_state:str
    cluster_limit_ok:bool=True; correlation_limit_ok:bool=True

def authorize_risk(req:RiskRequest, limits:RiskLimits, state:RiskState, *,
                   min_rr:float=1.0, now:datetime|None=None, ttl_minutes:int=5)->dict[str,Any]:
    reasons=[]
    if not req.opportunity_id.strip(): reasons.append("OPPORTUNITY_ID_MISSING")
    if not req.strategy_version.strip(): reasons.append("STRATEGY_VERSION_MISSING")
    if not req.structural_stop_valid: reasons.append("STRUCTURAL_STOP_INVALID")
    if req.rr_after_costs is None: reasons.append("RR_MISSING")
    elif float(req.rr_after_costs)<float(min_rr): reasons.append("RR_INSUFFICIENT")
    for ok,code in ((req.spread_ok,"SPREAD_TOO_HIGH"),(req.slippage_ok,"SLIPPAGE_GUARD"),
                    (req.liquidity_ok,"LIQUIDITY_GUARD"),(req.volatility_ok,"VOLATILITY_GUARD"),
                    (req.news_clear,"NEWS_LOCK"),(req.data_fresh,"DATA_STALE"),
                    (req.cluster_limit_ok,"RISK_CLUSTER_LIMIT"),(req.correlation_limit_ok,"CORRELATION_LIMIT")):
        if ok is not True: reasons.append(code)
    if str(req.opportunity_state).upper()!="TRIGGERED": reasons.append("OPPORTUNITY_NOT_TRIGGERED")
    try:
        guard=evaluate_risk_guard(limits,state,requested_trade_risk=req.requested_trade_risk,requested_exposure=req.requested_exposure)
        reasons.extend(f"GUARD:{x}" for x in guard.reasons)
    except Exception as exc:
        reasons.append("RISK_ENGINE_ERROR")
        guard=None
    approved=not reasons
    current=now or datetime.now(timezone.utc)
    auth_id=f"RISK-{uuid4().hex}" if approved else None
    return {"risk_gate":"APPROVED" if approved else "BLOCKED","approved":approved,
            "risk_auth_id":auth_id,"expires_at":(current+timedelta(minutes=max(1,int(ttl_minutes)))).isoformat() if approved else None,
            "opportunity_id":req.opportunity_id,"pair":req.pair,"strategy_version":req.strategy_version,
            "max_authorized_risk":req.requested_trade_risk if approved else 0.0,
            "max_authorized_exposure":req.requested_exposure if approved else 0.0,
            "reasons":reasons,"real_orders_enabled":False,"fail_closed":True}
