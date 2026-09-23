"""P0 filtered Paper evidence report. Historical metrics only, never a profit promise."""
from __future__ import annotations
from datetime import datetime,timezone,date
from typing import Any,Mapping,Sequence
from atlasquant_paper_evidence_audit import audit_paper_results
from atlasquant_paper_reconciliation import reconcile_day

def _day(v:Any)->str|None:
    try:
        d=datetime.fromisoformat(str(v).replace("Z","+00:00"))
        d=d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
        return d.date().isoformat()
    except Exception:
        return None

def build_paper_report(results:Sequence[Mapping[str,Any]]|None,*,day:str|date|None=None,pair:str|None=None,
                       strategy_version:str|None=None,session:str|None=None,min_sample:int=30)->dict[str,Any]:
    raw=[dict(x) for x in (results or [])]
    target_day=str(day) if day is not None else None
    selected=[]; filter_reasons=[]
    for r in raw:
        if str(r.get("environment","")).upper()!="PAPER":
            continue
        if target_day is not None:
            rd=_day(r.get("closed_at"))
            if rd is None:
                filter_reasons.append("CLOSED_AT_INVALID_FOR_DAY_FILTER");continue
            if rd!=target_day: continue
        if pair is not None and str(r.get("pair","")).upper()!=str(pair).upper(): continue
        if strategy_version is not None and str(r.get("strategy_version",""))!=str(strategy_version): continue
        if session is not None and str(r.get("session","")).upper()!=str(session).upper(): continue
        selected.append(r)
    audit=audit_paper_results(selected)
    metrics=reconcile_day([],selected,min_sample=min_sample)
    reasons=list(dict.fromkeys([*filter_reasons,*audit.get("reasons",[]),*metrics.get("integrity_reasons",[])]))
    ok=not reasons and audit.get("ok") is True and metrics.get("integrity_ok") is True
    return {"state":"NORMAL" if ok else "PROTECTED","integrity_ok":ok,"reasons":reasons,
            "filters":{"day":target_day,"pair":pair,"strategy_version":strategy_version,"session":session},
            "selected_results":len(selected),"metrics":metrics,
            "performance_claims_allowed":False,"metrics_are_historical_not_probability":True,
            "real_orders_enabled":False}
