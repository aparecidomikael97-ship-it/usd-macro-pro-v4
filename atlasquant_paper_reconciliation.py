"""Daily Paper reconciliation and evidence metrics."""
from __future__ import annotations
from typing import Any,Mapping,Sequence
import math

def reconcile_day(opportunities:Sequence[Mapping[str,Any]]|None,trades:Sequence[Mapping[str,Any]]|None)->dict[str,Any]:
    opp=[dict(x) for x in (opportunities or [])]; tr=[dict(x) for x in (trades or [])]
    states={}
    for x in opp:
        s=str(x.get("state",x.get("decision","UNKNOWN"))).upper(); states[s]=states.get(s,0)+1
    closed=[x for x in tr if str(x.get("status","")).upper() in {"CLOSED","WIN","LOSS","BREAKEVEN"} or x.get("net_r") is not None]
    rs=[]
    for x in closed:
        try:
            v=float(x.get("net_r",x.get("realized_r")))
            if math.isfinite(v): rs.append(v)
        except Exception: pass
    wins=sum(v>0 for v in rs); losses=sum(v<0 for v in rs)
    gross_win=sum(v for v in rs if v>0); gross_loss=abs(sum(v for v in rs if v<0))
    return {"environment":"PAPER","opportunities":len(opp),"states":states,"paper_trades":len(tr),"closed":len(rs),
            "wins":wins,"losses":losses,"breakeven":sum(v==0 for v in rs),"net_r":round(sum(rs),4),
            "expectancy_r":None if not rs else round(sum(rs)/len(rs),4),
            "profit_factor":None if gross_loss==0 else round(gross_win/gross_loss,4),
            "sample_sufficient":len(rs)>=30,"sample_label":"OK" if len(rs)>=30 else "INSUFFICIENT SAMPLE",
            "real_orders_enabled":False}

def strategy_scorecards(trades:Sequence[Mapping[str,Any]]|None)->dict[str,Any]:
    groups={}
    for x in trades or []:
        r=dict(x); key=str(r.get("strategy_version","UNKNOWN"))
        groups.setdefault(key,[]).append(r)
    return {k:reconcile_day([],v) for k,v in groups.items()}
