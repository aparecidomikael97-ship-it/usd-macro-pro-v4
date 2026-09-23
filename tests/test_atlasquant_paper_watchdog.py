from atlasquant_paper_watchdog import paper_watchdog
def test_critical_paper_store_failure_halts_new_entries():
 c={x:{"healthy":True} for x in ("market_data","scanner","risk","result_store","paper_store")}
 c["result_store"]["healthy"]=False
 r=paper_watchdog(c)
 assert r["state"]=="HALTED" and not r["new_paper_entries_allowed"] and r["management_allowed"]
def test_market_failure_protects_without_live_fallback():
 c={x:{"healthy":True} for x in ("market_data","scanner","risk","result_store","paper_store")}
 c["market_data"]["healthy"]=False
 r=paper_watchdog(c)
 assert r["state"]=="PROTECTED" and r["real_orders_enabled"] is False

def test_watchdog_can_enforce_freshness_without_live_fallback():
 from datetime import datetime,timezone,timedelta
 now=datetime(2026,9,23,12,tzinfo=timezone.utc)
 c={x:{"healthy":True,"last_ok":(now-timedelta(seconds=5)).isoformat()} for x in ("market_data","scanner","risk","result_store","paper_store")}
 c["market_data"]["last_ok"]=(now-timedelta(seconds=90)).isoformat()
 r=paper_watchdog(c,now=now,max_age_seconds=60)
 assert r["state"]=="PROTECTED" and not r["new_paper_entries_allowed"] and r["real_orders_enabled"] is False
