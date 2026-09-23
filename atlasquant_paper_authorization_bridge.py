"""P0 bridge: Risk Authorization -> Paper only. Never broker/live."""
from __future__ import annotations
from datetime import datetime,timezone
from typing import Any,Mapping
from atlasquant_paper_audit_bridge import audit_paper_decision
from atlasquant_instrument_registry import normalize_fx_symbol
import hashlib,math

def _utc(value:datetime|None)->datetime:
    d=value or datetime.now(timezone.utc)
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)

def _positive(value:Any)->bool:
    try: return math.isfinite(float(value)) and float(value)>0
    except Exception: return False

def _pair(value:Any)->str|None:
    try:
        s=normalize_fx_symbol(str(value)); return f"{s[:3]}/{s[3:]}"
    except Exception: return None

def paper_request_id_for_authorization(auth:Mapping[str,Any])->str|None:
    a=dict(auth or {});pair=_pair(a.get("pair"))
    if not str(a.get("risk_auth_id") or "").strip() or not str(a.get("opportunity_id") or "").strip() or not str(a.get("strategy_version") or "").strip() or pair is None:
        return None
    seed=f"{a.get('risk_auth_id')}|{a.get('opportunity_id')}|{a.get('strategy_version')}|{pair}"
    return "PAPER-"+hashlib.sha256(seed.encode()).hexdigest()[:20]

def paper_request_from_authorization(auth:Mapping[str,Any], *, now:datetime|None=None, opportunity_id:str|None=None,
                                     strategy_version:str|None=None, pair:str|None=None,
                                     requested_risk:float|None=None, requested_exposure:float|None=None)->dict[str,Any]:
    a=dict(auth or {}); current=_utc(now); reasons=[]
    if a.get("approved") is not True or str(a.get("risk_gate","")).upper()!="APPROVED": reasons.append("RISK_NOT_APPROVED")
    if not str(a.get("risk_auth_id") or "").strip(): reasons.append("RISK_AUTH_ID_MISSING")
    try:
        expiry=datetime.fromisoformat(str(a.get("expires_at")).replace("Z","+00:00"))
        expiry=expiry.replace(tzinfo=timezone.utc) if expiry.tzinfo is None else expiry.astimezone(timezone.utc)
        if current>=expiry: reasons.append("RISK_AUTH_EXPIRED")
    except Exception: reasons.append("RISK_AUTH_EXPIRY_INVALID")
    if a.get("real_orders_enabled") is not False: reasons.append("LIVE_FLAG_NOT_EXPLICITLY_DISABLED")
    if a.get("fail_closed") is not True or a.get("execution_grade") is not True: reasons.append("RISK_AUTH_CONTRACT_INVALID")
    if opportunity_id is not None and str(a.get("opportunity_id"))!=str(opportunity_id): reasons.append("RISK_AUTH_OPPORTUNITY_MISMATCH")
    if strategy_version is not None and str(a.get("strategy_version"))!=str(strategy_version): reasons.append("RISK_AUTH_STRATEGY_MISMATCH")
    auth_pair=_pair(a.get("pair"))
    if auth_pair is None: reasons.append("RISK_AUTH_PAIR_INVALID")
    if pair is not None:
        req_pair=_pair(pair)
        if req_pair is None: reasons.append("OPPORTUNITY_PAIR_INVALID")
        elif auth_pair!=req_pair: reasons.append("RISK_AUTH_PAIR_MISMATCH")
    direction=str(a.get("direction","")).upper()
    entry=a.get("entry_price"); stop=a.get("stop_price")
    if direction not in {"BUY","LONG","COMPRA","SELL","SHORT","VENDA"}: reasons.append("RISK_AUTH_DIRECTION_INVALID")
    if not _positive(entry): reasons.append("RISK_AUTH_ENTRY_PRICE_INVALID")
    if not _positive(stop): reasons.append("RISK_AUTH_STOP_PRICE_INVALID")
    if _positive(entry) and _positive(stop):
        if direction in {"BUY","LONG","COMPRA"} and not float(stop)<float(entry): reasons.append("RISK_AUTH_STOP_GEOMETRY_INVALID")
        if direction in {"SELL","SHORT","VENDA"} and not float(stop)>float(entry): reasons.append("RISK_AUTH_STOP_GEOMETRY_INVALID")
    max_risk=a.get("max_authorized_risk"); max_exp=a.get("max_authorized_exposure")
    if not _positive(max_risk): reasons.append("RISK_AUTH_MAX_RISK_INVALID")
    if not _positive(max_exp): reasons.append("RISK_AUTH_MAX_EXPOSURE_INVALID")
    if requested_risk is not None:
        if not _positive(requested_risk): reasons.append("REQUESTED_RISK_INVALID")
        elif _positive(max_risk) and float(requested_risk)>float(max_risk): reasons.append("RISK_AUTH_RISK_EXCEEDED")
    if requested_exposure is not None:
        if not _positive(requested_exposure): reasons.append("REQUESTED_EXPOSURE_INVALID")
        elif _positive(max_exp) and float(requested_exposure)>float(max_exp): reasons.append("RISK_AUTH_EXPOSURE_EXCEEDED")
    ok=not reasons
    request_id=paper_request_id_for_authorization(a)
    return {"accepted":ok,"paper_request_id":request_id if ok else None,
            "risk_auth_id":a.get("risk_auth_id"),"opportunity_id":a.get("opportunity_id"),"pair":auth_pair or a.get("pair"),
            "strategy_version":a.get("strategy_version"),"direction":a.get("direction"),"authorized_entry_price":a.get("entry_price"),
            "authorized_stop_price":a.get("stop_price"),"auth_expires_at":a.get("expires_at"),
            "max_risk":max_risk if _positive(max_risk) else 0,
            "max_exposure":max_exp if _positive(max_exp) else 0,"environment":"PAPER",
            "real_orders_enabled":False,"reasons":reasons}

def authorized_paper_audit(opportunity:Mapping[str,Any], auth:Mapping[str,Any], *, now:datetime|None=None)->dict[str,Any]:
    """Build Paper request and immutable audit decision in one deterministic step."""
    paper=paper_request_from_authorization(
        auth,now=now,opportunity_id=str(opportunity.get("opportunity_id","")),
        strategy_version=str(opportunity.get("strategy_version","")),pair=str(opportunity.get("pair","")),
        requested_risk=opportunity.get("requested_risk"),requested_exposure=opportunity.get("requested_exposure"))
    audit=audit_paper_decision(opportunity,auth,paper)
    return {"paper_request":paper,"audit_record":audit,"real_orders_enabled":False}
