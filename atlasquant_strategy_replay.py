"""AtlasQuant ICT Strategy Replay V1.

Offline historical replay that turns objective BOS/CHOCH + Order Block rules
into explicit research plans, candle by candle, without using future bars.

This module is research-only. It does not change the live Gate or macro engine.
"""
from __future__ import annotations

from typing import Any
import math

import pandas as pd

from ict_structure_v111 import detect_bos_choch, detect_order_block
from atlasquant_operational_backtest import normalize_candles


def _atr_last(d: pd.DataFrame, length: int = 14) -> float | None:
    if d.empty:
        return None
    prev = d["close"].shift(1)
    tr = pd.concat(
        [
            d["high"] - d["low"],
            (d["high"] - prev).abs(),
            (d["low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(length, min_periods=max(4, length // 3)).mean()
    if atr.empty or pd.isna(atr.iloc[-1]):
        return None
    out=float(atr.iloc[-1])
    return out if math.isfinite(out) and out > 0 else None


def _session_label(ts: pd.Timestamp) -> str:
    """UTC session label used only for grouping research results."""
    hour=int(ts.hour)
    if 0 <= hour < 7:
        return "Asia"
    if 7 <= hour < 12:
        return "London"
    if 12 <= hour < 17:
        return "New York"
    return "Off-hours"


def generate_bos_choch_ob_signals(
    candles: pd.DataFrame,
    *,
    pair: str,
    rr_target: float = 2.0,
    stop_buffer_atr: float = 0.05,
    entry_mode: str = "MIDPOINT",
    allow_bos: bool = True,
    allow_choch: bool = True,
    allow_buy: bool = True,
    allow_sell: bool = True,
    min_bars: int = 20,
) -> list[dict[str, Any]]:
    """Replay structure rules and emit explicit entry/stop/target plans.

    A signal is emitted only when the latest confirmed structure event happened
    on the current replay bar and the current Order Block belongs to that same
    event. Every prefix contains only information available up to that candle.
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
    if not math.isfinite(rr) or rr <= 0:
        raise ValueError("rr_target must be positive")
    if not math.isfinite(buf) or buf < 0:
        raise ValueError("stop_buffer_atr must be >= 0")

    rows=[]
    seen=set()
    start=max(12,int(min_bars))
    for end in range(start-1,len(d)):
        prefix=d.iloc[:end+1].copy()
        now=pd.Timestamp(prefix.iloc[-1]["datetime"])
        atr=_atr_last(prefix)
        if atr is None:
            continue

        for side,side_allowed in (("BUY",allow_buy),("SELL",allow_sell)):
            if not side_allowed:
                continue
            structure=detect_bos_choch(prefix,side)
            event=str(structure.get("event","NONE")).upper()
            if event not in ("BOS","CHOCH"):
                continue
            if event=="BOS" and not allow_bos:
                continue
            if event=="CHOCH" and not allow_choch:
                continue
            if str(structure.get("event_side","")).upper()!=side:
                continue
            if int(structure.get("bars_ago",999999))!=0:
                continue

            ob=detect_order_block(prefix,side)
            if int(ob.get("structure_index",-1)) != len(prefix)-1:
                continue
            if bool(ob.get("invalidated",False)):
                continue
            zlow=ob.get("zone_low")
            zhigh=ob.get("zone_high")
            if zlow is None or zhigh is None:
                continue
            zlow=float(zlow); zhigh=float(zhigh)
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

            key=(now.isoformat(),side,event,round(zlow,10),round(zhigh,10))
            if key in seen:
                continue
            seen.add(key)

            rows.append({
                "signal_time":now.isoformat(),
                "pair":pair,
                "setup":f"{event}+ORDER_BLOCK",
                "session":_session_label(now),
                "side":side,
                "entry":float(entry),
                "stop":float(stop),
                "target":float(target),
                "source":"AUTO_REPLAY_ICT_V1",
                "notes":"Gerado por replay histórico candle a candle; sem contexto macro/Fed.",
                "structure_event":event,
                "structure_level":structure.get("level"),
                "structure_prior_bias":structure.get("prior_bias"),
                "break_margin":structure.get("break_margin"),
                "noise_tolerance":structure.get("noise_tolerance"),
                "ob_zone_low":zlow,
                "ob_zone_high":zhigh,
                "ob_origin_index":ob.get("origin_index"),
                "ob_structure_index":ob.get("structure_index"),
                "rr_target":rr,
                "stop_buffer_atr":buf,
                "entry_mode":mode,
            })
    return rows
