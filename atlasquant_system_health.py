"""AtlasQuant P0 unified system health/circuit breaker. Fail-closed."""
from __future__ import annotations
from datetime import datetime,timezone
from typing import Any,Mapping
SEVERITY={"NORMAL":0,"CAUTION":1,"DEGRADED":1,"PROTECTED":2,"HALTED":3}
CRITICAL={"risk","result_store","paper_store"}
def system_health(components:Mapping[str,Any]|None,*,now:datetime|None=None)->dict[str,Any]:
 src=dict(components or {}); detail={}; reasons=[]; level=0
 required=("market_data","scanner","risk","result_store","paper_store")
 for name in required:
  row=dict(src.get(name,{}) or {}); state=str(row.get("state","UNKNOWN")).upper()
  if state=="UNKNOWN": state="HALTED" if name in CRITICAL else "PROTECTED"; reasons.append(f"{name.upper()}_UNKNOWN")
  if row.get("healthy") is not True: state="HALTED" if name in CRITICAL else "PROTECTED"; reasons.append(f"{name.upper()}_UNHEALTHY")
  sev=SEVERITY.get(state,2); level=max(level,sev); detail[name]={"state":state,"healthy":row.get("healthy"),"reason":row.get("reason"),"last_ok":row.get("last_ok")}
  if sev>=2 and f"{name.upper()}_UNHEALTHY" not in reasons: reasons.append(f"{name.upper()}_{state}")
 state=("NORMAL","CAUTION","PROTECTED","HALTED")[level]
 return {"state":state,"new_entries_allowed":state=="NORMAL","paper_new_entries_allowed":state=="NORMAL",
         "management_allowed":True,"management_mode":"SAFE_ONLY" if state!="NORMAL" else "NORMAL",
         "reasons":reasons,"components":detail,"checked_at":((now or datetime.now(timezone.utc)).replace(tzinfo=timezone.utc) if (now or datetime.now(timezone.utc)).tzinfo is None else (now or datetime.now(timezone.utc)).astimezone(timezone.utc)).isoformat(),
         "real_orders_enabled":False,"production_promotion_allowed":False}
