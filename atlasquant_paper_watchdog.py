"""Paper watchdog adapter over unified System Health."""
from __future__ import annotations
from datetime import datetime
from typing import Any,Mapping
from atlasquant_system_health import system_health
from atlasquant_health_hysteresis import stabilize_health
def paper_watchdog(components:Mapping[str,Any]|None,*,now:datetime|None=None,max_age_seconds:Any=None,previous_state:str|None=None,normal_streak:int=0,recovery_checks:int=2)->dict[str,Any]:
 normalized={}
 for name in ("market_data","scanner","risk","result_store","paper_store"):
  row=dict((components or {}).get(name,{}) or {}); healthy=row.get("healthy") is True
  if "state" not in row: row["state"]="NORMAL" if healthy else ("HALTED" if name in {"risk","result_store","paper_store"} else "PROTECTED")
  normalized[name]=row
 h=system_health(normalized,now=now,max_age_seconds=max_age_seconds)
 stable=stabilize_health(previous_state,h,normal_streak=normal_streak,recovery_checks=recovery_checks) if previous_state is not None else None
 state=stable["state"] if stable else h["state"]
 return {"state":state,"observed_state":h["state"],"new_paper_entries_allowed":state=="NORMAL","management_allowed":True,
         "management_mode":"NORMAL" if state=="NORMAL" else "SAFE_ONLY","recovery":stable,
         "unhealthy_components":[k for k,v in normalized.items() if v.get("healthy") is not True],
         "components":h["components"],"checked_at":h["checked_at"],"real_orders_enabled":False}
