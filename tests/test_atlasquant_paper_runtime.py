from atlasquant_paper_runtime import paper_state_snapshot,recover_paper_state
def row(pair="EUR/USD",status="OPEN",rid="P1"): return {"pair":pair,"status":status,"paper_request_id":rid,"opportunity_id":"O1"}
def test_restart_recovers_only_active_and_marks_missing_market():
 s=paper_state_snapshot([row(),row("GBP/USD","CLOSED","P2")],created_at="2026-09-23T12:00:00+00:00")
 r=recover_paper_state(s,current_market={})
 assert r["ok"] and len(r["trades"])==1 and r["trades"][0]["recovery_state"]=="AWAITING_MARKET_RECONCILIATION"
def test_present_but_unvalidated_market_does_not_recover():
 s=paper_state_snapshot([row()]); r=recover_paper_state(s,current_market={"EUR/USD":1.18})
 assert r["trades"][0]["recovery_state"]=="AWAITING_VALID_MARKET_DATA"
def test_valid_fresh_market_recovers():
 s=paper_state_snapshot([row()]); r=recover_paper_state(s,current_market={"EUR/USD":{"price":1.18,"fresh":True,"valid":True}})
 assert r["ok"] and r["trades"][0]["recovery_state"]=="RECOVERED"
def test_duplicate_runtime_id_fails_closed():
 s=paper_state_snapshot([row(rid="P1"),row("GBP/USD",rid="P1")])
 assert not recover_paper_state(s,current_market={})["ok"]
def test_tampered_snapshot_fails_closed():
 s=paper_state_snapshot([row()]); s["active"][0]["pair"]="GBP/USD"
 assert not recover_paper_state(s,current_market={})["ok"]
