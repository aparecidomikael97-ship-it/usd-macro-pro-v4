from datetime import datetime,timezone,timedelta
from atlasquant_paper_close import close_paper_trade
from atlasquant_result_store import decision_record

NOW=datetime(2026,9,23,12,tzinfo=timezone.utc)

def decision():
 d=decision_record(opportunity_id="O1",environment="PAPER",pair="EUR/USD",direction="SELL",strategy_version="AMD-1",
 score_version="S1",risk_version="R1",quality_score=90,confidence=91,gates={"DATA":"PASS"},risk_decision={"risk_gate":"APPROVED"},timestamp=NOW)
 d["paper_request_id"]="P1";d["paper_accepted"]=True;d["real_orders_enabled"]=False;return d

def trade(status="OPEN",**kw):
 d={"paper_request_id":"P1","opportunity_id":"O1","pair":"EUR/USD","strategy_version":"AMD-1","risk_auth_id":"RA1",
 "status":status,"environment":"PAPER","real_orders_enabled":False};d.update(kw);return d

def test_close_builds_linked_result_and_cost_adjusted_net_r():
 r=close_paper_trade(trade(),decision(),realized_r=2,spread_cost_r=.1,slippage_cost_r=.05,closed_at=NOW+timedelta(hours=1))
 assert r["closed"] and r["state"]=="CLOSED"
 x=r["result"];assert x["decision_record_id"]==decision()["record_id"] and x["paper_request_id"]=="P1" and abs(x["net_r"]-1.85)<1e-9
 assert x["outcome"]=="WIN" and x["real_orders_enabled"] is False

def test_negative_cost_or_outcome_mismatch_fails_closed():
 r=close_paper_trade(trade(),decision(),realized_r=1,spread_cost_r=-.1,closed_at=NOW+timedelta(hours=1))
 assert not r["closed"] and "SPREAD_COST_INVALID" in r["reasons"]
 r2=close_paper_trade(trade(),decision(),realized_r=-1,outcome="WIN",closed_at=NOW+timedelta(hours=1))
 assert not r2["closed"] and "OUTCOME_NET_R_MISMATCH" in r2["reasons"]

def test_wait_entry_cannot_be_closed_as_if_filled():
 r=close_paper_trade(trade(status="WAIT_ENTRY"),decision(),realized_r=1,closed_at=NOW+timedelta(hours=1))
 assert not r["closed"] and "TRADE_NOT_CLOSABLE" in r["reasons"]

def test_identity_mismatch_fails_closed():
 r=close_paper_trade(trade(pair="GBP/USD"),decision(),realized_r=1,closed_at=NOW+timedelta(hours=1))
 assert not r["closed"] and "PAIR_MISMATCH" in r["reasons"]

def test_close_is_idempotent_and_duplicate_evidence_requires_recovery():
 first=close_paper_trade(trade(),decision(),realized_r=1,closed_at=NOW+timedelta(hours=1))
 existing=first["result"]
 again=close_paper_trade(trade(),decision(),[existing],realized_r=1,closed_at=NOW+timedelta(hours=1))
 assert again["state"]=="ALREADY_CLOSED" and not again["closed"]
 dup=close_paper_trade(trade(),decision(),[existing,dict(existing)],realized_r=1,closed_at=NOW+timedelta(hours=1))
 assert dup["state"]=="RECOVERY_REQUIRED"

def test_close_before_decision_is_rejected():
 r=close_paper_trade(trade(),decision(),realized_r=1,closed_at=NOW-timedelta(seconds=1))
 assert not r["closed"] and "CLOSED_BEFORE_DECISION" in r["reasons"]
