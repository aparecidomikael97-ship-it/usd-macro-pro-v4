"""P0 health recovery hysteresis. Escalation is immediate; reopening is deliberate."""
from __future__ import annotations
from typing import Any,Mapping

STATES=("NORMAL","CAUTION","PROTECTED","HALTED")
SEVERITY={s:i for i,s in enumerate(STATES)}

def stabilize_health(previous_state:str,current_health:Mapping[str,Any],*,normal_streak:int=0,recovery_checks:int=2)->dict[str,Any]:
    prev=str(previous_state or "HALTED").upper();cur=str((current_health or {}).get("state","HALTED")).upper()
    reasons=[]
    if prev not in SEVERITY: prev="HALTED";reasons.append("PREVIOUS_STATE_INVALID")
    if cur not in SEVERITY: cur="HALTED";reasons.append("CURRENT_STATE_INVALID")
    try:
        checks=int(recovery_checks);streak=max(0,int(normal_streak))
        if isinstance(recovery_checks,bool) or checks<1 or float(recovery_checks)!=checks:raise ValueError
    except Exception:
        return {"state":"HALTED","normal_streak":0,"recovery_pending":False,"new_entries_allowed":False,
                "management_allowed":True,"management_mode":"SAFE_ONLY","reasons":["RECOVERY_CONFIG_INVALID"],
                "real_orders_enabled":False}
    if cur!="NORMAL":
        state=cur;streak=0;pending=False
    elif prev=="NORMAL":
        state="NORMAL";streak=checks;pending=False
    else:
        streak+=1
        if streak>=checks:
            state="NORMAL";pending=False
        else:
            state=prev;pending=True;reasons.append("RECOVERY_CONFIRMATION_PENDING")
    return {"state":state,"observed_state":cur,"previous_state":prev,"normal_streak":streak,
            "recovery_checks":checks,"recovery_pending":pending,"new_entries_allowed":state=="NORMAL",
            "management_allowed":True,"management_mode":"NORMAL" if state=="NORMAL" else "SAFE_ONLY",
            "reasons":reasons,"real_orders_enabled":False}
