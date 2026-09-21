"""AtlasQuant derived timeframe cache for research/Paper preparation.

Builds only closed research bars from data already collected by the Autopilot.
It never calls a market-data provider, never changes the live Gate and never
creates an order.

M30 is derived only from two complete contiguous M15 candles.
D1 comes from completed daily provider bars.
W1 is derived only from completed D1 bars and excludes the current week.
"""
from __future__ import annotations

from typing import Any, Mapping
import pandas as pd

from market_map_core_v10 import NY_TZ, aggregate_ohlc, completed_daily, normalize_ohlc

SCHEMA="ATLASQUANT_RESEARCH_TIMEFRAME_CACHE_V1"


def _records(frame:pd.DataFrame,limit:int)->list[dict[str,Any]]:
    d=normalize_ohlc(frame)
    if d.empty:
        return []
    d=d.tail(max(1,int(limit))).copy()
    d["datetime"]=pd.to_datetime(d["datetime"],utc=True,errors="coerce").astype(str)
    return d[["datetime","open","high","low","close"]].to_dict("records")


def exact_m30_from_m15(records:list[dict[str,Any]]|None,*,now:Any=None)->pd.DataFrame:
    d=normalize_ohlc(records or [])
    if d.empty:
        return d
    now_ts=pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    now_ts=now_ts.tz_localize("UTC") if now_ts.tzinfo is None else now_ts.tz_convert("UTC")
    d=d.sort_values("datetime").drop_duplicates("datetime",keep="last").reset_index(drop=True)
    d=d[d["datetime"].dt.minute.mod(15).eq(0) & d["datetime"].dt.second.eq(0)].copy()
    d["bucket"]=d["datetime"].dt.floor("30min")
    out=[]
    for bucket,g in d.groupby("bucket",sort=True):
        expected={bucket,bucket+pd.Timedelta(minutes=15)}
        actual=set(pd.Timestamp(x) for x in g["datetime"])
        if actual!=expected or len(g)!=2:
            continue
        if bucket+pd.Timedelta(minutes=30)>now_ts:
            continue
        g=g.sort_values("datetime")
        out.append({
            "datetime":bucket,
            "open":float(g.iloc[0]["open"]),
            "high":float(g["high"].max()),
            "low":float(g["low"].min()),
            "close":float(g.iloc[-1]["close"]),
        })
    return normalize_ohlc(pd.DataFrame(out))


def completed_d1(records:list[dict[str,Any]]|None,*,now:Any=None)->pd.DataFrame:
    d=normalize_ohlc(records or [])
    if d.empty:
        return d
    now_ts=pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    now_ts=now_ts.tz_localize("UTC") if now_ts.tzinfo is None else now_ts.tz_convert("UTC")
    today=now_ts.tz_convert(NY_TZ).date()
    return completed_daily(d,today)


def completed_w1_from_d1(records:list[dict[str,Any]]|None,*,now:Any=None)->pd.DataFrame:
    d=completed_d1(records,now=now)
    if d.empty:
        return d
    now_ts=pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    now_ts=now_ts.tz_localize("UTC") if now_ts.tzinfo is None else now_ts.tz_convert("UTC")
    today=now_ts.tz_convert(NY_TZ).date()
    current_end=pd.Timestamp(today).to_period("W-FRI").end_time.date()
    weekly=aggregate_ohlc(d,"W-FRI")
    if weekly.empty:
        return weekly
    return weekly[weekly["datetime"].dt.date < current_end].reset_index(drop=True)


def build_research_timeframe_cache(
    scanner:Mapping[str,Any]|None,
    daily_cache:Mapping[str,Any]|None,
    *,
    now:Any=None,
)->dict[str,Any]:
    now_ts=pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    now_ts=now_ts.tz_localize("UTC") if now_ts.tzinfo is None else now_ts.tz_convert("UTC")
    scanner_rows=dict((scanner or {}).get("resultados",{}) or {}) if isinstance(scanner,Mapping) else {}
    daily_rows=dict((daily_cache or {}).get("pairs",{}) or {}) if isinstance(daily_cache,Mapping) else {}
    pairs={}
    for pair in sorted(set(scanner_rows)|set(daily_rows)):
        scanner_pair=dict(scanner_rows.get(pair,{}) or {})
        tec=dict(scanner_pair.get("tecnico",{}) or {})
        cache=dict(tec.get("cache_v110",{}) or {})
        daily=list(dict(daily_rows.get(pair,{}) or {}).get("records",[]) or [])
        m30=exact_m30_from_m15(list(cache.get("m15",[]) or []),now=now_ts)
        d1=completed_d1(daily,now=now_ts)
        w1=completed_w1_from_d1(daily,now=now_ts)
        pairs[str(pair).upper()]={
            "M30":_records(m30,160),
            "D1":_records(d1,320),
            "W1":_records(w1,104),
            "provenance":{
                "M30":"DERIVED_FROM_EXACT_CLOSED_M15",
                "D1":"COMPLETED_PROVIDER_D1",
                "W1":"DERIVED_FROM_COMPLETED_D1",
            },
        }
    return {
        "schema":SCHEMA,
        "generated_at":now_ts.isoformat(),
        "pairs":pairs,
        "safety":{
            "research_only":True,
            "provider_calls_added":False,
            "real_orders":False,
            "automatic_execution":False,
            "automatic_gate_change":False,
        },
    }


__all__=[
    "SCHEMA","exact_m30_from_m15","completed_d1","completed_w1_from_d1",
    "build_research_timeframe_cache",
]
