"""AION audit/observability primitives.

Pure/offline helpers that redact common secret patterns before events are kept
in the mutable Checkpoint Mestre. These events are operational evidence, not a
remote logging service.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import hashlib
import json
import re

SCHEMA="ATLASQUANT_AION_OBSERVABILITY_V1"
MAX_EVENTS=500
SEVERITIES=("INFO","NOTICE","WARNING","ERROR","CRITICAL")
TRUTH_STATES=("CONFIRMED","INFERENCE","HYPOTHESIS","UNKNOWN")

_SECRET_PATTERNS=(
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]{6,}"),
)


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def redact_text(value:Any)->str:
    text=str(value or "")
    for pattern in _SECRET_PATTERNS:
        text=pattern.sub("[REDACTED]",text)
    return text[:4000]


def _severity(value:Any)->str:
    item=str(value or "INFO").strip().upper()
    return item if item in SEVERITIES else "INFO"


def _truth(value:Any)->str:
    item=str(value or "UNKNOWN").strip().upper()
    return item if item in TRUTH_STATES else "UNKNOWN"


def new_event(
    event_type:Any,
    message:Any,
    *,
    severity:Any="INFO",
    source:Any="AION",
    truth_state:Any="CONFIRMED",
    evidence:Mapping[str,Any]|None=None,
    created_at:str|None=None,
)->dict[str,Any]:
    created=str(created_at or _now())
    event_type_clean=redact_text(event_type).strip()[:120] or "event"
    message_clean=redact_text(message).strip()[:1200]
    evidence_clean={}
    if isinstance(evidence,Mapping):
        for key,value in list(evidence.items())[:20]:
            evidence_clean[redact_text(key)[:80]]=redact_text(value)[:700]
    seed=json.dumps(
        [event_type_clean,message_clean,created,evidence_clean],
        ensure_ascii=False,sort_keys=True,default=str,
    )
    return {
        "schema":SCHEMA,
        "event_id":"EV-"+hashlib.sha256(seed.encode("utf-8")).hexdigest()[:14].upper(),
        "event_type":event_type_clean,
        "message":message_clean,
        "severity":_severity(severity),
        "source":redact_text(source).strip()[:120] or "AION",
        "truth_state":_truth(truth_state),
        "evidence":evidence_clean,
        "created_at":created,
    }


def normalize_event(raw:Mapping[str,Any])->dict[str,Any]:
    if not isinstance(raw,Mapping):
        raise ValueError("invalid event")
    event=new_event(
        raw.get("event_type"),
        raw.get("message"),
        severity=raw.get("severity"),
        source=raw.get("source"),
        truth_state=raw.get("truth_state"),
        evidence=raw.get("evidence") if isinstance(raw.get("evidence"),Mapping) else {},
        created_at=str(raw.get("created_at") or _now()),
    )
    supplied=redact_text(raw.get("event_id")).strip()[:64]
    if supplied:
        event["event_id"]=supplied
    return event


def normalize_events(events:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(events or [])[-MAX_EVENTS*2:]:
        try:
            event=normalize_event(raw)
        except Exception:
            continue
        eid=event["event_id"]
        if eid in seen:
            continue
        seen.add(eid)
        out.append(event)
    return out[-MAX_EVENTS:]


def append_event(
    events:Sequence[Mapping[str,Any]]|None,
    event:Mapping[str,Any],
)->list[dict[str,Any]]:
    out=normalize_events(events)
    item=normalize_event(event)
    if all(x["event_id"]!=item["event_id"] for x in out):
        out.append(item)
    return out[-MAX_EVENTS:]


def observability_summary(
    events:Sequence[Mapping[str,Any]]|None,
)->dict[str,Any]:
    rows=normalize_events(events)
    by_severity={key:0 for key in SEVERITIES}
    by_truth={key:0 for key in TRUTH_STATES}
    for row in rows:
        by_severity[row["severity"]]+=1
        by_truth[row["truth_state"]]+=1
    important=[
        x for x in reversed(rows)
        if x["severity"] in {"WARNING","ERROR","CRITICAL"}
    ][:8]
    return {
        "schema":SCHEMA,
        "total":len(rows),
        "by_severity":by_severity,
        "by_truth":by_truth,
        "important_recent":important,
        "latest":rows[-1] if rows else None,
    }


def events_digest(events:Sequence[Mapping[str,Any]]|None)->str:
    raw=json.dumps(normalize_events(events),ensure_ascii=False,sort_keys=True,default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
