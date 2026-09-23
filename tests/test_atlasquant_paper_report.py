from atlasquant_paper_report import build_paper_report

def result(rid,did,pid,net,day="2026-09-23",pair="EUR/USD",strategy="AMD-1",session="LONDON"):
 return {"record_id":rid,"record_type":"RESULT","decision_record_id":did,"paper_request_id":pid,
 "opportunity_id":"O-"+pid,"environment":"PAPER","pair":pair,"direction":"BUY","strategy_version":strategy,
 "score_version":"S1","risk_version":"R1","quality_score":90,"confidence":90,"gates":{},"risk_decision":{},
 "immutable_evidence":True,"real_orders_enabled":False,"status":"CLOSED","outcome":"WIN" if net>0 else "LOSS" if net<0 else "BREAKEVEN",
 "realized_r":net,"spread_cost_r":0,"slippage_cost_r":0,"net_r":net,"closed_at":day+"T13:00:00+00:00","session":session}

def test_report_filters_day_pair_strategy_session():
 rows=[result("R1","D1","P1",1),result("R2","D2","P2",-1,pair="GBP/USD"),result("R3","D3","P3",2,day="2026-09-24")]
 r=build_paper_report(rows,day="2026-09-23",pair="EURUSD",strategy_version="AMD-1",session="LONDON",min_sample=1)
 assert r["state"]=="NORMAL" and r["selected_results"]==1 and r["metrics"]["net_r"]==1
 assert r["performance_claims_allowed"] is False and r["metrics_are_historical_not_probability"] is True

def test_invalid_pair_filter_protects():
 r=build_paper_report([result("R1","D1","P1",1)],pair="USD/BRL")
 assert r["state"]=="PROTECTED" and "PAIR_FILTER_INVALID" in r["reasons"] and r["selected_results"]==0

def test_invalid_close_time_under_day_filter_protects():
 x=result("R1","D1","P1",1);x["closed_at"]="bad"
 r=build_paper_report([x],day="2026-09-23")
 assert r["state"]=="PROTECTED" and "CLOSED_AT_INVALID_FOR_DAY_FILTER" in r["reasons"]

def test_tampered_result_protects_report():
 x=result("R1","D1","P1",1);x["net_r"]=9
 r=build_paper_report([x],min_sample=1)
 assert r["state"]=="PROTECTED" and not r["integrity_ok"]
