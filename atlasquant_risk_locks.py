"""P0 account risk locks. Values are risk units; invalid evidence fails closed."""
from __future__ import annotations
from typing import Any
import math
def risk_lock(*,daily_pnl:float,weekly_pnl:float,current_drawdown:float,max_daily_loss:float,max_weekly_loss:float,max_drawdown:float,kill_switch:bool=False,risk_engine_healthy:bool=True)->dict[str,Any]:
 reasons=[]
 vals={"daily_pnl":daily_pnl,"weekly_pnl":weekly_pnl,"current_drawdown":current_drawdown,"max_daily_loss":max_daily_loss,"max_weekly_loss":max_weekly_loss,"max_drawdown":max_drawdown}
 try: nums={k:float(v) for k,v in vals.items()}; valid=all(math.isfinite(v) for v in nums.values()) and all(nums[k]>0 for k in ("max_daily_loss","max_weekly_loss","max_drawdown")) and nums["current_drawdown"]>=0
 except Exception: valid=False;nums={}
 if not valid: reasons.append("RISK_LOCK_INPUT_INVALID")
 if kill_switch: reasons.append("KILL_SWITCH")
 if risk_engine_healthy is not True: reasons.append("RISK_ENGINE_UNHEALTHY")
 if valid:
  if -nums["daily_pnl"]>=nums["max_daily_loss"]:reasons.append("DAILY_LOSS_LIMIT")
  if -nums["weekly_pnl"]>=nums["max_weekly_loss"]:reasons.append("WEEKLY_LOSS_LIMIT")
  if nums["current_drawdown"]>=nums["max_drawdown"]:reasons.append("MAX_DRAWDOWN")
 if any(x in reasons for x in ("KILL_SWITCH","RISK_ENGINE_UNHEALTHY","RISK_LOCK_INPUT_INVALID")):state="HALTED"
 elif reasons:state="PROTECTED"
 else:state="NORMAL"
 return {"state":state,"new_entries_allowed":state=="NORMAL","reasons":reasons,"units":"RISK_UNITS","management_of_existing_positions_allowed":True}
