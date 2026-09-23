from datetime import datetime,timezone
from atlasquant_paper_orchestrator import orchestrate_paper
NOW=datetime(2026,9,23,12,tzinfo=timezone.utc)
O={"opportunity_id":"O1","pair":"EUR/USD","direction":"SELL","strategy_version":"AMD1","score_version":"S1","risk_version":"R1","quality_score":90,"confidence":90,"gates":{},"timestamp":NOW.isoformat()}
A={"approved":True,"risk_gate":"APPROVED","risk_auth_id":"R1","expires_at":"2026-09-23T12:05:00+00:00","opportunity_id":"O1","pair":"EUR/USD","strategy_version":"AMD1","max_authorized_risk":5,"max_authorized_exposure":5,"real_orders_enabled":False,"fail_closed":True}
def test_accept_once_only():
 a=orchestrate_paper(O,A,[],now=NOW); assert a["state"]=="ACCEPTED"
 b=orchestrate_paper(O,A,[a["paper_trade"]],now=NOW); assert b["state"]=="ALREADY_EXISTS" and not b["accepted"]
def test_duplicate_ledger_requires_recovery():
 row={"opportunity_id":"O1","environment":"PAPER"}; r=orchestrate_paper(O,A,[row,row],now=NOW)
 assert r["state"]=="RECOVERY_REQUIRED"
def test_watchdog_blocks_new_paper(): assert orchestrate_paper(O,A,[],watchdog_state="PROTECTED",now=NOW)["state"]=="REJECTED"
def test_expired_auth_rejected():
 a=dict(A);a["expires_at"]="2026-09-23T11:59:00+00:00";assert not orchestrate_paper(O,a,[],now=NOW)["accepted"]
