import pandas as pd
from atlasquant_timeframe_resampler import derive_from_m15, resampling_readiness

def _m15(n=1000):
    dt=pd.date_range("2026-01-01",periods=n,freq="15min",tz="UTC")
    return pd.DataFrame({"datetime":dt,"open":range(n),"high":[x+2 for x in range(n)],"low":[max(.1,x-.5) for x in range(n)],"close":[x+1 for x in range(n)]})

def test_m15_derives_only_complete_h1_and_h4_bars():
    d=_m15(64)
    assert len(derive_from_m15(d,"1h"))==16
    assert len(derive_from_m15(d,"4h"))==4

def test_gap_drops_incomplete_derived_bucket():
    d=_m15(20).drop(index=[2])
    assert len(derive_from_m15(d,"1h"))==4

def test_readiness_never_self_authorizes_execution():
    r=resampling_readiness(_m15())
    assert r["history_sufficient"] is True
    assert r["validated_for_execution"] is False
    assert r["manual_validation_required"] is True
