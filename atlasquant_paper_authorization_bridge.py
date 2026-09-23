"""P0 bridge: Risk Authorization -> Paper only. Never broker/live."""
from __future__ import annotations
from datetime import datetime,timezone
from typing import Any,Mapping
from atlasquant_paper_audit_bridge import audit_paper_decision
import hashlib

def paper_request_from_authorization(auth:Mapping[str,Any], *, now:datetime|None=None)->dict[str,Any]:
    a=dict(auth or {}); current=now or datetime.now(timezone.utc); reasons=[]
    if a.get("approved") is not True or str(a.get("risk_gate","")).upper()!="APPROVED": reasons.append("RISK_NOT_APPROVED")
    if not str(a.get("risk_auth_id") or "").strip(): reasons.append("RISK_AUTH_ID_MISSING")
    try:
        expiry=datetime.fromisoformat(str(a.get("expires_at")).replace("Z","+00:00"))
        expiry=expiry.replace(tzinfo=timezone.utc) if expiry.tzinfo is None else expiry.astimezone(timezone.utc)
        if current>=expiry: reasons.append("RISK_AUTH_EXPIRED")
    except Exception: reasons.append("RISK_AUTH_EXPIRY_INVALID")
    if a.get("real_orders_enabled") is not False: reasons.append("LIVE_FLAG_NOT_EXPLICITLY_DISABLED")
    ok=not reasons
    seed=f"{a.get('risk_auth_id')}|{a.get('opportunity_id')}|{a.get('strategy_version')}"
    return {"accepted":ok,"paper_request_id":"PAPER-"+hashlib.sha256(seed.encode()).hexdigest()[:20] if ok else None,
            "risk_auth_id":a.get("risk_auth_id"),"opportunity_id":a.get("opportunity_id"),"pair":a.get("pair"),
            "strategy_version":a.get("strategy_version"),"max_risk":a.get("max_authorized_risk",0),
            "max_exposure":a.get("max_authorized_exposure",0),"environment":"PAPER",
            "real_orders_enabled":False,"reasons":reasons}


def authorized_paper_audit(opportunity:Mapping[str,Any], auth:Mapping[str,Any], *, now:datetime|None=None)->dict[str,Any]:
    """Build Paper request and its immutable audit decision in one deterministic step."""
    paper=paper_request_from_authorization(auth,now=now)
    audit=audit_paper_decision(opportunity,auth,paper)
    return {"paper_request":paper,"audit_record":audit,"real_orders_enabled":False}
