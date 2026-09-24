"""P0 adaptive scanner scheduling for the canonical 28-pair FX universe.

Planning only: produces deterministic active/background tiers and due work. It does
not perform HTTP requests and therefore cannot bypass Twelve Data's persistent budget.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from atlasquant_instrument_registry import FX_28, normalize_fx_symbol

@dataclass(frozen=True)
class ScanJob:
    symbol:str
    display_pair:str
    tier:str
    cadence_minutes:int
    due:bool
    age_minutes:float|None

def _age(value:Any, now:datetime)->float|None:
    if value in (None,"",0,0.0): return None
    try:
        if isinstance(value,(int,float)):
            ts=datetime.fromtimestamp(float(value),tz=timezone.utc)
        else:
            ts=datetime.fromisoformat(str(value).replace("Z","+00:00"))
            ts=ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts.astimezone(timezone.utc)
        age=(now-ts).total_seconds()/60.0
        return age if age>=0 else None
    except Exception:
        return None

def choose_active_pairs(strength_rows:Mapping[str,float]|None=None, *, active_count:int=3)->tuple[str,...]:
    scores={}
    for key,value in dict(strength_rows or {}).items():
        try:
            symbol=normalize_fx_symbol(key); score=float(value)
        except Exception:
            continue
        scores[symbol]=score
    ordered=sorted(FX_28,key=lambda s:(scores.get(s,float("-inf")),-FX_28.index(s)),reverse=True)
    n=max(0,min(int(active_count),len(FX_28)))
    return tuple(ordered[:n])

def build_scan_plan(last_fetches:Mapping[str,Any]|None=None, strength_rows:Mapping[str,float]|None=None,
                    *, now:datetime|None=None, active_count:int=3,
                    active_cadence_minutes:int=55, background_cadence_minutes:int=180)->list[ScanJob]:
    current=now or datetime.now(timezone.utc)
    active=set(choose_active_pairs(strength_rows,active_count=active_count))
    fetches=dict(last_fetches or {})
    jobs=[]
    for symbol in FX_28:
        display=f"{symbol[:3]}/{symbol[3:]}"
        raw=fetches.get(display,fetches.get(symbol,{})) or {}
        stamp=raw.get("m15") if isinstance(raw,Mapping) else raw
        age=_age(stamp,current)
        tier="HOT" if symbol in active else "BACKGROUND"
        cadence=int(active_cadence_minutes if tier=="HOT" else background_cadence_minutes)
        jobs.append(ScanJob(symbol,display,tier,cadence,age is None or age>=cadence,age))
    return sorted(jobs,key=lambda j:(not j.due,j.tier!="HOT",-(j.age_minutes if j.age_minutes is not None else 10**9),FX_28.index(j.symbol)))

def plan_summary(jobs:list[ScanJob])->dict[str,Any]:
    return {
        "universe":len(jobs),
        "hot":sum(j.tier=="HOT" for j in jobs),
        "background":sum(j.tier=="BACKGROUND" for j in jobs),
        "due":sum(j.due for j in jobs),
        "automatic_execution_enabled":False,
    }
