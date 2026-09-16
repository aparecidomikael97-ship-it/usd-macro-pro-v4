"""AtlasQuant AMD / Power of Three Strategy Replay V1.

Offline technical research using a strict temporal state machine:
ACCUMULATION -> MANIPULATION -> DISTRIBUTION.

The accumulation range is frozen before the manipulation candle. Distribution
can only confirm on a later candle. No macro/Fed direction is invented and the
live Gate is never modified.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import math

import pandas as pd

from atlasquant_operational_backtest import normalize_candles


@dataclass
class _PendingAMD:
    side: str
    acc_high: float
    acc_low: float
    acc_start_index: int
    acc_end_index: int
    manipulation_index: int
    manipulation_extreme: float
    manipulation_close: float
    expires_index: int


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


def generate_amd_signals(
    candles: pd.DataFrame,
    *,
    pair: str,
    accumulation_bars: int = 8,
    max_distribution_bars: int = 4,
    stop_buffer_atr: float = 0.0,
    min_rr: float = 0.0,
    allow_buy: bool = True,
    allow_sell: bool = True,
    min_bars: int = 14,
) -> list[dict[str, Any]]:
    """Generate AMD/PO3 plans with strict phase ordering.

    BUY:
      accumulation range -> sweep below acc low + close back above ->
      later close above midpoint and above manipulation close.

    SELL is the exact mirror.

    Entry is the confirming distribution close. Structural target is the
    opposite side of the frozen accumulation range.
    """
    d=normalize_candles(candles)
    pair=str(pair or "").strip().upper()
    acc_n=int(accumulation_bars)
    max_dist=int(max_distribution_bars)
    buf=float(stop_buffer_atr)
    minimum_rr=float(min_rr)

    if d.empty or not pair:
        return []
    if acc_n<4:
        raise ValueError("accumulation_bars must be >= 4")
    if max_dist<1:
        raise ValueError("max_distribution_bars must be >= 1")
    if not math.isfinite(buf) or buf<0:
        raise ValueError("stop_buffer_atr must be >= 0")
    if not math.isfinite(minimum_rr) or minimum_rr<0:
        raise ValueError("min_rr must be >= 0")

    pending: _PendingAMD|None=None
    rows=[]
    start=max(acc_n+1,int(min_bars))

    for i in range(start-1,len(d)):
        ts=pd.Timestamp(d.iloc[i]["datetime"])
        atr=_atr_last(d.iloc[max(0,i-59):i+1].reset_index(drop=True))
        if atr is None:
            continue

        # Phase 3: distribution can only occur AFTER manipulation.
        if pending is not None:
            p=pending
            side=p.side
            if i>p.expires_index:
                pending=None
            elif i>p.manipulation_index:
                close=float(d.iloc[i]["close"])
                mid=(p.acc_high+p.acc_low)/2.0
                if side=="BUY":
                    distribution=close>mid and close>p.manipulation_close
                    entry=close
                    stop=p.manipulation_extreme-atr*buf
                    target=p.acc_high
                    risk=entry-stop
                    reward=target-entry
                    raid_side="SSL"
                else:
                    distribution=close<mid and close<p.manipulation_close
                    entry=close
                    stop=p.manipulation_extreme+atr*buf
                    target=p.acc_low
                    risk=stop-entry
                    reward=entry-target
                    raid_side="BSL"

                if distribution:
                    setup_rr=reward/risk if risk>0 else -1.0
                    if risk>0 and reward>0 and setup_rr>=minimum_rr:
                        rows.append({
                            "signal_time":ts.isoformat(),
                            "pair":pair,
                            "setup":"AMD_PO3",
                            "session":_session_label(ts),
                            "side":side,
                            "entry":float(entry),
                            "stop":float(stop),
                            "target":float(target),
                            "source":"AUTO_REPLAY_AMD_V1",
                            "notes":"AMD/PO3 técnico com ordem temporal rígida; sem contexto macro/Fed.",
                            "phase":"DISTRIBUTION",
                            "acc_high":float(p.acc_high),
                            "acc_low":float(p.acc_low),
                            "acc_mid":float(mid),
                            "acc_start_index":int(p.acc_start_index),
                            "acc_end_index":int(p.acc_end_index),
                            "manipulation_index":int(p.manipulation_index),
                            "distribution_index":int(i),
                            "manipulation_side":raid_side,
                            "manipulation_extreme":float(p.manipulation_extreme),
                            "manipulation_close":float(p.manipulation_close),
                            "distribution_close":float(close),
                            "setup_rr":float(setup_rr),
                            "stop_buffer_atr":buf,
                            "min_rr":minimum_rr,
                            "accumulation_bars":acc_n,
                            "max_distribution_bars":max_dist,
                        })
                    # Once distribution resolves this state, do not recycle it.
                    pending=None

        # Phase 2: detect a NEW manipulation using a range frozen from prior bars.
        if i<acc_n:
            continue
        acc=d.iloc[i-acc_n:i]
        ah=float(acc["high"].max())
        al=float(acc["low"].min())
        if not (math.isfinite(ah) and math.isfinite(al) and ah>al):
            continue

        row=d.iloc[i]
        if pending is None:
            buy_manip=allow_buy and float(row["low"])<al and float(row["close"])>al
            sell_manip=allow_sell and float(row["high"])>ah and float(row["close"])<ah

            selected=None
            if buy_manip and sell_manip:
                width=ah-al
                buy_depth=(al-float(row["low"]))/width
                sell_depth=(float(row["high"])-ah)/width
                selected="BUY" if buy_depth>=sell_depth else "SELL"
            elif buy_manip:
                selected="BUY"
            elif sell_manip:
                selected="SELL"

            if selected=="BUY":
                pending=_PendingAMD(
                    side="BUY",
                    acc_high=ah,
                    acc_low=al,
                    acc_start_index=i-acc_n,
                    acc_end_index=i-1,
                    manipulation_index=i,
                    manipulation_extreme=float(row["low"]),
                    manipulation_close=float(row["close"]),
                    expires_index=i+max_dist,
                )
            elif selected=="SELL":
                pending=_PendingAMD(
                    side="SELL",
                    acc_high=ah,
                    acc_low=al,
                    acc_start_index=i-acc_n,
                    acc_end_index=i-1,
                    manipulation_index=i,
                    manipulation_extreme=float(row["high"]),
                    manipulation_close=float(row["close"]),
                    expires_index=i+max_dist,
                )

    return rows
