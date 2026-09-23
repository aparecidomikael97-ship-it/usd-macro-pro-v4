"""Paper evidence reconciliation/metrics. PAPER only; never mixes environments."""
from __future__ import annotations
from typing import Any,Mapping,Sequence
import math

def _finite(v):
 try:
  x=float(v); return x if math.isfinite(x) else None
 except Exception:return None

def _closed(x): return str(x.get("status","")).upper() in {"CLOSED","WIN","LOSS","BREAKEVEN"}

def _max_dd(rs):
 equity=peak=dd=0.
 for r in rs:
  equity+=r; peak=max(peak,equity); dd=max(dd,peak-equity)
 return round(dd,4)

def _dedupe_closed(rows,reasons):
 out=[];seen_record=set();seen_decision=set()
 for x in rows:
  rid=str(x.get("record_id","")).strip();did=str(x.get("decision_record_id","")).strip()
  if rid and rid in seen_record:
   reasons.append(f"DUPLICATE_RESULT_RECORD:{rid}");continue
  if did and did in seen_decision:
   reasons.append(f"MULTIPLE_RESULTS_FOR_DECISION:{did}");continue
  if rid:seen_record.add(rid)
  if did:seen_decision.add(did)
  out.append(x)
 return out

def reconcile_day(opportunities:Sequence[Mapping[str,Any]]|None,trades:Sequence[Mapping[str,Any]]|None,*,min_sample:int=30)->dict[str,Any]:
 opp=[dict(x) for x in (opportunities or [])]; raw=[dict(x) for x in (trades or [])]; reasons=[]
 foreign=[x for x in raw if str(x.get("environment","PAPER")).upper()!="PAPER"]
 if foreign: reasons.append("ENVIRONMENT_MIX_DETECTED")
 tr=[x for x in raw if str(x.get("environment","PAPER")).upper()=="PAPER"]
 states={}
 for x in opp:
  s=str(x.get("state",x.get("decision","UNKNOWN"))).upper();states[s]=states.get(s,0)+1
 closed=_dedupe_closed([x for x in tr if _closed(x)],reasons)
 rs=[];gross=[];costs=[];mae=[];mfe=[];valid_closed=0
 for i,x in enumerate(closed):
  v=_finite(x.get("net_r",x.get("realized_r")));realized=_finite(x.get("realized_r",v))
  c1=_finite(x.get("spread_cost_r",0));c2=_finite(x.get("slippage_cost_r",0))
  if v is None or realized is None:
   reasons.append(f"CLOSED_RESULT_R_INVALID:{i}");continue
  if c1 is None or c2 is None or c1<0 or c2<0:
   reasons.append(f"CLOSED_RESULT_COST_INVALID:{i}");continue
  if "net_r" in x and abs(v-(realized-c1-c2))>1e-9:
   reasons.append(f"CLOSED_RESULT_ARITHMETIC_MISMATCH:{i}");continue
  rs.append(v);gross.append(realized);costs.append(c1+c2);valid_closed+=1
  a=_finite(x.get("mae_r"));f=_finite(x.get("mfe_r"))
  if x.get("mae_r") is not None and a is None: reasons.append(f"MAE_INVALID:{i}")
  elif a is not None:mae.append(a)
  if x.get("mfe_r") is not None and f is None: reasons.append(f"MFE_INVALID:{i}")
  elif f is not None:mfe.append(f)
 wins=sum(v>0 for v in rs);losses=sum(v<0 for v in rs);gw=sum(v for v in rs if v>0);gl=abs(sum(v for v in rs if v<0))
 try:
  if isinstance(min_sample,bool):raise ValueError
  threshold=int(min_sample)
  if threshold<1 or float(min_sample)!=threshold:raise ValueError
 except Exception:
  threshold=30;reasons.append("MIN_SAMPLE_INVALID")
 reasons=list(dict.fromkeys(reasons))
 return {"environment":"PAPER","integrity_ok":not reasons,"integrity_reasons":reasons,"opportunities":len(opp),"states":states,
 "paper_trades":len(tr),"closed":valid_closed,"closed_seen":len(closed),"wins":wins,"losses":losses,"breakeven":sum(v==0 for v in rs),
 "gross_realized_r":round(sum(gross),4),"net_r":round(sum(rs),4),"costs_r":round(sum(costs),4),
 "expectancy_r":None if not rs else round(sum(rs)/len(rs),4),
 "historical_win_rate_pct":None if not rs else round(100*wins/len(rs),2),
 "profit_factor":None if gl==0 else round(gw/gl,4),"max_drawdown_r":_max_dd(rs),
 "avg_mae_r":None if not mae else round(sum(mae)/len(mae),4),"avg_mfe_r":None if not mfe else round(sum(mfe)/len(mfe),4),
 "sample_sufficient":len(rs)>=threshold,"minimum_sample":threshold,"sample_label":"OK" if len(rs)>=threshold else "INSUFFICIENT SAMPLE",
 "metrics_are_historical_not_probability":True,"real_orders_enabled":False}

def scorecards(trades:Sequence[Mapping[str,Any]]|None,*,keys=("strategy_version","pair","session"),min_sample:int=30)->dict[str,Any]:
 out={}
 for key in keys:
  groups={}
  for x in trades or []:
   r=dict(x); groups.setdefault(str(r.get(key,"UNKNOWN")),[]).append(r)
  out[key]={k:reconcile_day([],v,min_sample=min_sample) for k,v in groups.items()}
 return out

def strategy_scorecards(trades): return scorecards(trades,keys=("strategy_version",))["strategy_version"]
