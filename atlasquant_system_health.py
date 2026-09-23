"""AtlasQuant P0 unified system health/circuit breaker. Fail-closed."""
from __future__ import annotations
from datetime import datetime,timezone
from typing import Any,Mapping
import math

SEVERITY={"NORMAL":0,"CAUTION":1,"DEGRADED":1,"PROTECTED":2,"HALTED":3}
CRITICAL={"risk","result_store","paper_store"}

def _utc(value:datetime|None)->datetime:
    d=value or datetime.now(timezone.utc)
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)

def _stamp(value:Any)->datetime|None:
    try:
        d=value if isinstance(value,datetime) else datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    except Exception:return None

def _threshold(name:str,max_age_seconds:Any)->float|None:
    if max_age_seconds is None:return None
    raw=max_age_seconds.get(name) if isinstance(max_age_seconds,Mapping) else max_age_seconds
    try:
        x=float(raw)
        return x if math.isfinite(x) and x>0 else -1.0
    except Exception:return -1.0

def system_health(components:Mapping[str,Any]|None,*,now:datetime|None=None,max_age_seconds:Any=None)->dict[str,Any]:
    src=dict(components or {});detail={};reasons=[];level=0;current=_utc(now)
    required=("market_data","scanner","risk","result_store","paper_store")
    for name in required:
        row=dict(src.get(name,{}) or {});state=str(row.get("state","UNKNOWN")).upper()
        if state=="UNKNOWN":
            state="HALTED" if name in CRITICAL else "PROTECTED";reasons.append(f"{name.upper()}_UNKNOWN")
        if row.get("healthy") is not True:
            state="HALTED" if name in CRITICAL else "PROTECTED";reasons.append(f"{name.upper()}_UNHEALTHY")
        threshold=_threshold(name,max_age_seconds);age=None
        if threshold is not None:
            if threshold<0:
                state="HALTED";reasons.append("HEALTH_FRESHNESS_CONFIG_INVALID")
            else:
                stamp=_stamp(row.get("last_ok"))
                if stamp is None:
                    state="HALTED" if name in CRITICAL else "PROTECTED";reasons.append(f"{name.upper()}_HEARTBEAT_UNKNOWN")
                else:
                    age=(current-stamp).total_seconds()
                    if age<0:
                        state="HALTED" if name in CRITICAL else "PROTECTED";reasons.append(f"{name.upper()}_HEARTBEAT_FUTURE")
                    elif age>=threshold:
                        state="HALTED" if name in CRITICAL else "PROTECTED";reasons.append(f"{name.upper()}_HEARTBEAT_STALE")
        sev=SEVERITY.get(state,2);level=max(level,sev)
        detail[name]={"state":state,"healthy":row.get("healthy"),"reason":row.get("reason"),"last_ok":row.get("last_ok"),
                      "heartbeat_age_seconds":age,"max_age_seconds":None if threshold is None or threshold<0 else threshold}
        if sev>=2 and f"{name.upper()}_UNHEALTHY" not in reasons and not any(str(x).startswith(f"{name.upper()}_HEARTBEAT") for x in reasons):
            reasons.append(f"{name.upper()}_{state}")
    state=("NORMAL","CAUTION","PROTECTED","HALTED")[level]
    return {"state":state,"new_entries_allowed":state=="NORMAL","paper_new_entries_allowed":state=="NORMAL",
            "management_allowed":True,"management_mode":"SAFE_ONLY" if state!="NORMAL" else "NORMAL",
            "reasons":list(dict.fromkeys(reasons)),"components":detail,"checked_at":current.isoformat(),
            "real_orders_enabled":False,"production_promotion_allowed":False}
