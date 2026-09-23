from atlasquant_paper_reconciliation import reconcile_day,strategy_scorecards
def test_daily_reconciliation_keeps_r_and_sample_warning():
 r=reconcile_day([{"state":"REJECTED"},{"state":"PAPER_ACCEPTED"}],[{"status":"CLOSED","net_r":2},{"status":"CLOSED","net_r":-1}])
 assert r["net_r"]==1 and r["expectancy_r"]==.5 and r["sample_label"]=="INSUFFICIENT SAMPLE"
 assert r["real_orders_enabled"] is False
def test_strategy_results_are_not_mixed():
 x=strategy_scorecards([{"strategy_version":"AMD-1","status":"CLOSED","net_r":1},{"strategy_version":"FVG-1","status":"CLOSED","net_r":-1}])
 assert x["AMD-1"]["net_r"]==1 and x["FVG-1"]["net_r"]==-1
