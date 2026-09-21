"""AtlasQuant execution timeframe profiles for research/backtest.

This module is descriptive only. It classifies the timeframe used by a test so
results from intraday, day-trade, swing and position research are not mixed.
It never changes live Gate, scores or execution permissions.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

SUPPORTED_EXECUTION_TIMEFRAMES=("M15","M30","H1","H4","D1","W1")

_ALIASES={
    "15M":"M15","15MIN":"M15","M15":"M15",
    "30M":"M30","30MIN":"M30","M30":"M30",
    "1H":"H1","60M":"H1","H1":"H1",
    "4H":"H4","240M":"H4","H4":"H4",
    "1D":"D1","D":"D1","D1":"D1","DAILY":"D1",
    "1W":"W1","W":"W1","W1":"W1","WEEKLY":"W1",
}

_PROFILES={
    "M15":{"trading_style":"INTRADAY","label":"Intraday","max_wait_bars":8,"max_hold_bars":96},
    "M30":{"trading_style":"INTRADAY","label":"Intraday","max_wait_bars":8,"max_hold_bars":72},
    "H1":{"trading_style":"DAY_TRADE","label":"Day Trade","max_wait_bars":6,"max_hold_bars":48},
    "H4":{"trading_style":"SWING","label":"Swing Trade","max_wait_bars":4,"max_hold_bars":42},
    "D1":{"trading_style":"SWING","label":"Swing Trade","max_wait_bars":3,"max_hold_bars":30},
    "W1":{"trading_style":"POSITION","label":"Position","max_wait_bars":2,"max_hold_bars":26},
}


def normalize_execution_timeframe(value:Any,default:str="M15")->str:
    raw=str(value or "").strip().upper().replace(" ","")
    if raw in _ALIASES:
        return _ALIASES[raw]
    fallback=str(default or "M15").strip().upper()
    return fallback if fallback in SUPPORTED_EXECUTION_TIMEFRAMES else "M15"


def timeframe_profile(value:Any)->dict[str,Any]:
    tf=normalize_execution_timeframe(value)
    return {"timeframe":tf,**dict(_PROFILES[tf])}


def apply_timeframe_context(
    signals:Iterable[Mapping[str,Any]]|None,
    timeframe:Any,
    *,
    overwrite:bool=False,
)->list[dict[str,Any]]:
    selected=normalize_execution_timeframe(timeframe)
    rows=[]
    for raw in list(signals or []):
        row=dict(raw)
        current=str(row.get("timeframe") or "").strip()
        tf=selected if overwrite or not current else normalize_execution_timeframe(current,selected)
        profile=timeframe_profile(tf)
        row["timeframe"]=tf
        if overwrite or not str(row.get("trading_style") or "").strip():
            row["trading_style"]=profile["trading_style"]
        rows.append(row)
    return rows


__all__=[
    "SUPPORTED_EXECUTION_TIMEFRAMES",
    "normalize_execution_timeframe",
    "timeframe_profile",
    "apply_timeframe_context",
]
