"""AtlasQuant strict M15-derived timeframe utilities.

H1/H4 bars are derived only from complete, contiguous, closed M15 candles.
Partial groups are discarded so the quota-saving layer cannot manufacture
higher-timeframe bars from incomplete M15 data.
"""
from __future__ import annotations

from typing import Any
import pandas as pd

from market_map_core_v10 import normalize_ohlc


TF_MINUTES = {"1h": 60, "4h": 240}
TF_EXPECTED_M15 = {"1h": 4, "4h": 16}


def _closed_m15(frame: Any, *, now_utc: Any = None) -> pd.DataFrame:
    d = normalize_ohlc(frame)
    if d.empty:
        return d
    now = pd.Timestamp.now(tz="UTC") if now_utc is None else pd.to_datetime(now_utc, utc=True, errors="coerce")
    if pd.isna(now):
        raise ValueError("Invalid now_utc")
    # Timestamp denotes the M15 candle open; it is closed 15 minutes later.
    return d[(d["datetime"] + pd.Timedelta(minutes=15)) <= now].copy()


def derive_from_m15(
    frame: Any,
    timeframe: str,
    *,
    now_utc: Any = None,
) -> pd.DataFrame:
    tf = str(timeframe).lower().strip()
    if tf not in TF_MINUTES:
        raise ValueError(f"Unsupported derived timeframe: {timeframe}")

    d = _closed_m15(frame, now_utc=now_utc)
    if d.empty:
        return pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "m15_count"])

    expected = TF_EXPECTED_M15[tf]
    rule = f"{TF_MINUTES[tf]}min"
    x = d.set_index("datetime").sort_index()
    grouped = x.resample(rule, label="left", closed="left", origin="epoch").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        m15_count=("close", "count"),
    ).dropna(subset=["open", "high", "low", "close"])

    # Exact completeness first: 4 M15 for H1, 16 M15 for H4.
    grouped = grouped[grouped["m15_count"] == expected].copy()
    if grouped.empty:
        return grouped.reset_index()

    # Then prove continuity: every expected 15-minute timestamp must exist.
    valid_rows = []
    for bucket, _row in grouped.iterrows():
        subset = d[
            (d["datetime"] >= bucket)
            & (d["datetime"] < bucket + pd.Timedelta(minutes=TF_MINUTES[tf]))
        ]
        expected_times = pd.date_range(bucket, periods=expected, freq="15min", tz="UTC")
        actual = pd.DatetimeIndex(subset["datetime"]).tz_convert("UTC")
        if actual.equals(expected_times):
            valid_rows.append(bucket)

    grouped = grouped.loc[grouped.index.isin(valid_rows)]
    return grouped.reset_index()


def derived_timeframe_health(
    m15_frame: Any,
    *,
    now_utc: Any = None,
    min_h1_bars: int = 12,
    min_h4_bars: int = 6,
) -> dict[str, Any]:
    h1 = derive_from_m15(m15_frame, "1h", now_utc=now_utc)
    h4 = derive_from_m15(m15_frame, "4h", now_utc=now_utc)
    return {
        "h1_bars": int(len(h1)),
        "h4_bars": int(len(h4)),
        "h1_ready": len(h1) >= int(min_h1_bars),
        "h4_ready": len(h4) >= int(min_h4_bars),
        "strict_complete_groups": True,
        "partial_groups_discarded": True,
    }
