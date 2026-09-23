"""P0 reconciliation of Paper ledger/snapshot identity. Ambiguity fails closed."""
from __future__ import annotations
from typing import Any,Mapping,Sequence
ACTIVE={"WAIT_ENTRY","OPEN","MANAGING"}
def reconcile_active_paper(snapshot_rows:Sequence[Mapping[str,Any]]|None,ledger:Sequence[Mapping[str,Any]]|None)->dict[str,Any]:
    snap=[dict(x) for x in (snapshot_rows or [])]; led=[dict(x) for x in (ledger or [])]; reasons=[]
    def ids(rows,key):
        out={}
        for r in rows:
            v=str(r.get(key,"")).strip()
            if not v: reasons.append(f"{key.upper()}_MISSING")
            else: out[v]=out.get(v,0)+1
        return out
    for key in ("paper_request_id","opportunity_id"):
        for v,n in ids(snap,key).items():
            if n>1: reasons.append(f"DUPLICATE_SNAPSHOT_{key.upper()}:{v}")
        for v,n in ids(led,key).items():
            if n>1: reasons.append(f"DUPLICATE_LEDGER_{key.upper()}:{v}")
    active=[r for r in snap if str(r.get("status","")).upper() in ACTIVE]
    ledger_req={str(r.get("paper_request_id","")) for r in led}
    orphans=[r for r in active if str(r.get("paper_request_id","")) not in ledger_req]
    if orphans: reasons.append("ORPHAN_ACTIVE_PAPER")
    return {"ok":not reasons,"system_state":"NORMAL" if not reasons else "PROTECTED","new_entries_allowed":not reasons,
            "management_allowed":True,"reasons":reasons,"orphans":orphans,"active_count":len(active),"real_orders_enabled":False}
