from atlasquant_paper_reconciliation import reconcile_day,scorecards
def trade(r,pair="EUR/USD",strategy="AMD1",session="LONDON",**kw):
 d={"environment":"PAPER","status":"CLOSED","net_r":r,"pair":pair,"strategy_version":strategy,"session":session,"spread_cost_r":.05,"slippage_cost_r":.02,"mae_r":-.4,"mfe_r":1.2};d.update(kw);return d
def test_drawdown_costs_mae_mfe():
 r=reconcile_day([], [trade(1),trade(-2),trade(1)])
 assert r["net_r"]==0 and r["max_drawdown_r"]==2 and r["costs_r"]==.21 and r["avg_mae_r"]==-.4 and r["avg_mfe_r"]==1.2
def test_foreign_environment_never_silently_mixes():
 x=trade(1); y=trade(99);y["environment"]="BACKTEST"
 r=reconcile_day([], [x,y]);assert r["net_r"]==1 and not r["integrity_ok"] and "ENVIRONMENT_MIX_DETECTED" in r["integrity_reasons"]
def test_only_explicitly_closed_rows_count():
 x=trade(5);x["status"]="OPEN";assert reconcile_day([], [x])["closed"]==0
def test_sample_threshold_configurable_not_claimed_as_truth():
 r=reconcile_day([], [trade(1),trade(-1)],min_sample=2);assert r["sample_sufficient"] and r["minimum_sample"]==2
def test_scorecards_separate_strategy_pair_session():
 rows=[trade(1),trade(-1,pair="GBP/USD",strategy="FVG1",session="NEW_YORK")]
 s=scorecards(rows,min_sample=1)
 assert set(s["strategy_version"])=={"AMD1","FVG1"} and set(s["pair"])=={"EUR/USD","GBP/USD"} and set(s["session"])=={"LONDON","NEW_YORK"}
