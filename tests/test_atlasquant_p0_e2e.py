from datetime import datetime,timezone,timedelta
from atlasquant_gate_chain import evaluate_gate_chain,execution_gate_passed
from atlasquant_risk_authorization import RiskRequest,authorize_risk
from atlasquant_risk_guardian import RiskLimits,RiskState
from atlasquant_paper_authorization_bridge import authorized_paper_audit
from atlasquant_result_store import attach_result
from atlasquant_paper_runtime import paper_state_snapshot,recover_paper_state
from atlasquant_paper_reconciliation import reconcile_day

NOW=datetime(2026,9,23,12,0,tzinfo=timezone.utc)
L=RiskLimits(1000,30,10,5,2,20,2); S=RiskState()
G={"DATA":"PASS","DIRECTION":"PASS_SHORT","MACRO":"ALIGNED_SHORT","STRATEGY":"TRIGGERED","TRIGGER":"CONFIRMED","SESSION":"OPTIMAL","NEWS":"CLEAR","MARKET_CONDITION":"NORMAL","RISK":"APPROVED"}
O={"opportunity_id":"O-E2E","pair":"EUR/USD","direction":"SELL","strategy_version":"AMD-1","score_version":"AQ_SCORE_1","risk_version":"AQ_RISK_1","quality_score":91,"confidence":93,"gates":G,"timestamp":NOW.isoformat()}

def request(**kw):
 d=dict(opportunity_id="O-E2E",pair="EUR/USD",strategy_version="AMD-1",requested_trade_risk=5,requested_exposure=5,structural_stop_valid=True,rr_after_costs=2,spread_ok=True,slippage_ok=True,liquidity_ok=True,volatility_ok=True,news_clear=True,data_fresh=True,opportunity_state="TRIGGERED")
 d.update(kw); return RiskRequest(**d)

def test_happy_path_gate_risk_paper_result_restart_metrics():
 assert execution_gate_passed(evaluate_gate_chain(G))
 auth=authorize_risk(request(),L,S,now=NOW)
 pack=authorized_paper_audit(O,auth,now=NOW)
 assert auth["approved"] and pack["paper_request"]["accepted"]
 result=attach_result(pack["audit_record"],outcome="WIN",realized_r=2,spread_cost_r=.1,slippage_cost_r=.05,closed_at=NOW+timedelta(hours=1))
 assert abs(result["net_r"]-1.85)<1e-9 and result["environment"]=="PAPER"
 snap=paper_state_snapshot([{"pair":"EUR/USD","status":"OPEN","paper_request_id":"P-E2E","opportunity_id":"O-E2E"}],created_at=NOW.isoformat())
 rec=recover_paper_state(snap,current_market={"EUR/USD":{"price":1.18,"fresh":True,"valid":True}})
 assert rec["ok"] and rec["trades"][0]["recovery_state"]=="RECOVERED"
 daily=reconcile_day([{"state":"PAPER_ACCEPTED"}],[{"status":"CLOSED","net_r":result["net_r"]}])
 assert daily["net_r"]==1.85 and daily["environment"]=="PAPER"

def test_news_lock_never_reaches_authorized_paper():
 g=dict(G); g["NEWS"]="LOCKED"
 assert not execution_gate_passed(evaluate_gate_chain(g))
 auth=authorize_risk(request(news_clear=False),L,S,now=NOW)
 pack=authorized_paper_audit(O,auth,now=NOW)
 assert not auth["approved"] and not pack["paper_request"]["accepted"]

def test_stale_data_never_reaches_authorized_paper():
 auth=authorize_risk(request(data_fresh=False),L,S,now=NOW)
 assert not authorized_paper_audit(O,auth,now=NOW)["paper_request"]["accepted"]

def test_portfolio_lock_blocks_paper():
 auth=authorize_risk(request(portfolio_lock_ok=False),L,S,now=NOW)
 assert not auth["approved"] and "PORTFOLIO_RISK_LOCK" in auth["reasons"]
