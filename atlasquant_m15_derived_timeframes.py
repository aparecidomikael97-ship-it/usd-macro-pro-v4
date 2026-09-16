"""AtlasQuant strict M15-derived timeframe utilities.

Research infrastructure for the 7→28-pair expansion path. H1/H4 bars are
derived only from complete, contiguous closed M15 candles. Partial groups are
discarded. This module performs no API calls and changes no live behavior.
"""
from __future__ import annotations

from typing import Any
import pandas as pd

from market_map_core_v10 import normalize_ohlc


TF_MINUTES={"1h":60,"4h":240}
TF_EXPECTED_M15={"1h":4,"4h":16}


def _closed_m15(frame: Any, *, now_utc: Any = None) -> pd.DataFrame:
    d=normalize_ohlc(frame)
    if d.empty:
        return d
    now=pd.Timestamp.now(tz="UTC") if now_utc is None else pd.to_datetime(now_utc,utc=True,errors="coerce")
    if pd.isna(now):
        raise ValueError("Invalid now_utc")
    # A timestamp denotes the M15 candle open; candle is closed 15 minutes later.
    return d[(d["datetime"] + pd.Timedelta(minutes=15)) <= now].copy()


def derive_from_m15(
    frame: Any,
    timeframe: str,
    *,
    now_utc: Any = None,
) -> pd.DataFrame:
    tf=str(timeframe).lower().strip()
    if tf not in TF_MINUTES:
        raise ValueError(f"Unsupported derived timeframe: {timeframe}")

    d=_closed_m15(frame,now_utc=now_utc)
    if d.empty:
        return pd.DataFrame(columns=["datetime","open","high","low","close","m15_count"])

    expected=TF_EXPECTED_M15[tf]
    rule=f"{TF_MINUTES[tf]}min"

    x=d.set_index("datetime").sort_index()
    grouped=x.resample(rule,label="left",closed="left",origin="epoch").agg(
        open=("open","first"),
        high=("high","max"),
        low=("low","min"),
        close=("close","last"),
        m15_count=("close","count"),
    ).dropna(subset=["open","high","low","close"])

    # Strict completeness: exactly 4/16 observations and no missing M15 interval.
    grouped=grouped[grouped["m15_count"]==expected].copy()
    if grouped.empty:
        return grouped.reset_index()

    valid_rows=[]
    for bucket,row in grouped.iterrows():
        subset=d[(d["datetime"]>=bucket) & (d["datetime"]<bucket+pd.Timedelta(minutes=TF_MINUTES[tf]))]
        expected_times=pd.date_range(
            bucket,
            periods=expected,
            freq="15min",
            tz="UTC",
        )
        actual=pd.DatetimeIndex(subset["datetime"]).tz_convert("UTC")
        if actual.equals(expected_times):
            valid_rows.append(bucket)

    grouped=grouped.loc[grouped.index.isin(valid_rows)]
    return grouped.reset_index()


def derived_timeframe_health(
    m15_frame: Any,
    *,
    now_utc: Any = None,
    min_h1_bars: int = 12,
    min_h4_bars: int = 6,
) -> dict[str,Any]:
    h1=derive_from_m15(m15_frame,"1h",now_utc=now_utc)
    h4=derive_from_m15(m15_frame,"4h",now_utc=now_utc)
    return {
        "h1_bars":int(len(h1)),
        "h4_bars":int(len(h4)),
        "h1_ready":len(h1)>=int(min_h1_bars),
        "h4_ready":len(h4)>=int(min_h4_bars),
        "strict_complete_groups":True,
        "partial_groups_discarded":True,
        "live_wiring_allowed":False,
    }
