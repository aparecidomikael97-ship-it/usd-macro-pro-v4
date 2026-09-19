"""AtlasQuant CRT Strategy Replay V1.

Offline technical research for a three-candle Candle Range Theory pattern:
anchor range -> liquidity raid/reclaim -> directional delivery.

The rule set mirrors AtlasQuant's existing CRT detector, but does not invent
macro direction. BUY and SELL patterns are evaluated independently.
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


def generate_crt_signals(
    candles: pd.DataFrame,
    *,
    pair: str,
    stop_buffer_atr: float = 0.0,
    min_rr: float = 0.0,
    allow_buy: bool = True,
    allow_sell: bool = True,
    min_bars: int = 14,
) -> list[dict[str, Any]]:
    """Generate explicit CRT research plans candle by candle.

    Entry is the confirmed delivery candle close, submitted only after that
    candle by the generic backtester. Stop is beyond the raid extreme and the
    structural target is the opposite side of the anchor range.
    """
    d=normalize_candles(candles)
    pair=str(pair or "").strip().upper()
    if d.empty or not pair:
        return []

    buf=float(stop_buffer_atr)
    minimum_rr=float(min_rr)
    if not math.isfinite(buf) or buf<0:
        raise ValueError("stop_buffer_atr must be >= 0")
    if not math.isfinite(minimum_rr) or minimum_rr<0:
        raise ValueError("min_rr must be >= 0")

    rows=[]
    start=max(3,int(min_bars))
    for i in range(start-1,len(d)):
        hist=d.iloc[:i+1]
        atr=_atr_last(hist.tail(60).reset_index(drop=True))
        if atr is None:
            continue

        c1=d.iloc[i-2]
        c2=d.iloc[i-1]
        c3=d.iloc[i]
        ah=float(c1["high"])
        al=float(c1["low"])
        if not (math.isfinite(ah) and math.isfinite(al) and ah>al):
            continue
        mid=(ah+al)/2.0
        ts=pd.Timestamp(c3["datetime"])
        candidates=[]

        if allow_buy:
            raid=float(c2["low"])<al and float(c2["close"])>al
            delivery=float(c3["close"])>float(c2["close"]) and float(c3["close"])>mid
            if raid and delivery:
                entry=float(c3["close"])
                stop=min(float(c2["low"]),al)-atr*buf
                target=ah
                risk=entry-stop
                reward=target-entry
                rr=reward/risk if risk>0 else -1.0
                if risk>0 and reward>0 and rr>=minimum_rr:
                    candidates.append(("BUY",entry,stop,target,rr,"SSL"))

        if allow_sell:
            raid=float(c2["high"])>ah and float(c2["close"])<ah
            delivery=float(c3["close"])<float(c2["close"]) and float(c3["close"])<mid
            if raid and delivery:
                entry=float(c3["close"])
                stop=max(float(c2["high"]),ah)+atr*buf
                target=al
                risk=stop-entry
                reward=entry-target
                rr=reward/risk if risk>0 else -1.0
                if risk>0 and reward>0 and rr>=minimum_rr:
                    candidates.append(("SELL",entry,stop,target,rr,"BSL"))

        for side,entry,stop,target,setup_rr,raid_side in candidates:
            rows.append({
                "signal_time":ts.isoformat(),
                "pair":pair,
                "setup":"CRT",
                "session":_session_label(ts),
                "side":side,
                "entry":float(entry),
                "stop":float(stop),
                "target":float(target),
                "source":"AUTO_REPLAY_CRT_V1",
                "notes":"CRT técnico de três candles; sem contexto macro/Fed.",
                "anchor_high":ah,
                "anchor_low":al,
                "anchor_mid":mid,
                "raid_side":raid_side,
                "raid_low":float(c2["low"]),
                "raid_high":float(c2["high"]),
                "raid_close":float(c2["close"]),
                "delivery_close":float(c3["close"]),
                "setup_rr":float(setup_rr),
                "stop_buffer_atr":buf,
                "min_rr":minimum_rr,
                "replay_bar_index":int(i),
            })
    return rows
