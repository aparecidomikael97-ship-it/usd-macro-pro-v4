from atlasquant_risk_locks import risk_lock
def test_weekly_loss_protects_new_entries():
 r=risk_lock(daily_pnl=0,weekly_pnl=-51,current_drawdown=10,max_daily_loss=30,max_weekly_loss=50,max_drawdown=100)
 assert r["state"]=="PROTECTED" and not r["new_entries_allowed"]
def test_kill_switch_halts_but_management_remains_allowed():
 r=risk_lock(daily_pnl=0,weekly_pnl=0,current_drawdown=0,max_daily_loss=30,max_weekly_loss=50,max_drawdown=100,kill_switch=True)
 assert r["state"]=="HALTED" and r["management_of_existing_positions_allowed"]
