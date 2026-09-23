from atlasquant_system_health import system_health
def good():return {x:{"state":"NORMAL","healthy":True} for x in ("market_data","scanner","risk","result_store","paper_store")}
def test_all_normal():assert system_health(good())["state"]=="NORMAL"
def test_market_data_failure_protects():
 x=good();x["market_data"]={"state":"PROTECTED","healthy":False};r=system_health(x);assert r["state"]=="PROTECTED" and not r["new_entries_allowed"] and r["management_mode"]=="SAFE_ONLY"
def test_risk_failure_halts():
 x=good();x["risk"]={"state":"HALTED","healthy":False};r=system_health(x);assert r["state"]=="HALTED" and r["management_allowed"]
def test_missing_critical_component_halts():assert system_health({})["state"]=="HALTED"

def test_normal_state_without_explicit_healthy_is_not_trusted():
 x={k:{"state":"NORMAL"} for k in ("market_data","scanner","risk","result_store","paper_store")}
 r=system_health(x);assert r["state"]=="HALTED" and not r["new_entries_allowed"]
def test_naive_health_clock_is_emitted_as_utc():
 from datetime import datetime
 r=system_health(good(),now=datetime(2026,9,23,12));assert r["checked_at"].endswith("+00:00")

def test_freshness_can_protect_stale_market_and_halt_stale_risk():
 from datetime import datetime,timezone,timedelta
 now=datetime(2026,9,23,12,tzinfo=timezone.utc);x=good()
 for row in x.values():row["last_ok"]=(now-timedelta(seconds=10)).isoformat()
 x["market_data"]["last_ok"]=(now-timedelta(seconds=61)).isoformat()
 r=system_health(x,now=now,max_age_seconds=60);assert r["state"]=="PROTECTED" and "MARKET_DATA_HEARTBEAT_STALE" in r["reasons"]
 x=good()
 for row in x.values():row["last_ok"]=(now-timedelta(seconds=10)).isoformat()
 x["risk"]["last_ok"]=(now-timedelta(seconds=61)).isoformat()
 r=system_health(x,now=now,max_age_seconds=60);assert r["state"]=="HALTED" and "RISK_HEARTBEAT_STALE" in r["reasons"]

def test_invalid_freshness_config_fails_closed():
 r=system_health(good(),max_age_seconds=0)
 assert r["state"]=="HALTED" and "HEALTH_FRESHNESS_CONFIG_INVALID" in r["reasons"]
