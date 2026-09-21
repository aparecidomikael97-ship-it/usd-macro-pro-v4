"""AtlasQuant live antecedent builder for economic nowcasts.

Transforms *already released* economic events into point-in-time LeadingSignal
objects. The initial weights/scales are transparent research heuristics and are
never changed automatically from performance.

EODHD's Economic Events schema documents a date/time string but does not
document a timezone. Therefore naive provider timestamps are treated
conservatively:
- an antecedent is usable only when its calendar date is strictly before the
  capture date;
- a target with a naive timestamp is capturable only before its calendar date;
- same-day naive timestamps are not used to claim pre-release timing.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math
import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence

from atlasquant_news_nowcast import LeadingSignal

SCHEMA="ATLASQUANT_LIVE_ANTECEDENTS_V1"


def _norm(value:Any)->str:
    text=unicodedata.normalize("NFKD",str(value or "")).encode("ascii","ignore").decode("ascii")
    text=text.casefold().replace("-"," ")
    return re.sub(r"\s+"," ",text).strip()


def _finite(value:Any)->float|None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _aware(value:datetime)->datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@dataclass(frozen=True)
class NormalizedEconomicEvent:
    event_id:str
    name:str
    comparison:str
    period:str
    country:str
    raw_date:str
    scheduled_at:datetime
    timezone_known:bool
    actual:float|None
    previous:float|None
    estimate:float|None
    source:str="EODHD Economic Events"


@dataclass(frozen=True)
class AntecedentRule:
    key:str
    aliases:tuple[str,...]
    weight:float
    surprise_scale:float
    polarity:int=1
    max_age_days:int=75


@dataclass(frozen=True)
class TargetRule:
    key:str
    aliases:tuple[str,...]
    comparison:str|None
    exclude:tuple[str,...]
    tolerance:float
    unit:str
    antecedents:tuple[AntecedentRule,...]


PAYROLL_ANTECEDENTS=(
    AntecedentRule(
        "ADP",
        ("adp employment change","adp nonfarm employment change","adp employment"),
        1.00,75.0,+1,45,
    ),
    AntecedentRule(
        "INITIAL_CLAIMS",
        ("initial jobless claims","initial unemployment claims","initial claims"),
        0.85,25.0,-1,35,
    ),
    AntecedentRule(
        "ISM_MFG_EMPLOYMENT",
        ("ism manufacturing employment","ism manufacturing employment index"),
        0.65,2.0,+1,45,
    ),
    AntecedentRule(
        "ISM_SERVICES_EMPLOYMENT",
        (
            "ism services employment",
            "ism non manufacturing employment",
            "ism nonmanufacturing employment",
        ),
        0.80,2.0,+1,45,
    ),
)

CPI_ANTECEDENTS=(
    AntecedentRule(
        "PPI",
        ("producer price inflation","producer price index","ppi"),
        0.70,0.25,+1,45,
    ),
    AntecedentRule(
        "CORE_PPI",
        ("core producer prices","core producer price index","core ppi"),
        0.85,0.25,+1,45,
    ),
    AntecedentRule(
        "IMPORT_PRICES",
        ("import prices","import price index"),
        0.45,0.35,+1,45,
    ),
)

PCE_ANTECEDENTS=(
    AntecedentRule(
        "CPI",
        ("inflation rate","consumer price index","cpi"),
        0.75,0.20,+1,50,
    ),
    AntecedentRule(
        "CORE_CPI",
        ("core inflation rate","core consumer price index","core cpi"),
        1.00,0.20,+1,50,
    ),
    AntecedentRule(
        "PPI",
        ("producer price inflation","producer price index","ppi"),
        0.45,0.25,+1,50,
    ),
    AntecedentRule(
        "CORE_PPI",
        ("core producer prices","core producer price index","core ppi"),
        0.60,0.25,+1,50,
    ),
)

TARGET_RULES:tuple[TargetRule,...]=(
    TargetRule(
        "PAYROLL",
        ("nonfarm payrolls","non farm payrolls","nonfarm payroll","employment situation"),
        None,(),5.0,"k",PAYROLL_ANTECEDENTS,
    ),
    TargetRule(
        "CORE_CPI",
        ("core inflation rate","core consumer price index","core cpi"),
        "yoy",(),0.05,"%",tuple(x for x in CPI_ANTECEDENTS if x.key!="PPI"),
    ),
    TargetRule(
        "CPI",
        ("inflation rate","consumer price index","cpi"),
        "yoy",("core",),0.05,"%",CPI_ANTECEDENTS,
    ),
    TargetRule(
        "CORE_PCE",
        ("core pce price index","core pce prices","core personal consumption expenditures"),
        "yoy",(),0.05,"%",PCE_ANTECEDENTS,
    ),
    TargetRule(
        "PCE",
        ("pce price index","pce prices","personal consumption expenditures price index"),
        "yoy",("core",),0.05,"%",PCE_ANTECEDENTS,
    ),
)


def _event_id(payload:Mapping[str,Any])->str:
    raw=json.dumps(dict(payload),sort_keys=True,ensure_ascii=False,separators=(",",":"),default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:24]


def normalize_economic_event(raw:Mapping[str,Any]|None)->NormalizedEconomicEvent|None:
    if not isinstance(raw,Mapping):
        return None
    name=str(raw.get("type") or raw.get("event") or "").strip()
    raw_date=str(raw.get("date") or "").strip()
    if not name or not raw_date:
        return None
    try:
        parsed=datetime.fromisoformat(raw_date.replace("Z","+00:00"))
    except Exception:
        return None
    timezone_known=parsed.tzinfo is not None
    scheduled=_aware(parsed)
    comparison=_norm(raw.get("comparison"))
    period=str(raw.get("period") or "").strip()
    country=str(raw.get("country") or "").strip().upper()
    identity={
        "name":_norm(name),
        "comparison":comparison,
        "period":period,
        "country":country,
        "raw_date":raw_date,
    }
    return NormalizedEconomicEvent(
        event_id=_event_id(identity),
        name=name,
        comparison=comparison,
        period=period,
        country=country,
        raw_date=raw_date,
        scheduled_at=scheduled,
        timezone_known=timezone_known,
        actual=_finite(raw.get("actual")),
        previous=_finite(raw.get("previous")),
        estimate=_finite(raw.get("estimate")),
    )


def normalize_economic_events(rows:Iterable[Mapping[str,Any]]|None)->list[NormalizedEconomicEvent]:
    out=[]
    seen=set()
    for raw in rows or []:
        event=normalize_economic_event(raw)
        if event is None or event.event_id in seen:
            continue
        seen.add(event.event_id)
        out.append(event)
    return sorted(out,key=lambda x:(x.scheduled_at,x.event_id))


def _matches(name:str,aliases:Sequence[str],exclude:Sequence[str]=())->bool:
    text=_norm(name)
    if any(_norm(x) in text for x in exclude):
        return False
    return any(_norm(alias) in text for alias in aliases)


def target_rule_for_event(event:NormalizedEconomicEvent)->TargetRule|None:
    for rule in TARGET_RULES:
        if not _matches(event.name,rule.aliases,rule.exclude):
            continue
        if rule.comparison and _norm(event.comparison)!=_norm(rule.comparison):
            continue
        return rule
    return None


def target_rule(key:Any)->TargetRule|None:
    wanted=str(key or "").strip().upper()
    return next((rule for rule in TARGET_RULES if rule.key==wanted),None)


def definitely_before_capture(event:NormalizedEconomicEvent,captured_at:datetime)->bool:
    capture=_aware(captured_at)
    if event.timezone_known:
        return event.scheduled_at < capture
    # Provider timezone is undocumented. Same-day use could accidentally include
    # a release that has not happened yet or had just happened after capture.
    return event.scheduled_at.date() < capture.date()


def definitely_future_target(event:NormalizedEconomicEvent,captured_at:datetime)->bool:
    capture=_aware(captured_at)
    if event.timezone_known:
        return event.scheduled_at > capture
    return event.scheduled_at.date() > capture.date()


def upcoming_targets(
    events:Sequence[NormalizedEconomicEvent],
    *,
    captured_at:datetime,
    horizon_days:int=14,
)->list[tuple[NormalizedEconomicEvent,TargetRule]]:
    capture=_aware(captured_at)
    horizon=max(1,int(horizon_days))
    out=[]
    for event in events:
        rule=target_rule_for_event(event)
        if rule is None or event.estimate is None or event.actual is not None:
            continue
        if not definitely_future_target(event,capture):
            continue
        days=(event.scheduled_at.date()-capture.date()).days
        if 0<days<=horizon:
            out.append((event,rule))
    return sorted(out,key=lambda x:x[0].scheduled_at)


def _latest_rule_event(
    events:Sequence[NormalizedEconomicEvent],
    rule:AntecedentRule,
    *,
    captured_at:datetime,
)->NormalizedEconomicEvent|None:
    capture=_aware(captured_at)
    candidates=[]
    for event in events:
        if event.actual is None or event.estimate is None:
            continue
        if not _matches(event.name,rule.aliases):
            continue
        if not definitely_before_capture(event,capture):
            continue
        age=(capture.date()-event.scheduled_at.date()).days
        if age<0 or age>rule.max_age_days:
            continue
        candidates.append(event)
    return max(candidates,key=lambda x:x.scheduled_at) if candidates else None


def event_surprise_signal(
    event:NormalizedEconomicEvent,
    rule:AntecedentRule,
    *,
    captured_at:datetime,
)->LeadingSignal:
    if not definitely_before_capture(event,captured_at):
        raise ValueError("antecedente não estava definitivamente disponível no snapshot")
    if event.actual is None or event.estimate is None:
        raise ValueError("antecedente precisa de actual e estimate")
    if rule.surprise_scale<=0 or rule.weight<=0 or rule.polarity not in (-1,1):
        raise ValueError("regra antecedente inválida")
    raw=(event.actual-event.estimate)/rule.surprise_scale
    score=max(-1.0,min(1.0,raw))*rule.polarity
    # For naive provider times, record noon UTC only as a serialization anchor.
    # The eligibility decision above relies on calendar-day separation.
    observed_at=event.scheduled_at
    return LeadingSignal(
        name=rule.key,
        observed_at=observed_at,
        direction_score=round(float(score),6),
        weight=float(rule.weight),
        source=event.source,
        detail=(
            f"{event.name}: atual {event.actual:g} vs consenso {event.estimate:g}; "
            f"escala research {rule.surprise_scale:g}; timezone "
            f"{'confirmado' if event.timezone_known else 'não documentado pelo provider'}."
        ),
    )


def build_target_antecedents(
    target_key:Any,
    events:Sequence[NormalizedEconomicEvent],
    *,
    captured_at:datetime,
)->dict[str,Any]:
    rule=target_rule(target_key)
    capture=_aware(captured_at)
    if rule is None:
        return {
            "schema":SCHEMA,"target":str(target_key or ""),"state":"UNSUPPORTED_TARGET",
            "signals":[],"signal_count":0,"captured_at":capture.isoformat(),
            "weights_calibrated":False,"lookahead_used":False,
        }
    signals=[]
    missing=[]
    provenance=[]
    for antecedent in rule.antecedents:
        event=_latest_rule_event(events,antecedent,captured_at=capture)
        if event is None:
            missing.append(antecedent.key)
            continue
        signal=event_surprise_signal(event,antecedent,captured_at=capture)
        signals.append(signal)
        provenance.append({
            "key":antecedent.key,
            "event_id":event.event_id,
            "event":event.name,
            "raw_date":event.raw_date,
            "timezone_known":event.timezone_known,
            "actual":event.actual,
            "estimate":event.estimate,
            "direction_score":signal.direction_score,
            "weight":signal.weight,
        })
    return {
        "schema":SCHEMA,
        "target":rule.key,
        "state":"READY" if signals else "INSUFFICIENT_SIGNALS",
        "signals":signals,
        "signal_count":len(signals),
        "missing":missing,
        "provenance":provenance,
        "captured_at":capture.isoformat(),
        "weights_calibrated":False,
        "weight_policy":"TRANSPARENT_RESEARCH_HEURISTIC_V1",
        "automatic_weight_change":False,
        "lookahead_used":False,
        "interpretation":(
            "Os antecedentes usam surpresa real vs consenso já publicado. Pesos e escalas "
            "são hipóteses transparentes para pesquisa; precisam de calibração histórica "
            "antes de qualquer influência operacional."
        ),
    }


def target_catalog()->list[dict[str,Any]]:
    return [{
        "target":rule.key,
        "tolerance":rule.tolerance,
        "unit":rule.unit,
        "antecedents":[x.key for x in rule.antecedents],
    } for rule in TARGET_RULES]


__all__=[
    "SCHEMA","NormalizedEconomicEvent","AntecedentRule","TargetRule",
    "TARGET_RULES","normalize_economic_event","normalize_economic_events",
    "target_rule_for_event","target_rule","definitely_before_capture",
    "definitely_future_target","upcoming_targets","event_surprise_signal",
    "build_target_antecedents","target_catalog",
]
