from datetime import datetime,timezone,timedelta
from atlasquant_gate_chain import evaluate_gate_chain,execution_gate_passed
from atlasquant_risk_authorization import RiskRequest,authorize_risk
from atlasquant_risk_guardian import RiskLimits,RiskState
from atlasquant_paper_orchestrator import orchestrate_paper
from atlasquant_paper_entry import activate_paper_entry
from atlasquant_paper_close import close_and_append_paper_result
from atlasquant_evidence_ledger import append_evidence,validate_evidence_ledger
from atlasquant_paper_evidence_audit import audit_paper_results
from atlasquant_paper_report import build_paper_report
from atlasquant_paper_store_health import paper_store_health
from atlasquant_system_health import system_health
from atlasquant_quality_gate import quality_gate,CRITICAL

NOW=datetime(2026,9,23,12,tzinfo=timezone.utc)
G={"DATA":"PASS","DIRECTION":"PASS_SHORT","MACRO":"ALIGNED_SHORT","STRATEGY":"TRIGGERED","TRIGGER":"CONFIRMED",
"SESSION":"OPTIMAL","NEWS":"CLEAR","MARKET_CONDITION":"NORMAL","RISK":"APPROVED"}
O={"opportunity_id":"O-FULL","pair":"EUR/USD","direction":"SELL","strategy_version":"AMD-1","score_version":"S1","risk_version":"R1",
"quality_score":92,"confidence":94,"gates":G,"timestamp":NOW.isoformat()}

def test_full_p0_paper_lifecycle_is_auditable_and_never_live():
 assert execution_gate_passed(evaluate_gate_chain(G))
 limits=RiskLimits(1000,30,10,5,2,20,2)
 req=RiskRequest(opportunity_id="O-FULL",pair="EUR/USD",strategy_version="AMD-1",requested_trade_risk=5,requested_exposure=5,
 structural_stop_valid=True,rr_after_costs=2,spread_ok=True,slippage_ok=True,liquidity_ok=True,volatility_ok=True,
 news_clear=True,data_fresh=True,opportunity_state="TRIGGERED",direction="SELL",entry_price=1.18,stop_price=1.19)
 auth=authorize_risk(req,limits,RiskState(),now=NOW)
 assert auth["approved"] and auth["execution_grade"] and auth["real_orders_enabled"] is False

 orchestrated=orchestrate_paper(O,auth,[],watchdog_state="NORMAL",now=NOW)
 assert orchestrated["accepted"] and orchestrated["paper_trade"]["status"]=="WAIT_ENTRY"
 opened=activate_paper_entry(orchestrated["paper_trade"],auth,{"price":1.18,"fresh":True,"valid":True},now=NOW)
 assert opened["opened"] and opened["trade"]["status"]=="OPEN"

 decision=orchestrated["audit_record"]
 led=append_evidence([],decision)
 assert led["appended"]
 final=close_and_append_paper_result(opened["trade"],decision,led["ledger"],realized_r=2,spread_cost_r=.1,slippage_cost_r=.05,
 closed_at=NOW+timedelta(hours=1))
 assert final["closed"] and final["appended"] and abs(final["result"]["net_r"]-1.85)<1e-9
 assert validate_evidence_ledger(final["ledger"])["ok"]
 assert audit_paper_results([final["result"]])["ok"]

 report=build_paper_report([final["result"]],day="2026-09-23",pair="EURUSD",strategy_version="AMD-1",min_sample=1)
 assert report["integrity_ok"] and report["metrics"]["net_r"]==1.85 and report["performance_claims_allowed"] is False

 closed_trade={**opened["trade"],"status":"CLOSED"}
 store=paper_store_health([], [closed_trade], [final["result"]])
 assert store["state"]=="NORMAL" and store["integrity_ok"]
 good={"state":"NORMAL","healthy":True}
 health=system_health({"market_data":dict(good),"scanner":dict(good),"risk":dict(good),"result_store":dict(good),"paper_store":store})
 assert health["state"]=="NORMAL" and health["new_entries_allowed"]

 checks={k:{"state":"PASS","evidence":"ci://full-p0"} for k in CRITICAL}
 q=quality_gate(checks,system_health=health)
 assert q["release_state"]=="RC_ELIGIBLE" and q["production_promotion_allowed"] is False and q["real_orders_enabled"] is False
