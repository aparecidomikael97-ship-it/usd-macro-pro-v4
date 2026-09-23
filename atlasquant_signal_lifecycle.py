"""AtlasQuant signal lifecycle and freshness.

Tracks when a directional reading is first observed, confirmed, blocked or
expired. This module is observational only: it does not create orders, change
gates, alter scores or promote strategies.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo
import math

import pandas as pd

from data_readiness_v1101 import TF_LIMITS

SCHEMA="ATLASQUANT_SIGNAL_LIFECYCLE_V1"
SIGNAL_LIFECYCLE_PATH="dados/atlasquant_signal_lifecycle_v1.json"
MAX_TRANSITIONS=500
M15_FRESH_MINUTES=float(TF_LIMITS["m15"]["fresh"])


def _safe_bool(value: Any)->bool:
    try:
        if value is None or pd.isna(value):
            return False
    except Exception:
        pass
    return bool(value)


def _side(pack: Mapping[str,Any])->str:
    raw=str(pack.get("side") or pack.get("direction") or "").upper()
    if "BUY" in raw or "COMPRA" in raw:
        return "BUY"
    if "SELL" in raw or "VENDA" in raw:
        return "SELL"
    return "WAIT"


def _timestamp(value: Any)->pd.Timestamp | None:
    if value in (None,"",0,0.0):
        return None
    try:
        if isinstance(value,(int,float)):
            if not math.isfinite(float(value)):
                return None
            ts=pd.Timestamp(float(value),unit="s",tz="UTC")
        else:
            ts=pd.to_datetime(value,utc=True,errors="coerce")
        if pd.isna(ts):
            return None
        return pd.Timestamp(ts).tz_convert("UTC")
    except Exception:
        return None


def _iso(value: Any)->str:
    ts=_timestamp(value)
    return "" if ts is None else ts.isoformat()


def _age_minutes(value: Any, now: Any = None)->float | None:
    ts=_timestamp(value)
    if ts is None:
        return None
    ref=_timestamp(now) if now is not None else pd.Timestamp.now(tz="UTC")
    if ref is None:
        ref=pd.Timestamp.now(tz="UTC")
    age=(ref-ts).total_seconds()/60.0
    if age < -1.0:
        return None
    return max(0.0,float(age))


def format_signal_time(value: Any, timezone: str = "UTC")->str:
    ts=_timestamp(value)
    if ts is None:
        return "horário não comprovado"
    try:
        zone=ZoneInfo(str(timezone or "UTC"))
    except Exception:
        zone=ZoneInfo("UTC")
        timezone="UTC"
    local=ts.tz_convert(zone)
    label=str(timezone or "UTC")
    return f"{local.strftime('%d/%m/%Y %H:%M')} {label}"


def _technical_reference(pack: Mapping[str,Any])->tuple[str,str]:
    candidates=(
        ("m15_fetched_at",pack.get("technical_timestamp")),
        ("m15_fetched_at",pack.get("m15_fetched_at")),
        ("processado_em",pack.get("scanner_processed_at")),
        ("market_map_updated_at",pack.get("updated_at")),
    )
    for source,value in candidates:
        iso=_iso(value)
        if iso:
            return iso,source
    return "","UNPROVEN"


def _mapping(value:Any)->dict[str,Any]:
    return dict(value) if isinstance(value,Mapping) else {}


def derive_signal_view(
    pack: Mapping[str,Any],
    *,
    now: Any = None,
    timezone: str = "UTC",
)->dict[str,Any]:
    """Classify the current reading without inventing an entry signal."""
    p=_mapping(pack)
    ref,ref_source=_technical_reference(p)
    age=_age_minutes(ref,now)
    side=_side(p)
    state=str(p.get("state") or "").upper()
    data=_mapping(p.get("data_ready"))
    timeframes=_mapping(data.get("timeframes"))
    m15=_mapping(timeframes.get("m15"))
    stale=bool(p.get("stale_technical")) or (age is not None and age > M15_FRESH_MINUTES)
    if m15 and not bool(m15.get("fresh",False)):
        stale=True

    blocked=(
        state.startswith("🔴")
        or "BLOQUE" in state
        or bool(list(p.get("hard_blocks",[]) or []))
    )
    executable=_safe_bool(p.get("executable")) and _safe_bool(data.get("sufficient"))

    if side=="WAIT":
        code="NO_SIGNAL"
        label="SEM SINAL / AGUARDAR"
    elif not ref or age is None:
        code="UNVERIFIED"
        label="SEM HORÁRIO COMPROVADO — NÃO ENTRAR"
    elif stale:
        code="EXPIRED"
        label="EXPIRADA — REVALIDAR"
    elif blocked:
        code="BLOCKED"
        label="BLOQUEADA — NÃO ENTRAR"
    elif executable:
        code="CONFIRMED"
        label="CONFIRMADA"
    else:
        code="POSSIBLE"
        label="POSSÍVEL — AGUARDANDO GATILHO"

    valid_until=""
    remaining=None
    if ref:
        ts=_timestamp(ref)
        if ts is not None:
            valid_until=(ts+pd.Timedelta(minutes=M15_FRESH_MINUTES)).isoformat()
            if age is not None:
                remaining=max(0.0,M15_FRESH_MINUTES-age)

    action=("COMPRA" if side=="BUY" else "VENDA" if side=="SELL" else "AGUARDAR")
    return {
        "schema":SCHEMA,
        "status_code":code,
        "status_label":label,
        "side":side,
        "action":action,
        "reference_at":ref,
        "reference_source":ref_source,
        "reference_display":format_signal_time(ref,timezone),
        "age_minutes":None if age is None else round(age,1),
        "valid_until":valid_until,
        "valid_until_display":format_signal_time(valid_until,timezone) if valid_until else "—",
        "remaining_minutes":None if remaining is None else round(remaining,1),
        "timezone":str(timezone or "UTC"),
        "m15_fresh_limit_minutes":M15_FRESH_MINUTES,
        "requires_revalidation":code in {"EXPIRED","UNVERIFIED","BLOCKED"},
        "is_current_confirmation":code=="CONFIRMED",
        "is_possible":code=="POSSIBLE",
        "automatic_execution":False,
        "real_orders_enabled":False,
    }


def _now_iso(now: Any = None)->str:
    ref=_timestamp(now)
    if ref is None:
        ref=pd.Timestamp.now(tz="UTC")
    return ref.isoformat()


def advance_signal_lifecycle(
    previous: Mapping[str,Any] | None,
    packs: Sequence[Mapping[str,Any]] | None,
    *,
    now: Any = None,
)->dict[str,Any]:
    """Persist state transitions so confirmation time is auditable from now on."""
    now_iso=_now_iso(now)
    prior=dict(previous or {})
    prior_pairs=dict(prior.get("pairs",{}) or {})
    pairs={}
    transitions=list(prior.get("transitions",[]) or [])

    for raw in list(packs or []):
        if not isinstance(raw,Mapping):
            continue
        p=dict(raw)
        pair=str(p.get("pair") or "").strip()
        if not pair:
            continue
        view=derive_signal_view(p,now=now,timezone="UTC")
        prev=dict(prior_pairs.get(pair,{}) or {})
        side=view["side"]
        prev_side=str(prev.get("side") or "WAIT")
        prev_code=str(prev.get("status_code") or "NO_SIGNAL")
        generation=int(prev.get("generation",0) or 0)

        direction_changed=side!=prev_side
        if direction_changed:
            generation+=1
            observed_at=now_iso if side in {"BUY","SELL"} else ""
            confirmed_at=""
            expired_at=""
            blocked_at=""
        else:
            observed_at=str(prev.get("observed_at") or "")
            confirmed_at=str(prev.get("confirmed_at") or "")
            expired_at=str(prev.get("expired_at") or "")
            blocked_at=str(prev.get("blocked_at") or "")
            if not observed_at and side in {"BUY","SELL"}:
                observed_at=now_iso

        code=view["status_code"]
        if code=="CONFIRMED" and (direction_changed or prev_code!="CONFIRMED" or not confirmed_at):
            confirmed_at=now_iso
        if code=="EXPIRED" and (direction_changed or prev_code!="EXPIRED" or not expired_at):
            expired_at=now_iso
        if code=="BLOCKED" and (direction_changed or prev_code!="BLOCKED" or not blocked_at):
            blocked_at=now_iso

        row={
            **view,
            "pair":pair,
            "generation":generation,
            "observed_at":observed_at,
            "confirmed_at":confirmed_at,
            "expired_at":expired_at,
            "blocked_at":blocked_at,
            "last_seen_at":now_iso,
            "previous_status_code":prev_code,
            "previous_side":prev_side,
        }
        pairs[pair]=row

        if direction_changed or code!=prev_code:
            transitions.append({
                "pair":pair,
                "at":now_iso,
                "from_side":prev_side,
                "to_side":side,
                "from_status":prev_code,
                "to_status":code,
                "generation":generation,
                "reference_at":view["reference_at"],
            })

    return {
        "schema":SCHEMA,
        "updated_at":now_iso,
        "pairs":pairs,
        "transitions":transitions[-MAX_TRANSITIONS:],
        "real_orders_enabled":False,
        "automatic_execution":False,
        "automatic_promotion":False,
    }


def annotate_packs_with_lifecycle(
    packs: Sequence[Mapping[str,Any]] | None,
    lifecycle: Mapping[str,Any] | None = None,
    *,
    now: Any = None,
    timezone: str = "UTC",
)->list[dict[str,Any]]:
    """Attach current freshness plus persisted transition timestamps to packs."""
    states=dict((lifecycle or {}).get("pairs",{}) or {})
    out=[]
    for raw in list(packs or []):
        if not isinstance(raw,Mapping):
            continue
        p=dict(raw)
        pair=str(p.get("pair") or "")
        current=derive_signal_view(p,now=now,timezone=timezone)
        persisted=dict(states.get(pair,{}) or {})
        # Current evidence owns status/freshness. Persisted data only contributes
        # historical transition timestamps for the same side/generation.
        if str(persisted.get("side") or "")==current["side"]:
            for key in ("generation","observed_at","confirmed_at","expired_at","blocked_at","last_seen_at"):
                if persisted.get(key) not in (None,""):
                    current[key]=persisted.get(key)
        p["signal_lifecycle"]=current
        out.append(p)
    return out


__all__=[
    "SCHEMA","SIGNAL_LIFECYCLE_PATH","M15_FRESH_MINUTES",
    "derive_signal_view","advance_signal_lifecycle",
    "annotate_packs_with_lifecycle","format_signal_time",
]
