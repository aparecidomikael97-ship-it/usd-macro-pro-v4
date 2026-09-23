"""P0 Paper watchdog: health only, never invents trades or market data."""
from __future__ import annotations
from datetime import datetime,timezone
from typing import Any,Mapping

def paper_watchdog(components:Mapping[str,Any]|None, *, now:datetime|None=None)->dict[str,Any]:
    current=now or datetime.now(timezone.utc); bad=[]; detail={}
    for name in ("market_data","scanner","risk","result_store","paper_store"):
        row=dict((components or {}).get(name,{}) or {})
        healthy=row.get("healthy") is True
        detail[name]={"healthy":healthy,"last_ok":row.get("last_ok"),"reason":row.get("reason")}
        if not healthy: bad.append(name)
    if not bad: state="NORMAL"
    elif any(x in bad for x in ("risk","result_store","paper_store")): state="HALTED"
    else: state="PROTECTED"
    return {"state":state,"new_paper_entries_allowed":state=="NORMAL","management_allowed":True,
            "unhealthy_components":bad,"components":detail,"checked_at":current.isoformat(),
            "real_orders_enabled":False}
