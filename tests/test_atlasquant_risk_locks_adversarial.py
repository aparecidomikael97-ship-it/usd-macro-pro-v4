import math
from atlasquant_risk_locks import risk_lock
BASE=dict(daily_pnl=0,weekly_pnl=0,current_drawdown=0,max_daily_loss=2,max_weekly_loss=5,max_drawdown=6)
def test_invalid_limit_halts():assert risk_lock(**{**BASE,"max_daily_loss":0})["state"]=="HALTED"
def test_nan_halts():assert risk_lock(**{**BASE,"daily_pnl":math.nan})["state"]=="HALTED"
def test_drawdown_breach_protects():assert risk_lock(**{**BASE,"current_drawdown":6})["state"]=="PROTECTED"
