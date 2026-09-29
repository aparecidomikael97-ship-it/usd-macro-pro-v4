"""Adapters from the persisted AION Live Event Journal into safe Replay training.

The journal stores the latest merged event plus first/last-seen clocks. Because
later enrichment may have changed mutable fields, this adapter intentionally
uses only event identity fields that are stable enough for a point-in-time news
replay: event_id, headline, kind, reported_at and first_seen_at.

Fields such as current truth state, sources, currencies, urgency, alert level,
peak values, seen_count and last_seen_at are deliberately excluded from the
historical evidence frame because the journal does not preserve their earlier
versions.

No network, persistence, live action or trading occurs here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from atlasquant_aion_event_journal import normalize_events
from atlasquant_aion_replay import (
    compact_replay_rows,
    reveal_replay_outcome,
    start_replay_session,
    submit_replay_decision,
)


SCHEMA = "ATLASQUANT_AION_REPLAY_LAB_V1"
MAX_SCENARIOS = 50
MAX_FUTURE_EVENTS = 20


def _clean(value: Any, limit: int = 600) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _journal(checkpoint_or_journal: Mapping[str, Any] | None) -> dict[str, Any]:
    root = dict(checkpoint_or_journal or {})
    if isinstance(root.get("live_event_journal"), Mapping):
        return dict(root.get("live_event_journal") or {})
    return root


def _eligible_events(
    checkpoint_or_journal: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    journal = _journal(checkpoint_or_journal)
    rows = normalize_events(
        journal.get("events") if isinstance(journal.get("events"), list) else []
    )
    eligible: list[dict[str, Any]] = []
    for item in rows:
        stamp = _utc(item.get("first_seen_at"))
        event_id = _clean(item.get("event_id"), 120)
        headline = _clean(item.get("headline"), 600)
        if not stamp or not event_id or not headline:
            continue
        eligible.append(dict(item))
    eligible.sort(
        key=lambda item: (
            _utc(item.get("first_seen_at"))
            or datetime.min.replace(tzinfo=timezone.utc),
            _clean(item.get("event_id"), 120),
        )
    )
    return eligible


def news_replay_catalog(
    checkpoint_or_journal: Mapping[str, Any] | None,
    *,
    max_scenarios: Any = 30,
) -> dict[str, Any]:
    """Return replay-eligible journal events without claiming full snapshots."""
    if isinstance(max_scenarios, bool):
        limit = 30
    else:
        try:
            limit = int(max_scenarios)
        except (TypeError, ValueError):
            limit = 30
    limit = max(1, min(MAX_SCENARIOS, limit))

    events = _eligible_events(checkpoint_or_journal)
    rows = []
    for item in events[-limit:]:
        stamp = _utc(item.get("first_seen_at"))
        rows.append({
            "scenario_id": "NEWS-" + _clean(item.get("event_id"), 120),
            "event_id": _clean(item.get("event_id"), 120),
            "title": _clean(item.get("headline"), 600),
            "kind": _clean(item.get("kind"), 80) or "NEWS",
            "replay_at": stamp.isoformat() if stamp else "",
            "mode": "NEWS_REPLAY",
            "domain": "news",
            "point_in_time_basis": "LIVE_EVENT_JOURNAL_FIRST_SEEN_AT",
            "full_historical_snapshot_available": False,
            "training_only": True,
            "real_trading_enabled": False,
        })

    return {
        "schema": SCHEMA,
        "state": "READY" if rows else "NO_ELIGIBLE_SCENARIOS",
        "scenarios": rows,
        "scenario_count": len(rows),
        "uses_live_data": False,
        "fabricated_scenarios": False,
        "automatic_promotion": False,
        "executes_action": False,
        "real_trading_enabled": False,
        "limitations": (
            "The current journal is not a versioned field-by-field snapshot. "
            "Replay therefore exposes only stable event identity fields at first_seen_at."
        ),
    }


def _historical_record(item: Mapping[str, Any]) -> dict[str, Any] | None:
    stamp = _utc(item.get("first_seen_at"))
    event_id = _clean(item.get("event_id"), 120)
    headline = _clean(item.get("headline"), 600)
    kind = _clean(item.get("kind"), 80) or "NEWS"
    if not stamp or not event_id or not headline:
        return None
    return {
        "record_id": event_id,
        "knowledge_key": event_id,
        "kind": kind,
        "label": headline,
        "source": "live_event_journal",
        "truth_state": "UNKNOWN",
        "available_at": stamp.isoformat(),
        "payload": {
            "event_id": event_id,
            "headline": headline,
            "kind": kind,
            "reported_at": _clean(item.get("reported_at"), 120),
            "historical_fields_limited": True,
        },
    }


def build_news_replay_package(
    checkpoint_or_journal: Mapping[str, Any] | None,
    *,
    event_id: Any,
    outcome_window_minutes: Any = 240,
) -> dict[str, Any]:
    """Build one journal-backed replay package and a hidden later-events outcome."""
    target_id = _clean(event_id, 120)
    events = _eligible_events(checkpoint_or_journal)
    target = next(
        (item for item in events if _clean(item.get("event_id"), 120) == target_id),
        None,
    )
    if target is None:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "reason": "SCENARIO_NOT_FOUND",
            "session": None,
            "outcome": None,
            "training_only": True,
            "executes_action": False,
            "real_trading_enabled": False,
        }

    cutoff = _utc(target.get("first_seen_at"))
    if cutoff is None:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "reason": "SCENARIO_TIME_INVALID",
            "session": None,
            "outcome": None,
            "training_only": True,
            "executes_action": False,
            "real_trading_enabled": False,
        }

    if isinstance(outcome_window_minutes, bool):
        window_minutes = 240
    else:
        try:
            window_minutes = int(outcome_window_minutes)
        except (TypeError, ValueError):
            window_minutes = 240
    window_minutes = max(15, min(24 * 60, window_minutes))
    window_end = cutoff + timedelta(minutes=window_minutes)

    past_records = []
    future_events = []
    for item in events:
        stamp = _utc(item.get("first_seen_at"))
        if stamp is None:
            continue
        if stamp <= cutoff:
            row = _historical_record(item)
            if row is not None:
                past_records.append(row)
        elif stamp <= window_end and len(future_events) < MAX_FUTURE_EVENTS:
            future_events.append({
                "event_id": _clean(item.get("event_id"), 120),
                "headline": _clean(item.get("headline"), 600),
                "kind": _clean(item.get("kind"), 80) or "NEWS",
                "first_seen_at": stamp.isoformat(),
            })

    session = start_replay_session(
        scenario_id="NEWS-" + target_id,
        title=_clean(target.get("headline"), 600),
        domain="news",
        mode="NEWS_REPLAY",
        replay_at=cutoff.isoformat(),
        records=past_records,
    )

    first_future = (
        _utc(future_events[0].get("first_seen_at"))
        if future_events
        else None
    )
    outcome = None
    if first_future is not None:
        outcome = {
            "available_at": first_future.isoformat(),
            "payload": {
                "later_events": future_events,
                "window_minutes": window_minutes,
                "comparison_kind": "SUBSEQUENT_JOURNAL_EVENTS",
            },
        }

    return {
        "schema": SCHEMA,
        "state": "READY" if session.get("state") == "ACTIVE" else "BLOCKED",
        "reason": session.get("reason") or "",
        "session": session,
        "outcome": outcome,
        "visible_rows": compact_replay_rows(session.get("frame")),
        "later_event_count": len(future_events),
        "outcome_available": bool(outcome),
        "full_historical_snapshot_available": False,
        "mutable_journal_enrichment_exposed": False,
        "training_only": True,
        "uses_live_data": False,
        "automatic_promotion": False,
        "executes_action": False,
        "real_trading_enabled": False,
    }


def submit_news_replay_decision(
    session: Mapping[str, Any] | None,
    *,
    choice: Any,
    rationale: Any,
    confidence_pct: Any,
    submitted_at: Any,
) -> dict[str, Any]:
    return submit_replay_decision(
        session,
        choice=choice,
        rationale=rationale,
        confidence_pct=confidence_pct,
        submitted_at=submitted_at,
    )


def reveal_news_replay_outcome(
    session: Mapping[str, Any] | None,
    outcome_package: Mapping[str, Any] | None,
    *,
    revealed_at: Any,
) -> dict[str, Any]:
    package = dict(outcome_package or {})
    available_at = package.get("available_at")
    payload = (
        package.get("payload")
        if isinstance(package.get("payload"), Mapping)
        else {}
    )
    if not available_at or not payload:
        current = dict(session or {})
        current["state"] = "BLOCKED"
        current["reason"] = "NO_LATER_EVENT_EVIDENCE"
        current["training_only"] = True
        current["uses_live_data"] = False
        current["automatic_promotion"] = False
        current["execution_authorized"] = False
        current["executes_action"] = False
        current["real_trading_enabled"] = False
        return current
    return reveal_replay_outcome(
        session,
        outcome=payload,
        available_at=available_at,
        revealed_at=revealed_at,
    )


__all__ = [
    "SCHEMA",
    "news_replay_catalog",
    "build_news_replay_package",
    "submit_news_replay_decision",
    "reveal_news_replay_outcome",
]
