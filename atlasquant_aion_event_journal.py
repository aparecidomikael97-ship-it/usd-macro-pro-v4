"""Persistent background journal for AION Live Event Intelligence.

This module extends the existing read-only live-event radar with auditable
runtime history. It never classifies news independently, fetches providers,
sends notifications, changes trading scores or places orders.

A 24h monitoring claim is fail-closed: it requires enough persisted Autopilot
heartbeats covering roughly one day with no large gap.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA="ATLASQUANT_AION_EVENT_JOURNAL_V1"
MAX_EVENTS=500
MAX_HEARTBEATS=120
MAX_DELIVERY_CANDIDATES=200

_ALERT_RANK={"NONE":0,"WATCH":1,"HIGH_REVIEW":2,"URGENT_REVIEW":3}


def _clean(value:Any,limit:int=800)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _finite(value:Any)->float|None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _utc(value:Any)->datetime|None:
    text=_clean(value,160)
    if not text:
        return None
    try:
        dt=datetime.fromisoformat(text.replace("Z","+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _event_id(raw:Mapping[str,Any])->str:
    eid=_clean(raw.get("event_id"),100)
    if eid:
        return eid
    seed="|".join((
        _clean(raw.get("headline"),500),
        _clean(raw.get("reported_at"),120),
        _clean(raw.get("kind"),80),
    ))
    return "EVT-"+sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def compact_event(raw:Mapping[str,Any],*,observed_at:Any="")->dict[str,Any]:
    item=dict(raw or {})
    stamp=_clean(observed_at,120)
    alert=_clean(item.get("alert_level"),40).upper() or "NONE"
    if alert not in _ALERT_RANK:
        alert="NONE"
    truth=_clean(item.get("truth_state"),40).upper() or "UNKNOWN"
    if truth not in {"CONFIRMED","INFERENCE","HYPOTHESIS","UNKNOWN"}:
        truth="UNKNOWN"
    sources=[_clean(x,180) for x in list(item.get("sources") or [])[:12] if _clean(x,180)]
    currencies=[_clean(x,20).upper() for x in list(item.get("currencies") or [])[:12] if _clean(x,20)]
    urgency=max(0,min(100,int(_finite(item.get("urgency_score")) or 0)))
    return {
        "schema":SCHEMA,
        "event_id":_event_id(item),
        "kind":_clean(item.get("kind"),80),
        "category":_clean(item.get("category"),100),
        "headline":_clean(item.get("headline"),600),
        "reported_at":_clean(item.get("reported_at"),120),
        "truth_state":truth,
        "truth_note":_clean(item.get("truth_note"),700),
        "sources":sources,
        "source_count":max(len(sources),int(_finite(item.get("source_count")) or 0)),
        "currencies":currencies,
        "urgency_score":urgency,
        "peak_urgency_score":urgency,
        "alert_level":alert,
        "peak_alert_level":alert,
        "impact_truth_state":_clean(item.get("impact_truth_state"),40).upper() or "HYPOTHESIS",
        "first_seen_at":stamp,
        "last_seen_at":stamp,
        "seen_count":1,
        "is_trade_signal":False,
        "automatic_notification_sent":False,
        "automatic_execution":False,
        "real_orders_enabled":False,
    }


def normalize_events(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[-MAX_EVENTS*2:]:
        if not isinstance(raw,Mapping):
            continue
        item=compact_event(raw,observed_at=raw.get("last_seen_at") or raw.get("first_seen_at"))
        item["first_seen_at"]=_clean(raw.get("first_seen_at"),120) or item["first_seen_at"]
        item["last_seen_at"]=_clean(raw.get("last_seen_at"),120) or item["last_seen_at"]
        item["seen_count"]=max(1,int(_finite(raw.get("seen_count")) or 1))
        item["peak_urgency_score"]=max(
            item["urgency_score"],
            int(_finite(raw.get("peak_urgency_score")) or 0),
        )
        peak=_clean(raw.get("peak_alert_level"),40).upper()
        if peak in _ALERT_RANK and _ALERT_RANK[peak]>=_ALERT_RANK[item["alert_level"]]:
            item["peak_alert_level"]=peak
        eid=item["event_id"]
        if eid in seen:
            continue
        seen.add(eid)
        out.append(item)
    return out[-MAX_EVENTS:]


def merge_events(
    existing:Sequence[Mapping[str,Any]]|None,
    incoming:Sequence[Mapping[str,Any]]|None,
    *,
    observed_at:Any,
)->list[dict[str,Any]]:
    stamp=_clean(observed_at,120)
    current={x["event_id"]:x for x in normalize_events(existing)}
    for raw in list(incoming or []):
        if not isinstance(raw,Mapping):
            continue
        item=compact_event(raw,observed_at=stamp)
        prior=current.get(item["event_id"])
        if prior:
            item["first_seen_at"]=prior.get("first_seen_at") or stamp
            item["seen_count"]=int(prior.get("seen_count") or 1)+1
            item["peak_urgency_score"]=max(
                int(prior.get("peak_urgency_score") or 0),
                item["urgency_score"],
            )
            prior_peak=_clean(prior.get("peak_alert_level"),40).upper()
            if _ALERT_RANK.get(prior_peak,0)>_ALERT_RANK.get(item["peak_alert_level"],0):
                item["peak_alert_level"]=prior_peak
        item["last_seen_at"]=stamp
        current[item["event_id"]]=item
    ordered=sorted(
        current.values(),
        key=lambda x:(_utc(x.get("last_seen_at")) or datetime.min.replace(tzinfo=timezone.utc)),
    )
    return ordered[-MAX_EVENTS:]


def compact_heartbeat(
    observed_at:Any,
    *,
    source_state:Any,
    event_count:Any,
    alert_count:Any,
)->dict[str,Any]:
    return {
        "observed_at":_clean(observed_at,120),
        "source_state":_clean(source_state,80).upper() or "UNKNOWN",
        "event_count":max(0,int(_finite(event_count) or 0)),
        "alert_count":max(0,int(_finite(alert_count) or 0)),
    }


def normalize_heartbeats(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[-MAX_HEARTBEATS*2:]:
        if not isinstance(raw,Mapping):
            continue
        stamp=_clean(raw.get("observed_at"),120)
        if not stamp or _utc(stamp) is None or stamp in seen:
            continue
        seen.add(stamp)
        out.append(compact_heartbeat(
            stamp,
            source_state=raw.get("source_state"),
            event_count=raw.get("event_count"),
            alert_count=raw.get("alert_count"),
        ))
    out.sort(key=lambda x:_utc(x["observed_at"]) or datetime.min.replace(tzinfo=timezone.utc))
    return out[-MAX_HEARTBEATS:]


def append_heartbeat(
    existing:Sequence[Mapping[str,Any]]|None,
    heartbeat:Mapping[str,Any],
)->list[dict[str,Any]]:
    rows=normalize_heartbeats(existing)
    item=compact_heartbeat(
        heartbeat.get("observed_at"),
        source_state=heartbeat.get("source_state"),
        event_count=heartbeat.get("event_count"),
        alert_count=heartbeat.get("alert_count"),
    )
    if _utc(item["observed_at"]) is None:
        return rows
    rows=[x for x in rows if x["observed_at"]!=item["observed_at"]]
    rows.append(item)
    return normalize_heartbeats(rows)


def continuity_summary(
    heartbeats:Sequence[Mapping[str,Any]]|None,
    *,
    now:datetime|None=None,
)->dict[str,Any]:
    rows=normalize_heartbeats(heartbeats)
    current=now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current=current.replace(tzinfo=timezone.utc)
    times=[_utc(x["observed_at"]) for x in rows]
    times=[x for x in times if x is not None]
    if not times:
        return {
            "state":"NOT_STARTED",
            "heartbeat_count":0,
            "coverage_minutes":0.0,
            "latest_age_minutes":None,
            "max_gap_minutes":None,
            "continuous_24h_confirmed":False,
        }
    latest=times[-1]
    oldest=times[0]
    coverage=max(0.0,(latest-oldest).total_seconds()/60.0)
    latest_age=max(0.0,(current-latest).total_seconds()/60.0)
    gaps=[
        max(0.0,(b-a).total_seconds()/60.0)
        for a,b in zip(times,times[1:])
    ]
    max_gap=max(gaps) if gaps else 0.0
    recent_24=[
        t for t in times
        if (current-t).total_seconds()<=24*3600+90*60
    ]
    confirmed=bool(
        coverage>=1380.0
        and len(recent_24)>=40
        and latest_age<=75.0
        and max_gap<=90.0
    )
    if confirmed:
        state="CONTINUOUS_24H"
    elif latest_age>90.0:
        state="STALE"
    else:
        state="BUILDING_EVIDENCE"
    return {
        "state":state,
        "heartbeat_count":len(rows),
        "recent_24h_heartbeats":len(recent_24),
        "coverage_minutes":round(coverage,2),
        "latest_age_minutes":round(latest_age,2),
        "max_gap_minutes":round(max_gap,2),
        "continuous_24h_confirmed":confirmed,
        "minimum_heartbeats_required":40,
        "maximum_gap_minutes_allowed":90.0,
        "minimum_coverage_minutes_required":1380.0,
    }


def internal_delivery_queue(snapshot:Mapping[str,Any]|None)->list[dict[str,Any]]:
    data=dict(snapshot or {})
    out=[]
    for event in list(data.get("top_alerts") or [])[:MAX_DELIVERY_CANDIDATES]:
        if not isinstance(event,Mapping):
            continue
        level=_clean(event.get("alert_level"),40).upper()
        if level not in {"WATCH","HIGH_REVIEW","URGENT_REVIEW"}:
            continue
        eid=_event_id(event)
        out.append({
            "delivery_id":"DLV-"+sha256((eid+"|"+level).encode("utf-8")).hexdigest()[:16].upper(),
            "event_id":eid,
            "alert_level":level,
            "headline":_clean(event.get("headline"),600),
            "truth_state":_clean(event.get("truth_state"),40).upper() or "UNKNOWN",
            "urgency_score":max(0,min(100,int(_finite(event.get("urgency_score")) or 0))),
            "state":"INTERNAL_ONLY",
            "requires_human_review":level in {"HIGH_REVIEW","URGENT_REVIEW"},
            "external_channel_connected":False,
            "external_delivery_allowed":False,
            "automatic_notification_sent":False,
            "market_action_authorized":False,
            "real_orders_enabled":False,
        })
    return out


def journal_digest(
    events:Sequence[Mapping[str,Any]]|None,
    heartbeats:Sequence[Mapping[str,Any]]|None,
)->str:
    payload={
        "events":normalize_events(events),
        "heartbeats":normalize_heartbeats(heartbeats),
    }
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:24]


def build_runtime_journal(
    previous:Mapping[str,Any]|None,
    live_snapshot:Mapping[str,Any]|None,
    *,
    observed_at:Any,
    now:datetime|None=None,
)->dict[str,Any]:
    prev=dict(previous or {})
    live=dict(live_snapshot or {})
    events=merge_events(
        prev.get("events") if isinstance(prev.get("events"),list) else [],
        live.get("events") if isinstance(live.get("events"),list) else [],
        observed_at=observed_at,
    )
    heartbeats=append_heartbeat(
        prev.get("heartbeats") if isinstance(prev.get("heartbeats"),list) else [],
        {
            "observed_at":observed_at,
            "source_state":live.get("news_source_state") or live.get("state"),
            "event_count":live.get("event_count"),
            "alert_count":live.get("alert_count"),
        },
    )
    continuity=continuity_summary(heartbeats,now=now)
    queue=internal_delivery_queue(live)
    return {
        "schema":SCHEMA,
        "updated_at":_clean(observed_at,120),
        "events":events,
        "heartbeats":heartbeats,
        "continuity":continuity,
        "delivery_queue":queue,
        "event_count":len(events),
        "delivery_candidate_count":len(queue),
        "digest":journal_digest(events,heartbeats),
        "performs_provider_request":False,
        "external_channel_connected":False,
        "external_delivery_allowed":False,
        "automatic_notification_sent":False,
        "market_action_authorized":False,
        "real_orders_enabled":False,
    }


def overlay_journal(
    live_snapshot:Mapping[str,Any]|None,
    journal:Mapping[str,Any]|None,
)->dict[str,Any]:
    live=dict(live_snapshot or {})
    data=dict(journal or {})
    continuity=(
        data.get("continuity")
        if isinstance(data.get("continuity"),Mapping)
        else {}
    )
    live["background_watch_state"]=_clean(continuity.get("state"),80).upper() or "UNKNOWN"
    live["background_heartbeat_count"]=int(_finite(continuity.get("heartbeat_count")) or 0)
    live["background_coverage_minutes"]=_finite(continuity.get("coverage_minutes"))
    live["background_latest_age_minutes"]=_finite(continuity.get("latest_age_minutes"))
    live["background_max_gap_minutes"]=_finite(continuity.get("max_gap_minutes"))
    live["continuous_runtime_confirmed"]=bool(
        continuity.get("continuous_24h_confirmed",False)
    )
    live["journal_event_count"]=int(_finite(data.get("event_count")) or 0)
    live["journal_events"]=[
        dict(x) for x in list(data.get("events") or [])[-MAX_EVENTS:]
        if isinstance(x,Mapping)
    ]
    live["delivery_queue"]=[
        dict(x) for x in list(data.get("delivery_queue") or [])[:MAX_DELIVERY_CANDIDATES]
        if isinstance(x,Mapping)
    ]
    live["delivery_candidate_count"]=int(_finite(data.get("delivery_candidate_count")) or 0)
    live["external_channel_connected"]=False
    live["external_delivery_allowed"]=False
    live["automatic_notification_sent"]=False
    live["real_orders_enabled"]=False
    return live


__all__=[
    "SCHEMA","MAX_EVENTS","MAX_HEARTBEATS",
    "compact_event","normalize_events","merge_events",
    "normalize_heartbeats","append_heartbeat","continuity_summary",
    "internal_delivery_queue","journal_digest","build_runtime_journal","overlay_journal",
]
