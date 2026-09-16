"""AtlasQuant OTE Strategy Replay V1.

Offline technical research for ICT Optimal Trade Entry (62%-79% retracement).
The replay anchors directional impulses using the same 28/12 lookback geometry
as the AtlasQuant ICT engine, then emits at most one plan per impulse when price
first closes inside the OTE zone.

No macro/Fed direction is invented and the live Gate is never modified.
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


def _impulse_range(
    frame: pd.DataFrame,
    side: str,
    *,
    lookback: int = 28,
    recent_extreme: int = 12,
) -> dict[str, Any] | None:
    d=normalize_candles(frame).tail(max(lookback,recent_extreme)).reset_index(drop=True)
    if len(d)<8 or side not in ("BUY","SELL"):
        return None

    recent=max(1,min(int(recent_extreme),len(d)))
    if side=="BUY":
        hi_idx=int(d["high"].tail(recent).idxmax())
        before=d.loc[:hi_idx]
        if before.empty:
            return None
        lo_idx=int(before["low"].idxmin())
        lo=float(d.loc[lo_idx,"low"])
        hi=float(d.loc[hi_idx,"high"])
        if hi_idx<=lo_idx or hi<=lo:
            return None
    else:
        lo_idx=int(d["low"].tail(recent).idxmin())
        before=d.loc[:lo_idx]
        if before.empty:
            return None
        hi_idx=int(before["high"].idxmax())
        hi=float(d.loc[hi_idx,"high"])
        lo=float(d.loc[lo_idx,"low"])
        if lo_idx<=hi_idx or hi<=lo:
            return None

    return {
        "side":side,
        "swing_low":lo,
        "swing_high":hi,
        "low_index":lo_idx,
        "high_index":hi_idx,
    }


def generate_ote_signals(
    candles: pd.DataFrame,
    *,
    pair: str,
    rr_target: float = 2.0,
    stop_buffer_atr: float = 0.05,
    entry_mode: str = "SWEET_705",
    min_impulse_atr: float = 0.0,
    allow_buy: bool = True,
    allow_sell: bool = True,
    lookback: int = 28,
    recent_extreme: int = 12,
    min_bars: int = 28,
) -> list[dict[str, Any]]:
    """Generate one OTE plan per unique impulse."""
    d=normalize_candles(candles)
    pair=str(pair or "").strip().upper()
    mode=str(entry_mode or "SWEET_705").strip().upper()
    if d.empty or not pair:
        return []
    if mode not in ("SWEET_705","ZONE_MIDPOINT"):
        raise ValueError("entry_mode must be SWEET_705 or ZONE_MIDPOINT")

    rr=float(rr_target)
    buf=float(stop_buffer_atr)
    min_imp=float(min_impulse_atr)
    lb=int(lookback)
    recent=int(recent_extreme)
    if not math.isfinite(rr) or rr<=0:
        raise ValueError("rr_target must be positive")
    if not math.isfinite(buf) or buf<0:
        raise ValueError("stop_buffer_atr must be >= 0")
    if not math.isfinite(min_imp) or min_imp<0:
        raise ValueError("min_impulse_atr must be >= 0")
    if lb<8 or recent<1 or recent>lb:
        raise ValueError("invalid lookback/recent_extreme")

    rows=[]
    seen=set()
    start=max(lb,int(min_bars))
    for end in range(start-1,len(d)):
        window=d.iloc[max(0,end-lb+1):end+1].copy().reset_index(drop=True)
        atr=_atr_last(window)
        if atr is None:
            continue
        ts=pd.Timestamp(d.iloc[end]["datetime"])
        px=float(window.iloc[-1]["close"])
        base=end-len(window)+1
        candidates=[]

        for side,allowed in (("BUY",allow_buy),("SELL",allow_sell)):
            if not allowed:
                continue
            imp=_impulse_range(window,side,lookback=lb,recent_extreme=recent)
            if not imp:
                continue
            lo=float(imp["swing_low"]); hi=float(imp["swing_high"])
            rng=hi-lo
            if rng<=0 or rng < atr*min_imp:
                continue

            if side=="BUY":
                retr=(hi-px)/rng
                z62=hi-.62*rng
                sweet=hi-.705*rng
                z79=hi-.79*rng
                entry=sweet if mode=="SWEET_705" else (z62+z79)/2.0
                stop=lo-atr*buf
                risk=entry-stop
                target=entry+risk*rr
            else:
                retr=(px-lo)/rng
                z62=lo+.62*rng
                sweet=lo+.705*rng
                z79=lo+.79*rng
                entry=sweet if mode=="SWEET_705" else (z62+z79)/2.0
                stop=hi+atr*buf
                risk=stop-entry
                target=entry-risk*rr

            if not (.62 <= retr <= .79):
                continue
            if not all(math.isfinite(x) for x in (entry,stop,target,risk)) or risk<=0:
                continue

            low_global=base+int(imp["low_index"])
            high_global=base+int(imp["high_index"])
            impulse_key=(side,low_global,high_global)
            if impulse_key in seen:
                continue
            candidates.append({
                "distance":abs(retr-.705),
                "impulse_key":impulse_key,
                "side":side,
                "retr":retr,
                "z62":z62,
                "z79":z79,
                "sweet":sweet,
                "entry":entry,
                "stop":stop,
                "target":target,
                "lo":lo,
                "hi":hi,
                "low_global":low_global,
                "high_global":high_global,
                "impulse_atr":rng/atr,
            })

        if not candidates:
            continue
        candidates.sort(key=lambda x:(x["distance"],0 if x["side"]=="BUY" else 1))
        chosen=candidates[0]
        seen.add(chosen["impulse_key"])
        rows.append({
            "signal_time":ts.isoformat(),
            "pair":pair,
            "setup":"OTE",
            "session":_session_label(ts),
            "side":chosen["side"],
            "entry":float(chosen["entry"]),
            "stop":float(chosen["stop"]),
            "target":float(chosen["target"]),
            "source":"AUTO_REPLAY_OTE_V1",
            "notes":"OTE 62-79% técnico; direção inferida apenas do impulso, sem macro/Fed.",
            "retracement_pct":float(chosen["retr"]*100.0),
            "ote_zone_low":float(min(chosen["z62"],chosen["z79"])),
            "ote_zone_high":float(max(chosen["z62"],chosen["z79"])),
            "ote_sweet_705":float(chosen["sweet"]),
            "swing_low":float(chosen["lo"]),
            "swing_high":float(chosen["hi"]),
            "impulse_low_index":int(chosen["low_global"]),
            "impulse_high_index":int(chosen["high_global"]),
            "impulse_atr":float(chosen["impulse_atr"]),
            "replay_bar_index":int(end),
            "rr_target":rr,
            "stop_buffer_atr":buf,
            "min_impulse_atr":min_imp,
            "entry_mode":mode,
        })
    return rows
