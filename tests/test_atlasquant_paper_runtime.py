from atlasquant_paper_runtime import paper_state_snapshot,recover_paper_state
def test_restart_recovers_only_paper_and_marks_missing_market():
 s=paper_state_snapshot([{"pair":"EUR/USD","status":"OPEN"},{"pair":"GBP/USD","status":"CLOSED"}],created_at="2026-09-23T12:00:00+00:00")
 r=recover_paper_state(s,current_market={})
 assert r["ok"] and len(r["trades"])==1 and r["trades"][0]["recovery_state"]=="AWAITING_MARKET_RECONCILIATION"
 assert r["real_orders_enabled"] is False
def test_tampered_snapshot_fails_closed():
 s=paper_state_snapshot([{"pair":"EUR/USD","status":"OPEN"}]); s["active"][0]["pair"]="GBP/USD"
 assert not recover_paper_state(s,current_market={})["ok"]
