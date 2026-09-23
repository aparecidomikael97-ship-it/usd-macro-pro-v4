import math
from datetime import datetime,timezone
from atlasquant_gate_chain import evaluate_gate_chain
from atlasquant_data_health import evaluate_pair_health

BASE={"DATA":"PASS","DIRECTION":"PASS_LONG","MACRO":"NEUTRAL","STRATEGY":"TRIGGERED","TRIGGER":"CONFIRMED","SESSION":"OPTIMAL","NEWS":"CLEAR","MARKET_CONDITION":"NORMAL","RISK":"APPROVED"}
NOW=datetime(2026,9,23,12,tzinfo=timezone.utc)

def test_invalid_macro_policy_fails_closed():
 r=evaluate_gate_chain(BASE,macro_policy="MAYBE")
 assert r["overall"]=="BLOCKED" and "MACRO_POLICY_INVALID" in r["hard_blocks"] and r["macro_policy_valid"] is False

def test_data_health_invalid_freshness_threshold_never_passes():
 for bad in (0,-1,math.nan,math.inf,"bad"):
  r=evaluate_pair_health("EURUSD",{"fetched_at":NOW.isoformat()},now=NOW,max_age_minutes=bad)
  assert r.status=="INVALID" and not r.execution_eligible and r.reason=="max_age_invalid"

def test_naive_health_clock_is_normalized_to_utc():
 r=evaluate_pair_health("EURUSD",{"fetched_at":NOW.isoformat()},now=datetime(2026,9,23,12))
 assert r.status=="PASS"
