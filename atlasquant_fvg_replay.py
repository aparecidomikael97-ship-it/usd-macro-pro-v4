"""AtlasQuant FVG Strategy Replay V1.

Offline, technical-only replay for Fair Value Gap research.
Signals are generated candle by candle from information available at that bar.
No macro/Fed context is invented and the live Gate is never modified.
"""
from __future__ import annotations

from typing import Any
import math

import pandas as pd

from atlasquant_operational_backtest import normalize_candles


def _atr_last(d: pd.DataFrame, length: int = 14) -> float | None:
    if d.empty:
        return None
    prev=d["close"].shift(1)
    tr=pd.concat(
        [
            d["high"]-d["low"],
            (d["high"]-prev).abs(),
            (d["low"]-prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr=tr.rolling(length,min_periods=max(4,length//3)).mean()
    if atr.empty or pd.isna(atr.iloc[-1]):
        return None
    out=float(atr.iloc[-1])
    return out if math.isfinite(out) and out>0 else None


def _session_label(ts: pd.Timestamp) -> str:
    hour=int(ts.hour)
    if 0 <= hour < 7:
        return "Asia"
    if 7 <= hour < 12:
        return "London"
    if 12 <= hour < 17:
        return "New York"
    return "Off-hours"


def generate_fvg_signals(
    candles: pd.DataFrame,
    *,
    pair: str,
    rr_target: float = 2.0,
    stop_buffer_atr: float = 0.0,
    min_gap_atr: float = 0.0,
    entry_mode: str = "MIDPOINT",
    allow_buy: bool = True,
    allow_sell: bool = True,
    min_bars: int = 14,
) -> list[dict[str, Any]]:
    """Generate explicit FVG plans from newly formed three-candle gaps.

    BUY FVG: current low > high two candles ago.
    SELL FVG: current high < low two candles ago.

    The signal time is the close time of the third candle. The generic backtest
    engine begins execution after that candle, preserving the no-look-ahead rule.
    """
    d=normalize_candles(candles)
    pair=str(pair or "").strip().upper()
    mode=str(entry_mode or "MIDPOINT").strip().upper()
    if d.empty or not pair:
        return []
    if mode not in ("MIDPOINT","PROXIMAL"):
        raise ValueError("entry_mode must be MIDPOINT or PROXIMAL")

    rr=float(rr_target)
    buf=float(stop_buffer_atr)
    min_gap=float(min_gap_atr)
    if not math.isfinite(rr) or rr<=0:
        raise ValueError("rr_target must be positive")
    if not math.isfinite(buf) or buf<0:
        raise ValueError("stop_buffer_atr must be >= 0")
    if not math.isfinite(min_gap) or min_gap<0:
        raise ValueError("min_gap_atr must be >= 0")

    rows=[]
    start=max(3,int(min_bars))
    for i in range(start-1,len(d)):
        hist=d.iloc[max(0,i-179):i+1].reset_index(drop=True)
        if len(hist)<3:
            continue
        atr=_atr_last(hist)
        if atr is None:
            continue

        c1=hist.iloc[-3]
        c3=hist.iloc[-1]
        ts=pd.Timestamp(c3["datetime"])

        setups=[]
        bull_gap=float(c3["low"])-float(c1["high"])
        if allow_buy and bull_gap>0 and bull_gap>=atr*min_gap:
            setups.append(("BUY",float(c1["high"]),float(c3["low"]),bull_gap))
        bear_gap=float(c1["low"])-float(c3["high"])
        if allow_sell and bear_gap>0 and bear_gap>=atr*min_gap:
            setups.append(("SELL",float(c3["high"]),float(c1["low"]),bear_gap))

        for side,zlow,zhigh,gap_size in setups:
            if not (math.isfinite(zlow) and math.isfinite(zhigh) and zhigh>zlow):
                continue
            if side=="BUY":
                entry=(zlow+zhigh)/2.0 if mode=="MIDPOINT" else zhigh
                stop=zlow-atr*buf
                risk=entry-stop
                target=entry+risk*rr
            else:
                entry=(zlow+zhigh)/2.0 if mode=="MIDPOINT" else zlow
                stop=zhigh+atr*buf
                risk=stop-entry
                target=entry-risk*rr

            if not all(math.isfinite(x) for x in (entry,stop,target,risk)) or risk<=0:
                continue

            rows.append({
                "signal_time":ts.isoformat(),
                "pair":pair,
                "setup":"FVG",
                "session":_session_label(ts),
                "side":side,
                "entry":float(entry),
                "stop":float(stop),
                "target":float(target),
                "source":"AUTO_REPLAY_FVG_V1",
                "notes":"FVG técnico de três candles; sem contexto macro/Fed.",
                "fvg_zone_low":float(zlow),
                "fvg_zone_high":float(zhigh),
                "fvg_gap_size":float(gap_size),
                "fvg_gap_atr":float(gap_size/atr),
                "replay_bar_index":int(i),
                "rr_target":rr,
                "stop_buffer_atr":buf,
                "min_gap_atr":min_gap,
                "entry_mode":mode,
            })
    return rows
