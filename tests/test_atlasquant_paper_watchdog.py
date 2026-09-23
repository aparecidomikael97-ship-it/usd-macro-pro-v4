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
