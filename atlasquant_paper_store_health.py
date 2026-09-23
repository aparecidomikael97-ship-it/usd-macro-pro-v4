"""P0 Paper store health projection from ledger and immutable result evidence."""
from __future__ import annotations
from typing import Any,Mapping,Sequence
from atlasquant_paper_ledger_reconciliation import reconcile_active_paper
from atlasquant_paper_evidence_audit import audit_paper_results

def paper_store_health(snapshot_rows:Sequence[Mapping[str,Any]]|None,ledger:Sequence[Mapping[str,Any]]|None,
                       results:Sequence[Mapping[str,Any]]|None,*,store_available:bool=True)->dict[str,Any]:
    if store_available is not True:
        return {"state":"HALTED","healthy":False,"available":False,"integrity_ok":False,
                "reason":"PAPER_STORE_UNAVAILABLE","new_entries_allowed":False,"management_allowed":True,
                "management_mode":"SAFE_ONLY","real_orders_enabled":False}
    led=reconcile_active_paper(snapshot_rows,ledger); ev=audit_paper_results(results)
    integrity=bool(led["ok"] and ev["ok"])
    reasons=[*list(led.get("reasons",[]) or []),*list(ev.get("reasons",[]) or [])]
    return {"state":"NORMAL" if integrity else "PROTECTED","healthy":True,"available":True,"integrity_ok":integrity,
            "reason":"PASS" if integrity else "PAPER_STORE_INTEGRITY_PROTECTED",
            "reasons":list(dict.fromkeys(reasons)),"new_entries_allowed":integrity,
            "management_allowed":True,"management_mode":"NORMAL" if integrity else "SAFE_ONLY",
            "ledger":led,"result_evidence":ev,"real_orders_enabled":False}
