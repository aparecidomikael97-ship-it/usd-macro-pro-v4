"""Prospective live ledger for AtlasQuant economic nowcasts.

The ledger freezes one snapshot per target event per UTC capture day. After the
release, the first observed actual value closes the snapshot; later revisions
never rewrite the original forecast or its first observed outcome.

No provider I/O lives here. The runtime runner supplies raw economic events.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from typing import Any, Iterable, Mapping

import pandas as pd

from atlasquant_news_nowcast import (
    HistoricalRelease,
    build_empirical_nowcast_from_score,
    classify_surprise,
    combine_leading_signals,
    validate_historical_release,
)
from atlasquant_nowcast_antecedents import (
    build_target_antecedents,
    normalize_economic_events,
    upcoming_targets,
)

SCHEMA="ATLASQUANT_LIVE_NOWCAST_V1"
LEDGER_COLUMNS=[
    "forecast_id","event_id","indicator","event_name","comparison","period",
    "scheduled_at","scheduled_raw_date","scheduled_timezone_known",
    "captured_at","capture_day","consensus","previous","tolerance","unit",
    "signal_score","signal_count","signals_json","missing_signals",
    "weights_calibrated","weight_policy","nowcast_state","estimate",
    "p_below","p_inline","p_above","top_class","historical_samples",
    "analog_samples","analog_method","actual","actual_seen_at",
    "surprise_class","closed","provider","lookahead_used",
    "market_reaction_predicted","automatic_execution",
]


def _utc(value:Any)->datetime:
    if isinstance(value,datetime):
        dt=value
    else:
        text=str(value or "")
        if text.endswith("Z"):
            text=text[:-1]+"+00:00"
        dt=datetime.fromisoformat(text)
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _finite(value:Any)->float|None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _forecast_id(event_id:str,capture_day:str)->str:
    return sha256(f"{event_id}|{capture_day}".encode("utf-8")).hexdigest()[:24]


def normalize_live_ledger(frame:pd.DataFrame|None)->pd.DataFrame:
    if not isinstance(frame,pd.DataFrame) or frame.empty:
        return pd.DataFrame(columns=LEDGER_COLUMNS)
    out=frame.copy()
    for col in LEDGER_COLUMNS:
        if col not in out.columns:
            out[col]=None
    return out[LEDGER_COLUMNS].copy()


def _bool(value:Any)->bool:
    if isinstance(value,bool):
        return value
    return str(value or "").strip().casefold() in {"1","true","yes","sim","on"}


def _history_from_closed(frame:pd.DataFrame)->list[HistoricalRelease]:
    d=normalize_live_ledger(frame)
    if d.empty:
        return []
    d=d[
        d["closed"].map(_bool)
        & pd.to_numeric(d["actual"],errors="coerce").notna()
        & pd.to_numeric(d["signal_score"],errors="coerce").notna()
        & pd.to_numeric(d["consensus"],errors="coerce").notna()
    ].copy()
    if d.empty:
        return []

    d["_captured"]=pd.to_datetime(d["captured_at"],utc=True,errors="coerce")
    d=d.dropna(subset=["_captured"])
    # One historical observation per actual release: use the latest safe
    # pre-release snapshot, never all daily snapshots as independent samples.
    d=d.sort_values("_captured").groupby("event_id",as_index=False).tail(1)

    rows=[]
    for _,row in d.iterrows():
        try:
            rows.append(validate_historical_release(HistoricalRelease(
                indicator=str(row.get("indicator") or ""),
                scheduled_at=_utc(row.get("scheduled_at")),
                captured_at=_utc(row.get("captured_at")),
                consensus=float(row.get("consensus")),
                actual=float(row.get("actual")),
                signal_score=float(row.get("signal_score")),
                tolerance=float(row.get("tolerance") or 0.0),
                unit=str(row.get("unit") or ""),
            )))
        except Exception:
            continue
    return rows


def completed_history(frame:pd.DataFrame|None)->list[HistoricalRelease]:
    return _history_from_closed(normalize_live_ledger(frame))


def _close_existing(
    ledger:pd.DataFrame,
    events,
    *,
    now:datetime,
)->tuple[pd.DataFrame,int]:
    if ledger.empty:
        return ledger,0
    by_id={event.event_id:event for event in events if event.actual is not None}
    out=ledger.copy()
    closed_count=0
    for idx,row in out.iterrows():
        if _bool(row.get("closed")):
            continue
        event=by_id.get(str(row.get("event_id") or ""))
        if event is None or event.actual is None:
            continue
        consensus=_finite(row.get("consensus"))
        tolerance=_finite(row.get("tolerance")) or 0.0
        if consensus is None:
            continue
        # Freeze the first actual observed by the runtime. Do not rewrite it
        # later when a provider revises a release.
        out.at[idx,"actual"]=float(event.actual)
        out.at[idx,"actual_seen_at"]=now.isoformat()
        out.at[idx,"surprise_class"]=classify_surprise(
            event.actual,consensus,tolerance
        )
        out.at[idx,"closed"]=True
        closed_count+=1
    return normalize_live_ledger(out),closed_count


def summarize_live_nowcasts(frame:pd.DataFrame|None)->dict[str,Any]:
    d=normalize_live_ledger(frame)
    if d.empty:
        return {
            "schema":SCHEMA,"snapshots":0,"events":0,"closed_events":0,
            "with_signals":0,"with_empirical_distribution":0,
            "by_indicator":{},"lookahead_used":False,
            "automatic_execution":False,
        }
    by_indicator={}
    for indicator,g in d.groupby(d["indicator"].fillna("").astype(str)):
        key=str(indicator).strip()
        if not key:
            continue
        by_indicator[key]={
            "snapshots":int(len(g)),
            "events":int(g["event_id"].fillna("").astype(str).nunique()),
            "closed_events":int(g[g["closed"].map(_bool)]["event_id"].fillna("").astype(str).nunique()),
            "with_signals":int(pd.to_numeric(g["signal_score"],errors="coerce").notna().sum()),
            "research_estimates":int(g["nowcast_state"].astype(str).eq("RESEARCH_ESTIMATE").sum()),
        }
    return {
        "schema":SCHEMA,
        "snapshots":int(len(d)),
        "events":int(d["event_id"].fillna("").astype(str).nunique()),
        "closed_events":int(d[d["closed"].map(_bool)]["event_id"].fillna("").astype(str).nunique()),
        "with_signals":int(pd.to_numeric(d["signal_score"],errors="coerce").notna().sum()),
        "with_empirical_distribution":int(d["nowcast_state"].astype(str).eq("RESEARCH_ESTIMATE").sum()),
        "by_indicator":by_indicator,
        "lookahead_used":False,
        "market_reaction_scored":False,
        "automatic_execution":False,
        "automatic_weight_change":False,
    }


def sync_live_nowcasts(
    raw_events:Iterable[Mapping[str,Any]]|None,
    existing:pd.DataFrame|None=None,
    *,
    now:datetime|None=None,
    horizon_days:int=7,
    min_history:int=40,
    min_analogs:int=20,
    bandwidth:float=0.25,
)->tuple[pd.DataFrame,dict[str,Any]]:
    capture=_utc(now or datetime.now(timezone.utc))
    events=normalize_economic_events(raw_events)
    ledger=normalize_live_ledger(existing)
    ledger,closed_now=_close_existing(ledger,events,now=capture)
    history=_history_from_closed(ledger)

    existing_ids=set(ledger["forecast_id"].fillna("").astype(str)) if not ledger.empty else set()
    created=0
    no_signal=0
    with_distribution=0

    for event,rule in upcoming_targets(
        events,captured_at=capture,horizon_days=horizon_days
    ):
        capture_day=capture.date().isoformat()
        forecast_id=_forecast_id(event.event_id,capture_day)
        if forecast_id in existing_ids:
            continue

        antecedents=build_target_antecedents(
            rule.key,events,captured_at=capture
        )
        signals=list(antecedents.get("signals",[]) or [])
        combined=combine_leading_signals(signals,captured_at=capture)
        signal_score=combined.get("signal_score")

        if combined.get("state")=="READY" and signal_score is not None:
            empirical=build_empirical_nowcast_from_score(
                indicator=rule.key,
                consensus=event.estimate,
                captured_at=capture,
                signal_score=signal_score,
                history=history,
                min_history=min_history,
                min_analogs=min_analogs,
                bandwidth=bandwidth,
            )
        else:
            empirical={
                "state":"INSUFFICIENT_SIGNALS",
                "estimate":None,
                "probabilities":None,
                "top_class":None,
                "historical_samples":len([
                    x for x in history if x.indicator==rule.key
                ]),
                "analog_samples":0,
                "analog_method":None,
            }
            no_signal+=1

        probabilities=dict(empirical.get("probabilities") or {})
        if empirical.get("state")=="RESEARCH_ESTIMATE":
            with_distribution+=1

        row={
            "forecast_id":forecast_id,
            "event_id":event.event_id,
            "indicator":rule.key,
            "event_name":event.name,
            "comparison":event.comparison,
            "period":event.period,
            "scheduled_at":event.scheduled_at.isoformat(),
            "scheduled_raw_date":event.raw_date,
            "scheduled_timezone_known":event.timezone_known,
            "captured_at":capture.isoformat(),
            "capture_day":capture_day,
            "consensus":event.estimate,
            "previous":event.previous,
            "tolerance":rule.tolerance,
            "unit":rule.unit,
            "signal_score":signal_score,
            "signal_count":len(signals),
            "signals_json":json.dumps(
                antecedents.get("provenance",[]),
                ensure_ascii=False,sort_keys=True,default=str,
            ),
            "missing_signals":" | ".join(
                str(x) for x in antecedents.get("missing",[])
            ),
            "weights_calibrated":False,
            "weight_policy":antecedents.get("weight_policy",""),
            "nowcast_state":empirical.get("state"),
            "estimate":empirical.get("estimate"),
            "p_below":probabilities.get("BELOW"),
            "p_inline":probabilities.get("INLINE"),
            "p_above":probabilities.get("ABOVE"),
            "top_class":empirical.get("top_class"),
            "historical_samples":empirical.get("historical_samples",0),
            "analog_samples":empirical.get("analog_samples",0),
            "analog_method":empirical.get("analog_method"),
            "actual":None,
            "actual_seen_at":None,
            "surprise_class":None,
            "closed":False,
            "provider":"EODHD Economic Events",
            "lookahead_used":False,
            "market_reaction_predicted":False,
            "automatic_execution":False,
        }
        ledger=pd.concat([ledger,pd.DataFrame([row])],ignore_index=True)
        existing_ids.add(forecast_id)
        created+=1

    ledger=normalize_live_ledger(ledger)
    if not ledger.empty:
        ledger["_capture_sort"]=pd.to_datetime(
            ledger["captured_at"],utc=True,errors="coerce"
        )
        ledger=ledger.sort_values(
            ["_capture_sort","indicator","event_id"],
            na_position="last",
        ).drop(columns=["_capture_sort"]).reset_index(drop=True)

    summary=summarize_live_nowcasts(ledger)
    cycle={
        **summary,
        "captured_at":capture.isoformat(),
        "provider_events":len(events),
        "new_snapshots":created,
        "closed_now":closed_now,
        "new_without_signals":no_signal,
        "new_with_empirical_distribution":with_distribution,
        "historical_releases_available":len(history),
        "same_day_naive_targets_allowed":False,
        "provider_timezone_policy":"FAIL_CLOSED_SAME_DAY_WHEN_UNDOCUMENTED",
    }
    return ledger,cycle


__all__=[
    "SCHEMA","LEDGER_COLUMNS","normalize_live_ledger","completed_history",
    "summarize_live_nowcasts","sync_live_nowcasts",
]
