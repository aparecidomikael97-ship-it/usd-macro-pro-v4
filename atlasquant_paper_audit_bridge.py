"""P0 audit bridge from Risk Authorization/Paper request into Result Store."""
from __future__ import annotations
from typing import Any,Mapping
from atlasquant_result_store import decision_record,rejected_record

def audit_paper_decision(opportunity:Mapping[str,Any],risk:Mapping[str,Any],paper:Mapping[str,Any]|None=None)->dict[str,Any]:
    o=dict(opportunity or {}); r=dict(risk or {}); p=dict(paper or {})
    accepted=bool(p.get("accepted",False))
    env="PAPER"
    gates=dict(o.get("gates",{}) or {})
    risk_snapshot={k:r.get(k) for k in ("risk_gate","approved","risk_auth_id","reasons","expires_at","max_authorized_risk","max_authorized_exposure")}
    builder=decision_record if accepted else rejected_record
    row=builder(opportunity_id=str(o.get("opportunity_id","")),environment=env,pair=str(o.get("pair","")),
        direction=str(o.get("direction","")),strategy_version=str(o.get("strategy_version","")),
        score_version=str(o.get("score_version","")),risk_version=str(o.get("risk_version","")),
        quality_score=float(o.get("quality_score",0)),confidence=float(o.get("confidence",0)),
        gates=gates,risk_decision=risk_snapshot,timestamp=o.get("timestamp"))
    row["paper_request_id"]=p.get("paper_request_id")
    row["paper_accepted"]=accepted
    row["decision"]="PAPER_ACCEPTED" if accepted else "REJECTED"
    row["real_orders_enabled"]=False
    return row
