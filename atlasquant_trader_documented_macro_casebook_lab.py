"""Read-only real-document macro event CASEBOOK, research timing only.

Documented public facts are not point-in-time historical receipts. This code
will not recast a past statement as a forecast available before research, nor
treat an expired calendar row as the actual published result.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping
from urllib.parse import urlsplit

SCHEMA = "ATLASQUANT_TRADER_DOCUMENTED_MACRO_EVENTS_CASEBOOK_LAB_V1"
INPUT_FIELDS = frozenset((
    "schema", "state", "research_day_utc", "usable_from_utc",
    "real_historical_capture_attested", "event_specific_consensus_verified",
    "prices_to_measure_reaction_verified", "source_redistribution_rights_verified",
    "events",
))
EVENT_FIELDS = frozenset((
    "event_id", "currency", "topic", "phase", "reference_period",
    "official_url", "official_release_at_utc", "scheduled_at_utc",
    "timing_note", "facts", "consensus_before_release",
    "published_at_utc_attested",
))
VALID_SOURCE_HOSTS = {
    ("USD", "INFLATION"): "www.bls.gov",
    ("USD", "EMPLOYMENT"): "www.bls.gov",
    ("USD", "POLICY"): "www.federalreserve.gov",
    ("EUR", "POLICY"): "www.ecb.europa.eu",
}


def _timestamp(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not 20 <= len(raw) <= 40:
        return None
    if not (raw.endswith("Z") or raw.endswith("+00:00")):
        return None
    try:
        x = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return x.astimezone(timezone.utc) if x.utcoffset() == timedelta(0) else None


def _official_document(url: Any, host: str) -> bool:
    if not isinstance(url, str) or not 12 <= len(url) <= 1024:
        return False
    try:
        x = urlsplit(url)
        return (x.scheme == "https" and x.hostname == host
                and x.username is None and x.password is None
                and x.port in (None, 443) and not x.fragment
                and x.path not in ("", "/")
                and not any(z.isspace() for z in url))
    except ValueError:
        return False


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_MACRO_CASEBOOK_REFUSED",
        "reason": reason, "past_research": [], "upcoming_watch": [],
        "expired_calendar": [],
        "real_historical_receipt_attested": False,
        "real_point_in_time_consensus_attested": False,
        "actual_vs_expected_surprise_computed": False,
        "market_impact_direction": "UNDETERMINED",
        "real_oos_authorized": False, "can_feed_live_radar": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False,
    }


def inspect_documented_macro_casebook_lab(
    book: Any, *, asof_utc: datetime,
) -> dict[str, Any]:
    """Display documentary context AFTER research day, never past OOS data."""
    if not isinstance(asof_utc, datetime) or asof_utc.tzinfo is None:
        raise ValueError("Explicit timezone-aware as-of required")
    asof = asof_utc.astimezone(timezone.utc)
    if not isinstance(book, Mapping) or set(book) != INPUT_FIELDS:
        return _deny("Manifest has missing, unexpected or retrospective fields")
    if (book["schema"] != SCHEMA
            or book["state"] != "PUBLIC_OFFICIAL_DOCUMENT_RESEARCH_NO_HISTORICAL_CUSTODY"):
        return _deny("Unsupported book state")
    if any(book[key] is not False for key in (
        "real_historical_capture_attested", "event_specific_consensus_verified",
        "prices_to_measure_reaction_verified", "source_redistribution_rights_verified",
    )):
        return _deny("Caller cannot promote unverified research to real evidence")
    try:
        day = date.fromisoformat(book["research_day_utc"])
    except (ValueError, TypeError):
        return _deny("Invalid research day")
    usable = _timestamp(book["usable_from_utc"])
    if usable is None or usable != datetime.combine(day + timedelta(days=1), datetime.min.time(), timezone.utc):
        return _deny("Date-only research is conservatively usable next UTC day")
    if asof < usable:
        return _deny("Research not attested before requested historical as-of")
    items = book["events"]
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        return _deny("Bounded events required")
    past, upcoming, expired, ids = [], [], [], set()
    for item in items:
        if not isinstance(item, Mapping) or set(item) != EVENT_FIELDS:
            return _deny("Unexpected event fields")
        eid = item["event_id"]
        if (not isinstance(eid, str) or not 5 <= len(eid) <= 90
                or eid in ids):
            return _deny("Missing or repeated event ID")
        ids.add(eid)
        host = VALID_SOURCE_HOSTS.get((item["currency"], item["topic"])) if (
            isinstance(item["currency"], str) and isinstance(item["topic"], str)
        ) else None
        if host is None or not _official_document(item["official_url"], host):
            return _deny("Source family or official document host mismatch")
        if (item["phase"] not in ("SCHEDULED", "RELEASED_CONTEXT")
                or item["consensus_before_release"] is not None
                or item["published_at_utc_attested"] is not False
                or not isinstance(item["timing_note"], str)
                or not 12 <= len(item["timing_note"]) <= 300):
            return _deny("Event must expose missing consensus, custody and timing limits")
        ref_period = item["reference_period"]
        if (not isinstance(ref_period, str) or len(ref_period) != 7
                or ref_period[4] != "-" or not ref_period[:4].isdigit()
                or not ref_period[5:].isdigit()
                or not 1 <= int(ref_period[5:]) <= 12):
            return _deny("Invalid reference period")
        scheduled, released = _timestamp(item["scheduled_at_utc"]), _timestamp(item["official_release_at_utc"])
        if item["scheduled_at_utc"] is not None and scheduled is None:
            return _deny("Bad schedule UTC")
        if item["official_release_at_utc"] is not None and released is None:
            return _deny("Bad announced release UTC")
        facts = item["facts"]
        if not isinstance(facts, Mapping) or len(facts) > 12:
            return _deny("Facts must be bounded")
        if item["phase"] == "SCHEDULED":
            if scheduled is None or released is not None or facts:
                return _deny("Upcoming event has actual figures or missing schedule")
            if scheduled <= usable:
                return _deny("Research already showed expired scheduled event")
            (upcoming if scheduled > asof else expired).append({
                "event_id": eid, "currency": item["currency"], "topic": item["topic"],
                "scheduled_at_utc": scheduled.isoformat(), "source_url": item["official_url"],
                "status": "FUTURE_CATALYST_UNVERIFIED" if scheduled > asof
                          else "PAST_DUE_NEW_RELEASE_REQUIRED",
                "event_consensus": None, "actual": None,
                "macro_direction": "UNDETERMINED",
            })
        else:
            if not facts or (released is not None and released > usable):
                return _deny("Historic facts unavailable by research day")
            if scheduled is not None and released is not None and scheduled > released:
                return _deny("Decision before advertised release")
            past.append({
                "event_id": eid, "currency": item["currency"], "topic": item["topic"],
                "official_release_clock": released.isoformat() if released else None,
                "source_url": item["official_url"],
                "status": "RETROSPECTIVE_PUBLIC_DOCUMENT_RESEARCH",
                "facts": dict(facts), "event_consensus": None,
                "macro_direction": "UNDETERMINED",
            })
    return {
        **_deny(""),
        "state": "LAB_DOCUMENTED_MACRO_WATCH_NO_PIT_CUSTODY",
        "reason": "Public-source research without historical capture or consensus",
        "research_day_utc": day.isoformat(),
        "asof_utc": asof.isoformat(),
        "past_research": past, "upcoming_watch": upcoming,
        "expired_calendar": expired,
    }


__all__ = ["SCHEMA", "inspect_documented_macro_casebook_lab"]
