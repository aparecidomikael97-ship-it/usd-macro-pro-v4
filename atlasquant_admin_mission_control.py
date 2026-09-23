"""P0 Admin Mission Control projection from authoritative health/quality evidence."""
from __future__ import annotations
from typing import Any,Mapping
def admin_mission_control(system_health:Mapping[str,Any],quality:Mapping[str,Any],*,environment:str="DEV")->dict[str,Any]:
 h=dict(system_health or {});q=dict(quality or {});state=str(h.get("state","UNKNOWN")).upper();release=str(q.get("release_state","NOT_READY")).upper()
 return {"environment":str(environment).upper(),"system_state":state,"release_state":release,
 "new_entries_allowed":state=="NORMAL","management_mode":h.get("management_mode","SAFE_ONLY"),
 "rc_eligible":release=="RC_ELIGIBLE" and state=="NORMAL","production_promotion_allowed":False,"real_orders_enabled":False,
 "banner":"OPERACIONAL" if state=="NORMAL" else f"SISTEMA {state} — NOVAS ENTRADAS BLOQUEADAS",
 "health_reasons":list(h.get("reasons",[]) or []),"quality_blocked":list(q.get("blocked",[]) or []),"quality_pending":list(q.get("pending",[]) or [])}
