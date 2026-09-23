"""P0 idempotent Paper orchestrator. Never broker/live."""
from __future__ import annotations
from typing import Any,Mapping,Sequence
from atlasquant_paper_authorization_bridge import authorized_paper_audit

ACTIVE={"WAIT_ENTRY","OPEN","MANAGING"}
def orchestrate_paper(opportunity:Mapping[str,Any],auth:Mapping[str,Any],ledger:Sequence[Mapping[str,Any]]|None,*,watchdog_state:str="NORMAL",now=None)->dict[str,Any]:
    rows=[dict(x) for x in (ledger or [])]; oid=str(opportunity.get("opportunity_id",""))
    existing=[x for x in rows if str(x.get("opportunity_id",""))==oid and str(x.get("environment","PAPER")).upper()=="PAPER"]
    if len(existing)>1:return {"state":"RECOVERY_REQUIRED","accepted":False,"reason":"DUPLICATE_OPPORTUNITY_LEDGER","real_orders_enabled":False}
    if existing:return {"state":"ALREADY_EXISTS","accepted":False,"existing":existing[0],"reason":"IDEMPOTENCY_GUARD","real_orders_enabled":False}
    if str(watchdog_state).upper()!="NORMAL":return {"state":"REJECTED","accepted":False,"reason":"WATCHDOG_NOT_NORMAL","real_orders_enabled":False}
    pack=authorized_paper_audit(opportunity,auth,now=now); req=pack["paper_request"]
    if not req["accepted"]:return {"state":"REJECTED","accepted":False,"reason":";".join(req["reasons"]) or "AUTH_REJECTED","audit_record":pack["audit_record"],"real_orders_enabled":False}
    row={"paper_request_id":req["paper_request_id"],"opportunity_id":oid,"pair":req["pair"],"strategy_version":req["strategy_version"],"risk_auth_id":req["risk_auth_id"],"status":"WAIT_ENTRY","environment":"PAPER","real_orders_enabled":False}
    return {"state":"ACCEPTED","accepted":True,"paper_trade":row,"audit_record":pack["audit_record"],"real_orders_enabled":False}
