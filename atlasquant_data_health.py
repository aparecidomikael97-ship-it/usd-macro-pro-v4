"""P0 market-data health aggregation for the canonical 28-pair FX scanner."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
import math
from atlasquant_instrument_registry import FX_28

@dataclass(frozen=True)
class DataHealth:
    symbol:str
    status:str
    age_minutes:float|None
    source:str
    execution_eligible:bool
    reason:str

def _stamp(value:Any)->datetime|None:
    try:
        if isinstance(value,(int,float)):
            d=datetime.fromtimestamp(float(value),tz=timezone.utc)
        else:
            d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
            d=d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
        return d
    except Exception:
        return None

def evaluate_pair_health(symbol:str, raw:Mapping[str,Any]|None, *, now:datetime|None=None,
                         max_age_minutes:float=60.0)->DataHealth:
    current=now or datetime.now(timezone.utc)
    current=current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current.astimezone(timezone.utc)
    row=dict(raw or {})
    try:
        max_age=float(max_age_minutes)
        if not math.isfinite(max_age) or max_age<=0: raise ValueError
    except Exception:
        return DataHealth(symbol,"INVALID",None,str(row.get("source","TWELVE_DATA")),False,"max_age_invalid")
    source=str(row.get("source","TWELVE_DATA"))
    stamp=_stamp(row.get("fetched_at",row.get("m15_fetched_at")))
    if stamp is None:
        return DataHealth(symbol,"MISSING",None,source,False,"timestamp_missing_or_invalid")
    age=(current-stamp).total_seconds()/60.0
    if age<0:
        return DataHealth(symbol,"INVALID",None,source,False,"timestamp_in_future")
    if bool(row.get("source_divergence",False)):
        return DataHealth(symbol,"DIVERGENT_SOURCE",age,source,False,"source_price_divergence")
    if bool(row.get("quality_ok",True)) is False:
        return DataHealth(symbol,"INVALID",age,source,False,"quality_rejected")
    if age>=max_age:
        return DataHealth(symbol,"STALE",age,source,False,"freshness_expired")
    return DataHealth(symbol,"PASS",age,source,True,"fresh_and_valid")

def fx28_health(rows:Mapping[str,Mapping[str,Any]]|None, *, now:datetime|None=None,
                max_age_minutes:float=60.0)->dict[str,Any]:
    src=dict(rows or {}); health={}
    for symbol in FX_28:
        health[symbol]=evaluate_pair_health(symbol,src.get(symbol),now=now,max_age_minutes=max_age_minutes)
    counts={k:sum(x.status==k for x in health.values()) for k in ("PASS","STALE","MISSING","INVALID","DIVERGENT_SOURCE")}
    eligible=sum(x.execution_eligible for x in health.values())
    return {
        "expected":28,"execution_eligible":eligible,"complete":eligible==28,
        "counts":counts,"pairs":health,
        "system_state":"NORMAL" if eligible==28 else ("DEGRADED" if eligible>0 else "PROTECTED"),
        "execution_expansion_enabled":False,
    }
