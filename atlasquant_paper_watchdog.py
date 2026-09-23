"""Paper watchdog adapter over unified System Health."""
from __future__ import annotations
from datetime import datetime
from typing import Any,Mapping
from atlasquant_system_health import system_health
def paper_watchdog(components:Mapping[str,Any]|None,*,now:datetime|None=None)->dict[str,Any]:
 normalized={}
 for name in ("market_data","scanner","risk","result_store","paper_store"):
  row=dict((components or {}).get(name,{}) or {}); healthy=row.get("healthy") is True
  if "state" not in row: row["state"]="NORMAL" if healthy else ("HALTED" if name in {"risk","result_store","paper_store"} else "PROTECTED")
  normalized[name]=row
 h=system_health(normalized,now=now)
 return {"state":h["state"],"new_paper_entries_allowed":h["paper_new_entries_allowed"],"management_allowed":h["management_allowed"],
         "management_mode":h["management_mode"],"unhealthy_components":[k for k,v in normalized.items() if v.get("healthy") is not True],
         "components":h["components"],"checked_at":h["checked_at"],"real_orders_enabled":False}
