"""AION audit/observability primitives.

Pure/offline helpers that redact common secret patterns before events are kept
in the mutable Checkpoint Mestre. These events are operational evidence, not a
remote logging service.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import hashlib
from itertools import islice
import json
import re
import unicodedata

SCHEMA="ATLASQUANT_AION_OBSERVABILITY_V1"
MAX_EVENTS=500
SEVERITIES=("INFO","NOTICE","WARNING","ERROR","CRITICAL")
TRUTH_STATES=("CONFIRMED","INFERENCE","HYPOTHESIS","UNKNOWN")

_SECRET_PATTERNS=(
    re.compile(r"(?i)\bBearer\s+[^\s,;\"']+"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?i)\b(password|passwd|senha|token|api[_-]?key|chave(?:[_ -]?de)?[_ -]?api|authorization|autorizacao|autorização|secret|segredo|cookie|credential|credencial|bearer)[\"']?\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;}]+)"),
)

# Substring families after letters-only normalization. Compound names such as
# client_secret and session_token match; bare "key" does not, so primary_key stays.
_SECRET_KEY=re.compile(
    r"password|passwd|senha|token|apikey|chavedeapi|privatekey|accesskey|authorization|autorizacao|secret|segredo|cookie|credential|credencial|bearer",
    re.I,
)


def is_secret_key(key:Any)->bool:
    """True when a field name belongs to a sensitive family, including compounds."""
    raw=unicodedata.normalize("NFKD",str(key or ""))
    ascii_name="".join(ch for ch in raw if not unicodedata.combining(ch))
    name=re.sub(r"[^a-z]","",ascii_name.lower())
    return bool(name) and _SECRET_KEY.search(name) is not None


def sanitize_metadata(value:Any, *, _depth:int=0)->Any:
    """Redact structured evidence before serialization, including short secrets."""
    if _depth>=12:
        return "[TRUNCATED]"
    if isinstance(value,Mapping):
        return {
            redact_text(key)[:80]: (
                "[REDACTED]" if is_secret_key(key)
                else sanitize_metadata(item,_depth=_depth+1)
            )
            for key,item in islice(value.items(), 100)
        }
    if isinstance(value,(list,tuple)):
        return [sanitize_metadata(item,_depth=_depth+1) for item in value[:100]]
    if isinstance(value,str):
        return redact_text(value)
    if value is None or isinstance(value,(bool,int,float)):
        return value
    return redact_text(value)


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
    request_id:Any="",
    task_id:Any="",
    domain:Any="",
    capability:Any="",
    tool:Any="",
    duration_ms:Any=None,
    result:Any="",
    risk:Any="",
    approval:Any="",
    fallback:Any="",
    confidence:Any=None,
)->dict[str,Any]:
    created=str(created_at or _now())
    event_type_clean=redact_text(event_type).strip()[:120] or "event"
    message_clean=redact_text(message).strip()[:1200]
    evidence_clean={}
    if isinstance(evidence,Mapping):
        for key,value in islice(sanitize_metadata(evidence).items(), 20):
            # Preserve the historical scalar representation for V17 digests.
            evidence_clean[key]=value if isinstance(value,(dict,list)) else redact_text(value)[:700]
    seed=json.dumps(
        [event_type_clean,message_clean,created,evidence_clean,redact_text(request_id),redact_text(task_id)],
        ensure_ascii=False,sort_keys=True,default=str,
    )
    try:
        duration=max(0.0,float(duration_ms)) if duration_ms is not None else None
    except Exception:
        duration=None
    try:
        confidence_value=max(0.0,min(100.0,float(confidence))) if confidence is not None else None
    except Exception:
        confidence_value=None
    # Empty correlation fields stay off the event. Checkpoints written before
    # the orchestration fields existed keep their digests; supplied correlation
    # is still stored and redacted.
    correlation={
        "request_id":redact_text(request_id).strip()[:120],
        "task_id":redact_text(task_id).strip()[:120],
        "domain":redact_text(domain).strip()[:80],
        "capability":redact_text(capability).strip()[:120],
        "tool":redact_text(tool).strip()[:120],
        "result":redact_text(result).strip()[:120],
        "risk":redact_text(risk).strip()[:40],
        "approval":redact_text(approval).strip()[:80],
        "fallback":redact_text(fallback).strip()[:120],
    }
    event={
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
    for key,value in correlation.items():
        if value:
            event[key]=value
    if duration is not None:
        event["duration_ms"]=duration
    if confidence_value is not None:
        event["confidence"]=confidence_value
    return event


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
        request_id=raw.get("request_id"),
        task_id=raw.get("task_id"),
        domain=raw.get("domain"),
        capability=raw.get("capability"),
        tool=raw.get("tool"),
        duration_ms=raw.get("duration_ms"),
        result=raw.get("result"),
        risk=raw.get("risk"),
        approval=raw.get("approval"),
        fallback=raw.get("fallback"),
        confidence=raw.get("confidence"),
    )
    supplied=redact_text(raw.get("event_id")).strip()[:64]
    if supplied:
        event["event_id"]=supplied
    return event


def normalize_events(events:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    source = (
        events[-MAX_EVENTS*2:]
        if isinstance(events, (list, tuple))
        else tuple(islice(events or (), MAX_EVENTS*2))
    )
    for raw in source:
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


def execution_event(
    *,
    request_id:Any,
    task_id:Any,
    domain:Any,
    capability:Any,
    status:Any,
    message:Any,
    tool:Any="",
    duration_ms:Any=None,
    risk:Any="",
    approved:bool=False,
    fallback:Any="",
    confidence:Any=None,
    error:Any="",
)->dict[str,Any]:
    """Create one correlated event without logging request/tool payloads."""
    evidence = {"error_type": redact_text(error).split(":", 1)[0][:120]} if error else {}
    severity = "ERROR" if error else "WARNING" if str(status).upper() in {"BLOCKED", "DEGRADED"} else "INFO"
    return new_event(
        "aion_execution",
        message,
        severity=severity,
        truth_state="CONFIRMED",
        evidence=evidence,
        request_id=request_id,
        task_id=task_id,
        domain=domain,
        capability=capability,
        tool=tool,
        duration_ms=duration_ms,
        result=status,
        risk=risk,
        approval="APPROVED" if approved else "NOT_APPROVED",
        fallback=fallback,
        confidence=confidence,
    )
