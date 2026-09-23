import pandas as pd
from atlasquant_dow_runtime import _swing_trend,build_dow_runtime_context,attach_dow_to_packs

def _trend_frame(up=True,n=40,freq="15min"):
 rows=[]
 for i in range(n):
  base=(100+i*.2) if up else (100-i*.2)
  rows.append({"datetime":pd.Timestamp("2026-01-01",tz="UTC")+pd.Timedelta(freq)*i,
               "open":base,"high":base+0.15,"low":base-0.15,"close":base+(.08 if up else -.08)})
 return rows

def test_short_or_no_pivots_fail_closed():
 assert _swing_trend([])=="UNKNOWN"
 assert _swing_trend(_trend_frame(True,10)) in {"UNKNOWN","MIXED","BULLISH"}

def test_runtime_adds_no_provider_calls_or_execution():
 scanner={"resultados":{"EUR/USD":{"tecnico":{"cache_v110":{"m15":_trend_frame(True,128)}}}}}
 daily={"pairs":{"EUR/USD":{"records":[
  {"datetime":(pd.Timestamp("2026-01-01",tz="UTC")+pd.Timedelta(days=i)).isoformat(),
   "open":100+i*.2,"high":100+i*.3,"low":100+i*.1,"close":100+i*.25} for i in range(120)
 ]}}}
 r=build_dow_runtime_context(scanner,daily,now="2026-05-20T12:00:00Z")
 assert r["safety"]["provider_calls_added"] is False
 assert r["safety"]["ranking_weight_change"] is False
 assert r["safety"]["gate_change"] is False
 assert r["safety"]["real_orders_enabled"] is False
 assert "EUR/USD" in r["pairs"]
 assert r["pairs"]["EUR/USD"]["provider_calls_added"] is False

def test_attach_preserves_upstream_fields():
 packs=[{"pair":"EUR/USD","priority":91,"quality":80,"risk_gate":"BLOCKED"}]
 runtime={"pairs":{"EUR/USD":{"status":"CONFIRMED_CONTEXT","aligned":True}}}
 out=attach_dow_to_packs(packs,runtime)[0]
 assert out["priority"]==91 and out["quality"]==80 and out["risk_gate"]=="BLOCKED"
 assert out["dow_context"]["status"]=="CONFIRMED_CONTEXT"
