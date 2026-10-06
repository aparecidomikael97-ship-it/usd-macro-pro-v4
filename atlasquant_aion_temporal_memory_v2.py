"""AION Temporal Project Memory V2.

Pure, evidence-bound project-history index. It does not write runtime state, call
providers, execute tools, infer missing history, or grant authority.

The model is deliberately temporal: an item may be valid at one historical
instant and later be superseded. Queries expose both "as of" and current status.
Missing or conflicting evidence stays explicit rather than being filled in.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
from typing import Any, Iterable, Mapping, Sequence
import json

SCHEMA = "ATLASQUANT_AION_TEMPORAL_PROJECT_MEMORY_V2"
EVENT_KINDS = frozenset({
    "DECISION", "REQUIREMENT", "SUGGESTION", "IMPLEMENTATION", "VALIDATION",
    "PENDING", "BLOCKER", "CORRECTION", "SUPERSESSION", "CHECKPOINT",
})
STATES = frozenset({
    "DECIDED", "IMPLEMENTED", "VALIDATED", "PENDING", "BLOCKED",
    "SUPERSEDED", "REJECTED", "UNKNOWN",
})
TRUTH_STATES = frozenset({"CONFIRMED", "INFERENCE", "UNKNOWN", "CONFLICT"})
MAX_EVENTS = 20000
MAX_REFS = 100


def _text(value: Any, limit: int = 1600) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _date(value: Any) -> str:
    text = _text(value, 40)
    if not text:
        return ""
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return ""


def _timestamp(value: Any) -> str:
    text = _text(value, 80)
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _refs(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:MAX_REFS]:
        ref = _text(raw, 500)
        if ref and ref not in out:
            out.append(ref)
    return out


def normalize_event(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("temporal event must be an object")
    event_id = _text(raw.get("event_id"), 160)
    if not event_id:
        raise ValueError("event_id required")
    event_date = _date(raw.get("date"))
    if not event_date:
        raise ValueError("valid ISO date required")
    kind = _text(raw.get("kind"), 40).upper()
    state = _text(raw.get("state"), 40).upper()
    truth = _text(raw.get("truth_state"), 40).upper()
    if kind not in EVENT_KINDS:
        raise ValueError("invalid event kind")
    if state not in STATES:
        raise ValueError("invalid event state")
    if truth not in TRUTH_STATES:
        raise ValueError("invalid truth state")

    title = _text(raw.get("title"), 300)
    summary = _text(raw.get("summary"), 2400)
    refs = _refs(raw.get("evidence_refs"))
    if truth == "CONFIRMED" and not refs:
        raise ValueError("confirmed temporal event requires evidence")
    if not title or not summary:
        raise ValueError("title and summary required")

    supersedes = _refs(raw.get("supersedes"))
    superseded_by = _refs(raw.get("superseded_by"))
    if event_id in supersedes or event_id in superseded_by:
        raise ValueError("event cannot supersede itself")

    row = {
        "schema": SCHEMA,
        "event_id": event_id,
        "date": event_date,
        "observed_at": _timestamp(raw.get("observed_at")),
        "kind": kind,
        "state": state,
        "truth_state": truth,
        "domain": _text(raw.get("domain"), 120).lower(),
        "topic": _text(raw.get("topic"), 240).lower(),
        "title": title,
        "summary": summary,
        "authority": _text(raw.get("authority"), 120),
        "source_type": _text(raw.get("source_type"), 120).upper(),
        "evidence_refs": refs,
        "supersedes": supersedes,
        "superseded_by": superseded_by,
        "current_relevance": _text(raw.get("current_relevance"), 80).upper() or "ACTIVE",
        "notes": _text(raw.get("notes"), 1200),
        "grants_authority": False,
        "executes_action": False,
        "runtime_write": False,
    }
    row["event_digest"] = _digest({k: v for k, v in row.items() if k != "event_digest"})
    return row


def build_timeline(events: Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    source = list(events or [])
    if len(source) > MAX_EVENTS:
        raise ValueError("temporal event limit exceeded")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in source:
        row = normalize_event(raw)
        if row["event_id"] in seen:
            raise ValueError("duplicate temporal event_id")
        seen.add(row["event_id"])
        normalized.append(row)

    known = set(seen)
    relationship_errors: list[str] = []
    for row in normalized:
        for ref in row["supersedes"] + row["superseded_by"]:
            if ref not in known:
                relationship_errors.append(f"UNKNOWN_RELATION:{row['event_id']}:{ref}")

    normalized.sort(key=lambda x: (x["date"], x["observed_at"], x["event_id"]))
    coverage_dates = sorted({x["date"] for x in normalized})
    return {
        "schema": SCHEMA,
        "state": "READY" if not relationship_errors else "BLOCKED",
        "blockers": relationship_errors,
        "event_count": len(normalized),
        "coverage_start": coverage_dates[0] if coverage_dates else "",
        "coverage_end": coverage_dates[-1] if coverage_dates else "",
        "coverage_dates": coverage_dates,
        "events": normalized,
        "timeline_digest": _digest(normalized),
        "complete_history_claimed": False,
        "missing_history_must_be_unknown": True,
        "grants_authority": False,
        "executes_action": False,
        "runtime_write": False,
    }


def _matches_text(row: Mapping[str, Any], value: str) -> bool:
    needle = value.casefold()
    haystack = " ".join(str(row.get(k) or "") for k in ("domain", "topic", "title", "summary"))
    return needle in haystack.casefold()


def query_timeline(
    timeline: Mapping[str, Any],
    *,
    exact_date: str = "",
    start_date: str = "",
    end_date: str = "",
    topic: str = "",
    domain: str = "",
    state: str = "",
    kind: str = "",
    source_type: str = "",
    include_superseded: bool = True,
) -> dict[str, Any]:
    if timeline.get("schema") != SCHEMA or not isinstance(timeline.get("events"), list):
        raise ValueError("invalid temporal timeline")
    if timeline.get("state") != "READY":
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "blockers": list(timeline.get("blockers") or ["TIMELINE_NOT_READY"]),
            "results": [],
            "result_count": 0,
            "grants_authority": False,
            "executes_action": False,
        }

    exact = _date(exact_date) if exact_date else ""
    start = _date(start_date) if start_date else ""
    end = _date(end_date) if end_date else ""
    if exact_date and not exact:
        raise ValueError("invalid exact_date")
    if start_date and not start:
        raise ValueError("invalid start_date")
    if end_date and not end:
        raise ValueError("invalid end_date")
    if start and end and start > end:
        raise ValueError("start_date after end_date")

    wanted_state = _text(state, 40).upper()
    wanted_kind = _text(kind, 40).upper()
    wanted_source = _text(source_type, 120).upper()
    wanted_domain = _text(domain, 120).lower()
    results: list[dict[str, Any]] = []
    for row in timeline["events"]:
        d = row["date"]
        if exact and d != exact:
            continue
        if start and d < start:
            continue
        if end and d > end:
            continue
        if topic and not _matches_text(row, topic):
            continue
        if wanted_domain and row.get("domain") != wanted_domain:
            continue
        if wanted_state and row.get("state") != wanted_state:
            continue
        if wanted_kind and row.get("kind") != wanted_kind:
            continue
        if wanted_source and row.get("source_type") != wanted_source:
            continue
        if not include_superseded and row.get("state") == "SUPERSEDED":
            continue
        results.append(dict(row))

    return {
        "schema": SCHEMA,
        "state": "FOUND" if results else "UNKNOWN",
        "query": {
            "exact_date": exact,
            "start_date": start,
            "end_date": end,
            "topic": _text(topic, 240),
            "domain": wanted_domain,
            "state": wanted_state,
            "kind": wanted_kind,
            "source_type": wanted_source,
            "include_superseded": include_superseded is True,
        },
        "results": results,
        "result_count": len(results),
        "unknown_means_no_ingested_evidence": not bool(results),
        "grants_authority": False,
        "executes_action": False,
    }


def legacy_commitments_to_events(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Convert the V1 historical commitments manifest without inventing state."""
    out: list[dict[str, Any]] = []
    for raw in list(manifest.get("commitments") or []):
        if not isinstance(raw, Mapping):
            continue
        state_text = _text(raw.get("state"), 120).upper()
        if raw.get("validated") is True:
            state = "VALIDATED"
        elif raw.get("implemented") is True:
            state = "IMPLEMENTED"
        elif "BLOQUE" in state_text or "BLOCK" in state_text:
            state = "BLOCKED"
        elif "PEND" in state_text:
            state = "PENDING"
        elif "SUBSTIT" in state_text or "SUPERSED" in state_text:
            state = "SUPERSEDED"
        else:
            state = "DECIDED"
        refs = _refs(raw.get("evidence"))
        truth = "CONFIRMED" if refs else "UNKNOWN"
        out.append({
            "event_id": _text(raw.get("id"), 160),
            "date": _date(raw.get("source_date")),
            "kind": "REQUIREMENT",
            "state": state,
            "truth_state": truth,
            "domain": _text(raw.get("domain"), 120),
            "topic": _text(raw.get("title"), 240),
            "title": _text(raw.get("title"), 300),
            "summary": _text(raw.get("summary"), 2400),
            "authority": "HISTORICAL_CHECKPOINT",
            "source_type": "LEGACY_COMMITMENT",
            "evidence_refs": refs,
            "supersedes": [],
            "superseded_by": [],
            "current_relevance": "ACTIVE" if state != "SUPERSEDED" else "SUPERSEDED",
        })
    return [normalize_event(row) for row in out if row.get("event_id") and row.get("date")]


__all__ = [
    "SCHEMA", "EVENT_KINDS", "STATES", "TRUTH_STATES", "normalize_event",
    "build_timeline", "query_timeline", "legacy_commitments_to_events",
]
