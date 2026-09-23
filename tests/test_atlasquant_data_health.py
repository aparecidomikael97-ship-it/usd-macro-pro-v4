from datetime import datetime,timezone,timedelta
from atlasquant_data_health import evaluate_pair_health, fx28_health
from atlasquant_instrument_registry import FX_28
NOW=datetime(2026,9,23,12,0,tzinfo=timezone.utc)

def test_health_pass_and_exact_boundary_stale():
    good=evaluate_pair_health("EURUSD",{"fetched_at":(NOW-timedelta(minutes=59)).isoformat()},now=NOW)
    stale=evaluate_pair_health("EURUSD",{"fetched_at":(NOW-timedelta(minutes=60)).isoformat()},now=NOW)
    assert good.status=="PASS" and good.execution_eligible
    assert stale.status=="STALE" and not stale.execution_eligible

def test_future_divergence_and_quality_fail_closed():
    assert evaluate_pair_health("EURUSD",{"fetched_at":(NOW+timedelta(minutes=1)).isoformat()},now=NOW).status=="INVALID"
    assert evaluate_pair_health("EURUSD",{"fetched_at":NOW.isoformat(),"source_divergence":True},now=NOW).status=="DIVERGENT_SOURCE"
    assert evaluate_pair_health("EURUSD",{"fetched_at":NOW.isoformat(),"quality_ok":False},now=NOW).status=="INVALID"

def test_partial_provider_failure_degrades_without_faking_28():
    rows={s:{"fetched_at":NOW.isoformat()} for s in FX_28}
    rows.pop(FX_28[-1])
    out=fx28_health(rows,now=NOW)
    assert out["execution_eligible"]==27
    assert out["complete"] is False
    assert out["system_state"]=="DEGRADED"
    assert out["counts"]["MISSING"]==1
    assert out["execution_expansion_enabled"] is False

def test_total_failure_is_protected():
    out=fx28_health({},now=NOW)
    assert out["execution_eligible"]==0
    assert out["system_state"]=="PROTECTED"
