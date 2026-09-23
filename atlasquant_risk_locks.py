"""P0 daily/weekly risk lock state, pure and fail-closed."""
from __future__ import annotations
from typing import Any

def risk_lock(*,daily_pnl:float,weekly_pnl:float,current_drawdown:float,
              max_daily_loss:float,max_weekly_loss:float,max_drawdown:float,
              kill_switch:bool=False,risk_engine_healthy:bool=True)->dict[str,Any]:
    reasons=[]
    if kill_switch: reasons.append("KILL_SWITCH")
    if risk_engine_healthy is not True: reasons.append("RISK_ENGINE_UNHEALTHY")
    if -float(daily_pnl)>=float(max_daily_loss): reasons.append("DAILY_LOSS_LIMIT")
    if -float(weekly_pnl)>=float(max_weekly_loss): reasons.append("WEEKLY_LOSS_LIMIT")
    if float(current_drawdown)>=float(max_drawdown): reasons.append("MAX_DRAWDOWN")
    if "KILL_SWITCH" in reasons or "RISK_ENGINE_UNHEALTHY" in reasons: state="HALTED"
    elif reasons: state="PROTECTED"
    else: state="NORMAL"
    return {"state":state,"new_entries_allowed":not reasons,"reasons":reasons,
            "management_of_existing_positions_allowed":True}
