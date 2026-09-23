"""Deterministic higher-timeframe derivation from closed M15 candles.

This module is deliberately pure. It never fetches provider data and never grants
execution. Derived H1/H4 frames carry provenance so downstream gates can distinguish
provider candles from AtlasQuant-derived candles.
"""
from __future__ import annotations
from typing import Any
import pandas as pd

_REQUIRED=("datetime","open","high","low","close")

def _closed_m15(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty or not set(_REQUIRED).issubset(frame.columns):
        return pd.DataFrame(columns=_REQUIRED)
    d=frame.loc[:,_REQUIRED].copy()
    d["datetime"]=pd.to_datetime(d["datetime"],utc=True,errors="coerce")
    for c in _REQUIRED[1:]:
        d[c]=pd.to_numeric(d[c],errors="coerce")
    d=d.dropna(subset=_REQUIRED).sort_values("datetime",kind="mergesort")
    return d.drop_duplicates("datetime",keep="last").reset_index(drop=True)

def derive_from_m15(frame: pd.DataFrame | None, target: str) -> pd.DataFrame:
    target=str(target).lower()
    rule={"1h":"1h","4h":"4h"}.get(target)
    if rule is None:
        raise ValueError("target must be 1h or 4h")
    d=_closed_m15(frame)
    if d.empty:
        return d
    idx=d.set_index("datetime")
    out=idx.resample(rule,label="left",closed="left",origin="epoch").agg(
        {"open":"first","high":"max","low":"min","close":"last"}
    ).dropna()
    # A valid derived candle must contain every expected M15 slot.
    counts=idx["close"].resample(rule,label="left",closed="left",origin="epoch").count()
    expected=4 if target=="1h" else 16
    out=out.loc[counts.reindex(out.index).eq(expected)].reset_index()
    out.attrs["derived_from"]="15min"
    out.attrs["target_interval"]=target
    out.attrs["provenance"]="ATLASQUANT_RESAMPLE_M15"
    return out

def resampling_readiness(frame: pd.DataFrame | None, *, required_history_bars: int=1000) -> dict[str,Any]:
    d=_closed_m15(frame)
    h1=derive_from_m15(d,"1h")
    h4=derive_from_m15(d,"4h")
    enough=len(d)>=max(0,int(required_history_bars))
    return {
        "m15_bars":len(d),"h1_bars":len(h1),"h4_bars":len(h4),
        "history_sufficient":enough,
        "h1_available":len(h1)>=60,
        "h4_available":len(h4)>=60,
        "validated_for_execution":False,
        "manual_validation_required":True,
    }
