import pandas as pd
from atlasquant_dow_cache_builder import structural_trend,dow_context_from_caches,build_dow_context_map

def bars(direction="up",n=80,freq="1h"):
 t=pd.date_range("2026-01-01",periods=n,freq=freq,tz="UTC")
 rows=[]
 for i,ts in enumerate(t):
  base=(100+i*0.5) if direction=="up" else (140-i*0.5)
  wiggle=(i%4)*0.08
  close=base+wiggle
  rows.append({"datetime":ts.isoformat(),"open":close-0.1,"high":close+0.35,"low":close-0.35,"close":close})
 return rows

def test_structural_trend_fails_closed_on_missing_history():
 assert structural_trend([])=="UNKNOWN"
 assert structural_trend(bars(n=5))=="UNKNOWN"

def test_builder_uses_existing_caches_and_never_authorizes_execution():
 scanner={"resultados":{"EURUSD":{"tecnico":{"cache_v110":{"h1":bars("up"),"h4":bars("up")}}}}}
 research={"pairs":{"EURUSD":{"D1":bars("up",80,"1D"),"W1":bars("up",40,"7D"),
 "provenance":{"D1":"COMPLETED_PROVIDER_D1","W1":"DERIVED_FROM_COMPLETED_D1"}}}}
 r=dow_context_from_caches("EURUSD",scanner,research)
 assert r["pair"]=="EURUSD"
 assert r["research_only"] is True and r["execution_authorized"] is False
 assert r["real_orders_enabled"] is False
 assert r["provenance"]["D1"]=="COMPLETED_PROVIDER_D1"

def test_missing_higher_timeframe_stays_unknown_not_fake_aligned():
 scanner={"resultados":{"EURUSD":{"tecnico":{"cache_v110":{"h1":bars("up"),"h4":bars("up")}}}}}
 r=dow_context_from_caches("EURUSD",scanner,{"pairs":{}})
 assert r["timeframe_trends"]["W1"]=="UNKNOWN"
 assert r["timeframe_trends"]["D1"]=="UNKNOWN"
 assert r["status"]=="INSUFFICIENT_DATA"

def test_context_map_cannot_change_ranking_or_gate():
 r=build_dow_context_map({"resultados":{"EURUSD":{}}},{"pairs":{}})
 assert r["safety"]["changes_quality_score"] is False
 assert r["safety"]["changes_ranking"] is False
 assert r["safety"]["changes_gate"] is False
 assert r["safety"]["real_orders_enabled"] is False
