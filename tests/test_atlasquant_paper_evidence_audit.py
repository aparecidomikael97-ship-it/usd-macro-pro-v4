from datetime import datetime,timezone,timedelta
from atlasquant_paper_close import close_paper_trade
from atlasquant_paper_evidence_audit import audit_paper_results
from atlasquant_result_store import decision_record

NOW=datetime(2026,9,23,12,tzinfo=timezone.utc)

def closed():
 d=decision_record(opportunity_id="O1",environment="PAPER",pair="EUR/USD",direction="BUY",strategy_version="AMD-1",
 score_version="S1",risk_version="R1",quality_score=90,confidence=90,gates={"DATA":"PASS"},risk_decision={"risk_gate":"APPROVED"},timestamp=NOW)
 d["paper_request_id"]="P1";d["paper_accepted"]=True;d["real_orders_enabled"]=False
 trade={"paper_request_id":"P1","opportunity_id":"O1","pair":"EUR/USD","strategy_version":"AMD-1","risk_auth_id":"RA1",
 "status":"OPEN","environment":"PAPER","real_orders_enabled":False}
 return close_paper_trade(trade,d,realized_r=1.2,spread_cost_r=.1,slippage_cost_r=.1,closed_at=NOW+timedelta(hours=1))["result"]

def test_clean_result_evidence_is_normal():
 r=audit_paper_results([closed()])
 assert r["ok"] and r["healthy"] and r["state"]=="NORMAL" and r["new_entries_allowed"]

def test_duplicate_close_identity_protects():
 x=closed();r=audit_paper_results([x,dict(x)])
 assert not r["ok"] and r["state"]=="PROTECTED" and not r["new_entries_allowed"] and any("DUPLICATE_DECISION_RECORD_ID" in z for z in r["reasons"])

def test_net_arithmetic_or_outcome_tamper_is_detected():
 x=closed();x["net_r"]=9
 r=audit_paper_results([x]);assert not r["ok"] and any("NET_R_ARITHMETIC_MISMATCH" in z for z in r["reasons"])
 y=closed();y["outcome"]="LOSS"
 r2=audit_paper_results([y]);assert not r2["ok"] and any("OUTCOME_NET_R_MISMATCH" in z for z in r2["reasons"])

def test_live_or_negative_cost_evidence_is_rejected():
 x=closed();x["environment"]="LIVE"
 assert any("ENVIRONMENT_INVALID" in z for z in audit_paper_results([x])["reasons"])
 y=closed();y["spread_cost_r"]=-.1
 assert any("SPREAD_COST_INVALID" in z for z in audit_paper_results([y])["reasons"])
